"""End-to-end combination tests.

Semi-randomly generates valid project files that permute estimation types,
units, configuration options, dependency structures, and risk setups.
Each generated project is parsed, simulated, and checked against universal
invariants that must hold for any valid project.

The key correctness check is **deterministic bounds verification**: for every
project we compute the theoretical minimum and maximum project duration by
walking the dependency graph with best-case and worst-case task durations.
Every simulated iteration must fall within those bounds.  For triangular
distributions these bounds are exact (hard limits of the distribution); for
lognormal distributions a conservative statistical envelope is used.

The test matrix is driven by ``DIMENSIONS`` — every axis of variation is
listed once, and a seeded RNG draws N combinations. This keeps the suite
deterministic (same seed → same projects → same results) while covering
far more combinations than hand-written cases ever could.
"""

from __future__ import annotations

import math
import itertools
import random
from typing import Any

import numpy as np
import pytest
import yaml

from mcprojsim.config import Config, EffortUnit
from mcprojsim.models.project import (
    DistributionType,
    Project,
    Risk,
    Task,
    convert_to_hours,
)
from mcprojsim.parsers.yaml_parser import YAMLParser
from mcprojsim.simulation.distributions import (
    LOGNORMAL_BOUNDARY_SIGMA_MULTIPLIER,
    fit_shifted_lognormal,
)
from mcprojsim.simulation.engine import SimulationEngine
from mcprojsim.simulation.scheduler import TaskScheduler

# ---------------------------------------------------------------------------
# Dimension definitions
# ---------------------------------------------------------------------------

ESTIMATE_TYPES = ["triangular", "lognormal", "t_shirt", "story_points"]

EXPLICIT_UNITS = [None, "hours", "days", "weeks"]  # None → default (hours)

T_SHIRT_SIZES = ["XS", "S", "M", "L", "XL", "XXL"]

STORY_POINT_VALUES = [1, 2, 3, 5, 8, 13, 21]

CONFIG_T_SHIRT_UNITS = ["hours", "days", "weeks"]

CONFIG_SP_UNITS = ["hours", "days", "weeks"]

HOURS_PER_DAY_OPTIONS = [6.0, 8.0, 10.0]

DEPENDENCY_STRUCTURES = ["none", "linear", "diamond", "fan_out"]

RISK_SETUPS = [
    "none",
    "task_plain",  # plain numeric impact (hours)
    "task_structured",  # RiskImpact with explicit unit
    "task_percentage",  # percentage impact
    "project_plain",
    "project_structured",
    "project_percentage",
    "both_plain",  # task + project, plain
]

UNCERTAINTY_PRESETS = [
    None,  # no uncertainty factors
    {"team_experience": "high", "requirements_maturity": "high"},
    {"team_experience": "low", "technical_complexity": "high"},
    {"team_distribution": "distributed", "integration_complexity": "high"},
]


# ---------------------------------------------------------------------------
# Project generator
# ---------------------------------------------------------------------------


class ProjectSpec:
    """Immutable description of one generated project scenario."""

    def __init__(
        self,
        *,
        task_specs: list[dict[str, Any]],
        dep_structure: str,
        risk_setup: str,
        hours_per_day: float,
        config_tshirt_unit: str,
        config_sp_unit: str,
        uncertainty: dict[str, str] | None,
        seed: int,
    ):
        self.task_specs = task_specs
        self.dep_structure = dep_structure
        self.risk_setup = risk_setup
        self.hours_per_day = hours_per_day
        self.config_tshirt_unit = config_tshirt_unit
        self.config_sp_unit = config_sp_unit
        self.uncertainty = uncertainty
        self.seed = seed

    @property
    def label(self) -> str:
        types = "+".join(t["type"] for t in self.task_specs)
        return (
            f"tasks={types} deps={self.dep_structure} "
            f"risk={self.risk_setup} hpd={self.hours_per_day} "
            f"ts_unit={self.config_tshirt_unit} sp_unit={self.config_sp_unit} "
            f"seed={self.seed}"
        )


def _make_estimate(spec: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    """Build an estimate dict for a YAML task definition."""
    etype = spec["type"]

    if etype == "triangular":
        low = round(rng.uniform(0.5, 5.0), 1)
        mid = round(low + rng.uniform(0.5, 5.0), 1)
        high = round(mid + rng.uniform(0.5, 10.0), 1)
        est: dict[str, Any] = {"low": low, "expected": mid, "high": high}
        if spec.get("unit") is not None:
            est["unit"] = spec["unit"]
        return est

    if etype == "lognormal":
        low = round(rng.uniform(0.5, 5.0), 1)
        expected = round(low + rng.uniform(0.5, 5.0), 1)
        high = round(expected + rng.uniform(0.5, 10.0), 1)
        est = {
            "distribution": "lognormal",
            "low": low,
            "expected": expected,
            "high": high,
        }
        if spec.get("unit") is not None:
            est["unit"] = spec["unit"]
        return est

    if etype == "t_shirt":
        return {"t_shirt_size": spec["size"]}

    if etype == "story_points":
        return {"story_points": spec["sp_value"]}

    raise ValueError(f"Unknown estimate type: {etype}")


def _make_risks(risk_setup: str, rng: random.Random) -> tuple[list, list]:
    """Return (task_risks, project_risks) for the given setup."""
    task_risks: list[dict[str, Any]] = []
    project_risks: list[dict[str, Any]] = []

    def _plain() -> dict:
        return {
            "id": f"risk_{rng.randint(1, 9999):04d}",
            "name": "test risk",
            "probability": round(rng.uniform(0.05, 0.5), 2),
            "impact": round(rng.uniform(0.5, 8.0), 1),
        }

    def _structured(unit: str | None = None) -> dict:
        impact: dict[str, Any] = {
            "type": "absolute",
            "value": round(rng.uniform(1.0, 10.0), 1),
        }
        if unit:
            impact["unit"] = unit
        return {
            "id": f"risk_{rng.randint(1, 9999):04d}",
            "name": "test risk",
            "probability": round(rng.uniform(0.05, 0.5), 2),
            "impact": impact,
        }

    def _percentage() -> dict:
        return {
            "id": f"risk_{rng.randint(1, 9999):04d}",
            "name": "test risk",
            "probability": round(rng.uniform(0.05, 0.5), 2),
            "impact": {"type": "percentage", "value": round(rng.uniform(5, 30), 1)},
        }

    makers = {
        "task_plain": (lambda: task_risks.append(_plain()), None),
        "task_structured": (
            lambda: task_risks.append(
                _structured(rng.choice(["hours", "days", "weeks"]))
            ),
            None,
        ),
        "task_percentage": (lambda: task_risks.append(_percentage()), None),
        "project_plain": (None, lambda: project_risks.append(_plain())),
        "project_structured": (
            None,
            lambda: project_risks.append(
                _structured(rng.choice(["hours", "days", "weeks"]))
            ),
        ),
        "project_percentage": (None, lambda: project_risks.append(_percentage())),
        "both_plain": (
            lambda: task_risks.append(_plain()),
            lambda: project_risks.append(_plain()),
        ),
    }

    if risk_setup != "none":
        task_fn, proj_fn = makers[risk_setup]
        if task_fn:
            task_fn()
        if proj_fn:
            proj_fn()

    return task_risks, project_risks


def _apply_dep_structure(tasks: list[dict[str, Any]], structure: str) -> None:
    """Mutate *tasks* in-place to add dependency links."""
    n = len(tasks)
    for t in tasks:
        t.setdefault("dependencies", [])

    if structure == "none" or n < 2:
        return

    if structure == "linear":
        for i in range(1, n):
            tasks[i]["dependencies"] = [tasks[i - 1]["id"]]

    elif structure == "diamond":
        # First task is root; middle tasks depend on root; last depends on all middle.
        for i in range(1, n - 1):
            tasks[i]["dependencies"] = [tasks[0]["id"]]
        if n > 2:
            tasks[-1]["dependencies"] = [t["id"] for t in tasks[1:-1]]

    elif structure == "fan_out":
        # All tasks after the first depend on the first.
        for i in range(1, n):
            tasks[i]["dependencies"] = [tasks[0]["id"]]


def build_project_data(spec: ProjectSpec, rng: random.Random) -> tuple[dict, dict]:
    """Build (project_data, config_data) dicts ready for YAML serialization."""

    # -- tasks ---------------------------------------------------------------
    tasks: list[dict[str, Any]] = []
    task_risks, project_risks = _make_risks(spec.risk_setup, rng)

    for i, tspec in enumerate(spec.task_specs):
        task: dict[str, Any] = {
            "id": f"t{i + 1:03d}",
            "name": f"Task {i + 1}",
            "estimate": _make_estimate(tspec, rng),
            "dependencies": [],
        }
        if spec.uncertainty:
            task["uncertainty_factors"] = dict(spec.uncertainty)
        # Attach task-level risks to the first task only.
        if i == 0 and task_risks:
            task["risks"] = task_risks
        tasks.append(task)

    _apply_dep_structure(tasks, spec.dep_structure)

    project_data: dict[str, Any] = {
        "project": {
            "name": f"combo-{spec.seed}",
            "start_date": "2026-03-01",
            "hours_per_day": spec.hours_per_day,
            "confidence_levels": [50, 80, 90, 95],
        },
        "tasks": tasks,
    }
    if project_risks:
        project_data["project_risks"] = project_risks

    # -- config --------------------------------------------------------------
    config_data: dict[str, Any] = {
        "t_shirt_size_unit": spec.config_tshirt_unit,
        "story_point_unit": spec.config_sp_unit,
    }

    return project_data, config_data


# ---------------------------------------------------------------------------
# Scenario generator
# ---------------------------------------------------------------------------


def _random_task_specs(
    rng: random.Random,
    *,
    count: int,
    force_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Generate *count* task spec dicts.

    If *force_types* is given, the first len(force_types) tasks use those
    types; remaining tasks are random.
    """
    specs: list[dict[str, Any]] = []
    for i in range(count):
        if force_types and i < len(force_types):
            etype = force_types[i]
        else:
            etype = rng.choice(ESTIMATE_TYPES)

        tspec: dict[str, Any] = {"type": etype}

        if etype in ("triangular", "lognormal"):
            tspec["unit"] = rng.choice(EXPLICIT_UNITS)
        elif etype == "t_shirt":
            tspec["size"] = rng.choice(T_SHIRT_SIZES)
        elif etype == "story_points":
            tspec["sp_value"] = rng.choice(STORY_POINT_VALUES)

        specs.append(tspec)
    return specs


def generate_scenarios(
    n: int = 300,
    master_seed: int = 20260309,
) -> list[ProjectSpec]:
    """Generate *n* diverse project scenarios.

    The first batch covers every estimation type in isolation plus pairwise
    mixes. The remaining budget is filled with fully random combinations.
    """
    rng = random.Random(master_seed)
    scenarios: list[ProjectSpec] = []
    seed_counter = itertools.count(1)

    def _new_spec(
        task_specs: list[dict[str, Any]],
        dep_structure: str | None = None,
        risk_setup: str | None = None,
        hours_per_day: float | None = None,
        config_tshirt_unit: str | None = None,
        config_sp_unit: str | None = None,
        uncertainty: dict[str, str] | None = None,
    ) -> ProjectSpec:
        return ProjectSpec(
            task_specs=task_specs,
            dep_structure=dep_structure or rng.choice(DEPENDENCY_STRUCTURES),
            risk_setup=risk_setup or rng.choice(RISK_SETUPS),
            hours_per_day=hours_per_day or rng.choice(HOURS_PER_DAY_OPTIONS),
            config_tshirt_unit=config_tshirt_unit or rng.choice(CONFIG_T_SHIRT_UNITS),
            config_sp_unit=config_sp_unit or rng.choice(CONFIG_SP_UNITS),
            uncertainty=uncertainty,
            seed=next(seed_counter),
        )

    # --- Phase 1: systematic coverage of each type in isolation ------------
    for etype in ESTIMATE_TYPES:
        for unit_combo in _unit_combos_for(etype):
            specs = _random_task_specs(rng, count=3, force_types=[etype] * 3)
            # override unit for explicit types
            if etype in ("triangular", "lognormal"):
                for s in specs:
                    s["unit"] = unit_combo["explicit_unit"]
            scenarios.append(
                _new_spec(
                    specs,
                    config_tshirt_unit=unit_combo.get("ts_unit"),
                    config_sp_unit=unit_combo.get("sp_unit"),
                )
            )

    # --- Phase 2: pairwise type mixes -------------------------------------
    for a, b in itertools.combinations(ESTIMATE_TYPES, 2):
        specs = _random_task_specs(rng, count=4, force_types=[a, b, a, b])
        scenarios.append(_new_spec(specs))

    # --- Phase 3: all four types in one project ----------------------------
    for _ in range(10):
        specs = _random_task_specs(rng, count=4, force_types=list(ESTIMATE_TYPES))
        scenarios.append(
            _new_spec(
                specs,
                uncertainty=rng.choice(UNCERTAINTY_PRESETS),
            )
        )

    # --- Phase 4: fill remaining budget with fully random combos -----------
    while len(scenarios) < n:
        task_count = rng.randint(2, 6)
        specs = _random_task_specs(rng, count=task_count)
        scenarios.append(
            _new_spec(
                specs,
                uncertainty=rng.choice(UNCERTAINTY_PRESETS),
            )
        )

    return scenarios[:n]


def _unit_combos_for(etype: str) -> list[dict[str, Any]]:
    """Return relevant unit combinations for a given estimate type.

    For explicit types → vary the explicit unit.
    For T-shirt → vary the config t_shirt_size_unit.
    For story points → vary the config story_point_unit.
    """
    if etype in ("triangular", "lognormal"):
        return [{"explicit_unit": u} for u in EXPLICIT_UNITS]

    if etype == "t_shirt":
        return [{"ts_unit": u} for u in CONFIG_T_SHIRT_UNITS]

    if etype == "story_points":
        return [{"sp_unit": u} for u in CONFIG_SP_UNITS]

    return [{}]


# ---------------------------------------------------------------------------
# Deterministic bounds computation
# ---------------------------------------------------------------------------


def _resolve_estimate_range(
    task: Task,
    config: Config,
    project_distribution: DistributionType,
    hours_per_day: float,
) -> tuple[float, float]:
    """Return (min_hours, max_hours) for a task after resolution + conversion.

    For triangular distributions the bounds are exact.
    For lognormal distributions the lower bound is a near-zero quantile
    and the upper bound is a conservative statistical ceiling.
    """
    est = task.estimate
    effective_distribution = est.distribution or project_distribution

    # Resolve symbolic estimates
    if est.t_shirt_size is not None:
        rc = config.get_t_shirt_size(est.t_shirt_size)
        assert rc is not None
        unit = config.t_shirt_size_unit
        if effective_distribution == DistributionType.TRIANGULAR:
            return (
                convert_to_hours(rc.low, unit, hours_per_day),
                convert_to_hours(rc.high, unit, hours_per_day),
            )
        mu, sigma = fit_shifted_lognormal(
            rc.low,
            rc.expected,
            rc.high,
            config.get_lognormal_high_z_value(),
        )
        return (
            convert_to_hours(rc.low, unit, hours_per_day),
            convert_to_hours(
                rc.low + math.exp(mu + LOGNORMAL_BOUNDARY_SIGMA_MULTIPLIER * sigma),
                unit,
                hours_per_day,
            ),
        )

    if est.story_points is not None:
        sp = config.get_story_point(est.story_points)
        assert sp is not None
        unit = config.story_point_unit
        if effective_distribution == DistributionType.TRIANGULAR:
            return (
                convert_to_hours(sp.low, unit, hours_per_day),
                convert_to_hours(sp.high, unit, hours_per_day),
            )
        mu, sigma = fit_shifted_lognormal(
            sp.low,
            sp.expected,
            sp.high,
            config.get_lognormal_high_z_value(),
        )
        return (
            convert_to_hours(sp.low, unit, hours_per_day),
            convert_to_hours(
                sp.low + math.exp(mu + LOGNORMAL_BOUNDARY_SIGMA_MULTIPLIER * sigma),
                unit,
                hours_per_day,
            ),
        )

    # Explicit estimate
    unit = est.unit or EffortUnit.HOURS

    if effective_distribution == DistributionType.TRIANGULAR:
        assert est.low is not None and est.high is not None
        return (
            convert_to_hours(est.low, unit, hours_per_day),
            convert_to_hours(est.high, unit, hours_per_day),
        )

    assert est.low is not None and est.expected is not None and est.high is not None
    mu, sigma = fit_shifted_lognormal(
        est.low,
        est.expected,
        est.high,
        config.get_lognormal_high_z_value(),
    )
    lo = est.low
    hi = est.low + math.exp(mu + LOGNORMAL_BOUNDARY_SIGMA_MULTIPLIER * sigma)
    return (
        convert_to_hours(lo, unit, hours_per_day),
        convert_to_hours(hi, unit, hours_per_day),
    )


def _uncertainty_multiplier(task: Task, config: Config) -> float:
    """Compute the total uncertainty multiplier for *task*."""
    if not task.uncertainty_factors:
        return 1.0
    multiplier = 1.0
    factors = task.uncertainty_factors
    for factor_name, level in [
        ("team_experience", factors.team_experience),
        ("requirements_maturity", factors.requirements_maturity),
        ("technical_complexity", factors.technical_complexity),
        ("team_distribution", factors.team_distribution),
        ("integration_complexity", factors.integration_complexity),
    ]:
        if level:
            multiplier *= config.get_uncertainty_multiplier(factor_name, level)
    return multiplier


def _max_risk_impact(
    risks: list[Risk],
    base_duration_hours: float,
    hours_per_day: float,
) -> float:
    """Worst-case (all risks fire) cumulative impact in hours."""
    total = 0.0
    for risk in risks:
        total += risk.get_impact_value(base_duration_hours, hours_per_day)
    return total


def compute_project_bounds(
    project: Project,
    config: Config,
) -> tuple[float, float]:
    """Compute (min_hours, max_hours) for overall project duration.

    Lower bound: every task at its minimum sample, uncertainty applied,
    no risks triggered, scheduled through dependencies.

    Upper bound: every task at its maximum sample, uncertainty applied,
    all task risks triggered, scheduled through dependencies, then all
    project risks triggered on top.
    """
    hours_per_day = project.project.hours_per_day

    task_min_hours: dict[str, float] = {}
    task_max_hours: dict[str, float] = {}

    for task in project.tasks:
        lo, hi = _resolve_estimate_range(
            task,
            config,
            project.project.distribution,
            hours_per_day,
        )
        uf = _uncertainty_multiplier(task, config)

        task_lo = lo * uf
        task_hi = hi * uf

        # Worst case: all task-level risks fire on top of max base duration
        task_hi += _max_risk_impact(task.risks, task_hi, hours_per_day)

        task_min_hours[task.id] = task_lo
        task_max_hours[task.id] = task_hi

    # Schedule through dependency graph
    scheduler = TaskScheduler(project)
    schedule_lo = scheduler.schedule_tasks(task_min_hours)
    schedule_hi = scheduler.schedule_tasks(task_max_hours)

    project_lo = max(info["end"] for info in schedule_lo.values())
    project_hi = max(info["end"] for info in schedule_hi.values())

    # Project-level risks (worst case: all fire on top of max duration)
    project_hi += _max_risk_impact(project.project_risks, project_hi, hours_per_day)

    return project_lo, project_hi


# ---------------------------------------------------------------------------
# Invariant checks
# ---------------------------------------------------------------------------

ITERATIONS = 50  # keep fast; we're testing correctness, not statistics


def assert_invariants(
    results: Any,
    project: Project,
    spec: ProjectSpec,
    config: Config,
) -> None:
    """Check universal invariants that must hold for any valid simulation."""
    # Correct number of iterations
    assert results.iterations == ITERATIONS

    # All durations are positive
    assert np.all(results.durations > 0), "All project durations must be positive"

    # Mean is positive
    assert results.mean > 0

    # Standard deviation is non-negative
    assert results.std_dev >= 0

    # Percentile ordering: P50 <= P80 <= P90 <= P95
    p50 = results.percentile(50)
    p80 = results.percentile(80)
    p90 = results.percentile(90)
    p95 = results.percentile(95)
    assert (
        p50 <= p80 <= p90 <= p95
    ), f"Percentiles out of order: P50={p50}, P80={p80}, P90={p90}, P95={p95}"

    # Every task appears in results
    expected_task_ids = {task.id for task in project.tasks}
    assert set(results.task_durations.keys()) == expected_task_ids

    # Per-task durations have the right length and are positive
    for tid, durations in results.task_durations.items():
        assert len(durations) == ITERATIONS, f"Task {tid} has wrong number of samples"
        assert np.all(durations > 0), f"Task {tid} has non-positive durations"

    # Critical path frequency keys are task IDs
    assert set(results.critical_path_frequency.keys()) == expected_task_ids

    # At least one task is on the critical path in every iteration
    total_critical = sum(results.critical_path_frequency.values())
    assert (
        total_critical >= ITERATIONS
    ), "Critical path should have at least one task per iteration"

    # --- Deterministic bounds check -----------------------------------------
    project_lo, project_hi = compute_project_bounds(project, config)

    # Lower bound: no iteration should produce a duration below the
    # all-minimums schedule (risks can only add, never subtract).
    observed_min = float(results.durations.min())
    assert (
        observed_min >= project_lo - 1e-9
    ), f"Observed min {observed_min:.4f} < theoretical lower bound {project_lo:.4f}"

    # Upper bound: every iteration should fall at or below the worst case.
    # For lognormal this is a statistical ceiling (K=6σ), so an exceedance
    # would indicate a bug, not normal randomness.
    observed_max = float(results.durations.max())
    assert (
        observed_max <= project_hi + 1e-9
    ), f"Observed max {observed_max:.4f} > theoretical upper bound {project_hi:.4f}"

    # Mean should be between the bounds
    assert (
        project_lo <= results.mean <= project_hi
    ), f"Mean {results.mean:.4f} outside [{project_lo:.4f}, {project_hi:.4f}]"

    # Duration array shape
    assert results.durations.shape == (ITERATIONS,)

    # Mean should be between min and max of durations
    assert results.durations.min() <= results.mean <= results.durations.max()


# ---------------------------------------------------------------------------
# Config builder
# ---------------------------------------------------------------------------


def build_config(config_data: dict[str, Any]) -> Config:
    """Build a full Config from partial overrides."""
    from mcprojsim.config import _build_default_config_data, _merge_nested_dicts

    merged = _merge_nested_dicts(_build_default_config_data(), config_data)
    return Config.model_validate(merged)


# ---------------------------------------------------------------------------
# Test parametrisation
# ---------------------------------------------------------------------------

SCENARIOS = generate_scenarios(n=300, master_seed=20260309)


@pytest.mark.parametrize(
    "spec",
    SCENARIOS,
    ids=[s.label for s in SCENARIOS],
)
def test_e2e_combination(spec: ProjectSpec, tmp_path):
    """Run a generated project through the full pipeline and verify invariants."""
    rng = random.Random(spec.seed)
    project_data, config_data = build_project_data(spec, rng)

    # Write project file
    project_file = tmp_path / "project.yaml"
    project_file.write_text(yaml.dump(project_data, sort_keys=False))

    # Parse
    parser = YAMLParser()
    project = parser.parse_file(str(project_file))

    # Build config
    config = build_config(config_data)

    # Simulate
    engine = SimulationEngine(
        iterations=ITERATIONS,
        random_seed=spec.seed,
        config=config,
        show_progress=False,
    )
    results = engine.run(project)

    # Check invariants
    assert_invariants(results, project, spec, config)


# ---------------------------------------------------------------------------
# Focused unit-conversion tests
# ---------------------------------------------------------------------------


class TestUnitConversionConsistency:
    """Verify that different units produce proportional results.

    A 1-day task at 8 hours/day should produce ~8× the duration of a
    1-hour task, all else equal.
    """

    @pytest.mark.parametrize("hours_per_day", [6.0, 8.0, 10.0])
    def test_days_vs_hours_scaling(self, hours_per_day: float):
        """Estimate in days should produce hours_per_day× the hours estimate."""
        project_hours = Project.model_validate(
            {
                "project": {
                    "name": "unit-hours",
                    "start_date": "2026-03-01",
                    "hours_per_day": hours_per_day,
                },
                "tasks": [
                    {
                        "id": "t1",
                        "name": "Task",
                        "estimate": {
                            "low": 1,
                            "expected": 2,
                            "high": 3,
                            "unit": "hours",
                        },
                        "dependencies": [],
                    }
                ],
            }
        )
        project_days = Project.model_validate(
            {
                "project": {
                    "name": "unit-days",
                    "start_date": "2026-03-01",
                    "hours_per_day": hours_per_day,
                },
                "tasks": [
                    {
                        "id": "t1",
                        "name": "Task",
                        "estimate": {
                            "low": 1,
                            "expected": 2,
                            "high": 3,
                            "unit": "days",
                        },
                        "dependencies": [],
                    }
                ],
            }
        )

        seed = 99
        config = Config.get_default()
        r_hours = SimulationEngine(
            iterations=500, random_seed=seed, config=config, show_progress=False
        ).run(project_hours)
        r_days = SimulationEngine(
            iterations=500, random_seed=seed, config=config, show_progress=False
        ).run(project_days)

        ratio = r_days.mean / r_hours.mean
        assert (
            abs(ratio - hours_per_day) < 0.5
        ), f"Expected ratio ~{hours_per_day}, got {ratio:.2f}"

    def test_weeks_vs_days_scaling(self):
        """1 week should equal 5 days at the same hours_per_day."""
        hpd = 8.0
        project_days = Project.model_validate(
            {
                "project": {
                    "name": "unit-days",
                    "start_date": "2026-03-01",
                    "hours_per_day": hpd,
                },
                "tasks": [
                    {
                        "id": "t1",
                        "name": "Task",
                        "estimate": {
                            "low": 5,
                            "expected": 10,
                            "high": 15,
                            "unit": "days",
                        },
                        "dependencies": [],
                    }
                ],
            }
        )
        project_weeks = Project.model_validate(
            {
                "project": {
                    "name": "unit-weeks",
                    "start_date": "2026-03-01",
                    "hours_per_day": hpd,
                },
                "tasks": [
                    {
                        "id": "t1",
                        "name": "Task",
                        "estimate": {
                            "low": 1,
                            "expected": 2,
                            "high": 3,
                            "unit": "weeks",
                        },
                        "dependencies": [],
                    }
                ],
            }
        )

        seed = 77
        config = Config.get_default()
        r_days = SimulationEngine(
            iterations=500, random_seed=seed, config=config, show_progress=False
        ).run(project_days)
        r_weeks = SimulationEngine(
            iterations=500, random_seed=seed, config=config, show_progress=False
        ).run(project_weeks)

        ratio = r_weeks.mean / r_days.mean
        assert (
            abs(ratio - 1.0) < 0.1
        ), f"Expected ratio ~1.0 (5 days ≈ 1 week), got {ratio:.2f}"

    @pytest.mark.parametrize("config_unit", ["hours", "days", "weeks"])
    def test_tshirt_config_unit_produces_results(self, config_unit: str):
        """T-shirt estimates work with any config unit."""
        project = Project.model_validate(
            {
                "project": {"name": "ts", "start_date": "2026-03-01"},
                "tasks": [
                    {
                        "id": "t1",
                        "name": "Task",
                        "estimate": {"t_shirt_size": "M"},
                        "dependencies": [],
                    }
                ],
            }
        )
        config = build_config({"t_shirt_size_unit": config_unit})
        results = SimulationEngine(
            iterations=100, random_seed=42, config=config, show_progress=False
        ).run(project)
        assert results.mean > 0

    def test_qualified_tshirt_values_produce_results(self):
        """Qualified category.size T-shirt values should resolve in simulations."""
        project = Project.model_validate(
            {
                "project": {"name": "ts-qualified", "start_date": "2026-03-01"},
                "tasks": [
                    {
                        "id": "t1",
                        "name": "Story task",
                        "estimate": {"t_shirt_size": "story.M"},
                        "dependencies": [],
                    },
                    {
                        "id": "t2",
                        "name": "Epic task",
                        "estimate": {"t_shirt_size": "epic.M"},
                        "dependencies": [],
                    },
                ],
            }
        )
        config = build_config({"t_shirt_size_unit": "hours"})
        results = SimulationEngine(
            iterations=200,
            random_seed=42,
            config=config,
            show_progress=False,
        ).run(project)
        assert results.mean > 0
        assert results.task_durations["t2"].mean() > results.task_durations["t1"].mean()

    @pytest.mark.parametrize("config_unit", ["hours", "days", "weeks"])
    def test_story_point_config_unit_produces_results(self, config_unit: str):
        """Story point estimates work with any config unit."""
        project = Project.model_validate(
            {
                "project": {"name": "sp", "start_date": "2026-03-01"},
                "tasks": [
                    {
                        "id": "t1",
                        "name": "Task",
                        "estimate": {"story_points": 5},
                        "dependencies": [],
                    }
                ],
            }
        )
        config = build_config({"story_point_unit": config_unit})
        results = SimulationEngine(
            iterations=100, random_seed=42, config=config, show_progress=False
        ).run(project)
        assert results.mean > 0

    def test_tshirt_days_larger_than_hours(self):
        """T-shirt 'M' in days should produce a larger mean than in hours."""
        project = Project.model_validate(
            {
                "project": {"name": "ts", "start_date": "2026-03-01"},
                "tasks": [
                    {
                        "id": "t1",
                        "name": "Task",
                        "estimate": {"t_shirt_size": "M"},
                        "dependencies": [],
                    }
                ],
            }
        )
        r_hours = SimulationEngine(
            iterations=500,
            random_seed=42,
            config=build_config({"t_shirt_size_unit": "hours"}),
            show_progress=False,
        ).run(project)
        r_days = SimulationEngine(
            iterations=500,
            random_seed=42,
            config=build_config({"t_shirt_size_unit": "days"}),
            show_progress=False,
        ).run(project)
        assert (
            r_days.mean > r_hours.mean
        ), f"Days mean ({r_days.mean}) should exceed hours mean ({r_hours.mean})"


# ---------------------------------------------------------------------------
# Mixed-type project regression tests
# ---------------------------------------------------------------------------


class TestMixedEstimationProjects:
    """Projects combining all four estimation methods."""

    def test_all_four_types_linear_deps(self):
        project = Project.model_validate(
            {
                "project": {
                    "name": "all-types",
                    "start_date": "2026-03-01",
                    "hours_per_day": 8,
                },
                "tasks": [
                    {
                        "id": "t1",
                        "name": "Triangular task",
                        "estimate": {
                            "low": 4,
                            "expected": 8,
                            "high": 16,
                            "unit": "hours",
                        },
                        "dependencies": [],
                    },
                    {
                        "id": "t2",
                        "name": "Lognormal task",
                        "estimate": {
                            "distribution": "lognormal",
                            "low": 1,
                            "expected": 3,
                            "high": 8,
                            "unit": "days",
                        },
                        "dependencies": ["t1"],
                    },
                    {
                        "id": "t3",
                        "name": "T-shirt task",
                        "estimate": {"t_shirt_size": "L"},
                        "dependencies": ["t2"],
                    },
                    {
                        "id": "t4",
                        "name": "Story point task",
                        "estimate": {"story_points": 8},
                        "dependencies": ["t3"],
                    },
                ],
            }
        )
        config = build_config(
            {
                "t_shirt_size_unit": "hours",
                "story_point_unit": "days",
            }
        )
        results = SimulationEngine(
            iterations=200, random_seed=42, config=config, show_progress=False
        ).run(project)

        assert results.mean > 0
        assert len(results.task_durations) == 4
        # In a linear chain every task has a chance to be critical
        assert any(f > 0 for f in results.critical_path_frequency.values())

    def test_all_four_types_weeks_unit(self):
        """Same project but with explicit estimates in weeks."""
        project = Project.model_validate(
            {
                "project": {
                    "name": "weeks-mix",
                    "start_date": "2026-03-01",
                    "hours_per_day": 8,
                },
                "tasks": [
                    {
                        "id": "t1",
                        "name": "Weeks task",
                        "estimate": {
                            "low": 1,
                            "expected": 2,
                            "high": 3,
                            "unit": "weeks",
                        },
                        "dependencies": [],
                    },
                    {
                        "id": "t2",
                        "name": "T-shirt task",
                        "estimate": {"t_shirt_size": "XL"},
                        "dependencies": ["t1"],
                    },
                    {
                        "id": "t3",
                        "name": "SP task",
                        "estimate": {"story_points": 13},
                        "dependencies": ["t1"],
                    },
                    {
                        "id": "t4",
                        "name": "Hours task",
                        "estimate": {"low": 10, "expected": 20, "high": 40},
                        "dependencies": ["t2", "t3"],
                    },
                ],
            }
        )
        config = build_config(
            {
                "t_shirt_size_unit": "weeks",
                "story_point_unit": "hours",
            }
        )
        results = SimulationEngine(
            iterations=200, random_seed=42, config=config, show_progress=False
        ).run(project)
        assert results.mean > 0
        # Diamond deps: t2 and t3 are parallel
        assert results.critical_path_frequency["t1"] > 0
        assert results.critical_path_frequency["t4"] > 0

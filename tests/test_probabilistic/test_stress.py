"""Category 9: Complex project stress tests.

Large, realistic projects with mixed features to verify the engine
handles complexity without degenerate output.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mcprojsim.models.project import (
    Project,
    Risk,
    Task,
    TaskEstimate,
)
from mcprojsim.parsers.yaml_parser import YAMLParser
from mcprojsim.planning.sprint_engine import SprintSimulationEngine

from .conftest import (
    STAT_ITERATIONS_FULL,
    _meta,
    run_simulation,
)

pytestmark = pytest.mark.probabilistic

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _load_example(filename: str) -> Project:
    """Load a project from the examples directory."""
    parser = YAMLParser()
    return parser.parse_file(EXAMPLES_DIR / filename)


# ------------------------------------------------------------------
# 9.1  Large project convergence (100 tasks)
# ------------------------------------------------------------------
class TestLargeProjectConvergence:
    """A 100-task project should produce finite, non-degenerate results."""

    @pytest.mark.probabilistic_full
    def test_100_task_no_degenerate_output(self):
        project = _load_example("large_project_100_tasks.yaml")
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)

        assert not np.any(
            np.isnan(results.durations)
        ), "LARGE PROJECT: NaN values in durations."
        assert not np.any(
            np.isinf(results.durations)
        ), "LARGE PROJECT: Inf values in durations."
        assert results.mean > 0, "LARGE PROJECT: mean should be positive."
        assert (
            results.std_dev > 0
        ), "LARGE PROJECT: std_dev should be positive (non-degenerate)."
        assert results.std_dev < results.mean * 10, (
            f"LARGE PROJECT: std_dev ({results.std_dev:.2f}) is > 10× "
            f"the mean ({results.mean:.2f}). This is likely degenerate."
        )

    @pytest.mark.probabilistic_full
    def test_100_task_all_tasks_have_durations(self):
        project = _load_example("large_project_100_tasks.yaml")
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)

        for task in project.tasks:
            assert (
                task.id in results.task_durations
            ), f"LARGE PROJECT: task {task.id} missing from task_durations."
            td = results.task_durations[task.id]
            assert len(td) == results.iterations
            assert np.all(td >= 0)


# ------------------------------------------------------------------
# 9.2  Mixed estimate types
# ------------------------------------------------------------------
class TestMixedEstimateTypes:
    """A project mixing t-shirt sizes, story points, and explicit
    estimates should produce valid results.
    """

    @pytest.mark.probabilistic_full
    def test_mixed_estimates_valid(self):
        project = _load_example("mixed_task_estimates.yaml")
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)

        assert results.mean > 0
        assert results.std_dev > 0
        assert not np.any(np.isnan(results.durations))
        assert len(results.task_durations) == len(project.tasks)


# ------------------------------------------------------------------
# 9.3  Full feature project (resources, calendars, risks, uncertainty)
# ------------------------------------------------------------------
class TestFullFeatureProject:
    """A project with resources, calendars, and risks should produce
    complete diagnostic results.
    """

    @pytest.mark.probabilistic_full
    def test_constrained_project_diagnostics(self):
        project = _load_example("constrained_portal.yaml")
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)

        assert results.mean > 0
        assert results.iterations == STAT_ITERATIONS_FULL
        assert results.resource_constraints_active is True
        assert results.resource_utilization > 0, (
            "FULL FEATURE: resource utilization should be positive "
            "for a constrained project."
        )
        assert results.resource_wait_time_hours >= 0

        # Sensitivity populated for all tasks
        for task in project.tasks:
            assert (
                task.id in results.sensitivity
            ), f"FULL FEATURE: missing sensitivity for task {task.id}."

        # Critical path populated
        total_cp_freq = sum(results.critical_path_frequency.values())
        assert total_cp_freq > 0

    @pytest.mark.probabilistic_full
    def test_two_pass_produces_trace(self):
        """Two-pass scheduling should populate the trace."""
        project = _load_example("constrained_portal.yaml")
        results = run_simulation(
            project,
            iterations=STAT_ITERATIONS_FULL,
            seed=42,
            two_pass=True,
        )

        assert (
            results.two_pass_trace is not None
        ), "FULL FEATURE: two_pass_trace should be populated."
        assert results.two_pass_trace.enabled is True


# ------------------------------------------------------------------
# 9.4  Sprint planning convergence
# ------------------------------------------------------------------
class TestSprintPlanningConvergence:
    """Sprint simulation should produce finite sprint counts with
    reasonable statistics.
    """

    @pytest.mark.probabilistic_full
    def test_sprint_simulation_valid(self):
        project = _load_example("sprint_planning_minimal.yaml")
        engine = SprintSimulationEngine(iterations=STAT_ITERATIONS_FULL, random_seed=42)
        results = engine.run(project)
        results.calculate_statistics()

        assert results.mean > 0, "SPRINT PLANNING: mean sprints should be positive."
        assert (
            results.min_sprints >= 1
        ), "SPRINT PLANNING: minimum sprints should be at least 1."
        assert not np.any(np.isnan(results.sprint_counts))
        assert not np.any(np.isinf(results.sprint_counts))
        assert results.std_dev >= 0, "SPRINT PLANNING: std_dev should be non-negative."


# ------------------------------------------------------------------
# 9.5  Programmatic large project (no YAML dependency)
# ------------------------------------------------------------------
class TestProgrammaticLargeProject:
    """Build a 50-task diamond network purely in code to verify
    scaling without depending on example YAML files.
    """

    @pytest.mark.probabilistic_full
    def test_50_task_diamond_network(self):
        """50 tasks: root → 48 parallel → sink.
        Should complete without error and produce valid results.
        """
        tasks: list[Task] = [
            Task(
                id="root",
                name="Root",
                estimate=TaskEstimate(low=5.0, expected=10.0, high=20.0),
            ),
        ]
        for i in range(48):
            tasks.append(
                Task(
                    id=f"mid_{i}",
                    name=f"Middle {i}",
                    estimate=TaskEstimate(low=8.0, expected=20.0, high=50.0),
                    dependencies=["root"],
                    risks=(
                        [
                            Risk(
                                id=f"r_{i}",
                                name=f"Risk {i}",
                                probability=0.2,
                                impact=10.0,
                            )
                        ]
                        if i % 5 == 0
                        else []
                    ),
                )
            )
        tasks.append(
            Task(
                id="sink",
                name="Sink",
                estimate=TaskEstimate(low=3.0, expected=8.0, high=15.0),
                dependencies=[f"mid_{i}" for i in range(48)],
            )
        )

        project = Project(
            project=_meta(name="LargeDiamondNetwork"),
            tasks=tasks,
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)

        assert results.mean > 0
        assert results.max_parallel_tasks == 48, (
            f"LARGE DIAMOND: expected peak parallelism 48, "
            f"got {results.max_parallel_tasks}."
        )
        assert not np.any(np.isnan(results.durations))
        assert len(results.task_durations) == 50

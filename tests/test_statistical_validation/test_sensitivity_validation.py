"""Test 6: Sensitivity analysis validation.

The simulation computes Spearman rank correlations to identify which
tasks most strongly influence total project duration. We validate this
by constructing projects where the sensitivity ordering is analytically
known:
- A high-variance task on the critical path should dominate
- A low-variance task or one not on the critical path should be weak
"""

from __future__ import annotations

from scipy import stats

from mcprojsim.config import EffortUnit
from mcprojsim.models.project import (
    DistributionType,
    Project,
    ProjectMetadata,
    Task,
    TaskEstimate,
)

from .conftest import (
    N_ITERATIONS,
    START_DATE,
    run_sim,
)


class TestSensitivityOrdering:
    """Tasks with higher variance on the critical path have higher sensitivity."""

    def test_high_variance_dominates_sensitivity(self):
        """In a chain, the task with widest range has highest |ρ|."""
        # t1: narrow range (low variance)
        # t2: very wide range (high variance) → should dominate sensitivity
        # t3: narrow range
        project = Project(
            project=ProjectMetadata(
                name="Sensitivity",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1 (narrow)",
                    estimate=TaskEstimate(
                        low=18.0, expected=20.0, high=22.0, unit=EffortUnit.HOURS
                    ),
                ),
                Task(
                    id="t2",
                    name="T2 (wide)",
                    estimate=TaskEstimate(
                        low=10.0, expected=30.0, high=100.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["t1"],
                ),
                Task(
                    id="t3",
                    name="T3 (narrow)",
                    estimate=TaskEstimate(
                        low=9.0, expected=10.0, high=11.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["t2"],
                ),
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=300)

        # Compute Spearman correlations manually
        rho_t1 = float(
            stats.spearmanr(results.task_durations["t1"], results.durations).statistic
        )
        rho_t2 = float(
            stats.spearmanr(results.task_durations["t2"], results.durations).statistic
        )
        rho_t3 = float(
            stats.spearmanr(results.task_durations["t3"], results.durations).statistic
        )

        # t2 should have highest correlation
        assert abs(rho_t2) > abs(
            rho_t1
        ), f"|ρ_t2|={abs(rho_t2):.4f} should > |ρ_t1|={abs(rho_t1):.4f}"
        assert abs(rho_t2) > abs(
            rho_t3
        ), f"|ρ_t2|={abs(rho_t2):.4f} should > |ρ_t3|={abs(rho_t3):.4f}"

    def test_parallel_tasks_only_critical_one_matters(self):
        """In parallel topology, only the dominant task correlates with project duration."""
        # t1: long task (usually determines project duration)
        # t2: very short task (rarely the bottleneck)
        project = Project(
            project=ProjectMetadata(
                name="Par Sensitivity",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1 (long)",
                    estimate=TaskEstimate(
                        low=50.0, expected=100.0, high=200.0, unit=EffortUnit.HOURS
                    ),
                ),
                Task(
                    id="t2",
                    name="T2 (short)",
                    estimate=TaskEstimate(
                        low=1.0, expected=3.0, high=8.0, unit=EffortUnit.HOURS
                    ),
                ),
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=301)

        rho_t1 = float(
            stats.spearmanr(results.task_durations["t1"], results.durations).statistic
        )
        rho_t2 = float(
            stats.spearmanr(results.task_durations["t2"], results.durations).statistic
        )

        # t1 dominates → very high correlation
        assert rho_t1 > 0.9, f"ρ_t1={rho_t1:.4f} should be > 0.9"
        # t2 rarely matters → very low correlation
        assert abs(rho_t2) < 0.3, f"|ρ_t2|={abs(rho_t2):.4f} should be < 0.3"

    def test_equal_variance_equal_sensitivity(self):
        """Chain of identical tasks → roughly equal sensitivity for each."""
        est = (10.0, 25.0, 50.0)
        n_tasks = 4
        tasks = [
            Task(
                id=f"t{i+1}",
                name=f"T{i+1}",
                estimate=TaskEstimate(
                    low=est[0], expected=est[1], high=est[2], unit=EffortUnit.HOURS
                ),
                dependencies=[f"t{i}"] if i > 0 else [],
            )
            for i in range(n_tasks)
        ]
        project = Project(
            project=ProjectMetadata(
                name="Equal Sensitivity",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=tasks,
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=302)

        correlations = []
        for i in range(n_tasks):
            tid = f"t{i+1}"
            rho = float(
                stats.spearmanr(
                    results.task_durations[tid], results.durations
                ).statistic
            )
            correlations.append(rho)

        # All correlations should be similar (within 10% of each other)
        max_rho = max(correlations)
        min_rho = min(correlations)
        assert max_rho - min_rho < 0.15, f"Sensitivity spread too wide: {correlations}"


class TestSensitivityDirectionality:
    """Sensitivity correlations should be positive (longer task → longer project)."""

    def test_all_correlations_positive(self):
        """For tasks on the critical path, rho > 0."""
        project = Project(
            project=ProjectMetadata(
                name="Positive Sens",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1",
                    estimate=TaskEstimate(
                        low=5.0, expected=15.0, high=30.0, unit=EffortUnit.HOURS
                    ),
                ),
                Task(
                    id="t2",
                    name="T2",
                    estimate=TaskEstimate(
                        low=10.0, expected=25.0, high=50.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["t1"],
                ),
                Task(
                    id="t3",
                    name="T3",
                    estimate=TaskEstimate(
                        low=8.0, expected=20.0, high=40.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["t2"],
                ),
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=303)

        for tid in ["t1", "t2", "t3"]:
            rho = float(
                stats.spearmanr(
                    results.task_durations[tid], results.durations
                ).statistic
            )
            assert rho > 0, f"Task {tid}: ρ={rho:.4f} should be positive"

    def test_sensitivity_sum_of_squares_bounded(self):
        """Sum of squared Spearman correlations ≈ 1 for a pure chain.

        This is a known property: for Y = X1 + X2 + ... + Xn (independent),
        the sum of squared rank correlations is approximately 1.
        """
        estimates = [
            (5.0, 15.0, 30.0),
            (10.0, 25.0, 50.0),
            (8.0, 20.0, 40.0),
            (12.0, 30.0, 60.0),
        ]
        tasks = [
            Task(
                id=f"t{i+1}",
                name=f"T{i+1}",
                estimate=TaskEstimate(
                    low=e[0], expected=e[1], high=e[2], unit=EffortUnit.HOURS
                ),
                dependencies=[f"t{i}"] if i > 0 else [],
            )
            for i, e in enumerate(estimates)
        ]
        project = Project(
            project=ProjectMetadata(
                name="Sum Sq",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=tasks,
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=304)

        sum_rho_sq = 0.0
        for i in range(len(estimates)):
            tid = f"t{i+1}"
            rho = float(
                stats.spearmanr(
                    results.task_durations[tid], results.durations
                ).statistic
            )
            sum_rho_sq += rho**2

        # For independent additive components, sum of squared rank correlations ≈ 1
        # Allow some tolerance due to rank vs linear correlation difference
        assert 0.85 < sum_rho_sq < 1.15, f"Σρ²={sum_rho_sq:.4f}, expected ≈ 1.0"

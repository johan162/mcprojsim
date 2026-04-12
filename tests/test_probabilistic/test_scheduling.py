"""Category 5: Scheduling invariant tests.

Verify structural properties of the dependency-only and resource-
constrained scheduling algorithms.
"""

from __future__ import annotations

import numpy as np
import pytest

from .conftest import (
    STAT_ITERATIONS_CI,
    make_chain_project,
    make_constrained_parallel_project,
    make_diamond_project,
    make_fan_out_project,
    make_parallel_project,
    run_simulation,
)

pytestmark = pytest.mark.probabilistic


# ------------------------------------------------------------------
# 5.1  Chain duration = sum of task durations
# ------------------------------------------------------------------
class TestChainScheduling:
    """For a pure chain, project duration = sum of task durations
    in every iteration (no parallelism possible).
    """

    def test_chain_3_tasks(self):
        project = make_chain_project(n_tasks=3)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        task_sum = np.zeros(results.iterations)
        for durations in results.task_durations.values():
            task_sum += durations

        max_diff = float(np.max(np.abs(results.durations - task_sum)))
        assert max_diff < 1e-6, (
            f"CHAIN SCHEDULING ERROR: project duration ≠ Σ task durations. "
            f"Max |diff| = {max_diff:.6e}. "
            f"SUGGESTION: For a pure chain with no project-level risks, "
            f"the scheduler should produce duration = sum of all task "
            f"durations.  Check the forward-pass in scheduler and whether "
            f"project-level risks are unexpectedly applied."
        )

    def test_chain_10_tasks(self):
        project = make_chain_project(n_tasks=10)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=77)

        task_sum = np.zeros(results.iterations)
        for durations in results.task_durations.values():
            task_sum += durations

        assert np.allclose(results.durations, task_sum, atol=1e-6)


# ------------------------------------------------------------------
# 5.2  Parallel duration = max of task durations
# ------------------------------------------------------------------
class TestParallelScheduling:
    """For fully parallel tasks, project duration = max(task_i) per
    iteration.
    """

    def test_parallel_4_tasks(self):
        project = make_parallel_project(n_parallel=4)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        task_max = np.zeros(results.iterations)
        for durations in results.task_durations.values():
            task_max = np.maximum(task_max, durations)

        max_diff = float(np.max(np.abs(results.durations - task_max)))
        assert max_diff < 1e-6, (
            f"PARALLEL SCHEDULING ERROR: project duration ≠ max(task_i). "
            f"Max |diff| = {max_diff:.6e}. "
            f"SUGGESTION: For independent parallel tasks with no project "
            f"risks, project duration should be the maximum end time "
            f"= max(task durations).  Check scheduler for unexpected "
            f"serialization."
        )


# ------------------------------------------------------------------
# 5.3  Diamond critical path frequency
# ------------------------------------------------------------------
class TestDiamondCriticalPath:
    """In A → {B, C} → D, the longer branch should dominate the
    critical path.
    """

    def test_longer_branch_dominates(self):
        # B: large task, C: small task
        project = make_diamond_project(
            b_estimate=(40.0, 80.0, 150.0),
            c_estimate=(5.0, 10.0, 20.0),
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        freq_b = results.critical_path_frequency.get("B", 0) / results.iterations
        freq_c = results.critical_path_frequency.get("C", 0) / results.iterations

        assert freq_b > 0.80, (
            f"CRITICAL PATH FREQUENCY: B freq={freq_b:.3f}, expected > 0.80. "
            f"B has a much larger estimate than C, so B should dominate "
            f"the critical path.  SUGGESTION: Check critical-path tracing "
            f"in scheduler.get_critical_paths."
        )
        assert freq_b > freq_c, (
            f"CRITICAL PATH ORDERING: B freq={freq_b:.3f} should be > "
            f"C freq={freq_c:.3f}."
        )

    def test_balanced_branches_share_criticality(self):
        """When B and C have identical estimates, both should appear
        on the critical path roughly equally.
        """
        project = make_diamond_project(
            b_estimate=(10.0, 30.0, 70.0),
            c_estimate=(10.0, 30.0, 70.0),
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        freq_b = results.critical_path_frequency.get("B", 0) / results.iterations
        freq_c = results.critical_path_frequency.get("C", 0) / results.iterations

        # Both should have meaningful criticality (> 30%)
        assert freq_b > 0.30, f"Balanced diamond: B criticality {freq_b:.3f} too low."
        assert freq_c > 0.30, f"Balanced diamond: C criticality {freq_c:.3f} too low."


# ------------------------------------------------------------------
# 5.4  Effort vs duration relationship
# ------------------------------------------------------------------
class TestEffortVsDuration:
    """effort == duration for chains, effort > duration for parallel."""

    def test_chain_effort_equals_duration(self):
        project = make_chain_project(n_tasks=4)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)
        assert np.allclose(
            results.effort_durations, results.durations, atol=1e-6
        ), "Chain: effort should equal duration."

    def test_parallel_effort_exceeds_duration(self):
        project = make_parallel_project(n_parallel=5)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        # In every iteration, effort (sum) > duration (max) when n > 1
        # unless by coincidence one task has 0 duration
        violations = int(np.sum(results.effort_durations <= results.durations + 1e-6))
        # Allow a tiny fraction of iterations where max ≈ sum (extremely rare)
        assert violations < results.iterations * 0.01, (
            f"PARALLEL EFFORT ≤ DURATION in {violations}/{results.iterations} "
            f"iterations.  With 5 parallel tasks, effort (sum) should "
            f"almost always exceed duration (max)."
        )


# ------------------------------------------------------------------
# 5.5  Resource constraint increases duration
# ------------------------------------------------------------------
class TestResourceConstraintEffect:
    """Adding resource constraints to parallel tasks should increase
    mean project duration (resource contention forces serialization).
    """

    def test_constrained_duration_ge_unconstrained(self):
        project_unc = make_parallel_project(n_parallel=4)
        project_con = make_constrained_parallel_project(n_parallel=4, n_resources=2)

        results_unc = run_simulation(
            project_unc, iterations=STAT_ITERATIONS_CI, seed=42
        )
        results_con = run_simulation(
            project_con, iterations=STAT_ITERATIONS_CI, seed=42
        )

        # Constrained mean should be higher or equal
        assert results_con.mean >= results_unc.mean - 1.0, (
            f"RESOURCE CONSTRAINT ANOMALY: constrained mean "
            f"({results_con.mean:.2f}) < unconstrained mean "
            f"({results_unc.mean:.2f}).  Resource contention should "
            f"increase duration.  SUGGESTION: Check resource scheduling "
            f"and greedy dispatch logic."
        )


# ------------------------------------------------------------------
# 5.6  Peak parallelism bounds
# ------------------------------------------------------------------
class TestPeakParallelism:
    """Peak parallelism should match the project structure."""

    def test_chain_peak_parallelism_is_one(self):
        project = make_chain_project(n_tasks=5)
        results = run_simulation(project, iterations=100, seed=42)
        assert results.max_parallel_tasks == 1, (
            f"PEAK PARALLELISM: chain should be 1, "
            f"got {results.max_parallel_tasks}.  "
            f"SUGGESTION: Check sweep-line algorithm in "
            f"scheduler.max_parallel_tasks."
        )

    def test_parallel_peak_equals_n(self):
        n = 6
        project = make_parallel_project(n_parallel=n)
        results = run_simulation(project, iterations=100, seed=42)
        assert results.max_parallel_tasks == n, (
            f"PEAK PARALLELISM: {n} parallel tasks should give "
            f"peak={n}, got {results.max_parallel_tasks}."
        )

    def test_fan_out_peak_matches_branches(self):
        n_branches = 8
        project = make_fan_out_project(n_parallel=n_branches)
        results = run_simulation(project, iterations=100, seed=42)
        assert results.max_parallel_tasks == n_branches, (
            f"FAN-OUT PEAK PARALLELISM: {n_branches} branches should "
            f"give peak={n_branches}, got {results.max_parallel_tasks}."
        )


# ------------------------------------------------------------------
# 5.7  Scheduling diagnostics for dependency-only mode
# ------------------------------------------------------------------
class TestSchedulingDiagnostics:
    """Dependency-only mode should have zero resource wait time."""

    def test_dependency_only_no_resource_wait(self):
        project = make_parallel_project(n_parallel=4)
        results = run_simulation(project, iterations=100, seed=42)

        assert (
            results.schedule_mode == "dependency_only"
        ), f"Expected dependency_only mode, got '{results.schedule_mode}'."
        assert results.resource_wait_time_hours == 0.0, (
            f"RESOURCE WAIT TIME in dependency-only mode: "
            f"{results.resource_wait_time_hours:.4f}h. Should be 0."
        )

    def test_constrained_has_positive_utilization(self):
        project = make_constrained_parallel_project(n_parallel=4, n_resources=2)
        results = run_simulation(project, iterations=100, seed=42)

        assert results.resource_constraints_active is True
        assert results.resource_utilization > 0, (
            "ZERO UTILIZATION in constrained mode. With 4 tasks and "
            "2 resources, utilization should be positive."
        )


# ------------------------------------------------------------------
# 5.8  Chain: all tasks on critical path
# ------------------------------------------------------------------
class TestChainCriticality:
    """In a pure chain, every task is always on the critical path."""

    def test_all_tasks_critical(self):
        project = make_chain_project(n_tasks=5)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        for task in project.tasks:
            freq = results.critical_path_frequency.get(task.id, 0) / results.iterations
            assert freq > 0.99, (
                f"CHAIN CRITICALITY: task {task.id} critical path "
                f"freq={freq:.3f}, expected ~1.0. "
                f"In a pure chain, every task should always be on the "
                f"critical path.  SUGGESTION: Check critical-path "
                f"tracing backward pass."
            )

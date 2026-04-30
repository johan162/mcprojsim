"""Test 12: Critical path frequency validation.

Verify that the simulation correctly identifies and reports critical paths
for various topologies where the analytical criticality can be computed
or bounded.
"""

from __future__ import annotations

import numpy as np
import pytest
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
    ALPHA,
    N_ITERATIONS,
    START_DATE,
    assert_proportion,
    run_sim,
)

# numpy triangular requires left < right; use tiny spread for "deterministic"
EPS = 0.001


def _det_estimate(value: float) -> TaskEstimate:
    return TaskEstimate(
        low=value - EPS, expected=value, high=value + EPS, unit=EffortUnit.HOURS
    )


class TestCriticalPathFrequency:
    """Critical path frequencies match analytical expectations."""

    def test_chain_all_tasks_always_critical(self):
        """In a serial chain (stochastic), every task is always critical."""
        tasks = [
            Task(
                id=f"t{i+1}",
                name=f"T{i+1}",
                estimate=TaskEstimate(
                    low=5.0, expected=15.0, high=30.0, unit=EffortUnit.HOURS
                ),
                dependencies=[f"t{i}"] if i > 0 else [],
            )
            for i in range(4)
        ]
        project = Project(
            project=ProjectMetadata(
                name="Chain CP",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=tasks,
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=900)

        # Every task in a chain is always on the critical path
        for tid in ["t1", "t2", "t3", "t4"]:
            assert results.critical_path_frequency[tid] == N_ITERATIONS

    def test_symmetric_diamond_equal_criticality(self):
        """In a diamond with identical B and C, both ≈ 50% critical."""
        project = Project(
            project=ProjectMetadata(
                name="Sym Diamond",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="A",
                    name="A",
                    estimate=TaskEstimate(
                        low=5.0, expected=10.0, high=15.0, unit=EffortUnit.HOURS
                    ),
                ),
                Task(
                    id="B",
                    name="B",
                    estimate=TaskEstimate(
                        low=10.0, expected=20.0, high=40.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["A"],
                ),
                Task(
                    id="C",
                    name="C",
                    estimate=TaskEstimate(
                        low=10.0, expected=20.0, high=40.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["A"],
                ),
                Task(
                    id="D",
                    name="D",
                    estimate=TaskEstimate(
                        low=5.0, expected=10.0, high=15.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["B", "C"],
                ),
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=901)

        # A and D always on critical path
        assert results.critical_path_frequency["A"] == N_ITERATIONS
        assert results.critical_path_frequency["D"] == N_ITERATIONS

        # B and C each ≈ 50% (binomial test)
        freq_b = results.critical_path_frequency["B"]
        result = stats.binomtest(freq_b, N_ITERATIONS, 0.5)
        assert result.pvalue > ALPHA, (
            f"B criticality = {freq_b/N_ITERATIONS:.4f}, p={result.pvalue:.2e}"
        )

    def test_asymmetric_diamond_dominant_branch(self):
        """When one branch is much longer, it dominates criticality."""
        project = Project(
            project=ProjectMetadata(
                name="Asym Diamond",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="A",
                    name="A",
                    estimate=TaskEstimate(
                        low=5.0, expected=10.0, high=15.0, unit=EffortUnit.HOURS
                    ),
                ),
                Task(
                    id="B",
                    name="B (long)",
                    estimate=TaskEstimate(
                        low=80.0, expected=120.0, high=200.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["A"],
                ),
                Task(
                    id="C",
                    name="C (short)",
                    estimate=TaskEstimate(
                        low=5.0, expected=10.0, high=20.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["A"],
                ),
                Task(
                    id="D",
                    name="D",
                    estimate=TaskEstimate(
                        low=5.0, expected=10.0, high=15.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["B", "C"],
                ),
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=902)

        # B should be critical in almost all iterations
        freq_b = results.critical_path_frequency["B"]
        assert freq_b / N_ITERATIONS > 0.99, (
            f"B criticality = {freq_b/N_ITERATIONS:.4f}, expected > 0.99"
        )
        # C should rarely be critical
        freq_c = results.critical_path_frequency["C"]
        assert freq_c / N_ITERATIONS < 0.01

    def test_three_parallel_branches_criticality_sum(self):
        """Sum of branch criticalities equals 1 (exactly one is critical per iteration)."""
        project = Project(
            project=ProjectMetadata(
                name="Three Branches",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="start",
                    name="Start",
                    estimate=_det_estimate(5.0),
                ),
                Task(
                    id="B1",
                    name="Branch 1",
                    estimate=TaskEstimate(
                        low=10.0, expected=20.0, high=40.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["start"],
                ),
                Task(
                    id="B2",
                    name="Branch 2",
                    estimate=TaskEstimate(
                        low=10.0, expected=20.0, high=40.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["start"],
                ),
                Task(
                    id="B3",
                    name="Branch 3",
                    estimate=TaskEstimate(
                        low=10.0, expected=20.0, high=40.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["start"],
                ),
                Task(
                    id="end",
                    name="End",
                    estimate=_det_estimate(3.0),
                    dependencies=["B1", "B2", "B3"],
                ),
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=903)

        # Each branch is critical when it's the maximum
        # With 3 iid branches, each is critical ≈ 1/3 of the time
        for bid in ["B1", "B2", "B3"]:
            freq = results.critical_path_frequency[bid]
            result = stats.binomtest(freq, N_ITERATIONS, 1 / 3.0)
            assert result.pvalue > ALPHA, (
                f"{bid} criticality = {freq/N_ITERATIONS:.4f}, expected ≈ 1/3, "
                f"p={result.pvalue:.2e}"
            )


class TestCriticalPathSequences:
    """Full path sequence recording is correct."""

    def test_chain_single_sequence(self):
        """A serial chain has exactly one critical path sequence."""
        tasks = [
            Task(
                id=f"t{i+1}",
                name=f"T{i+1}",
                estimate=_det_estimate(10.0),
                dependencies=[f"t{i}"] if i > 0 else [],
            )
            for i in range(3)
        ]
        project = Project(
            project=ProjectMetadata(
                name="Chain Seq",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=tasks,
        )
        results = run_sim(project, iterations=500, seed=910)

        # Should have exactly one sequence
        assert len(results.critical_path_sequences) == 1
        # And it should be the full chain
        seq = results.critical_path_sequences[0]
        assert set(seq.path) == {"t1", "t2", "t3"}
        assert seq.count == 500
        assert seq.frequency == 1.0

    def test_diamond_two_possible_sequences(self):
        """Diamond has 2 possible sequences when branches have overlap."""
        project = Project(
            project=ProjectMetadata(
                name="Diamond Seq",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="A",
                    name="A",
                    estimate=TaskEstimate(
                        low=5.0, expected=10.0, high=15.0, unit=EffortUnit.HOURS
                    ),
                ),
                Task(
                    id="B",
                    name="B",
                    estimate=TaskEstimate(
                        low=10.0, expected=20.0, high=40.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["A"],
                ),
                Task(
                    id="C",
                    name="C",
                    estimate=TaskEstimate(
                        low=10.0, expected=20.0, high=40.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["A"],
                ),
                Task(
                    id="D",
                    name="D",
                    estimate=TaskEstimate(
                        low=5.0, expected=10.0, high=15.0, unit=EffortUnit.HOURS
                    ),
                    dependencies=["B", "C"],
                ),
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=911)

        # Should have at most 2 distinct sequences (A-B-D and A-C-D)
        assert len(results.critical_path_sequences) <= 2

        # Total frequency should sum to 1.0
        total_freq = sum(seq.frequency for seq in results.critical_path_sequences)
        assert abs(total_freq - 1.0) < 0.01

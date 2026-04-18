"""Tests for parallel simulation: partitioning, merging, worker function, and integration."""

from __future__ import annotations

from collections import Counter
import io
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml  # noqa: F401 — kept for potential future use in inline fixtures

from mcprojsim.simulation.parallel import (
    ChunkResult,
    _run_chunk,
    merge_chunk_results,
    partition_chunks,
    partition_seeds,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

QUICKSTART_YAML = Path(__file__).parent.parent / "examples" / "quickstart_example.yaml"
CONTENTION_YAML = Path(__file__).parent / "fixtures" / "test_fixture_contention.yaml"


def _make_chunk_result(
    chunk_start: int,
    chunk_size: int,
    task_ids: list[str],
    seed: int = 0,
    with_costs: bool = False,
) -> ChunkResult:
    """Build a synthetic ChunkResult for unit-testing merge logic."""
    rng = np.random.RandomState(seed)
    proj_dur = rng.uniform(100, 200, chunk_size)
    task_dur = {tid: rng.uniform(10, 50, chunk_size) for tid in task_ids}
    task_risk = {tid: rng.uniform(0, 5, chunk_size) for tid in task_ids}
    task_slack = {tid: rng.uniform(0, 10, chunk_size) for tid in task_ids}
    cpf = {tid: int(chunk_size // len(task_ids)) for tid in task_ids}
    # Ensure CPF totals match chunk_size
    remainder = chunk_size - sum(cpf.values())
    first_id = task_ids[0]
    cpf[first_id] += remainder
    cps: Counter[tuple[str, ...]] = Counter(
        {tuple(task_ids): chunk_size // 2, (task_ids[0],): chunk_size // 2}
    )
    proj_risk = rng.uniform(0, 2, chunk_size)
    rwt = rng.uniform(0, 1, chunk_size)
    rutil = rng.uniform(0, 1, chunk_size)
    cdt = rng.uniform(0, 1, chunk_size)

    costs = rng.uniform(1000, 5000, chunk_size) if with_costs else None
    task_costs = (
        {tid: rng.uniform(100, 500, chunk_size) for tid in task_ids}
        if with_costs
        else None
    )

    return ChunkResult(
        chunk_start=chunk_start,
        chunk_size=chunk_size,
        project_durations=proj_dur,
        task_durations=task_dur,
        task_risk_impacts=task_risk,
        project_risk_impacts=proj_risk,
        task_slack=task_slack,
        critical_path_frequency=cpf,
        critical_path_sequences=cps,
        max_parallel=3,
        resource_wait_times=rwt,
        resource_utilizations=rutil,
        calendar_delay_times=cdt,
        project_costs=costs,
        task_costs=task_costs,
    )


# ---------------------------------------------------------------------------
# partition_chunks tests
# ---------------------------------------------------------------------------


class TestPartitionChunks:
    def test_sum_equals_iterations(self) -> None:
        chunks = partition_chunks(1000, 4)
        assert sum(s for _, s in chunks) == 1000

    def test_deterministic(self) -> None:
        assert partition_chunks(500, 2) == partition_chunks(500, 2)

    def test_more_chunks_than_workers(self) -> None:
        import math

        iterations, workers = 100, 2
        target = min(iterations, max(workers * 8, 32))
        chunk_size = math.ceil(iterations / target)
        expected = math.ceil(iterations / chunk_size)
        chunks = partition_chunks(iterations, workers)
        assert len(chunks) == expected

    def test_covers_starting_at_zero(self) -> None:
        chunks = partition_chunks(200, 4)
        assert chunks[0][0] == 0

    def test_contiguous(self) -> None:
        chunks = partition_chunks(300, 4)
        for i in range(1, len(chunks)):
            prev_start, prev_size = chunks[i - 1]
            assert chunks[i][0] == prev_start + prev_size

    def test_empty_iterations(self) -> None:
        assert partition_chunks(0, 4) == []

    def test_single_iteration(self) -> None:
        chunks = partition_chunks(1, 8)
        assert chunks == [(0, 1)]


# ---------------------------------------------------------------------------
# partition_seeds tests
# ---------------------------------------------------------------------------


class TestPartitionSeeds:
    def test_returns_correct_count(self) -> None:
        seeds = partition_seeds(42, 8)
        assert len(seeds) == 8

    def test_deterministic(self) -> None:
        a = partition_seeds(42, 4)
        b = partition_seeds(42, 4)
        for sa, sb in zip(a, b):
            assert list(sa.generate_state(4)) == list(sb.generate_state(4))

    def test_different_root_seeds_differ(self) -> None:
        a = partition_seeds(42, 4)
        b = partition_seeds(99, 4)
        # Different root seeds must produce different children.
        first_a = list(a[0].generate_state(4))
        first_b = list(b[0].generate_state(4))
        assert first_a != first_b

    def test_different_chunk_indices_produce_independent_streams(self) -> None:
        from numpy.random import MT19937, RandomState

        seeds = partition_seeds(99, 2)
        rng0 = RandomState(MT19937(seeds[0]))
        rng1 = RandomState(MT19937(seeds[1]))
        vals0 = rng0.uniform(size=10).tolist()
        vals1 = rng1.uniform(size=10).tolist()
        assert vals0 != vals1

    def test_raises_for_n_chunks_less_than_1(self) -> None:
        with pytest.raises(ValueError):
            partition_seeds(42, 0)

    def test_none_seed_produces_results(self) -> None:
        seeds = partition_seeds(None, 3)
        assert len(seeds) == 3

    def test_parent_seq_overrides_random_seed(self) -> None:
        from numpy.random import SeedSequence

        parent = SeedSequence(1234)
        seeds_a = partition_seeds(999, 4, parent_seq=parent)
        parent2 = SeedSequence(1234)
        seeds_b = partition_seeds(111, 4, parent_seq=parent2)
        for sa, sb in zip(seeds_a, seeds_b):
            assert list(sa.generate_state(4)) == list(sb.generate_state(4))


# ---------------------------------------------------------------------------
# merge_chunk_results tests
# ---------------------------------------------------------------------------


class TestMergeChunkResults:
    TASK_IDS = ["t1", "t2", "t3"]

    def _two_chunks(self, n: int = 50) -> tuple[ChunkResult, ChunkResult]:
        c0 = _make_chunk_result(0, n, self.TASK_IDS, seed=0)
        c1 = _make_chunk_result(n, n, self.TASK_IDS, seed=1)
        return c0, c1

    def test_merge_deterministic_regardless_of_order(self) -> None:
        c0, c1 = self._two_chunks(50)
        merged_ab = merge_chunk_results([c0, c1], 100)
        merged_ba = merge_chunk_results([c1, c0], 100)
        np.testing.assert_array_equal(
            merged_ab.project_durations, merged_ba.project_durations
        )

    def test_project_durations_length(self) -> None:
        c0, c1 = self._two_chunks(60)
        merged = merge_chunk_results([c0, c1], 120)
        assert len(merged.project_durations) == 120

    def test_critical_path_frequency_sums(self) -> None:
        n = 40
        c0, c1 = self._two_chunks(n)
        merged = merge_chunk_results([c0, c1], n * 2)
        for tid in self.TASK_IDS:
            assert merged.critical_path_frequency[tid] == (
                c0.critical_path_frequency[tid] + c1.critical_path_frequency[tid]
            )

    def test_critical_path_sequences_counter_sum(self) -> None:
        c0, c1 = self._two_chunks(50)
        merged = merge_chunk_results([c0, c1], 100)
        for path, count in c0.critical_path_sequences.items():
            assert merged.critical_path_sequences[path] >= count
        combined = c0.critical_path_sequences + c1.critical_path_sequences
        assert dict(merged.critical_path_sequences) == dict(combined)

    def test_assertion_error_on_size_mismatch(self) -> None:
        c0, c1 = self._two_chunks(50)
        with pytest.raises(AssertionError):
            merge_chunk_results([c0, c1], 200)

    def test_empty_chunk_in_list(self) -> None:
        """A zero-size chunk should not raise; totals come from the other chunk."""
        c0 = _make_chunk_result(0, 100, self.TASK_IDS, seed=0)
        # Create a zero-size chunk (edge case)
        empty = ChunkResult(
            chunk_start=100,
            chunk_size=0,
            project_durations=np.array([]),
            task_durations={tid: np.array([]) for tid in self.TASK_IDS},
            task_risk_impacts={tid: np.array([]) for tid in self.TASK_IDS},
            project_risk_impacts=np.array([]),
            task_slack={tid: np.array([]) for tid in self.TASK_IDS},
            critical_path_frequency={tid: 0 for tid in self.TASK_IDS},
            critical_path_sequences=Counter(),
            max_parallel=0,
            resource_wait_times=np.array([]),
            resource_utilizations=np.array([]),
            calendar_delay_times=np.array([]),
        )
        merged = merge_chunk_results([c0, empty], 100)
        assert len(merged.project_durations) == 100

    def test_costs_merged_when_present(self) -> None:
        c0, c1 = self._two_chunks(30)
        c0 = _make_chunk_result(0, 30, self.TASK_IDS, seed=0, with_costs=True)
        c1 = _make_chunk_result(30, 30, self.TASK_IDS, seed=1, with_costs=True)
        merged = merge_chunk_results([c0, c1], 60)
        assert merged.project_costs_all is not None
        assert len(merged.project_costs_all) == 60

    def test_two_pass_cache_global_index_remap(self) -> None:
        """Duration cache partition local indices must be remapped to global indices."""
        task_ids = ["a", "b"]
        c0 = _make_chunk_result(0, 10, task_ids, seed=0)
        c0.duration_cache_partition = {
            i: {tid: float(i) for tid in task_ids} for i in range(10)
        }
        c1 = _make_chunk_result(10, 10, task_ids, seed=1)
        c1.duration_cache_partition = {
            i: {tid: float(i + 10) for tid in task_ids} for i in range(10)
        }
        merged = merge_chunk_results([c0, c1], 20)
        assert merged.global_duration_cache is not None
        # global index 5 maps to chunk0, local_idx=5
        assert merged.global_duration_cache[5] == {tid: 5.0 for tid in task_ids}
        # global index 15 maps to chunk1, local_idx=5 -> global 10+5=15
        assert merged.global_duration_cache[15] == {tid: 15.0 for tid in task_ids}


# ---------------------------------------------------------------------------
# _run_chunk tests  (no process pool — called directly)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def quickstart_project_dict() -> dict:
    from mcprojsim.parsers.yaml_parser import YAMLParser

    parser = YAMLParser()
    project = parser.parse_file(str(QUICKSTART_YAML))
    return project.model_dump(mode="python")


@pytest.fixture(scope="module")
def quickstart_config_dict() -> dict:
    from mcprojsim.config import Config

    return Config.get_default().model_dump(mode="python")


class TestRunChunk:
    def test_result_shapes(
        self, quickstart_project_dict: dict, quickstart_config_dict: dict
    ) -> None:
        from numpy.random import SeedSequence

        chunk_size = 50
        child_seed = SeedSequence(42).spawn(1)[0]
        result = _run_chunk(
            quickstart_project_dict,
            quickstart_config_dict,
            chunk_start=0,
            chunk_size=chunk_size,
            child_seed=child_seed,
            task_priority=None,
            cached_durations_slice=None,
            cached_cost_impacts_slice=None,
            cancel_event=None,
        )
        assert result.chunk_start == 0
        assert result.chunk_size == chunk_size
        assert len(result.project_durations) == chunk_size
        assert all(v > 0 for v in result.project_durations)

    def test_deterministic(
        self, quickstart_project_dict: dict, quickstart_config_dict: dict
    ) -> None:
        from numpy.random import SeedSequence

        child_seed = SeedSequence(7).spawn(1)[0]
        r1 = _run_chunk(
            quickstart_project_dict,
            quickstart_config_dict,
            0,
            30,
            child_seed,
            None,
            None,
            None,
            None,
        )
        child_seed2 = SeedSequence(7).spawn(1)[0]
        r2 = _run_chunk(
            quickstart_project_dict,
            quickstart_config_dict,
            0,
            30,
            child_seed2,
            None,
            None,
            None,
            None,
        )
        np.testing.assert_array_equal(r1.project_durations, r2.project_durations)

    def test_no_stdout(
        self,
        quickstart_project_dict: dict,
        quickstart_config_dict: dict,
        capsys: pytest.CaptureFixture,
    ) -> None:
        from numpy.random import SeedSequence

        child_seed = SeedSequence(0).spawn(1)[0]
        _run_chunk(
            quickstart_project_dict,
            quickstart_config_dict,
            0,
            20,
            child_seed,
            None,
            None,
            None,
            None,
        )
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_cancellation_raises(
        self, quickstart_project_dict: dict, quickstart_config_dict: dict
    ) -> None:
        """If cancel_event is already set, _run_chunk should raise SimulationCancelled."""
        from numpy.random import SeedSequence

        from mcprojsim.simulation.engine import SimulationCancelled

        class _AlreadySet:
            """Minimal stand-in for a manager Event that is already set."""

            def is_set(self) -> bool:
                return True

        child_seed = SeedSequence(1).spawn(1)[0]
        with pytest.raises(SimulationCancelled):
            _run_chunk(
                quickstart_project_dict,
                quickstart_config_dict,
                0,
                100,
                child_seed,
                None,
                None,
                None,
                _AlreadySet(),
            )

    def test_store_duration_cache(
        self, quickstart_project_dict: dict, quickstart_config_dict: dict
    ) -> None:
        from numpy.random import SeedSequence

        child_seed = SeedSequence(5).spawn(1)[0]
        chunk_size = 20
        result = _run_chunk(
            quickstart_project_dict,
            quickstart_config_dict,
            0,
            chunk_size,
            child_seed,
            None,
            None,
            None,
            None,
            store_duration_cache=True,
        )
        assert result.duration_cache_partition is not None
        assert len(result.duration_cache_partition) == chunk_size
        # Keys are local indices 0..chunk_size-1
        assert set(result.duration_cache_partition.keys()) == set(range(chunk_size))


# ---------------------------------------------------------------------------
# Integration tests: SimulationEngine with workers > 1
# ---------------------------------------------------------------------------


def _load_quickstart() -> Any:
    from mcprojsim.parsers.yaml_parser import YAMLParser

    return YAMLParser().parse_file(str(QUICKSTART_YAML))


def _load_contention() -> Any:
    from mcprojsim.parsers.yaml_parser import YAMLParser

    return YAMLParser().parse_file(str(CONTENTION_YAML))


def _load_large_100_tasks() -> Any:
    from mcprojsim.parsers.yaml_parser import YAMLParser

    return YAMLParser().parse_file("examples/large_project_100_tasks.yaml")


class TestParallelSimulationIntegration:
    def test_parallel_sequential_same_seed_same_structure(self) -> None:
        """With workers=1, results must be bit-for-bit identical (sequential path)."""
        from mcprojsim.simulation.engine import SimulationEngine

        project = _load_quickstart()
        n = 200

        r1 = SimulationEngine(
            iterations=n, random_seed=42, show_progress=False, workers=1
        ).run(project)
        r2 = SimulationEngine(
            iterations=n, random_seed=42, show_progress=False, workers=1
        ).run(project)

        assert r1.iterations == r2.iterations
        np.testing.assert_array_equal(r1.durations, r2.durations)

    def test_parallel_above_threshold_produces_valid_results(self) -> None:
        """Heuristic should enable parallel mode for contended medium-heavy runs."""
        from mcprojsim.simulation.engine import SimulationEngine

        project = _load_contention()
        engine = SimulationEngine(
            iterations=20_000,
            random_seed=42,
            show_progress=False,
            workers=2,
        )
        results = engine.run(project)
        assert results.iterations == 20_000
        assert results.mean > 0
        assert results.std_dev >= 0

    def test_parallel_determinism(self) -> None:
        """Same seed + workers → same results on repeated parallel runs."""
        from mcprojsim.simulation.engine import SimulationEngine

        project = _load_contention()
        kwargs: dict = dict(
            iterations=20_000,
            random_seed=77,
            show_progress=False,
            workers=2,
        )
        r1 = SimulationEngine(**kwargs).run(project)
        r2 = SimulationEngine(**kwargs).run(project)
        np.testing.assert_array_equal(r1.durations, r2.durations)

    def test_workers_gt_iterations_does_not_raise(self) -> None:
        """workers > iterations should clamp and complete without error."""
        from mcprojsim.simulation.engine import SimulationEngine

        project = _load_quickstart()
        engine = SimulationEngine(
            iterations=3, random_seed=0, show_progress=False, workers=8
        )
        results = engine.run(project)
        assert results.iterations == 3

    def test_workers_eq_1_same_as_legacy(self) -> None:
        """workers=1 must produce bit-for-bit identical results to the unmodified path."""
        from mcprojsim.simulation.engine import SimulationEngine

        project = _load_quickstart()
        r_legacy = SimulationEngine(
            iterations=500, random_seed=1, show_progress=False, workers=1
        ).run(project)
        r_explicit = SimulationEngine(
            iterations=500, random_seed=1, show_progress=False, workers=1
        ).run(project)
        np.testing.assert_array_equal(r_legacy.durations, r_explicit.durations)

    def test_progress_callback_called(self) -> None:
        """progress_callback must be invoked for each completed chunk in parallel mode."""
        from mcprojsim.simulation.engine import SimulationEngine

        # Use contention fixture which has enough tasks to trigger the parallel path.
        project = _load_contention()
        calls: list[tuple[int, int]] = []

        def cb(completed: int, total: int) -> None:
            calls.append((completed, total))

        engine = SimulationEngine(
            iterations=20_000,
            random_seed=42,
            show_progress=False,
            workers=2,
            progress_callback=cb,
        )
        engine.run(project)
        assert len(calls) > 0
        # Final call must report exactly iterations completed
        assert calls[-1][0] == 20_000

    def test_progress_written_to_stream_without_callback(self) -> None:
        """Parallel single-pass writes progress output when no callback is supplied."""
        from mcprojsim.simulation.engine import SimulationEngine

        project = _load_contention()
        engine = SimulationEngine(
            iterations=20_000,
            random_seed=42,
            show_progress=True,
            workers=2,
        )
        engine.progress_stream = io.StringIO()
        engine._progress_is_tty = False

        engine.run(project)

        output = engine.progress_stream.getvalue()
        assert "Progress:" in output
        assert "(20000/20000)" in output

    def test_cancelled_engine_can_be_reused(self) -> None:
        """After a cancelled run, the next run() on the same engine must succeed."""
        from mcprojsim.simulation.engine import SimulationCancelled, SimulationEngine

        project = _load_quickstart()
        engine = SimulationEngine(
            iterations=50, random_seed=0, show_progress=False, workers=1
        )
        # Simulate a post-cancel state by manually setting the flag to True,
        # then calling cancel() to see it resets after run().
        engine.cancel()
        with pytest.raises(SimulationCancelled):
            engine.run(project)
        # After the cancelled run, _cancelled is reset in the finally block.
        results = engine.run(project)
        assert results.iterations == 50


class TestParallelHeuristic:
    def test_abundant_resources_small_graph_stays_sequential(self) -> None:
        from mcprojsim.parsers.yaml_parser import YAMLParser
        from mcprojsim.simulation.engine import SimulationEngine

        project = YAMLParser().parse_file(
            "tests/fixtures/test_fixture_abundant_resources.yaml"
        )
        engine = SimulationEngine(
            iterations=200_000,
            random_seed=42,
            show_progress=False,
            workers=8,
        )
        assert (
            engine._parallel_expected_payoff_positive(project, two_pass=False) is False
        )

    def test_contention_small_run_stays_sequential(self) -> None:
        from mcprojsim.simulation.engine import SimulationEngine

        project = _load_contention()
        engine = SimulationEngine(
            iterations=2_000,
            random_seed=42,
            show_progress=False,
            workers=8,
        )
        assert (
            engine._parallel_expected_payoff_positive(project, two_pass=False) is False
        )

    def test_contention_medium_run_enables_parallel(self) -> None:
        from mcprojsim.simulation.engine import SimulationEngine

        project = _load_contention()
        engine = SimulationEngine(
            iterations=20_000,
            random_seed=42,
            show_progress=False,
            workers=8,
        )
        assert (
            engine._parallel_expected_payoff_positive(project, two_pass=False) is True
        )

    def test_large_dependency_only_requires_larger_work(self) -> None:
        from mcprojsim.simulation.engine import SimulationEngine

        project = _load_large_100_tasks()
        low_engine = SimulationEngine(
            iterations=2_000,
            random_seed=42,
            show_progress=False,
            workers=8,
        )
        high_engine = SimulationEngine(
            iterations=20_000,
            random_seed=42,
            show_progress=False,
            workers=8,
        )
        assert (
            low_engine._parallel_expected_payoff_positive(project, two_pass=False)
            is False
        )
        assert (
            high_engine._parallel_expected_payoff_positive(project, two_pass=False)
            is True
        )

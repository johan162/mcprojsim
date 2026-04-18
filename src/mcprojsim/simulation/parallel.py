"""Parallel simulation helpers: chunk partitioning, seed management, and merge."""

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from numpy.random import MT19937, RandomState, SeedSequence

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------

PARALLEL_MIN_ITERATIONS: int = 500
PARALLEL_MIN_TASKS: int = 5


# -------------------------------------------------------------------
# ChunkResult
# -------------------------------------------------------------------


@dataclass
class ChunkResult:
    """Partial accumulators from one worker's iteration chunk."""

    chunk_start: int
    chunk_size: int
    project_durations: np.ndarray  # shape (chunk_size,)
    task_durations: Dict[str, np.ndarray]  # per-task, shape (chunk_size,)
    task_risk_impacts: Dict[str, np.ndarray]
    project_risk_impacts: np.ndarray  # shape (chunk_size,)
    task_slack: Dict[str, np.ndarray]
    critical_path_frequency: Dict[str, int]
    critical_path_sequences: "Counter[Tuple[str, ...]]"
    max_parallel: int
    resource_wait_times: np.ndarray  # shape (chunk_size,)
    resource_utilizations: np.ndarray  # shape (chunk_size,)
    calendar_delay_times: np.ndarray  # shape (chunk_size,)
    project_costs: Optional[np.ndarray] = None  # shape (chunk_size,) or None
    task_costs: Optional[Dict[str, np.ndarray]] = None
    # Two-pass only: duration cache keyed by LOCAL iteration index (0-based in chunk).
    # Parent remaps: global_idx = chunk_start + local_idx.
    duration_cache_partition: Optional[Dict[int, Dict[str, float]]] = None
    cost_impact_cache_partition: Optional[Dict[int, Dict[str, float]]] = None


# -------------------------------------------------------------------
# Merged accumulator type alias (matches _build_results signature)
# -------------------------------------------------------------------


@dataclass
class MergedAccumulators:
    """Merged accumulators ready to be passed to _build_results."""

    project_durations: np.ndarray
    task_durations_all: Dict[str, np.ndarray]
    task_risk_impacts_all: Dict[str, np.ndarray]
    project_risk_impacts_all: np.ndarray
    task_slack_accum: Dict[str, np.ndarray]
    critical_path_frequency: Dict[str, int]
    critical_path_sequences: "Counter[Tuple[str, ...]]"
    max_parallel_overall: int
    resource_wait_time_all: np.ndarray
    resource_utilization_all: np.ndarray
    calendar_delay_time_all: np.ndarray
    project_costs_all: Optional[np.ndarray] = None
    task_costs_all: Optional[Dict[str, np.ndarray]] = None
    # Two-pass: global-index-keyed caches (chunk_start + local offset applied)
    global_duration_cache: Optional[Dict[int, Dict[str, float]]] = field(default=None)
    global_cost_impact_cache: Optional[Dict[int, Dict[str, float]]] = field(
        default=None
    )


# -------------------------------------------------------------------
# Chunk partitioning
# -------------------------------------------------------------------


def partition_chunks(iterations: int, workers: int) -> List[Tuple[int, int]]:
    """Return a list of (start, size) pairs covering all iterations.

    The number of chunks is ``min(iterations, max(workers * 8, 32))`` so that
    progress granularity is decoupled from the worker count.  Chunks are
    deterministic for a fixed ``(iterations, workers)`` tuple.

    Args:
        iterations: Total number of iterations to cover.
        workers: Number of parallel workers.  Used only to scale chunk count.

    Returns:
        List of ``(chunk_start, chunk_size)`` pairs ordered by ``chunk_start``.
        The sum of sizes equals *iterations*.
    """
    if iterations <= 0:
        return []
    target_count = min(iterations, max(workers * 8, 32))
    chunk_size = math.ceil(iterations / target_count)
    chunks: List[Tuple[int, int]] = []
    start = 0
    while start < iterations:
        size = min(chunk_size, iterations - start)
        chunks.append((start, size))
        start += size
    return chunks


# -------------------------------------------------------------------
# Seed partitioning
# -------------------------------------------------------------------


def partition_seeds(
    random_seed: Optional[int],
    n_chunks: int,
    parent_seq: Optional[SeedSequence] = None,
) -> List[SeedSequence]:
    """Return *n_chunks* child SeedSequence objects derived from *random_seed*.

    Args:
        random_seed: Root entropy value.  ``None`` uses unseeded entropy.
        n_chunks: Number of child sequences to produce.  Must be >= 1.
        parent_seq: Pre-constructed parent SeedSequence.  When provided,
            *random_seed* is ignored.  Useful for two-pass independence.

    Returns:
        List of child SeedSequence objects, one per chunk.

    Raises:
        ValueError: If *n_chunks* < 1.
    """
    if n_chunks < 1:
        raise ValueError(f"n_chunks must be >= 1, got {n_chunks}")
    seq = parent_seq if parent_seq is not None else SeedSequence(random_seed)
    return list(seq.spawn(n_chunks))


# -------------------------------------------------------------------
# Merge
# -------------------------------------------------------------------


def merge_chunk_results(
    chunks: List[ChunkResult],
    total_iterations: int,
) -> MergedAccumulators:
    """Merge a list of :class:`ChunkResult` objects into full accumulators.

    Chunks are sorted by ``chunk_start`` before merging so that the
    concatenation order is deterministic regardless of future-completion order.

    Args:
        chunks: List of partial results from workers.
        total_iterations: Expected total iteration count.

    Returns:
        :class:`MergedAccumulators` ready for ``_build_results``.

    Raises:
        AssertionError: If the sum of chunk sizes does not equal *total_iterations*.
    """
    chunks = sorted(chunks, key=lambda c: c.chunk_start)

    actual_total = sum(c.chunk_size for c in chunks)
    assert actual_total == total_iterations, (
        f"Chunk sizes sum to {actual_total} but expected {total_iterations}. "
        "This indicates a partitioning bug."
    )

    if not chunks:
        empty: np.ndarray = np.array([], dtype=float)
        return MergedAccumulators(
            project_durations=empty,
            task_durations_all={},
            task_risk_impacts_all={},
            project_risk_impacts_all=empty,
            task_slack_accum={},
            critical_path_frequency={},
            critical_path_sequences=Counter(),
            max_parallel_overall=0,
            resource_wait_time_all=empty,
            resource_utilization_all=empty,
            calendar_delay_time_all=empty,
        )

    project_durations = np.concatenate([c.project_durations for c in chunks])
    project_risk_impacts_all = np.concatenate([c.project_risk_impacts for c in chunks])
    resource_wait_time_all = np.concatenate([c.resource_wait_times for c in chunks])
    resource_utilization_all = np.concatenate([c.resource_utilizations for c in chunks])
    calendar_delay_time_all = np.concatenate([c.calendar_delay_times for c in chunks])

    # Per-task arrays
    task_ids: Sequence[str] = list(chunks[0].task_durations.keys())
    task_durations_all: Dict[str, np.ndarray] = {
        tid: np.concatenate([c.task_durations[tid] for c in chunks]) for tid in task_ids
    }
    task_risk_impacts_all: Dict[str, np.ndarray] = {
        tid: np.concatenate([c.task_risk_impacts[tid] for c in chunks])
        for tid in task_ids
    }
    task_slack_accum: Dict[str, np.ndarray] = {
        tid: np.concatenate([c.task_slack[tid] for c in chunks]) for tid in task_ids
    }

    # Critical path frequency: sum counts (not union)
    critical_path_frequency: Dict[str, int] = {}
    for c in chunks:
        for tid, count in c.critical_path_frequency.items():
            critical_path_frequency[tid] = critical_path_frequency.get(tid, 0) + count

    # Critical path sequences: Counter sum
    critical_path_sequences: Counter[Tuple[str, ...]] = Counter()
    for c in chunks:
        critical_path_sequences += c.critical_path_sequences

    max_parallel_overall = max(c.max_parallel for c in chunks)

    # Cost arrays (optional)
    project_costs_all: Optional[np.ndarray] = None
    task_costs_all: Optional[Dict[str, np.ndarray]] = None
    if chunks[0].project_costs is not None:
        project_costs_all = np.concatenate(
            [c.project_costs for c in chunks if c.project_costs is not None]
        )
        if chunks[0].task_costs is not None:
            task_costs_all = {
                tid: np.concatenate(
                    [c.task_costs[tid] for c in chunks if c.task_costs is not None]  # type: ignore[index]
                )
                for tid in task_ids
            }

    # Two-pass caches: remap local indices to global indices
    global_duration_cache: Optional[Dict[int, Dict[str, float]]] = None
    global_cost_impact_cache: Optional[Dict[int, Dict[str, float]]] = None
    if any(c.duration_cache_partition is not None for c in chunks):
        global_duration_cache = {}
        for c in chunks:
            if c.duration_cache_partition is not None:
                for local_idx, dur_map in c.duration_cache_partition.items():
                    global_duration_cache[c.chunk_start + local_idx] = dur_map
    if any(c.cost_impact_cache_partition is not None for c in chunks):
        global_cost_impact_cache = {}
        for c in chunks:
            if c.cost_impact_cache_partition is not None:
                for local_idx, impact_map in c.cost_impact_cache_partition.items():
                    global_cost_impact_cache[c.chunk_start + local_idx] = impact_map

    return MergedAccumulators(
        project_durations=project_durations,
        task_durations_all=task_durations_all,
        task_risk_impacts_all=task_risk_impacts_all,
        project_risk_impacts_all=project_risk_impacts_all,
        task_slack_accum=task_slack_accum,
        critical_path_frequency=critical_path_frequency,
        critical_path_sequences=critical_path_sequences,
        max_parallel_overall=max_parallel_overall,
        resource_wait_time_all=resource_wait_time_all,
        resource_utilization_all=resource_utilization_all,
        calendar_delay_time_all=calendar_delay_time_all,
        project_costs_all=project_costs_all,
        task_costs_all=task_costs_all,
        global_duration_cache=global_duration_cache,
        global_cost_impact_cache=global_cost_impact_cache,
    )


# -------------------------------------------------------------------
# Worker function (top-level for pickling)
# -------------------------------------------------------------------


def _run_chunk(  # pyright: ignore[reportUnusedFunction]
    project_dict: dict[str, Any],
    config_dict: dict[str, Any],
    chunk_start: int,
    chunk_size: int,
    child_seed: SeedSequence,
    task_priority: Optional[Dict[str, float]],
    cached_durations_slice: Optional[Dict[int, Dict[str, float]]],
    cached_cost_impacts_slice: Optional[Dict[int, Dict[str, float]]],
    cancel_event: Optional[Any],
    store_duration_cache: bool = False,
) -> ChunkResult:
    """Execute one iteration chunk in a worker process.

    This function is module-level so that it is picklable under ``spawn``.

    Args:
        project_dict: Serialised project from ``Project.model_dump()``.
        config_dict: Serialised config from ``Config.model_dump()``.
        chunk_start: Global index of the first iteration in this chunk.
        chunk_size: Number of iterations to run.
        child_seed: Chunk-specific SeedSequence child.
        task_priority: Optional criticality index for priority-ordered scheduling.
        cached_durations_slice: Per-global-iteration cached durations for replay
            (two-pass pass-2 only).  Keys are global iteration indices.
        cached_cost_impacts_slice: Same for cost impacts.
        cancel_event: Manager-backed event proxy.  Checked each iteration.
        store_duration_cache: When True, store per-local-iteration duration maps
            for pass-1 parallel two-pass replay.

    Returns:
        :class:`ChunkResult` with accumulated arrays for this chunk.
    """
    from collections import Counter as _Counter

    from mcprojsim.config import Config
    from mcprojsim.models.project import Project
    from mcprojsim.simulation.distributions import DistributionSampler
    from mcprojsim.simulation.engine import (
        SimulationCancelled,
        SimulationEngine,
    )
    from mcprojsim.simulation.risk_evaluator import RiskEvaluator
    from mcprojsim.simulation.scheduler import TaskScheduler

    # Reconstruct models
    project = Project.model_validate(project_dict)
    config = Config.model_validate(config_dict)

    # Build chunk-specific RNG (must wrap SeedSequence in MT19937)
    rng = RandomState(MT19937(child_seed))

    # Build engine solely for helper method access; no recursion into parallel path.
    engine = SimulationEngine(
        workers=1,
        random_seed=None,
        config=config,
        show_progress=False,
        progress_callback=None,
    )
    # Override the engine's random state and sampler with our chunk-local rng.
    engine.random_state = rng
    engine.sampler = DistributionSampler(rng, config.get_lognormal_high_z_value())
    engine.risk_evaluator = RiskEvaluator(rng)

    # Scheduler uses the same rng for reproducibility within the chunk.
    scheduler = TaskScheduler(project, rng, config)
    hours_per_day = project.project.hours_per_day
    static_data = engine._build_project_run_static_data(project)  # pyright: ignore[reportPrivateUsage]

    # Accumulator setup
    task_ids = [t.id for t in project.tasks]
    project_durations = np.zeros(chunk_size)
    task_durations_acc: Dict[str, list[float]] = {tid: [] for tid in task_ids}
    task_risk_impacts_acc: Dict[str, list[float]] = {tid: [] for tid in task_ids}
    project_risk_impacts_acc: list[float] = []
    task_slack_acc: Dict[str, list[float]] = {tid: [] for tid in task_ids}
    critical_path_frequency: Dict[str, int] = {tid: 0 for tid in task_ids}
    critical_path_sequences: Counter[Tuple[str, ...]] = _Counter()
    max_parallel = 0
    resource_wait_times: list[float] = []
    resource_utilizations: list[float] = []
    calendar_delay_times: list[float] = []

    cost_active = engine._cost_estimation_active(project)  # pyright: ignore[reportPrivateUsage]
    project_costs_acc: list[float] = []
    task_costs_acc: Dict[str, list[float]] = {tid: [] for tid in task_ids}

    duration_cache_partition: Dict[int, Dict[str, float]] = {}
    cost_impact_cache_partition: Dict[int, Dict[str, float]] = {}

    for local_idx in range(chunk_size):
        if cancel_event is not None and cancel_event.is_set():
            raise SimulationCancelled()

        global_idx = chunk_start + local_idx

        # Resolve cached replay data for two-pass pass-2
        cached_dur: Optional[Dict[str, float]] = None
        cached_cost: Optional[Dict[str, float]] = None
        if cached_durations_slice is not None and global_idx in cached_durations_slice:
            cached_dur = cached_durations_slice[global_idx]
        if (
            cached_cost_impacts_slice is not None
            and global_idx in cached_cost_impacts_slice
        ):
            cached_cost = cached_cost_impacts_slice[global_idx]

        (
            duration,
            task_durations,
            critical_path,
            critical_paths,
            task_risk_impacts,
            project_risk_impact,
            task_risk_cost_impacts,
            project_risk_cost_impact,
            schedule,
            slack,
            max_p,
            constrained_diagnostics,
        ) = engine._run_iteration_with_sampler(  # pyright: ignore[reportPrivateUsage]
            project,
            scheduler,
            hours_per_day,
            static_data,
            engine.sampler,
            engine.risk_evaluator,
            task_priority=task_priority,
            cached_task_durations=cached_dur,
            cached_task_risk_cost_impacts=cached_cost,
        )

        project_durations[local_idx] = duration
        max_parallel = max(max_parallel, max_p)

        for tid in task_ids:
            task_durations_acc[tid].append(task_durations[tid])
            task_risk_impacts_acc[tid].append(task_risk_impacts[tid])
            task_slack_acc[tid].append(slack.get(tid, 0.0))
        project_risk_impacts_acc.append(project_risk_impact)
        resource_wait_times.append(constrained_diagnostics["resource_wait_time_hours"])
        resource_utilizations.append(constrained_diagnostics["resource_utilization"])
        calendar_delay_times.append(
            constrained_diagnostics["calendar_delay_time_hours"]
        )

        if cost_active:
            total_cost, per_task_cost = (
                engine._compute_iteration_costs(  # pyright: ignore[reportPrivateUsage]
                    project,
                    task_durations,
                    task_risk_cost_impacts,
                    project_risk_cost_impact,
                    schedule,
                )
            )
            project_costs_acc.append(total_cost)
            for tid in task_ids:
                task_costs_acc[tid].append(per_task_cost.get(tid, 0.0))

        for tid in critical_path:
            critical_path_frequency[tid] += 1
        critical_path_sequences.update(critical_paths)

        if store_duration_cache:
            duration_cache_partition[local_idx] = dict(task_durations)
            cost_impact_cache_partition[local_idx] = dict(task_risk_cost_impacts)

    return ChunkResult(
        chunk_start=chunk_start,
        chunk_size=chunk_size,
        project_durations=project_durations,
        task_durations={tid: np.array(task_durations_acc[tid]) for tid in task_ids},
        task_risk_impacts={
            tid: np.array(task_risk_impacts_acc[tid]) for tid in task_ids
        },
        project_risk_impacts=np.array(project_risk_impacts_acc),
        task_slack={tid: np.array(task_slack_acc[tid]) for tid in task_ids},
        critical_path_frequency=critical_path_frequency,
        critical_path_sequences=critical_path_sequences,
        max_parallel=max_parallel,
        resource_wait_times=np.array(resource_wait_times),
        resource_utilizations=np.array(resource_utilizations),
        calendar_delay_times=np.array(calendar_delay_times),
        project_costs=np.array(project_costs_acc) if cost_active else None,
        task_costs=(
            {tid: np.array(task_costs_acc[tid]) for tid in task_ids}
            if cost_active
            else None
        ),
        duration_cache_partition=(
            duration_cache_partition if store_duration_cache else None
        ),
        cost_impact_cache_partition=(
            cost_impact_cache_partition if store_duration_cache else None
        ),
    )

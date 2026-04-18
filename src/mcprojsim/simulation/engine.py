"""Monte Carlo simulation engine."""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import logging
import multiprocessing
import sys
from typing import Any, Callable, Dict, Optional, TextIO, Union

import numpy as np

from mcprojsim.config import (
    Config,
    ConstrainedSchedulingAssignmentMode,
    DEFAULT_SIMULATION_ITERATIONS,
    EffortUnit,
    EstimateRangeConfig,
)
from mcprojsim.models.project import (
    DistributionType,
    Project,
    STANDARD_HOURS_PER_DAY,
    Task,
    TaskEstimate,
    convert_to_hours,
)
from mcprojsim.models.simulation import (
    CriticalPathRecord,
    SimulationResults,
    TwoPassDelta,
)
from mcprojsim.simulation.parallel import (
    PARALLEL_MIN_ITERATIONS,
    PARALLEL_MIN_TASKS,
)
from mcprojsim.simulation.distributions import DistributionSampler
from mcprojsim.simulation.risk_evaluator import RiskEvaluator
from mcprojsim.simulation.scheduler import TaskScheduler

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskRunStaticData:
    """Task-specific data that does not change within one simulation run."""

    task: Task
    resolved_estimate: TaskEstimate
    hours_multiplier: float
    uncertainty_multiplier: float


@dataclass(frozen=True)
class ProjectRunStaticData:
    """Project-level cached inputs reused across all iterations in one run."""

    task_data: tuple[TaskRunStaticData, ...]
    task_ids: tuple[str, ...]


class DurationCache:
    """Cache of sampled task durations from pass-1 for deterministic replay in pass-2.

    Keys are ``(iteration_index, task_id)``; values are sampled durations in hours.
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[int, str], float] = {}

    def store(self, iteration_idx: int, task_id: str, duration_hours: float) -> None:
        """Store a sampled duration for a given iteration and task."""
        self._cache[(iteration_idx, task_id)] = duration_hours

    def retrieve(self, iteration_idx: int, task_id: str) -> float:
        """Return the cached duration; raises KeyError if not found."""
        key = (iteration_idx, task_id)
        if key not in self._cache:
            raise KeyError(
                f"No cached duration for task '{task_id}' in iteration {iteration_idx}"
            )
        return self._cache[key]

    def __len__(self) -> int:
        return len(self._cache)


class CostImpactCache:
    """Cache of per-task risk cost impacts from pass-1 for deterministic replay.

    Without this cache, pass-2 would zero out all task-level cost impacts for
    replayed iterations, causing cost underestimation when task risks carry a
    ``cost_impact``. The cache pairs each replayed iteration with the cost
    impacts computed by the same probability roll in pass-1, preserving the
    correlation between schedule overruns and cost overruns.
    """

    def __init__(self) -> None:
        self._cache: dict[int, Dict[str, float]] = {}

    def store(self, iteration_idx: int, task_cost_impacts: Dict[str, float]) -> None:
        """Store the per-task cost impact map for a given iteration."""
        self._cache[iteration_idx] = dict(task_cost_impacts)

    def retrieve(self, iteration_idx: int) -> Dict[str, float]:
        """Return the cached per-task cost impact map; raises KeyError if missing."""
        if iteration_idx not in self._cache:
            raise KeyError(f"No cached cost impacts for iteration {iteration_idx}")
        return self._cache[iteration_idx]

    def __contains__(self, iteration_idx: object) -> bool:
        return iteration_idx in self._cache


class SimulationCancelled(Exception):
    """Raised when a running simulation is cancelled via :meth:`SimulationEngine.cancel`."""


class SimulationEngine:
    """Monte Carlo simulation engine for project estimation."""

    def __init__(
        self,
        iterations: int = DEFAULT_SIMULATION_ITERATIONS,
        random_seed: Optional[int] = None,
        config: Optional[Config] = None,
        show_progress: bool = True,
        two_pass: bool = False,
        pass1_iterations: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        workers: int = 1,
    ):
        """Initialize simulation engine.

        Args:
            iterations: Number of Monte Carlo iterations
            random_seed: Random seed for reproducibility
            config: Configuration object
            show_progress: Whether to show progress updates
            two_pass: Enable criticality-two-pass scheduling (overrides config).
                Only has effect when resource-constrained scheduling is active.
            pass1_iterations: Number of pass-1 iterations for criticality ranking.
                Overrides config value when provided.  Capped to ``iterations``.
            progress_callback: Optional callback invoked with
                ``(completed_iterations, total_iterations)`` during the run.
                When provided, stdout progress output is suppressed regardless
                of the *show_progress* flag.
            workers: Number of worker processes for parallel execution.
                ``1`` (default) forces sequential execution.  Values > 1
                enable a ``ProcessPoolExecutor`` with that many workers.
                ``auto`` is resolved by the CLI layer before constructing
                the engine; accept only integers here.
        """
        self.iterations = iterations
        self.random_seed = random_seed
        self.config = config or Config.get_default()
        self.show_progress = show_progress
        self._progress_callback = progress_callback
        self.progress_stream: TextIO = sys.stdout
        self._progress_is_tty = self.progress_stream.isatty()
        self._cancelled: bool = False
        self.workers: int = workers
        # Set to a manager-backed Event proxy during a parallel run; None otherwise.
        self._active_cancel_event: Optional[Any] = None

        # Two-pass CLI override takes precedence over config.
        if two_pass:
            self.config.constrained_scheduling.assignment_mode = (
                ConstrainedSchedulingAssignmentMode.CRITICALITY_TWO_PASS
            )
        if pass1_iterations is not None:
            self.config.constrained_scheduling.pass1_iterations = pass1_iterations

        # Initialize random state
        self.random_state = np.random.RandomState(random_seed)

        # Initialize components
        self.sampler = DistributionSampler(
            self.random_state, self.config.get_lognormal_high_z_value()
        )
        self.risk_evaluator = RiskEvaluator(self.random_state)

    def cancel(self) -> None:
        """Request cancellation of a running simulation.

        The engine checks this flag at the top of each iteration.  When set,
        the current ``run()`` call raises :class:`SimulationCancelled`.
        For parallel runs the active manager-backed cancel event is also set
        so that worker processes learn about cancellation promptly.
        """
        self._cancelled = True
        if self._active_cancel_event is not None:
            self._active_cancel_event.set()

    def run(self, project: Project) -> SimulationResults:
        """Run Monte Carlo simulation for project.

        When ``assignment_mode`` is ``criticality_two_pass`` and resource
        constraints are active, the engine performs two passes:

        - **Pass 1** (pass1_iterations): greedy single-pass to build criticality
          indices.  Task durations are stored in a :class:`DurationCache` for
          deterministic replay.
        - **Pass 2** (self.iterations): criticality-prioritized scheduling.
          The first pass1_iterations use cached durations; remaining iterations
          use fresh samples.

        The final ``SimulationResults`` contains pass-2 statistics and an
        optional :class:`TwoPassDelta` traceability block when two-pass is used.

        Args:
            project: Project to simulate

        Returns:
            Simulation results
        """
        # Reset cancellation state at the end so a previously cancelled engine
        # can be reused, while still allowing cancel() called before run() to raise.
        try:
            static_data = self._build_project_run_static_data(project)
            use_two_pass = (
                self.config.constrained_scheduling.assignment_mode
                == ConstrainedSchedulingAssignmentMode.CRITICALITY_TWO_PASS
                and len(project.resources) > 0
            )

            if use_two_pass:
                return self._run_two_pass(project, static_data)
            return self._run_single_pass(project, static_data)
        finally:
            self._cancelled = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resource_contention_index(self, project: Project) -> float:
        """Estimate how strongly tasks compete for shared named resources.

        Returns a value in [0, 1], where 0 means no measurable sharing and
        1 means every resource assignment targets a resource that is shared by
        at least one other task.
        """
        if not project.resources:
            return 0.0

        assignment_counts: Dict[str, int] = {}
        total_assignments = 0
        for task in project.tasks:
            for res_name in task.resources:
                total_assignments += 1
                assignment_counts[res_name] = assignment_counts.get(res_name, 0) + 1

        if total_assignments == 0:
            return 0.0

        shared_assignments = 0
        for task in project.tasks:
            for res_name in task.resources:
                if assignment_counts.get(res_name, 0) > 1:
                    shared_assignments += 1

        return shared_assignments / total_assignments

    def _parallel_expected_payoff_positive(
        self,
        project: Project,
        two_pass: bool = False,
    ) -> bool:
        """Return True when expected parallel payoff is positive for this run.

        The heuristic combines overall work size with scheduling complexity:

        - Work proxy: ``iterations * n_tasks``
        - Two-pass multiplier: pass-1 + pass-2 work roughly doubles scheduler cost
        - Resource contention: lower threshold when assignments are highly shared

        This keeps parallel mode off for tiny runs where process overhead
        dominates, while enabling it for large constrained workloads where
        scheduling work is expensive.
        """
        if self.workers <= 1:
            return False

        n_tasks = len(project.tasks)
        if n_tasks == 0:
            return False

        # Very small graphs rarely amortize multiprocessing overhead.
        if n_tasks < PARALLEL_MIN_TASKS:
            return False

        # Absolute floor: below this, spawn/IPC overhead is almost always dominant.
        if self.iterations < PARALLEL_MIN_ITERATIONS:
            return False

        pass_multiplier = 2 if two_pass else 1
        work_units = self.iterations * n_tasks * pass_multiplier

        # Dependency-only (or unconstrained) scheduling generally needs more work
        # before process-level parallelism pays off.
        if len(project.resources) == 0:
            return work_units >= 1_000_000

        contention_index = self._resource_contention_index(project)

        # Strongly contended resource assignments benefit earlier.
        if contention_index >= 0.5:
            return work_units >= 120_000
        if contention_index >= 0.2:
            return work_units >= 250_000
        return work_units >= 500_000

    def _run_single_pass(
        self,
        project: Project,
        static_data: ProjectRunStaticData,
    ) -> SimulationResults:
        """Run the standard (single-pass greedy) simulation."""
        if self._parallel_expected_payoff_positive(project, two_pass=False):
            return self._run_single_pass_parallel(project, static_data)

        scheduler = TaskScheduler(project, self.random_state, self.config)
        hours_per_day = project.project.hours_per_day

        # Storage for results
        project_durations = np.zeros(self.iterations)
        task_durations_all: Dict[str, list[float]] = {
            task.id: [] for task in project.tasks
        }
        task_risk_impacts_all: Dict[str, list[float]] = {
            task.id: [] for task in project.tasks
        }
        project_risk_impacts_all: list[float] = []
        task_slack_accum: Dict[str, list[float]] = {
            task.id: [] for task in project.tasks
        }
        critical_path_frequency: Dict[str, int] = {task.id: 0 for task in project.tasks}
        critical_path_sequences: Counter[tuple[str, ...]] = Counter()
        max_parallel_overall = 0
        resource_wait_time_all: list[float] = []
        resource_utilization_all: list[float] = []
        calendar_delay_time_all: list[float] = []
        last_reported_progress = -1

        cost_active = self._cost_estimation_active(project)
        project_costs_all: list[float] = []
        task_costs_all: Dict[str, list[float]] = {task.id: [] for task in project.tasks}

        for iteration in range(self.iterations):
            if self._cancelled:
                raise SimulationCancelled()

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
                max_parallel,
                constrained_diagnostics,
            ) = self._run_iteration(project, scheduler, hours_per_day, static_data)

            project_durations[iteration] = duration
            max_parallel_overall = max(max_parallel_overall, max_parallel)

            for task_id, task_duration in task_durations.items():
                task_durations_all[task_id].append(task_duration)
            for task_id, impact in task_risk_impacts.items():
                task_risk_impacts_all[task_id].append(impact)
            project_risk_impacts_all.append(project_risk_impact)
            resource_wait_time_all.append(
                constrained_diagnostics["resource_wait_time_hours"]
            )
            resource_utilization_all.append(
                constrained_diagnostics["resource_utilization"]
            )
            calendar_delay_time_all.append(
                constrained_diagnostics["calendar_delay_time_hours"]
            )

            if cost_active:
                total_cost, per_task_cost = self._compute_iteration_costs(
                    project,
                    task_durations,
                    task_risk_cost_impacts,
                    project_risk_cost_impact,
                    schedule,
                )
                project_costs_all.append(total_cost)
                for task_id, tc in per_task_cost.items():
                    task_costs_all[task_id].append(tc)

            for task_id, slack_val in slack.items():
                task_slack_accum[task_id].append(slack_val)

            for task_id in critical_path:
                critical_path_frequency[task_id] += 1

            critical_path_sequences.update(critical_paths)

            if self.show_progress or self._progress_callback is not None:
                last_reported_progress = self._maybe_report_progress(
                    iteration, self.iterations, last_reported_progress
                )

        if (
            self.show_progress
            and self._progress_callback is None
            and self._progress_is_tty
        ):
            self.progress_stream.write("\n")
            self.progress_stream.flush()

        return self._build_results(
            project,
            project_durations,
            task_durations_all,
            task_risk_impacts_all,
            project_risk_impacts_all,
            task_slack_accum,
            critical_path_frequency,
            critical_path_sequences,
            max_parallel_overall,
            resource_wait_time_all,
            resource_utilization_all,
            calendar_delay_time_all,
            project_costs_all=project_costs_all if cost_active else None,
            task_costs_all=task_costs_all if cost_active else None,
        )

    def _run_single_pass_parallel(
        self,
        project: Project,
        static_data: ProjectRunStaticData,
    ) -> SimulationResults:
        """Parallel variant of the single-pass simulation using ProcessPoolExecutor."""
        from mcprojsim.simulation.parallel import (
            _run_chunk,  # pyright: ignore[reportPrivateUsage]
            merge_chunk_results,
            partition_chunks,
            partition_seeds,
        )

        effective_workers = min(self.workers, self.iterations)
        chunks = partition_chunks(self.iterations, effective_workers)

        assert (
            sum(size for _, size in chunks) == self.iterations
        ), "Partition sizes do not sum to total iterations"

        child_seeds = partition_seeds(self.random_seed, len(chunks))
        project_dict = project.model_dump(mode="python", exclude_none=True)
        config_dict = self.config.model_dump(mode="python", exclude_none=True)

        completed_iterations = 0
        chunk_results = []

        ctx = multiprocessing.get_context("spawn")
        manager = ctx.Manager()
        cancel_event = manager.Event()
        self._active_cancel_event = cancel_event

        try:
            with ProcessPoolExecutor(
                max_workers=effective_workers, mp_context=ctx
            ) as executor:
                future_to_chunk = {
                    executor.submit(
                        _run_chunk,
                        project_dict,
                        config_dict,
                        start,
                        size,
                        child_seeds[i],
                        None,  # task_priority
                        None,  # cached_durations_slice
                        None,  # cached_cost_impacts_slice
                        cancel_event,
                        False,  # store_duration_cache
                    ): (start, size)
                    for i, (start, size) in enumerate(chunks)
                }

                try:
                    for future in as_completed(future_to_chunk):
                        if self._cancelled:
                            raise SimulationCancelled()
                        result = future.result()
                        chunk_results.append(result)
                        completed_iterations += result.chunk_size
                        if self.show_progress or self._progress_callback is not None:
                            progress = (completed_iterations * 100) // self.iterations
                            self._report_progress(
                                progress,
                                completed_iterations,
                                total_iterations=self.iterations,
                            )
                except SimulationCancelled:
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise
        finally:
            self._active_cancel_event = None
            manager.shutdown()

        merged = merge_chunk_results(chunk_results, self.iterations)
        return self._build_results(
            project,
            merged.project_durations,
            merged.task_durations_all,
            merged.task_risk_impacts_all,
            list(merged.project_risk_impacts_all),
            merged.task_slack_accum,
            merged.critical_path_frequency,
            merged.critical_path_sequences,
            merged.max_parallel_overall,
            list(merged.resource_wait_time_all),
            list(merged.resource_utilization_all),
            list(merged.calendar_delay_time_all),
            project_costs_all=(
                list(merged.project_costs_all)
                if merged.project_costs_all is not None
                else None
            ),
            task_costs_all=(
                {tid: list(v) for tid, v in merged.task_costs_all.items()}
                if merged.task_costs_all is not None
                else None
            ),
        )

    def _run_two_pass(
        self,
        project: Project,
        static_data: ProjectRunStaticData,
    ) -> SimulationResults:
        """Run two-pass criticality-aware constrained simulation."""
        hours_per_day = project.project.hours_per_day
        effective_p1_iters = min(
            self.config.constrained_scheduling.pass1_iterations,
            self.iterations,
        )

        if self._parallel_expected_payoff_positive(project, two_pass=True):
            return self._run_two_pass_parallel(project, static_data, effective_p1_iters)

        total_progress_iterations = effective_p1_iters + self.iterations

        if effective_p1_iters < 100 and self.iterations >= 100:
            logger.warning(
                "two-pass: pass1_iterations=%d is less than 100; "
                "criticality ranking may be noisy.",
                effective_p1_iters,
            )

        # ------- Pass 1: greedy baseline --------------------------------
        # Use a *copy* of the random state so pass-1 sampling is isolated.
        pass1_rs = np.random.RandomState(self.random_seed)
        pass1_sampler = DistributionSampler(
            pass1_rs, self.config.get_lognormal_high_z_value()
        )
        pass1_risk_eval = RiskEvaluator(pass1_rs)
        pass1_scheduler = TaskScheduler(project, pass1_rs, self.config)

        p1_durations_arr = np.zeros(effective_p1_iters)
        p1_critical_path_freq: Dict[str, int] = {task.id: 0 for task in project.tasks}
        p1_resource_wait: list[float] = []
        p1_resource_util: list[float] = []
        p1_calendar_delay: list[float] = []
        duration_cache = DurationCache()
        cost_impact_cache = CostImpactCache()

        if self.show_progress and self._progress_callback is None:
            self.progress_stream.write("Pass 1: computing criticality indices\n")
            self.progress_stream.flush()

        last_reported_p1 = -1
        for iteration in range(effective_p1_iters):
            if self._cancelled:
                raise SimulationCancelled()

            (
                duration,
                task_durations,
                critical_path,
                _critical_paths,
                _task_risk_impacts,
                _proj_risk_impact,
                task_risk_cost_impacts_p1,
                _proj_risk_cost_impact,
                _schedule,
                _slack,
                _max_parallel,
                constrained_diagnostics,
            ) = self._run_iteration_with_sampler(
                project,
                pass1_scheduler,
                hours_per_day,
                static_data,
                pass1_sampler,
                pass1_risk_eval,
                task_priority=None,
            )

            p1_durations_arr[iteration] = duration
            for task_id in critical_path:
                p1_critical_path_freq[task_id] += 1
            p1_resource_wait.append(constrained_diagnostics["resource_wait_time_hours"])
            p1_resource_util.append(constrained_diagnostics["resource_utilization"])
            p1_calendar_delay.append(
                constrained_diagnostics["calendar_delay_time_hours"]
            )

            # Cache sampled durations and cost risk impacts for paired replay in
            # pass-2. Cost impacts must be replayed alongside their corresponding
            # durations so that cost overruns stay correlated with schedule
            # overruns from the same iteration.
            for task_id, dur in task_durations.items():
                duration_cache.store(iteration, task_id, dur)
            cost_impact_cache.store(iteration, task_risk_cost_impacts_p1)

            if self.show_progress or self._progress_callback is not None:
                completed = iteration + 1
                current_progress = (completed * 100) // effective_p1_iters
                bucket = (current_progress // 10) * 10
                if (bucket > last_reported_p1 and bucket > 0) or (
                    completed == effective_p1_iters and last_reported_p1 < 100
                ):
                    rep = 100 if completed == effective_p1_iters else bucket
                    self._report_progress(
                        rep,
                        completed,
                        total_iterations=effective_p1_iters,
                        callback_completed=completed,
                        callback_total=total_progress_iterations,
                    )
                    last_reported_p1 = rep

        if (
            self.show_progress
            and self._progress_callback is None
            and self._progress_is_tty
        ):
            self.progress_stream.write("\n")
            self.progress_stream.flush()

        # Compute criticality indices from pass-1
        task_ci: Dict[str, float] = {}
        for task_id, count in p1_critical_path_freq.items():
            ci = count / effective_p1_iters
            assert 0.0 <= ci <= 1.0, f"CI out of range for {task_id}: {ci}"
            task_ci[task_id] = ci

        # ------- Pass 2: priority-ordered scheduling --------------------
        # Use the main random_state (same seed path) for pass-2.
        pass2_scheduler = TaskScheduler(project, self.random_state, self.config)

        project_durations = np.zeros(self.iterations)
        task_durations_all: Dict[str, list[float]] = {
            task.id: [] for task in project.tasks
        }
        task_risk_impacts_all: Dict[str, list[float]] = {
            task.id: [] for task in project.tasks
        }
        project_risk_impacts_all: list[float] = []
        task_slack_accum: Dict[str, list[float]] = {
            task.id: [] for task in project.tasks
        }
        critical_path_frequency: Dict[str, int] = {task.id: 0 for task in project.tasks}
        critical_path_sequences: Counter[tuple[str, ...]] = Counter()
        max_parallel_overall = 0
        resource_wait_time_all: list[float] = []
        resource_utilization_all: list[float] = []
        calendar_delay_time_all: list[float] = []

        cost_active = self._cost_estimation_active(project)
        project_costs_all: list[float] = []
        task_costs_all: Dict[str, list[float]] = {task.id: [] for task in project.tasks}

        if self.show_progress and self._progress_callback is None:
            self.progress_stream.write("Pass 2: priority-ordered scheduling\n")
            self.progress_stream.flush()

        last_reported_p2 = -1
        for iteration in range(self.iterations):
            if self._cancelled:
                raise SimulationCancelled()

            # For pass-1 iterations, replay cached durations (paired replay).
            # For remaining iterations, sample fresh.
            if iteration < effective_p1_iters:
                cached_durations = {
                    task_id: duration_cache.retrieve(iteration, task_id)
                    for task_id in static_data.task_ids
                }
                cached_cost_impacts: Dict[str, float] | None = (
                    cost_impact_cache.retrieve(iteration)
                    if iteration in cost_impact_cache
                    else None
                )
            else:
                cached_durations = None
                cached_cost_impacts = None

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
                max_parallel,
                constrained_diagnostics,
            ) = self._run_iteration_with_sampler(
                project,
                pass2_scheduler,
                hours_per_day,
                static_data,
                self.sampler,
                self.risk_evaluator,
                task_priority=task_ci,
                cached_task_durations=cached_durations,
                cached_task_risk_cost_impacts=cached_cost_impacts,
            )

            project_durations[iteration] = duration
            max_parallel_overall = max(max_parallel_overall, max_parallel)

            for task_id, task_duration in task_durations.items():
                task_durations_all[task_id].append(task_duration)
            for task_id, impact in task_risk_impacts.items():
                task_risk_impacts_all[task_id].append(impact)
            project_risk_impacts_all.append(project_risk_impact)
            resource_wait_time_all.append(
                constrained_diagnostics["resource_wait_time_hours"]
            )
            resource_utilization_all.append(
                constrained_diagnostics["resource_utilization"]
            )
            calendar_delay_time_all.append(
                constrained_diagnostics["calendar_delay_time_hours"]
            )

            if cost_active:
                total_cost, per_task_cost = self._compute_iteration_costs(
                    project,
                    task_durations,
                    task_risk_cost_impacts,
                    project_risk_cost_impact,
                    schedule,
                )
                project_costs_all.append(total_cost)
                for task_id, tc in per_task_cost.items():
                    task_costs_all[task_id].append(tc)

            for task_id, slack_val in slack.items():
                task_slack_accum[task_id].append(slack_val)
            for task_id in critical_path:
                critical_path_frequency[task_id] += 1
            critical_path_sequences.update(critical_paths)

            if self.show_progress or self._progress_callback is not None:
                completed = iteration + 1
                current_progress = (completed * 100) // self.iterations
                bucket = (current_progress // 10) * 10
                if (bucket > last_reported_p2 and bucket > 0) or (
                    completed == self.iterations and last_reported_p2 < 100
                ):
                    rep = 100 if completed == self.iterations else bucket
                    self._report_progress(
                        rep,
                        completed,
                        total_iterations=self.iterations,
                        callback_completed=effective_p1_iters + completed,
                        callback_total=total_progress_iterations,
                    )
                    last_reported_p2 = rep

        if (
            self.show_progress
            and self._progress_callback is None
            and self._progress_is_tty
        ):
            self.progress_stream.write("\n")
            self.progress_stream.flush()

        # Build main results from pass-2
        results = self._build_results(
            project,
            project_durations,
            task_durations_all,
            task_risk_impacts_all,
            project_risk_impacts_all,
            task_slack_accum,
            critical_path_frequency,
            critical_path_sequences,
            max_parallel_overall,
            resource_wait_time_all,
            resource_utilization_all,
            calendar_delay_time_all,
            project_costs_all=project_costs_all if cost_active else None,
            task_costs_all=task_costs_all if cost_active else None,
        )

        # Compute pass-delta traceability
        p1_mean = float(np.mean(p1_durations_arr))
        p1_p50 = float(np.percentile(p1_durations_arr, 50))
        p1_p80 = float(np.percentile(p1_durations_arr, 80))
        p1_p90 = float(np.percentile(p1_durations_arr, 90))
        p1_p95 = float(np.percentile(p1_durations_arr, 95))
        p1_rw = float(np.mean(p1_resource_wait))
        p1_ru = float(np.mean(p1_resource_util))
        p1_cd = float(np.mean(p1_calendar_delay))

        p2_mean = results.mean
        p2_p50 = results.percentile(50)
        p2_p80 = results.percentile(80)
        p2_p90 = results.percentile(90)
        p2_p95 = results.percentile(95)
        p2_rw = results.resource_wait_time_hours
        p2_ru = results.resource_utilization
        p2_cd = results.calendar_delay_time_hours

        results.two_pass_trace = TwoPassDelta(
            enabled=True,
            pass1_iterations=effective_p1_iters,
            pass2_iterations=self.iterations,
            ranking_method="criticality_index",
            pass1_mean_hours=p1_mean,
            pass1_p50_hours=p1_p50,
            pass1_p80_hours=p1_p80,
            pass1_p90_hours=p1_p90,
            pass1_p95_hours=p1_p95,
            pass1_resource_wait_hours=p1_rw,
            pass1_resource_utilization=p1_ru,
            pass1_calendar_delay_hours=p1_cd,
            pass2_mean_hours=p2_mean,
            pass2_p50_hours=p2_p50,
            pass2_p80_hours=p2_p80,
            pass2_p90_hours=p2_p90,
            pass2_p95_hours=p2_p95,
            pass2_resource_wait_hours=p2_rw,
            pass2_resource_utilization=p2_ru,
            pass2_calendar_delay_hours=p2_cd,
            delta_mean_hours=p2_mean - p1_mean,
            delta_p50_hours=p2_p50 - p1_p50,
            delta_p80_hours=p2_p80 - p1_p80,
            delta_p90_hours=p2_p90 - p1_p90,
            delta_p95_hours=p2_p95 - p1_p95,
            delta_resource_wait_hours=p2_rw - p1_rw,
            delta_resource_utilization=p2_ru - p1_ru,
            delta_calendar_delay_hours=p2_cd - p1_cd,
            task_criticality_index=task_ci,
        )

        return results

    def _run_two_pass_parallel(
        self,
        project: Project,
        static_data: ProjectRunStaticData,
        effective_p1_iters: int,
    ) -> SimulationResults:
        """Parallel two-pass execution with pass-1 replay into pass-2."""
        from numpy.random import SeedSequence

        from mcprojsim.simulation.parallel import (
            _run_chunk,  # pyright: ignore[reportPrivateUsage]
            merge_chunk_results,
            partition_chunks,
            partition_seeds,
        )

        if self._cancelled:
            raise SimulationCancelled()

        project_dict = project.model_dump(mode="python", exclude_none=True)
        config_dict = self.config.model_dump(mode="python", exclude_none=True)
        root_seq = SeedSequence(self.random_seed)
        pass1_seq, pass2_seq = root_seq.spawn(2)
        total_progress_iterations = effective_p1_iters + self.iterations

        ctx = multiprocessing.get_context("spawn")
        manager = ctx.Manager()
        cancel_event = manager.Event()
        self._active_cancel_event = cancel_event

        try:
            # -------------------------------
            # Pass 1: parallel greedy baseline
            # -------------------------------
            p1_workers = min(self.workers, effective_p1_iters)
            p1_chunks = partition_chunks(effective_p1_iters, p1_workers)
            assert (
                sum(size for _, size in p1_chunks) == effective_p1_iters
            ), "Pass-1 chunk sizes do not sum to pass1_iterations"
            p1_child_seeds = partition_seeds(
                random_seed=None,
                n_chunks=len(p1_chunks),
                parent_seq=pass1_seq,
            )

            if self.show_progress and self._progress_callback is None:
                self.progress_stream.write("Pass 1: computing criticality indices\n")
                self.progress_stream.flush()

            p1_results = []
            p1_completed = 0
            with ProcessPoolExecutor(
                max_workers=p1_workers, mp_context=ctx
            ) as executor:
                futures = [
                    executor.submit(
                        _run_chunk,
                        project_dict,
                        config_dict,
                        start,
                        size,
                        p1_child_seeds[i],
                        None,
                        None,
                        None,
                        cancel_event,
                        True,
                    )
                    for i, (start, size) in enumerate(p1_chunks)
                ]

                try:
                    for future in as_completed(futures):
                        if self._cancelled:
                            raise SimulationCancelled()
                        result = future.result()
                        p1_results.append(result)
                        p1_completed += result.chunk_size
                        if self.show_progress or self._progress_callback is not None:
                            progress = (p1_completed * 100) // effective_p1_iters
                            self._report_progress(
                                progress,
                                p1_completed,
                                total_iterations=effective_p1_iters,
                                callback_completed=p1_completed,
                                callback_total=total_progress_iterations,
                            )
                except SimulationCancelled:
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise

            if (
                self.show_progress
                and self._progress_callback is None
                and self._progress_is_tty
            ):
                self.progress_stream.write("\n")
                self.progress_stream.flush()

            merged_p1 = merge_chunk_results(p1_results, effective_p1_iters)
            p1_critical_path_freq = merged_p1.critical_path_frequency
            p1_durations_arr = merged_p1.project_durations
            p1_resource_wait = merged_p1.resource_wait_time_all
            p1_resource_util = merged_p1.resource_utilization_all
            p1_calendar_delay = merged_p1.calendar_delay_time_all

            global_duration_cache = merged_p1.global_duration_cache or {}
            global_cost_impact_cache = merged_p1.global_cost_impact_cache or {}
            assert (
                len(global_duration_cache) == effective_p1_iters
            ), "Pass-1 duration cache size mismatch; global remap is broken"
            assert (
                len(global_cost_impact_cache) == effective_p1_iters
            ), "Pass-1 cost impact cache size mismatch; global remap is broken"

            task_ci: Dict[str, float] = {}
            for task_id, count in p1_critical_path_freq.items():
                ci = count / effective_p1_iters
                assert 0.0 <= ci <= 1.0, f"CI out of range for {task_id}: {ci}"
                task_ci[task_id] = ci

            # -------------------------------
            # Pass 2: parallel prioritised run
            # -------------------------------
            p2_workers = min(self.workers, self.iterations)
            p2_chunks = partition_chunks(self.iterations, p2_workers)
            assert (
                sum(size for _, size in p2_chunks) == self.iterations
            ), "Pass-2 chunk sizes do not sum to total iterations"
            p2_child_seeds = partition_seeds(
                random_seed=None,
                n_chunks=len(p2_chunks),
                parent_seq=pass2_seq,
            )

            if self.show_progress and self._progress_callback is None:
                self.progress_stream.write("Pass 2: priority-ordered scheduling\n")
                self.progress_stream.flush()

            p2_results = []
            p2_completed = 0
            with ProcessPoolExecutor(
                max_workers=p2_workers, mp_context=ctx
            ) as executor:
                futures = []
                for i, (start, size) in enumerate(p2_chunks):
                    replay_end = min(start + size, effective_p1_iters)
                    if start < replay_end:
                        cached_durations_slice = {
                            gidx: global_duration_cache[gidx]
                            for gidx in range(start, replay_end)
                        }
                        cached_cost_impacts_slice = {
                            gidx: global_cost_impact_cache[gidx]
                            for gidx in range(start, replay_end)
                        }
                    else:
                        cached_durations_slice = None
                        cached_cost_impacts_slice = None

                    futures.append(
                        executor.submit(
                            _run_chunk,
                            project_dict,
                            config_dict,
                            start,
                            size,
                            p2_child_seeds[i],
                            task_ci,
                            cached_durations_slice,
                            cached_cost_impacts_slice,
                            cancel_event,
                            False,
                        )
                    )

                try:
                    for future in as_completed(futures):
                        if self._cancelled:
                            raise SimulationCancelled()
                        result = future.result()
                        p2_results.append(result)
                        p2_completed += result.chunk_size
                        if self.show_progress or self._progress_callback is not None:
                            progress = (p2_completed * 100) // self.iterations
                            self._report_progress(
                                progress,
                                p2_completed,
                                total_iterations=self.iterations,
                                callback_completed=effective_p1_iters + p2_completed,
                                callback_total=total_progress_iterations,
                            )
                except SimulationCancelled:
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise

            if (
                self.show_progress
                and self._progress_callback is None
                and self._progress_is_tty
            ):
                self.progress_stream.write("\n")
                self.progress_stream.flush()

            merged_p2 = merge_chunk_results(p2_results, self.iterations)
            results = self._build_results(
                project,
                merged_p2.project_durations,
                merged_p2.task_durations_all,
                merged_p2.task_risk_impacts_all,
                merged_p2.project_risk_impacts_all,
                merged_p2.task_slack_accum,
                merged_p2.critical_path_frequency,
                merged_p2.critical_path_sequences,
                merged_p2.max_parallel_overall,
                merged_p2.resource_wait_time_all,
                merged_p2.resource_utilization_all,
                merged_p2.calendar_delay_time_all,
                project_costs_all=merged_p2.project_costs_all,
                task_costs_all=merged_p2.task_costs_all,
            )

            p1_mean = float(np.mean(p1_durations_arr))
            p1_p50 = float(np.percentile(p1_durations_arr, 50))
            p1_p80 = float(np.percentile(p1_durations_arr, 80))
            p1_p90 = float(np.percentile(p1_durations_arr, 90))
            p1_p95 = float(np.percentile(p1_durations_arr, 95))
            p1_rw = float(np.mean(p1_resource_wait))
            p1_ru = float(np.mean(p1_resource_util))
            p1_cd = float(np.mean(p1_calendar_delay))

            p2_mean = results.mean
            p2_p50 = results.percentile(50)
            p2_p80 = results.percentile(80)
            p2_p90 = results.percentile(90)
            p2_p95 = results.percentile(95)
            p2_rw = results.resource_wait_time_hours
            p2_ru = results.resource_utilization
            p2_cd = results.calendar_delay_time_hours

            results.two_pass_trace = TwoPassDelta(
                enabled=True,
                pass1_iterations=effective_p1_iters,
                pass2_iterations=self.iterations,
                ranking_method="criticality_index",
                pass1_mean_hours=p1_mean,
                pass1_p50_hours=p1_p50,
                pass1_p80_hours=p1_p80,
                pass1_p90_hours=p1_p90,
                pass1_p95_hours=p1_p95,
                pass1_resource_wait_hours=p1_rw,
                pass1_resource_utilization=p1_ru,
                pass1_calendar_delay_hours=p1_cd,
                pass2_mean_hours=p2_mean,
                pass2_p50_hours=p2_p50,
                pass2_p80_hours=p2_p80,
                pass2_p90_hours=p2_p90,
                pass2_p95_hours=p2_p95,
                pass2_resource_wait_hours=p2_rw,
                pass2_resource_utilization=p2_ru,
                pass2_calendar_delay_hours=p2_cd,
                delta_mean_hours=p2_mean - p1_mean,
                delta_p50_hours=p2_p50 - p1_p50,
                delta_p80_hours=p2_p80 - p1_p80,
                delta_p90_hours=p2_p90 - p1_p90,
                delta_p95_hours=p2_p95 - p1_p95,
                delta_resource_wait_hours=p2_rw - p1_rw,
                delta_resource_utilization=p2_ru - p1_ru,
                delta_calendar_delay_hours=p2_cd - p1_cd,
                task_criticality_index=task_ci,
            )

            return results
        finally:
            self._active_cancel_event = None
            manager.shutdown()

    def _build_results(
        self,
        project: Project,
        project_durations: np.ndarray,
        task_durations_all: Union[Dict[str, list[float]], Dict[str, np.ndarray]],
        task_risk_impacts_all: Union[Dict[str, list[float]], Dict[str, np.ndarray]],
        project_risk_impacts_all: Union[list[float], np.ndarray],
        task_slack_accum: Union[Dict[str, list[float]], Dict[str, np.ndarray]],
        critical_path_frequency: Dict[str, int],
        critical_path_sequences: "Counter[tuple[str, ...]]",
        max_parallel_overall: int,
        resource_wait_time_all: Union[list[float], np.ndarray],
        resource_utilization_all: Union[list[float], np.ndarray],
        calendar_delay_time_all: Union[list[float], np.ndarray],
        project_costs_all: Optional[Union[list[float], np.ndarray]] = None,
        task_costs_all: Optional[
            Union[Dict[str, list[float]], Dict[str, np.ndarray]]
        ] = None,
    ) -> SimulationResults:
        """Assemble a :class:`SimulationResults` from accumulated per-iteration data."""
        n_iterations = len(project_durations)

        stored_critical_paths = [
            CriticalPathRecord(
                path=path,
                count=count,
                frequency=count / n_iterations,
            )
            for path, count in sorted(
                critical_path_sequences.items(),
                key=lambda item: (-item[1], item[0]),
            )[: self.config.simulation.max_stored_critical_paths]
        ]

        mean_slack = {
            task_id: float(np.mean(values))
            for task_id, values in task_slack_accum.items()
        }

        task_durations_arrays = {
            task_id: np.array(durations)
            for task_id, durations in task_durations_all.items()
        }

        if task_durations_arrays:
            effort_durations = np.sum(
                np.stack(list(task_durations_arrays.values())), axis=0
            )
        else:
            effort_durations = project_durations.copy()

        # Resolve cost arrays
        costs_arr: Optional[np.ndarray] = None
        task_costs_arrays: Optional[Dict[str, np.ndarray]] = None
        resolved_currency: Optional[str] = None
        if project_costs_all is not None:
            costs_arr = np.array(project_costs_all)
            task_costs_arrays = (
                {tid: np.array(v) for tid, v in task_costs_all.items()}
                if task_costs_all is not None
                else None
            )
            resolved_currency = project.project.currency or self.config.cost.currency

        results = SimulationResults(
            iterations=n_iterations,
            project_name=project.project.name,
            durations=project_durations,
            task_durations=task_durations_arrays,
            critical_path_frequency=critical_path_frequency,
            critical_path_sequences=stored_critical_paths,
            random_seed=self.random_seed,
            probability_red_threshold=project.project.probability_red_threshold,
            probability_green_threshold=project.project.probability_green_threshold,
            hours_per_day=project.project.hours_per_day,
            start_date=project.project.start_date,
            task_slack=mean_slack,
            risk_impacts={
                task_id: np.array(impacts)
                for task_id, impacts in task_risk_impacts_all.items()
            },
            project_risk_impacts=np.array(project_risk_impacts_all),
            max_parallel_tasks=max_parallel_overall,
            effort_durations=effort_durations,
            schedule_mode=(
                "resource_constrained"
                if len(project.resources) > 0
                else "dependency_only"
            ),
            resource_constraints_active=len(project.resources) > 0,
            resource_wait_time_hours=float(np.mean(resource_wait_time_all)),
            resource_utilization=float(np.mean(resource_utilization_all)),
            calendar_delay_time_hours=float(np.mean(calendar_delay_time_all)),
            costs=costs_arr,
            task_costs=task_costs_arrays,
            currency=resolved_currency,
        )

        results.calculate_statistics()
        results.calculate_cost_statistics()

        for p in project.project.confidence_levels:
            results.percentile(p)
            results.effort_percentile(p)
            if results.costs is not None:
                results.cost_percentile(p)

        from mcprojsim.analysis.sensitivity import SensitivityAnalyzer

        results.sensitivity = SensitivityAnalyzer.calculate_correlations(results)

        if results.costs is not None:
            from mcprojsim.analysis.cost import CostAnalyzer

            results.cost_analysis = CostAnalyzer().analyze(results)

        return results

    def _maybe_report_progress(
        self,
        iteration: int,
        total: int,
        last_reported: int,
        callback_completed: Optional[int] = None,
        callback_total: Optional[int] = None,
    ) -> int:
        """Update progress display if a 10% bucket boundary has been crossed."""
        completed = iteration + 1
        current_progress = (completed * 100) // total
        bucket = (current_progress // 10) * 10
        if (bucket > last_reported and bucket > 0) or (
            completed == total and last_reported < 100
        ):
            rep = 100 if completed == total else bucket
            self._report_progress(
                rep,
                completed,
                total_iterations=total,
                callback_completed=callback_completed,
                callback_total=callback_total,
            )
            return rep
        return last_reported

    def _report_progress(
        self,
        progress: int,
        completed_iterations: int,
        total_iterations: Optional[int] = None,
        callback_completed: Optional[int] = None,
        callback_total: Optional[int] = None,
    ) -> None:
        """Report simulation progress.

        When a *progress_callback* was supplied at construction time, it is
        invoked with ``(completed_iterations, total_iterations)`` and stdout
        output is skipped.  Otherwise the original stdout behaviour is used:
        when writing to a terminal, update a single line in place; when output
        is redirected, emit one line per progress update.

        Args:
            progress: Progress percentage to report
            completed_iterations: Number of completed iterations
        """
        resolved_total = (
            total_iterations if total_iterations is not None else self.iterations
        )

        if self._progress_callback is not None:
            self._progress_callback(
                (
                    callback_completed
                    if callback_completed is not None
                    else completed_iterations
                ),
                callback_total if callback_total is not None else resolved_total,
            )
            return

        message = (
            f"Progress: {progress:.1f}% " f"({completed_iterations}/{resolved_total})"
        )

        if self._progress_is_tty:
            self.progress_stream.write(f"\r\033[K{message}")
        else:
            self.progress_stream.write(f"{message}\n")
        self.progress_stream.flush()

    def _cost_estimation_active(self, project: Project) -> bool:
        """Return True if any cost input is present in the project."""
        meta = project.project
        if meta.default_hourly_rate is not None and meta.default_hourly_rate > 0:
            return True
        if any(r.hourly_rate is not None for r in project.resources):
            return True
        if any(t.fixed_cost is not None for t in project.tasks):
            return True
        if any(
            risk.cost_impact is not None
            for task in project.tasks
            for risk in task.risks
        ):
            return True
        if any(r.cost_impact is not None for r in project.project_risks):
            return True
        return False

    def _resolve_task_rate(
        self,
        task: Task,
        schedule_entry: Dict[str, Any],
        project: Project,
    ) -> float:
        """Return the effective hourly rate for one task.

        In constrained mode, use the assigned resource's hourly_rate if present,
        falling back to project default. For multi-resource tasks, return the
        mean rate across assignees.

        **Phase 1 simplifying assumption — equal-effort split**: each assignee
        is assumed to contribute an equal share of the task's sampled duration.
        The mean rate × total elapsed duration is mathematically equivalent to
        (rate_i × duration/n) summed over n resources. This underestimates cost
        when resources work in parallel (each for the full elapsed duration
        rather than 1/n of it). Full per-resource contributed-hours tracking
        is deferred to a later phase.

        In dependency-only mode, always use project default_hourly_rate.

        Returns 0.0 if no rate is configured anywhere.
        """
        assigned = schedule_entry.get("assigned", [])
        default_rate = project.project.default_hourly_rate or 0.0
        if assigned:
            resource_map = {r.name: r for r in project.resources}
            rates: list[float] = []
            for name in assigned:
                r = resource_map.get(name)
                if r is not None and r.hourly_rate is not None:
                    rates.append(float(r.hourly_rate))
                else:
                    rates.append(default_rate)
            return float(np.mean(rates)) if rates else default_rate
        return default_rate

    def _compute_iteration_costs(
        self,
        project: Project,
        task_durations: Dict[str, float],
        task_risk_cost_impacts: Dict[str, float],
        project_risk_cost_impact: float,
        schedule: Dict[str, Dict[str, Any]],
    ) -> tuple[float, Dict[str, float]]:
        """Compute total project cost and per-task cost for one iteration.

        Args:
            project: Project definition
            task_durations: Sampled task durations in hours
            task_risk_cost_impacts: Per-task cost impacts from triggered risks
            project_risk_cost_impact: Cost impact from project-level risks
            schedule: Schedule dict with "assigned" key per task

        Returns:
            (total_cost, per_task_costs) where total_cost includes overhead.

        Note:
            ``per_task_costs`` contains labor + fixed + risk cost per task but
            does **not** include overhead (overhead is a project-level markup
            applied on top of total labor, not distributed back to individual
            tasks). As a result, ``sum(per_task_costs.values()) < total_cost``
            whenever ``overhead_rate > 0``.
        """
        meta = project.project
        overhead_rate = meta.overhead_rate

        total_labor = 0.0
        total_fixed = 0.0
        total_risk_cost = 0.0
        per_task: Dict[str, float] = {}

        for task in project.tasks:
            rate = self._resolve_task_rate(task, schedule.get(task.id, {}), project)
            labor = task_durations.get(task.id, 0.0) * rate
            fixed = task.fixed_cost or 0.0
            risk_c = task_risk_cost_impacts.get(task.id, 0.0)
            per_task[task.id] = labor + fixed + risk_c
            total_labor += labor
            total_fixed += fixed
            total_risk_cost += risk_c

        total_risk_cost += project_risk_cost_impact

        overhead = total_labor * overhead_rate
        total_cost = total_labor + total_fixed + total_risk_cost + overhead
        return total_cost, per_task

    def _run_iteration(
        self,
        project: Project,
        scheduler: TaskScheduler,
        hours_per_day: float,
        static_data: ProjectRunStaticData,
    ) -> tuple[
        float,
        Dict[str, float],
        set[str],
        list[tuple[str, ...]],
        Dict[str, float],
        float,
        Dict[str, float],
        float,
        Dict[str, Dict[str, Any]],
        Dict[str, float],
        int,
        Dict[str, float],
    ]:
        """Run a single simulation iteration using the engine's own sampler."""
        return self._run_iteration_with_sampler(
            project,
            scheduler,
            hours_per_day,
            static_data,
            self.sampler,
            self.risk_evaluator,
        )

    def _run_iteration_with_sampler(
        self,
        project: Project,
        scheduler: TaskScheduler,
        hours_per_day: float,
        static_data: ProjectRunStaticData,
        sampler: DistributionSampler,
        risk_evaluator: RiskEvaluator,
        task_priority: Dict[str, float] | None = None,
        cached_task_durations: Dict[str, float] | None = None,
        cached_task_risk_cost_impacts: Dict[str, float] | None = None,
    ) -> tuple[
        float,
        Dict[str, float],
        set[str],
        list[tuple[str, ...]],
        Dict[str, float],
        float,
        Dict[str, float],
        float,
        Dict[str, Dict[str, Any]],
        Dict[str, float],
        int,
        Dict[str, float],
    ]:
        """Run a single simulation iteration.

        All durations are computed in hours (the canonical internal unit).

        Args:
            project: Project to simulate
            scheduler: Task scheduler
            hours_per_day: Working hours per day
            sampler: Distribution sampler to use for this iteration
            risk_evaluator: Risk evaluator to use for this iteration
            task_priority: Optional criticality-index map for priority ordering.
            cached_task_durations: When provided, use these task durations instead
                of sampling (paired-replay for pass-2). The cached durations
                already include the task-level time risk impacts from pass-1.
            cached_task_risk_cost_impacts: When provided alongside
                cached_task_durations, restore the pass-1 task-level cost risk
                impacts rather than zeroing them. This preserves the correlation
                between schedule overruns and cost overruns in pass-2 replay.

        Returns:
            Tuple of (project_duration, task_durations, critical_path_tasks,
            critical_paths, task_risk_impacts, project_risk_impact, slack,
            max_parallel_tasks, constrained_diagnostics)
        """
        task_durations: Dict[str, float] = {}
        task_risk_impacts: Dict[str, float] = {}
        task_risk_cost_impacts: Dict[str, float] = {}

        if cached_task_durations is not None:
            # Paired replay: reuse pass-1 sampled durations exactly.
            # Time risk impacts are zeroed because they are already baked into
            # the cached duration values. Cost risk impacts are restored from
            # the pass-1 cache when available so that cost overruns stay
            # correlated with the schedule overruns from the same iteration.
            for task in project.tasks:
                task_durations[task.id] = cached_task_durations[task.id]
                task_risk_impacts[task.id] = 0.0
                task_risk_cost_impacts[task.id] = (
                    cached_task_risk_cost_impacts.get(task.id, 0.0)
                    if cached_task_risk_cost_impacts is not None
                    else 0.0
                )
        else:
            # Sample and adjust task durations
            for task_static_data in static_data.task_data:
                task = task_static_data.task
                base_duration = sampler.sample(task_static_data.resolved_estimate)
                base_duration_hours = base_duration * task_static_data.hours_multiplier
                adjusted_duration = (
                    base_duration_hours * task_static_data.uncertainty_multiplier
                )
                risk_impact, risk_cost_impact = risk_evaluator.evaluate_risks_with_cost(
                    task.risks, adjusted_duration, STANDARD_HOURS_PER_DAY
                )
                final_duration = adjusted_duration + risk_impact
                task_durations[task.id] = final_duration
                task_risk_impacts[task.id] = risk_impact
                task_risk_cost_impacts[task.id] = risk_cost_impact

        # Schedule tasks (all durations in hours)
        use_resource_constraints = len(project.resources) > 0
        schedule_with_diagnostics = scheduler.schedule_tasks(
            task_durations,
            use_resource_constraints=use_resource_constraints,
            return_diagnostics=True,
            start_date=project.project.start_date,
            hours_per_day=hours_per_day,
            task_priority=task_priority,
        )
        schedule, constrained_diagnostics = schedule_with_diagnostics

        # Compute peak parallelism for this iteration
        max_parallel = scheduler.max_parallel_tasks(schedule)

        # Calculate schedule slack
        slack = scheduler.calculate_slack(schedule)

        # Calculate project duration (max end time)
        project_duration = max(info["end"] for info in schedule.values())

        # Apply project-level risks (impacts converted to hours)
        project_risk_impact, project_risk_cost_impact = (
            risk_evaluator.evaluate_risks_with_cost(
                project.project_risks, project_duration, STANDARD_HOURS_PER_DAY
            )
        )
        project_duration += project_risk_impact

        # Identify critical path
        critical_paths = scheduler.get_critical_paths(schedule)
        critical_path = {task_id for path in critical_paths for task_id in path}

        return (
            project_duration,
            task_durations,
            critical_path,
            critical_paths,
            task_risk_impacts,
            project_risk_impact,
            task_risk_cost_impacts,
            project_risk_cost_impact,
            schedule,
            slack,
            max_parallel,
            constrained_diagnostics,
        )

    def _apply_uncertainty_factors(self, task: Task, base_duration: float) -> float:
        """Apply uncertainty factors to base duration.

        Args:
            task: Task with uncertainty factors
            base_duration: Base sampled duration

        Returns:
            Adjusted duration
        """
        return base_duration * self._resolve_uncertainty_multiplier(task)

    def _resolve_uncertainty_multiplier(self, task: Task) -> float:
        """Resolve the combined uncertainty multiplier for one task."""
        if not task.uncertainty_factors:
            return 1.0

        multiplier = 1.0
        factors = task.uncertainty_factors

        if factors.team_experience:
            multiplier *= self.config.get_uncertainty_multiplier(
                "team_experience", factors.team_experience
            )

        if factors.requirements_maturity:
            multiplier *= self.config.get_uncertainty_multiplier(
                "requirements_maturity", factors.requirements_maturity
            )

        if factors.technical_complexity:
            multiplier *= self.config.get_uncertainty_multiplier(
                "technical_complexity", factors.technical_complexity
            )

        if factors.team_distribution:
            multiplier *= self.config.get_uncertainty_multiplier(
                "team_distribution", factors.team_distribution
            )

        if factors.integration_complexity:
            multiplier *= self.config.get_uncertainty_multiplier(
                "integration_complexity", factors.integration_complexity
            )

        return multiplier

    def _build_project_run_static_data(
        self,
        project: Project,
    ) -> ProjectRunStaticData:
        """Precompute project-static task inputs for one simulation run."""
        task_data: list[TaskRunStaticData] = []
        task_ids: list[str] = []
        # hours_per_day = project.project.hours_per_day

        for task in project.tasks:
            resolved_estimate = self._resolve_estimate(
                task, project.project.distribution
            )
            # Use STANDARD_HOURS_PER_DAY (8h) as the reference for converting
            # days/weeks estimates to effort-hours.  The project hours_per_day
            # controls *scheduling rate* (calendar days = hours / hours_per_day)
            # and must NOT participate in the estimate conversion, otherwise the
            # two uses of hours_per_day cancel and calendar duration becomes
            # independent of hours_per_day.
            hours_multiplier = convert_to_hours(
                1.0,
                resolved_estimate.unit or EffortUnit.HOURS,
                STANDARD_HOURS_PER_DAY,
            )
            task_data.append(
                TaskRunStaticData(
                    task=task,
                    resolved_estimate=resolved_estimate,
                    hours_multiplier=hours_multiplier,
                    uncertainty_multiplier=self._resolve_uncertainty_multiplier(task),
                )
            )
            task_ids.append(task.id)

        return ProjectRunStaticData(
            task_data=tuple(task_data),
            task_ids=tuple(task_ids),
        )

    def _resolve_estimate(
        self, task: Task, project_distribution: DistributionType
    ) -> TaskEstimate:
        """Resolve symbolic estimates to actual estimate values.

        For T-shirt sizes and story points, the numeric ranges and unit
        come from the configuration.

        Args:
            task: Task whose estimate should be resolved
            project_distribution: Project-level default distribution

        Returns:
            TaskEstimate with resolved values
        """
        from mcprojsim.models.project import TaskEstimate

        estimate = task.estimate
        effective_distribution = estimate.distribution or project_distribution
        resolved_config: EstimateRangeConfig | None = None
        resolved_unit: EffortUnit | None = None

        if estimate.t_shirt_size is not None:
            resolved_config = self.config.resolve_t_shirt_size(estimate.t_shirt_size)
            resolved_unit = self.config.t_shirt_size_unit

        elif estimate.story_points is not None:
            resolved_config = self.config.get_story_point(estimate.story_points)
            if resolved_config is None:
                raise ValueError(
                    f"Unknown Story Point value: {estimate.story_points}. "
                    f"Available Story Points: {', '.join(str(value) for value in sorted(self.config.story_points.keys()))}"
                )
            resolved_unit = self.config.story_point_unit

        else:
            return TaskEstimate(
                distribution=effective_distribution,
                low=estimate.low,
                expected=estimate.expected,
                high=estimate.high,
                unit=estimate.unit,
            )

        # Create new estimate with resolved values and config unit
        return TaskEstimate(
            distribution=effective_distribution,
            low=resolved_config.low,
            expected=resolved_config.expected,
            high=resolved_config.high,
            unit=resolved_unit,
        )

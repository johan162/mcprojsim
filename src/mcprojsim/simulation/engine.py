"""Monte Carlo simulation engine."""

from collections import Counter
import sys
from typing import Dict, Optional, TextIO

import numpy as np

from mcprojsim.config import (
    Config,
    DEFAULT_SIMULATION_ITERATIONS,
    EffortUnit,
    EstimateRangeConfig,
)
from mcprojsim.models.project import (
    Project,
    Task,
    TaskEstimate,
    convert_to_hours,
)
from mcprojsim.models.simulation import CriticalPathRecord, SimulationResults
from mcprojsim.simulation.distributions import DistributionSampler
from mcprojsim.simulation.risk_evaluator import RiskEvaluator
from mcprojsim.simulation.scheduler import TaskScheduler


class SimulationEngine:
    """Monte Carlo simulation engine for project estimation."""

    def __init__(
        self,
        iterations: int = DEFAULT_SIMULATION_ITERATIONS,
        random_seed: Optional[int] = None,
        config: Optional[Config] = None,
        show_progress: bool = True,
    ):
        """Initialize simulation engine.

        Args:
            iterations: Number of Monte Carlo iterations
            random_seed: Random seed for reproducibility
            config: Configuration object
            show_progress: Whether to show progress updates
        """
        self.iterations = iterations
        self.random_seed = random_seed
        self.config = config or Config.get_default()
        self.show_progress = show_progress
        self.progress_stream: TextIO = sys.stdout
        self._progress_is_tty = self.progress_stream.isatty()

        # Initialize random state
        self.random_state = np.random.RandomState(random_seed)

        # Initialize components
        self.sampler = DistributionSampler(self.random_state)
        self.risk_evaluator = RiskEvaluator(self.random_state)

    def run(self, project: Project) -> SimulationResults:
        """Run Monte Carlo simulation for project.

        Args:
            project: Project to simulate

        Returns:
            Simulation results
        """
        scheduler = TaskScheduler(project)
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

        # Run iterations
        for iteration in range(self.iterations):
            # Run single iteration
            (
                duration,
                task_durations,
                critical_path,
                critical_paths,
                task_risk_impacts,
                project_risk_impact,
                slack,
                max_parallel,
                constrained_diagnostics,
            ) = self._run_iteration(project, scheduler, hours_per_day)

            project_durations[iteration] = duration
            max_parallel_overall = max(max_parallel_overall, max_parallel)

            # Store task durations and risk impacts
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

            # Store slack
            for task_id, slack_val in slack.items():
                task_slack_accum[task_id].append(slack_val)

            # Update critical path frequency
            for task_id in critical_path:
                critical_path_frequency[task_id] += 1

            # Update full critical path sequence frequency
            critical_path_sequences.update(critical_paths)

            if self.show_progress:
                completed_iterations = iteration + 1
                current_progress = (completed_iterations * 100) // self.iterations
                progress_bucket = (current_progress // 10) * 10
                should_report = (
                    progress_bucket > last_reported_progress and progress_bucket > 0
                ) or (
                    completed_iterations == self.iterations
                    and last_reported_progress < 100
                )
                if should_report:
                    reported_progress = (
                        100
                        if completed_iterations == self.iterations
                        else progress_bucket
                    )
                    self._report_progress(reported_progress, completed_iterations)
                    last_reported_progress = reported_progress

        if self.show_progress and self._progress_is_tty:
            self.progress_stream.write("\n")
            self.progress_stream.flush()

        stored_critical_paths = [
            CriticalPathRecord(
                path=path,
                count=count,
                frequency=count / self.iterations,
            )
            for path, count in sorted(
                critical_path_sequences.items(),
                key=lambda item: (-item[1], item[0]),
            )[: self.config.simulation.max_stored_critical_paths]
        ]

        # Compute mean slack per task
        mean_slack = {
            task_id: float(np.mean(values))
            for task_id, values in task_slack_accum.items()
        }

        # Create results object
        task_durations_arrays = {
            task_id: np.array(durations)
            for task_id, durations in task_durations_all.items()
        }

        # Compute per-iteration total effort (sum of all task durations)
        if task_durations_arrays:
            effort_durations = np.sum(
                np.stack(list(task_durations_arrays.values())), axis=0
            )
        else:
            effort_durations = project_durations.copy()

        results = SimulationResults(
            iterations=self.iterations,
            project_name=project.project.name,
            durations=project_durations,
            task_durations=task_durations_arrays,
            critical_path_frequency=critical_path_frequency,
            critical_path_sequences=stored_critical_paths,
            random_seed=self.random_seed,
            probability_red_threshold=project.project.probability_red_threshold,
            probability_green_threshold=project.project.probability_green_threshold,
            hours_per_day=hours_per_day,
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
        )

        # Calculate statistics
        results.calculate_statistics()

        # Calculate percentiles
        for p in project.project.confidence_levels:
            results.percentile(p)
            results.effort_percentile(p)

        # Calculate sensitivity correlations
        from mcprojsim.analysis.sensitivity import SensitivityAnalyzer

        results.sensitivity = SensitivityAnalyzer.calculate_correlations(results)

        return results

    def _report_progress(self, progress: int, completed_iterations: int) -> None:
        """Report simulation progress.

        When writing to a terminal, update a single line in place.
        When output is redirected, emit one line per progress update.

        Args:
            progress: Progress percentage to report
            completed_iterations: Number of completed iterations
        """
        message = (
            f"Progress: {progress:.1f}% " f"({completed_iterations}/{self.iterations})"
        )

        if self._progress_is_tty:
            self.progress_stream.write(f"\r\033[K{message}")
        else:
            self.progress_stream.write(f"{message}\n")
        self.progress_stream.flush()

    def _run_iteration(
        self, project: Project, scheduler: TaskScheduler, hours_per_day: float
    ) -> tuple[
        float,
        Dict[str, float],
        set[str],
        list[tuple[str, ...]],
        Dict[str, float],
        float,
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

        Returns:
            Tuple of (project_duration, task_durations, critical_path_tasks,
            critical_paths, task_risk_impacts, project_risk_impact, slack,
            max_parallel_tasks, constrained_diagnostics)
        """
        task_durations: Dict[str, float] = {}
        task_risk_impacts: Dict[str, float] = {}

        # Sample and adjust task durations
        for task in project.tasks:
            # Resolve T-shirt size / story points to actual estimate if needed
            estimate = self._resolve_estimate(task.estimate)

            # Sample base duration (in the estimate's native unit)
            base_duration = self.sampler.sample(estimate)

            # Convert to hours (the canonical internal unit)
            unit = estimate.unit or EffortUnit.HOURS
            base_duration_hours = convert_to_hours(base_duration, unit, hours_per_day)

            # Apply uncertainty factors
            adjusted_duration = self._apply_uncertainty_factors(
                task, base_duration_hours
            )

            # Apply task-level risks (impacts converted to hours)
            risk_impact = self.risk_evaluator.evaluate_risks(
                task.risks, adjusted_duration, hours_per_day
            )
            final_duration = adjusted_duration + risk_impact

            task_durations[task.id] = final_duration
            task_risk_impacts[task.id] = risk_impact

        # Schedule tasks (all durations in hours)
        use_resource_constraints = len(project.resources) > 0
        schedule_with_diagnostics = scheduler.schedule_tasks(
            task_durations,
            use_resource_constraints=use_resource_constraints,
            return_diagnostics=True,
            start_date=project.project.start_date,
            hours_per_day=hours_per_day,
        )
        if not isinstance(schedule_with_diagnostics, tuple):
            schedule = schedule_with_diagnostics
            constrained_diagnostics = {
                "resource_wait_time_hours": 0.0,
                "resource_utilization": 0.0,
                "calendar_delay_time_hours": 0.0,
            }
        else:
            schedule, constrained_diagnostics = schedule_with_diagnostics

        # Compute peak parallelism for this iteration
        max_parallel = scheduler.max_parallel_tasks(schedule)

        # Calculate schedule slack
        slack = scheduler.calculate_slack(schedule)

        # Calculate project duration (max end time)
        project_duration = max(info["end"] for info in schedule.values())

        # Apply project-level risks (impacts converted to hours)
        project_risk_impact = self.risk_evaluator.evaluate_risks(
            project.project_risks, project_duration, hours_per_day
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
        if not task.uncertainty_factors:
            return base_duration

        multiplier = 1.0
        factors = task.uncertainty_factors

        # Apply each uncertainty factor
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

        return base_duration * multiplier

    def _resolve_estimate(self, estimate: TaskEstimate) -> TaskEstimate:
        """Resolve symbolic estimates to actual estimate values.

        For T-shirt sizes and story points, the numeric ranges and unit
        come from the configuration.

        Args:
            estimate: TaskEstimate object

        Returns:
            TaskEstimate with resolved values
        """
        from mcprojsim.models.project import TaskEstimate

        resolved_config: EstimateRangeConfig | None = None
        resolved_unit: EffortUnit | None = None

        if estimate.t_shirt_size is not None:
            resolved_config = self.config.get_t_shirt_size(estimate.t_shirt_size)
            if resolved_config is None:
                raise ValueError(
                    f"Unknown T-shirt size: {estimate.t_shirt_size}. "
                    f"Available sizes: {', '.join(self.config.t_shirt_sizes.keys())}"
                )
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
            return estimate

        # Create new estimate with resolved values and config unit
        return TaskEstimate(
            distribution=estimate.distribution,
            min=resolved_config.min,
            most_likely=resolved_config.most_likely,
            max=resolved_config.max,
            unit=resolved_unit,
        )

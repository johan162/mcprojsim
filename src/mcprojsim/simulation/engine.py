"""Monte Carlo simulation engine."""

from collections import Counter
import sys
from typing import Dict, Optional, TextIO

import numpy as np

from mcprojsim.config import (
    Config,
    DEFAULT_SIMULATION_ITERATIONS,
    EstimateRangeConfig,
)
from mcprojsim.models.project import Project, Task, TaskEstimate
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

        # Storage for results
        project_durations = np.zeros(self.iterations)
        task_durations_all: Dict[str, list[float]] = {
            task.id: [] for task in project.tasks
        }
        critical_path_frequency: Dict[str, int] = {task.id: 0 for task in project.tasks}
        critical_path_sequences: Counter[tuple[str, ...]] = Counter()
        last_reported_progress = -1

        # Run iterations
        for iteration in range(self.iterations):
            # Run single iteration
            duration, task_durations, critical_path, critical_paths = (
                self._run_iteration(project, scheduler)
            )

            project_durations[iteration] = duration

            # Store task durations
            for task_id, task_duration in task_durations.items():
                task_durations_all[task_id].append(task_duration)

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

        # Create results object
        results = SimulationResults(
            iterations=self.iterations,
            project_name=project.project.name,
            durations=project_durations,
            task_durations={
                task_id: np.array(durations)
                for task_id, durations in task_durations_all.items()
            },
            critical_path_frequency=critical_path_frequency,
            critical_path_sequences=stored_critical_paths,
            random_seed=self.random_seed,
            probability_red_threshold=project.project.probability_red_threshold,
            probability_green_threshold=project.project.probability_green_threshold,
        )

        # Calculate statistics
        results.calculate_statistics()

        # Calculate percentiles
        for p in project.project.confidence_levels:
            results.percentile(p)

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
        self, project: Project, scheduler: TaskScheduler
    ) -> tuple[float, Dict[str, float], set[str], list[tuple[str, ...]]]:
        """Run a single simulation iteration.

        Args:
            project: Project to simulate
            scheduler: Task scheduler

        Returns:
            Tuple of (project_duration, task_durations, critical_path_tasks, critical_paths)
        """
        task_durations: Dict[str, float] = {}

        # Sample and adjust task durations
        for task in project.tasks:
            # Resolve T-shirt size to actual estimate if needed
            estimate = self._resolve_estimate(task.estimate)

            # Sample base duration
            base_duration = self.sampler.sample(estimate)

            # Apply uncertainty factors
            adjusted_duration = self._apply_uncertainty_factors(task, base_duration)

            # Apply task-level risks
            risk_impact = self.risk_evaluator.evaluate_risks(
                task.risks, adjusted_duration
            )
            final_duration = adjusted_duration + risk_impact

            task_durations[task.id] = final_duration

        # Schedule tasks
        schedule = scheduler.schedule_tasks(task_durations)

        # Calculate project duration (max end time)
        project_duration = max(info["end"] for info in schedule.values())

        # Apply project-level risks
        project_risk_impact = self.risk_evaluator.evaluate_risks(
            project.project_risks, project_duration
        )
        project_duration += project_risk_impact

        # Identify critical path
        critical_paths = scheduler.get_critical_paths(schedule)
        critical_path = {task_id for path in critical_paths for task_id in path}

        return project_duration, task_durations, critical_path, critical_paths

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
        """Resolve symbolic estimates to actual day-based estimate values.

        Args:
            estimate: TaskEstimate object

        Returns:
            TaskEstimate with resolved values
        """
        from mcprojsim.models.project import TaskEstimate

        resolved_config: EstimateRangeConfig | None = None

        if estimate.t_shirt_size is not None:
            resolved_config = self.config.get_t_shirt_size(estimate.t_shirt_size)
            if resolved_config is None:
                raise ValueError(
                    f"Unknown T-shirt size: {estimate.t_shirt_size}. "
                    f"Available sizes: {', '.join(self.config.t_shirt_sizes.keys())}"
                )

        elif estimate.story_points is not None:
            resolved_config = self.config.get_story_point(estimate.story_points)
            if resolved_config is None:
                raise ValueError(
                    f"Unknown Story Point value: {estimate.story_points}. "
                    f"Available Story Points: {', '.join(str(value) for value in sorted(self.config.story_points.keys()))}"
                )

        else:
            return estimate

        # Create new estimate with resolved values
        return TaskEstimate(
            distribution=estimate.distribution,
            min=resolved_config.min,
            most_likely=resolved_config.most_likely,
            max=resolved_config.max,
            unit="days",
        )

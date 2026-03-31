"""Sprint-based Monte Carlo simulation engine."""

from __future__ import annotations

from datetime import timedelta

import numpy as np

from mcprojsim.config import DEFAULT_SIMULATION_ITERATIONS
from mcprojsim.models.project import Project
from mcprojsim.models.sprint_simulation import SprintPlanningResults
from mcprojsim.planning.sprint_capacity import SprintCapacitySampler
from mcprojsim.planning.sprint_planner import SprintPlanner


class SprintSimulationEngine:
    """Run sprint-planning Monte Carlo simulations."""

    def __init__(
        self,
        iterations: int = DEFAULT_SIMULATION_ITERATIONS,
        random_seed: int | None = None,
    ):
        """Initialize the sprint simulation engine."""
        self.iterations = iterations
        self.random_seed = random_seed
        self.random_state = np.random.RandomState(random_seed)

    def run(self, project: Project) -> SprintPlanningResults:
        """Run sprint-planning simulation for the given project."""
        if project.sprint_planning is None or not project.sprint_planning.enabled:
            raise ValueError(
                "Sprint simulation requires enabled project.sprint_planning"
            )

        sprint_planning = project.sprint_planning

        sampler = SprintCapacitySampler(sprint_planning, self.random_state)
        planner = SprintPlanner(project, self.random_state)
        sprint_counts = np.zeros(self.iterations)
        peak_carryover_units = np.zeros(self.iterations)
        spillover_rates = np.zeros(self.iterations)
        disruption_flags = np.zeros(self.iterations)
        burnup_samples: list[list[float]] = []

        for iteration in range(self.iterations):
            (
                sprint_counts[iteration],
                peak_carryover_units[iteration],
                spillover_rates[iteration],
                disruption_flags[iteration],
                burnup_trace,
            ) = self._run_iteration(project, sampler, planner)
            burnup_samples.append(burnup_trace)

        historical_diagnostics = sampler.get_historical_diagnostics()
        
        # Serialize future sprint overrides for results reporting
        overrides_list = [
            {
                "sprint_number": override.sprint_number,
                "start_date": override.start_date.isoformat() if override.start_date else None,
                "holiday_factor": override.holiday_factor,
                "capacity_multiplier": override.capacity_multiplier,
                "effective_multiplier": override.effective_multiplier(),
                "notes": override.notes,
            }
            for override in sprint_planning.future_sprint_overrides
        ]
        
        results = SprintPlanningResults(
            iterations=self.iterations,
            project_name=project.project.name,
            sprint_length_weeks=sprint_planning.sprint_length_weeks,
            sprint_counts=sprint_counts,
            random_seed=self.random_seed,
            start_date=project.project.start_date,
            planning_confidence_level=sprint_planning.planning_confidence_level,
            removed_work_treatment=str(sprint_planning.removed_work_treatment),
            historical_diagnostics=historical_diagnostics,
            planned_commitment_guidance=self._calculate_planned_commitment(
                sampler,
                sprint_planning.planning_confidence_level,
            ),
            carryover_statistics=self._series_summary(peak_carryover_units),
            spillover_statistics={
                "aggregate_spillover_rate": self._series_summary(spillover_rates),
            },
            disruption_statistics={
                "enabled": project.sprint_planning.volatility_overlay.enabled,
                "configured_probability": (
                    sprint_planning.volatility_overlay.disruption_probability
                    if sprint_planning.volatility_overlay.enabled
                    else 0.0
                ),
                "observed_frequency": float(np.mean(disruption_flags)),
            },
            burnup_percentiles=self._build_burnup_percentiles(burnup_samples),
            future_sprint_overrides=overrides_list,
        )
        results.calculate_statistics()
        for percentile in (50, 80, 90):
            results.percentile(percentile)
            results.date_percentile(percentile)
        return results

    def _run_iteration(
        self,
        project: Project,
        sampler: SprintCapacitySampler,
        planner: SprintPlanner,
    ) -> tuple[int, float, float, float, list[float]]:
        """Run one sprint-planning iteration until named and synthetic backlog are done."""
        completed_task_ids: set[str] = set()
        work_items = planner.build_initial_work_items()
        aggregate_backlog_units = 0.0
        total_tasks = len(project.tasks)
        sprint_planning = project.sprint_planning
        if sprint_planning is None:
            raise ValueError("Sprint simulation requires sprint planning settings")
        sprint_count = 0
        spillover_events = 0
        pulled_items = 0
        disruption_seen = 0.0
        peak_carryover_units = 0.0
        cumulative_delivered = 0.0
        burnup_trace: list[float] = []

        while work_items or aggregate_backlog_units > 1e-9:
            sprint_count += 1
            if sprint_count > 10000:
                raise ValueError(
                    "Sprint planning did not converge within 10000 simulated sprints"
                )

            sprint_start_date = project.project.start_date + timedelta(
                days=(sprint_count - 1) * sprint_planning.sprint_length_weeks * 7
            )
            sampled_outcome = sampler.sample(
                sprint_number=sprint_count,
                sprint_start_date=sprint_start_date,
            )
            plan = planner.plan_sprint(
                completed_task_ids=completed_task_ids,
                sampled_outcome=sampled_outcome,
                sprint_number=sprint_count,
                work_items=work_items,
            )
            disruption_seen = max(
                disruption_seen,
                1.0 if sampled_outcome.disruption_applied else 0.0,
            )
            spillover_events += plan.spillover_event_count
            pulled_items += plan.pulled_item_count

            for item_id in plan.completed_item_ids:
                work_items.pop(item_id, None)
            for item_id in plan.spillover_item_ids:
                work_items.pop(item_id, None)
            for carryover_item in plan.carryover_items:
                work_items[carryover_item.item_id] = carryover_item
            completed_task_ids.update(plan.completed_task_ids)

            for entry in plan.ledger_entries:
                if entry.entry_type == "added_scope":
                    aggregate_backlog_units += entry.units
                elif entry.affects_remaining_backlog:
                    aggregate_backlog_units = max(
                        0.0, aggregate_backlog_units - entry.units
                    )

            synthetic_delivered = 0.0
            if plan.remaining_capacity > 0 and aggregate_backlog_units > 0:
                synthetic_delivered = min(
                    plan.remaining_capacity, aggregate_backlog_units
                )
                aggregate_backlog_units -= synthetic_delivered

            cumulative_delivered += plan.delivered_units + synthetic_delivered
            burnup_trace.append(cumulative_delivered)
            current_carryover_units = sum(
                item.units for item in work_items.values() if item.is_remainder
            )
            peak_carryover_units = max(peak_carryover_units, current_carryover_units)

        if len(completed_task_ids) < total_tasks:
            raise ValueError("Sprint planning ended before all named tasks completed")

        spillover_rate = (
            float(spillover_events / pulled_items) if pulled_items > 0 else 0.0
        )
        return (
            sprint_count,
            peak_carryover_units,
            spillover_rate,
            disruption_seen,
            burnup_trace,
        )

    def _calculate_planned_commitment(
        self,
        sampler: SprintCapacitySampler,
        confidence_level: float,
    ) -> float:
        """Compute the planned-load guidance heuristic from historical diagnostics."""
        rows = sampler.get_diagnostic_rows()
        completed_units = np.asarray([row.completed_units for row in rows], dtype=float)
        added_units = np.asarray([row.added_units for row in rows], dtype=float)
        spillover_ratios = np.asarray(
            [
                sampler.safe_ratio(
                    row.spillover_units,
                    row.completed_units + row.spillover_units,
                )
                for row in rows
            ],
            dtype=float,
        )
        removal_ratios = np.asarray(
            [
                sampler.safe_ratio(
                    row.removed_units,
                    row.completed_units + row.spillover_units + row.removed_units,
                )
                for row in rows
            ],
            dtype=float,
        )

        q = confidence_level * 100
        commitment = float(np.percentile(completed_units, 50)) * (
            1 - float(np.percentile(spillover_ratios, q))
        ) * (1 - float(np.percentile(removal_ratios, q))) - float(
            np.percentile(added_units, q)
        )
        return max(0.0, commitment)

    def _series_summary(self, values: np.ndarray) -> dict[str, float]:
        """Summarize a one-dimensional simulated series."""
        return {
            "mean": float(np.mean(values)),
            "median": float(np.median(values)),
            "p80": float(np.percentile(values, 80)),
            "p90": float(np.percentile(values, 90)),
            "max": float(np.max(values)),
        }

    def _build_burnup_percentiles(
        self,
        burnup_samples: list[list[float]],
    ) -> list[dict[str, float]]:
        """Build exporter-ready cumulative delivery percentile bands by sprint."""
        if not burnup_samples:
            return []

        max_sprints = max(len(sample) for sample in burnup_samples)
        burnup_percentiles: list[dict[str, float]] = []
        for sprint_number in range(1, max_sprints + 1):
            values = []
            for sample in burnup_samples:
                if sprint_number <= len(sample):
                    values.append(sample[sprint_number - 1])
                else:
                    values.append(sample[-1])
            array = np.asarray(values, dtype=float)
            burnup_percentiles.append(
                {
                    "sprint_number": float(sprint_number),
                    "p50": float(np.percentile(array, 50)),
                    "p80": float(np.percentile(array, 80)),
                    "p90": float(np.percentile(array, 90)),
                }
            )
        return burnup_percentiles

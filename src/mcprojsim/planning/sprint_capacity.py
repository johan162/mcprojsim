"""Historical sprint-capacity normalization and sampling."""

from __future__ import annotations

from datetime import date
from dataclasses import dataclass
from itertools import combinations
from typing import Any

import numpy as np

from mcprojsim.models.project import (
    SprintCapacityMode,
    SprintHistoryEntry,
    SprintPlanningSpec,
    SprintVelocityModel,
)


@dataclass(frozen=True)
class NormalizedSprintRow:
    """Canonical historical sprint observation after normalization."""

    sprint_id: str
    sprint_length_weeks: int
    completed_units: float
    spillover_units: float
    added_units: float
    removed_units: float


@dataclass(frozen=True)
class SprintOutcomeSample:
    """Sampled sprint outcome in canonical planning units."""

    completed_units: float
    spillover_units: float
    added_units: float
    removed_units: float
    sampling_mode: str
    nominal_completed_units: float = 0.0
    volatility_multiplier: float = 1.0
    future_override_multiplier: float = 1.0
    sickness_multiplier: float = 1.0
    disruption_applied: bool = False


class SprintCapacitySampler:
    """Normalize and sample historical sprint outcomes."""

    def __init__(
        self,
        sprint_planning: SprintPlanningSpec,
        random_state: np.random.RandomState,
    ):
        """Create a sampler for the given sprint-planning configuration."""
        self.sprint_planning = sprint_planning
        self.random_state = random_state
        self.normalized_rows = tuple(
            self._normalize_entry(entry) for entry in sprint_planning.history
        )
        self._matching_cadence_rows = tuple(
            row
            for row in self.normalized_rows
            if row.sprint_length_weeks == sprint_planning.sprint_length_weeks
        )
        self.uses_weekly_fallback = len(self._matching_cadence_rows) == 0
        self._diagnostic_rows = (
            self._matching_cadence_rows
            if self._matching_cadence_rows
            else self._build_weekly_rows()
        )
        self._nb_mu: float = 0.0
        self._nb_k: float = float("inf")
        if sprint_planning.velocity_model == SprintVelocityModel.NEG_BINOMIAL:
            self._nb_mu, self._nb_k = self._fit_neg_binomial_params()

    def sample(
        self,
        sprint_number: int | None = None,
        sprint_start_date: date | None = None,
    ) -> SprintOutcomeSample:
        """Sample one future sprint outcome from historical observations."""
        if self.sprint_planning.velocity_model == SprintVelocityModel.NEG_BINOMIAL:
            return self._sample_neg_binomial_outcome(sprint_number, sprint_start_date)

        if self._matching_cadence_rows:
            sampled_row = self._sample_row(self._matching_cadence_rows)
            return self._apply_forward_adjustments(
                sampled_row=sampled_row,
                sampling_mode="matching_cadence",
                sprint_number=sprint_number,
                sprint_start_date=sprint_start_date,
            )

        weekly_rows = self._build_weekly_rows()
        sampled_rows = [
            self._sample_row(weekly_rows)
            for _ in range(self.sprint_planning.sprint_length_weeks)
        ]
        aggregate_row = NormalizedSprintRow(
            sprint_id="weekly_fallback",
            sprint_length_weeks=self.sprint_planning.sprint_length_weeks,
            completed_units=float(sum(row.completed_units for row in sampled_rows)),
            spillover_units=float(sum(row.spillover_units for row in sampled_rows)),
            added_units=float(sum(row.added_units for row in sampled_rows)),
            removed_units=float(sum(row.removed_units for row in sampled_rows)),
        )
        return self._apply_forward_adjustments(
            sampled_row=aggregate_row,
            sampling_mode="weekly_fallback",
            sprint_number=sprint_number,
            sprint_start_date=sprint_start_date,
        )

    def _apply_forward_adjustments(
        self,
        sampled_row: NormalizedSprintRow,
        sampling_mode: str,
        sprint_number: int | None,
        sprint_start_date: date | None,
    ) -> SprintOutcomeSample:
        """Apply volatility and future overrides to sampled deliverable capacity."""
        volatility_multiplier, disruption_applied = self._sample_volatility_multiplier()
        future_override_multiplier = self._future_override_multiplier(
            sprint_number=sprint_number,
            sprint_start_date=sprint_start_date,
        )
        sickness_multiplier = self._sample_sickness_multiplier()
        nominal_completed_units = float(sampled_row.completed_units)
        effective_completed_units = (
            nominal_completed_units
            * volatility_multiplier
            * future_override_multiplier
            * sickness_multiplier
        )

        return SprintOutcomeSample(
            completed_units=effective_completed_units,
            nominal_completed_units=nominal_completed_units,
            spillover_units=sampled_row.spillover_units,
            added_units=sampled_row.added_units,
            removed_units=sampled_row.removed_units,
            sampling_mode=sampling_mode,
            volatility_multiplier=volatility_multiplier,
            future_override_multiplier=future_override_multiplier,
            sickness_multiplier=sickness_multiplier,
            disruption_applied=disruption_applied,
        )

    def get_historical_diagnostics(self) -> dict[str, Any]:
        """Return descriptive statistics and correlation summaries for history."""
        completed = [row.completed_units for row in self._diagnostic_rows]
        spillover = [row.spillover_units for row in self._diagnostic_rows]
        added = [row.added_units for row in self._diagnostic_rows]
        removed = [row.removed_units for row in self._diagnostic_rows]

        velocity_model = str(self.sprint_planning.velocity_model.value)
        base_sampling_mode = (
            "matching_cadence" if self._matching_cadence_rows else "weekly_fallback"
        )
        sampling_mode = (
            f"neg_binomial_{base_sampling_mode}"
            if velocity_model == "neg_binomial"
            else base_sampling_mode
        )

        diagnostics: dict[str, Any] = {
            "sampling_mode": sampling_mode,
            "velocity_model": velocity_model,
            "observation_count": len(self._diagnostic_rows),
            "series_statistics": {
                "completed_units": self._series_statistics(completed),
                "spillover_units": self._series_statistics(spillover),
                "added_units": self._series_statistics(added),
                "removed_units": self._series_statistics(removed),
            },
            "ratios": {
                "spillover_ratio": self._ratio_statistics(
                    [
                        self.safe_ratio(
                            row.spillover_units,
                            row.completed_units + row.spillover_units,
                        )
                        for row in self._diagnostic_rows
                    ]
                ),
                "scope_addition_ratio": self._ratio_statistics(
                    [
                        self.safe_ratio(
                            row.added_units,
                            row.completed_units + row.added_units,
                        )
                        for row in self._diagnostic_rows
                    ]
                ),
                "scope_removal_ratio": self._ratio_statistics(
                    [
                        self.safe_ratio(
                            row.removed_units,
                            row.completed_units
                            + row.spillover_units
                            + row.removed_units,
                        )
                        for row in self._diagnostic_rows
                    ]
                ),
            },
            "correlations": self._correlation_statistics(
                {
                    "completed_units": completed,
                    "spillover_units": spillover,
                    "added_units": added,
                    "removed_units": removed,
                }
            ),
        }

        if velocity_model == "neg_binomial":
            diagnostics["neg_binomial_params"] = {
                "mu": self._nb_mu,
                "k": self._nb_k if not np.isinf(self._nb_k) else None,
                "overdispersed": not np.isinf(self._nb_k),
            }

        sickness = self.sprint_planning.sickness
        diagnostics["sickness"] = {
            "enabled": sickness.enabled,
            "team_size": sickness.team_size,
            "probability_per_person_per_week": sickness.probability_per_person_per_week,
            "duration_log_mu": sickness.duration_log_mu,
            "duration_log_sigma": sickness.duration_log_sigma,
        }

        return diagnostics

    def get_diagnostic_rows(self) -> tuple[NormalizedSprintRow, ...]:
        """Return the normalized rows used for historical diagnostics."""
        return self._diagnostic_rows

    @staticmethod
    def safe_ratio(numerator: float, denominator: float) -> float:
        """Calculate a stable ratio for diagnostics."""
        if denominator <= 0:
            return 0.0
        return float(numerator / denominator)

    def _normalize_entry(self, entry: SprintHistoryEntry) -> NormalizedSprintRow:
        """Normalize one sprint history entry into canonical planning units."""
        if self.sprint_planning.capacity_mode == SprintCapacityMode.STORY_POINTS:
            completed_units = float(entry.completed_story_points or 0)
            spillover_units = float(entry.spillover_story_points)
            added_units = float(entry.added_story_points)
            removed_units = float(entry.removed_story_points)
        else:
            completed_units = float(entry.completed_tasks or 0)
            spillover_units = float(entry.spillover_tasks)
            added_units = float(entry.added_tasks)
            removed_units = float(entry.removed_tasks)

        holiday_factor = float(entry.holiday_factor)
        return NormalizedSprintRow(
            sprint_id=entry.sprint_id,
            sprint_length_weeks=int(entry.sprint_length_weeks or 1),
            completed_units=completed_units / holiday_factor,
            spillover_units=spillover_units / holiday_factor,
            added_units=added_units,
            removed_units=removed_units,
        )

    def _build_weekly_rows(self) -> tuple[NormalizedSprintRow, ...]:
        """Convert normalized sprint rows into weekly-rate observations."""
        return tuple(
            NormalizedSprintRow(
                sprint_id=row.sprint_id,
                sprint_length_weeks=1,
                completed_units=row.completed_units / row.sprint_length_weeks,
                spillover_units=row.spillover_units / row.sprint_length_weeks,
                added_units=row.added_units / row.sprint_length_weeks,
                removed_units=row.removed_units / row.sprint_length_weeks,
            )
            for row in self.normalized_rows
        )

    def _fit_neg_binomial_params(self) -> tuple[float, float]:
        """Estimate Negative Binomial mu and dispersion k from history.

        Uses method-of-moments: if sample variance exceeds the mean the data
        is overdispersed and k = mu^2 / (var - mu).  Otherwise k is infinite
        and a Poisson observation model is used as fallback.
        """
        completed = np.asarray(
            [row.completed_units for row in self._diagnostic_rows], dtype=float
        )
        mu = float(np.mean(completed))
        if mu <= 0:
            return 0.0, float("inf")
        var = float(np.var(completed, ddof=1))
        if var <= mu:
            return mu, float("inf")
        k = mu**2 / (var - mu)
        return mu, k

    def _sample_nb_value(self) -> float:
        """Sample one completed-units draw from the fitted NB distribution."""
        if self._nb_mu <= 0:
            return 0.0
        if np.isinf(self._nb_k):
            return float(self.random_state.poisson(self._nb_mu))
        p = self._nb_k / (self._nb_k + self._nb_mu)
        return float(self.random_state.negative_binomial(self._nb_k, p))

    def _sample_neg_binomial_outcome(
        self,
        sprint_number: int | None,
        sprint_start_date: date | None,
    ) -> SprintOutcomeSample:
        """Sample one sprint outcome using the Negative Binomial velocity model."""
        if self.uses_weekly_fallback:
            completed = sum(
                self._sample_nb_value()
                for _ in range(self.sprint_planning.sprint_length_weeks)
            )
        else:
            completed = self._sample_nb_value()

        churn_rows = (
            self._matching_cadence_rows
            if self._matching_cadence_rows
            else self._build_weekly_rows()
        )
        if self.uses_weekly_fallback:
            sampled_churn = [
                self._sample_row(churn_rows)
                for _ in range(self.sprint_planning.sprint_length_weeks)
            ]
            spillover = float(sum(r.spillover_units for r in sampled_churn))
            added = float(sum(r.added_units for r in sampled_churn))
            removed = float(sum(r.removed_units for r in sampled_churn))
        else:
            churn_row = self._sample_row(churn_rows)
            spillover = churn_row.spillover_units
            added = churn_row.added_units
            removed = churn_row.removed_units

        sampled_row = NormalizedSprintRow(
            sprint_id="neg_binomial",
            sprint_length_weeks=self.sprint_planning.sprint_length_weeks,
            completed_units=completed,
            spillover_units=spillover,
            added_units=added,
            removed_units=removed,
        )
        return self._apply_forward_adjustments(
            sampled_row=sampled_row,
            sampling_mode="neg_binomial",
            sprint_number=sprint_number,
            sprint_start_date=sprint_start_date,
        )

    def _sample_row(self, rows: tuple[NormalizedSprintRow, ...]) -> NormalizedSprintRow:
        """Sample one normalized observation using the configured RNG."""
        index = int(self.random_state.randint(0, len(rows)))
        return rows[index]

    def _sample_volatility_multiplier(self) -> tuple[float, bool]:
        """Sample the optional disruption multiplier for one sprint."""
        volatility = self.sprint_planning.volatility_overlay
        if not volatility.enabled or volatility.disruption_probability <= 0:
            return 1.0, False

        if float(self.random_state.random_sample()) > volatility.disruption_probability:
            return 1.0, False

        if (
            volatility.disruption_multiplier_low
            == volatility.disruption_multiplier_expected
            == volatility.disruption_multiplier_high
        ):
            return float(volatility.disruption_multiplier_low), True

        multiplier = float(
            self.random_state.triangular(
                volatility.disruption_multiplier_low,
                volatility.disruption_multiplier_expected,
                volatility.disruption_multiplier_high,
            )
        )
        return multiplier, True

    def _sample_sickness_multiplier(self) -> float:
        """Sample a capacity multiplier accounting for team sickness absence.

        Uses a two-stage per-person model:
        1. Binomial draw for the number of people who fall sick this sprint.
        2. For each sick person, a LogNormal draw for the number of lost days.
        Total lost days are converted to a fractional capacity multiplier.
        """
        sickness = self.sprint_planning.sickness
        if not sickness.enabled or not sickness.team_size:
            return 1.0

        team_size = sickness.team_size
        sprint_weeks = self.sprint_planning.sprint_length_weeks
        total_person_days = team_size * sprint_weeks * 5  # working days

        # Stage 1: how many people fall sick at least once per week?
        total_sick_events = 0
        for _ in range(sprint_weeks):
            sick_this_week = int(
                self.random_state.binomial(
                    team_size, sickness.probability_per_person_per_week
                )
            )
            total_sick_events += sick_this_week

        if total_sick_events == 0:
            return 1.0

        # Stage 2: duration per sick event (days), capped at remaining sprint days
        lost_days = 0.0
        max_days = float(sprint_weeks * 5)
        for _ in range(total_sick_events):
            duration = float(
                self.random_state.lognormal(
                    sickness.duration_log_mu, sickness.duration_log_sigma
                )
            )
            lost_days += min(duration, max_days)

        lost_days = min(lost_days, float(total_person_days))
        return max(0.0, 1.0 - lost_days / total_person_days)

    def _future_override_multiplier(
        self,
        sprint_number: int | None,
        sprint_start_date: date | None,
    ) -> float:
        """Resolve the explicit forward-looking multiplier for a future sprint."""
        for override in self.sprint_planning.future_sprint_overrides:
            matches_sprint_number = (
                sprint_number is not None and override.sprint_number == sprint_number
            )
            matches_start_date = (
                sprint_start_date is not None
                and override.start_date == sprint_start_date
            )
            if matches_sprint_number or matches_start_date:
                return override.effective_multiplier()
        return 1.0

    def _series_statistics(self, values: list[float]) -> dict[str, float]:
        """Calculate descriptive statistics for a single series."""
        array = np.asarray(values, dtype=float)
        mean = float(np.mean(array))
        median = float(np.median(array))
        std_dev = float(np.std(array))
        return {
            "mean": mean,
            "median": median,
            "std_dev": std_dev,
            "min": float(np.min(array)),
            "max": float(np.max(array)),
            "coefficient_of_variation": (std_dev / mean if mean > 0 else 0.0),
        }

    def _ratio_statistics(self, values: list[float]) -> dict[str, Any]:
        """Calculate descriptive and percentile statistics for a ratio series."""
        stats: dict[str, Any] = self._series_statistics(values)
        array = np.asarray(values, dtype=float)
        stats["percentiles"] = {
            50: float(np.percentile(array, 50)),
            80: float(np.percentile(array, 80)),
            90: float(np.percentile(array, 90)),
        }
        return stats

    def _correlation_statistics(
        self, series_map: dict[str, list[float]]
    ) -> dict[str, float]:
        """Calculate pairwise Pearson correlations across historical series."""
        correlations: dict[str, float] = {}
        for left_key, right_key in combinations(series_map.keys(), 2):
            pair_key = f"{left_key}|{right_key}"
            correlations[pair_key] = self._safe_pearson(
                series_map[left_key],
                series_map[right_key],
            )
        return correlations

    def _safe_pearson(self, left: list[float], right: list[float]) -> float:
        """Calculate Pearson correlation, returning 0 for degenerate cases."""
        left_array = np.asarray(left, dtype=float)
        right_array = np.asarray(right, dtype=float)
        if len(left_array) < 2 or len(right_array) < 2:
            return 0.0
        if np.std(left_array) == 0 or np.std(right_array) == 0:
            return 0.0
        return float(np.corrcoef(left_array, right_array)[0, 1])

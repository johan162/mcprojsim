"""Staffing analysis based on simulation results.

Provides team-size recommendations using a communication-overhead model
inspired by Brooks's Law.  For a team of *n* people each individual's
productivity is reduced by a per-person overhead factor *c*, giving an
effective team capacity of:

    E(n) = n · max(min_prod, 1 - c·(n-1)) · f

where *f* is a productivity factor that depends on the experience profile
and *min_prod* is a floor that prevents the model from predicting
zero-productivity teams.

Calendar duration for a given team size is the larger of the critical-path
time (which cannot be compressed by adding people) and total effort divided
by effective capacity:

    T(n) = max(T_cp, W / E(n))

The module supports multiple experience profiles (senior, mixed, junior)
each with their own *f* and *c*.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Dict, List

from mcprojsim.config import Config
from mcprojsim.models.simulation import SimulationResults


class StaffingRow:
    """A single row in the staffing analysis table."""

    __slots__ = (
        "team_size",
        "profile",
        "individual_productivity",
        "effective_capacity",
        "calendar_hours",
        "calendar_working_days",
        "delivery_date",
        "efficiency",
    )

    def __init__(
        self,
        *,
        team_size: int,
        profile: str,
        individual_productivity: float,
        effective_capacity: float,
        calendar_hours: float,
        calendar_working_days: int,
        delivery_date: date | None,
        efficiency: float,
    ) -> None:
        self.team_size = team_size
        self.profile = profile
        self.individual_productivity = individual_productivity
        self.effective_capacity = effective_capacity
        self.calendar_hours = calendar_hours
        self.calendar_working_days = calendar_working_days
        self.delivery_date = delivery_date
        self.efficiency = efficiency

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "team_size": self.team_size,
            "profile": self.profile,
            "individual_productivity": round(self.individual_productivity, 4),
            "effective_capacity": round(self.effective_capacity, 2),
            "calendar_hours": round(self.calendar_hours, 2),
            "calendar_working_days": self.calendar_working_days,
            "delivery_date": (
                self.delivery_date.isoformat() if self.delivery_date else None
            ),
            "efficiency": round(self.efficiency, 4),
        }


class StaffingRecommendation:
    """Recommended team size for one experience profile."""

    __slots__ = (
        "profile",
        "recommended_team_size",
        "calendar_working_days",
        "delivery_date",
        "efficiency",
        "total_effort_hours",
        "critical_path_hours",
        "parallelism_ratio",
    )

    def __init__(
        self,
        *,
        profile: str,
        recommended_team_size: int,
        calendar_working_days: int,
        delivery_date: date | None,
        efficiency: float,
        total_effort_hours: float,
        critical_path_hours: float,
        parallelism_ratio: float,
    ) -> None:
        self.profile = profile
        self.recommended_team_size = recommended_team_size
        self.calendar_working_days = calendar_working_days
        self.delivery_date = delivery_date
        self.efficiency = efficiency
        self.total_effort_hours = total_effort_hours
        self.critical_path_hours = critical_path_hours
        self.parallelism_ratio = parallelism_ratio

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "profile": self.profile,
            "recommended_team_size": self.recommended_team_size,
            "calendar_working_days": self.calendar_working_days,
            "delivery_date": (
                self.delivery_date.isoformat() if self.delivery_date else None
            ),
            "efficiency": round(self.efficiency, 4),
            "total_effort_hours": round(self.total_effort_hours, 2),
            "critical_path_hours": round(self.critical_path_hours, 2),
            "parallelism_ratio": round(self.parallelism_ratio, 2),
        }


class StaffingAnalyzer:
    """Compute staffing recommendations from simulation results."""

    @staticmethod
    def individual_productivity(
        team_size: int,
        communication_overhead: float,
        min_productivity: float,
    ) -> float:
        """Return per-person productivity for a given team size.

        Args:
            team_size: Number of people on the team (>= 1).
            communication_overhead: Fractional productivity loss per
                additional team member (e.g. 0.06 = 6%).
            min_productivity: Floor below which individual productivity
                will not drop.

        Returns:
            A value in [min_productivity, 1.0].
        """
        raw = 1.0 - communication_overhead * (team_size - 1)
        return max(min_productivity, raw)

    @staticmethod
    def effective_capacity(
        team_size: int,
        communication_overhead: float,
        productivity_factor: float,
        min_productivity: float,
    ) -> float:
        """Effective person-equivalents for a sized team.

        Args:
            team_size: Number of people.
            communication_overhead: Per-person overhead fraction.
            productivity_factor: Experience-level multiplier (0–1].
            min_productivity: Individual productivity floor.

        Returns:
            Effective capacity in person-equivalents.
        """
        ip = StaffingAnalyzer.individual_productivity(
            team_size, communication_overhead, min_productivity
        )
        return team_size * ip * productivity_factor

    @staticmethod
    def calendar_hours(
        total_effort: float,
        critical_path_hours: float,
        team_size: int,
        communication_overhead: float,
        productivity_factor: float,
        min_productivity: float,
        hours_per_day: float,
    ) -> float:
        """Compute calendar elapsed hours for a team size.

        Calendar time cannot go below the critical-path duration
        regardless of team size.

        Args:
            total_effort: Total person-hours of work.
            critical_path_hours: Critical-path elapsed hours (floor).
            team_size: Number of people.
            communication_overhead: Per-person overhead fraction.
            productivity_factor: Experience-level multiplier.
            min_productivity: Individual productivity floor.
            hours_per_day: Working hours per day.

        Returns:
            Elapsed calendar hours.
        """
        cap = StaffingAnalyzer.effective_capacity(
            team_size, communication_overhead, productivity_factor, min_productivity
        )
        effort_hours = total_effort / cap if cap > 0 else total_effort
        return max(critical_path_hours, effort_hours)

    @staticmethod
    def calculate_staffing_table(
        results: SimulationResults,
        config: Config,
    ) -> List[StaffingRow]:
        """Build a staffing table for team sizes 1 .. max_parallel_tasks.

        Args:
            results: Simulation results.
            config: Active configuration (provides staffing parameters).

        Returns:
            Flat list of ``StaffingRow`` objects (one per team-size
            per experience profile), sorted by profile then team size.
        """
        total_effort = results.total_effort_hours()
        cp_hours = results.mean  # elapsed critical-path time
        hours_per_day = results.hours_per_day
        max_team = max(results.max_parallel_tasks, 1)
        min_prod = config.staffing.min_individual_productivity

        rows: List[StaffingRow] = []
        for prof_name, prof in sorted(config.staffing.experience_profiles.items()):
            for n in range(1, max_team + 1):
                ip = StaffingAnalyzer.individual_productivity(
                    n, prof.communication_overhead, min_prod
                )
                cap = StaffingAnalyzer.effective_capacity(
                    n,
                    prof.communication_overhead,
                    prof.productivity_factor,
                    min_prod,
                )
                cal_hours = StaffingAnalyzer.calendar_hours(
                    total_effort,
                    cp_hours,
                    n,
                    prof.communication_overhead,
                    prof.productivity_factor,
                    min_prod,
                    hours_per_day,
                )
                cal_wd = math.ceil(cal_hours / hours_per_day)
                delivery = results.delivery_date(cal_hours)
                # Efficiency = ideal single-person time / actual person-hours
                actual_person_hours = cal_hours * cap if cap > 0 else total_effort
                efficiency = (
                    total_effort / actual_person_hours
                    if actual_person_hours > 0
                    else 0.0
                )
                rows.append(
                    StaffingRow(
                        team_size=n,
                        profile=prof_name,
                        individual_productivity=ip,
                        effective_capacity=cap,
                        calendar_hours=cal_hours,
                        calendar_working_days=cal_wd,
                        delivery_date=delivery,
                        efficiency=efficiency,
                    )
                )
        return rows

    @staticmethod
    def recommend_team_size(
        results: SimulationResults,
        config: Config,
    ) -> List[StaffingRecommendation]:
        """Find the optimal team size for each experience profile.

        Optimal is defined as the smallest *n* where adding one more
        person reduces calendar time by less than 5%.

        Args:
            results: Simulation results.
            config: Active configuration.

        Returns:
            One ``StaffingRecommendation`` per experience profile,
            sorted alphabetically by profile name.
        """
        total_effort = results.total_effort_hours()
        cp_hours = results.mean
        hours_per_day = results.hours_per_day
        max_team = max(results.max_parallel_tasks, 1)
        min_prod = config.staffing.min_individual_productivity
        parallelism_ratio = total_effort / cp_hours if cp_hours > 0 else 1.0
        threshold = 0.05  # 5 % improvement threshold

        recommendations: List[StaffingRecommendation] = []
        for prof_name, prof in sorted(config.staffing.experience_profiles.items()):
            best_n = 1
            prev_cal = StaffingAnalyzer.calendar_hours(
                total_effort,
                cp_hours,
                1,
                prof.communication_overhead,
                prof.productivity_factor,
                min_prod,
                hours_per_day,
            )
            for n in range(2, max_team + 1):
                cur_cal = StaffingAnalyzer.calendar_hours(
                    total_effort,
                    cp_hours,
                    n,
                    prof.communication_overhead,
                    prof.productivity_factor,
                    min_prod,
                    hours_per_day,
                )
                improvement = (prev_cal - cur_cal) / prev_cal if prev_cal > 0 else 0.0
                if improvement < threshold:
                    break
                best_n = n
                prev_cal = cur_cal

            final_cal = StaffingAnalyzer.calendar_hours(
                total_effort,
                cp_hours,
                best_n,
                prof.communication_overhead,
                prof.productivity_factor,
                min_prod,
                hours_per_day,
            )
            final_wd = math.ceil(final_cal / hours_per_day)
            delivery = results.delivery_date(final_cal)
            cap = StaffingAnalyzer.effective_capacity(
                best_n,
                prof.communication_overhead,
                prof.productivity_factor,
                min_prod,
            )
            actual_ph = final_cal * cap if cap > 0 else total_effort
            efficiency = total_effort / actual_ph if actual_ph > 0 else 0.0

            recommendations.append(
                StaffingRecommendation(
                    profile=prof_name,
                    recommended_team_size=best_n,
                    calendar_working_days=final_wd,
                    delivery_date=delivery,
                    efficiency=efficiency,
                    total_effort_hours=total_effort,
                    critical_path_hours=cp_hours,
                    parallelism_ratio=parallelism_ratio,
                )
            )
        return recommendations

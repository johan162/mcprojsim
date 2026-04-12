"""Risk evaluator for probabilistic risk assessment."""

from typing import Optional

import numpy as np

from mcprojsim.models.project import Risk


class RiskEvaluator:
    """Evaluator for risk events."""

    def __init__(self, random_state: Optional[np.random.RandomState] = None):
        """Initialize risk evaluator.

        Args:
            random_state: NumPy random state for reproducibility
        """
        self.random_state = random_state or np.random.RandomState()

    def evaluate_risk(
        self,
        risk: Risk,
        base_duration: float = 0.0,
        hours_per_day: float = 8.0,
    ) -> float:
        """Evaluate a risk and return its impact if triggered.

        Args:
            risk: Risk to evaluate
            base_duration: Base duration in hours for percentage-based impacts
            hours_per_day: Working hours per day for unit conversion

        Returns:
            Impact value in hours (0 if not triggered)
        """
        # Roll the dice
        if self.random_state.random() < risk.probability:
            # Risk triggered!
            return risk.get_impact_value(base_duration, hours_per_day)
        return 0.0

    def evaluate_risks(
        self,
        risks: list[Risk],
        base_duration: float = 0.0,
        hours_per_day: float = 8.0,
    ) -> float:
        """Evaluate multiple risks and return cumulative impact.

        Args:
            risks: List of risks to evaluate
            base_duration: Base duration in hours for percentage-based impacts
            hours_per_day: Working hours per day for unit conversion

        Returns:
            Total impact in hours from all triggered risks
        """
        total_impact = 0.0
        for risk in risks:
            total_impact += self.evaluate_risk(risk, base_duration, hours_per_day)
        return total_impact

    def evaluate_risk_with_cost(
        self,
        risk: Risk,
        base_duration: float = 0.0,
        hours_per_day: float = 8.0,
    ) -> tuple[float, float]:
        """Evaluate a risk and return both time and cost impacts.

        A single probability roll determines whether the risk triggers.
        When triggered, both the time impact (hours) and cost impact (currency
        units) are returned. This preserves the correlation between schedule
        overruns and cost overruns.

        Args:
            risk: Risk to evaluate
            base_duration: Base duration in hours for percentage-based time impacts
            hours_per_day: Working hours per day for unit conversion

        Returns:
            Tuple of (time_impact_hours, cost_impact_currency) where both are 0.0
            when the risk does not trigger.
        """
        if self.random_state.random() < risk.probability:
            time_impact = risk.get_impact_value(base_duration, hours_per_day)
            cost_impact = risk.cost_impact if risk.cost_impact is not None else 0.0
            return (time_impact, cost_impact)
        return (0.0, 0.0)

    def evaluate_risks_with_cost(
        self,
        risks: list[Risk],
        base_duration: float = 0.0,
        hours_per_day: float = 8.0,
    ) -> tuple[float, float]:
        """Evaluate multiple risks and return cumulative time and cost impacts.

        Args:
            risks: List of risks to evaluate
            base_duration: Base duration in hours for percentage-based time impacts
            hours_per_day: Working hours per day for unit conversion

        Returns:
            Tuple of (total_time_impact_hours, total_cost_impact_currency)
        """
        total_time = 0.0
        total_cost = 0.0
        for risk in risks:
            t, c = self.evaluate_risk_with_cost(risk, base_duration, hours_per_day)
            total_time += t
            total_cost += c
        return (total_time, total_cost)

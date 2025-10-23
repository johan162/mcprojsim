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

    def evaluate_risk(self, risk: Risk, base_duration: float = 0.0) -> float:
        """Evaluate a risk and return its impact if triggered.

        Args:
            risk: Risk to evaluate
            base_duration: Base duration for percentage-based impacts

        Returns:
            Impact value (0 if not triggered, impact value if triggered)
        """
        # Roll the dice
        if self.random_state.random() < risk.probability:
            # Risk triggered!
            return risk.get_impact_value(base_duration)
        return 0.0

    def evaluate_risks(
        self, risks: list[Risk], base_duration: float = 0.0
    ) -> float:
        """Evaluate multiple risks and return cumulative impact.

        Args:
            risks: List of risks to evaluate
            base_duration: Base duration for percentage-based impacts

        Returns:
            Total impact from all triggered risks
        """
        total_impact = 0.0
        for risk in risks:
            total_impact += self.evaluate_risk(risk, base_duration)
        return total_impact

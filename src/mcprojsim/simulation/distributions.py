"""Probability distributions for task estimation."""

from typing import Optional

import numpy as np

from mcprojsim.models.project import DistributionType, TaskEstimate


class DistributionSampler:
    """Sampler for various probability distributions."""

    def __init__(self, random_state: Optional[np.random.RandomState] = None):
        """Initialize sampler with optional random state.

        Args:
            random_state: NumPy random state for reproducibility
        """
        self.random_state = random_state or np.random.RandomState()

    def sample(self, estimate: TaskEstimate) -> float:
        """Sample a value from the task estimate distribution.

        Args:
            estimate: Task estimate with distribution parameters

        Returns:
            Sampled duration value
        """
        if estimate.distribution == DistributionType.TRIANGULAR:
            return self._sample_triangular(
                estimate.low, estimate.expected, estimate.high  # type: ignore
            )
        elif estimate.distribution == DistributionType.LOGNORMAL:
            return self._sample_lognormal(
                estimate.expected, estimate.standard_deviation  # type: ignore
            )
        else:
            raise ValueError(f"Unknown distribution type: {estimate.distribution}")

    def _sample_triangular(
        self, low_val: float, expected: float, high_val: float
    ) -> float:
        """Sample from triangular distribution.

        Args:
            low_val: Lower bound value
            expected: Expected value (mode)
            high_val: Upper bound value

        Returns:
            Sampled value
        """
        return float(self.random_state.triangular(low_val, expected, high_val))

    def _sample_lognormal(self, expected: float, std_dev: float) -> float:
        """Sample from lognormal distribution.

        Args:
            expected: Expected value (used as mode to calculate mu)
            std_dev: Standard deviation (sigma)

        Returns:
            Sampled value
        """
        # Convert expected (mode) to mu parameter for lognormal
        # For lognormal, mode = exp(mu - sigma^2)
        # So mu = ln(mode) + sigma^2
        sigma = std_dev
        mu = np.log(expected) + sigma**2

        return float(self.random_state.lognormal(mu, sigma))

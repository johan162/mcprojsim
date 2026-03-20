"""Probability distributions for task estimation."""

import math
from typing import Optional

import numpy as np

from mcprojsim.models.project import DistributionType, TaskEstimate

LOGNORMAL_BOUNDARY_SIGMA_MULTIPLIER = 6.0


def fit_shifted_lognormal(
    low: float, expected: float, high: float, high_percentile_z: float
) -> tuple[float, float]:
    """Fit shifted-lognormal parameters from low/mode/high-percentile inputs."""
    shifted_mode = expected - low
    shifted_high = high - low
    if shifted_mode <= 0 or shifted_high <= 0:
        raise ValueError("Shifted lognormal requires low < expected < high")

    log_ratio = math.log(shifted_high) - math.log(shifted_mode)
    sigma = (-high_percentile_z + math.sqrt(high_percentile_z**2 + 4 * log_ratio)) / 2
    mu = math.log(shifted_mode) + sigma**2
    return mu, sigma


class DistributionSampler:
    """Sampler for various probability distributions."""

    def __init__(
        self,
        random_state: Optional[np.random.RandomState] = None,
        lognormal_high_percentile_z: float = 1.6448536269514722,
    ):
        """Initialize sampler with optional random state.

        Args:
            random_state: NumPy random state for reproducibility
        """
        self.random_state = random_state or np.random.RandomState()
        self.lognormal_high_percentile_z = lognormal_high_percentile_z

    def sample(self, estimate: TaskEstimate) -> float:
        """Sample a value from the task estimate distribution.

        Args:
            estimate: Task estimate with distribution parameters

        Returns:
            Sampled duration value
        """
        distribution = estimate.distribution or DistributionType.TRIANGULAR
        if distribution == DistributionType.TRIANGULAR:
            assert (
                estimate.low is not None
                and estimate.expected is not None
                and estimate.high is not None
            )
            return self._sample_triangular(
                estimate.low, estimate.expected, estimate.high
            )
        elif distribution == DistributionType.LOGNORMAL:
            assert (
                estimate.low is not None
                and estimate.expected is not None
                and estimate.high is not None
            )
            return self._sample_lognormal(
                estimate.low,
                estimate.expected,
                estimate.high,
            )
        else:
            raise ValueError(f"Unknown distribution type: {distribution}")

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

    def _sample_lognormal(self, low: float, expected: float, high: float) -> float:
        """Sample from a shifted lognormal distribution.

        Args:
            low: Lower bound shift
            expected: Expected value interpreted as the mode
            high: High value interpreted as the configured percentile

        Returns:
            Sampled value
        """
        mu, sigma = fit_shifted_lognormal(
            low,
            expected,
            high,
            self.lognormal_high_percentile_z,
        )
        return float(low + self.random_state.lognormal(mu, sigma))

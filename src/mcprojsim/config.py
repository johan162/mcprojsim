"""Configuration management for uncertainty factors and simulation settings."""

from copy import deepcopy
from pathlib import Path
from typing import Dict, Optional

import yaml
from pydantic import BaseModel, Field

# This file defines the configuration schema and default values for the Monte Carlo Project Simulator.
# This is where we centralize all configurable parameters, including uncertainty factors, T-shirt size mappings,
# and simulation settings. The SimulationEngine will use this configuration to adjust task durations and apply
# risk impacts during simulation.
# It is the single source of truth for all configuration-related logic, making it easier to maintain and extend in the future.

DEFAULT_SIMULATION_ITERATIONS = 10000
DEFAULT_OUTPUT_FORMATS = ["json", "csv", "html"]
DEFAULT_HISTOGRAM_BINS = 50
DEFAULT_MAX_STORED_CRITICAL_PATHS = 20
DEFAULT_CRITICAL_PATH_REPORT_LIMIT = 2
DEFAULT_CONFIDENCE_LEVELS = [25, 50, 75, 80, 85, 90, 95, 99]
DEFAULT_PROBABILITY_RED_THRESHOLD = 0.50
DEFAULT_PROBABILITY_GREEN_THRESHOLD = 0.90
DEFAULT_UNCERTAINTY_FACTOR_LEVELS = {
    "team_experience": "medium",
    "requirements_maturity": "medium",
    "technical_complexity": "medium",
    "team_distribution": "colocated",
    "integration_complexity": "medium",
}
DEFAULT_UNCERTAINTY_FACTORS = {
    "team_experience": {"high": 0.90, "medium": 1.0, "low": 1.30},
    "requirements_maturity": {"high": 1.0, "medium": 1.15, "low": 1.40},
    "technical_complexity": {"low": 1.0, "medium": 1.20, "high": 1.50},
    "team_distribution": {"colocated": 1.0, "distributed": 1.25},
    "integration_complexity": {"low": 1.0, "medium": 1.15, "high": 1.35},
}
DEFAULT_T_SHIRT_SIZE_VALUES = {
    "XS": {"min": 0.5, "most_likely": 1, "max": 2},
    "S": {"min": 1, "most_likely": 2, "max": 4},
    "M": {"min": 3, "most_likely": 5, "max": 8},
    "L": {"min": 5, "most_likely": 8, "max": 13},
    "XL": {"min": 8, "most_likely": 13, "max": 21},
    "XXL": {"min": 13, "most_likely": 21, "max": 34},
}
DEFAULT_STORY_POINT_VALUES = {
    1: {"min": 0.5, "most_likely": 1, "max": 3},
    2: {"min": 1, "most_likely": 2, "max": 4},
    3: {"min": 1.5, "most_likely": 3, "max": 5},
    5: {"min": 3, "most_likely": 5, "max": 8},
    8: {"min": 5, "most_likely": 8, "max": 15},
    13: {"min": 8, "most_likely": 13, "max": 21},
    21: {"min": 13, "most_likely": 21, "max": 34},
}


def _build_default_config_data() -> dict:
    """Build the default configuration payload."""
    return {
        "uncertainty_factors": deepcopy(DEFAULT_UNCERTAINTY_FACTORS),
        "t_shirt_sizes": {
            size: deepcopy(values)
            for size, values in DEFAULT_T_SHIRT_SIZE_VALUES.items()
        },
        "story_points": {
            points: deepcopy(values)
            for points, values in DEFAULT_STORY_POINT_VALUES.items()
        },
        "simulation": {
            "default_iterations": DEFAULT_SIMULATION_ITERATIONS,
            "random_seed": None,
            "max_stored_critical_paths": DEFAULT_MAX_STORED_CRITICAL_PATHS,
        },
        "output": {
            "formats": list(DEFAULT_OUTPUT_FORMATS),
            "include_histogram": True,
            "histogram_bins": DEFAULT_HISTOGRAM_BINS,
            "critical_path_report_limit": DEFAULT_CRITICAL_PATH_REPORT_LIMIT,
        },
    }


def _merge_nested_dicts(base: dict, overrides: dict) -> dict:
    """Recursively merge dictionaries, preserving defaults."""
    merged = deepcopy(base)

    for key, value in overrides.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_nested_dicts(merged[key], value)
        else:
            merged[key] = value

    return merged


class UncertaintyFactorConfig(BaseModel):
    """Configuration for a single uncertainty factor."""

    high: float = Field(default=1.0)
    medium: float = Field(default=1.0)
    low: float = Field(default=1.0)


class SimulationConfig(BaseModel):
    """Simulation settings."""

    default_iterations: int = Field(default=DEFAULT_SIMULATION_ITERATIONS, gt=0)
    random_seed: Optional[int] = None
    max_stored_critical_paths: int = Field(
        default=DEFAULT_MAX_STORED_CRITICAL_PATHS,
        gt=0,
    )


class OutputConfig(BaseModel):
    """Output settings."""

    formats: list[str] = Field(default_factory=lambda: list(DEFAULT_OUTPUT_FORMATS))
    include_histogram: bool = True
    histogram_bins: int = Field(default=DEFAULT_HISTOGRAM_BINS, gt=0)
    critical_path_report_limit: int = Field(
        default=DEFAULT_CRITICAL_PATH_REPORT_LIMIT,
        gt=0,
    )


class EstimateRangeConfig(BaseModel):
    """Range configuration for a symbolic estimate."""

    min: float = Field(gt=0)
    most_likely: float = Field(gt=0)
    max: float = Field(gt=0)


class TShirtSizeConfig(EstimateRangeConfig):
    """T-shirt size estimate configuration."""


class StoryPointConfig(EstimateRangeConfig):
    """Story Point estimate configuration."""


class Config(BaseModel):
    """Complete application configuration."""

    uncertainty_factors: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    t_shirt_sizes: Dict[str, TShirtSizeConfig] = Field(default_factory=dict)
    story_points: Dict[int, StoryPointConfig] = Field(default_factory=dict)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @classmethod
    def load_from_file(cls, config_path: Path | str) -> "Config":
        """Load configuration from YAML file.

        Args:
            config_path: Path to configuration file

        Returns:
            Config object
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        merged_data = _merge_nested_dicts(_build_default_config_data(), data)
        return cls.model_validate(merged_data)

    @classmethod
    def get_default(cls) -> "Config":
        """Get default configuration with standard uncertainty factors."""
        return cls.model_validate(_build_default_config_data())

    def get_uncertainty_multiplier(self, factor_name: str, level: str) -> float:
        """Get uncertainty multiplier for a given factor and level.

        Args:
            factor_name: Name of uncertainty factor
            level: Level of the factor (e.g., 'high', 'medium', 'low')

        Returns:
            Multiplier value
        """
        if factor_name not in self.uncertainty_factors:
            return 1.0

        factor_config = self.uncertainty_factors[factor_name]
        return factor_config.get(level, 1.0)

    def get_t_shirt_size(self, size: str) -> Optional[TShirtSizeConfig]:
        """Get T-shirt size configuration.

        Args:
            size: T-shirt size (e.g., 'XS', 'S', 'M', 'L', 'XL', 'XXL')

        Returns:
            TShirtSizeConfig object or None if not found
        """
        return self.t_shirt_sizes.get(size)

    def get_story_point(self, points: int) -> Optional[StoryPointConfig]:
        """Get Story Point configuration.

        Args:
            points: Story Point value (for example 1, 2, 3, 5, 8, 13, 21)

        Returns:
            StoryPointConfig object or None if not found
        """
        return self.story_points.get(points)

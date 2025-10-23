"""Configuration management for uncertainty factors and simulation settings."""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field


class UncertaintyFactorConfig(BaseModel):
    """Configuration for a single uncertainty factor."""

    high: float = Field(default=1.0)
    medium: float = Field(default=1.0)
    low: float = Field(default=1.0)


class SimulationConfig(BaseModel):
    """Simulation settings."""

    default_iterations: int = Field(default=10000, gt=0)
    random_seed: Optional[int] = None


class OutputConfig(BaseModel):
    """Output settings."""

    formats: list[str] = Field(default_factory=lambda: ["json", "csv", "html"])
    include_histogram: bool = True
    histogram_bins: int = Field(default=50, gt=0)


class TShirtSizeConfig(BaseModel):
    """T-shirt size estimate configuration."""

    min: float = Field(gt=0)
    most_likely: float = Field(gt=0)
    max: float = Field(gt=0)


class Config(BaseModel):
    """Complete application configuration."""

    uncertainty_factors: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    t_shirt_sizes: Dict[str, TShirtSizeConfig] = Field(default_factory=dict)
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
            data = yaml.safe_load(f)

        return cls(**data)

    @classmethod
    def get_default(cls) -> "Config":
        """Get default configuration with standard uncertainty factors."""
        return cls(
            uncertainty_factors={
                "team_experience": {"high": 0.90, "medium": 1.0, "low": 1.30},
                "requirements_maturity": {"high": 1.0, "medium": 1.15, "low": 1.40},
                "technical_complexity": {"low": 1.0, "medium": 1.20, "high": 1.50},
                "team_distribution": {"colocated": 1.0, "distributed": 1.25},
                "integration_complexity": {"low": 1.0, "medium": 1.15, "high": 1.35},
            },
            t_shirt_sizes={
                "XS": TShirtSizeConfig(min=0.5, most_likely=1, max=2),
                "S": TShirtSizeConfig(min=1, most_likely=2, max=4),
                "M": TShirtSizeConfig(min=3, most_likely=5, max=8),
                "L": TShirtSizeConfig(min=5, most_likely=8, max=13),
                "XL": TShirtSizeConfig(min=8, most_likely=13, max=21),
                "XXL": TShirtSizeConfig(min=13, most_likely=21, max=34),
            },
        )

    def get_uncertainty_multiplier(
        self, factor_name: str, level: str
    ) -> float:
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

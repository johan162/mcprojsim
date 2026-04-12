"""Configuration management for uncertainty factors and simulation settings."""

from copy import deepcopy
from enum import Enum
from pathlib import Path
from statistics import NormalDist
from typing import Any, Dict, Literal, Optional, cast

import yaml
from pydantic import BaseModel, Field, field_validator


class EffortUnit(str, Enum):
    """Supported effort units."""

    HOURS = "hours"
    DAYS = "days"
    WEEKS = "weeks"


class ConstrainedSchedulingAssignmentMode(str, Enum):
    """Constrained scheduling dispatch policy."""

    GREEDY_SINGLE_PASS = "greedy_single_pass"
    CRITICALITY_TWO_PASS = "criticality_two_pass"


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
DEFAULT_CONFIDENCE_LEVELS = [10, 25, 50, 75, 80, 85, 90, 95, 99]
DEFAULT_SPRINT_PLANNING_CONFIDENCE_LEVEL = 0.80
DEFAULT_SPRINT_REMOVED_WORK_TREATMENT = "churn_only"
DEFAULT_SPRINT_VOLATILITY_DISRUPTION_PROBABILITY = 0.0
DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_LOW = 1.0
DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_EXPECTED = 1.0
DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_HIGH = 1.0
DEFAULT_SPRINT_SPILLOVER_MODEL = "table"
DEFAULT_SPRINT_SPILLOVER_SIZE_REFERENCE_POINTS = 5.0
DEFAULT_SPRINT_SPILLOVER_SIZE_BRACKETS: list[dict[str, float | None]] = [
    {"max_points": 2.0, "probability": 0.05},
    {"max_points": 5.0, "probability": 0.12},
    {"max_points": 8.0, "probability": 0.25},
    {"max_points": None, "probability": 0.40},
]
DEFAULT_SPRINT_SPILLOVER_CONSUMED_FRACTION_ALPHA = 3.25
DEFAULT_SPRINT_SPILLOVER_CONSUMED_FRACTION_BETA = 1.75
DEFAULT_SPRINT_SPILLOVER_LOGISTIC_SLOPE = 1.9
DEFAULT_SPRINT_SPILLOVER_LOGISTIC_INTERCEPT = -1.9924301646902063
DEFAULT_SPRINT_VELOCITY_MODEL = "empirical"
DEFAULT_SPRINT_SICKNESS_PROBABILITY_PER_PERSON_PER_WEEK = 0.058
DEFAULT_SPRINT_SICKNESS_DURATION_LOG_MU = 0.693
DEFAULT_SPRINT_SICKNESS_DURATION_LOG_SIGMA = 0.75
DEFAULT_CONSTRAINED_SCHEDULING_SICKNESS_PROB = 0.0
DEFAULT_CONSTRAINED_SCHEDULING_ASSIGNMENT_MODE = "greedy_single_pass"
DEFAULT_CONSTRAINED_SCHEDULING_PASS1_ITERATIONS = 1000
DEFAULT_PROBABILITY_RED_THRESHOLD = 0.50
DEFAULT_PROBABILITY_GREEN_THRESHOLD = 0.90
DEFAULT_LOGNORMAL_HIGH_PERCENTILE = 95
ALLOWED_LOGNORMAL_HIGH_PERCENTILES = [70, 75, 80, 85, 90, 95, 99]
DEFAULT_UNCERTAINTY_FACTOR_LEVELS = {
    "team_experience": "medium",
    "requirements_maturity": "high",
    "technical_complexity": "low",
    "team_distribution": "colocated",
    "integration_complexity": "low",
}
DEFAULT_UNCERTAINTY_FACTORS = {
    "team_experience": {"high": 0.90, "medium": 1.0, "low": 1.30},
    "requirements_maturity": {"high": 1.0, "medium": 1.15, "low": 1.40},
    "technical_complexity": {"low": 1.0, "medium": 1.20, "high": 1.50},
    "team_distribution": {"colocated": 1.0, "distributed": 1.25},
    "integration_complexity": {"low": 1.0, "medium": 1.15, "high": 1.35},
}
DEFAULT_T_SHIRT_SIZE_VALUES: dict[str, dict[str, dict[str, float]]] = {
    "story": {
        "XS": {"low": 3, "expected": 5, "high": 15},
        "S": {"low": 5, "expected": 16, "high": 40},
        "M": {"low": 40, "expected": 60, "high": 120},
        "L": {"low": 160, "expected": 240, "high": 500},
        "XL": {"low": 320, "expected": 400, "high": 750},
        "XXL": {"low": 400, "expected": 500, "high": 1200},
    },
    "bug": {
        "XS": {"low": 0.5, "expected": 1, "high": 4},
        "S": {"low": 1, "expected": 3, "high": 10},
        "M": {"low": 3, "expected": 8, "high": 24},
        "L": {"low": 8, "expected": 20, "high": 60},
        "XL": {"low": 20, "expected": 40, "high": 100},
        "XXL": {"low": 40, "expected": 80, "high": 200},
    },
    "epic": {
        "XS": {"low": 20, "expected": 40, "high": 60},
        "S": {"low": 60, "expected": 120, "high": 170},
        "M": {"low": 120, "expected": 240, "high": 400},
        "L": {"low": 290, "expected": 480, "high": 700},
        "XL": {"low": 600, "expected": 1000, "high": 1500},
        "XXL": {"low": 1200, "expected": 2000, "high": 3200},
    },
    "business": {
        "XS": {"low": 400, "expected": 800, "high": 2000},
        "S": {"low": 800, "expected": 2000, "high": 5000},
        "M": {"low": 2000, "expected": 4000, "high": 10000},
        "L": {"low": 4000, "expected": 8000, "high": 20000},
        "XL": {"low": 8000, "expected": 16000, "high": 40000},
        "XXL": {"low": 16000, "expected": 32000, "high": 80000},
    },
    "initiative": {
        "XS": {"low": 2000, "expected": 4000, "high": 10000},
        "S": {"low": 4000, "expected": 10000, "high": 25000},
        "M": {"low": 10000, "expected": 20000, "high": 50000},
        "L": {"low": 20000, "expected": 40000, "high": 100000},
        "XL": {"low": 40000, "expected": 80000, "high": 200000},
        "XXL": {"low": 80000, "expected": 160000, "high": 400000},
    },
}
DEFAULT_T_SHIRT_SIZE_DEFAULT_CATEGORY = "story"
T_SHIRT_SIZE_TOKEN_ALIASES = {
    "XS": "XS",
    "S": "S",
    "M": "M",
    "L": "L",
    "XL": "XL",
    "XXL": "XXL",
    "EXTRA_SMALL": "XS",
    "SMALL": "S",
    "MEDIUM": "M",
    "LARGE": "L",
    "EXTRA_LARGE": "XL",
    "EXTRA_EXTRA_LARGE": "XXL",
    "MED": "M",
    "LRG": "L",
    "XLRG": "XL",
    "XXLRG": "XXL",
    "EXTRA-SMALL": "XS",
    "EXTRA-LARGE": "XL",
    "EXTRA-EXTRA-LARGE": "XXL",
}

DEFAULT_STORY_POINT_VALUES = {
    1: {"low": 0.5, "expected": 1, "high": 3},
    2: {"low": 1, "expected": 2, "high": 4},
    3: {"low": 1.5, "expected": 3, "high": 5},
    5: {"low": 3, "expected": 5, "high": 8},
    8: {"low": 5, "expected": 8, "high": 15},
    13: {"low": 8, "expected": 13, "high": 21},
    21: {"low": 13, "expected": 21, "high": 34},
}


def _build_default_config_data() -> dict[str, Any]:
    """Build the default configuration payload."""
    return {
        "uncertainty_factors": deepcopy(DEFAULT_UNCERTAINTY_FACTORS),
        "t_shirt_sizes": {
            category: {
                size: deepcopy(values) for size, values in category_sizes.items()
            }
            for category, category_sizes in DEFAULT_T_SHIRT_SIZE_VALUES.items()
        },
        "t_shirt_size_default_category": DEFAULT_T_SHIRT_SIZE_DEFAULT_CATEGORY,
        "t_shirt_size_unit": EffortUnit.HOURS.value,
        "story_points": {
            points: deepcopy(values)
            for points, values in DEFAULT_STORY_POINT_VALUES.items()
        },
        "story_point_unit": EffortUnit.DAYS.value,
        "simulation": {
            "default_iterations": DEFAULT_SIMULATION_ITERATIONS,
            "random_seed": None,
            "max_stored_critical_paths": DEFAULT_MAX_STORED_CRITICAL_PATHS,
        },
        "lognormal": {
            "high_percentile": DEFAULT_LOGNORMAL_HIGH_PERCENTILE,
        },
        "output": {
            "formats": list(DEFAULT_OUTPUT_FORMATS),
            "include_histogram": True,
            "histogram_bins": DEFAULT_HISTOGRAM_BINS,
            "critical_path_report_limit": DEFAULT_CRITICAL_PATH_REPORT_LIMIT,
        },
        "staffing": {
            "min_individual_productivity": 0.25,
            "experience_profiles": {
                "senior": {
                    "productivity_factor": 1.0,
                    "communication_overhead": 0.04,
                },
                "mixed": {
                    "productivity_factor": 0.85,
                    "communication_overhead": 0.06,
                },
                "junior": {
                    "productivity_factor": 0.65,
                    "communication_overhead": 0.08,
                },
            },
        },
        "constrained_scheduling": {
            "sickness_prob": DEFAULT_CONSTRAINED_SCHEDULING_SICKNESS_PROB,
        },
        "sprint_defaults": {
            "planning_confidence_level": DEFAULT_SPRINT_PLANNING_CONFIDENCE_LEVEL,
            "removed_work_treatment": DEFAULT_SPRINT_REMOVED_WORK_TREATMENT,
            "velocity_model": DEFAULT_SPRINT_VELOCITY_MODEL,
            "volatility_disruption_probability": DEFAULT_SPRINT_VOLATILITY_DISRUPTION_PROBABILITY,
            "volatility_disruption_multiplier_low": DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_LOW,
            "volatility_disruption_multiplier_expected": DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_EXPECTED,
            "volatility_disruption_multiplier_high": DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_HIGH,
            "spillover_model": DEFAULT_SPRINT_SPILLOVER_MODEL,
            "spillover_size_reference_points": DEFAULT_SPRINT_SPILLOVER_SIZE_REFERENCE_POINTS,
            "spillover_size_brackets": deepcopy(DEFAULT_SPRINT_SPILLOVER_SIZE_BRACKETS),
            "spillover_consumed_fraction_alpha": DEFAULT_SPRINT_SPILLOVER_CONSUMED_FRACTION_ALPHA,
            "spillover_consumed_fraction_beta": DEFAULT_SPRINT_SPILLOVER_CONSUMED_FRACTION_BETA,
            "spillover_logistic_slope": DEFAULT_SPRINT_SPILLOVER_LOGISTIC_SLOPE,
            "spillover_logistic_intercept": DEFAULT_SPRINT_SPILLOVER_LOGISTIC_INTERCEPT,
            "sickness": {
                "enabled": False,
                "probability_per_person_per_week": DEFAULT_SPRINT_SICKNESS_PROBABILITY_PER_PERSON_PER_WEEK,
                "duration_log_mu": DEFAULT_SPRINT_SICKNESS_DURATION_LOG_MU,
                "duration_log_sigma": DEFAULT_SPRINT_SICKNESS_DURATION_LOG_SIGMA,
            },
        },
    }


def _merge_nested_dicts(
    base: dict[str, Any], overrides: dict[str, Any]
) -> dict[str, Any]:
    """Recursively merge dictionaries, preserving defaults."""
    merged = deepcopy(base)

    for key, value in overrides.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_nested_dicts(merged[key], value)
        else:
            merged[key] = value

    return merged


def _is_tshirt_estimate_leaf(candidate: Any) -> bool:
    if not isinstance(candidate, dict):
        return False
    keys = set(candidate.keys())
    return keys == {"low", "expected", "high"}


def _normalize_tshirt_size_token(size_token: str) -> Optional[str]:
    normalized = size_token.strip().replace("-", "_").replace(" ", "_").upper()
    return T_SHIRT_SIZE_TOKEN_ALIASES.get(normalized)


def _normalize_t_shirt_size_map(
    categories: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    normalized_categories: dict[str, dict[str, Any]] = {}
    for raw_category, raw_sizes in categories.items():
        category_name = str(raw_category).strip().lower()
        if not category_name:
            raise ValueError("Invalid empty t_shirt_size category name in config")
        if not isinstance(raw_sizes, dict):
            raise ValueError(
                "Invalid t_shirt_sizes config shape. Each category must map to a "
                "dictionary of size estimates."
            )
        normalized_sizes: dict[str, Any] = {}
        for raw_size, estimate in raw_sizes.items():
            canonical_size = _normalize_tshirt_size_token(str(raw_size))
            if canonical_size is None:
                raise ValueError(
                    f"Invalid t_shirt_size token '{raw_size}' in category "
                    f"'{category_name}'. Use one of XS, S, M, L, XL, XXL."
                )
            normalized_sizes[canonical_size] = estimate
        normalized_categories[category_name] = normalized_sizes
    return normalized_categories


def _normalize_t_shirt_config_input(data: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(data)
    canonical_key = "t_shirt_sizes"
    alias_key = "t_shirt_size_categories"

    has_canonical = canonical_key in normalized
    has_alias = alias_key in normalized

    if has_canonical and has_alias:
        raise ValueError(
            "Config cannot define both 't_shirt_sizes' and "
            "'t_shirt_size_categories'. Use only 't_shirt_sizes'."
        )

    if has_alias:
        normalized[canonical_key] = normalized.pop(alias_key)

    if canonical_key not in normalized:
        return normalized

    raw_sizes = normalized[canonical_key]
    if not isinstance(raw_sizes, dict):
        return normalized

    entries = list(raw_sizes.values())
    if len(entries) == 0:
        return normalized

    all_leaf_entries = all(_is_tshirt_estimate_leaf(entry) for entry in entries)
    all_nested_entries = all(isinstance(entry, dict) for entry in entries) and all(
        all(_is_tshirt_estimate_leaf(leaf) for leaf in entry.values())
        for entry in entries
    )

    if all_leaf_entries:
        raw_default_category = normalized.get(
            "t_shirt_size_default_category", DEFAULT_T_SHIRT_SIZE_DEFAULT_CATEGORY
        )
        default_category = str(raw_default_category).strip().lower()
        if not default_category:
            default_category = DEFAULT_T_SHIRT_SIZE_DEFAULT_CATEGORY
        normalized[canonical_key] = _normalize_t_shirt_size_map(
            {default_category: raw_sizes}
        )
        return normalized

    if all_nested_entries:
        normalized[canonical_key] = _normalize_t_shirt_size_map(raw_sizes)
        return normalized

    raise ValueError(
        "Invalid t_shirt_sizes config shape. Use either a flat size map or a "
        "nested '<category>: <size>: {low, expected, high}' map."
    )


class UncertaintyFactorConfig(BaseModel):
    """Configuration for a single uncertainty factor."""

    model_config = {"extra": "forbid"}

    high: float = Field(default=1.0)
    medium: float = Field(default=1.0)
    low: float = Field(default=1.0)


class SimulationConfig(BaseModel):
    """Simulation settings."""

    model_config = {"extra": "forbid"}

    default_iterations: int = Field(default=DEFAULT_SIMULATION_ITERATIONS, gt=0)
    random_seed: Optional[int] = None
    max_stored_critical_paths: int = Field(
        default=DEFAULT_MAX_STORED_CRITICAL_PATHS,
        gt=0,
    )


class LogNormalConfig(BaseModel):
    """Shifted log-normal interpretation settings."""

    model_config = {"extra": "forbid"}

    high_percentile: int = Field(default=DEFAULT_LOGNORMAL_HIGH_PERCENTILE)

    def model_post_init(self, __context: Any) -> None:
        if self.high_percentile not in ALLOWED_LOGNORMAL_HIGH_PERCENTILES:
            allowed = ", ".join(
                str(value) for value in ALLOWED_LOGNORMAL_HIGH_PERCENTILES
            )
            raise ValueError(
                "lognormal.high_percentile must be one of: "
                f"{allowed}; got {self.high_percentile}"
            )


class OutputConfig(BaseModel):
    """Output settings."""

    model_config = {"extra": "forbid"}

    formats: list[str] = Field(default_factory=lambda: list(DEFAULT_OUTPUT_FORMATS))
    include_histogram: bool = True
    histogram_bins: int = Field(default=DEFAULT_HISTOGRAM_BINS, gt=0)
    critical_path_report_limit: int = Field(
        default=DEFAULT_CRITICAL_PATH_REPORT_LIMIT,
        gt=0,
    )

    @field_validator("formats")
    @classmethod
    def validate_formats(cls, value: list[str]) -> list[str]:
        """Require non-empty, known output formats."""
        if not value:
            raise ValueError("output.formats must include at least one format")

        allowed = set(DEFAULT_OUTPUT_FORMATS)
        normalized: list[str] = []
        unknown: list[str] = []
        for item in value:
            fmt = item.strip().lower()
            if not fmt:
                raise ValueError("output.formats cannot contain empty values")
            if fmt not in allowed:
                unknown.append(fmt)
            normalized.append(fmt)

        if unknown:
            allowed_text = ", ".join(DEFAULT_OUTPUT_FORMATS)
            unknown_text = ", ".join(sorted(set(unknown)))
            raise ValueError(
                "output.formats contains unsupported value(s): "
                f"{unknown_text}. Supported values: {allowed_text}"
            )

        return normalized


class ExperienceProfileConfig(BaseModel):
    """Productivity and overhead parameters for an experience profile."""

    model_config = {"extra": "forbid"}

    productivity_factor: float = Field(default=1.0, gt=0)
    communication_overhead: float = Field(default=0.06, ge=0, le=1)


class StaffingConfig(BaseModel):
    """Staffing analysis settings."""

    model_config = {"extra": "forbid"}

    effort_percentile: Optional[int] = Field(
        default=None,
        ge=1,
        le=99,
        description=(
            "Percentile of the effort distribution to use as the basis for "
            "staffing calculations (e.g. 80 for P80). When None (the default), "
            "the mean effort and mean elapsed time are used instead."
        ),
    )
    min_individual_productivity: float = Field(
        default=0.25,
        gt=0,
        le=1,
        description=(
            "Floor for individual productivity after communication overhead. "
            "Prevents the model from predicting zero-productivity teams."
        ),
    )
    experience_profiles: Dict[str, ExperienceProfileConfig] = Field(
        default_factory=lambda: {
            "senior": ExperienceProfileConfig(
                productivity_factor=1.0,
                communication_overhead=0.04,
            ),
            "mixed": ExperienceProfileConfig(
                productivity_factor=0.85,
                communication_overhead=0.06,
            ),
            "junior": ExperienceProfileConfig(
                productivity_factor=0.65,
                communication_overhead=0.08,
            ),
        }
    )


class ConstrainedSchedulingConfig(BaseModel):
    """Defaults for resource-constrained scheduling behavior."""

    model_config = {"extra": "forbid"}

    sickness_prob: float = Field(
        default=DEFAULT_CONSTRAINED_SCHEDULING_SICKNESS_PROB,
        ge=0.0,
        le=1.0,
        description=(
            "Default per-resource sickness probability used by constrained "
            "scheduling when a resource does not specify sickness_prob in the "
            "project file."
        ),
    )
    assignment_mode: ConstrainedSchedulingAssignmentMode = Field(
        default=ConstrainedSchedulingAssignmentMode.GREEDY_SINGLE_PASS,
        description=(
            "Scheduling dispatch policy for constrained mode. "
            "'greedy_single_pass' uses deterministic ID-order greedy dispatch (default). "
            "'criticality_two_pass' runs a pass-1 baseline to rank tasks by criticality "
            "index and re-schedules in pass-2 with those ranks as priority."
        ),
    )
    pass1_iterations: int = Field(
        default=DEFAULT_CONSTRAINED_SCHEDULING_PASS1_ITERATIONS,
        gt=0,
        description=(
            "Number of pass-1 iterations used to compute criticality indices when "
            "assignment_mode is 'criticality_two_pass'. Capped to total simulation "
            "iterations if larger. Must be > 0."
        ),
    )


class SprintSicknessDefaultsConfig(BaseModel):
    """Company-wide defaults for sprint sickness modeling."""

    model_config = {"extra": "forbid"}

    enabled: bool = False
    probability_per_person_per_week: float = Field(
        default=DEFAULT_SPRINT_SICKNESS_PROBABILITY_PER_PERSON_PER_WEEK,
        gt=0.0,
        lt=1.0,
    )
    duration_log_mu: float = Field(default=DEFAULT_SPRINT_SICKNESS_DURATION_LOG_MU)
    duration_log_sigma: float = Field(
        default=DEFAULT_SPRINT_SICKNESS_DURATION_LOG_SIGMA,
        gt=0,
    )


class SprintDefaultsConfig(BaseModel):
    """Company-wide defaults for sprint-planning behavior."""

    model_config = {"extra": "forbid"}

    planning_confidence_level: float = Field(
        default=DEFAULT_SPRINT_PLANNING_CONFIDENCE_LEVEL,
        gt=0,
        lt=1,
    )
    removed_work_treatment: Literal["churn_only", "reduce_backlog"] = Field(
        default=cast(
            Literal["churn_only", "reduce_backlog"],
            DEFAULT_SPRINT_REMOVED_WORK_TREATMENT,
        )
    )
    velocity_model: Literal["empirical", "neg_binomial"] = Field(
        default=cast(
            Literal["empirical", "neg_binomial"],
            DEFAULT_SPRINT_VELOCITY_MODEL,
        )
    )
    volatility_disruption_probability: float = Field(
        default=DEFAULT_SPRINT_VOLATILITY_DISRUPTION_PROBABILITY,
        ge=0.0,
        le=1.0,
    )
    volatility_disruption_multiplier_low: float = Field(
        default=DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_LOW,
        ge=0.0,
    )
    volatility_disruption_multiplier_expected: float = Field(
        default=DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_EXPECTED,
        ge=0.0,
    )
    volatility_disruption_multiplier_high: float = Field(
        default=DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_HIGH,
        ge=0.0,
    )
    spillover_model: Literal["table", "logistic"] = Field(
        default=cast(
            Literal["table", "logistic"],
            DEFAULT_SPRINT_SPILLOVER_MODEL,
        )
    )
    spillover_size_reference_points: float = Field(
        default=DEFAULT_SPRINT_SPILLOVER_SIZE_REFERENCE_POINTS,
        gt=0,
    )
    spillover_size_brackets: list[dict[str, float | None]] = Field(
        default_factory=lambda: deepcopy(DEFAULT_SPRINT_SPILLOVER_SIZE_BRACKETS)
    )
    spillover_consumed_fraction_alpha: float = Field(
        default=DEFAULT_SPRINT_SPILLOVER_CONSUMED_FRACTION_ALPHA,
        gt=0,
    )
    spillover_consumed_fraction_beta: float = Field(
        default=DEFAULT_SPRINT_SPILLOVER_CONSUMED_FRACTION_BETA,
        gt=0,
    )
    spillover_logistic_slope: float = Field(
        default=DEFAULT_SPRINT_SPILLOVER_LOGISTIC_SLOPE,
        gt=0,
    )
    spillover_logistic_intercept: float = Field(
        default=DEFAULT_SPRINT_SPILLOVER_LOGISTIC_INTERCEPT,
    )
    sickness: SprintSicknessDefaultsConfig = Field(
        default_factory=SprintSicknessDefaultsConfig
    )


class CostConfig(BaseModel):
    """Configuration for monetary cost estimation."""

    model_config = {"extra": "forbid"}

    default_hourly_rate: Optional[float] = Field(
        default=None,
        ge=0,
        description="Default hourly rate when project does not specify one.",
    )
    overhead_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=3.0,
        description="Default fractional overhead markup on labor cost.",
    )
    currency: str = Field(
        default="EUR",
        description="Default currency code when project does not specify one.",
    )
    include_in_output: bool = Field(
        default=True,
        description="Whether to include cost sections in reports and console output when cost data exists.",
    )


class EstimateRangeConfig(BaseModel):
    """Range configuration for a symbolic estimate."""

    model_config = {"extra": "forbid"}

    low: float = Field(gt=0)
    expected: float = Field(gt=0)
    high: float = Field(gt=0)


class TShirtSizeConfig(EstimateRangeConfig):
    """T-shirt size estimate configuration."""


class StoryPointConfig(EstimateRangeConfig):
    """Story Point estimate configuration."""


class Config(BaseModel):
    """Complete application configuration."""

    model_config = {"extra": "forbid"}

    uncertainty_factors: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    t_shirt_sizes: Dict[str, Dict[str, TShirtSizeConfig]] = Field(default_factory=dict)
    t_shirt_size_default_category: str = Field(
        default=DEFAULT_T_SHIRT_SIZE_DEFAULT_CATEGORY
    )
    t_shirt_size_unit: EffortUnit = Field(default=EffortUnit.HOURS)
    story_points: Dict[int, StoryPointConfig] = Field(default_factory=dict)
    story_point_unit: EffortUnit = Field(default=EffortUnit.DAYS)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    lognormal: LogNormalConfig = Field(default_factory=LogNormalConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    staffing: StaffingConfig = Field(default_factory=StaffingConfig)
    constrained_scheduling: ConstrainedSchedulingConfig = Field(
        default_factory=ConstrainedSchedulingConfig
    )
    sprint_defaults: SprintDefaultsConfig = Field(default_factory=SprintDefaultsConfig)
    cost: CostConfig = Field(default_factory=CostConfig)

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

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        if not isinstance(data, dict):
            raise ValueError(
                "Invalid configuration: top-level content must be a mapping/object"
            )

        normalized_data = _normalize_t_shirt_config_input(data)
        merged_data = _merge_nested_dicts(_build_default_config_data(), normalized_data)
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
            size: T-shirt size token (for example 'M' or 'epic.M')

        Returns:
            TShirtSizeConfig object or None if not found or invalid
        """
        try:
            return self.resolve_t_shirt_size(size)
        except ValueError:
            return None

    def get_t_shirt_categories(self) -> list[str]:
        """Return configured T-shirt categories in declaration order."""
        return list(self.t_shirt_sizes.keys())

    def resolve_t_shirt_size(self, size: str) -> TShirtSizeConfig:
        """Resolve a T-shirt size token to a concrete estimate range."""
        raw_size = size.strip()
        if not raw_size:
            raise ValueError(
                "Invalid t_shirt_size format ''. Use '<category>.<size>' or '<size>'."
            )

        if raw_size.count(".") > 1:
            raise ValueError(
                f"Invalid t_shirt_size format '{size}'. Use '<category>.<size>' or '<size>'."
            )

        category_name: str
        size_token: str
        if "." in raw_size:
            category_part, size_part = raw_size.split(".")
            if not category_part or not size_part:
                raise ValueError(
                    f"Invalid t_shirt_size format '{size}'. Use '<category>.<size>' or '<size>'."
                )
            category_name = category_part.strip().lower()
            size_token = size_part.strip()
        else:
            category_name = self.t_shirt_size_default_category.strip().lower()
            size_token = raw_size

        if category_name not in self.t_shirt_sizes:
            valid_categories = ", ".join(self.get_t_shirt_categories())
            raise ValueError(
                f"Invalid t_shirt_size category '{category_name}' in '{size}'. "
                f"Valid categories: {valid_categories}"
            )

        canonical_size = _normalize_tshirt_size_token(size_token)
        if canonical_size is None:
            normalized_candidate = (
                size_token.strip().replace("-", "_").replace(" ", "_").upper()
            )
            if normalized_candidate and normalized_candidate.replace("_", "").isalpha():
                valid_sizes = ", ".join(self.t_shirt_sizes[category_name].keys())
                raise ValueError(
                    f"Invalid t_shirt_size '{size}'. Valid sizes for category "
                    f"'{category_name}': {valid_sizes}"
                )
            raise ValueError(
                f"Invalid t_shirt_size format '{size}'. Use '<category>.<size>' or '<size>'."
            )

        category_sizes = self.t_shirt_sizes[category_name]
        resolved = category_sizes.get(canonical_size)
        if resolved is None:
            valid_sizes = ", ".join(category_sizes.keys())
            raise ValueError(
                f"Invalid t_shirt_size '{size}'. Valid sizes for category "
                f"'{category_name}': {valid_sizes}"
            )
        return resolved

    def get_story_point(self, points: int) -> Optional[StoryPointConfig]:
        """Get Story Point configuration.

        Args:
            points: Story Point value (for example 1, 2, 3, 5, 8, 13, 21)

        Returns:
            StoryPointConfig object or None if not found
        """
        return self.story_points.get(points)

    def get_lognormal_high_z_value(self) -> float:
        """Return the z-score for the configured shifted-lognormal high percentile."""
        return NormalDist().inv_cdf(self.lognormal.high_percentile / 100.0)

"""Tests for configuration."""

import pytest
import yaml

from mcprojsim.config import (
    Config,
    DEFAULT_CONFIDENCE_LEVELS,
    OutputConfig,
    SimulationConfig,
)


class TestConfig:
    """Tests for configuration."""

    def test_default_config(self):
        """Test default configuration."""
        config = Config.get_default()

        assert "team_experience" in config.uncertainty_factors
        assert "requirements_maturity" in config.uncertainty_factors
        assert "technical_complexity" in config.uncertainty_factors
        assert config.simulation.default_iterations == 10000
        assert config.lognormal.high_percentile == 95
        assert config.sprint_defaults.velocity_model == "empirical"
        assert config.constrained_scheduling.sickness_prob == 0.0
        assert config.sprint_defaults.sickness.probability_per_person_per_week == 0.058

    def test_default_confidence_levels_include_p10_p25_and_p99(self):
        """Test the shared default confidence levels include P10, P25, and P99."""
        assert DEFAULT_CONFIDENCE_LEVELS == [10, 25, 50, 75, 80, 85, 90, 95, 99]

    def test_get_uncertainty_multiplier(self):
        """Test getting uncertainty multiplier."""
        config = Config.get_default()

        multiplier = config.get_uncertainty_multiplier("team_experience", "high")
        assert multiplier == 0.9

        multiplier = config.get_uncertainty_multiplier("team_experience", "medium")
        assert multiplier == 1.0

        multiplier = config.get_uncertainty_multiplier("team_experience", "low")
        assert multiplier == 1.3

    def test_get_uncertainty_multiplier_unknown_factor(self):
        """Test getting multiplier for unknown factor."""
        config = Config.get_default()

        multiplier = config.get_uncertainty_multiplier("unknown_factor", "high")
        assert multiplier == 1.0

    def test_get_uncertainty_multiplier_unknown_level(self):
        """Test getting multiplier for unknown level."""
        config = Config.get_default()

        multiplier = config.get_uncertainty_multiplier("team_experience", "unknown")
        assert multiplier == 1.0

    def test_load_from_file(self, tmp_path):
        """Test loading from file."""
        config_data = {
            "uncertainty_factors": {
                "team_experience": {"high": 0.8, "medium": 1.0, "low": 1.5}
            },
            "simulation": {"default_iterations": 5000, "random_seed": 42},
            "output": {
                "formats": ["json"],
                "include_histogram": False,
                "histogram_bins": 30,
            },
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config.load_from_file(config_file)
        assert config.simulation.default_iterations == 5000
        assert config.simulation.random_seed == 42
        assert config.simulation.max_stored_critical_paths == 20
        assert config.get_t_shirt_size("M") is not None
        assert config.get_story_point(5) is not None

    def test_load_from_file_overrides_sprint_defaults(self, tmp_path):
        """Sprint defaults should load and merge from configuration files."""
        config_data = {
            "sprint_defaults": {
                "velocity_model": "neg_binomial",
                "planning_confidence_level": 0.9,
                "sickness": {
                    "enabled": True,
                    "probability_per_person_per_week": 0.08,
                },
            }
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config.load_from_file(config_file)
        assert config.sprint_defaults.velocity_model == "neg_binomial"
        assert config.sprint_defaults.planning_confidence_level == 0.9
        assert config.sprint_defaults.sickness.enabled is True
        assert config.sprint_defaults.sickness.probability_per_person_per_week == 0.08

    def test_load_from_file_overrides_constrained_scheduling_defaults(self, tmp_path):
        """Constrained scheduling defaults should load from configuration file."""
        config_data = {
            "constrained_scheduling": {
                "sickness_prob": 0.03,
            }
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config.load_from_file(config_file)
        assert config.constrained_scheduling.sickness_prob == pytest.approx(0.03)

    def test_load_from_file_merges_symbolic_defaults(self, tmp_path):
        """Test loading config preserves built-in symbolic defaults not overridden."""
        config_data = {
            "story_points": {5: {"low": 4, "expected": 6, "high": 9}},
            "t_shirt_sizes": {"M": {"low": 4, "expected": 6, "high": 9}},
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config.load_from_file(config_file)

        assert config.get_story_point(5) is not None
        sp5 = config.get_story_point(5)
        assert sp5 is not None
        assert sp5.expected == 6
        assert config.get_story_point(8) is not None
        assert config.get_t_shirt_size("M") is not None
        ts_m = config.get_t_shirt_size("M")
        assert ts_m is not None
        assert ts_m.expected == 6
        assert config.get_t_shirt_size("XL") is not None

    def test_load_from_nonexistent_file(self):
        """Test loading from non-existent file."""
        with pytest.raises(FileNotFoundError):
            Config.load_from_file("nonexistent.yaml")

    def test_load_from_file_overrides_lognormal_percentile(self, tmp_path):
        """Test loading config supports a custom shifted-lognormal percentile."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("lognormal:\n  high_percentile: 90\n")

        config = Config.load_from_file(config_file)
        assert config.lognormal.high_percentile == 90

    def test_invalid_lognormal_percentile_rejected(self, tmp_path):
        """Only the documented percentile choices should be accepted."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("lognormal:\n  high_percentile: 92\n")

        with pytest.raises(ValueError, match="must be one of"):
            Config.load_from_file(config_file)

    def test_config_load_rejects_non_mapping_root(self, tmp_path):
        """Top-level config must be a mapping/object, not a list or scalar."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("- not\n- a\n- mapping\n")

        with pytest.raises(ValueError, match="top-level content must be a mapping"):
            Config.load_from_file(config_file)

    def test_config_load_rejects_unsupported_output_formats(self, tmp_path):
        """output.formats should fail fast for unknown format values."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "output": {
                        "formats": ["json", "xml"],
                    }
                }
            )
        )

        with pytest.raises(ValueError, match="output.formats contains unsupported"):
            Config.load_from_file(config_file)

    def test_config_load_rejects_unknown_top_level_field(self, tmp_path):
        """Unknown top-level config keys should be rejected to catch typos early."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "simluation": {"default_iterations": 5000},
                }
            )
        )

        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            Config.load_from_file(config_file)

    def test_config_load_rejects_unknown_nested_simulation_field(self, tmp_path):
        """Unknown keys inside simulation config should fail validation."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "simulation": {
                        "default_iterations": 5000,
                        "unknown_setting": True,
                    }
                }
            )
        )

        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            Config.load_from_file(config_file)

    def test_config_load_rejects_unknown_nested_output_field(self, tmp_path):
        """Unknown keys inside output config should fail validation."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "output": {
                        "formats": ["json"],
                        "legacy_mode": True,
                    }
                }
            )
        )

        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            Config.load_from_file(config_file)

    def test_config_load_rejects_unknown_nested_sprint_defaults_field(self, tmp_path):
        """Unknown keys in sprint_defaults nested sections should fail validation."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "sprint_defaults": {
                        "planning_confidence_level": 0.8,
                        "sickness": {
                            "enabled": True,
                            "unexpected": 123,
                        },
                    }
                }
            )
        )

        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            Config.load_from_file(config_file)


class TestSimulationConfig:
    """Tests for simulation configuration."""

    def test_simulation_config_defaults(self):
        """Test simulation config defaults."""
        config = SimulationConfig()
        assert config.default_iterations == 10000
        assert config.random_seed is None
        assert config.max_stored_critical_paths == 20


class TestTShirtSizes:
    """Tests for T-shirt size configuration."""

    def test_default_tshirt_sizes(self):
        """Test default T-shirt categories and sizes are defined."""
        config = Config.get_default()

        assert config.get_t_shirt_categories() == [
            "story",
            "bug",
            "epic",
            "business",
            "initiative",
        ]
        assert config.t_shirt_size_default_category == "epic"

        for size in ("XS", "S", "M", "L", "XL", "XXL"):
            assert size in config.t_shirt_sizes["story"]
            assert size in config.t_shirt_sizes["bug"]

    def test_tshirt_size_values(self):
        """Test T-shirt size values are correctly configured."""
        config = Config.get_default()

        xs = config.get_t_shirt_size("XS")
        assert xs is not None
        assert xs.low == 20
        assert xs.expected == 40
        assert xs.high == 60

        m = config.get_t_shirt_size("M")
        assert m is not None
        assert m.low == 120
        assert m.expected == 240
        assert m.high == 400

        bug_m = config.get_t_shirt_size("bug.M")
        assert bug_m is not None
        assert bug_m.low == 3
        assert bug_m.expected == 8
        assert bug_m.high == 24

        xxl = config.get_t_shirt_size("XXL")
        assert xxl is not None
        assert xxl.low == 1200
        assert xxl.expected == 2000
        assert xxl.high == 3200

    def test_tshirt_long_form_aliases(self):
        """Test long-form T-shirt values resolve to canonical abbreviations."""
        config = Config.get_default()

        medium = config.get_t_shirt_size("Medium")
        assert medium is not None
        assert medium.expected == 240

        qualified = config.get_t_shirt_size("Epic.Large")
        assert qualified is not None
        assert qualified.expected == 480

    def test_get_unknown_tshirt_size_returns_none(self):
        """Test compatibility helper returns None for unknown values."""
        config = Config.get_default()

        assert config.get_t_shirt_size("XXXL") is None
        assert config.get_t_shirt_size("foo.M") is None

    def test_resolve_unknown_category_raises_clear_error(self):
        """Unknown category errors should include valid categories."""
        config = Config.get_default()

        with pytest.raises(ValueError, match="Valid categories"):
            config.resolve_t_shirt_size("foo.M")

    def test_resolve_unknown_size_raises_clear_error(self):
        """Unknown size errors should include valid sizes for category."""
        config = Config.get_default()

        with pytest.raises(ValueError, match="Valid sizes for category 'epic'"):
            config.resolve_t_shirt_size("epic.HUGE")

    def test_resolve_invalid_dotted_format_raises(self):
        """Invalid dotted formats should provide the contract message."""
        config = Config.get_default()

        with pytest.raises(ValueError, match="Use '<category>.<size>' or '<size>'"):
            config.resolve_t_shirt_size("epic.sub.M")


class TestTShirtConfigCompatibility:
    """Tests for compatibility and migration behaviors."""

    def test_old_flat_tshirt_map_migrates_to_default_category(self, tmp_path):
        """Old flat t_shirt_sizes map should be migrated to the default category."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "t_shirt_size_default_category": "bug",
                    "t_shirt_sizes": {
                        "M": {"low": 2, "expected": 4, "high": 8},
                    },
                }
            )
        )

        config = Config.load_from_file(config_file)

        bug_m = config.get_t_shirt_size("M")
        assert bug_m is not None
        assert bug_m.expected == 4
        story_m = config.get_t_shirt_size("story.M")
        assert story_m is not None
        assert story_m.expected == 60

    def test_alias_key_is_accepted_and_normalized(self, tmp_path):
        """Transitional alias key should load as canonical t_shirt_sizes."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "t_shirt_size_categories": {
                        "initiative": {
                            "M": {"low": 9000, "expected": 10000, "high": 12000}
                        }
                    },
                    "t_shirt_size_default_category": "initiative",
                }
            )
        )

        config = Config.load_from_file(config_file)

        assert "initiative" in config.t_shirt_sizes
        resolved = config.get_t_shirt_size("M")
        assert resolved is not None
        assert resolved.expected == 10000

    def test_conflicting_canonical_and_alias_keys_fail(self, tmp_path):
        """Config should reject both canonical and alias keys together."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "t_shirt_sizes": {
                        "story": {"M": {"low": 10, "expected": 20, "high": 30}}
                    },
                    "t_shirt_size_categories": {
                        "bug": {"M": {"low": 1, "expected": 2, "high": 3}}
                    },
                }
            )
        )

        with pytest.raises(
            ValueError,
            match="cannot define both 't_shirt_sizes' and 't_shirt_size_categories'",
        ):
            Config.load_from_file(config_file)

    def test_mixed_flat_and_nested_shape_fails(self, tmp_path):
        """Config should reject mixed flat and nested structures."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "t_shirt_sizes": {
                        "M": {"low": 40, "expected": 60, "high": 120},
                        "story": {"L": {"low": 160, "expected": 240, "high": 500}},
                    }
                }
            )
        )

        with pytest.raises(ValueError, match="Invalid t_shirt_sizes config shape"):
            Config.load_from_file(config_file)


class TestStoryPoints:
    """Tests for Story Point configuration."""

    def test_default_story_points(self):
        """Test default Story Point mappings are defined."""
        config = Config.get_default()

        for value in (1, 2, 3, 5, 8, 13, 21):
            assert config.get_story_point(value) is not None

    def test_story_point_values(self):
        """Test Story Point ranges are correctly configured."""
        config = Config.get_default()

        sp1 = config.get_story_point(1)
        assert sp1 is not None
        assert sp1.low == 0.5
        assert sp1.expected == 1
        assert sp1.high == 3

        sp8 = config.get_story_point(8)
        assert sp8 is not None
        assert sp8.low == 5
        assert sp8.expected == 8
        assert sp8.high == 15

        sp21 = config.get_story_point(21)
        assert sp21 is not None
        assert sp21.low == 13
        assert sp21.expected == 21
        assert sp21.high == 34

    def test_get_unknown_story_point(self):
        """Test getting unknown Story Point value returns None."""
        config = Config.get_default()

        assert config.get_story_point(34) is None


class TestOutputConfig:
    """Tests for output configuration."""

    def test_output_config_defaults(self):
        """Test output config defaults."""
        config = OutputConfig()
        assert "json" in config.formats
        assert "csv" in config.formats
        assert "html" in config.formats
        assert config.include_histogram is True
        assert config.histogram_bins == 50
        assert config.critical_path_report_limit == 2

    def test_output_config_custom_critical_path_report_limit(self):
        """Test custom critical path report limit."""
        config = OutputConfig(critical_path_report_limit=4)
        assert config.critical_path_report_limit == 4

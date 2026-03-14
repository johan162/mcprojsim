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

    def test_default_confidence_levels_include_p25_and_p99(self):
        """Test the shared default confidence levels include P25 and P99."""
        assert DEFAULT_CONFIDENCE_LEVELS == [25, 50, 75, 80, 85, 90, 95, 99]

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

    def test_load_from_file_merges_symbolic_defaults(self, tmp_path):
        """Test loading config preserves built-in symbolic defaults not overridden."""
        config_data = {
            "story_points": {5: {"min": 4, "most_likely": 6, "max": 9}},
            "t_shirt_sizes": {"M": {"min": 4, "most_likely": 6, "max": 9}},
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config.load_from_file(config_file)

        assert config.get_story_point(5) is not None
        sp5 = config.get_story_point(5)
        assert sp5 is not None
        assert sp5.most_likely == 6
        assert config.get_story_point(8) is not None
        assert config.get_t_shirt_size("M") is not None
        ts_m = config.get_t_shirt_size("M")
        assert ts_m is not None
        assert ts_m.most_likely == 6
        assert config.get_t_shirt_size("XL") is not None

    def test_load_from_nonexistent_file(self):
        """Test loading from non-existent file."""
        with pytest.raises(FileNotFoundError):
            Config.load_from_file("nonexistent.yaml")


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
        """Test default T-shirt sizes are defined."""
        config = Config.get_default()

        assert "XS" in config.t_shirt_sizes
        assert "S" in config.t_shirt_sizes
        assert "M" in config.t_shirt_sizes
        assert "L" in config.t_shirt_sizes
        assert "XL" in config.t_shirt_sizes
        assert "XXL" in config.t_shirt_sizes

    def test_tshirt_size_values(self):
        """Test T-shirt size values are correctly configured."""
        config = Config.get_default()

        # Test a few sizes
        xs = config.get_t_shirt_size("XS")
        assert xs is not None
        assert xs.min == 3
        assert xs.most_likely == 5
        assert xs.max == 15

        m = config.get_t_shirt_size("M")
        assert m is not None
        assert m.min == 40
        assert m.most_likely == 60
        assert m.max == 120

        xxl = config.get_t_shirt_size("XXL")
        assert xxl is not None
        assert xxl.min == 400
        assert xxl.most_likely == 500
        assert xxl.max == 1200

    def test_get_unknown_tshirt_size(self):
        """Test getting unknown T-shirt size returns None."""
        config = Config.get_default()

        size = config.get_t_shirt_size("XXXL")
        assert size is None


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
        assert sp1.min == 0.5
        assert sp1.most_likely == 1
        assert sp1.max == 3

        sp8 = config.get_story_point(8)
        assert sp8 is not None
        assert sp8.min == 5
        assert sp8.most_likely == 8
        assert sp8.max == 15

        sp21 = config.get_story_point(21)
        assert sp21 is not None
        assert sp21.min == 13
        assert sp21.most_likely == 21
        assert sp21.max == 34

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

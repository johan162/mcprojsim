"""Tests for configuration."""

import pytest
import yaml

from mcprojsim.config import Config, SimulationConfig, OutputConfig


class TestConfig:
    """Tests for configuration."""

    def test_default_config(self):
        """Test default configuration."""
        config = Config.get_default()

        assert "team_experience" in config.uncertainty_factors
        assert "requirements_maturity" in config.uncertainty_factors
        assert "technical_complexity" in config.uncertainty_factors
        assert config.simulation.default_iterations == 10000

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
        assert xs.min == 0.5
        assert xs.most_likely == 1
        assert xs.max == 2

        m = config.get_t_shirt_size("M")
        assert m is not None
        assert m.min == 3
        assert m.most_likely == 5
        assert m.max == 8

        xxl = config.get_t_shirt_size("XXL")
        assert xxl is not None
        assert xxl.min == 13
        assert xxl.most_likely == 21
        assert xxl.max == 34

    def test_get_unknown_tshirt_size(self):
        """Test getting unknown T-shirt size returns None."""
        config = Config.get_default()

        size = config.get_t_shirt_size("XXXL")
        assert size is None


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

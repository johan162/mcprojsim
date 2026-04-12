"""Tests for exchange_rates.py — ExchangeRateProvider with 24-hour file cache."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import numpy as np
import pytest

import mcprojsim.exchange_rates as fx_module
from mcprojsim.exchange_rates import (
    CACHE_TTL_HOURS,
    ExchangeRateProvider,
)

# ---------------------------------------------------------------------------
# Autouse fixture: redirect cache to a temp dir for every test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect CACHE_FILE and CACHE_DIR to a per-test temp directory.

    This prevents tests from reading or writing the real ~/.mcprojsim/ cache
    and ensures each test starts with an empty cache.
    """
    tmp_cache_dir = tmp_path / "mcprojsim"
    tmp_cache_dir.mkdir()
    tmp_cache_file = tmp_cache_dir / "fx_rates_cache.json"
    monkeypatch.setattr(fx_module, "CACHE_DIR", tmp_cache_dir)
    monkeypatch.setattr(fx_module, "CACHE_FILE", tmp_cache_file)
    return tmp_cache_file


# ---------------------------------------------------------------------------
# TestAdjustedRateFormula
# ---------------------------------------------------------------------------


class TestAdjustedRateFormula:
    """Verify the adjusted-rate formula: (1 + conv + overhead) * official."""

    def test_design_example(self) -> None:
        """Design doc example: EUR→SEK, official=10.50, conv=0.02, overhead=0.05."""
        provider = ExchangeRateProvider(
            base_currency="EUR",
            fx_conversion_cost=0.02,
            fx_overhead_rate=0.05,
            manual_overrides={"SEK": 10.50},  # use override to avoid network
        )
        # Manual overrides bypass markup → adjusted == override
        # So test with patched _mem_cache instead
        provider._mem_cache["SEK"] = 10.50
        provider._fetched_at["SEK"] = datetime.now(timezone.utc)
        provider._rate_source["SEK"] = "test"
        adj = provider.get_adjusted_rate("SEK")
        assert adj is not None
        # For manual override the value is returned as-is
        assert adj == pytest.approx(10.50)

    def test_design_example_via_cache(self) -> None:
        """Same numbers but rate comes from mem-cache so markup IS applied."""
        provider = ExchangeRateProvider(
            base_currency="EUR",
            fx_conversion_cost=0.02,
            fx_overhead_rate=0.05,
        )
        provider._mem_cache["SEK"] = 10.50
        provider._fetched_at["SEK"] = datetime.now(timezone.utc)
        provider._rate_source["SEK"] = "test"
        adj = provider.get_adjusted_rate("SEK")
        assert adj is not None
        # (1 + 0.02 + 0.05) * 10.50 = 1.07 * 10.50 = 11.235
        assert adj == pytest.approx(11.235, rel=1e-9)

    def test_zero_markups(self) -> None:
        """With zero markups adjusted == official."""
        provider = ExchangeRateProvider(base_currency="EUR")
        provider._mem_cache["USD"] = 1.08
        provider._rate_source["USD"] = "test"
        adj = provider.get_adjusted_rate("USD")
        assert adj == pytest.approx(1.08)

    def test_manual_override_bypasses_markup(self) -> None:
        """Manual override rates are returned as-is, without conv/overhead markup."""
        provider = ExchangeRateProvider(
            base_currency="EUR",
            fx_conversion_cost=0.05,
            fx_overhead_rate=0.10,
            manual_overrides={"GBP": 0.85},
        )
        # Even though conv+overhead = 0.15, GBP override should be returned unchanged
        assert provider.get_adjusted_rate("GBP") == pytest.approx(0.85)

    def test_unavailable_returns_none(self) -> None:
        """Returns None when rate cannot be obtained and network is absent."""
        provider = ExchangeRateProvider(base_currency="EUR")
        with patch.object(provider, "_fetch_from_frankfurter", return_value={}):
            result = provider.get_adjusted_rate("XYZ")
        assert result is None


# ---------------------------------------------------------------------------
# TestConvertArray
# ---------------------------------------------------------------------------


class TestConvertArray:
    """Verify element-wise conversion of cost arrays."""

    def test_scales_correctly(self) -> None:
        provider = ExchangeRateProvider(base_currency="EUR")
        provider._mem_cache["SEK"] = 10.0
        provider._rate_source["SEK"] = "test"
        arr = np.array([1000.0, 2000.0, 3000.0])
        result = provider.convert_array(arr, "SEK")
        assert result is not None
        np.testing.assert_array_almost_equal(result, [10000.0, 20000.0, 30000.0])

    def test_returns_none_when_rate_unavailable(self) -> None:
        provider = ExchangeRateProvider(base_currency="EUR")
        with patch.object(provider, "_fetch_from_frankfurter", return_value={}):
            result = provider.convert_array(np.array([1.0, 2.0]), "XXX")
        assert result is None

    def test_applies_markup_to_array(self) -> None:
        provider = ExchangeRateProvider(
            base_currency="EUR", fx_conversion_cost=0.07, fx_overhead_rate=0.0
        )
        provider._mem_cache["USD"] = 1.0
        provider._rate_source["USD"] = "test"
        arr = np.array([100.0])
        result = provider.convert_array(arr, "USD")
        assert result is not None
        assert result[0] == pytest.approx(107.0)

    def test_manual_override_no_markup(self) -> None:
        provider = ExchangeRateProvider(
            base_currency="EUR",
            fx_conversion_cost=0.10,
            fx_overhead_rate=0.05,
            manual_overrides={"JPY": 160.0},
        )
        arr = np.array([1000.0])
        result = provider.convert_array(arr, "JPY")
        assert result is not None
        assert result[0] == pytest.approx(160_000.0)


# ---------------------------------------------------------------------------
# TestFileCache
# ---------------------------------------------------------------------------


class TestFileCache:
    """Tests for the 24-hour persistent file cache."""

    def test_cache_written_after_fetch(self, isolated_cache: Path) -> None:
        cache_file = isolated_cache
        provider = ExchangeRateProvider(base_currency="EUR")
        fetched = {"SEK": 10.50, "USD": 1.08}
        provider._save_disk_cache(fetched)

        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert "EUR" in data
        assert "SEK" in data["EUR"]
        assert data["EUR"]["SEK"]["rate"] == pytest.approx(10.50)
        assert "USD" in data["EUR"]

    def test_fresh_cache_used_on_reload(self, isolated_cache: Path) -> None:
        """A fresh cache entry (< 24h) is loaded into memory without an API call."""
        cache_file = isolated_cache
        now_str = datetime.now(timezone.utc).isoformat()
        cache_data: Dict[str, Any] = {
            "EUR": {
                "SEK": {"rate": 11.23, "fetched_at": now_str},
            }
        }
        cache_file.write_text(json.dumps(cache_data))

        provider = ExchangeRateProvider(base_currency="EUR")

        # Should be in _mem_cache from disk, no network call needed
        assert "SEK" in provider._mem_cache
        assert provider._mem_cache["SEK"] == pytest.approx(11.23)
        assert provider._rate_source["SEK"] == "disk_cache"

    def test_stale_cache_triggers_refetch(self, isolated_cache: Path) -> None:
        """A stale entry (> 24h) is NOT loaded and triggers a network fetch."""
        cache_file = isolated_cache
        old_time = (
            datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS + 1)
        ).isoformat()
        cache_data: Dict[str, Any] = {
            "EUR": {"SEK": {"rate": 9.99, "fetched_at": old_time}}
        }
        cache_file.write_text(json.dumps(cache_data))

        provider = ExchangeRateProvider(base_currency="EUR")

        # Stale entry must NOT be loaded
        assert "SEK" not in provider._mem_cache

    def test_fresh_cache_not_refetched(self, isolated_cache: Path) -> None:
        """When entry is fresh, fetch_rates does not call Frankfurter."""
        cache_file = isolated_cache
        now_str = datetime.now(timezone.utc).isoformat()
        cache_data: Dict[str, Any] = {
            "EUR": {"SEK": {"rate": 10.50, "fetched_at": now_str}}
        }
        cache_file.write_text(json.dumps(cache_data))

        provider = ExchangeRateProvider(base_currency="EUR")

        with patch.object(
            provider, "_fetch_from_frankfurter", return_value={}
        ) as mock_fetch:
            provider.fetch_rates(["SEK"])
            mock_fetch.assert_not_called()

    def test_corrupt_cache_silently_ignored(self, isolated_cache: Path) -> None:
        """Corrupt JSON in cache file does not raise — provider starts clean."""
        isolated_cache.write_text("{ this is not valid JSON !!!")

        provider = ExchangeRateProvider(base_currency="EUR")

        assert provider._mem_cache == {}

    def test_missing_cache_dir_created(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """~/.mcprojsim/ is created if it does not exist."""
        nested_dir = tmp_path / "deep" / "nested"
        nested_cache_file = nested_dir / "fx_rates_cache.json"
        assert not nested_dir.exists()

        monkeypatch.setattr(fx_module, "CACHE_DIR", nested_dir)
        monkeypatch.setattr(fx_module, "CACHE_FILE", nested_cache_file)

        provider = ExchangeRateProvider(base_currency="EUR")
        provider._save_disk_cache({"USD": 1.05})

        assert nested_dir.exists()
        assert nested_cache_file.exists()

    def test_multiple_base_currencies_coexist(self, isolated_cache: Path) -> None:
        """Cache entries for different base currencies are preserved."""
        cache_file = isolated_cache
        now_str = datetime.now(timezone.utc).isoformat()
        existing: Dict[str, Any] = {
            "USD": {"SEK": {"rate": 9.80, "fetched_at": now_str}}
        }
        cache_file.write_text(json.dumps(existing))

        provider = ExchangeRateProvider(base_currency="EUR")
        provider._save_disk_cache({"SEK": 10.50})

        data = json.loads(cache_file.read_text())
        # Both base currencies must be present
        assert "EUR" in data
        assert "USD" in data
        assert data["USD"]["SEK"]["rate"] == pytest.approx(9.80)
        assert data["EUR"]["SEK"]["rate"] == pytest.approx(10.50)

    def test_disk_io_error_silently_ignored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Write failure (e.g. permission denied) is silently swallowed."""
        read_only_file = tmp_path / "ro_cache.json"
        read_only_file.write_text("{}")
        read_only_file.chmod(0o444)

        monkeypatch.setattr(fx_module, "CACHE_FILE", read_only_file)
        monkeypatch.setattr(fx_module, "CACHE_DIR", tmp_path)

        provider = ExchangeRateProvider(base_currency="EUR")
        # Must not raise
        provider._save_disk_cache({"USD": 1.05})

        # File was not modified
        assert json.loads(read_only_file.read_text()) == {}
        read_only_file.chmod(0o644)  # cleanup


# ---------------------------------------------------------------------------
# TestFetchRates
# ---------------------------------------------------------------------------


class TestFetchRates:
    """Tests for batch fetch logic."""

    def test_single_batch_request_for_multiple_targets(self) -> None:
        """fetch_rates issues one batch call, not one per currency."""
        provider = ExchangeRateProvider(base_currency="EUR")

        calls: list[list[str]] = []

        def mock_fetch(targets: list[str]) -> dict[str, float]:
            calls.append(list(targets))
            return {t: 1.0 for t in targets}

        with patch.object(provider, "_fetch_from_frankfurter", side_effect=mock_fetch):
            provider.fetch_rates(["SEK", "USD", "GBP"])

        # Exactly one call with all three targets
        assert len(calls) == 1
        assert set(calls[0]) == {"SEK", "USD", "GBP"}

    def test_cached_targets_not_refetched(self) -> None:
        """Currencies already in _mem_cache skip the network."""
        provider = ExchangeRateProvider(base_currency="EUR")
        provider._mem_cache["SEK"] = 10.50
        provider._rate_source["SEK"] = "test"

        with patch.object(
            provider, "_fetch_from_frankfurter", return_value={"USD": 1.08}
        ) as mock_fetch:
            provider.fetch_rates(["SEK", "USD"])
            # Only USD should be fetched
            mock_fetch.assert_called_once_with(["USD"])

    def test_manual_overrides_skip_fetch(self) -> None:
        """Currencies in manual_overrides never hit the network."""
        provider = ExchangeRateProvider(
            base_currency="EUR", manual_overrides={"GBP": 0.85}
        )

        with patch.object(
            provider, "_fetch_from_frankfurter", return_value={}
        ) as mock_fetch:
            provider.fetch_rates(["GBP"])
            mock_fetch.assert_not_called()

    def test_requested_targets_tracked_in_order(self) -> None:
        """_requested_targets preserves insertion order."""
        provider = ExchangeRateProvider(base_currency="EUR")
        with patch.object(
            provider, "_fetch_from_frankfurter", return_value={"SEK": 10.5, "USD": 1.08}
        ):
            provider.fetch_rates(["SEK", "USD"])
        assert provider._requested_targets == ["SEK", "USD"]

    def test_network_failure_emits_warning(self) -> None:
        """When fetch returns nothing, a UserWarning is emitted per missing currency."""
        provider = ExchangeRateProvider(base_currency="EUR")
        with patch.object(provider, "_fetch_from_frankfurter", return_value={}):
            with pytest.warns(UserWarning, match="unavailable"):
                provider.fetch_rates(["XYZ"])


# ---------------------------------------------------------------------------
# TestRateInfo
# ---------------------------------------------------------------------------


class TestRateInfo:
    """Tests for rate_info metadata output."""

    def test_live_rate_info(self) -> None:
        now = datetime.now(timezone.utc)
        provider = ExchangeRateProvider(
            base_currency="EUR", fx_conversion_cost=0.02, fx_overhead_rate=0.05
        )
        provider._mem_cache["SEK"] = 10.50
        provider._fetched_at["SEK"] = now
        provider._rate_source["SEK"] = "live"

        info = provider.rate_info("SEK")
        assert info is not None
        assert info["official_rate"] == pytest.approx(10.50)
        assert info["adjusted_rate"] == pytest.approx(11.235)
        assert info["fx_conversion_cost"] == pytest.approx(0.02)
        assert info["fx_overhead_rate"] == pytest.approx(0.05)
        assert info["source"] == "live"
        assert info["fetched_at"] is not None

    def test_manual_override_rate_info(self) -> None:
        provider = ExchangeRateProvider(
            base_currency="EUR",
            fx_conversion_cost=0.10,
            manual_overrides={"GBP": 0.85},
        )
        info = provider.rate_info("GBP")
        assert info is not None
        assert info["official_rate"] == pytest.approx(0.85)
        assert info["adjusted_rate"] == pytest.approx(0.85)
        assert info["fx_conversion_cost"] == pytest.approx(0.0)
        assert info["source"] == "manual_override"
        assert info["fetched_at"] is None

    def test_unavailable_rate_info_returns_none(self) -> None:
        provider = ExchangeRateProvider(base_currency="EUR")
        assert provider.rate_info("XYZ") is None


# ---------------------------------------------------------------------------
# TestFrankfurterParsing
# ---------------------------------------------------------------------------


class TestFrankfurterParsing:
    """Tests for _fetch_from_frankfurter response parsing."""

    def test_v2_list_format_parsed(self) -> None:
        """v2 API returns a list of {base, quote, rate} objects."""
        provider = ExchangeRateProvider(base_currency="EUR")
        mock_response = json.dumps(
            [
                {"base": "EUR", "quote": "SEK", "rate": 10.50},
                {"base": "EUR", "quote": "USD", "rate": 1.08},
            ]
        ).encode()

        import urllib.request  # noqa: F401
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_response
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = provider._fetch_from_frankfurter(["SEK", "USD"])

        assert result == {"SEK": pytest.approx(10.50), "USD": pytest.approx(1.08)}

    def test_network_exception_returns_empty(self) -> None:
        """Any network exception is swallowed; empty dict returned."""
        provider = ExchangeRateProvider(base_currency="EUR")
        with patch(
            "urllib.request.urlopen", side_effect=Exception("connection refused")
        ):
            result = provider._fetch_from_frankfurter(["SEK"])
        assert result == {}

    def test_timeout_returns_empty(self) -> None:
        """Timeout is treated as unavailable."""
        import socket

        provider = ExchangeRateProvider(base_currency="EUR")
        with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
            result = provider._fetch_from_frankfurter(["USD"])
        assert result == {}


# ---------------------------------------------------------------------------
# TestModelFields
# ---------------------------------------------------------------------------


class TestModelFields:
    """Verify new ProjectMetadata FX fields parse correctly."""

    def test_secondary_currencies_parsed(self) -> None:
        from datetime import date

        from mcprojsim.models.project import ProjectMetadata

        meta = ProjectMetadata(
            name="T",
            start_date=date(2026, 1, 1),
            secondary_currencies=["SEK", "USD"],
            fx_conversion_cost=0.02,
            fx_overhead_rate=0.05,
            fx_rates={"GBP": 0.85},
        )
        assert meta.secondary_currencies == ["SEK", "USD"]
        assert meta.fx_conversion_cost == pytest.approx(0.02)
        assert meta.fx_overhead_rate == pytest.approx(0.05)
        assert meta.fx_rates == {"GBP": pytest.approx(0.85)}

    def test_empty_secondary_currencies_default(self) -> None:
        from datetime import date

        from mcprojsim.models.project import ProjectMetadata

        meta = ProjectMetadata(name="T", start_date=date(2026, 1, 1))
        assert meta.secondary_currencies == []
        assert meta.fx_conversion_cost == pytest.approx(0.0)
        assert meta.fx_overhead_rate == pytest.approx(0.0)
        assert meta.fx_rates == {}

    def test_max_5_secondary_currencies(self) -> None:
        from datetime import date

        import pydantic

        from mcprojsim.models.project import ProjectMetadata

        with pytest.raises(pydantic.ValidationError, match="at most 5"):
            ProjectMetadata(
                name="T",
                start_date=date(2026, 1, 1),
                secondary_currencies=["SEK", "USD", "GBP", "JPY", "CHF", "AUD"],
            )

    def test_fx_conversion_cost_ceiling(self) -> None:
        from datetime import date

        import pydantic

        from mcprojsim.models.project import ProjectMetadata

        with pytest.raises(pydantic.ValidationError):
            ProjectMetadata(
                name="T", start_date=date(2026, 1, 1), fx_conversion_cost=0.51
            )

    def test_invalid_currency_code_warns(self) -> None:
        from datetime import date

        import warnings

        from mcprojsim.models.project import ProjectMetadata

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ProjectMetadata(
                name="T",
                start_date=date(2026, 1, 1),
                secondary_currencies=["lowercase"],
            )
        assert any("lowercase" in str(warning.message) for warning in w)

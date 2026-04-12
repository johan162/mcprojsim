"""Exchange rate provider with 24-hour file cache.

Fetches mid-market rates from Frankfurter v2 (https://frankfurter.dev/),
a free, key-less service backed by 52 central banks and official sources.

Rates are cached in ``~/.mcprojsim/fx_rates_cache.json`` with a 24-hour TTL
so repeated runs do not hit the network.  All disk I/O errors are silently
swallowed — the cache is best-effort.  When a rate cannot be obtained (network
failure, unknown currency, timeout) the affected currency is skipped and a
warning is emitted; the simulation results are never blocked.

Adjusted-rate formula
---------------------
The official mid-market rate is marked up by two additive fractions:

    r_adj = (1 + fx_conversion_cost + fx_overhead_rate) * r_official

where *fx_conversion_cost* represents the bank's bid-ask spread and
*fx_overhead_rate* covers hedging, admin, or other indirect costs.

Manual overrides (``fx_rates`` field in the project file) are used as-is —
neither markup is applied, allowing contract-agreed or locked rates to be
specified without double-counting.
"""

from __future__ import annotations

import json
import urllib.request
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

CACHE_DIR = Path.home() / ".mcprojsim"
CACHE_FILE = CACHE_DIR / "fx_rates_cache.json"
CACHE_TTL_HOURS = 24

_FRANKFURTER_BASE_URL = "https://api.frankfurter.dev/v2/rates"


@dataclass
class ExchangeRateProvider:
    """Provides adjusted exchange rates with file-backed caching.

    Args:
        base_currency: ISO 4217 source currency (e.g. ``"EUR"``).
        fx_conversion_cost: Bank spread fraction in [0, 0.50].
        fx_overhead_rate: Additional overhead fraction in [0, 1].
        manual_overrides: Mapping of target ISO code → final rate.
            These bypass both the live fetch and the markup formula.
    """

    base_currency: str
    fx_conversion_cost: float = 0.0
    fx_overhead_rate: float = 0.0
    manual_overrides: Dict[str, float] = field(default_factory=dict)

    # In-memory cache: target currency → official (mid-market) rate
    _mem_cache: Dict[str, float] = field(default_factory=dict, init=False, repr=False)
    # Timestamps for in-memory entries (used for rate_info metadata)
    _fetched_at: Dict[str, datetime] = field(
        default_factory=dict, init=False, repr=False
    )
    # Track where each rate came from ("live", "disk_cache", "manual_override")
    _rate_source: Dict[str, str] = field(default_factory=dict, init=False, repr=False)
    # Ordered list of requested secondary currency targets
    _requested_targets: List[str] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self._load_disk_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def requested_targets(self) -> List[str]:
        """Ordered list of target currencies passed to :meth:`fetch_rates`."""
        return list(self._requested_targets)

    def get_adjusted_rate(self, target: str) -> Optional[float]:
        """Return the adjusted rate from *base_currency* to *target*.

        Manual overrides are returned directly (no markup applied).
        Returns ``None`` if the rate cannot be obtained.
        """
        if target in self.manual_overrides:
            return self.manual_overrides[target]
        official = self._get_official_rate(target)
        if official is None:
            return None
        return (1.0 + self.fx_conversion_cost + self.fx_overhead_rate) * official

    def convert_array(self, arr: np.ndarray, target: str) -> Optional[np.ndarray]:
        """Scale a cost array to *target* currency element-wise.

        Returns ``None`` when the rate is unavailable so callers can
        skip secondary-currency output gracefully.
        """
        rate = self.get_adjusted_rate(target)
        if rate is None:
            return None
        return arr * rate

    def fetch_rates(self, targets: List[str]) -> None:
        """Batch-fetch official rates for *targets* not already in cache.

        Flow:
        1. Skip targets covered by manual overrides.
        2. Use in-memory cache for already-loaded rates.
        3. For the rest, check the disk cache (24 h TTL).
        4. Remaining targets → one Frankfurter batch request.
        5. Persist new rates back to disk cache.
        """
        # Track all requested targets in order (for ordered output)
        for t in targets:
            if t not in self._requested_targets:
                self._requested_targets.append(t)

        needed_from_network: List[str] = []
        for t in targets:
            if t in self.manual_overrides or t in self._mem_cache:
                continue
            # Try disk cache (already loaded into _mem_cache by __post_init__,
            # but if target was stale it won't be in _mem_cache yet)
            needed_from_network.append(t)

        if not needed_from_network:
            return

        fetched = self._fetch_from_frankfurter(needed_from_network)
        if fetched:
            now = datetime.now(timezone.utc)
            for cur, rate in fetched.items():
                self._mem_cache[cur] = rate
                self._fetched_at[cur] = now
                self._rate_source[cur] = "live"
            self._save_disk_cache(fetched)

        # Warn about anything we couldn't get
        unavailable = [t for t in needed_from_network if t not in self._mem_cache]
        for cur in unavailable:
            warnings.warn(
                f"Exchange rate {self.base_currency}→{cur} unavailable; "
                f"skipping {cur} cost output.",
                UserWarning,
                stacklevel=2,
            )

    def rate_info(self, target: str) -> Optional[Dict[str, Any]]:
        """Return metadata about the rate for *target*, for use in exports.

        Returns ``None`` if no rate is available for *target*.
        """
        if target in self.manual_overrides:
            return {
                "official_rate": self.manual_overrides[target],
                "adjusted_rate": self.manual_overrides[target],
                "fx_conversion_cost": 0.0,
                "fx_overhead_rate": 0.0,
                "source": "manual_override",
                "fetched_at": None,
            }
        official = self._mem_cache.get(target)
        if official is None:
            return None
        adjusted = (1.0 + self.fx_conversion_cost + self.fx_overhead_rate) * official
        fetched_at = self._fetched_at.get(target)
        return {
            "official_rate": round(official, 6),
            "adjusted_rate": round(adjusted, 6),
            "fx_conversion_cost": self.fx_conversion_cost,
            "fx_overhead_rate": self.fx_overhead_rate,
            "source": self._rate_source.get(target, "unknown"),
            "fetched_at": fetched_at.isoformat() if fetched_at else None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_official_rate(self, target: str) -> Optional[float]:
        """Return official rate from memory, or fetch it on demand."""
        if target in self._mem_cache:
            return self._mem_cache[target]
        # Single-target fallback (when fetch_rates was not called first)
        fetched = self._fetch_from_frankfurter([target])
        if fetched:
            now = datetime.now(timezone.utc)
            for cur, rate in fetched.items():
                self._mem_cache[cur] = rate
                self._fetched_at[cur] = now
                self._rate_source[cur] = "live"
            self._save_disk_cache(fetched)
        return fetched.get(target)

    def _fetch_from_frankfurter(self, targets: List[str]) -> Dict[str, float]:
        """Batch-fetch official rates from Frankfurter v2.

        Returns a dict of {target: rate} for successfully retrieved
        currencies.  Any exception (network, parse, HTTP error) is
        caught and returns an empty dict — never raises.
        """
        quotes = ",".join(targets)
        url = f"{_FRANKFURTER_BASE_URL}?base={self.base_currency}&quotes={quotes}"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "mcprojsim/exchange-rates"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                raw = resp.read()
            data = json.loads(raw)
            # v2 response: [{"base":"EUR","quote":"SEK","rate":10.50,...}, ...]
            if isinstance(data, list):
                return {
                    item["quote"]: float(item["rate"])
                    for item in data
                    if "quote" in item and "rate" in item
                }
            # Defensive: some endpoints may return a dict form
            if isinstance(data, dict) and "rates" in data:
                return {k: float(v) for k, v in data["rates"].items()}
            return {}
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Disk cache
    # ------------------------------------------------------------------

    def _load_disk_cache(self) -> None:
        """Load fresh entries for *base_currency* from the disk cache."""
        try:
            if not CACHE_FILE.exists():
                return
            raw = CACHE_FILE.read_text(encoding="utf-8")
            cache: Dict[str, Any] = json.loads(raw)
            base_entries: Dict[str, Any] = cache.get(self.base_currency, {})
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=CACHE_TTL_HOURS)
            for target, entry in base_entries.items():
                if not isinstance(entry, dict):
                    continue
                fetched_str: Optional[str] = entry.get("fetched_at")
                if not fetched_str:
                    continue
                try:
                    fetched_at = datetime.fromisoformat(fetched_str)
                    # Ensure timezone-aware for comparison
                    if fetched_at.tzinfo is None:
                        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                if fetched_at < cutoff:
                    # Stale — will be re-fetched from network
                    continue
                rate = entry.get("rate")
                if rate is None:
                    continue
                self._mem_cache[target] = float(rate)
                self._fetched_at[target] = fetched_at
                self._rate_source[target] = "disk_cache"
        except Exception:
            # Corrupt file, permission error, etc. — silently ignore
            pass

    def _save_disk_cache(self, new_rates: Dict[str, float]) -> None:
        """Persist *new_rates* for *base_currency* to the disk cache.

        Merges with any existing entries from other base currencies so
        that cached rates for EUR, USD, etc. coexist in the same file.
        """
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            # Read existing cache (may contain other base currencies).
            # json.loads can return any JSON value, so we use Any and guard with isinstance.
            _raw: Any = {}
            if CACHE_FILE.exists():
                try:
                    _raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
                except Exception:
                    _raw = {}
            existing: Dict[str, Any] = _raw if isinstance(_raw, dict) else {}

            _raw_base: Any = existing.get(self.base_currency, {})
            base_entries: Dict[str, Any] = (
                _raw_base if isinstance(_raw_base, dict) else {}
            )

            now_str = datetime.now(timezone.utc).isoformat()
            for target, rate in new_rates.items():
                base_entries[target] = {"rate": rate, "fetched_at": now_str}

            existing[self.base_currency] = base_entries
            CACHE_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception:
            # Permission denied, read-only fs, etc. — silently ignore
            pass

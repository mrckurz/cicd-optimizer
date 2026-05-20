"""Runner pricing model.

Defaults follow GitHub's public pricing for hosted runners (USD/min). Override at runtime via
``Pricing.from_overrides({...})`` or the ``--pricing path.json`` CLI flag.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# USD per minute, sourced from GitHub Actions billing docs (verified 2026-05).
# https://docs.github.com/en/billing/reference/actions-runner-pricing
#
# Note: GitHub revised pricing in 2024–2025. The old "2x Windows, 10x macOS" multipliers
# are no longer accurate — macOS in particular dropped significantly.
DEFAULT_RATES: dict[str, float] = {
    # Linux x64 standard
    "ubuntu-latest": 0.006,
    "ubuntu-22.04": 0.006,
    "ubuntu-20.04": 0.006,
    "ubuntu-24.04": 0.006,
    "ubuntu-latest-slim": 0.002,   # 1-core slim runner
    # Linux x64 larger runners
    "ubuntu-latest-4-core": 0.012,
    "ubuntu-latest-8-core": 0.022,
    "ubuntu-latest-16-core": 0.042,
    "ubuntu-latest-32-core": 0.082,
    "ubuntu-latest-64-core": 0.162,
    "ubuntu-latest-96-core": 0.252,
    # Linux arm64
    "ubuntu-latest-arm": 0.005,
    "ubuntu-latest-2-core-arm": 0.005,
    "ubuntu-latest-4-core-arm": 0.008,
    "ubuntu-latest-8-core-arm": 0.014,
    "ubuntu-latest-16-core-arm": 0.026,
    "ubuntu-latest-32-core-arm": 0.050,
    "ubuntu-latest-64-core-arm": 0.098,
    # Linux GPU
    "ubuntu-latest-4-core-gpu": 0.052,
    # Windows x64
    "windows-latest": 0.010,
    "windows-2025": 0.010,
    "windows-2022": 0.010,
    "windows-2019": 0.010,
    "windows-latest-4-core": 0.022,
    "windows-latest-8-core": 0.042,
    "windows-latest-16-core": 0.082,
    "windows-latest-32-core": 0.162,
    "windows-latest-64-core": 0.322,
    "windows-latest-96-core": 0.552,
    # Windows arm64
    "windows-latest-arm": 0.008,
    "windows-latest-2-core-arm": 0.008,
    "windows-latest-4-core-arm": 0.014,
    "windows-latest-8-core-arm": 0.026,
    "windows-latest-16-core-arm": 0.050,
    "windows-latest-32-core-arm": 0.098,
    "windows-latest-64-core-arm": 0.194,
    # Windows GPU
    "windows-latest-4-core-gpu": 0.102,
    # macOS — note: pricing dropped sharply in 2024–2025
    "macos-latest": 0.062,         # 3 or 4-core M1/Intel
    "macos-13": 0.062,
    "macos-14": 0.062,
    "macos-15": 0.062,
    "macos-latest-large": 0.077,    # 12-core
    "macos-latest-xlarge": 0.102,   # M2 Pro 5-core (current "xlarge")
    # GitLab SaaS approximations (no public per-minute USD table; ~CI minutes shares).
    "gitlab-saas-small": 0.005,
    "gitlab-saas-medium": 0.01,
    "gitlab-saas-large": 0.02,
}

# Self-hosted runners are free from GitHub's perspective; users may set a custom blended rate.
SELF_HOSTED_DEFAULT = 0.0


@dataclass
class Pricing:
    rates: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_RATES))
    self_hosted_rate: float = SELF_HOSTED_DEFAULT

    @classmethod
    def from_file(cls, path: str | Path) -> Pricing:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        rates = dict(DEFAULT_RATES)
        rates.update(data.get("rates", {}))
        return cls(rates=rates, self_hosted_rate=float(data.get("self_hosted_rate", 0.0)))

    @classmethod
    def from_overrides(cls, overrides: dict[str, float]) -> Pricing:
        rates = dict(DEFAULT_RATES)
        rates.update(overrides or {})
        return cls(rates=rates)

    def rate_for(self, runner: str | list[str]) -> float:
        """Return the per-minute USD rate for a runner label.

        Heuristics:
          * Exact match wins.
          * Labels starting with ``self-hosted`` use ``self_hosted_rate``.
          * Unknown labels are treated as ``ubuntu-latest`` (cheapest hosted).
        """
        label = runner[0] if isinstance(runner, list) else runner
        label = str(label).strip()
        if not label:
            return self.rates["ubuntu-latest"]
        if label in self.rates:
            return self.rates[label]
        if label.startswith("self-hosted"):
            return self.self_hosted_rate
        # Pattern fallbacks for community-named labels.
        lower = label.lower()
        if "macos" in lower and "xlarge" in lower:
            return self.rates["macos-latest-xlarge"]
        if "macos" in lower or "darwin" in lower:
            return self.rates["macos-latest"]
        if "windows" in lower:
            return self.rates["windows-latest"]
        return self.rates["ubuntu-latest"]

    def annotate(self) -> dict[str, float]:
        """Return a copy of the rate table for inclusion in reports."""
        return dict(self.rates)

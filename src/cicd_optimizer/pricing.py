"""Runner pricing model.

Defaults follow GitHub's public pricing for hosted runners (USD/min). Override at runtime via
``Pricing.from_overrides({...})`` or the ``--pricing path.json`` CLI flag.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# USD per minute, sourced from GitHub Actions billing docs.
# https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions
DEFAULT_RATES: dict[str, float] = {
    # Linux hosted
    "ubuntu-latest": 0.008,
    "ubuntu-22.04": 0.008,
    "ubuntu-20.04": 0.008,
    "ubuntu-24.04": 0.008,
    "ubuntu-latest-4-core": 0.016,
    "ubuntu-latest-8-core": 0.032,
    "ubuntu-latest-16-core": 0.064,
    "ubuntu-latest-32-core": 0.128,
    "ubuntu-latest-64-core": 0.256,
    # Windows hosted (2x multiplier)
    "windows-latest": 0.016,
    "windows-2022": 0.016,
    "windows-2019": 0.016,
    "windows-latest-4-core": 0.032,
    "windows-latest-8-core": 0.064,
    "windows-latest-16-core": 0.128,
    # macOS hosted (10x multiplier)
    "macos-latest": 0.08,
    "macos-13": 0.08,
    "macos-14": 0.08,
    "macos-15": 0.08,
    "macos-latest-large": 0.12,
    "macos-latest-xlarge": 0.32,
    # GitLab SaaS — small/medium/large saas runners, USD/min (approximate)
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

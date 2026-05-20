"""Base classes for detection rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..models import Finding, RunStats, Workflow
from ..pricing import Pricing


@dataclass
class RuleContext:
    """Everything a rule needs to make a finding."""
    pricing: Pricing
    runs_per_month_default: int = 200
    run_stats: dict[str, RunStats] | None = None  # keyed by f"{workflow_path}::{job_id}"

    def runs_per_month(self, workflow_path: str, job_id: str | None) -> float:
        if self.run_stats:
            key = f"{workflow_path}::{job_id}" if job_id else workflow_path
            stats = self.run_stats.get(key)
            if stats:
                return stats.runs_per_month
        return float(self.runs_per_month_default)

    def avg_minutes(self, workflow_path: str, job_id: str | None, default: float) -> float:
        if self.run_stats:
            key = f"{workflow_path}::{job_id}" if job_id else workflow_path
            stats = self.run_stats.get(key)
            if stats:
                return stats.avg_duration_minutes
        return default


class Rule(Protocol):
    id: str
    title: str

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]: ...

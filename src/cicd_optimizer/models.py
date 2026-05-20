"""Core data models shared across providers, rules and reporters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        return {"low": 1, "medium": 2, "high": 3}[self.value]


class Provider(str, Enum):
    GITHUB_ACTIONS = "github-actions"
    GITLAB_CI = "gitlab-ci"


@dataclass
class Step:
    name: str | None
    uses: str | None
    run: str | None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_action(self) -> bool:
        return self.uses is not None

    @property
    def is_script(self) -> bool:
        return self.run is not None


@dataclass
class Job:
    id: str
    name: str
    runs_on: str | list[str]
    steps: list[Step] = field(default_factory=list)
    needs: list[str] = field(default_factory=list)
    strategy: dict[str, Any] | None = None
    timeout_minutes: int | None = None
    if_condition: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def runner(self) -> str:
        """Primary runner label as a string."""
        if isinstance(self.runs_on, list):
            return self.runs_on[0] if self.runs_on else "unknown"
        return str(self.runs_on)

    @property
    def matrix_size(self) -> int:
        """Approximate number of matrix expansions."""
        if not self.strategy:
            return 1
        matrix = self.strategy.get("matrix", {})
        if not isinstance(matrix, dict):
            return 1
        size = 1
        for key, vals in matrix.items():
            if key in ("include", "exclude"):
                continue
            if isinstance(vals, list):
                size *= max(1, len(vals))
        includes = matrix.get("include")
        if isinstance(includes, list):
            size += len(includes)
        return size


@dataclass
class Workflow:
    path: str
    name: str
    provider: Provider
    on: dict[str, Any] | list[str] | str
    jobs: dict[str, Job] = field(default_factory=dict)
    concurrency: dict[str, Any] | str | None = None
    permissions: dict[str, Any] | str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def triggers(self) -> list[str]:
        if isinstance(self.on, str):
            return [self.on]
        if isinstance(self.on, list):
            return [str(x) for x in self.on]
        if isinstance(self.on, dict):
            return list(self.on.keys())
        return []


@dataclass
class Patch:
    """A suggested YAML modification."""
    description: str
    diff: str  # unified-diff-style for display
    apply: dict[str, Any] | None = None  # structured patch instructions (optional)


@dataclass
class Finding:
    rule_id: str
    severity: Severity
    title: str
    message: str
    workflow_path: str
    job_id: str | None = None
    step_index: int | None = None
    estimated_minutes_saved_per_month: float = 0.0
    estimated_usd_saved_per_month: float = 0.0
    patch: Patch | None = None
    docs_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "workflow": self.workflow_path,
            "job": self.job_id,
            "step_index": self.step_index,
            "estimated_minutes_saved_per_month": round(self.estimated_minutes_saved_per_month, 2),
            "estimated_usd_saved_per_month": round(self.estimated_usd_saved_per_month, 4),
            "patch": (
                {
                    "description": self.patch.description,
                    "diff": self.patch.diff,
                }
                if self.patch
                else None
            ),
            "docs_url": self.docs_url,
        }


@dataclass
class RunStats:
    """Aggregated real run-history for a job/workflow."""
    workflow_path: str
    job_id: str | None
    runs_per_month: float
    avg_duration_minutes: float
    p95_duration_minutes: float
    total_minutes_per_month: float

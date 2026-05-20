"""R007 — duplicate matrix entries; R008 — fail-fast disabled on long matrices."""

from __future__ import annotations

import itertools
from typing import Any

from ..models import Finding, Patch, Severity, Workflow
from .base import RuleContext


def _expand_matrix(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand a matrix block into the cartesian product, plus include entries."""
    if not isinstance(matrix, dict):
        return []
    keys = [k for k in matrix if k not in ("include", "exclude")]
    value_lists = [matrix[k] if isinstance(matrix[k], list) else [matrix[k]] for k in keys]
    rows = [dict(zip(keys, combo)) for combo in itertools.product(*value_lists)] if keys else []
    rows.extend(matrix.get("include") or [])
    return rows


class MatrixDuplicatesRule:
    id = "R007"
    title = "Duplicate matrix entries"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for job_id, job in workflow.jobs.items():
            if not job.strategy:
                continue
            matrix = job.strategy.get("matrix")
            if not isinstance(matrix, dict):
                continue
            rows = _expand_matrix(matrix)
            if not rows:
                continue
            seen: dict[tuple, int] = {}
            for r in rows:
                key = tuple(sorted(r.items()))
                seen[key] = seen.get(key, 0) + 1
            dupes = {k: v for k, v in seen.items() if v > 1}
            if not dupes:
                continue
            extra = sum(v - 1 for v in dupes.values())
            runs = ctx.runs_per_month(workflow.path, job_id)
            avg_min = ctx.avg_minutes(workflow.path, job_id, 5.0)
            minutes = extra * avg_min * runs
            usd = minutes * ctx.pricing.rate_for(job.runs_on)
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=Severity.MEDIUM,
                    title=self.title,
                    message=(
                        f"Matrix for job '{job_id}' contains {extra} duplicate row(s). Each "
                        "duplicate runs an entire job clone."
                    ),
                    workflow_path=workflow.path,
                    job_id=job_id,
                    estimated_minutes_saved_per_month=minutes,
                    estimated_usd_saved_per_month=usd,
                    patch=Patch(
                        description="Remove duplicate matrix entries.",
                        diff=(
                            f"--- a/{workflow.path}\n+++ b/{workflow.path}\n"
                            f"@@ jobs.{job_id}.strategy.matrix @@\n"
                            f"# remove {extra} duplicate row(s)\n"
                        ),
                        apply={"job": job_id, "dedupe_matrix": True},
                    ),
                )
            )
        return findings


class MatrixFailFastRule:
    id = "R008"
    title = "Long matrix with fail-fast disabled"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for job_id, job in workflow.jobs.items():
            if not job.strategy:
                continue
            matrix = job.strategy.get("matrix")
            if not isinstance(matrix, dict):
                continue
            if job.strategy.get("fail-fast") is not False:
                continue
            size = job.matrix_size
            if size < 6:
                continue
            avg_min = ctx.avg_minutes(workflow.path, job_id, 5.0)
            runs = ctx.runs_per_month(workflow.path, job_id)
            # With ~5% failure rate, fail-fast saves the rest of the matrix on a failed run.
            minutes = 0.05 * runs * (size - 1) * avg_min
            usd = minutes * ctx.pricing.rate_for(job.runs_on)
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=Severity.MEDIUM,
                    title=self.title,
                    message=(
                        f"Matrix '{job_id}' has {size} entries with fail-fast disabled. "
                        "Re-enable fail-fast if early failure should cancel the rest."
                    ),
                    workflow_path=workflow.path,
                    job_id=job_id,
                    estimated_minutes_saved_per_month=minutes,
                    estimated_usd_saved_per_month=usd,
                    patch=Patch(
                        description="Re-enable fail-fast on the strategy.",
                        diff=(
                            f"--- a/{workflow.path}\n+++ b/{workflow.path}\n"
                            f"@@ jobs.{job_id}.strategy @@\n"
                            f"-      fail-fast: false\n"
                            f"+      fail-fast: true\n"
                        ),
                        apply={"job": job_id, "set_fail_fast": True},
                    ),
                )
            )
        return findings

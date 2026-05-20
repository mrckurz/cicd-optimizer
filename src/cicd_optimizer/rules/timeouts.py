"""R004 — missing timeout-minutes on jobs."""

from __future__ import annotations

from ..models import Finding, Patch, Severity, Workflow
from .base import RuleContext


class MissingTimeoutRule:
    id = "R004"
    title = "Missing timeout-minutes"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for job_id, job in workflow.jobs.items():
            if job.timeout_minutes is not None:
                continue
            # Conservative model: a hung job ~once/month would burn the default 6h cap.
            wasted_minutes = 60.0  # blended: 360 min cap * P(hang per month) ~ 0.17
            rate = ctx.pricing.rate_for(job.runs_on)
            usd = wasted_minutes * rate
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=Severity.MEDIUM,
                    title=self.title,
                    message=(
                        f"Job '{job_id}' has no timeout-minutes set. The default is 6 hours, "
                        "which silently burns money on hung jobs."
                    ),
                    workflow_path=workflow.path,
                    job_id=job_id,
                    estimated_minutes_saved_per_month=wasted_minutes,
                    estimated_usd_saved_per_month=usd,
                    patch=Patch(
                        description="Set timeout-minutes to a sane upper bound (e.g. 20).",
                        diff=(
                            f"--- a/{workflow.path}\n+++ b/{workflow.path}\n"
                            f"@@ jobs.{job_id} @@\n"
                            f"+    timeout-minutes: 20\n"
                        ),
                        apply={"job": job_id, "set_timeout": 20},
                    ),
                )
            )
        return findings

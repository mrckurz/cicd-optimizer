"""R006 — redundant actions/checkout across dependent jobs."""

from __future__ import annotations

from ..models import Finding, Patch, Severity, Workflow
from .base import RuleContext


def _has_checkout(job) -> bool:
    return any(s.uses and s.uses.startswith("actions/checkout") for s in job.steps)


class RedundantCheckoutRule:
    id = "R006"
    title = "Redundant checkout in dependent jobs"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        # A job that ``needs:`` a parent and re-checks-out source is often redundant if
        # the parent already produced an artifact.
        for job_id, job in workflow.jobs.items():
            if not job.needs:
                continue
            if not _has_checkout(job):
                continue
            uses_artifact = any(
                (s.uses or "").startswith("actions/download-artifact") for s in job.steps
            )
            if uses_artifact:
                continue
            # Each redundant checkout costs ~10s of run time.
            runs = ctx.runs_per_month(workflow.path, job_id)
            minutes = 0.17 * runs * job.matrix_size
            usd = minutes * ctx.pricing.rate_for(job.runs_on)
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=Severity.MEDIUM,
                    title=self.title,
                    message=(
                        f"Job '{job_id}' has `needs:` parents but re-runs actions/checkout instead "
                        "of downloading their build artifact. Consider uploading once and "
                        "downloading per dependent job."
                    ),
                    workflow_path=workflow.path,
                    job_id=job_id,
                    estimated_minutes_saved_per_month=minutes,
                    estimated_usd_saved_per_month=usd,
                    patch=Patch(
                        description=(
                            "Upload build artifacts in the parent job and use "
                            "actions/download-artifact here instead of actions/checkout."
                        ),
                        diff=(
                            f"--- a/{workflow.path}\n+++ b/{workflow.path}\n"
                            f"@@ jobs.{job_id}.steps @@\n"
                            f"-      - uses: actions/checkout@v4\n"
                            f"+      - uses: actions/download-artifact@v4\n"
                            f"+        with:\n+          name: build\n"
                        ),
                        apply={"job": job_id, "replace_checkout_with_artifact": True},
                    ),
                )
            )
        return findings

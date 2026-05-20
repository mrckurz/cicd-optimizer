"""R003 — missing concurrency cancel-in-progress on PR workflows."""

from __future__ import annotations

from ..models import Finding, Patch, Severity, Workflow
from .base import RuleContext


def _has_pr_trigger(workflow: Workflow) -> bool:
    on = workflow.on
    if isinstance(on, str):
        return on == "pull_request"
    if isinstance(on, list):
        return "pull_request" in on
    if isinstance(on, dict):
        return "pull_request" in on or "pull_request_target" in on
    return False


def _concurrency_cancels(workflow: Workflow) -> bool:
    c = workflow.concurrency
    if isinstance(c, dict):
        return bool(c.get("cancel-in-progress"))
    return False


class MissingConcurrencyRule:
    id = "R003"
    title = "Missing concurrency cancel-in-progress on PR workflow"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        if not _has_pr_trigger(workflow):
            return []
        if _concurrency_cancels(workflow):
            return []
        # Total avg per-run minutes across jobs.
        per_run = 0.0
        for job_id, job in workflow.jobs.items():
            per_run += ctx.avg_minutes(workflow.path, job_id, 5.0) * job.matrix_size
        # Assume ~25% of PR runs get superseded by force-pushes.
        runs = ctx.runs_per_month(workflow.path, None)
        minutes = per_run * runs * 0.25
        rate = max(
            (ctx.pricing.rate_for(j.runs_on) for j in workflow.jobs.values()),
            default=ctx.pricing.rate_for("ubuntu-latest"),
        )
        usd = minutes * rate
        patch_diff = (
            f"--- a/{workflow.path}\n+++ b/{workflow.path}\n"
            f"@@ workflow @@\n"
            f"+concurrency:\n"
            f"+  group: ${{{{ github.workflow }}}}-${{{{ github.ref }}}}\n"
            f"+  cancel-in-progress: true\n"
        )
        return [
            Finding(
                rule_id=self.id,
                severity=Severity.HIGH,
                title=self.title,
                message=(
                    "PR workflow lacks `concurrency` with `cancel-in-progress: true`. "
                    "Force-pushes leave stale runs eating minutes."
                ),
                workflow_path=workflow.path,
                estimated_minutes_saved_per_month=minutes,
                estimated_usd_saved_per_month=usd,
                patch=Patch(
                    description="Add a concurrency group keyed by workflow+ref that cancels stale runs.",
                    diff=patch_diff,
                    apply={"set_concurrency": True},
                ),
                docs_url="https://docs.github.com/actions/using-jobs/using-concurrency",
            )
        ]

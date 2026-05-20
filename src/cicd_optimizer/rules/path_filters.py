"""R005 — missing path filters; R015 — double-trigger push + pull_request."""

from __future__ import annotations

from ..models import Finding, Patch, Severity, Workflow
from .base import RuleContext

HEAVY_TOKENS = ("build", "test", "deploy", "docker", "publish", "release", "bench")


def _trigger_dict(workflow: Workflow) -> dict:
    if isinstance(workflow.on, dict):
        return workflow.on
    return {}


def _looks_heavy(workflow: Workflow) -> bool:
    for job in workflow.jobs.values():
        joined = " ".join(filter(None, [job.name or "", job.id])).lower()
        if any(t in joined for t in HEAVY_TOKENS):
            return True
    return False


class MissingPathFiltersRule:
    id = "R005"
    title = "Heavy workflow without paths/paths-ignore filter"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        if not _looks_heavy(workflow):
            return []
        trig = _trigger_dict(workflow)
        if not trig:
            return []
        offenders = []
        for key in ("push", "pull_request"):
            cfg = trig.get(key)
            if not isinstance(cfg, dict):
                continue
            if "paths" in cfg or "paths-ignore" in cfg:
                continue
            offenders.append(key)
        if not offenders:
            return []
        # Assume ~20% of pushes/PRs touch only docs.
        per_run = sum(
            ctx.avg_minutes(workflow.path, jid, 5.0) * j.matrix_size
            for jid, j in workflow.jobs.items()
        )
        runs = ctx.runs_per_month(workflow.path, None)
        minutes = per_run * runs * 0.20
        rate = ctx.pricing.rate_for(
            next(iter(workflow.jobs.values())).runs_on if workflow.jobs else "ubuntu-latest"
        )
        usd = minutes * rate
        diff = (
            f"--- a/{workflow.path}\n+++ b/{workflow.path}\n"
            f"@@ on @@\n"
            + "\n".join(
                f"+  {k}:\n+    paths-ignore:\n+      - '**.md'\n+      - 'docs/**'"
                for k in offenders
            )
        )
        return [
            Finding(
                rule_id=self.id,
                severity=Severity.MEDIUM,
                title=self.title,
                message=(
                    f"Heavy workflow triggers on {', '.join(offenders)} without paths-ignore. "
                    "Doc-only changes still run the full pipeline."
                ),
                workflow_path=workflow.path,
                estimated_minutes_saved_per_month=minutes,
                estimated_usd_saved_per_month=usd,
                patch=Patch(
                    description="Add paths-ignore for docs/markdown.",
                    diff=diff,
                    apply={"add_paths_ignore": offenders},
                ),
            )
        ]


class DoubleTriggerRule:
    id = "R015"
    title = "Workflow triggers on both push and pull_request"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        trig = _trigger_dict(workflow)
        if "push" not in trig or "pull_request" not in trig:
            return []
        # If push is restricted to main/master/release branches, that's fine.
        push = trig.get("push") or {}
        if isinstance(push, dict):
            branches = push.get("branches") or []
            if branches and all(
                b in {"main", "master"} or b.startswith("release") for b in branches
            ):
                return []
        per_run = sum(
            ctx.avg_minutes(workflow.path, jid, 5.0) * j.matrix_size
            for jid, j in workflow.jobs.items()
        )
        runs = ctx.runs_per_month(workflow.path, None)
        # Roughly half of double-runs are duplicate work.
        minutes = per_run * runs * 0.5
        rate = ctx.pricing.rate_for(
            next(iter(workflow.jobs.values())).runs_on if workflow.jobs else "ubuntu-latest"
        )
        usd = minutes * rate
        return [
            Finding(
                rule_id=self.id,
                severity=Severity.LOW,
                title=self.title,
                message=(
                    "Workflow runs on both push and pull_request without branch scoping — "
                    "PR commits run the workflow twice."
                ),
                workflow_path=workflow.path,
                estimated_minutes_saved_per_month=minutes,
                estimated_usd_saved_per_month=usd,
                patch=Patch(
                    description="Limit push to protected branches; keep pull_request for PRs.",
                    diff=(
                        f"--- a/{workflow.path}\n+++ b/{workflow.path}\n"
                        f"@@ on.push @@\n"
                        f"+    branches: [main]\n"
                    ),
                    apply={"limit_push_branches": ["main"]},
                ),
            )
        ]

"""R012 — outdated major versions of common actions."""

from __future__ import annotations

import re

from ..models import Finding, Patch, Severity, Workflow
from .base import RuleContext

# action -> (minimum acceptable major version, current major) — verified 2026-05
RECOMMENDED: dict[str, tuple[int, int]] = {
    "actions/checkout": (5, 6),
    "actions/setup-node": (4, 4),
    "actions/setup-python": (5, 6),
    "actions/setup-go": (5, 5),
    "actions/setup-java": (4, 4),
    "actions/cache": (4, 4),
    "actions/upload-artifact": (5, 7),
    "actions/download-artifact": (4, 5),
    "docker/build-push-action": (5, 6),
    "docker/login-action": (3, 3),
    "docker/setup-buildx-action": (3, 3),
    "docker/setup-qemu-action": (3, 3),
}

VERSION_TAG = re.compile(r"@v(\d+)")


class OutdatedActionsRule:
    id = "R012"
    title = "Outdated action versions"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for job_id, job in workflow.jobs.items():
            outdated: list[tuple[str, str]] = []
            for step in job.steps:
                if not step.uses:
                    continue
                base = step.uses.split("@", 1)[0]
                if base not in RECOMMENDED:
                    continue
                minimum, _ = RECOMMENDED[base]
                m = VERSION_TAG.search(step.uses)
                if not m:
                    continue
                if int(m.group(1)) < minimum:
                    outdated.append((step.uses, f"{base}@v{minimum}"))
            if not outdated:
                continue
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=Severity.LOW,
                    title=self.title,
                    message=(
                        f"Job '{job_id}' uses outdated action versions. Newer majors include "
                        "perf/cache improvements (typ. 5–15s saved per run)."
                    ),
                    workflow_path=workflow.path,
                    job_id=job_id,
                    estimated_minutes_saved_per_month=0.2 * len(outdated)
                    * ctx.runs_per_month(workflow.path, job_id),
                    estimated_usd_saved_per_month=0.0,
                    patch=Patch(
                        description="Bump to the latest stable major version.",
                        diff="\n".join(
                            f"-      - uses: {old}\n+      - uses: {new}"
                            for old, new in outdated
                        ),
                        apply={"job": job_id, "upgrade": outdated},
                    ),
                )
            )
        return findings

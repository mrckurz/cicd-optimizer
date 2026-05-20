"""R009 — Docker build without layer cache."""

from __future__ import annotations

from ..models import Finding, Patch, Severity, Workflow
from .base import RuleContext


class DockerLayerCacheRule:
    id = "R009"
    title = "Docker build without layer cache"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for job_id, job in workflow.jobs.items():
            offenders = []
            for idx, step in enumerate(job.steps):
                if not step.uses:
                    continue
                if "docker/build-push-action" not in step.uses:
                    continue
                with_block = step.raw.get("with") or {}
                if with_block.get("cache-from") or with_block.get("cache-to"):
                    continue
                offenders.append((idx, step))
            if not offenders:
                continue
            runs = ctx.runs_per_month(workflow.path, job_id)
            # A cold Docker build typically takes 1–3 minutes more than a warm one.
            minutes = 2.0 * runs * len(offenders) * job.matrix_size
            usd = minutes * ctx.pricing.rate_for(job.runs_on)
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=Severity.MEDIUM,
                    title=self.title,
                    message=(
                        f"Job '{job_id}' runs docker/build-push-action without layer caching. "
                        "Add cache-from / cache-to (GHA cache backend) to skip warm rebuilds."
                    ),
                    workflow_path=workflow.path,
                    job_id=job_id,
                    estimated_minutes_saved_per_month=minutes,
                    estimated_usd_saved_per_month=usd,
                    patch=Patch(
                        description="Enable BuildKit layer cache via type=gha.",
                        diff=(
                            f"--- a/{workflow.path}\n+++ b/{workflow.path}\n"
                            f"@@ jobs.{job_id}.steps[docker/build-push-action] @@\n"
                            f"+        with:\n"
                            f"+          cache-from: type=gha\n"
                            f"+          cache-to: type=gha,mode=max\n"
                        ),
                        apply={"job": job_id, "docker_cache": True},
                    ),
                    docs_url="https://docs.docker.com/build/ci/github-actions/cache/",
                )
            )
        return findings

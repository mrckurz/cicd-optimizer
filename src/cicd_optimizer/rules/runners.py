"""R002 — oversized runner; R011 — expensive platform when Linux would do."""

from __future__ import annotations

import re

from ..models import Finding, Patch, Severity, Workflow
from .base import RuleContext

CORE_PATTERN = re.compile(r"-(\d+)-core")
HEAVY_HINTS = (
    "build",
    "compile",
    "docker",
    "bazel",
    "android",
    "kernel",
    "ffmpeg",
    "ml",
    "training",
)


class OversizedRunnerRule:
    id = "R002"
    title = "Oversized runner"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for job_id, job in workflow.jobs.items():
            label = job.runner
            m = CORE_PATTERN.search(label)
            if not m:
                continue
            cores = int(m.group(1))
            if cores < 8:
                continue
            heavy = any(_looks_heavy(s.run) or _looks_heavy(s.name or "") for s in job.steps)
            heavy = heavy or any(h in job_id.lower() or h in (job.name or "").lower() for h in HEAVY_HINTS)
            if heavy:
                continue
            # Suggest the next smaller tier (cores/2). Savings: rate delta * avg duration * runs.
            runs = ctx.runs_per_month(workflow.path, job_id)
            avg_min = ctx.avg_minutes(workflow.path, job_id, 5.0)
            old_rate = ctx.pricing.rate_for(label)
            smaller = label.replace(f"-{cores}-core", "" if cores // 2 == 2 else f"-{cores // 2}-core")
            new_rate = ctx.pricing.rate_for(smaller)
            usd = max(0.0, (old_rate - new_rate) * avg_min * runs * job.matrix_size)
            minutes = 0.0  # no minute savings, only cost savings
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=Severity.HIGH,
                    title=self.title,
                    message=(
                        f"Job '{job_id}' runs on {label} ({cores} cores) but does not look "
                        f"compute-bound. Downsize to {smaller} for ~"
                        f"{int(100 * (1 - new_rate / max(old_rate, 1e-9)))}% lower runner cost."
                    ),
                    workflow_path=workflow.path,
                    job_id=job_id,
                    estimated_minutes_saved_per_month=minutes,
                    estimated_usd_saved_per_month=usd,
                    patch=Patch(
                        description=f"Change runs-on from {label} to {smaller}",
                        diff=(
                            f"--- a/{workflow.path}\n+++ b/{workflow.path}\n"
                            f"@@ jobs.{job_id} @@\n"
                            f"-    runs-on: {label}\n"
                            f"+    runs-on: {smaller}\n"
                        ),
                        apply={"job": job_id, "set_runs_on": smaller},
                    ),
                )
            )
        return findings


class ExpensivePlatformRule:
    id = "R011"
    title = "Expensive platform (macOS/Windows) where Linux would do"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for job_id, job in workflow.jobs.items():
            label = job.runner.lower()
            if "macos" not in label and "windows" not in label:
                continue
            # If the job mentions iOS/Xcode/MSVC, the platform is required.
            required_markers = ("xcode", "ios", "swift", "msvc", "powershell", ".net framework", "winsdk")
            joined = " ".join(
                (s.run or "") + " " + (s.name or "") for s in job.steps
            ).lower()
            if any(m in joined for m in required_markers):
                continue
            runs = ctx.runs_per_month(workflow.path, job_id)
            avg_min = ctx.avg_minutes(workflow.path, job_id, 5.0)
            current_rate = ctx.pricing.rate_for(job.runs_on)
            linux_rate = ctx.pricing.rate_for("ubuntu-latest")
            usd = max(0.0, (current_rate - linux_rate) * avg_min * runs * job.matrix_size)
            if usd <= 0:
                continue
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=Severity.LOW,
                    title=self.title,
                    message=(
                        f"Job '{job_id}' uses '{job.runner}' but does not reference platform-specific "
                        "tooling. Linux runners are ~10x cheaper for macOS and ~2x cheaper than Windows."
                    ),
                    workflow_path=workflow.path,
                    job_id=job_id,
                    estimated_minutes_saved_per_month=0,
                    estimated_usd_saved_per_month=usd,
                    patch=Patch(
                        description=f"Switch {job_id} to ubuntu-latest",
                        diff=(
                            f"--- a/{workflow.path}\n+++ b/{workflow.path}\n"
                            f"@@ jobs.{job_id} @@\n"
                            f"-    runs-on: {job.runner}\n"
                            f"+    runs-on: ubuntu-latest\n"
                        ),
                        apply={"job": job_id, "set_runs_on": "ubuntu-latest"},
                    ),
                )
            )
        return findings


def _looks_heavy(text: str | None) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(h in t for h in HEAVY_HINTS)

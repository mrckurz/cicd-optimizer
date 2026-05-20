"""R013 — sequential needs chain; R014 — self-hosted candidate by volume."""

from __future__ import annotations

from ..models import Finding, Patch, Severity, Workflow
from .base import RuleContext


class SequentialNeedsRule:
    id = "R013"
    title = "Sequential needs chain could fan out"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        # A "chain" is A -> B -> C -> ... where each downstream has exactly one parent.
        chains: list[list[str]] = []
        successors: dict[str, list[str]] = {jid: [] for jid in workflow.jobs}
        for jid, j in workflow.jobs.items():
            for parent in j.needs:
                if parent in successors:
                    successors[parent].append(jid)
        for jid, j in workflow.jobs.items():
            if j.needs:
                continue
            chain = [jid]
            current = jid
            while len(successors.get(current, [])) == 1:
                nxt = successors[current][0]
                # Only count it as a chain if the downstream's only parent is the current node.
                if len(workflow.jobs[nxt].needs) != 1:
                    break
                chain.append(nxt)
                current = nxt
            if len(chain) >= 3:
                chains.append(chain)
        findings: list[Finding] = []
        for chain in chains:
            avg = sum(ctx.avg_minutes(workflow.path, j, 5.0) for j in chain[1:])  # avoidable
            runs = ctx.runs_per_month(workflow.path, chain[0])
            minutes = max(0.0, avg) * runs * 0.4  # ~40% of the chain is independent on average
            usd = minutes * ctx.pricing.rate_for(workflow.jobs[chain[0]].runs_on)
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=Severity.MEDIUM,
                    title=self.title,
                    message=(
                        "Sequential `needs:` chain detected: "
                        + " → ".join(chain)
                        + ". If the downstream jobs don't truly require the previous one, "
                        "let them fan out in parallel for shorter wall-clock."
                    ),
                    workflow_path=workflow.path,
                    estimated_minutes_saved_per_month=minutes,
                    estimated_usd_saved_per_month=usd,
                    patch=Patch(
                        description="Review needs: chain and parallelize jobs that don't truly depend on each other.",
                        diff=(
                            f"--- a/{workflow.path}\n+++ b/{workflow.path}\n"
                            f"@@ jobs @@\n"
                            f"# review needs: declarations along chain {' -> '.join(chain)}\n"
                        ),
                        apply={"review_chain": chain},
                    ),
                )
            )
        return findings


class SelfHostedCandidateRule:
    id = "R014"
    title = "Self-hosted candidate by volume"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        if not ctx.run_stats:
            return findings  # this rule requires real run data
        for job_id, job in workflow.jobs.items():
            stats = ctx.run_stats.get(f"{workflow.path}::{job_id}")
            if not stats:
                continue
            label = job.runner
            if "self-hosted" in str(label):
                continue
            hosted_rate = ctx.pricing.rate_for(label)
            if hosted_rate <= 0:
                continue
            monthly_minutes = stats.total_minutes_per_month
            monthly_usd = monthly_minutes * hosted_rate
            if monthly_usd < 200:
                continue
            # Even a 60% blended cost reduction by moving to self-hosted is a routine outcome.
            saved_usd = monthly_usd * 0.6
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=Severity.HIGH,
                    title=self.title,
                    message=(
                        f"Job '{job_id}' on '{label}' burns ~{monthly_minutes:.0f} min "
                        f"(~${monthly_usd:.0f}) per month. A self-hosted pool would typically "
                        "cut blended cost by ~60% at this volume."
                    ),
                    workflow_path=workflow.path,
                    job_id=job_id,
                    estimated_minutes_saved_per_month=0,
                    estimated_usd_saved_per_month=saved_usd,
                    patch=Patch(
                        description="Migrate hot job to a self-hosted runner pool.",
                        diff=(
                            f"--- a/{workflow.path}\n+++ b/{workflow.path}\n"
                            f"@@ jobs.{job_id} @@\n"
                            f"-    runs-on: {label}\n"
                            f"+    runs-on: [self-hosted, linux, x64]\n"
                        ),
                        apply={"job": job_id, "set_runs_on": ["self-hosted", "linux", "x64"]},
                    ),
                )
            )
        return findings

"""R010 — long test job not sharded."""

from __future__ import annotations

import re

from ..models import Finding, Patch, Severity, Workflow
from .base import RuleContext

TEST_HINTS = re.compile(r"\b(pytest|jest|vitest|mocha|go\s+test|cargo\s+test|rspec|phpunit|mvn\s+test|gradle\s+test)\b")


class MissingShardingRule:
    id = "R010"
    title = "Long test job not sharded"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for job_id, job in workflow.jobs.items():
            avg = ctx.avg_minutes(workflow.path, job_id, 0.0)
            if avg < 10:
                # Without API data we can still flag if the job is named 'test' and has no matrix.
                pass
            is_test = any(
                step.run and TEST_HINTS.search(step.run) for step in job.steps
            ) or "test" in job_id.lower()
            if not is_test:
                continue
            if job.matrix_size > 1:
                continue
            if avg == 0.0:
                # No run-history; conservative estimate based on test-heuristic only.
                minutes_estimate = 6.0
            else:
                if avg < 10:
                    continue
                minutes_estimate = avg
            # Sharding into 4 reduces wall-clock by ~3/4 but uses 4 parallel jobs.
            # Net minute spend stays roughly the same; we report wall-clock savings as
            # *developer wait* time, not $ (so report $ as 0 unless avg known).
            runs = ctx.runs_per_month(workflow.path, job_id)
            minutes_saved_wallclock = (minutes_estimate * 0.75) * runs
            # $ savings only if user is on a self-hosted/paid concurrency model — we conservatively
            # report 0 $ and flag this for developer-wait reduction.
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=Severity.LOW,
                    title=self.title,
                    message=(
                        f"Job '{job_id}' looks like a long test job (~{minutes_estimate:.0f} min) "
                        "and is not sharded. Split the test suite via a matrix of shard indices."
                    ),
                    workflow_path=workflow.path,
                    job_id=job_id,
                    estimated_minutes_saved_per_month=minutes_saved_wallclock,
                    estimated_usd_saved_per_month=0.0,
                    patch=Patch(
                        description="Add a `shard` matrix and parameterize your test runner.",
                        diff=(
                            f"--- a/{workflow.path}\n+++ b/{workflow.path}\n"
                            f"@@ jobs.{job_id} @@\n"
                            f"+    strategy:\n"
                            f"+      matrix:\n"
                            f"+        shard: [1, 2, 3, 4]\n"
                            f"+    steps:\n"
                            f"+      - run: pytest --shard=${{{{ matrix.shard }}}}/4\n"
                        ),
                        apply={"job": job_id, "add_shard_matrix": 4},
                    ),
                )
            )
        return findings

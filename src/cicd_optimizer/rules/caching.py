"""R001 — missing dependency cache."""

from __future__ import annotations

import re

from ..models import Finding, Patch, Severity, Workflow
from .base import RuleContext

# Patterns that fetch dependencies and should usually be cached.
PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("pip", re.compile(r"\bpip\s+install\b"), "actions/setup-python@v5 with cache: pip"),
    ("npm", re.compile(r"\bnpm\s+(ci|install)\b"), "actions/setup-node@v4 with cache: npm"),
    ("yarn", re.compile(r"\byarn\s+(install|--frozen-lockfile)?"), "actions/setup-node@v4 with cache: yarn"),
    ("pnpm", re.compile(r"\bpnpm\s+(install|i)\b"), "pnpm/action-setup + cache: pnpm"),
    ("gradle", re.compile(r"\b\./gradlew\b|\bgradle\b"), "actions/setup-java@v4 with cache: gradle"),
    ("maven", re.compile(r"\bmvn\b"), "actions/setup-java@v4 with cache: maven"),
    ("go", re.compile(r"\bgo\s+(build|test|mod)\b"), "actions/setup-go@v5 with cache: true (default)"),
    ("cargo", re.compile(r"\bcargo\s+(build|test|fetch)\b"), "Swatinem/rust-cache@v2"),
    ("bundler", re.compile(r"\bbundle\s+install\b"), "ruby/setup-ruby@v1 with bundler-cache: true"),
]


def _existing_setup_cache(workflow: Workflow, job_id: str) -> set[str]:
    """Return the set of ecosystem keys (pip, npm, …) already cached in the job."""
    found: set[str] = set()
    job = workflow.jobs[job_id]
    for step in job.steps:
        if step.uses and step.uses.startswith("actions/setup-"):
            with_block = step.raw.get("with") or {}
            cache_val = str(with_block.get("cache", "")).lower()
            if cache_val:
                found.add(cache_val)
        if step.uses and "actions/cache@" in step.uses:
            found.add("manual")
        if step.uses and "rust-cache" in step.uses.lower():
            found.add("cargo")
        if step.uses and "bundler-cache" in step.raw.get("with", {}):
            found.add("bundler")
    return found


class MissingCacheRule:
    id = "R001"
    title = "Missing dependency cache"

    def analyze(self, workflow: Workflow, ctx: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for job_id, job in workflow.jobs.items():
            cached = _existing_setup_cache(workflow, job_id)
            if "manual" in cached:
                continue
            detected: set[str] = set()
            for step in job.steps:
                if not step.run:
                    continue
                for eco, pat, _fix in PATTERNS:
                    if eco in cached:
                        continue
                    if pat.search(step.run):
                        detected.add(eco)
            if not detected:
                continue
            # Cost model: typical cold install is ~60–120s. Assume 90s saved per run on average.
            runs = ctx.runs_per_month(workflow.path, job_id)
            minutes_saved = 1.5 * runs * job.matrix_size
            usd = minutes_saved * ctx.pricing.rate_for(job.runs_on)
            ecos = ", ".join(sorted(detected))
            patch = _build_cache_patch(workflow, job_id, sorted(detected))
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=Severity.HIGH,
                    title=self.title,
                    message=(
                        f"Job '{job_id}' installs {ecos} without caching. "
                        f"Add the cache option on actions/setup-* or a dedicated cache action."
                    ),
                    workflow_path=workflow.path,
                    job_id=job_id,
                    estimated_minutes_saved_per_month=minutes_saved,
                    estimated_usd_saved_per_month=usd,
                    patch=patch,
                    docs_url="https://docs.github.com/actions/using-workflows/caching-dependencies-to-speed-up-workflows",
                )
            )
        return findings


def _build_cache_patch(workflow: Workflow, job_id: str, ecos: list[str]) -> Patch:
    suggestions = {
        "pip": "      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n          cache: pip",
        "npm": "      - uses: actions/setup-node@v4\n        with:\n          node-version: '20'\n          cache: npm",
        "yarn": "      - uses: actions/setup-node@v4\n        with:\n          node-version: '20'\n          cache: yarn",
        "pnpm": "      - uses: pnpm/action-setup@v4\n      - uses: actions/setup-node@v4\n        with:\n          node-version: '20'\n          cache: pnpm",
        "gradle": "      - uses: actions/setup-java@v4\n        with:\n          distribution: temurin\n          java-version: '21'\n          cache: gradle",
        "maven": "      - uses: actions/setup-java@v4\n        with:\n          distribution: temurin\n          java-version: '21'\n          cache: maven",
        "go": "      - uses: actions/setup-go@v5\n        with:\n          go-version: stable",
        "cargo": "      - uses: Swatinem/rust-cache@v2",
        "bundler": "      - uses: ruby/setup-ruby@v1\n        with:\n          bundler-cache: true",
    }
    diff_body = "\n".join(suggestions[e] for e in ecos if e in suggestions)
    diff = (
        f"--- a/{workflow.path}\n"
        f"+++ b/{workflow.path}\n"
        f"@@ jobs.{job_id}.steps @@\n"
        + "\n".join(f"+{line}" for line in diff_body.splitlines())
    )
    return Patch(
        description=f"Add setup-* with built-in cache for: {', '.join(ecos)}",
        diff=diff,
        apply={"job": job_id, "insert_steps": ecos},
    )

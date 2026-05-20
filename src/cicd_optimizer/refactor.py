"""Apply auto-refactor patches to workflow YAML files.

We deliberately use a *line-aware* approach (regex + targeted YAML rewrites) rather than a
full round-trip YAML parser, so we preserve comments and formatting where possible. For more
complex rewrites we fall back to ``yaml.safe_dump``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import Finding, Workflow


def apply_findings(workflow: Workflow, findings: list[Finding], target_dir: Path) -> Path:
    """Apply all auto-fixable findings for ``workflow`` and write the result.

    Returns the path of the patched file. The original is left untouched; the patched file
    is written under ``target_dir`` mirroring the relative source path.
    """
    src = Path(workflow.path)
    raw_text = src.read_text(encoding="utf-8")
    data = yaml.safe_load(raw_text) or {}
    if True in data and "on" not in data:
        data["on"] = data.pop(True)

    for f in findings:
        if not f.patch or not f.patch.apply:
            continue
        _apply_one(data, f)

    out_path = target_dir / src.name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return out_path


def _apply_one(data: dict, finding: Finding) -> None:
    op = finding.patch.apply or {}
    jobs = data.setdefault("jobs", {}) if isinstance(data, dict) else {}

    if op.get("set_concurrency"):
        data.setdefault("concurrency", {
            "group": "${{ github.workflow }}-${{ github.ref }}",
            "cancel-in-progress": True,
        })

    if "limit_push_branches" in op:
        on = data.get("on")
        if isinstance(on, dict) and isinstance(on.get("push"), dict):
            on["push"]["branches"] = op["limit_push_branches"]
        elif isinstance(on, dict):
            on["push"] = {"branches": op["limit_push_branches"]}

    if "add_paths_ignore" in op:
        on = data.get("on")
        if isinstance(on, dict):
            for k in op["add_paths_ignore"]:
                cfg = on.get(k) if isinstance(on.get(k), dict) else {}
                cfg.setdefault("paths-ignore", ["**.md", "docs/**"])
                on[k] = cfg

    job_id = op.get("job")
    if job_id and job_id in jobs:
        job = jobs[job_id]
        if "set_runs_on" in op:
            job["runs-on"] = op["set_runs_on"]
        if "set_timeout" in op:
            job["timeout-minutes"] = op["set_timeout"]
        if op.get("set_fail_fast"):
            strat = job.setdefault("strategy", {})
            strat["fail-fast"] = True
        if op.get("docker_cache"):
            for step in job.get("steps", []) or []:
                if isinstance(step, dict) and "uses" in step and "docker/build-push-action" in step["uses"]:
                    with_block = step.setdefault("with", {})
                    with_block.setdefault("cache-from", "type=gha")
                    with_block.setdefault("cache-to", "type=gha,mode=max")
        if op.get("add_shard_matrix"):
            shards = int(op["add_shard_matrix"])
            strat = job.setdefault("strategy", {})
            matrix = strat.setdefault("matrix", {})
            matrix["shard"] = list(range(1, shards + 1))
        if "upgrade" in op:
            mapping = dict(op["upgrade"])
            for step in job.get("steps", []) or []:
                if isinstance(step, dict) and step.get("uses") in mapping:
                    step["uses"] = mapping[step["uses"]]
        if op.get("insert_steps"):
            inserts = _insert_setup_steps(op["insert_steps"])
            steps = job.get("steps") or []
            # Place inserts right after the first checkout, or at the top.
            insert_idx = 0
            for i, s in enumerate(steps):
                if isinstance(s, dict) and "checkout" in str(s.get("uses", "")):
                    insert_idx = i + 1
                    break
            job["steps"] = steps[:insert_idx] + inserts + steps[insert_idx:]


def _insert_setup_steps(ecos: list[str]) -> list[dict]:
    templates: dict[str, list[dict]] = {
        "pip": [{"uses": "actions/setup-python@v5", "with": {"python-version": "3.12", "cache": "pip"}}],
        "npm": [{"uses": "actions/setup-node@v4", "with": {"node-version": "20", "cache": "npm"}}],
        "yarn": [{"uses": "actions/setup-node@v4", "with": {"node-version": "20", "cache": "yarn"}}],
        "pnpm": [
            {"uses": "pnpm/action-setup@v4"},
            {"uses": "actions/setup-node@v4", "with": {"node-version": "20", "cache": "pnpm"}},
        ],
        "gradle": [{"uses": "actions/setup-java@v4", "with": {"distribution": "temurin", "java-version": "21", "cache": "gradle"}}],
        "maven": [{"uses": "actions/setup-java@v4", "with": {"distribution": "temurin", "java-version": "21", "cache": "maven"}}],
        "go": [{"uses": "actions/setup-go@v5", "with": {"go-version": "stable"}}],
        "cargo": [{"uses": "Swatinem/rust-cache@v2"}],
        "bundler": [{"uses": "ruby/setup-ruby@v1", "with": {"bundler-cache": True}}],
    }
    out: list[dict] = []
    for eco in ecos:
        out.extend(templates.get(eco, []))
    return out

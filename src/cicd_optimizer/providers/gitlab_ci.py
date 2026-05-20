"""GitLab CI configuration parser.

GitLab pipelines do not have an exact ``jobs`` key the way GitHub Actions do — instead, every
top-level key that isn't a reserved keyword is a job. We normalize it into the same internal
``Workflow``/``Job`` shape so the rule engine doesn't care which provider it came from.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..models import Job, Provider, Step, Workflow

RESERVED_KEYS: set[str] = {
    "default",
    "include",
    "stages",
    "variables",
    "workflow",
    "image",
    "services",
    "before_script",
    "after_script",
    "cache",
    "pages",
    "true",  # YAML 1.1 quirk
}


def _job_to_steps(j: dict[str, Any]) -> list[Step]:
    """Map GitLab's ``script:``/``before_script:``/``after_script:`` into Step objects."""
    out: list[Step] = []
    for key in ("before_script", "script", "after_script"):
        s = j.get(key)
        if isinstance(s, list):
            for line in s:
                out.append(Step(name=f"{key}", uses=None, run=str(line), raw={"run": str(line)}))
        elif isinstance(s, str):
            out.append(Step(name=key, uses=None, run=s, raw={"run": s}))
    return out


def _runner_from_tags(j: dict[str, Any]) -> str:
    tags = j.get("tags") or []
    if isinstance(tags, list) and tags:
        joined = ",".join(str(t) for t in tags)
        # Heuristic mapping
        lower = joined.lower()
        if "saas-linux-small" in lower:
            return "gitlab-saas-small"
        if "saas-linux-medium" in lower:
            return "gitlab-saas-medium"
        if "saas-linux-large" in lower:
            return "gitlab-saas-large"
        if "self-hosted" in lower or "private" in lower:
            return "self-hosted"
        return f"gitlab-tag:{joined}"
    return "gitlab-saas-small"


def parse_gitlab_ci(path: Path) -> Workflow | None:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None

    jobs: dict[str, Job] = {}
    for key, j in data.items():
        if not isinstance(j, dict):
            continue
        if key.startswith(".") or key in RESERVED_KEYS:
            continue
        if "script" not in j and "trigger" not in j and "extends" not in j:
            continue
        needs_raw = j.get("needs")
        if isinstance(needs_raw, str):
            needs = [needs_raw]
        elif isinstance(needs_raw, list):
            needs = [n if isinstance(n, str) else n.get("job", "") for n in needs_raw]
        else:
            needs = []
        jobs[key] = Job(
            id=key,
            name=key,
            runs_on=_runner_from_tags(j),
            steps=_job_to_steps(j),
            needs=[n for n in needs if n],
            strategy={"matrix": j.get("parallel", {}).get("matrix")} if isinstance(j.get("parallel"), dict) else None,
            timeout_minutes=_parse_timeout(j.get("timeout")),
            if_condition=None,
            raw=j,
        )
    return Workflow(
        path=str(path),
        name=Path(path).stem,
        provider=Provider.GITLAB_CI,
        on=data.get("workflow", {}).get("rules", []) if isinstance(data.get("workflow"), dict) else [],
        jobs=jobs,
        concurrency=None,
        permissions=None,
        raw=data,
    )


def _parse_timeout(value: Any) -> int | None:
    """Parse GitLab ``timeout: 1h 30m`` into minutes."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    total = 0
    current = ""
    for ch in value.strip().lower():
        if ch.isdigit():
            current += ch
        elif ch in {"h", "m", "s"} and current:
            n = int(current)
            if ch == "h":
                total += n * 60
            elif ch == "m":
                total += n
            elif ch == "s":
                total += n // 60
            current = ""
    if current.isdigit():
        total += int(current)
    return total or None

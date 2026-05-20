"""GitHub Actions workflow parser."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..models import Job, Provider, Step, Workflow


# PyYAML loses ``on:`` because YAML 1.1 interprets the bare word as boolean True.
# We post-process the parsed dict to recover it.
def _normalize_on_key(data: dict[str, Any]) -> dict[str, Any]:
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


def _parse_steps(steps_raw: list[Any] | None) -> list[Step]:
    if not steps_raw:
        return []
    out: list[Step] = []
    for s in steps_raw:
        if not isinstance(s, dict):
            continue
        out.append(
            Step(
                name=s.get("name"),
                uses=s.get("uses"),
                run=s.get("run"),
                raw=s,
            )
        )
    return out


def _parse_jobs(jobs_raw: dict[str, Any] | None) -> dict[str, Job]:
    out: dict[str, Job] = {}
    if not isinstance(jobs_raw, dict):
        return out
    for job_id, j in jobs_raw.items():
        if not isinstance(j, dict):
            continue
        needs_raw = j.get("needs")
        if isinstance(needs_raw, str):
            needs = [needs_raw]
        elif isinstance(needs_raw, list):
            needs = [str(x) for x in needs_raw]
        else:
            needs = []
        out[job_id] = Job(
            id=job_id,
            name=j.get("name", job_id),
            runs_on=j.get("runs-on", "ubuntu-latest"),
            steps=_parse_steps(j.get("steps")),
            needs=needs,
            strategy=j.get("strategy") if isinstance(j.get("strategy"), dict) else None,
            timeout_minutes=j.get("timeout-minutes"),
            if_condition=j.get("if"),
            raw=j,
        )
    return out


def parse_github_actions(path: Path) -> Workflow | None:
    """Parse a GitHub Actions workflow YAML file."""
    try:
        text = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    data = _normalize_on_key(data)
    return Workflow(
        path=str(path),
        name=data.get("name") or Path(path).stem,
        provider=Provider.GITHUB_ACTIONS,
        on=data.get("on", {}),
        jobs=_parse_jobs(data.get("jobs")),
        concurrency=data.get("concurrency"),
        permissions=data.get("permissions"),
        raw=data,
    )

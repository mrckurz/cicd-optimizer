"""Fetch real GitHub Actions run-history.

Requires a ``GITHUB_TOKEN`` env var (or token passed in). Hits ``/repos/{repo}/actions/runs``
and ``/actions/runs/{id}/jobs`` to gather durations.
"""

from __future__ import annotations

import os
import statistics
import time
from datetime import datetime, timedelta, timezone

import requests

from ..models import RunStats

API_ROOT = "https://api.github.com"


def _headers(token: str | None) -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _parse_since(since: str) -> datetime:
    """Parse '7d', '30d', '12h', or ISO-8601 into a UTC datetime."""
    since = since.strip()
    now = datetime.now(timezone.utc)
    if since.endswith("d") and since[:-1].isdigit():
        return now - timedelta(days=int(since[:-1]))
    if since.endswith("h") and since[:-1].isdigit():
        return now - timedelta(hours=int(since[:-1]))
    return datetime.fromisoformat(since.replace("Z", "+00:00"))


def _get(url: str, token: str | None, params: dict | None = None) -> dict:
    for attempt in range(3):
        r = requests.get(url, headers=_headers(token), params=params, timeout=30)
        if r.status_code == 429 or (r.status_code == 403 and "rate limit" in r.text.lower()):
            time.sleep(2 ** attempt * 5)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()
    return {}


def collect_github_run_history(
    repo: str,
    since: str = "30d",
    token: str | None = None,
    max_runs: int = 500,
) -> dict[str, RunStats]:
    """Return run-history keyed by ``f"{workflow_path}::{job_id}"`` and by ``workflow_path``."""
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    since_dt = _parse_since(since)
    days = max(1, (datetime.now(timezone.utc) - since_dt).days)

    # Workflows listing -> map workflow id -> path
    wf_index: dict[int, str] = {}
    data = _get(f"{API_ROOT}/repos/{repo}/actions/workflows", token, {"per_page": 100})
    for wf in data.get("workflows", []):
        wf_index[wf["id"]] = wf["path"]

    # Runs listing — paginate.
    durations_by_workflow: dict[str, list[float]] = {}
    durations_by_job: dict[str, list[float]] = {}
    page = 1
    collected = 0
    while collected < max_runs:
        data = _get(
            f"{API_ROOT}/repos/{repo}/actions/runs",
            token,
            {
                "per_page": 100,
                "page": page,
                "created": f">={since_dt.date().isoformat()}",
            },
        )
        runs = data.get("workflow_runs", []) or []
        if not runs:
            break
        for run in runs:
            wf_path = wf_index.get(run.get("workflow_id"), run.get("path", "unknown"))
            collected += 1
            # Aggregate at workflow level using run_started_at -> updated_at.
            try:
                s = datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00"))
                e = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
                durations_by_workflow.setdefault(wf_path, []).append(
                    max(0.0, (e - s).total_seconds() / 60.0)
                )
            except Exception:
                pass
            # Pull jobs only for the first 200 runs to bound API usage.
            if collected <= 200:
                try:
                    jobs_data = _get(
                        f"{API_ROOT}/repos/{repo}/actions/runs/{run['id']}/jobs",
                        token,
                        {"per_page": 100},
                    )
                    for jb in jobs_data.get("jobs", []) or []:
                        if not jb.get("completed_at") or not jb.get("started_at"):
                            continue
                        s = datetime.fromisoformat(jb["started_at"].replace("Z", "+00:00"))
                        e = datetime.fromisoformat(jb["completed_at"].replace("Z", "+00:00"))
                        durations_by_job.setdefault(
                            f"{wf_path}::{jb['name']}", []
                        ).append((e - s).total_seconds() / 60.0)
                except Exception:
                    pass
            if collected >= max_runs:
                break
        if len(runs) < 100:
            break
        page += 1

    out: dict[str, RunStats] = {}
    for wf_path, durs in durations_by_workflow.items():
        if not durs:
            continue
        runs_per_month = len(durs) * 30.0 / days
        out[wf_path] = RunStats(
            workflow_path=wf_path,
            job_id=None,
            runs_per_month=runs_per_month,
            avg_duration_minutes=statistics.fmean(durs),
            p95_duration_minutes=_quantile(durs, 0.95),
            total_minutes_per_month=sum(durs) * 30.0 / days,
        )
    for key, durs in durations_by_job.items():
        if not durs:
            continue
        wf_path, job_id = key.split("::", 1)
        runs_per_month = len(durs) * 30.0 / days
        out[key] = RunStats(
            workflow_path=wf_path,
            job_id=job_id,
            runs_per_month=runs_per_month,
            avg_duration_minutes=statistics.fmean(durs),
            p95_duration_minutes=_quantile(durs, 0.95),
            total_minutes_per_month=sum(durs) * 30.0 / days,
        )
    return out


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[k]

"""JSON reporter — stable schema for CI consumption."""

from __future__ import annotations

import json
from typing import Any

from ..analyzer import AnalysisResult


def to_json(result: AnalysisResult, indent: int = 2) -> str:
    payload: dict[str, Any] = {
        "summary": {
            "workflows_scanned": len(result.workflows),
            "findings": len(result.findings),
            "estimated_minutes_saved_per_month": round(result.total_minutes_saved, 2),
            "estimated_usd_saved_per_month": round(result.total_usd_saved, 2),
            "by_severity": result.by_severity(),
        },
        "pricing": result.pricing.annotate(),
        "findings": [f.to_dict() for f in result.findings],
        "workflows": [
            {
                "path": wf.path,
                "name": wf.name,
                "provider": wf.provider.value,
                "jobs": list(wf.jobs.keys()),
                "triggers": wf.triggers,
            }
            for wf in result.workflows
        ],
    }
    return json.dumps(payload, indent=indent)

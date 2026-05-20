"""HTML dashboard reporter — self-contained, opens in any browser."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..analyzer import AnalysisResult

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _colorize_diff(diff: str) -> str:
    out: list[str] = []
    for line in diff.splitlines():
        e = escape(line)
        if line.startswith("+++") or line.startswith("---"):
            out.append(f'<span style="color:#9aa3b2">{e}</span>')
        elif line.startswith("+"):
            out.append(f'<span class="add">{e}</span>')
        elif line.startswith("-"):
            out.append(f'<span class="del">{e}</span>')
        elif line.startswith("@@"):
            out.append(f'<span style="color:#8b5cf6">{e}</span>')
        else:
            out.append(e)
    return "\n".join(out)


def render_html(result: AnalysisResult) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("dashboard.html")

    by_wf_agg = sorted(
        (
            {
                "path": wf.path,
                "provider": wf.provider.value,
                "count": len(fs),
                "minutes": sum(f.estimated_minutes_saved_per_month for f in fs),
                "usd": sum(f.estimated_usd_saved_per_month for f in fs),
            }
            for wf, fs in (
                (wf, [f for f in result.findings if f.workflow_path == wf.path])
                for wf in result.workflows
            )
        ),
        key=lambda r: -r["usd"],
    )

    chart_by_workflow = {
        "labels": [Path(r["path"]).name for r in by_wf_agg],
        "values": [round(r["usd"], 2) for r in by_wf_agg],
    }
    by_sev = result.by_severity()
    chart_by_severity = {
        "labels": ["High", "Medium", "Low"],
        "values": [by_sev.get("high", 0), by_sev.get("medium", 0), by_sev.get("low", 0)],
    }
    by_rule = result.by_rule()
    rule_order = sorted(
        by_rule.keys(),
        key=lambda r: -sum(f.estimated_usd_saved_per_month for f in by_rule[r]),
    )
    chart_by_rule = {
        "labels": rule_order,
        "usd": [round(sum(f.estimated_usd_saved_per_month for f in by_rule[r]), 2) for r in rule_order],
        "minutes": [round(sum(f.estimated_minutes_saved_per_month for f in by_rule[r]), 1) for r in rule_order],
    }

    findings_ctx = []
    for f in result.findings:
        d = f.to_dict()
        d["patch_diff_html"] = _colorize_diff(f.patch.diff) if f.patch else ""
        findings_ctx.append(d)

    providers = ", ".join(sorted({wf.provider.value for wf in result.workflows})) or "—"
    return template.render(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        providers=providers,
        workflow_count=len(result.workflows),
        finding_count=len(result.findings),
        total_usd=result.total_usd_saved,
        total_minutes=result.total_minutes_saved,
        by_severity=result.by_severity(),
        auto_fixable=sum(1 for f in result.findings if f.patch),
        workflow_rollup=by_wf_agg,
        findings=findings_ctx,
        chart_by_workflow=json.dumps(chart_by_workflow),
        chart_by_severity=json.dumps(chart_by_severity),
        chart_by_rule=json.dumps(chart_by_rule),
    )

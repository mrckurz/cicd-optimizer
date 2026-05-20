"""Markdown reporter — suitable for PR comments."""

from __future__ import annotations

from ..analyzer import AnalysisResult

SEVERITY_BADGES = {
    "high": "🔴 high",
    "medium": "🟠 medium",
    "low": "🟡 low",
}


def to_markdown(result: AnalysisResult) -> str:
    lines: list[str] = []
    lines.append("# 💸 cicd-optimizer report")
    lines.append("")
    lines.append(
        f"- **Workflows scanned**: {len(result.workflows)}"
    )
    lines.append(f"- **Findings**: {len(result.findings)}")
    lines.append(
        f"- **Estimated waste**: ~{result.total_minutes_saved:.0f} min / month "
        f"(~${result.total_usd_saved:.2f} / month)"
    )
    by_sev = result.by_severity()
    lines.append(
        f"- **By severity**: {SEVERITY_BADGES['high']}: {by_sev.get('high', 0)} · "
        f"{SEVERITY_BADGES['medium']}: {by_sev.get('medium', 0)} · "
        f"{SEVERITY_BADGES['low']}: {by_sev.get('low', 0)}"
    )
    lines.append("")
    if not result.findings:
        lines.append("✅ No issues detected. Nice.")
        return "\n".join(lines)

    lines.append("## Findings")
    lines.append("")
    lines.append("| Rule | Severity | Workflow | Job | Est. min/mo | Est. $/mo | Title |")
    lines.append("|---|---|---|---|---:|---:|---|")
    for f in result.findings:
        lines.append(
            f"| `{f.rule_id}` | {SEVERITY_BADGES.get(f.severity.value, f.severity.value)} | "
            f"`{f.workflow_path}` | `{f.job_id or '-'}` | "
            f"{f.estimated_minutes_saved_per_month:.0f} | "
            f"${f.estimated_usd_saved_per_month:.2f} | {f.title} |"
        )
    lines.append("")
    lines.append("## Suggested fixes")
    for f in result.findings:
        if not f.patch:
            continue
        lines.append("")
        lines.append(f"### `{f.rule_id}` — {f.title} (`{f.workflow_path}`)")
        lines.append("")
        lines.append(f.message)
        lines.append("")
        lines.append("```diff")
        lines.append(f.patch.diff)
        lines.append("```")
    return "\n".join(lines)

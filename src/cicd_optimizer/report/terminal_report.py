"""Rich-based terminal renderer."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..analyzer import AnalysisResult

SEVERITY_STYLE = {
    "high": "bold red",
    "medium": "bold yellow",
    "low": "bold blue",
}


def render_terminal(result: AnalysisResult, console: Console | None = None) -> None:
    console = console or Console()

    header = Text()
    header.append("cicd-optimizer ", style="bold magenta")
    header.append("— CI/CD cost observability\n", style="dim")
    header.append(
        f"  {len(result.workflows)} workflow(s) scanned, "
        f"{len(result.findings)} finding(s)\n",
        style="dim",
    )
    header.append(
        "  Estimated waste: ", style="dim"
    )
    header.append(
        f"{result.total_minutes_saved:,.0f} min/mo", style="bold cyan"
    )
    header.append(" ≈ ", style="dim")
    header.append(f"${result.total_usd_saved:,.2f}/mo", style="bold green")
    by_sev = result.by_severity()
    header.append(
        f"   [high: {by_sev.get('high', 0)}, medium: {by_sev.get('medium', 0)}, "
        f"low: {by_sev.get('low', 0)}]",
        style="dim",
    )
    console.print(Panel.fit(header, border_style="magenta"))

    if not result.findings:
        console.print("[green]✓ No issues detected.[/green]")
        return

    # Per-workflow rollup table.
    by_wf = result.by_workflow()
    rollup = Table(title="By workflow", show_lines=False, header_style="bold")
    rollup.add_column("Workflow", overflow="fold")
    rollup.add_column("Findings", justify="right")
    rollup.add_column("Min/mo", justify="right")
    rollup.add_column("$/mo", justify="right", style="bold green")
    for wf, fs in sorted(
        by_wf.items(), key=lambda kv: -sum(f.estimated_usd_saved_per_month for f in kv[1])
    ):
        rollup.add_row(
            wf,
            str(len(fs)),
            f"{sum(f.estimated_minutes_saved_per_month for f in fs):,.0f}",
            f"${sum(f.estimated_usd_saved_per_month for f in fs):,.2f}",
        )
    console.print(rollup)

    # Findings table.
    table = Table(title="Findings", show_lines=False, header_style="bold")
    table.add_column("Rule")
    table.add_column("Sev")
    table.add_column("Workflow", overflow="fold")
    table.add_column("Job")
    table.add_column("Min/mo", justify="right")
    table.add_column("$/mo", justify="right", style="bold green")
    table.add_column("Title", overflow="fold")
    for f in result.findings:
        table.add_row(
            f.rule_id,
            f"[{SEVERITY_STYLE[f.severity.value]}]{f.severity.value}[/]",
            f.workflow_path,
            f.job_id or "-",
            f"{f.estimated_minutes_saved_per_month:,.0f}",
            f"${f.estimated_usd_saved_per_month:,.2f}",
            f.title,
        )
    console.print(table)

    console.print(
        "[dim]Run with --html out/dashboard.html for a richer view, or "
        "[bold]cicd-optimizer serve[/bold] for a live dashboard.[/dim]"
    )

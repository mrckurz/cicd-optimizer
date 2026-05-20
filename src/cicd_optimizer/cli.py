"""Command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .analyzer import AnalysisConfig, analyze
from .collectors import collect_github_run_history
from .pricing import Pricing
from .refactor import apply_findings
from .report import render_html, render_terminal, to_json, to_markdown

CONFIG_FILE = ".cicd-optimizer.yml"


def _resolve_config(config_path: Path | None, pricing_path: Path | None) -> AnalysisConfig:
    cfg = AnalysisConfig.from_file(config_path) if config_path else AnalysisConfig()
    if pricing_path:
        cfg.pricing = Pricing.from_file(pricing_path)
    return cfg


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version")
def main() -> None:
    """cicd-optimizer — find wasted minutes and cloud dollars in CI/CD pipelines."""


@main.command(name="analyze", help="Analyze workflows and print/save a report.")
@click.argument("targets", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("--repo", help="GitHub owner/name — fetch run history via API.")
@click.option("--since", default="30d", show_default=True, help="How far back to fetch runs (e.g. 7d, 30d).")
@click.option("--token", envvar="GITHUB_TOKEN", help="GitHub token (or env GITHUB_TOKEN).")
@click.option("--pricing", "pricing_path", type=click.Path(path_type=Path), help="JSON file overriding runner rates.")
@click.option("--config", "config_path", type=click.Path(path_type=Path), help="Path to .cicd-optimizer.yml (default: repo root).")
@click.option("--json", "as_json", is_flag=True, help="Print JSON instead of the terminal report.")
@click.option("--markdown", "markdown_path", type=click.Path(path_type=Path), help="Write a Markdown report (great for PR comments).")
@click.option("--html", "html_path", type=click.Path(path_type=Path), help="Write a self-contained HTML dashboard.")
@click.option("--fix", "fix_dir", type=click.Path(path_type=Path), is_flag=False, flag_value="./.cicd-optimizer-fixes", help="Apply auto-refactor patches into the given directory (default ./.cicd-optimizer-fixes).")
@click.option("--fail-over", type=float, default=None, help="Exit with code 1 if estimated $/month waste exceeds this number.")
@click.option("--no-banner", is_flag=True, help="Suppress the rich banner; useful in CI.")
def analyze_cmd(
    targets: tuple[Path, ...],
    repo: str | None,
    since: str,
    token: str | None,
    pricing_path: Path | None,
    config_path: Path | None,
    as_json: bool,
    markdown_path: Path | None,
    html_path: Path | None,
    fix_dir: Path | str | None,
    fail_over: float | None,
    no_banner: bool,
) -> None:
    console = Console()

    resolved_targets: list[Path] = list(targets) or [Path(".")]
    # Auto-discover config file in cwd.
    auto_cfg = Path.cwd() / CONFIG_FILE
    if config_path is None and auto_cfg.exists():
        config_path = auto_cfg
    cfg = _resolve_config(config_path, pricing_path)

    run_stats = None
    if repo:
        if not no_banner:
            console.print(f"[dim]Fetching run history for {repo} (since {since})…[/dim]")
        try:
            run_stats = collect_github_run_history(repo=repo, since=since, token=token)
        except Exception as exc:
            console.print(f"[red]Failed to fetch run history: {exc}[/red]")

    result = analyze(resolved_targets, config=cfg, run_stats=run_stats)

    if as_json:
        click.echo(to_json(result))
    else:
        render_terminal(result, console=console)

    if markdown_path:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(to_markdown(result), encoding="utf-8")
        console.print(f"[green]Markdown report written to {markdown_path}[/green]")

    if html_path:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_html(result), encoding="utf-8")
        console.print(f"[green]HTML dashboard written to {html_path}[/green]")

    if fix_dir is not None:
        out_dir = Path(fix_dir) if isinstance(fix_dir, str) else fix_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        for wf in result.workflows:
            findings = [f for f in result.findings if f.workflow_path == wf.path and f.patch]
            if not findings:
                continue
            out = apply_findings(wf, findings, out_dir)
            console.print(f"[green]Patched: {out}[/green]")

    if fail_over is not None and result.total_usd_saved > fail_over:
        console.print(
            f"[red]Total estimated waste ${result.total_usd_saved:.2f}/mo "
            f"exceeds threshold ${fail_over:.2f}/mo[/red]"
        )
        sys.exit(1)


@main.command(name="serve", help="Run a local dashboard server (http://127.0.0.1:8765).")
@click.argument("targets", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8765, show_default=True, type=int)
@click.option("--no-browser", is_flag=True, help="Don't auto-open the browser.")
@click.option("--pricing", "pricing_path", type=click.Path(path_type=Path))
@click.option("--config", "config_path", type=click.Path(path_type=Path))
def serve_cmd(
    targets: tuple[Path, ...],
    host: str,
    port: int,
    no_browser: bool,
    pricing_path: Path | None,
    config_path: Path | None,
) -> None:
    from .server import serve

    resolved_targets: list[Path] = list(targets) or [Path(".")]
    auto_cfg = Path.cwd() / CONFIG_FILE
    if config_path is None and auto_cfg.exists():
        config_path = auto_cfg
    cfg = _resolve_config(config_path, pricing_path)
    serve(resolved_targets, cfg, host=host, port=port, open_browser=not no_browser)


@main.command(name="rules", help="List built-in detection rules.")
def rules_cmd() -> None:
    from .rules import ALL_RULES

    console = Console()
    from rich.table import Table

    table = Table(title="Detection rules", header_style="bold magenta")
    table.add_column("ID")
    table.add_column("Title")
    for r in ALL_RULES:
        table.add_row(r.id, r.title)
    console.print(table)


if __name__ == "__main__":
    main()

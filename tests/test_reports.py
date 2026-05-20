import json
from pathlib import Path

from cicd_optimizer.analyzer import AnalysisConfig, analyze
from cicd_optimizer.report import render_html, to_json, to_markdown

FIX = Path(__file__).parent / "fixtures"


def test_json_report_schema():
    result = analyze([FIX / "wasteful.yml"], config=AnalysisConfig())
    payload = json.loads(to_json(result))
    assert "summary" in payload
    assert payload["summary"]["findings"] == len(result.findings)
    assert payload["summary"]["estimated_usd_saved_per_month"] >= 0
    assert isinstance(payload["findings"], list)


def test_markdown_report_contains_table():
    result = analyze([FIX / "wasteful.yml"], config=AnalysisConfig())
    md = to_markdown(result)
    assert "# 💸 cicd-optimizer report" in md
    assert "| Rule | Severity |" in md


def test_html_report_renders():
    result = analyze([FIX / "wasteful.yml"], config=AnalysisConfig())
    html = render_html(result)
    assert "<title>cicd-optimizer" in html
    assert "Findings" in html
    # Chart.js is referenced
    assert "chart.js" in html.lower()

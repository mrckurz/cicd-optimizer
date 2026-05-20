from pathlib import Path

import yaml

from cicd_optimizer.analyzer import AnalysisConfig, analyze
from cicd_optimizer.refactor import apply_findings

FIX = Path(__file__).parent / "fixtures"


def test_apply_findings_writes_patched_yaml(tmp_path: Path):
    result = analyze([FIX / "wasteful.yml"], config=AnalysisConfig())
    wf = result.workflows[0]
    findings = [f for f in result.findings if f.workflow_path == wf.path and f.patch]
    out = apply_findings(wf, findings, tmp_path)
    assert out.exists()
    data = yaml.safe_load(out.read_text())
    # Concurrency should be inserted.
    assert "concurrency" in data
    # Oversized runner should be downsized.
    assert data["jobs"]["test"]["runs-on"] != "ubuntu-latest-16-core"
    # Timeout should be set.
    assert data["jobs"]["test"].get("timeout-minutes") == 20
    # Outdated checkout should be bumped to current minimum (v5 as of 2026-05).
    uses = [s.get("uses") for s in data["jobs"]["test"]["steps"] if isinstance(s, dict)]
    assert any(u and "actions/checkout@v5" in u for u in uses)

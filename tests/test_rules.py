from pathlib import Path

from cicd_optimizer.analyzer import AnalysisConfig, analyze

FIX = Path(__file__).parent / "fixtures"


def _findings(wf_path: Path):
    return analyze([wf_path], config=AnalysisConfig()).findings


def test_wasteful_triggers_many_rules():
    fs = _findings(FIX / "wasteful.yml")
    rule_ids = {f.rule_id for f in fs}
    # The wasteful fixture should trigger at least these rules.
    expected = {"R001", "R002", "R003", "R004", "R007", "R008", "R009", "R011", "R012", "R015"}
    missing = expected - rule_ids
    assert not missing, f"Missing expected rules: {missing}; got {rule_ids}"


def test_clean_has_few_findings():
    fs = _findings(FIX / "clean.yml")
    # The clean fixture should at most trigger low-severity informational rules.
    high = [f for f in fs if f.severity.value == "high"]
    assert not high, f"Clean workflow surprisingly triggered high-sev rules: {[f.rule_id for f in high]}"


def test_total_usd_nonnegative():
    fs = _findings(FIX / "wasteful.yml")
    assert all(f.estimated_usd_saved_per_month >= 0 for f in fs)


def test_findings_sorted_by_severity_then_usd():
    fs = _findings(FIX / "wasteful.yml")
    ranks = [(f.severity.rank, f.estimated_usd_saved_per_month) for f in fs]
    # Sorted descending by severity then $.
    for a, b in zip(ranks, ranks[1:]):
        assert (a[0], a[1]) >= (b[0], b[1])

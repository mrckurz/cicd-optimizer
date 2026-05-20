"""Orchestrates parse → rules → cost → report."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models import Finding, Severity, Workflow
from .pricing import Pricing
from .providers import discover, parse_file
from .rules import ALL_RULES, RuleContext


@dataclass
class AnalysisConfig:
    pricing: Pricing = field(default_factory=Pricing)
    runs_per_month_default: int = 200
    muted_rules: set[str] = field(default_factory=set)
    severity_overrides: dict[str, Severity] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> AnalysisConfig:
        if not path.exists():
            return cls()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        pricing = Pricing.from_overrides(data.get("pricing_overrides", {}))
        if "self_hosted_rate" in data:
            pricing.self_hosted_rate = float(data["self_hosted_rate"])
        sev = {
            k: Severity(v) for k, v in (data.get("severity_overrides") or {}).items()
        }
        return cls(
            pricing=pricing,
            runs_per_month_default=int(data.get("runs_per_month", 200)),
            muted_rules=set(data.get("mute") or []),
            severity_overrides=sev,
        )


@dataclass
class AnalysisResult:
    workflows: list[Workflow]
    findings: list[Finding]
    pricing: Pricing
    run_stats: dict | None = None

    @property
    def total_minutes_saved(self) -> float:
        return sum(f.estimated_minutes_saved_per_month for f in self.findings)

    @property
    def total_usd_saved(self) -> float:
        return sum(f.estimated_usd_saved_per_month for f in self.findings)

    def by_workflow(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {}
        for f in self.findings:
            out.setdefault(f.workflow_path, []).append(f)
        return out

    def by_rule(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {}
        for f in self.findings:
            out.setdefault(f.rule_id, []).append(f)
        return out

    def by_severity(self) -> dict[str, int]:
        out = {"high": 0, "medium": 0, "low": 0}
        for f in self.findings:
            out[f.severity.value] = out.get(f.severity.value, 0) + 1
        return out


def analyze(
    targets: list[Path],
    config: AnalysisConfig | None = None,
    run_stats: dict | None = None,
) -> AnalysisResult:
    """Analyze one or more workflow files / directories and return an AnalysisResult."""
    config = config or AnalysisConfig()
    files: list[Path] = []
    for t in targets:
        if t.is_dir():
            files.extend(discover(t))
        else:
            files.append(t)

    workflows: list[Workflow] = []
    for f in files:
        wf = parse_file(f)
        if wf and wf.jobs:
            workflows.append(wf)

    ctx = RuleContext(
        pricing=config.pricing,
        runs_per_month_default=config.runs_per_month_default,
        run_stats=run_stats,
    )

    findings: list[Finding] = []
    for wf in workflows:
        for rule in ALL_RULES:
            if rule.id in config.muted_rules:
                continue
            try:
                for finding in rule.analyze(wf, ctx):
                    if finding.rule_id in config.severity_overrides:
                        finding.severity = config.severity_overrides[finding.rule_id]
                    findings.append(finding)
            except Exception as exc:  # never let one bad rule crash the whole run
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        severity=Severity.LOW,
                        title=f"{rule.id} crashed",
                        message=f"Rule '{rule.id}' raised {type(exc).__name__}: {exc}",
                        workflow_path=wf.path,
                    )
                )

    findings.sort(
        key=lambda f: (
            -f.severity.rank,
            -f.estimated_usd_saved_per_month,
            f.workflow_path,
        )
    )
    return AnalysisResult(
        workflows=workflows,
        findings=findings,
        pricing=config.pricing,
        run_stats=run_stats,
    )

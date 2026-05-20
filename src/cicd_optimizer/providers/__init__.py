"""Workflow parsers for the supported CI providers."""

from __future__ import annotations

from pathlib import Path

from ..models import Provider, Workflow
from .github_actions import parse_github_actions
from .gitlab_ci import parse_gitlab_ci


def detect_provider(path: Path) -> Provider | None:
    """Guess the CI provider for a given path."""
    p = path.resolve()
    name = p.name.lower()
    parts = {part.lower() for part in p.parts}
    if name in {".gitlab-ci.yml", ".gitlab-ci.yaml"} or "gitlab-ci" in name:
        return Provider.GITLAB_CI
    if ".github" in parts and "workflows" in parts:
        return Provider.GITHUB_ACTIONS
    if name.endswith((".yml", ".yaml")):
        # Default guess based on content sniffing is done by the parser.
        return None
    return None


def parse_file(path: Path) -> Workflow | None:
    """Parse a single workflow file, auto-detecting provider when possible."""
    provider = detect_provider(path)
    if provider == Provider.GITHUB_ACTIONS:
        return parse_github_actions(path)
    if provider == Provider.GITLAB_CI:
        return parse_gitlab_ci(path)
    # Fallback: try GHA first, then GitLab.
    try:
        wf = parse_github_actions(path)
        if wf and wf.jobs:
            return wf
    except Exception:
        pass
    try:
        return parse_gitlab_ci(path)
    except Exception:
        return None


def discover(root: Path) -> list[Path]:
    """Yield candidate CI files under ``root``.

    Strategy:
      * If ``root`` is a file, return [root].
      * If ``root`` is the repo root (contains ``.github/workflows`` or ``.gitlab-ci.yml``),
        return those canonical locations.
      * Otherwise, treat ``root`` as an explicit folder and scan all ``*.yml``/``*.yaml`` in it.
    """
    root = root.resolve()
    if root.is_file():
        return [root]
    out: list[Path] = []
    gha_dir = root / ".github" / "workflows"
    # Treat path as repo root if .github/workflows exists; otherwise as an explicit folder.
    if gha_dir.exists():
        for f in sorted(gha_dir.iterdir()):
            if f.suffix.lower() in {".yml", ".yaml"} and f.is_file():
                out.append(f)
        for name in (".gitlab-ci.yml", ".gitlab-ci.yaml"):
            candidate = root / name
            if candidate.exists():
                out.append(candidate)
        return out
    # Explicit folder: pull every YAML in it (non-recursive) plus .gitlab-ci.yml.
    for f in sorted(root.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() in {".yml", ".yaml"} or f.name in {".gitlab-ci.yml", ".gitlab-ci.yaml"}:
            out.append(f)
    return out


__all__ = ["detect_provider", "parse_file", "discover", "parse_github_actions", "parse_gitlab_ci"]

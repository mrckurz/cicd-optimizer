from pathlib import Path

from cicd_optimizer.models import Provider
from cicd_optimizer.providers import parse_file

FIX = Path(__file__).parent / "fixtures"


def test_parse_github_actions():
    wf = parse_file(FIX / "wasteful.yml")
    assert wf is not None
    assert wf.provider == Provider.GITHUB_ACTIONS
    assert set(wf.jobs.keys()) == {"test", "docker", "e2e"}
    assert wf.jobs["test"].matrix_size == 8  # 4 nodes × 2 OSes
    assert "pull_request" in wf.triggers


def test_parse_gitlab_ci():
    wf = parse_file(FIX / "gitlab-ci.yml")
    assert wf is not None
    assert wf.provider == Provider.GITLAB_CI
    assert "test" in wf.jobs

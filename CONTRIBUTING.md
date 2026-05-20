# Contributing

Thanks for considering a contribution. Issues and PRs are very welcome.

## Local setup

```bash
git clone https://github.com/mrckurz/cicd-optimizer
cd cicd-optimizer
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Adding a new rule

1. Drop a new file in `src/cicd_optimizer/rules/`. Subclass `Rule` from `rules/base.py`.
2. Implement `analyze(workflow) -> list[Finding]`.
3. Register it in `rules/__init__.py`.
4. Add a test fixture in `tests/fixtures/` and a test in `tests/test_rules.py`.
5. Document it in the README rules table.

## Coding style

- Python 3.10+.
- `ruff check .` and `mypy src/` should pass.
- Prefer plain functions/dataclasses over heavy OOP.
- Every finding must carry: `rule_id`, `severity`, `workflow`, `job` (if applicable),
  `message`, `estimated_minutes_saved_per_month`, `estimated_usd_saved_per_month`, and an
  optional `patch` (a YAML diff).

## Commit messages

Conventional Commits, e.g. `feat(rules): detect docker BuildKit cache misses`. Sign-off not
required.

## Code of conduct

We follow the [Contributor Covenant](CODE_OF_CONDUCT.md).

# cicd-optimizer

> **Find wasted minutes and cloud dollars in GitHub Actions and GitLab CI pipelines — with auto-refactor suggestions and a live dashboard.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/mrckurz/cicd-optimizer/actions/workflows/ci.yml/badge.svg)](https://github.com/mrckurz/cicd-optimizer/actions/workflows/ci.yml)

`cicd-optimizer` is an open-source CI/CD **cost observability** tool. It statically analyzes your
GitHub Actions and GitLab CI configuration, optionally enriches the analysis with **real run
history** from the GitHub API, and tells you exactly:

- 💸 **Where money is burning** — per workflow, per job, per rule.
- ⏱️ **Where minutes are wasted** — missing caches, oversized runners, redundant checkouts,
  forgotten `concurrency:` groups, unfiltered docs-triggered pipelines, missing `timeout-minutes`,
  matrix bloat, sequential jobs that could fan out, Docker layer cache misses, and more.
- 🛠️ **How to fix it** — every finding includes a concrete **auto-refactor suggestion** in the
  form of a YAML diff you can apply with `--fix`.
- 📊 **A pretty dashboard** — rich terminal output for the CLI, plus a self-contained HTML
  dashboard you can open in any browser or host on Pages.

## Highlights

- **Multi-provider**: GitHub Actions and GitLab CI today, extensible rule engine.
- **Run-history aware**: feed in real run durations via the GitHub API to get **actual** $ and
  minutes wasted, not just estimates.
- **Cost model included**: GitHub-hosted runner pricing baked in (Linux 2/4/8/16/32/64-core,
  Windows, macOS) — overridable via `--pricing` JSON.
- **15+ detection rules** out of the box — see [Rules](#rules).
- **Auto-fix mode** (`--fix`) writes patched YAML next to your originals.
- **Three reporters**: rich terminal, JSON (for CI gating), and a self-contained HTML dashboard.
- **No SaaS, no telemetry, no account.** Runs entirely locally.

## Install

```bash
pip install cicd-optimizer
```

Or from source:

```bash
git clone https://github.com/mrckurz/cicd-optimizer
cd cicd-optimizer
pip install -e ".[dev]"
```

## Quickstart

```bash
# Analyze the current repo
cicd-optimizer analyze

# Analyze a specific workflow directory or file
cicd-optimizer analyze .github/workflows/
cicd-optimizer analyze .gitlab-ci.yml

# Enrich with real run history (last 30 days) — needs GITHUB_TOKEN
export GITHUB_TOKEN=ghp_xxx
cicd-optimizer analyze --repo owner/name --since 30d

# Open the HTML dashboard
cicd-optimizer analyze --html out/dashboard.html && open out/dashboard.html

# Auto-apply safe refactors
cicd-optimizer analyze --fix

# JSON for CI gating (exit code 1 if estimated waste exceeds threshold)
cicd-optimizer analyze --json --fail-over 50
```

Short alias: `cco analyze` works too.

## What it finds

### Rules

| ID | Severity | What it detects |
|---|---|---|
| `R001` | high | Missing dependency cache (`npm`, `pip`, `yarn`, `pnpm`, `gradle`, `maven`, `go`) |
| `R002` | high | Oversized runner (e.g. 16-core for `npm test`) |
| `R003` | high | Missing `concurrency:` cancel-in-progress on PR workflows |
| `R004` | medium | No `timeout-minutes` set (risk of runaway jobs) |
| `R005` | medium | Heavy workflow without `paths`/`paths-ignore` filter (runs on doc edits) |
| `R006` | medium | Redundant `actions/checkout` across dependent jobs (use artifacts) |
| `R007` | medium | Matrix entries that are identical or duplicates |
| `R008` | medium | Matrix `fail-fast: false` on expensive long matrices without need |
| `R009` | medium | Docker build without layer cache (`cache-from`/`cache-to`) |
| `R010` | low | Long test job not sharded (>10 min single job) |
| `R011` | low | macOS or Windows runner used where Linux would do |
| `R012` | low | Pinned outdated major versions of common actions |
| `R013` | medium | Sequential `needs:` chain where parallel fan-out is possible |
| `R014` | high | Self-hosted candidate: same job runs 100s of times/month on hosted |
| `R015` | low | Workflow triggers on `push` AND `pull_request` for same branch (double-run) |

Each finding includes: workflow/job, estimated minutes saved/month, estimated $/month saved, a
human-readable explanation, and an auto-refactor patch.

### Pricing model (GitHub-hosted, USD/min)

Baked-in defaults follow GitHub's [public Actions runner pricing reference](https://docs.github.com/en/billing/reference/actions-runner-pricing) (verified 2026-05). Override at runtime with `--pricing path.json`.

**Linux x64**

| Runner | $/min |
|---|---:|
| `ubuntu-latest` (2-core) | 0.006 |
| `ubuntu-latest-4-core` | 0.012 |
| `ubuntu-latest-8-core` | 0.022 |
| `ubuntu-latest-16-core` | 0.042 |
| `ubuntu-latest-32-core` | 0.082 |
| `ubuntu-latest-64-core` | 0.162 |
| `ubuntu-latest-96-core` | 0.252 |

**Linux arm64** (cheaper than x64)

| Runner | $/min |
|---|---:|
| `ubuntu-latest-2-core-arm` | 0.005 |
| `ubuntu-latest-4-core-arm` | 0.008 |
| `ubuntu-latest-8-core-arm` | 0.014 |
| `ubuntu-latest-16-core-arm` | 0.026 |
| `ubuntu-latest-32-core-arm` | 0.050 |
| `ubuntu-latest-64-core-arm` | 0.098 |

**Windows x64**

| Runner | $/min |
|---|---:|
| `windows-latest` (2-core) | 0.010 |
| `windows-latest-4-core` | 0.022 |
| `windows-latest-8-core` | 0.042 |
| `windows-latest-16-core` | 0.082 |
| `windows-latest-32-core` | 0.162 |
| `windows-latest-64-core` | 0.322 |
| `windows-latest-96-core` | 0.552 |

**macOS**

| Runner | $/min |
|---|---:|
| `macos-latest` (3/4-core, M1/Intel) | 0.062 |
| `macos-latest-large` (12-core) | 0.077 |
| `macos-latest-xlarge` (5-core M2 Pro) | 0.102 |

**GPU runners**

| Runner | $/min |
|---|---:|
| `ubuntu-latest-4-core-gpu` | 0.052 |
| `windows-latest-4-core-gpu` | 0.102 |

> ⚠️ GitHub revised pricing in 2024–2025. The old folk wisdom of "2× Linux for Windows, 10× for macOS" is no longer accurate — macOS in particular dropped significantly. Always reference the live page if you need treasury-grade numbers.

## Dashboard

`cicd-optimizer analyze --html out/dashboard.html` generates a self-contained HTML file with:

- Cost & minutes wasted, **overall** and per workflow
- Top offenders ranked by estimated $/month
- Severity distribution donut
- Per-rule breakdown
- The exact YAML diff for every finding

Open the file in any browser. No web server needed.

If you want a live, refreshable view:

```bash
cicd-optimizer serve   # http://localhost:8765
```

## Use in CI

Gate PRs on net-new waste:

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with: { python-version: "3.12", cache: pip }
- run: pip install cicd-optimizer
- run: cicd-optimizer analyze --json --fail-over 10  # fail if >$10/mo of new waste
```

## Configuration

Drop a `.cicd-optimizer.yml` at repo root to tune severity, mute rules, override pricing,
or define your average monthly run count for forecast accuracy:

```yaml
pricing_overrides:
  ubuntu-latest: 0.008
  my-self-hosted: 0.0   # treat self-hosted as free
runs_per_month: 800     # for forecasting; otherwise derived from API
mute:
  - R012   # don't care about action version pins
severity_overrides:
  R004: low
```

## Architecture

```
src/cicd_optimizer/
├── cli.py             # click-based CLI
├── analyzer.py        # orchestrates parse → rules → cost → report
├── providers/         # GHA + GitLab YAML parsers
├── rules/             # individual detection rules (one file each)
├── pricing.py         # runner cost model
├── collectors/        # GitHub API run-history fetcher
├── refactor.py        # YAML auto-patcher
├── report/            # rich/json/html reporters
└── templates/         # HTML dashboard template
```

## Contributing

Issues and PRs are very welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and our open
[issues](https://github.com/mrckurz/cicd-optimizer/issues). A good place to start is writing a
new rule — the [`rules/`](src/cicd_optimizer/rules/) directory has examples.

## License

[Apache 2.0](LICENSE) — see `LICENSE` for the full text.

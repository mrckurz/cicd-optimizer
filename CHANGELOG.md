# Changelog

All notable changes to this project will be documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release: static analyzer for GitHub Actions and GitLab CI.
- 15 built-in detection rules covering caching, runner sizing, concurrency, matrix bloat,
  Docker layer cache, sharding, path filters, and more.
- Pricing model with GitHub-hosted runner rates (overridable).
- Three reporters: rich terminal, JSON, and a self-contained HTML dashboard.
- Live local web dashboard via `cicd-optimizer serve`.
- Auto-refactor patches (`--fix`).
- GitHub API run-history collector for $/min estimates from real runs.
- Configuration via `.cicd-optimizer.yml`.

## [0.1.0] - 2026-05-20

First public release.

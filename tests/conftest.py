"""Pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

# Make ``src`` importable without an install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

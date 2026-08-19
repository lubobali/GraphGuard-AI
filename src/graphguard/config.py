"""Paths and settings, resolved from the environment rather than hardcoded.

Reproducibility rule: no path is baked into code. Every location is derived
from the repo root or overridden by an environment variable, so the same code
runs on this box, in CI, and in a container without edits.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = Path(os.environ.get("GRAPHGUARD_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
SPLITS_DIR = DATA_DIR / "splits"

# The dataset we start on. HI-Medium and HI-Large come later.
DATASET = os.environ.get("GRAPHGUARD_DATASET", "HI-Small")

TRANSACTIONS_FILE = RAW_DIR / f"{DATASET}_Trans.csv"
PATTERNS_FILE = RAW_DIR / f"{DATASET}_Patterns.txt"
ACCOUNTS_FILE = RAW_DIR / f"{DATASET}_accounts.csv"

# MLflow tracking server. Bound to localhost only; nothing is exposed publicly.
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5010")
MLFLOW_EXPERIMENT = os.environ.get("GRAPHGUARD_EXPERIMENT", "graphguard")

# Fixed everywhere a random choice is made. Reproducibility rule.
SEED = 42

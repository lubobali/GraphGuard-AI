"""The S6.3 proof on the REAL validation window: ~1.0M events through the updater, every
history feature of every row equal (==) to training. Slow (~2 min, ~2.1 GB); needs the
dataset. Train + validation rows only. The same replay through a throwaway Redis:
`python -m graphguard.stream.proof --redis URL` (measured 2026-11-21: 0 mismatches,
6,038 events/s, 224 MB of Redis data at peak).
"""

import pytest

from graphguard.config import TRANSACTIONS_FILE
from graphguard.stream import proof
from graphguard.stream import updater as up

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not TRANSACTIONS_FILE.exists(), reason="dataset not downloaded"),
]


def test_the_whole_validation_window_replays_to_trainings_features():
    training, seed = proof.load()
    store = up.MemoryStore()
    up.seed(store, *seed)
    result = proof.replay(store, training)
    assert result["events"] > 1_000_000
    assert result["statuses"] == {"applied": result["events"]}
    assert result["mismatches"] == 0, result["first"]

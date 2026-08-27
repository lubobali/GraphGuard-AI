"""What gets deployed: the model plus everything needed to use it correctly.

A served model is not just weights. It is weights, the exact feature order the
weights expect, and the category encodings fitted at training time. Ship the
weights alone and the service will score columns in the wrong order and return
confident nonsense -- no error, no warning, just wrong numbers.

Saved as a directory rather than a pickle so the model file is XGBoost's own
format, readable by any version, and the metadata is JSON a human can open.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl
import xgboost as xgb

MODEL_FILE = "model.json"
META_FILE = "metadata.json"


@dataclass
class ModelBundle:
    model: xgb.XGBClassifier
    feature_columns: tuple[str, ...]
    category_maps: dict[str, dict[str, int]]
    trained_on: str

    def save(self, directory: str | Path) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        self.model.save_model(directory / MODEL_FILE)
        (directory / META_FILE).write_text(
            json.dumps(
                {
                    "feature_columns": list(self.feature_columns),
                    "category_maps": self.category_maps,
                    "trained_on": self.trained_on,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return directory

    @classmethod
    def load(cls, directory: str | Path) -> ModelBundle:
        directory = Path(directory)
        meta = json.loads((directory / META_FILE).read_text())

        model = xgb.XGBClassifier()
        model.load_model(directory / MODEL_FILE)

        return cls(
            model=model,
            feature_columns=tuple(meta["feature_columns"]),
            category_maps=meta["category_maps"],
            trained_on=meta["trained_on"],
        )

    def to_vector(self, row: dict[str, float]) -> np.ndarray:
        """Order a feature dict the way the model expects.

        A missing feature raises rather than defaulting to zero. Silently
        zero-filling a feature is how a serving path drifts from training
        without anything failing -- measured at an 83% cost in FINDING-008.
        """
        return np.array([row[c] for c in self.feature_columns], dtype=np.float32)

    def score_frame(self, frame: pl.DataFrame) -> np.ndarray:
        matrix = frame.select(self.feature_columns).cast(pl.Float32).to_numpy()
        return self.model.predict_proba(matrix)[:, 1]

    def score_one(self, row: dict[str, float]) -> float:
        vector = self.to_vector(row).reshape(1, -1)
        return float(self.model.predict_proba(vector)[0, 1])

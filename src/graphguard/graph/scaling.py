"""Feature scaling for the GNN.

XGBoost is scale-invariant: a tree splits on order, so a column in the billions
and a column in [0, 1] cost it nothing. A neural network is not. Handed
`sender_amount_sent_before` raw, the first forward pass produced a loss of
1.4e8 and learned nothing.

So the GNN needs scaling that the tabular model did not. Two properties matter:

**Statistics come from training data only.** Fitting on the full frame would
let the validation distribution shape the transform, which is a small leak of
exactly the kind contract rule 3 exists to stop.

**log1p before standardising.** These columns are heavy-tailed -- account
degree spans 0 to 169,756 (FINDING-002) -- and standardising a raw heavy tail
leaves almost every value squashed near zero with a handful of huge outliers.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True)
class EdgeScaler:
    mean: dict[str, float]
    std: dict[str, float]

    @classmethod
    def fit(cls, train: pl.DataFrame, columns: tuple[str, ...]) -> EdgeScaler:
        prepared = cls._prepare(train, columns)
        mean, std = {}, {}
        for c in columns:
            col = prepared[c]
            mean[c] = float(col.mean() or 0.0)
            # A constant column has std 0; dividing by it gives inf. Guard it.
            s = float(col.std() or 0.0)
            std[c] = s if s > 1e-9 else 1.0
        return cls(mean=mean, std=std)

    def transform(self, df: pl.DataFrame, columns: tuple[str, ...]) -> pl.DataFrame:
        prepared = self._prepare(df, columns)
        return prepared.with_columns(
            [((pl.col(c) - self.mean[c]) / self.std[c]).alias(c) for c in columns]
        )

    @staticmethod
    def _prepare(df: pl.DataFrame, columns: tuple[str, ...]) -> pl.DataFrame:
        """Nulls to zero, then log1p on non-negative magnitudes."""
        return df.with_columns(
            [
                pl.when(pl.col(c).is_null() | pl.col(c).is_nan())
                .then(0.0)
                .otherwise(pl.col(c))
                .cast(pl.Float64)
                .alias(c)
                for c in columns
            ]
        ).with_columns(
            [
                pl.when(pl.col(c) > 0).then(pl.col(c).log1p()).otherwise(pl.col(c)).alias(c)
                for c in columns
            ]
        )

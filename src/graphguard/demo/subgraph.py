"""The ring as it looked at the moment of the alert (S7.5).

Only transactions strictly before the alert in the project's order -- (time, source_row),
the order the features use (FINDING-010) -- inside the 72 hours before it. The view follows
the money two hops: who paid the sender and who paid them (upstream), whom the receiver paid
and whom they paid (downstream), plus the sender's other payees and the receiver's other
payers. A hub keeps its `cap` most recent edges per direction; the rest become one "+N more".
No labels: ring membership belongs to the answer key (S7.8).
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import polars as pl

WINDOW = dt.timedelta(hours=72)  # a ring spans a median of 3 days (FINDING-002)
CAP = 6


def _node(bank, account) -> str:
    return f"{int(bank)}:{account}"


class EdgeIndex:
    """Transactions in the project's order, with per-account positions for fast as-of
    lookups. Built once; each subgraph is then a few binary searches."""

    def __init__(self, edges: pl.DataFrame):
        df = edges.sort("timestamp", "source_row")
        self.df = df
        self.ts = df["timestamp"].to_numpy()
        self.ids = df["source_row"].to_numpy()
        self.pos_of = {int(i): p for p, i in enumerate(self.ids)}
        # one shared string per account (2.2M rows, ~0.5M accounts): memory, not semantics
        pool: dict[str, str] = {}
        self.frm = [pool.setdefault(n, n) for n in self._nodes(df, "from")]
        self.to = [pool.setdefault(n, n) for n in self._nodes(df, "to")]
        self.out_pos: dict[str, list[int]] = {}
        self.in_pos: dict[str, list[int]] = {}
        for p, (f, t) in enumerate(zip(self.frm, self.to, strict=True)):
            if f == t:  # reinvestment / self-transfer: not part of the expansion
                continue
            self.out_pos.setdefault(f, []).append(p)
            self.in_pos.setdefault(t, []).append(p)
        self.out_arr = {k: np.array(v) for k, v in self.out_pos.items()}
        self.in_arr = {k: np.array(v) for k, v in self.in_pos.items()}
        # numbers as arrays (Python lists of 2.2M floats cost ~0.5 GB, S7.5); the stream's
        # rank/score where the edge is a validation transaction (else -1 / NaN)
        has = "rank" in df.columns
        self.rank = df["rank"].fill_null(-1).to_numpy() if has else None
        self.score = df["score"].fill_null(float("nan")).to_numpy() if has else None
        self.amount = df["amount_paid"].to_numpy()
        self.currency, self.currency_names = self._codes(df["payment_currency"])
        self.fmt, self.fmt_names = self._codes(df["payment_format"])

    @staticmethod
    def _codes(col: pl.Series) -> tuple[np.ndarray, list[str]]:
        names = sorted(col.unique().to_list())
        return col.cast(pl.Enum(names)).to_physical().to_numpy(), names

    @staticmethod
    def _nodes(df: pl.DataFrame, side: str) -> list[str]:
        return (
            df.select(
                pl.col(f"{side}_bank").cast(pl.Int64).cast(pl.Utf8)
                + pl.lit(":")
                + pl.col(f"{side}_account")
            )
            .to_series()
            .to_list()
        )

    def recent(self, node: str, direction: str, lo: int, hi: int, cap: int):
        """Positions in [lo, hi) for `node`'s edges in `direction`, newest `cap` first-kept,
        and how many more there were."""
        arr = (self.out_arr if direction == "out" else self.in_arr).get(node)
        if arr is None:
            return [], 0
        a, b = np.searchsorted(arr, lo), np.searchsorted(arr, hi)
        sel = arr[a:b]
        return sel[-cap:].tolist(), max(0, len(sel) - cap)


def subgraph(index: EdgeIndex, alert_id: int, cap: int = CAP):
    p = index.pos_of[int(alert_id)]
    t = index.ts[p]
    lo = int(np.searchsorted(index.ts, t - np.timedelta64(int(WINDOW.total_seconds()), "s")))
    hi = p  # strictly before the alert in (time, source_row) order
    sender, receiver = index.frm[p], index.to[p]

    roles: dict[int, str] = {p: "alert"}
    more: list[dict] = []

    def take(node, direction, role):
        got, extra = index.recent(node, direction, lo, hi, cap)
        for q in got:
            roles.setdefault(q, role)
        if extra:
            more.append({"node": node, "direction": direction, "count": extra})
        return got

    # Downstream first: in a loop (S -> R -> D -> S) an edge is both "after the receiver"
    # and "before the sender"; following the alert's money forward is the story.
    for q in take(receiver, "out", "downstream"):
        take(index.to[q], "out", "downstream 2")
    for q in take(sender, "in", "upstream"):
        take(index.frm[q], "in", "upstream 2")
    take(sender, "out", "sender's other payees")
    take(receiver, "in", "receiver's other payers")

    edges, nodes = [], {}
    for q in sorted(roles):
        f, to = index.frm[q], index.to[q]
        nodes.setdefault(f, None)
        nodes.setdefault(to, None)
        e = {
            "id": int(index.ids[q]),
            "from": f,
            "to": to,
            "t": str(index.ts[q].astype("datetime64[s]")).replace("T", " "),
            "amount": float(index.amount[q]),
            "currency": index.currency_names[int(index.currency[q])],
            "format": index.fmt_names[int(index.fmt[q])],
            "role": roles[q],
        }
        if index.rank is not None and index.rank[q] >= 0:
            e["rank"], e["score"] = int(index.rank[q]), float(index.score[q])
        edges.append(e)
    seed = {sender: "sender", receiver: "receiver"}
    return {
        "alert": int(alert_id),
        "as_of": str(t.astype("datetime64[s]")).replace("T", " "),
        "window_hours": int(WINDOW.total_seconds() // 3600),
        "cap": cap,
        "nodes": [{"id": n, "seed": seed.get(n)} for n in sorted(nodes)],
        "edges": edges,
        "more": sorted(more, key=lambda m: (m["node"], m["direction"])),
    }

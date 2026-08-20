# Model comparison — Phase 4

Required by the Phase 4 gate: a fair comparison against Phase 3 on precision@k
and pattern-level recall. All numbers on **validation**; the test window has
never been opened.

## The table

| Model | Features | Tuned | PR-AUC | p@1000 | Rings @5000 |
|---|---|---|---|---|---|
| random | — | — | 0.00107 | 0.000 | 0 / 168 |
| rank by amount | — | — | 0.00170 | 0.001 | 0 / 168 |
| MLP, graph off | 14 artifact-free | 20 trials | 0.01869 | 0.085 | 34 / 168 |
| **GraphSAGE** | 14 artifact-free | 20 trials | **0.04470** | 0.111 | **60 / 168** |
| **XGBoost** | 15 artifact-free | 20 trials | **0.28155** | 0.332 | **127 / 168** |

Both models received the same feature set, the same frozen split, the same
`evaluate()` entry point and the same 20-trial Optuna budget.

## What the comparison shows

**The graph earns its place, and the margin is measurable.** Across the search,
12 trials ran with message passing enabled and 8 with it disabled. Best with
the graph: 0.06198. Best without: 0.01869. Same features, same budget, same
architecture otherwise. Structure contributes roughly **3.3x** over the
features alone, and nearly doubles rings caught (60 vs 34).

**The tuned tree still wins by about 6x.** This is consistent with the wider
literature: gradient-boosted trees dominate neural networks on tabular
features, and our features are tabular. The graph adds signal, but not enough
to close a gap that large at this scale.

**The single most important hyperparameter was `pos_weight`.** It was initially
fixed at the exact class ratio, 1326, which is correct for XGBoost's
`scale_pos_weight` and catastrophic for gradient descent: the loss became
almost entirely about 2,296 positive rows out of three million, and the model
learned nothing useful. Optuna chose **6.34**, and PR-AUC improved roughly
**8x**, from 0.0075 to 0.062. That difference between the two model classes --
one indifferent to class weighting, one destabilised by it -- was the largest
single effect found in this phase.

**Neural training needed scaling the tree did not.** Handed the raw parity
features, the first forward pass produced a loss of 1.4e8, because
`sender_amount_sent_before` runs into the billions. A tree splits on order and
does not care. This is another concrete way the comparison is not
apples-to-apples at the implementation level even when the inputs are
identical.

## Honest caveats

**The GNN's result is noisy; the tree's is not.** The same parameters produced
0.0447 standalone and 0.06198 inside the search, a difference attributable to
dropout RNG state. The tree reproduces exactly. The table quotes the lower,
reproducible number.

**Day-granularity snapshots are coarse.** A transaction is scored against a
graph frozen at the start of its day, so it cannot see same-day neighbours,
while XGBoost's history features are exact to the second. Rings complete in a
median of 3.1 days (FINDING-003), so a substantial part of the structure a ring
eventually forms does not exist yet at scoring time. A continuous-time model
(TGN or similar) would not have this handicap. This is the most likely place a
better GNN result is hiding, and it is a known limitation rather than a
disproven hypothesis.

**More training made it worse.** At 8 epochs and 300k rows/day the same
parameters scored 0.0473 against 0.0447 at the tuned 3 epochs / 120k. The GNN
overfits the training window quickly.

## Verdict

The graph model does not beat a well-built tabular baseline at this scale, and
it is not close. That is the result, and it is reported as one rather than
tuned away against the test set.

What can be said with evidence, and matters more than the headline:

1. Graph structure **does** contribute — 3.3x over identical features without it.
2. The gap is a model-class gap on tabular features, not a failure of the graph.
3. The dominant cause of the GNN's early failure was a hyperparameter that is
   correct for trees and wrong for neural networks, found only by giving both
   models the same search budget.

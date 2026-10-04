# I07.var02 — scheduled stock reorder size

This bounded matched pair derives from the accepted E15 v1.0.1 default-on-hand
stock arm. Both inputs have one tracked discardable DU at a depot with nominal
and opening on-hand stock four, ROSIZ two, and a one-hour reorder lead. The
control has an all-null `ChangesStockAllocation` placeholder. The child alone
sets the existing depot ROSIZ to one at h5. Everything else, including the h10
ordinary demand, is identical.

The native h5 change places no order and moves no stock. The shared h10
demand sends physical DU ID0 from depot to base, lowering depot on-hand from
four to three. Control stays above its reorder point of two and starts no
order. The child reaches its new point of three, starts one order at h10,
and receives one **new** DU, ID6, at the depot at h11. The common ID0 reaches
the base at h12 in both arms. The selected 72 half-hour depot results retain
nominal stock four, show no backorder, and end with on-hand three in control
and four in the child. Mission, system, and aggregate stock results are equal;
this pair does not show a readiness improvement.

`build.py` verifies and reconstructs the byte-pinned inputs. The guarded
session-0 SSH runner completed eight serial CLI steps while preserving the
protected GUI. `validate.py` checks the 22 authored populated tables against
their native exports, all raw source and run seals, exact converter warnings,
physical stock events and snapshots, selected depot bins and paired business
results. The native export has additional null placeholder rows. Raw SXI,
SXO, logs and reports remain in ignored local `runs/` and are pinned in the
published `evidence-index.json`.

Scope: one fixed seed, one stock-based DU reorder point, one h5 ROSIZ change,
one later h10 demand, and a 36-hour horizon. This does not establish the
behavior of an already outstanding order, the time-based strategy, multiple
orders, other stocks, GUI presentation, cross-engine equivalence, or the full
I07 and Issue #18 contracts. The local v1.0.0 explicit-three draft was never
run or published.

# I02.var14 — both transfer endpoints `<OUTSIDE>`

The installed 2017 SIMLOX manual says an `ItemTransfer` may not set both
`STFID` and `STTID` to `<OUTSIDE>`. This case tests that boundary against the
accepted I02.var01 one-unit h4 IN source. It changes only the target field
from `DEPOT-01` to `<OUTSIDE>` and the description. The other 30 tables,
stock, seed, missions, collection and horizon stay fixed.

The installed CLI imports and exports all 22 populated authored tables
exactly, including the double-`<OUTSIDE>` row. Calculation reports zero
conversion errors and produces a valid output, but the native log contains
no h4 scheduled transfer. The accepted IN parent increases DEPOT-01 nominal
and on-hand stock from one to two at h4; this child stays at one. In all 64
half-hour bins from h4 through h36, its `ItemResults.STSZ` and `STOHA` are
one lower than the parent. Its terminal depot stock is one versus the
parent's two. Selected mission, system, aggregate stock and summary tables
match; ordinary demand at h10 uses the original depot item in both arms.

The initial v1.0.0 local probe predeclared rejection, but the converter
accepted the model, so its runner stopped before report and roundtrip
checks. That sealed probe is excluded from this publication. The v1.0.1
candidate reruns the same source under the full guarded native/report gates.
Its two accepted closures seal 14 raw files under ignored `runs/`. The
source, closure and local raw fingerprints are in `evidence-index.json`;
`validate_native.py` and `review/independent_readonly.py` replay the result
separately.

This is a counterexample for one installed CLI build, model, seed and h4
row. It is not a recommendation to use a manual-prohibited input or a
general guarantee that such rows are silently ignored. GUI rendering and
cross-engine parity remain unverified.

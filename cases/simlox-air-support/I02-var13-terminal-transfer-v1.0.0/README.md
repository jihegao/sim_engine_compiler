# I02.var13 — transfer states at the simulation endpoint

This package freezes two short-horizon children of accepted I02 transfers.
`transit` derives from I02.var04: one tracked item enters DEPOT-01 at h4,
then another depot item departs on a two-hour BETWEEN transfer at h6. The
simulation ends at h7, before the scheduled h8 arrival. `backorder` derives
from I02.var05's zero-source case: the h2 BETWEEN request finds no depot
item, and the simulation ends at h3 before its accepted h4 IN can clear the
transfer backorder. Both children use one h0 scheduled profile row with
`IQTY=0`, preserving the referenced profile while suppressing later missions.

In the transit run, native event log ID 0 leaves DEPOT-01 at h6, and there is
no target receipt before h7. Depot ItemResults finishes with nominal/on-hand
1/1 and BASE-01 with 0/0. The ledger is initial depot 1 plus h4 IN 1 equals
terminal depot 1 plus one in transit. In the backorder run, the h2 task
arrives with zero items; the native log adds one transfer backorder and never
removes it before h3. Depot ItemResults remains 0/0. BASE-01 nominal `STSZ`
rises to 1 at h2 although its on-hand `STOHA` stays zero. Ordinary `NBO`
remains zero; the transfer backorder is observed in the event log, not that
ordinary-backorder report field.

The two guarded session-0 native runs and four report-only station exports
are sealed under ignored `runs/`. `build.py` and `describe_diff.py` reproduce
and assert the parent changes; `validate_native.py` replays source, event,
report, guard, closure and terminal-ledger checks. `review/` contains a
separate read-only replay. `evidence-index.json` identifies local raw paths
and SHA-256 fingerprints without publishing proprietary model files.

These are two separately parented endpoint examples with one IID, two
stations, seed 1, no mission initiation, and h7/h3 horizons. They do not
establish transfer behavior under active aircraft demand, a general horizon
rule, GUI rendering, or cross-engine parity.

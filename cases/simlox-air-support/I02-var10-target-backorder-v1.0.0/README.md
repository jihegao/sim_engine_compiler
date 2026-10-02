# I02.var10 — transfer arrival with or without target backorder

This matched pair derives from accepted I02.var03: one tracked LRU enters
`DEPOT-01` at h4 and a zero-duration one-unit BETWEEN transfer goes to
`BASE-01`. The two arms change only scheduled `TFTIME` to h9 or h11,
plus description. Ordinary aircraft item demand occurs at h10 in both.

EARLY delivers physical ID 0 to BASE-01 at h9, placing it in stock before
the demand. The aircraft receives that local item at h10; no target
backorder forms. LATE has an ordinary BASE-01 backorder from h10 to h11.
Its scheduled BETWEEN transfer brings physical ID 1 at h11 and removes
the backorder, supplying the waiting aircraft directly. BASE-01 nominal
stock rises to 1 at h11 but on-hand remains 0. A distinct ordinary depot
shipment of ID 0 reaches BASE-01 at h12 and raises on-hand to 1.

The two guarded session-0 native runs and four report-only station exports
are under ignored `runs/`. `build.py` and `describe_diff.py` freeze the
parent and pair deltas; the report settings generator recreates local
proprietary selectors from the fingerprinted installed default.
`validate_native.py` and the independent `review/` checker replay events,
station ItemResults, source hashes, closures and raw seals without running
SIMLOX. `evidence-index.json` identifies the local raw paths and SHA-256s.

This demonstrates one target backorder and one no-backorder arrival in
this fixed stock and demand geometry. The scheduled time also changes when
the aircraft obtains its replacement, so the case does not establish a
general queue-priority law, arbitrary backorders, positive transfer duration,
procurement, GUI rendering or cross-engine behavior.

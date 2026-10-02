# I02.var10 bounded CLI signoff — target backorder at transfer arrival

**Accepted parent and matched source:** The accepted I02.var03 one-unit
BETWEEN source has an h4 one-unit IN to `DEPOT-01`, followed by a
zero-duration transfer to `BASE-01` at h6. This pair moves only the latter
`TFTIME` to h9 (EARLY) or h11 (LATE), plus description; the h4 IN row and
30 other tables are unchanged. Parent source SHA-256 is
`4842382bd3728f7f9520d3b20e1ad7148f7436f5132e9cc933773550d64b4560`;
EARLY and LATE source hashes are
`ed117928b3e82c8194d0d7f56fc5fe43d0fdbf0f71c400813ad67644ae0d4e84`
and `5f342138a74e6453822b17684741af13ef3e5aa694d036455dfdcce53cd666f8`.
The exact-diff hash is
`4a7573fe4339508164cd53935aeb2861d9f62b153ff1979c00e2571d0335e932`;
the arms differ only in BETWEEN `TFTIME` 9→11 plus description.

Two serial guarded session-0 SSH runs preserved GUI PID 13340, completed
all five native steps each, converted with zero errors and exactly
round-tripped 22 populated authored tables per arm. Four report-only
exports from the sealed SXOs supply 72 half-hour `ItemResults` rows for
BASE-01 and DEPOT-01 in each arm. Six closures seal 32 local raw files.
The raw files and proprietary report selectors remain local, ignored by
Git, with paths and SHA-256 hashes in `evidence-index.json`.

EARLY’s h9 transfer draws depot ID 0 and stocks BASE-01 before ordinary
h10 demand. The aircraft consumes local ID 0 at h10, and no BASE-01
backorder forms. Depot ID 1 is separately issued for ordinary resupply
at h10 and stocks BASE-01 at h12. EARLY aircraft readiness returns h10.5.

LATE’s h10 ordinary demand creates BASE-01 backorder 1. Depot ID 0 is
already en route by ordinary transport. At h11 the scheduled BETWEEN
transfer draws depot ID 1 and arrives at BASE-01; its physical log removes
the one-hour backorder and gives ID 1 directly to the waiting aircraft.
The h11 BASE-01 item bins have nominal `STSZ=1`, on-hand `STOHA=0` and
`NBO=0`, after h10/h10.5 bins with `NBO=1`. The separate ordinary ID 0
arrives h12 and stocks BASE-01, raising on-hand to 1. LATE aircraft
readiness returns h11.3333. Both arms end with BASE-01 and DEPOT-01
nominal/on-hand 1, zero backorders and one ready aircraft. Mission and
summary results match; their system readiness intervals differ. Horizon
ItemResultsTotal means are not terminal counts.

Author read-only replay passed 56/56 checks. Separate independent read-only
replay passed 895/895, verified all 32 raw seals and returned bounded GO.
Its checker and exact verdict are under `review/` and indexed in
`evidence-index.json`.

**Boundary:** This is one tracked IID, one unit transfer, two stations,
zero transfer duration, h9 versus h11 and one seed. Scheduled timing and
ordinary resupply differ together, so this proves the observed target
backorder service sequence, not a general priority rule. Other quantities,
multiple targets, positive duration, procurement, GUI visual behavior and
cross-engine parity remain unverified. I02 and Issue #18 remain open.

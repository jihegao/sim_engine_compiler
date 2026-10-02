# I02 coverage from the accepted transfer runs

This note maps the accepted I02 evidence to adjacent catalog variants. It
does not extend the simulator claims or replace the sealed case packages.

| Catalog variant | Status and direct evidence | Limit |
| --- | --- | --- |
| I02.var05, sufficient source | The accepted [I02.var03 BETWEEN case](I02-var03-between-transfer-v1.0.0/cli-scope-signoff-2026-10-02.md) moves one available depot item to base at h6 after h4 IN. | One zero-delay unit, one seed. |
| I02.var05, insufficient source | The accepted [request-three case](I02-var05-insufficient-between-v1.0.0/cli-scope-signoff-2026-10-02.md) has two depot items available at h6; IDs 0 and 1 move then and one transfer backorder waits. | One available-two/request-three condition. |
| I02.var05, zero source | The accepted [matched zero-source pair](I02-var05-zero-source-v1.0.0/cli-scope-signoff-2026-10-02.md) starts a one-unit h2 BETWEEN with no item, then h4 IN clears its transfer backorder and moves ID 0. | Transfer precedes a later IN; no standalone zero-stock result. |
| I02.var06, split transfer | In the request-three case, the native task moves IDs 0 and 1 at h6, then a second task moves repaired ID 2 at h13.1667. | One two-plus-one split. Arbitrary quantities and sources are unverified. |
| I02.var07, competition | In that same request-three case, a separate ordinary depot backorder begins h10. When repaired ID 2 returns h13.1667, the transfer backorder clears and ID 2 moves to base while the ordinary backorder remains. | One realized contention. General queue fairness and all priority classes are unverified. |
| I02.var09, nominal update at split times | In the request-three case, base native `ItemResults.STSZ` rises 0→3 at h6 although only two items arrive and one transfer backorder remains. In the zero-source child, base `STSZ` rises 0→1 at h2 with zero physical arrival and an open transfer backorder. | The catalog's literal per-completed-sub-transfer nominal timing expectation is contradicted by these installed-CLI observations. Physical arrival and nominal position must be recorded separately. |

The two accepted shortage packages each have exact source deltas, guarded
session-0 native runs, selected station-specific `ItemResults`, local raw
SHA-256 seals, author replay and independent read-only GO. The request-three
case has 16 raw seals and independent 1222/1222; the zero-source pair has
32 raw seals and independent 1717/1717. The physical and station ledgers
support only the fixed configurations above. I02.var08 and I02.var10–14
remain unverified. Issue #18 stays open.

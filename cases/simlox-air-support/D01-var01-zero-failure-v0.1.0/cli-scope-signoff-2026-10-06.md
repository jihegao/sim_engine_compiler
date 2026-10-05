# D01.var01 matched zero-FRT control: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope`, ready for a bounded
`reusable_published` entry. The child of the accepted D01 installed-LRU case
changes only `System.FRT` and `Item.FRT` **300000→0** and its description. All
other authored values across the 257-cell shape, one installed critical LRU, one physical local
spare, three scheduled two-hour missions, seed 1 and 36-hour horizon are
retained. The child input SHA-256 is
`f9b1d2120de85307458dfddd92f69d7fa4bec9dd7bc5ee88c06c99b9cc338786`.
The [contract](contract.json), [exact diff checker](check_parent_diff.py), and
[evidence index](evidence-index.json) define the boundary. Evidence-index
SHA-256: `a4c8a5dbd7f1a0ba2d0bd7624d09c27c28eee2ce3ef4cc2f7e253795ab55d60d`.

The single guarded session-0 SSH run
`d01-var01-zero-v010-ssh-20261006-01` held
`Global\SimloxIssue18NativeQueue` and preserved the responsive GUI PID13340,
session1 and exact start identity before and after each native step. Import,
export, authored-table roundtrip, calculation and JSON report completed. All
18 populated source tables roundtripped exactly. Conversion reported zero
errors, warning #108 for logging and warning #2053 for deliberately zero
`Item.FRT`, and zero notes. The [invocation](runs/d01-var01-zero-v010-ssh-20261006-01/invocation.json)
SHA-256 is `1ffde70a6033fb17ebfddb0b3f088225e43473a80573499914208b6048626475`;
the [closure](runs/d01-var01-zero-v010-ssh-20261006-01/closure.json) SHA-256 is
`a0e396e3cb454e35471fa25625d5adbaee89cdfe402f50a6b8412cb01f5d11fb`.
All 12 child and 12 accepted-parent raw size/SHA seals match; raw native
files remain in ignored local run directories.

The native log creates missions at h7, h19 and h31, launches at h8, h20 and
h32, and records success at h10, h22 and h34, with no additional mission,
abort, cancellation, ordinary failure, replacement demand or repair. The
opening physical spare is `TEACH-LRU-01` ID0 at `BASE-01`, level 1; the
complete event ledger records no stock transition. Terminal on-hand is
inferred from that ledger, not a terminal stock snapshot or report `PNB`
(an aggregate report field). All 72 half-hour `SystemResults` and 72
`StockTotalResults` rows align with this timeline: **6 flight aircraft-hours**,
**27 ready aircraft-hours**, **36 available aircraft-hours**, zero
failure/repair/demand/backorder counters and one terminal ready aircraft.

The original prelaunch validator was rejected and its
[NO_GO review](review/independent-prelaunch-no-go-2026-10-06.md) remains
preserved. The corrected prelaunch package received a separate
[GO addendum](review/independent-prelaunch-go-addendum-2026-10-06.md).
The native runner pinned `validate_native_cli_v011.py`; its first read-only
[author replay](review/author-validation-v011.json) failed **53/54** only
because that checker looked up the old validator filename (SHA-256
`a4606aab12f88fa8523dad68bb6843f03bc42a7bd71b232b63f18c991b5cf9d7`).
The separate `validate_native_cli_v012.py` corrects the filename lookup
without changing the native run; its [replay](review/author-validation-v012.json)
passes **54/54**. A separately authored [independent replay](review/independent-verdict.json)
and [postrun review](review/independent-static-postrun-2026-10-06.md)
pass **496/496** and return `GO_BOUNDED`.

**Limits:** Both rates changed together, so this case does not isolate either
field. One seed, one executable and one quiet mission schedule do not prove
general zero-failure behavior, other mechanisms, or cross-engine parity.
GUI visual behavior remains unverified. K01/K08 capture blockers, I07
opening-stock-three and E05.var02 exact-time diagnostics remain excluded.
D01 and Issue #18 overall remain unfinished.

# P1 dependency and acceptance gate review — 2026-09-28

## Source and frozen parents

The working branch `codex/simlox-p1-a03-gates` was fast-forwarded to the
verified remote `simlox/main` head `7fc4bee941e18f708b4bd99366e07001b5645165`
before this report. The local proxy could not reach GitHub, so the head was
queried and fetched through 4700-3, transferred in a hash-checked incremental
Git bundle, and fast-forwarded locally. The A03 files do not overlap the 24
new mainline commits.

The native A03 bundle was executed while the local tracking ref still named
`89b904c7dcedea6d1d08434b3c0d5738a7a720f6`; after the fast-forward,
the A03 input, contract, runner and validator bytes are unchanged. The
execution bundle hash and exact source hashes remain in the evidence index.

All 19 frozen A01/A02 files still match their exact size and SHA-256 in
`catalog-import-source-v2.json`; neither case directory differs from the
updated `simlox/main`. On 4700-3 the four historical A01/A02 closure files
still match their published hashes, including each final and replay run.
This confirms preservation of the frozen source and closures. It does not
add GUI evidence or expand the parents' prior CLI behavior scope. Six shared
catalog/documentation/tool files in the broader import list have evolved since
that snapshot; they are outside the 19 frozen parent files.

## A03 candidate

Parent: `A02@1.0.0`, native input SHA-256
`84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8`.
The candidate input SHA-256 is
`51e3f99ecf86e05e35dce2b2c9e062b483a2c0f3dd64625761bc64c45900cce6`.
Its only changed tables are `SystemDeployment`, `MissionType` and
`OperationProfile`: two deployed aircraft, `NOS=MNOS=2`, one 08:00 wave.
The builder, row diff, contract, validator and GUI checklist are in
`A03-two-aircraft-formation/`.

On 4700-3, SIMLOX executable SHA-256 remained
`fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`.
The final isolated run `probe-a03-20260928-03` completed import, export,
calculation and report export with zero errors and only explained warnings
`#108` and `#126`. Nonempty business rows survived the JSON roundtrip.
Raw ENLOG shows one mission tag, two distinct allocations, one launch at
08:00 listing both aircraft, and completion at 10:00 listing both. The
half-hour SystemResults show `FTMO=1` and `NSYMO=2` during 08:00–10:00:
two mission-hours and four aircraft-hours are different measures. The
read-only local replay of the transferred raw archive passed with no
differences; the remote SIMLOX process count after sealing was zero.

The first probe is retained as a failed validator result because it wrongly
expected `FTMO=2`; it did not expose a native model failure. A second probe
passed the corrected metric check. The final third probe additionally binds
the exact warning set and ordered/success events. All three original archives,
hashes and run IDs are in `A03-two-aircraft-formation/evidence-index.json`.
Final archive SHA-256:
`55cc457b056be7510be117bd2a5bda30a9fe2f5fa7b27e0bc587b56b275d5b73`.

**A03 status:** `isolated_contract_cli`, `publication_state=not_published`,
`prerequisites_state=not_all_published`, `gui_status=not_run`. These CLI
results are an isolated capability check, not the formal parent-dependent
case acceptance.

## GUI and serial queue

The 4700-3 Windows user session was disconnected (`quser`), and the available
GUI control inventory contained no apps or browsers. A01/A02 GUI calibration
and A03 GUI review therefore remain open. The exact A01/A02 screenshot checks
are in `handoff-v1/gui-checklist.json`; A03 checks are in its own
`gui-checklist.json`. No screenshot or observed menu path has been invented.

The formal 4700-3 queue remains closed until the frozen parent and A03 GUI
gates have reviewable evidence. Then rerun, serially and in fresh directories,
`B01 → B02 → C01 → C02 → C03`, checking each native input hash, GUI view,
resource request/acquire/release events, nonempty raw outputs, closure and
independent local replay. Handle `B03` separately after B02: prove only the
explicit `COLD-FIRST` and `HOT-SORTIE` task-type mapping, without claiming
automatic history-based switching. The prior 12/12 results retain only
`isolated_contract_cli` and cannot be promoted by changing a status field.

After P1, start C04 as a separate deadline/cancellation case. C03 staffing-0
cancellation at 08:30 is a fixed-profile observation before its 09:00
latest-launch bound, not a general cancellation rule. Task dependencies,
RBD, initial age and other batches follow the P1 exit gate.

## Subsequent review addendum — 2026-09-28 08:51 CST

An independent review found that the original source-bound A03 probe validator
did not check `ResultSummary.RTILW/RTIUP/MSTF/MSUF`. Its three historical
archives and `validate.py` remain unchanged. A new `validate_strict.py` checks
those fields and is bound by source hash in future runs. A read-only check of
the retained probe-03 raw report found no strict-summary difference; that
check does not relabel the historical run as a new formal acceptance.

The live session check at this time found an active `rdp-tcp#31` session and no
SIMLOX process. The earlier disconnected-session observation above remains a
historical observation; neither state proves a local `Console` executor. The
formal GUI queue therefore remains closed. P0 also includes K01/K02/K07/J05,
which are still planned: A01/A02 GUI calibration is only the minimum parent
gate for this P1 path, not completion of all P0 cases.

## RDP authorization and read-only preflight — 2026-09-28

The owner now authorizes using remote desktop for SIMLOX. The former
Console-only handoff no longer describes the permitted session, but permission
does not establish native execution capability or case acceptance. A read-only
check found active `rdp-tcp#35` session ID 1 and an existing `Simlox.exe` process
in that session. No second instance was launched. The revised candidate
runners accept a matching active interactive Console/RDP process and reject
SSH/session-0. The owner also separately authorized SSH CLI acceptance; that
path needs its own source-bound launch contract and does not supply GUI evidence.
The RDP path still needs a fresh native run, license observation,
GUI evidence, and independent replay. A01/A02/A03 status remains unchanged.

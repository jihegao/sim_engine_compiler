# B01 1.0.0 `fixed-30m`: bounded CLI review, 2026-09-29

This is a later, read-only case review under the [revised Issue #18 CLI
standard](../../execution-plan-v2.md#3-证据状态和阶段门). It leaves the frozen
1.0.0 contract, generated input, parent diff, run manifest, raw artifacts,
and 2026-09-27 independent review unchanged. Their `isolated_contract_cli`
and `not_published` fields record the original run gate; this review retains
the publication limit while accepting a narrower observed CLI behavior.
The [A01 normal-path sign-off](../../A01-single-aircraft-single-mission/cli-scope-signoff-2026-09-29.md)
supplies the required behavior parent only within its stated range.

## Decision

The one-aircraft, one-wave, deterministic B01 `fixed-30m` **observed
preparation execution** is `native_behavior_accepted_cli_scope` for this
frozen profile; `publication_state=not_published` remains in force. The native result establishes
one 30-minute positive-duration preparation for the assigned aircraft before
the 08:00 launch. It does not establish an invisible internal object-creation
count, a pure one-field causal difference from A01, or a general preparation
rule beyond this configuration. The D1 stable-business-ID gate and original
contract A1 creation-event requirement are not met, as detailed below, so
this record does **not** release B01 as a reusable parent for B02.

The run is `formal-b01-6539ea`, input SHA-256
`134bff623caa8554679121e2b876f25b9f14609faceca65872e90d0f3bdef804`,
under the frozen source root
`C:\Users\user\Documents\Codex\2026-09-27\simlox-preparation-resource-v1-6539ea720ef2`.
The raw directory is
`data\local\simlox-preparation-resource\v1\B01\fixed-30m\formal-b01-6539ea`
below that root. The SIMLOX executable SHA-256 is
`fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`.
The [remote evidence index](../remote-execution-v1/evidence-index.json) and
[independent run review](final-run-review.json) bind the input, invocation
`c6093af63011c3daa7dfe22e1cba66b81a1a1af539915980468a4382a70574f6`,
closure `5665d82ac9d17f2ea4a3891d6d78af3beae91746fcef462f2f68a8b9d4a852ab`,
validation `516a3f331861e056d6341a28e606cf1a15959e38b746367ef7656eb24c827241`,
and run manifest `4086c9ce6286ff2df7f05251549d4d058af18e984b41c256712b404e6d05c0cd`.
The source manifest and archive hashes are respectively
`6539ea720ef2b9c301889517da3cfdd8ff1eecfbb71dff48c32f85dbfd1bbe7a`
and `ca430b78ddb99936475419f92b455d971b2502311630b413732e6ffe7a057c66`.
In B01's raw closure, `model.log` is 2,976 bytes, SHA-256
`d056721559dcd787eac54b17eddaf2de9014678f4cede0704ef722eb011a9797`,
and `report-raw.json` is 40,832 bytes, SHA-256
`5713345ca1e11b2400336c75bceb0df09622ad721e5f7d70d8ecadc4a387bf86`.

The original 12-run independent review recomputed 144 closure-bound raw
artifact hashes, including B01's 12, and replayed every CLI check. A fresh
read-only B01 audit on 2026-09-29 again matched the 72-file frozen source
snapshot and B01's 12 raw closure entries. Import, JSON roundtrip,
calculation, and report export exited 0; conversion errors were zero;
warnings 108 and 126 were expected; all nonempty input business rows survived
roundtrip; the strict validator returned an empty difference list. The
historical `behavior_assertion_count=0` in `final-run-review.json` is a
reporting counter for the B01 validator path, not a claim that it skipped
behavior checks: those checks returned `behavior_status=passed` and are
spelled out below.

## Identity and A1–A5 readout

The [frozen contract](../contracts/B01.json) calls the one business aircraft
`AIR-01` and the one business mission `MISSION-01`. This input has exactly one
`AIR-TYPE` deployment (`QTYPS=1`) and one 08:00 `MISSION-BASIC` wave
(`IQTY=1`). Within this exact input and run, the event owner `AIR-TYPE,0`
maps to `AIR-01`, and the one `MISSION-BASIC` wave maps to `MISSION-01`.
Those source-bound mappings are not a promise that the native instance index
is stable when the deployment or schedule changes. The A01 contract instead
uses `TEACH-AIR-01` and `BASIC-MISSION` as its business IDs. The B01 1.0.0
contract changes both across the parent edge; a one-to-one mapping within
this B01 run does not satisfy the revised standard's D1 business-ID stability
requirement.

| Contract item | CLI evidence and accepted reading |
| --- | --- |
| B01-A1, bound preparation instance | The input has exactly one `MissionPreparation` row for `MISSION-BASIC`/`AIR-TYPE`/`BASE-01` and one `PREP-FIXED` task row. The event log has one aircraft preparation lifecycle, one system preparation task lifecycle, and one subtask lifecycle for the assigned owner and mission; the report has `NPSTA=NPSUC=1`. This proves one **observable execution**. The log does not expose a separate `prep-created` record or internal object count. |
| B01-A2, 450–480 min | Notice and preparation start occur at 07:30; the 30-minute work and preparation end occur by 08:00. |
| B01-A3, launch ordering | Preparation end precedes the 08:00 launch in log order; the same mission completes at 09:00. This is the observed ordering for this run, not a general same-time priority rule. |
| B01-A4, positive work | `NSYMP` integrates to 0.5 aircraft-hour, and the event log shows 0.5 h of performed preparation. This is actual positive-duration work in this native result; a zero-duration control remains deferred. |
| B01-A5, count and NOPER separated | `MissionType.NOPER=0.5 h` is an input parameter; `NPSTA=NPSUC=1` is the separate native count. The 07:30 notice is checked independently. No sensitivity experiment establishes a general `NOPER` rule. |

The report has 24 contiguous half-hour intervals over the 12-hour horizon,
one successful mission, and one aircraft-hour of mission operation from
08:00–09:00. No cancellation or resource wait occurred. The contract has no
resource demand and this review claims no personnel or equipment behavior.

The independent raw-file audit located the 07:30 notice in `model.log` line
7, the single mission creation in line 8, assignment in line 10, the single
aircraft preparation start in line 13, 0.5 h perform statement in line 18,
preparation and task completion in lines 22–24, launch in line 28, and
success/completion in lines 31–32. `report-raw.json` has the 07:30–08:00
`NSYMP=1`, `NPSTA=1` row at lines 879–920, `NPSUC=1` in the 08:00–08:30
row, and `FTMO=1` in both 08:00–08:30 and 08:30–09:00 rows. Counting all
24 raw intervals gives `NPSTA=NPSUC=1`, a 0.5 aircraft-hour preparation
integral, and a 1 aircraft-hour mission-operation integral. `input.json`
records `MissionType.NOPER=0.5` and the single `MissionPreparation` row.
These line references are to the frozen raw files in the run directory above,
not to a later pretty-printed copy.

The frozen validator checks the expected B01 start/end at 450/480 min and
the `NPSTA` interval count, but does not globally reject an additional
off-time preparation-start event or check `NPSUC`. The 2026-09-29 independent
review counted the **whole frozen raw log and all report intervals** for this
sign-off. Existing source tests reject missing/wrong-identity preparation
events and misplaced `NPSTA`; a future validator revision should add global
extra-event and `NPSUC` mutation checks before applying the same acceptance
procedure to a different run.

## Parent delta and limits

The frozen [parent diff](../parent-diffs/B01--fixed-30m.json) has an overly
narrow `declared_delta` sentence saying only that a 30-minute
`MissionPreparation` row was added. Its `actual_normalized_diff` is the
authoritative readout: **11 tables, 8 added rows, 6 removed rows, and 5 field
changes**. Besides `MissionPreparation` and `Tasks`, it changes
`ProblemDescription`, `Control`, `System`, `SystemDeployment`, `MissionType`,
`OperationProfile`, `Operations`, `Unit`, and `ResultCollection`. Specifically:

- `TEACH-AIR-01`/`TEACH-UNIT`/`BASIC-MISSION`/`BASIC-SCHEDULE` become
  `AIR-TYPE`/`PREP-UNIT`/`MISSION-BASIC`/`PREP-SCHEDULE`. These are one-to-one
  input identities in this fixed profile, not byte-preserved A01 IDs.
- Flight duration changes from 2 h to 1 h; `NOPER` from 1 h to 0.5 h;
  notice lead from 1 h to 0.5 h; the native `DTIM` field changes from 1/3 h
  to 1 h. `SIMPE`, `Control.RCEND`, and two result-collection end times change
  from 36 h to 12 h. The description and unit label also change.
- A 0.5 h scalar `MissionPreparation` row and its `PREP-FIXED` task row are
  added. They are the main new mechanism, but the old result cannot isolate
  their causal effect from all other changed fields or prove preparation
  delayed a launch relative to A01.

The original B01 contract's literal claim that a preparation instance is
*created once at notice time*, and its requested create/start/complete event
evidence, cannot be fully checked: the log has a mission-created event but no
separate preparation-created event or internal object count. A versioned
contract must narrow A1 to one observable execution or obtain creation
evidence before this case can be published. The frozen parent diff's
`declared_delta` also needs a versioned correction or full exception review.

This CLI review is limited to the observed fixed positive-duration path.
The zero-duration/no-preparation control, object creation internals, delay
cutoff, resource contention, changed `NOPER` behavior, random durations,
GUI-only interaction, Python/Rust/J35 equivalence, and performance remain
unverified. The frozen source snapshot must be used for exact reproduction:
the current repository's runner, binding, and README bytes have drifted from
the invocation's source-hash map. A fresh run must get a unique directory;
the preserved `formal-b01-6539ea` files must not be overwritten. Keep the
user's current SIMLOX GUI running; no rerun is needed for this historical
fixed-run review. A new B01 input or contract version requires new source
binding, a new run ID, and independent acceptance.

## Handoff for a publishable B01 revision

A possible B01 1.0.1 should derive from the checked A01 input without
renaming `TEACH-AIR-01`, `BASIC-MISSION`, `TEACH-UNIT`, or `BASIC-SCHEDULE`.
Keeping A01's 1 h notice, 2 h mission, 36 h horizon, and 30-minute result
interval allows a two-row candidate delta: add a 0.5 h
`MissionPreparation` row for `BASIC-MISSION`/`TEACH-AIR-01`/`BASE-01` with
`TID=PREP-FIXED`, and a matching `Tasks` row. The proposed observable
timeline is 07:00–07:30 preparation, 08:00 launch, and 10:00 completion;
it remains **unrun and unverified**. A versioned contract must assert
observable preparation starts, work, completion, identity, and count without
claiming an invisible creation event. Generate and review a true A01-to-B01
diff, run under a new source-bound ID, and independently replay raw evidence
before publication. The old `formal-b01-6539ea` run must remain intact.

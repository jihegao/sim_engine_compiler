# C03 shared-resource contract preparation

**Prepared and statically validated; every new native behavior is unverified.**
This independent branch starts at PR21 `861ce9e193046bc1c8cec276fdb85101044dbfaa`,
an **unmerged dependency**. It adds no engine code, Plan, native binary, SXI,
runtime trace or measured timing. The six JSON files are candidate native table
inputs, not successful native imports. Existing catalog statuses stay unchanged.
The scoped priority follows [issue #18's review](https://github.com/jihegao/sim_engine_compiler/issues/18#issuecomment-5853416248).

## Minimum dependency chain

| Case | Unique mechanism to establish | Candidate / still unknown |
|---|---|---|
| A01 | One scheduled mission, no preparation/resources | Existing CLI and bounded Python mapping accepted; GUI gate remains open. Reuse hours/minutes, notice/start/return and identity checking, not support semantics. |
| A02 | Reuse one aircraft for non-overlapping missions | Reuse evidence format and return/readiness checks only. It proves neither concurrent aircraft selection nor resource pools. |
| B01 (requires A01) | A positive fixed preparation trigger | One 10-minute task, no resources. Check TID activation, DURN and notice relationship. Deliberately **does not test resource consumption**. |
| B02 (requires B01) | Serial positive work durations | Adds a 40-minute second step. Confirm SEQ means effective serial work and preparation DURN agrees with, rather than adds to or overrides, the step total. |
| C01 (requires B02) | Personnel identity and quantity | One specialty RID, quantity 1 on **both** steps, capacity 2. Confirm release per step, not only numeric schema support. Specialty means RID/category mapping here. |
| C02 (requires C01) | Equipment plus personnel | Adds equipment quantity 1 on SERVICE, capacity 2. Confirm both resources are occupied and released when available. This single-job parent cannot prove holding while blocked or all-or-none acquisition under scarcity. |
| C03 (requires C02) | Waiting and release in a shared pool | Adds second aircraft and distinct scheduled mission; equipment capacity 1/2 variants. Two-instance selection and pool sharing are additional explicit gates. |

All B01–C03 entries are still `planned` in the existing catalog. This folder is
a preparation package, not a new accepted version of those cases. The candidates
for B01/B02 isolate temporal behavior before resources are introduced. Their
resource-free steps cannot satisfy C01/C02/C03 resource acceptance.

B01 uses a new common teaching scaffold (stable labels, one-hour flight,
12-hour horizon) rather than claiming a single-field native delta from A01.
Within this scaffold B02 changes only positive serial preparation structure;
C01 introduces personnel rows; C02 introduces equipment rows; C03 introduces
concurrency and then the explicitly checked capacity intervention. Do not call
the multi-instance identity gate A03 acceptance or broaden to the 26-case plan.

## Proposed common business contract

The versioned [contract](contract.json) is a proposed deterministic profile,
not a statement about default Python/J35 or SIMLOX internals. It requires
joint all-or-none acquisition of a step's resources and release on completion.
If native behavior differs, retain the counterexample and review the contract;
do not patch the default runtime or hide the difference with averages.

Two named business aircraft and missions receive notice at 420/440 minutes;
planned launch is 480/500. INSPECT consumes one specialist for 10 minutes;
SERVICE consumes one specialist and one shared device for 40 minutes. Personnel
capacity stays 2. Only the device capacity changes from 1 to 2. The source
specialty and equipment types are represented by distinct RIDs, not an invented
native `TYPE=PERSONNEL` value. `SPECIAL` is a previously observed native value.

| Event/interval (minutes) | Capacity 1 | Capacity 2 |
|---|---|---|
| A INSPECT | [420,430), personnel 1 | same |
| A SERVICE | [430,470), personnel 1 + device 1 | same |
| B INSPECT | [440,450), personnel 1 | same |
| B SERVICE request | 450 | 450 |
| B waiting | [450,470), owns neither resource | none |
| B SERVICE | [470,510), personnel 1 + device 1 | [450,490), personnel 1 + device 1 |
| A launch / return | 480 / 540 | same |
| B launch / return | 510 / 570 | 500 / 560 |
| B queue wait / launch delay | 20 / 10 | 0 / 0 |
| Personnel / equipment integrals | 100 person-min / 80 device-min | same totals |

The two [hand ledgers](hand-ledger-capacity-1.json) are authored expectations,
not model results. The checker validates serial durations, ownership, capacity,
non-idling, launch readiness and integrals. Identical totals are insufficient:
at 450+ capacity 1 must leave B queued without a SERVICE lease; at 470+ both
variants have B using the resources, but B has 40 versus 20 minutes remaining.

Intervals use `[grant, release)`. At a shared timestamp compare left and right
states separately and retain causal grant/release events. The contract says a
release must precede a grant that needs that unit; it does **not** assign a
native phase number or infer micro-order from decimal log timestamps.

### Deadline and observation boundaries

Nominal latest launch is 510 for A and 530 for B (`STIM + DTIM`, minutes).
Both main variants prepare strictly before their deadlines; they exercise no
cancellation/refund. This nominal mapping is not an accepted missing-aircraft
cutoff: PR15 showed that selected-aircraft resource delays and missing-aircraft
waits can differ. C04 remains outside scope.

`observe_ledger` inspects either side of a timestamp without changing a lease.
At 455, A is still servicing and B is queued in capacity 1: clipping a report
there must not fabricate a release, cancellation, completion or returned stock.
At 510- B still holds its SERVICE lease; at 510+ it has completed and launched
under the proposed contract. Native tie behavior remains a future probe.
Observation end, simulation horizon, launch deadline and work completion are
four distinct concepts. No short-SIMPE candidate is generated.

## Static reproduction

Python 3.9+ and stdlib only; no SIMLOX, runtime, database or credentials needed:

```sh
python3 cases/simlox-air-support/c03-contract-prep-v1/prepare.py --check
python3 -m unittest tests.conformance.test_simlox_c03_contract_prep -v
python3 cases/simlox-air-support/c03-contract-prep-v1/prepare.py --case C03 --capacity 1 --output /tmp/c03-cap1-new.json
```

The output command refuses an existing file. Use `--case B01/B02/C01/C02
--capacity 2` for parent candidates. The table writer reuses the pinned
`../tools/generate_native.py` schema helpers, without changing that generator's
frozen A01/A02 support. No second Project interpreter or canonical bridge exists
here. Candidate JSON intentionally repeats the existing native column schema;
the manifest gives exact hashes. `capacity_delta` rejects any other changed
field, including schedule, duration, other capacity or model description.
`validate_native` is deliberately closed to the six frozen candidates. It does
not certify arbitrary native models: type/reference checks give diagnostics,
then full candidate matching rejects hidden flags or distributions in otherwise
valid tables. [Format provenance](native-format-evidence.json) pins the two
retained 4700-3 files independently read back for `SPECIAL`, the known resource
row syntax and result-column names. Those old rows establish format evidence
only, not this contract's acquisition or sharing behavior.

## Native unknowns and next execution gate

1. Review this contract and candidate tables in the existing private GUI/model
   review flow. Do not start a CLI run or ask for a new connection in this slice.
2. Confirm `TaskBreakDown.SEQ`, effective duration, and whether subtask-only
   `SubTaskResource` activates/holds/releases resources with empty `TaskResource`.
   This is deliberately **blocked_unverified**; copying both demands could
   double-reserve or hold capacity across steps. Do not add arbitrary flags.
3. Confirm a `ResourceAllocation` row at `POINT=RESOURCE-AIR`, same site and
   `QTYPS=2` really represents one shared pool. Do not allocate one row per
   aircraft and accidentally double supply. Probe two-instance native identities
   and selection; all exact native instance mappings remain null until observed.
4. Sequentially accept B01, B02, C01 and C02 before C03. C01 needs positive
   per-step personnel usage; C02 needs both resources occupied and released in
   its available-capacity case. Scarcity behavior stays unverified until C03:
   its 450–470 queue interval must prove whether B holds neither resource.
   For each,
   seal input, roundtrip, binary/version, invocation, logs, result and checker
   before accepting behavior. Existing native validators only accept A01/A02;
   **do not run a new candidate through them and reuse their success labels**.
5. Only then run capacity 1 and 2 with exact one-field delta and fresh immutable
   directories, normal then independent replay, through the sole 4700-3 executor.
   Any missing lease/queue visibility is a mapping blocker, not a reason to infer
   it from ResourceResults totals. A new verified C03 checker is required.
6. Schedule separate before/tie/after completion versus deadline probes only
   after these gates. They must record actual cancellation/retention/release
   instead of presuming the C03 proposal establishes C04 semantics.

The future execution is **not authorized by this preparation artifact**. It
also needs the active task's authorization after the existing gates are met.
No new scheduler, Codex runner, GUI, SIMLOX, native replay or performance run
was created here.

## Minimum handoff to AMD128

Freeze this contract version and full file manifest on both sides first. Supply
the six input candidates, units/identities, both independent hand oracles, the
one-field capacity intervention, unknowns and parent status. AMD128 may inspect
the proposed mapping, but engine execution/pairing is a subsequent scoped task.
It must use the canonical integration and three IR layers; no Project JSON
shortcut, default-profile change, engine trace fabricated from this ledger, or
new Rust equivalence claim is permitted.

The native return must include full mission/aircraft identity binding, per-step
request/wait/acquire/release ledger with resource owner/count, step progress,
launch/return and left/right snapshots, source/roundtrip/native-tool identity,
raw ENLOG and report with raw and normalized hashes, collection semantics,
replay evidence and first difference. If native does not expose a field, list
it as unavailable and identify a controlled discriminating probe; do not fill
it from the hand ledger. `ResourceResults` columns exist in prior exports but
their occupancy/queue semantics are not accepted here.

Keep GUI pending, notification proxy, J35 wave20, 403 nested LRU and full
material-ledger blockers unchanged. This preparation does not close #18, join
#6, establish Rust/full F35/J35 equivalence or justify performance measurement.

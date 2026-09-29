# A01 1.0.0: bounded CLI behavior sign-off, 2026-09-29

This is a later, read-only review under the [revised Issue #18 delivery
standard](../execution-plan-v2.md#3-证据状态和阶段门). It does not alter the frozen
input, contract, acceptance record, or either native run. The older
`acceptance.json` records the status at its original review date.

## Decision and scope

The A01 normal 0–36 h, one-aircraft, one-scheduled-mission path is
`native_behavior_accepted_cli_scope` and `reusable_published` **only within
that declared path**. This range is an accepted behavior parent for cases
that require the A01 ready-aircraft baseline, including B01. It does not
pre-accept any B01 input, parent delta, or preparation behavior.

The source-bound native input is SHA-256
`8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7`;
the frozen contract is
`29d81aeadc5b138b07a3e6242fec8df74a768998c71d3ee0e5e4ca0bf45c7cb6`.
The two independent run directories under
`C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A01`
are `a01-bound-final-20260927-03` and
`a01-bound-replay-20260927-04`. The [evidence index](evidence-index.json)
records every raw path, size, hash, and the two invocation source-hash maps.
The [manifest](manifest.json) pins SIMLOX 2017.0.0.0, executable SHA-256
`fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`,
runner SHA-256 `f685a71e8a59d97c71a37ced9799be502fe531d5c61c4f4f666614f1dca1e22e`,
and binding SHA-256 `d7cb8cdb670d6ac24536254904d9ac527bee1cfa1d9954dca9bd6a7d9ca0c28a`.

| SHA-256 | Final | Replay |
| --- | --- | --- |
| `invocation.json` | `6e5d18919d34b36455384cb833d49efc69d06fc11645f167b4badb92d0d62d90` | `deb92bf529c2431d886ffefabd90826cc6b7f61bf109d8ba8a42657a9ca39313` |
| `closure.json` | `7e253f9acdeed55197e191530f7e9ad8d88abe387326fd7b4c5152da3529288e` | `3781103d253f08c6d3f8f84572877f6b65319a18c10a9e40736e608f829811ee` |
| `model.sxi` | `47cc6f3b7026affa210f17a9c77989ba661796cce5a1e09f0c4759ca2929d003` | same |
| `model.sxo` | `b22e832c44c5780ecd6b3e10ef0d4cedcafbd2ae66a02df70d6b75ba302876bf` | `83ced804cca264d724147241d27c0cdedc14e49e294000e86a743550b6e02fc8` |
| `model.log` | `6337dc631e574eb9fab1eb24c45b4a3e1568d7e645282051c234a032591887ed` | same |
| `report-raw.json` | `b9b7d970e7f12763f0098eb2d2c546cc2ed2b68792840e74f2175fcd4ca14099` | same |

An independent reviewer recomputed bytes and SHA-256 for all 34 files in
these two remote directories: 34/34 match the checked-in index. On 4700-3,
the reviewer reran `validate_native.py --read-only --case A01` against each
directory. Both returned `cli_behavior_verified`, `passed=true`, and an empty
differences list. All four native commands in each run exited 0, conversion
errors were zero, warnings 108/126 were accounted for, and roundtrip export
preserved all 10 nonempty business tables. The validator and runner are
source-bound in each invocation; the checked validator SHA-256 is
`43b42fbc5f6d2b9ecbeb82b1419224d6a99025c1be5c600dd959f77d362b6354`.

The event log and report agree on 07:00 notice/reservation, 08:00 launch,
10:00 completion, one planned and successful wave, one sortie, no cancellation
or unfinished mission, 72 half-hour report intervals, 2 aircraft-hours of
mission operation, 33 aircraft-hours ready, and `NPSTA=0`. The two SXO files
are byte-different; equality is claimed for the checked inputs, event logs,
and reports, not the SXO bytes.

## Reproduction and limits

The [A01 README](README.md) gives a fresh-run command with a unique run ID,
source hash check, and the pinned Python and runner paths. It also records the
initial zero-duration preparation-row diagnostic: that row gave `NPSTA=1`,
while the final row-free input gave `NPSTA=0`. The import warnings 108 and 126
are explained in the [contract](contract.json), and the strict validator
rejects unlisted conversion errors. The runner refuses
an existing SIMLOX process, so a future rerun must be scheduled without
closing the user's current GUI merely to run this check. The sealed runs and
read-only replay above are the evidence for this sign-off.

The always-ready path does not exercise the 20-minute launch-delay deadline,
before/at/after-deadline priority, or a mission crossing `SIMPE`. Those
behaviors are excluded. GUI-only interactions, Python/Rust/J35 equivalence,
random or fault behavior, and performance are also outside this publication.
GUI sampling has its own evidence and is not a release prerequisite under the
revised standard.

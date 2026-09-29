# D06 explicit position failure mode: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one explicit FMID on the first of two positions holding the same LRU type, with local direct system CM. This is a bounded D06 foundation; other failure modes and replacement behavior remain planned.

## Source and native run

The accepted [D01 installed-LRU parent](../D01-installed-lru-direct-repair-v1.0.0/cli-scope-signoff-2026-09-29.md) input SHA-256 is `eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93`. The [D06 input](native-input.json) SHA-256 is `ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78`; the [exact parent diff](parent-diff.json), SHA-256 `b878916c46ae14b7e989adea493dcfb424ac13d8becc18a1d887ea53e493366d`, changes seven parent tables and adds `MaterielPosition`, `MaterielStructure`, `FailureMode` and `CMLocation`, leaving 24 parent tables unchanged. The two positions `POS-A` and `POS-B` each hold `TEACH-LRU-01`. `FM-POS-A` has `FRQ=300000` per million `OPHOURS` and `CRITF=1`. `CMLocation` maps it to `TEACH-AIR-01` at `BASE-01` for `CMT=0.5` hours. Both traditional FRT fields are null, and the traditional structure, repair and stock rows are empty. The [contract](contract.json) states the predeclared hypothesis and limits.

The installed SIMLOX 2017 manual, SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, pages 355–357 and 364–370, documents failure-mode CM mapping, position-linked modes and avoiding traditional FRT for explicitly modeled items. The installed field dictionary was supplemented by the native exporter's optional `RUBM`, `CMM` and `CMC` columns. Neither proprietary source is uploaded.

Accepted native run ID `d06-position-cm-v100-ssh-20260930-02` used session-0 SSH, the host-wide `Global\SimloxIssue18NativeQueue`, and the active GUI PID 13340 guard. Import, export, calculation, report and roundtrip checker all exited zero. All 18 source row-containing tables roundtripped exactly, including three all-null placeholder rows. Conversion had **zero errors and one warning**, #108 for event logging. Raw artifacts remain in ignored local `runs/`.

| Accepted raw artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `db8925c06d1ca4a5d74f5d022d8eb919f68d375db3ed5f9d35693ef84c903108` |
| `closure.json` | `afd8689161874d247dee92a6f6265211733375b8933f3fcd30bfb297cfe975c7` |
| `model.log` | `92930370c7a60faa7870fa4fb43fffad73d2c3582e187c39506927012198ae1a` |
| `report-raw.json` | `230403de72c36ae2ba2b6e57939ef9dd94571f94de840fa718084736e93630b8` |

## Observed behavior and review

Native events show critical `FM-POS-A` failures on `POS-A` at 9.8829 and 33.8602 hours. Both abort the current mission. On returns at 10 and 34, the aircraft starts system CM tasks bearing `FM-POS-A`; they complete at 10.5 and 34.5. The middle mission succeeds at 22. Across 72 half-hour bins, `NFAIL=2` and `NREPT=2`, with one aircraft-hour in repair and one ready aircraft at the hour-36 stop. The explicit input has no traditional FRT branch, and all observed failure/repair counts reconcile to the two FMID events. The native log names the affected position; the same-LRU placement at both positions is evidenced by the input and its roundtrip, not by an isolated failure at `POS-B`.

The [author replay](review/author-position-validation-2026-09-30.json) passed **60/60** checks, SHA-256 `fdf10f1bc28af643424e4f33d69bcd0f158c5e69ca2635a6c7f69f245e2b1eae`. Its [validator](validate_position.py) SHA-256 is `dc94ba182763d9143391e748690293b5819b1c96eb706c144bf8b73c9f13918d`. A separate reviewer wrote a [read-only replay](review/independent_position_readonly.py), SHA-256 `7ddd5e4764465a95dbd1bd51be0fa74dce86e1ce7b68d5482cbc00fbb070bebcd`, without importing the author validator. Its [76/76 result](review/independent-position-2026-09-30.json), SHA-256 `6ba8f422c80c78695a5005ea29a6465e8df0816bb06fbfaa3142fc4b2eb82627`, agrees with the exact delta, sealed native raw data, FMID/position/CM mapping and report totals.

The earlier immutable run `d06-position-cm-v100-ssh-20260930-01` is excluded. Its source input SHA-256 was `bac738acdfb0e869549a858be8f63fd39de45d686907af7e25e19c232e253ad8`; the roundtrip checker exited 1 because the native exporter added the three optional columns absent from that input. Its native event log and report hashes match the accepted run, but a successful simulation alone did not meet the frozen identity check.

This result does not establish `POS-B` failure behavior, position-specific alternative maintenance, multiple modes, item replacement or stock effects, `CMRF`/`CMRQ`/`CMRQD`, resources, GUI visual content or cross-engine equivalence. The GUI identity and active session were guarded, but visual content was not sampled. Issue #18 stays open.

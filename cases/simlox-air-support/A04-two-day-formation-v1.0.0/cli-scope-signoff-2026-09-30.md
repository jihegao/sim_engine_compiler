# A04 two-day, four-wave formation: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one fixed-seed, two-day, two-wave-per-day schedule with two ready aircraft required and allocated to each fixed mission. This is a bounded A04 composition of already accepted A03 and A09 behavior, not the full A04 boundary matrix.

## Accepted sources and exact delta

The model parent is the accepted [A03 two-aircraft formation](../A03-two-aircraft-formation-v1.0.1/cli-scope-signoff-2026-09-29.md), input SHA-256 `d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4`. The accepted [A09 nested-profile prerequisite](../A09-hierarchical-operation-profile-v1.0.1/cli-scope-signoff-2026-09-29.md) has input SHA-256 `e795c5fcf563f8e42ab9e9cb161a925bec3b06157cbbecde7901e99bfec91d85`. Its three `OperationProfile` rows are copied exactly into A03, retaining root `IQTY=2`, `IPER=48` and relative child starts 8/20. A03 retains `SystemDeployment.QTYPS=2` and `MissionType.NOS=MNOS=2`. The [A04 input](native-input.json) SHA-256 is `9e2eac17e0408903e099e6ce054ebf4b91db1ca79036afe29638ee8a41d40711`.

The [exact A03 parent diff](parent-diff.json), SHA-256 `111cf01bb3cc648cb476b68b015cc507a6582dc7e20ff2cd59cec88344211d40`, changes only `OperationProfile`, `Control.SIMPE/RCEND` 36→48, both `ResultCollection.RCEND` values 36→48, the problem label, and the inherited unit description from one to two aircraft. The other 26 A03 tables are unchanged. The [contract](contract.json) predeclared four expected launch hours, formation size, ledgers and limitations before the run.

The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`. Physical PDF pages 179, 184, 187–188 and 270–276 describe scheduled missions, minimum/desired system quantities, hierarchical operational profiles and their repetition fields. The installed dictionary SHA-256 is `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. The proprietary files are not uploaded.

## Sealed native result and review

Run `a04-two-day-form-v100-ssh-20260930-01` used session-0 SSH, the host-wide `Global\SimloxIssue18NativeQueue` mutex and GUI PID 13340 identity guard. Import, export, calculation, report and roundtrip checker all exited zero. The 13 row-containing source tables roundtripped exactly. Conversion had zero errors and warnings #108 for event logging and #126 for the teaching aircraft with no items. Native JSON reports have writer trailing commas; both replays parse a normalized copy while preserving the raw-byte hashes.

The event log has exactly four missions, ordered one hour before launch, each allocating aircraft #0 and #1. They start at hours 8, 20, 32 and 44 without delay, then succeed and return both aircraft at 10, 22, 34 and 46. No abort, cancellation, random failure, repair, or extra cross-window mission occurs. The 96 aligned half-hour `SystemResults` bins cover 0–48 hours: two aircraft operate in precisely the eight mission hours, producing **eight aircraft sorties and 16 aircraft mission-hours**. Both are ready between waves after return and at the hour-48 stop. Summary mission fractions are 1; `NFAIL=NREPT=0`; stock demand and backorder are zero. No resource-consuming preparation is configured. The accepted A03 parent supplies the two-aircraft one-wave control, and accepted A09 supplies the 8/20/32/44 nested schedule control; their combination is established by this child run.

| Child raw artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `8a7522a1cb275af3a8da107d7f9d2507883d5ad162d80ef98dc52356214eb8bb` |
| `closure.json` | `fdb7d87e1cc3537c2999217888cca03647ef87796c94568c81ad175357ddad0d` |
| `model.log` | `f335e5cabd03d4691aad30c7873d69b25d921ff30583ac67868c3f1b7d2c9d45` |
| `report-raw.json` | `46c45c12839220cf4f7dd334502318faa6673749e8d056378445a61335e33ab4` |

The [author validator](validate_two_day_formation.py), SHA-256 `9af0bbb4fbafce420edc28449e0a8fe7113b60995622bd8b0cc6c73614cd1dba`, passes [106/106 checks](review/author-two-day-validation-2026-09-30.json), SHA-256 `78614c131f7de2ad20fff2352c4339aff14d423f28ee08bd025b65b3b200aeef`. A separate reviewer wrote a [read-only replay](review/independent_formation_readonly.py), SHA-256 `3adf6c2327a572d8801198048d312835f2cdc8ed687a3c5bf162ec45b1b27623`, without importing the author validator. Its [91/91 result](review/independent-formation-2026-09-30.json), SHA-256 `5e7899734fa804b2c537084003c08b4c0ec29fc999354e72d9000531d7a73ddb`, independently verifies source/diff, accepted A03/A09 control outcomes, all raw seals, guarded execution, events, bins and limits. Raw files remain in ignored local `runs/`.

This result is specific to installed SIMLOX executable SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`, one seed, one explicit minimum-two formation, and four fixed waves. Insufficient aircraft, delays, cross-day return, another repetition layout, a mission still active at the horizon, failures, resource contention, GUI visual content and cross-engine equivalence remain unverified. Issue #18 stays open.

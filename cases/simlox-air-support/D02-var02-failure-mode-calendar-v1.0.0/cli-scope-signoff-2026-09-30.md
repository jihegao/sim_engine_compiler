# D02.var02 explicit failure-mode calendar clock: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for a fixed-seed explicit `FailureMode` comparison: `OPHOURS` in the accepted D06 control versus `CALHOURS` in this child. This is a bounded D02.var02 result, not the full D02 traditional-item and clock-boundary matrix.

## Source and paired native runs

The accepted [D06 control](../D06-explicit-position-direct-repair-v1.0.0/cli-scope-signoff-2026-09-30.md) input SHA-256 is `ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78`. The [child input](native-input.json) SHA-256 is `23b550dbc4e0aea4d6d328fe4805a4eb50af81f3af54ccd6353e45bce933271b`. The [exact parent diff](parent-diff.json), SHA-256 `9b793a2b1349f84ca2c6445e83c3b2cfd4ea03daca22214496c3d9af0c18d8da`, changes only `FailureMode.OPID` from `OPHOURS` to `CALHOURS` and the description label; 33 other parent tables are unchanged. The same `FM-POS-A` has `FRQ=300000` per million selected clock units. The [contract](contract.json) fixes the seed, missions, half-hour direct CM and 36-hour horizon before the run.

The installed SIMLOX 2017 manual, SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, pages 364–369, describes the explicit failure-mode frequency and clock fields. Native results below establish this model's behavior. The proprietary manual and dictionary are not uploaded.

The child native run ID is `d02-var02-calendar-v100-ssh-20260930-01`; the control run ID is `d06-position-cm-v100-ssh-20260930-02`. Both used session-0 SSH, the host-wide `Global\SimloxIssue18NativeQueue` and GUI PID 13340 identity guard. The child import, export, calculation, report and roundtrip checker exited zero. All 18 row-containing source tables roundtripped exactly, including three all-null placeholder rows. Conversion had **zero errors and one warning**, #108 for event logging. Raw artifacts remain in ignored local `runs/`.

| Child raw artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `31daf88571a30406cdbb78423fd395ccae1859e7cff1cde8a6238872bbaf3b17` |
| `closure.json` | `c21c0793a1009da194430cf7cf864345d8c69cab3be724e1e253e34600df628c` |
| `model.log` | `b587e5e3557a6530be92711588993ed65f7c4b610204fc7e8115a7849ee79c96` |
| `report-raw.json` | `f1fd9cefe6b12e0b9dfbb3a85eac6f8bef168915531edd9edd2a20923aa43a0d` |

## Observed comparison and review

The control logs two `FM-POS-A` failures during missions at 9.8829 and 33.8602 hours, with no failure before the first mission or in the long gap between the second and third. The calendar child logs five: 1.8829 and 4.84945 before the first mission, 21.2495 during the second mission, 26.7141 in the idle gap, and 34.2389 after the third mission returns. Four are ground-idle failures; the 21.2495 failure aborts the second mission. The child direct CM tasks complete at 2.3829, 5.34945, 22.2495, 27.2141 and 34.7389. Missions 8–10 and 32–34 succeed. Its 72 half-hour report bins total `NFAIL=5`, `NREPT=5`, 2.5 aircraft-hours of repair and one ready aircraft at the hour-36 stop. The control totals two failures and two repairs.

The [author paired replay](review/author-calendar-validation-2026-09-30.json) passed **73/73** checks, SHA-256 `3607673deb881bbe91ddcd5c2fca4fe1ac52a8172dc53ed64c542e991a475ec2`; its [validator](validate_calendar.py) SHA-256 is `34d228ee8a03beaea7c8c1b3961ac9452cc80451a15930a447a3e6a01495858f`. A separate reviewer wrote a [standard-library-only read-only replay](review/independent_calendar_readonly.py), SHA-256 `59095bd2d15fcccae5aae7c3abab32743a0bdb32b69f6a5f1168119b3d622073`, without importing the author validator. Its [95/95 result](review/independent-calendar-2026-09-30.json), SHA-256 `7b97c2513656b9c36a9edee3c7c91f46571f4e320078806bc23f010bcbc73c98`, agrees with the exact input delta, sealed source and raw hashes, clock-specific timing, CM ledger and report totals.

The five-versus-two failure count is one fixed-seed realization with different accumulated exposure; it is not a measured ratio of failure rates. Traditional `Item`/`ItemFailureRate` `CALHOURS` or `MISSIONS` input acceptance, maintenance clock edge cases, zero exposure, other seeds, GUI visual content and cross-engine equivalence remain unverified. The GUI identity and active session were guarded, but visual content was not sampled. Issue #18 stays open.

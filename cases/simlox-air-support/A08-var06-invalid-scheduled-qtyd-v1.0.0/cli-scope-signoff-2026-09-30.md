# A08.var06 SCHEDULED plus IQTYD converter rejection: CLI scope sign-off (2026-09-30)

**Decision:** `native_converter_rejected_cli_scope`, `reusable_published` as a diagnostic capability case. This is a deliberately invalid source; no simulation behavior is accepted from it.

## Source and frozen expectation

The accepted [A08.var02 parent](../A08-var02-random-count-equidist-v1.0.0/cli-scope-signoff-2026-09-30.md) input SHA-256 is `54e1fab467ede59829b0c8994aa4d72f1e08878cf7a39532c6fe61364ca87c84`. The [invalid child](native-input.json) SHA-256 is `8313773e7dd0bb94914454b248745dbf42b0f6874ac03c41b54c9ac864fce4fa`; the [exact diff](exact-diff.json) SHA-256 is `e0d3d8626428214b2fb0d2fd52a1bbd8c480a3c23393403fbdc574c594e51d60`. `OperationProfile.ITYPE` changes `RANDOM`→`SCHEDULED` while `IQTYD=<POISSON>`, `IQTY=3`, `IDISP=EQUIDIST`, `STIM=8` and `IPER=12` remain. `ProblemDescription.PDESC` changes only a label; the other 29 tables are identical. The [negative-case contract](contract.json) SHA-256 is `bc9d928f8b61db01c0f0b6200f5c539ea7f6fe5bfb8c72d74bb5df5eaab91fab`.

The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`. Physical PDF pages 271 and 273–275 limit `IQTYD` to `ITYPE=RANDOM`; page 795 documents error #212 for violating that rule. The proprietary manual remains local.

## Guarded native rejection

Run `a08-var06-invalid-scheduled-qtyd-v100-ssh-20260930-01` used session-0 SSH, host mutex `Global\\SimloxIssue18NativeQueue` and preserved GUI PID 13340/session 1 with its original start identity before and after every native step. JSON import and export succeeded; the checker verified exact rows and columns across all 13 populated source tables. Native calculation then reported `Input conversion completed. Errors: 1, Warnings: 2, Notes: 0`, exactly error #212 (`Initiation quantity distribution (IQTYD) only allowed for random initiation types (ITYPE)`) and warnings #108 (logging) and #126 (teaching aircraft with no items). Its process exit code was zero, but `.sxo` contains only four bytes and no JSON report was produced. The runner records the calculation as `expected_rejection`, followed by a successful source roundtrip check. A zero process exit code is not taken as model acceptance.

| Artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `683f9215b4b60eee857cd2e12a8dbc2665be354c422aabaf0306c01dc7d27103` |
| `closure.json` | `6c3202417fe739659a67cd142c323e176a5506740121019bb216fc085cf774a4` |
| `steps.json` | `31a6ef682ccc1d77a7f3f04bb09926f876d1986e96a75011f8294c3becbfe25c` |
| `run.log` | `fa9def02f4ca7692207c7007e65ac10e9424d6b69595d7def137fa5fa90df77c` |
| `model.sxo` (four bytes) | `2a2d5e177502c5a794270deadd8dd755859f202a96d9d27568826ab0b69f984b` |
| `roundtrip-raw.json` | `d92e355afdda3515712245156e4d24325acd342969476e351dc18129ae4a3654` |

The closure seals nine raw files and shows source hashes unchanged before and after. Installed executable SHA-256 is `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`. The native export's trailing commas are normalized only in a parser copy; raw byte seals remain intact. The [author replay](validate_rejection.py), SHA-256 `3c87dc665394f19634ddb1ffc84ebeb5a8fded75b1940040425dd8a690dda352`, passes [39/39 checks](review/author-rejection-validation-2026-09-30.json), SHA-256 `745c0a3d84984f84b33af10cf3cc5d097fda40693b1b6001bedf07b93e6bcd4e`. A [separate read-only reviewer](review/independent_rejection_readonly.py), SHA-256 `a00252fda846fff6a5bd443258387e38f58a13828d75a9cbbdf35f0260d4990f`, passes [49/49 checks](review/independent-rejection-2026-09-30.json), SHA-256 `19e1a713d274d33bfb88009e560916701a7e90888c90f8c56ab89df95f4c2888`, without importing author validation. Its JSON was byte-identical on a second replay.

Reproduce source with `python build.py` and `python describe_diff.py`; replay sealed local evidence with `python validate_rejection.py` and `python review/independent_rejection_readonly.py`. New native execution requires a fresh versioned run ID. This diagnostic covers one `SCHEDULED+<POISSON>` source under the installed executable. Other invalid combinations, diagnostic precedence, GUI visual content and cross-engine behavior remain unverified. Issue #18 remains open.

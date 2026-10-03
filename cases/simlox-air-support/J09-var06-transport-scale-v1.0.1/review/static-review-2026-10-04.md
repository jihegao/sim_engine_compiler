# J09.var06 independent static pre-run review — 2026-10-04

**Verdict: GO for one fresh guarded diagnostic run of v1.0.1.** This is a static source and runner review, not native acceptance.

## Original v1.0.0 review and exclusion

The accepted E04 SLOW input, closure and signoff matched their pinned SHA-256 values. The v1.0.0 child appended only one `ScaleFactors` row: `SCFRT`, `SCRPT`, `SCLDT`, `SCPMI` and `SCPMT` at 1.0, and `SCTRT` at 2.0. The other 31 tables were unchanged. The six names, floating types and defaults match the installed SIMLOX dictionary. The guarded runner had session-0 SSH, `sshd.exe` ancestry, the global native mutex, active GUI PID 13340 checks, hidden serial CLI steps, converter and source gates, and closure sealing. PowerShell parsing found zero errors.

The sealed v1.0.0 run completed import, export, calculation and JSON report with exit code 0, GUI preserved, and converter `Errors: 0, Warnings: 1, Notes: 0` with only warning #108. Its strict roundtrip checker then exited 1 because native export added ten all-null optional `ScaleFactors` columns. The run remains excluded under closure SHA-256 `d4a5cfb4d13e4b761dc9fcbdb603fcdab7d0133b3d154c66e3d3061dbe42b2d1`.

## v1.0.1 re-review

| Frozen file | SHA-256 |
| --- | --- |
| `scaled-input.json` | `9d22f2596897fceb6e00a425c9e8bcd226a1f9549a3b00d08b53b0204e1083fe` |
| `exact-diff.json` | `7a141df91b9b8e7f7016594fe39ed04792f1bb2fafbc5b9d10ff29a6cf600ab0` |
| `contract.json` | `1c9ec3a06380270b8a097c30b9ea041f70fbcd1e0f4dcf4a2df6ea32ced4c142` |
| `build.py` | `8cc8f6a9edce82c6928ac331d6ed0ca6b96ec182fa2e47d49a277782676ee153` |
| `describe_diff.py` | `6fb09bd47df45ca27915e8e46d5537b14d3711fb3b90f219c8173dead48601d6` |
| `check_roundtrip.py` | `8d61c67769bb298c7d86ccd013c050315ea5ea686423cd869ef453a4559045d5` |
| `run_native_ssh.ps1` | `2ec6ab1fd060698ae8404488bcc4f778750f5e1650f7b23cf5f34f8059d88374` |

The v1.0.1 input and diff are byte-identical to v1.0.0. Read-only builder and diff replay passed. The new contract pins the excluded closure and requires a fresh run. The revised checker passes read-only replay against the excluded export: it compares every other authored populated table exactly, preserves all six authored `ScaleFactors` values and types, and accepts only additional null-valued double columns in that table. The runner pins the new contract and excluded closure, retains the earlier SSH, mutex, GUI, converter, before/after source-hash, roundtrip and raw-closure guards, and parses with zero PowerShell errors. No v1.0.1 run directory existed at review time.

**Limit:** The checker does not allow-list the ten observed extra column names; any additional double `ScaleFactors` column is accepted if its value is null. This is a lossless projection of the six authored source values, but future native schema changes would need separate inspection. Four-hour transport legs remain a conditional hypothesis to verify from fresh physical item events; this review does not establish the native timing or publication claim.

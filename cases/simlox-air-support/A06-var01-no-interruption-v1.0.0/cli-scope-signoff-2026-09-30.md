# A06.var01 no-interruption extendable mission: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one two-aircraft, no-failure `MPAT=EXTENDABLE` mission. With no interruption, the mission operates from hour 8 to hour 12, succeeds, and returns both aircraft ready. This is a bounded equality check against the accepted continuous control, not a general equivalence claim.

## Source and exact delta

The accepted [A05 continuous two-aircraft parent](../A05-continuous-baseline-v1.0.1/cli-scope-signoff-2026-09-30.md) input SHA-256 is `997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea`. The [A06.var01 child input](native-input.json) SHA-256 is `6d508cb4af5f997785be802c0527cd6f50918cde78714406ae2106e7b421ca6c`. The [exact diff](exact-diff.json) SHA-256 is `5da75bb5143b431f1089f0480ba2ab51aed796a34302d0f0980eb68311cdecfc`: only `MissionType.MPAT` changes `CONTINUOUS→EXTENDABLE` and `ProblemDescription.PDESC` changes its label; the other 29 source tables are identical. `NOS=MNOS=2`, deployment of two aircraft, `DURN=4`, schedule, seed, zero failure rate, and 16-hour reporting horizon remain unchanged. The [frozen contract](contract.json) SHA-256 is `8fed52081bd27e8227859f27965e19328618047a2bf5d2329f48eee25dc90605`.

The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; physical PDF pages 179, 182–183, 265–266 describe extendable and continuous mission patterns. Neither that proprietary manual nor the installed dictionary was uploaded.

## Guarded native evidence

Run `a06-var01-no-interruption-v100-ssh-20260930-02` used session-0 SSH with an `sshd.exe` ancestor, host-wide `Global\SimloxIssue18NativeQueue` mutex, and GUI PID 13340/session-1 identity guard. Import, export, calculation, report export and exact source roundtrip checker exited zero. All 13 row-containing source tables roundtripped exactly. Conversion errors were zero; warning #108 enables event logging and #126 denotes the teaching aircraft with no items. The native report's trailing commas were normalized only in parser memory while raw bytes were retained and hashed.

| Raw artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `6f9b0e8aa8f374984471ad55f030e0d9bc3ac54428cadcdea23af1601645f784` |
| `closure.json` | `d7c96ea29a80243cfbfe322003e5c5bfa2355682fbb680f486a834248ddca3ba` |
| `model.log` | `85febf15fd2c3f9f58306ee7284db4af87592b2238fcec2b76c0446e5d1a6d08` |
| `report-raw.json` | `56efcc29e6ebfb2c366e9abe17ea7367469ca7967b4bd72d8776e69c2cfd803d` |

The event log is byte identical to the accepted A05 continuous control. Both aircraft allocate and prepare at hour 7, start at hour 8, and complete successfully at hour 12. Neither run has suspension, failure, repair or stock demand. Both return ready at hour 12. All 32 `SystemResults` rows, 32 `StockTotalResults` rows, and `ResultSummary` are exactly equal to the accepted control; only `ProblemDescription` differs. The half-hour bins integrate `NSYMO=STACC=8` aircraft-hours and `NSYMS=NSYRP=NSYMP=0`. `MTMF=STMF=1`. `MSTF=MSUF=0` are fixed-mission-only fractions; the native success event is the direct success evidence.

The [author validator](validate_no_interruption.py), SHA-256 `49fc17b39ce60ced9f864ea5242a292b6dd222614159c823cf67578f65a94aec`, passes [157/157 checks](review/author-no-interruption-validation-2026-09-30.json), SHA-256 `02eeb5b01e08582ba78638d7219ec8a82ba70a0e70c6f28159b19315f2a2159c`. A [separate read-only reviewer](review/independent_no_interruption_readonly.py), SHA-256 `2315f4f684cf86be7980758621d1b14afd43876b78f9c9eb32eab38e4bf2066c`, passes [64/64 checks](review/independent-no-interruption-2026-09-30.json), SHA-256 `ed32334c57b883dbabb643f0f6ac978b906050b3362035da5c17877d9361d8d4`, without importing the author validator; its JSON was byte-identical on a second replay.

The preceding immutable run `a06-var01-no-interruption-v100-ssh-20260930-01` is excluded from acceptance: its copied checker expected 16 source tables and exited 1 even though native import, export, calculation and report completed. This parent contains 13 row-containing source tables. The checker was corrected before the `-02` run; both raw run directories remain locally ignored. The accepted artifacts above are specific to installed SIMLOX executable SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`.

Reproduce the source input with `python build.py` and exact table diff with `python describe_diff.py` from this package. Re-run the sealed author and independent replays with `python validate_no_interruption.py` and `python review/independent_no_interruption_readonly.py` while local raw runs are present. Only a new versioned run ID may be used for another native execution. The finding covers one no-failure seed and formation. It does not establish generic no-interruption equivalence, interrupted behavior, GUI visual content or cross-engine equivalence. Issue #18 remains open.

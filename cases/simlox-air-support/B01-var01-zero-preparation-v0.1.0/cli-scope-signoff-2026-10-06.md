# B01.var01 — zero-duration preparation: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope`; candidate for `reusable_published` on `simlox/main`. This signs one fixed-seed, one-aircraft, one-mission SIMLOX 2017 CLI observation. GUI visual behavior, cross-engine equivalence, performance, resource demand, other durations/seeds, full B01.var01 and Issue #18 remain unverified.

## Source and dependencies

- Accepted parent: `B01-fixed-preparation-v1.0.1`, input SHA256 `2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b`; published positive half-hour preparation run `b01-v101-ssh-20260929-06`, closure SHA256 `046a7724f053f63e6967e3c3e803f726fd5f4b6322015239cb25a380c6446516`, 11 local raw seals. The accepted A01 final/replay runs supply the instructional prerequisite and 34 additional local raw seals. Neither parent was rerun.
- Child input SHA256 `5e2d473cdd617955e2920da0a473854a7576a041aa2653e65397dfc1746f1aee`. Only `MissionPreparation.DURN` changes 0.5→0 among 167 authored cells; the `PREP-FIXED` task link, one-hour notice, h8 mission, seed, 36-hour horizon and half-hour reports remain. The inherited `Tasks.DESCR` says “30-minute” and is stale; numeric DURN and native events establish duration.
- The installed manual defines DURN as mandatory nonnegative calendar duration. Independent contract memo SHA256 `7371c8d86a8c09a01892d3dfb5409761a667182b74f8060d2e48727590222b8d`; exact-file prelaunch GO SHA256 `5359e71d808ed19e743dee05dfe305f4e88fbbd9f3237bad48c883211422ca38`.

## Native result

The single run `b01-var01-zero-prep-v010-ssh-20261006-01` used actual SSH session 0 with `sshd.exe` ancestry, `Global\SimloxIssue18NativeQueue`, an absent unique run directory and the responding protected GUI PID 13340/session 1/start `1790590196826` ms. Import, export, exact 15-row-containing-table roundtrip, calculation and report completed. Converter Errors 0, Warnings 2 (#108 and #126), Notes 0. Child closure SHA256 `ed20962a1a02d315f4c316b40c87651a43bd6a8b515557d0852f1700ab6c5028` seals 12 local raw files. Native raw runs remain local and are not committed.

Aircraft ID 0 was allocated for the sole mission at h7. Its preparation, linked task and subtask started and completed at h7; the subtask planned zero hours, with no resource wait or second lifecycle. The same aircraft launched h8, performed the h8.5–9.5 mission task, succeeded and returned h10. The complete 72×40 System ledger differs from positive-duration B01 in exactly four predeclared cells: at h7–7.5 `NSYMP` 1→0, `NSYMR` 0→1 and `NPSUC` 0→1; at h7.5–8 `NPSUC` 1→0. `NPSTA` remains one. Preparation work is zero, reserved aircraft time one hour, flight two hours, ready 33 hours, terminal ready one. All 72×16 Stock cells, 11 summary fields and ProblemDescription match B01.

Author validation passed **4,600/4,600**, SHA256 `a97d6f3f726179e64479c73ce477806bf2bb235c8fe4b7f2ec8cb840b33dbf2e`. Separately authored read-only replay passed **4,490/4,490**, verdict SHA256 `2e8a06d967a23d82aac4f7d4d64c3ad9c590f5bd8ce259241777b872e7b22197`. [The evidence index](evidence-index.json) pins 15 package source files and 57 local accepted-parent/child raw files. Native trailing commas were normalized only in memory; raw byte seals remain authoritative.

## Reproduce the checks

From the repository root, use the pinned Python runtime or compatible Python 3.12:

```powershell
python cases/simlox-air-support/B01-var01-zero-preparation-v0.1.0/build.py
python cases/simlox-air-support/B01-var01-zero-preparation-v0.1.0/check_parent_diff.py
python cases/simlox-air-support/B01-var01-zero-preparation-v0.1.0/validate_native_cli.py
python cases/simlox-air-support/B01-var01-zero-preparation-v0.1.0/review/independent_replay.py
```

These commands recheck existing files; the frozen native invocation and local raw paths are in `evidence-index.json`. Do not rerun the accepted parents or overwrite this run ID. The earlier A01 zero-duration diagnostic lacked `PREP-FIXED` and served only as advisory context. K01/K08 capture and K06 remain blocked; I07 opening-stock-three and E05.var02 exact-time remain excluded.

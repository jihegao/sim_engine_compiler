# A03.var01 — three available, two required: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope`; candidate for `reusable_published` on `simlox/main`. This signs one fixed-seed, one-wave SIMLOX 2017 CLI behavior. GUI visual behavior, cross-engine equivalence, performance, alternative seeds and full A03.var01/Issue #18 remain unverified.

## Frozen source and dependency

- Accepted parent: `A03-two-aircraft-formation-v1.0.1`, input SHA256 `d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4`, accepted run `a03-v101-ssh-gui-20260929-01`, closure SHA256 `a3b4a2739b5b098c956aa19428cf997b2079aab858e22fb5ea9c4486a4209edd` and 11 sealed local raw files. Published A02 is the instructional prerequisite.
- Child input SHA256 `6fc81a5a5ce9304c007a2087a0116cb585bf3fe70312649937e43d0576be0e71`. Only `SystemDeployment.QTYPS` changes 2→3 among 155 authored cells. `MissionType.NOS=MNOS=2`, h8 fixed wave, seed, 36-hour horizon and half-hour reports remain unchanged. The inherited Unit description saying one aircraft is stale and is not used as physical evidence.
- Independent contract memo SHA256 `cfe12c5cf2575180886ad73801bfde8f0531e1505773b47d2e79e47bfaf1c9ef`; exact-file prelaunch GO SHA256 `4f0aebb1e32a03660b91c63d84baa4bdc4a76c39cd732e6a82e591e60687b3d0`.

## Native run and result

The single run `a03-var01-three-avail-v010-ssh-20261006-01` used actual SSH session 0 with `sshd.exe` ancestry, `Global\SimloxIssue18NativeQueue`, an absent unique run directory and the responding protected GUI PID 13340/session 1/start `1790590196826` ms. Import, export, exact 13-row-containing-table roundtrip, calculation and JSON report completed. Converter Errors 0, Warnings 2 (#108 and #126), Notes 0. Child closure SHA256 `965ba78470846f2ad6634c3e82008dabc20a9beefb1762bba3ae0fef9a46396d` seals 12 local raw files. Native raw runs remain local and are not committed.

Three distinct aircraft were ready at h0. The sole h7 mission requested two, allocated IDs 0 and 1, and left ID 2 ready. The same pair launched at h8, performed the h8.5–9.5 task, succeeded and returned at h10; all three were ready afterward. There was no extra sortie, waiting/cancellation, fault, maintenance or stock movement. The complete 72×40 System ledger has one extra available and ready system per bin versus the parent, two reserved aircraft-hours, four flight aircraft-hours and 102 ready aircraft-hours. `FTMO=2/3` in h8–10 and zero elsewhere. All 72×16 Stock cells, all 11 summary fields and ProblemDescription match the accepted parent; summary `NREP=1`, `MTMF=MSTF=MSUF=STMF=1`.

Author validation passed **4,498/4,498**, SHA256 `b227f15ac861cf894f379cb871793d0417c1a8148aa53f2ce834b26ba34effb5`. A separately authored read-only replay passed **4,382/4,382**, verdict SHA256 `bdc4f11eb325b0d0411288ecc6ed146f2c0617ba247f56911f39ac8cfb34e3fd`. The reviewer did not rerun SIMLOX. [The evidence index](evidence-index.json) pins 15 package source files and 23 local parent/child raw files. Parse normalization of native trailing commas was in memory only; original byte seals remain authoritative.

## Reproduce the checks

From the repository root, use the pinned Python runtime or compatible Python 3.12:

```powershell
python cases/simlox-air-support/A03-var01-three-available-v0.1.0/build.py
python cases/simlox-air-support/A03-var01-three-available-v0.1.0/check_parent_diff.py
python cases/simlox-air-support/A03-var01-three-available-v0.1.0/validate_native_cli.py
python cases/simlox-air-support/A03-var01-three-available-v0.1.0/review/independent_replay.py
```

The frozen native invocation and raw-file locations are in `evidence-index.json`; these commands only recheck existing files. Do not rerun the accepted parent or overwrite this run ID. The observed numeric pair 0/1 does not establish a selection-priority rule for other fleets or seeds. GUI K01/K08 capture and K06, excluded I07 opening-stock-three and E05.var02 exact-time remain separate unresolved boundaries.

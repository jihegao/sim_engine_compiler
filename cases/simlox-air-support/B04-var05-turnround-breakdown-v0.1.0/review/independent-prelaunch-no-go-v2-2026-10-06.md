# Independent exact-file prelaunch review, revision 2 — NO_GO_PRELAUNCH

Reviewed 2026-10-06. This memo applies to the revised validator and runner below. The first prelaunch no-go memo remains the historical finding; its full-report coverage defect is fixed in this revision. No native child was launched or approved by this review.

## Exact files and guards

- Run ID: `b04-var05-turnbreak-v010-ssh-20261006-01`; target run directory absent.
- Contract SHA-256: `5292459de185e04ef445ff89e4e20cb1c8d9148151f767340b59893d089d3020`.
- Input SHA-256: `965a3acc431696e56b760b07323e4cf11cb571e030885fff708787ce84f3e42f`.
- Runner SHA-256: `523f6d5a5fea6cf81b10c8ee608685ceb3ea7b067f346c0177d04853f1edef6a`.
- Validator SHA-256: `519d737285e78a605b0a106fd7e6b00fe49f2b8bf65117592b30f5b4a5d01d6c`.
- Expected ledger delta SHA-256: `5659de210fd4f9eca999b616615eb62f124ea0a8ff789f1718549a7ae0b239dc`.
- Accepted B04 report SHA-256: `ea429a8c563f50256ca24168e8ae103222e5fe01918fbb52c40c6adf64a66897`.

I independently rehashed the accepted B04 12 and B02 11 raw closure records: all 23 files match SHA and size. The source diff checker reports one changed `MissionTurnround.TID` cell, 17 newly authored cells in three rows, and no removal. The Python files parse. The parent-reported actual SSH PowerShell 5 `-PreflightOnly` passed in session 0 with sshd ancestry, free mutex, absent run, and responding GUI PID 13340/session 1/start 1790590196826. The current runner pins the revised validator, expected delta, and parent report, checks GUI identity around each hidden child step, stops only its own child on timeout, and seals failed output. I found no new runner protection defect.

## Corrected report gate

The new validator compares all 11 summary cells, all 72×40 System cells, and all 72×16 Stock cells with the accepted B04 report after six declared System row patches. The patch is analytically consistent with the source-bound proposed timeline: first turnround h23.5–24, preparation h24–24.5, reserved interval h24.5–24.75, second flight h24.75–26.75, and second turnround h26.75–27.25. Accepted B04.var01 quarter-hour evidence shows the same half-bin flight/turnround metrics and placement of `NPSTA`/`NPSUC`; accepted B04 parent row 42 establishes `NSYMR` for a prepared aircraft waiting for launch. Exact equality is a strict frozen gate; any unexpected float or field difference would be a diagnostic, not an implicit tolerance.

## Remaining blocking event gate

The contract separately requires the **second mission notice at h23.75** and **two existing serial preparation steps totaling 0.5 hour**. The revised validator's mission regex checks `mission preassigns a system` at h23.75 but never parses the `mission ordered`, `mission created`, or `mission activated` notice events. Its subtask regex parses both preparation and turnround lines, but the validation loop records only `task_kind == "turnround"`; it does not check either `PREP-FIXED` SEQ1 or SEQ2 lifecycle for either mission. A log with missing, duplicated, or mistimed preparation subtasks could pass if the aggregate preparation start/end lines and report cells remained as expected. The first physical `System arrives` return event is likewise not parsed, although the validator checks success/completion and turnround start at h23.5.

These are explicit frozen event hypotheses, so I cannot issue `GO_PRELAUNCH` for this exact validator. Add identity-specific h23.75 notice/creation events, first physical return, and both serial preparation subtask start/perform/completion sequences to the validator; keep the full-report comparison. Rehash the validator and runner's pin, repeat actual `-PreflightOnly`, then request exact-file review. No `independent-prelaunch-go.json` was written.

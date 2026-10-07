# Author read-only diagnosis: v1.0.7 native child

**Decision: NO_GO_FROZEN_BEHAVIOR_GATE.** This memo diagnoses the sole sealed run `c09-var02-v107-shortage-ssh-20261007-01`. It does not accept the prospective child, alter raw evidence, approve another native call, or infer a general return-duration rule.

## Evidence custody

- Frozen run closure: 460,162 bytes, SHA-256 `e09f5fa2549c088e4c3e25a9dc3acea660cac9e1331f4a012e3acaa981810715`; 23 raw SHA/size seals match.
- Failure seal: 6,848 bytes, SHA-256 `1a8cbc59efeeae35bc30af33854bf85121b9cdb73dc5f84b2a20ea4e8650ee3a`; 25 file seals match. Source hashes match before and after for all 1,726 manifest records.
- Unchanged child `model.log`: 16,958 bytes, SHA-256 `7783aa9918672f5579324d3b56043d0c2d5bb9ee465d8b8a61d5449aca24457b`. Unchanged `report-raw.json`: 59,461 bytes, SHA-256 `ac369021b872bf4d80c26396cc705a923b9b40b0a6077b067fea4277207c42d3`.
- The first five captured process steps exited with actual integer OS status 0 in SSH session 0; `check_behavior` exited 1. The original `author-validation.json` is 109 bytes, SHA-256 `3d762e4d3d127c3ee65323cad6f038f018eeb81d8ccbf2500fd45dec12e3f0ad`, and says `passed: false` with a bare `AssertionError`. The source verifier, import/export roundtrip and converter gates pass in the separate read-only audit.

## First frozen failure

The accepted ordinary control logs return transport task 0 starting at h9.46988 with printed `transportation time: 0.5` and arriving at h9.96988: 0.5 hours elapsed. The v1.0.7 child logs the same printed annotation and start, but arrival at h9.59488: 0.125 hours elapsed. Its HOME PM subtask starts at h9.59488 and the system PM task completes at h9.84488.

In the original live run, the frozen `physical_ledger.py` gate at line 81 required the return annotation to equal the printed start-to-arrival duration. A read-only replay of the frozen `physical()` function against the **unchanged** child log reproduces that assertion as its first behavior failure. Calling the complete frozen validator after sealing stops earlier at its deliberate nonempty-closure-error provenance gate; that post-seal behavior does not change the live failure location.

An **in-memory diagnostic only** replaces the single child annotation `0.5` with `0.125`. That synthetic string passes `physical()`, localizing the first assertion. No file was rewritten and the synthetic string is not accepted evidence. A separate author oracle diagnostic derives and compares all 1,754 report cells from the original unmodified child log with zero cell differences and finds terminal closure; it bypasses the frozen `physical()` rejection and therefore cannot promote this run. The printed annotation and measured elapsed time must remain distinct facts in any later retrospective review. This observation alone does not establish the native algorithm, a general TTRSS branch rule, or a valid replacement prospective gate.

## Reproduction

Run `review/author_failed_run_audit.py` read-only with the bundled Python and `-X utf8`. Its deterministic JSON stdout can be compared with `review/author-failed-run-diagnostic.json`. The script is 8,400 bytes, SHA-256 `9b847dd8b291912a25116da5fa63fcbd7418f0ae443a7fb05e4a1a1ddfd2be06`; the JSON is 2,515 bytes, SHA-256 `0805ff0624f897479c8e49b6a4bbcc3ce9b7ce1f668f3c4f46175c78c737da68`.

Keep v1.0.7 source, closure, failure files, original raw, approval and run identity frozen. The absent alternative child is not inferred from this run. Any different acceptance claim requires a separately reviewed contract and read-only replay of the unchanged raw; no continuation or rerun is authorized by this diagnosis.

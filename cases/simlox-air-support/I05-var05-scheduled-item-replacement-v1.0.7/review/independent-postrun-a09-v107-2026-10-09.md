# I05.var05 v1.0.7 independent failure replay

**Verdict:** NO_GO remains the status of the sealed v1.0.7 native attempt. The reported “duplicate system SURP task started: 0” is a **checker defect**. A separate read-only replay finds the three top-level SURP tasks, physical item flow, and the selected report assertions consistent with the frozen bounded contract. This review does not turn the failed checker exit into an accepted run.

## Exact evidence and custody

- review/v107-failure-seal.json: 6,315 bytes, SHA-256 90ab30ca55d18d1432a9b4f5ae0aab8d15375361c6855c4231ff2224bed9e7a0, Windows attributes 33.
- Independently verified all 14 raw_files and 10 supporting_files in that seal for path, byte count, SHA-256, and attributes: 24/24 match. The separate raw-custody map reconciles its 14 read-only copies with the same bytes and hashes.
- The seal records one native dispatch, zero retries, checker exit 1, and no behavior-validation file. Import, export, roundtrip, calculation, and JSON report completed before this behavior-check failure; the original status remains NO_GO_BEHAVIOR_CHECKER_FAILURE_PENDING_INDEPENDENT_REVIEW.
- validate_native_cli.py: 17,843 bytes, SHA-256 3a8994a9f0e5817901bd80231dec36bc488709f507bcd03f545e6af94407700f.

## Why the checker failed

At validate_native_cli.py lines 129-137, an unanchored re.search looks for “system SURP task <id> on <TEACH-AIR-01,0> started|completed” anywhere in a timed line. For task 0, physical line 38 is the actual top-level start, while lines 48 and 53 are nested remove/fit subtasks whose text also ends in “system SURP task 0 ... started”. The checker treats these as three starts of task 0 and raises on the second. The same loose pattern yields 18 matches across three task IDs; exact top-level line matching yields three starts and three completions.

## Independent bounded replay

The independent script matched the 214 physical log lines and 184 timed lines, with exact top-level task IDs 0, 2, and 4. Their observed start/end hours are 9.28145/10.7814, 21.2434/22.7434, and 32.6812/34.1812. Each is after hour 5 and lasts 1.5 hours; no immediate hour-5 SURP task appears.

Three damage/demand/issue/repair/return chains reconcile damaged IDs 1, 2, 3, issued spare IDs 0, 1, 2, and returned IDs 1, 2, 3. Each direct item repair lasts one hour, with a level-zero snapshot after issue and the corresponding level-one item snapshot after return. The sealed report has the accepted parent's four table/column rosters, 1 summary row, 72 System rows, 72 Stock rows, and 4,044 typed cells. The selected NDAM, NREPT, NDD, and NWT bin counts align with log events; NBO is zero and PNB is one in all 72 Stock bins. Both asserted System state partitions reconcile per bin. Integrated NSYRP exposure is 4.4999999851 hours against the 4.5-hour task ledger; terminal readiness is one, MSTF is one, and MSUF is zero.

**Limit:** This replay checks the bounded fields asserted by the frozen behavior checker. Other native report values have byte custody but no semantic acceptance here. The originally failed checker produced no validation receipt or ledger. A distinct source revision can anchor top-level SURP lines and test nested-subtask false positives; it needs its own review and gates. Do not rerun or reclassify v1.0.7 from this note.

## Reproducible read-only method

Python 3.12.14 executable: C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe, 106,448 bytes, SHA-256 10d845f50a2af64e3500bb2fcb348b5bc98a75d8ddada63e45ba1da6a1fc79d1.

Script: review/independent-a09-v107-replay.py, 11,336 bytes, SHA-256 53df33aa7890b5a3288249da044e722a25b86ef88ccf567893debef89e55b035. It imports no project checker and writes no sealed input. Run from any directory:

& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B 'C:\Users\user\Documents\Codex\2026-09-29\i05-var05-worktree\cases\simlox-air-support\I05-var05-scheduled-item-replacement-v1.0.7\review\independent-a09-v107-replay.py'

The original replay exit was 0. Its UTF-8 JSON stdout was saved separately as review/independent-a09-v107-replay-output.json, 1,774 bytes, SHA-256 d243438101ca27418471f23c2d2275a6577c77bc6f6e7d8dda356d5a5e09e33b. The script rechecks the sealed files and never invokes SIMLOX, SSH, the project runner, or the project checker.
# Independent v1.0.8 replay review — GO_REPLAY_ONLY

I independently reviewed the frozen v1.0.8 candidate and replayed its validator against private byte copies of the sealed v1.0.7 `model.log` and `report-raw.json`. This is acceptance of the corrected **replay interpretation only**. The original v1.0.7 runner result and its failure seal remain `NO_GO`; this review does not authorize a new native run or publication.

## Frozen custody and source change

- `source-freeze.json`: 3,245 bytes, SHA-256 `078ed313c0dd522d0753852b6f70613c8b15cca2708487c56cc44b8a41224fff`. All 10 listed v1.0.8 source files and all 28 v1.0.7 evidence references matched their declared byte length, SHA-256, and Windows attributes before replay and again afterward. The sealed raw directory retained exactly its 14 listed files. The v1.0.7 failure seal remained SHA-256 `90ab30ca55d18d1432a9b4f5ae0aab8d15375361c6855c4231ff2224bed9e7a0`.
- `validate_native_cli.py`: 18,124 bytes, SHA-256 `632e4e9c9d38d1e81382c82a89f12dab165a7a92930b310e2f415667ac1028f9`. Relative to v1.0.7, the top-level SURP matcher now requires the complete event line, excluding nested subtask lines. The cycle check removes only the unsupported `near(task_end, c_time)` equality and its error wording. It still requires three closed tasks of approximately 1.5 hours, no hour-5 task, the task start at the spare issue, one-hour direct repair, matching damaged-item identities, arrival/stock return at repair completion, and physical stock snapshots.
- The two-test parser source is 1,308 bytes, SHA-256 `8dcfed2cba11f5c73f3ecf0ae7416efbbb2da489e279225439faed0fb7755aa1`. It accepts nested remove/fit lines without creating duplicate top-level events and rejects duplicate top-level starts.

## Independent commands and original output

Capture method: `tmp/i05-var05-a17-v108-final-replay-capture.py`, 4,260 bytes, SHA-256 `c68cca26634d583fb25e9e669ae5ea150fe23469b1562ad4578b446d2f3a8c31`; runtime `python.exe`, 106,448 bytes, SHA-256 `10d845f50a2af64e3500bb2fcb348b5bc98a75d8ddada63e45ba1da6a1fc79d1`. Exact argument arrays, working directory, original stdout/stderr bytes, exits, and all stream hashes are in [capture.json](independent-final-replay-v108-20261009/capture.json), 5,524 bytes, SHA-256 `274f8f6e37b39e476a80c13789140ff57bcabd369998184cc8dbbd15066d318d`.

1. From the v1.0.8 package directory: `python.exe -B -m unittest -v test_surp_event_parser`. Exit `0`; stdout empty (SHA-256 `e3b0c442…`); stderr 459 bytes, SHA-256 `6315a4a1ea71cb3f0d0429f1600af9e2586ef24668341dd8e0de97f5fa8e8537`: both named tests passed, `Ran 2 tests`, `OK`.
2. From the same directory: `python.exe -B validate_native_cli.py C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\tmp\i05-var05-a17-v108-private-replay-20261009-01`. Exit `0`; stdout 1,029 bytes, SHA-256 `4d9b9d5825dbd009170f5f820990121cc5a8263c0cca5ee19af632b8bf33e091`; stderr empty. The private run directory contained only byte-identical copies of the sealed log and report before the validator wrote its derived ledger there. The originals were never passed as the run argument.

The validator reports `PASS_BOUNDED_EVENT_AND_SELECTED_REPORT_FIELDS`, 3 replacement tasks and damage cycles, task durations `[1.49995, 1.5, 1.5]`, 214 physical log lines (184 timed), 72 System and 72 Stock half-hour bins, and 4,044 typed report cells. It reconciles selected event counts, stock flows, state partitions, and approximately 4.5 hours of System repair exposure. The private derived ledger is 55,989 bytes, SHA-256 `2c9a357bf482ad175c241bccc0f85cfb590d36f7dda1010a368440505178295a`. Its first System task ends at 10.7814 while direct repair returns at 11.0314; the corresponding later pairs differ likewise. This is why task completion and physical return must remain separate assertions.

## Limits

The replay checks the report roster/column names, 4,044-cell count, 72-bin structure, and the selected fields named in the validator output. It **does not assert every value in the 4,044 cells**, other ResultSummary metrics, general stochastic timing, other seeds/stations/items, queue behavior, GUI behavior, or behavior of SURPD/SURPF changes. It cannot turn the failed v1.0.7 checker invocation into a historical success. No SSH, SIMLOX, native runner, or accepted-parent checker was invoked by this review.

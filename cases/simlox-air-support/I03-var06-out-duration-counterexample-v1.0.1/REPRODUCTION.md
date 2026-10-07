# Read-only reproduction

Run from the repository root with the bundled Python executable. The commands below write no existing evidence and start no SIMLOX process:

```powershell
$py = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$case = 'cases\simlox-air-support\I03-var06-out-duration-counterexample-v1.0.1'
& $py -X utf8 -B "$case\copy_v100_source.py"
& $py -X utf8 -B "$case\copy_context.py"
& $py -X utf8 -B "$case\verify_custody_v101.py"
& $py -X utf8 -B "$case\replay_v101.py"
& $py -X utf8 -B "$case\self_check_v101.py"
& $py -X utf8 -B "$case\review\independent_replay.py"
& $py -X utf8 -B "$case\review\independent_self_check.py"
```

Expected author result: 445 v1.0.0 source records, 214 accepted source disk/Git pairs, 118 accepted/context original raw records, all 26 original failed-child run files, 117 inert v1.0.0 source/review copies, 30 small context copies; full 32-table/220-cell source comparison with only PDESC/TFDT changed; 5,210 checked report cells per arm; original six process exits `[0,0,0,0,0,1]`; h6 printed4, h10 linked OUT arrival; zero new native calls. The author self-check rejects 19 in-memory semantic/provenance mutations after original seals. The frozen independent method is SHA-256 `80f73b72c52bc95d833a01f8d2f8835d4d194e41a06f39b0a7921c0d57126426`, with self-check SHA-256 `e020c751fd9e9e82ffe1a0ee1dbc7d898b4c90d5d5f952f5904cf74a87930cd3`. Its current read-only replay passes 20,433 checks and 5,210 report cells per arm; its self-check rejects 29 semantic mutations. The separate final independent acceptance decision is recorded outside these methods.

The required original ignored run paths include published I03.var02, C03 and C08 accepted context (118 raw records in `contract.json`) plus all 26 files under `../I03-var06-out-ignored-duration-v1.0.0/runs/i03-var06-out-dt4-v100-ssh-20261008-01`. Restore exact original bytes at those paths before replay; no synthetic replacement or native rerun. The three installed SIMLOX executable/manual/dictionary files are also checked by SHA. The historical v1.0.0 **non-run** source/review originals may be absent: `v100-source-custody.json` requires their exact inert owned copies and checks an original if present. `root-context-custody.json` does likewise for small tmp/transport/guard originals. The two large helper SSH fixture streams remain original historical pins rather than published byte copies; they are not substitutes for accepted or failed-child raw.

The current catalog is checked against the exact archived 491-entry local snapshot, with a separate base Git blob identity. Later entries are permitted only with unchanged typed first491 entries, unchanged metadata and unique IDs. The replay performs this check on every run; no post-append check is dropped. The old v1.0.0 prospective checker and its original independent reader are kept for failure provenance. They are not the v1.0.1 acceptance reader and may not replay successfully after catalog append.

Any missing mandatory raw file, source/Git mismatch, changed original failed verdict, h6/h10 task mismatch, unbalanced task quantity, extra/missing typed event, report metadata/cell mismatch or unknown numeric field rejects the classification. Preserve the original bytes and report the first failing gate. Do not edit the frozen v1.0.0 run or replace its failed checker receipt.

# Read-only reproduction and raw custody

## Originals to restore

Use the pinned [raw custody map](raw-custody-map.json) and [contract](contract.json) to restore the **original SHA/size bytes** before running the checker. The accepted parent map at `../C09-var02-lender-shortage-control-v0.1.1/raw-custody-map.json` lists nine dependency run directories with 117 raw records and the accepted ordinary-control directory with 13 raw records, their closures/invocations and the external C03 path. The new map lists all 26 retained files in `../C09-var02-lender-shortage-v1.0.7/runs/c09-var02-v107-shortage-ssh-20261007-01`, including its 23 closure raw seals and 25 failure-file seals. Both `runs/` directories are ignored by Git and remain local evidence. Do not substitute a new native run, rewrite a log or reconstruct missing files from a report.

The v1.0.7 manifest pins 1,726 source records. The merged parent evidence index pins 101 source Git/disk identities at `d1d9a4dcbcfe146a0de41e01c3089dae235bb7ef`, 130 raw files and 77 separate accepted local/Git identities. The parent publication-index snapshot is archived byte-for-byte under `../C09-var02-lender-shortage-v1.0.7/preserved-root-context/publication-index-at-base.json` because the live central index can later append entries. The 12 new `preserved-root-context/` files are exact named copies of originally pinned root `tmp/` receipts; the checker accepts only these declared copies if a `tmp/` original is unavailable. It never falls back to an arbitrary path. The original helper-test streams already have ten distinct named custody copies in the frozen v1.0.7 package.

## Commands

From the repository root in PowerShell, use the bundled Python. These commands **read** the sealed source and raw; they print deterministic JSON and do not write a verdict by default:

```powershell
$py = 'C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $py -B -X utf8 cases/simlox-air-support/C09-var02-lender-shortage-return-v0.1.0/replay.py
& $py -B -X utf8 cases/simlox-air-support/C09-var02-lender-shortage-return-v0.1.0/self_check.py
```

Expected author replay fields: `passed=true`, `decision=GO_AUTHOR_REPLAY_ONLY`, `original_run_decision=NO_GO_RUN`, `new_native_runs=0`, 1,754 source/event-derived report-cell checks **per arm** (3,508 total), 174 direct contract pins, accepted parent 101 source disk/Git, 77 separate local/Git references, 130 raw records, and v1.0.7 23 closure raw/25 failure-file seals. The observed cross-arm diff counts are ProblemDescription 1, ResultSummary 0, SystemResults 12, StockTotalResults 0, ResourceResults 6, ResourceResultsTotal 4. The oracle's unrounded ResourceResultsTotal.NRUM values differ about 1.67e-6 while native report values are equal; both arms pass the predeclared field bounds. The self-check expects 16 semantic rejections plus one within-bound serialization control. Saved LF JSON files are [author-validation.json](author-validation.json) and [author-self-check.json](author-self-check.json); Windows stdout may use CRLF, so compare parsed JSON or normalize line endings when checking deterministic output.

The independent reviewer uses a separate read-only script under `review/`, without importing the author checker. Its frozen SHA-256 is `02bb9d431f7cecfa0ba8f725d818cf5256d12bb25fe07e934dc095032f8e5d37`. Run:

```powershell
& $py -B -X utf8 cases/simlox-air-support/C09-var02-lender-shortage-return-v0.1.0/review/independent_replay.py
```

It prints a bounded retrospective GO result with 3,508 reconciled report cells and 53 rejecting semantic/provenance probes, without rewriting the frozen [independent verdict](review/independent-verdict.json). The [evidence index](evidence-index.json), once generated, lists exact publishable source bytes separately from ignored raw custody and accepted parent disk/Git identities.

## Failure diagnosis

- **Missing original or SHA/size mismatch:** stop. Use the exact directory and file identity in the raw custody map. The checker rejects missing dependency raw, closure, failure evidence and source pins. A byte-identical named archived root receipt is allowed only where explicitly declared; it cannot replace a run file.
- **Source or import/export mismatch:** inspect the two frozen inputs and native `roundtrip-raw.json` without editing them. Only ResourceRemoteSupport.TTRSS `0.5→0.125` and ProblemDescription.PDESC differ; all 32 authored table metadata and 25 row-containing table values must survive native export. Seven authored empty tables may have only all-null native placeholders.
- **Converter/provenance mismatch:** require six captured process records with integer OS exits `0,0,0,0,0,1`, session 0, unchanged GUI identity, exact error/warning/note contexts, original false author verdict and original NO_GO closure. A zero exit from another stage never overrides the failed sixth stage.
- **Ledger or report mismatch:** compare the unchanged raw printed return annotation and measured event interval separately. Inspect typed transport task, station receipt, resource booking/release, HOME PM and terminal edges. Expected report cells come from source and event intervals, not the native report itself. Null/ID/count/source-whole/zero-FTMO cells are exact; genuinely fractional fields use the contract's six declared bounds and only the two named h9 wait cells can use the conditional 3e-6 limit. Unknown edges or excess bounds fail closed.

The frozen v1.0.7 prospective **NO_GO_RUN** and the older v1.0.2 **NO_GO_PROSPECTIVE_PAIR** remain historical failures. This retrospective classification has no native command. A different input or new native test needs a new contract/version, independent review, unique run ID and root-controlled execution.

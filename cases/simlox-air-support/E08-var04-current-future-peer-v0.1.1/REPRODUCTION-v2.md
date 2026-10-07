# Read-only reproduction

Run these commands from the repository root in PowerShell using the bundled Python. They parse sealed raw in memory and do not launch SIMLOX:

```powershell
$py = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pkg = 'cases/simlox-air-support/E08-var04-current-future-peer-v0.1.1'
& $py -X utf8 -B "$pkg/replay.py"
& $py -X utf8 -B "$pkg/self_check_v2.py"
& $py -X utf8 -B "$pkg/review/independent_replay.py"
& $py -X utf8 -B "$pkg/make_evidence_index_v2.py"
```

Expected results: author `AUTHOR_PASS_PENDING_INDEPENDENT` with 303 pin checks and 48,684 report cells; author v2 self-check with 24 semantic rejections; independent `GO_BOUNDED` with 48,684 cells, two direct arms and six selected-station reports; dry index builder prints the committed index SHA/size and `written:false`. The independent replay is separate code and does not import the author replay. `self_check.py` and its 13-probe result are historical first-handoff artifacts; `self_check_v2.py` covers the additional frozen contract probes.

## Original evidence and custody

The two accepted package sections of `contract.json` name every original input, native run directory, closure, invocation and station selector. `raw-custody-map.json` lists 16 accepted runs (72 raw plus 16 closures and 16 invocations), six selectors, and excluded diagnostic run records with exact original path, byte size and SHA-256. These raw runs and binary selector files remain at their original ignored local paths. They are not copied into this package or synthesized from reports. Restore exact original bytes at those paths before replay; a missing file or SHA mismatch is a hard failure. The accepted source refs in `evidence-index-v2.json` keep local disk and published Git identities separate, including any differing byte representations.

Eleven small root selection/review receipts are copied byte-for-byte to `preserved-root-context/`; `context-custody-map.json` records both original `tmp/` paths and package copies. These are context receipts, not accepted native raw. The contract also pins 22 source files in excluded E08.var01 v1.0.0/v1.0.1 diagnostic packages that had no published Git identity. `preserved-excluded-source-v2/` and `excluded-source-custody-map-v2.json` retain exact byte-identical copies and original paths; those files are historical diagnostics, not accepted parents. The v2 map separately names the old rejected archive copy for each file. Four archived `.gitattributes`/`.gitignore` contents are saved with inert `.bytes` suffixes so they cannot modify Git handling of their neighbors. The old `preserved-excluded-source/` subtree is rejected local evidence and is excluded from v2 publication source files. If an original receipt or excluded source is missing in a fresh checkout, restore only its named exact v2 copy to its mapped original path after checking its hash; do not overwrite an existing file with different bytes. The author and independent historical readers use the original paths and fail closed otherwise. The original accepted runs, installed SIMLOX executable, PDF manual and dictionary must remain available at the paths declared in the contract.

`README.md` and `contract.json` are the frozen contract-stage snapshot. `README-publication.md` describes the later bounded replay result. v0.1.0 files and review NO_GO remain excluded historical evidence. `preserved-development/` contains exact available author draft sources/stdout/stderr, including one transport-receipt fixture error and one v2 station-key fixture error; these were not native failures. The source and raw mappings never promote those drafts.

## Failure diagnosis and change control

- A missing or changed source/raw/closure/invocation/selector pin means the original evidence has not been restored exactly. Check the named path against `raw-custody-map.json`, `context-custody-map.json` or `excluded-source-custody-map-v2.json`; do not regenerate it with a native run.
- A parser, typed route, physical ID or line-order failure means the observed trace differs from this fixed source and event contract. Inspect the original `model.log` alongside the failing label; keep it unchanged.
- A report metadata, null, whole-bin or numeric-bound failure means a cell does not follow the declared source/event formula and printed-time uncertainty. The bound is selected before reading the candidate cell; do not widen it to fit the report.
- A new input, seed, station arrangement, SIMLOX version or claim requires a new contract and independent review. This package does not authorize a native rerun.

The v2 evidence index pins package source, accepted dual byte identities, local raw records, root-context copies, the inert excluded-source copies and the independent verdict. The original `evidence-index.json` is preserved NO_GO_PUBLICATION_ARCHIVE_ATTRIBUTES history and is not an acceptance index. Later content/staged/remote review memos that bind the v2 index SHA are excluded from it to avoid a self-reference cycle.

# Read-only reproduction of B03.var01 v0.1.2

Run from the repository root using the bundled Python. These commands read sealed files and print JSON. They do not invoke SIMLOX or rewrite a saved verdict.

```powershell
$py = 'C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$case = 'cases/simlox-air-support/B03-var01-cold-first-full-report-v0.1.2'
& $py -X utf8 -B "$case/replay_v2.py"
& $py -X utf8 -B "$case/self_check_v2.py"
& $py -X utf8 -B "$case/review/independent_replay_v4.py"
& $py -X utf8 -B "$case/make_evidence_index.py"
```

Expected parsed results: author `GO_BOUNDED_AUTHOR_REPLAY`, 4,044 report cells and seven state integrals; author self-check 53 semantic rejections; independent `GO_BOUNDED`, 4,044 cells and 35 rejections. Independent root receipt separately records 37 more targeted rejections. The dry index builder must print the same SHA/size as [evidence-index.json](evidence-index.json), with `written: false`. Windows console CRLF output is byte-distinct from saved LF verdict JSON; compare parsed content unless a byte identity is explicitly stated.

Before replay, restore the original directories declared by `contract.json.parent_runs[*].original_directory` and all **29** B03 files in [raw-custody-map.json](raw-custody-map.json) at their original paths, retaining SHA-256 and size. The accepted B02 v1.0.2 `report-raw.json` listed there is a mandatory format-context byte pin only; it is not a B03 behavior parent. The 38 accepted B03/B02/A02 source files, their distinct local and base-Git bytes, installed SIMLOX executable/manual/dictionary, and base catalog must also be available. The checker verifies these before interpreting any candidate report. The two original B03 runs are never rerun or synthesized.

The archived historical catalog and root context are under `preserved-v011/` and `preserved-root-context/`; the 27 copied root probe scripts/receipts/streams and their original identities are in `preserved-root-v012-gates/custody-map.json`. Exact inert copies of unpublished NO_GO/context files are required, while their original untracked paths may be absent in a fresh checkout. If such an original exists, its bytes are checked. Accepted source, installed and raw run paths have no missing-file fallback. The live catalog may grow only while preserving the base prefix and metadata.

If a pin fails, recover the **original byte-identical** file at the declared path and rerun the read-only check. If parser, typed ledger, metadata, null, whole-bin or numeric-bound checks fail, keep the diagnostic; do not widen a bound, edit raw or treat a failed `-01` run as accepted. Any different input, new native call, or broader behavior claim requires a new frozen contract and independent review. `README.md` is the immutable contract-stage snapshot; [README-publication.md](README-publication.md) describes the later bounded content result. Historical v0.1.0/v0.1.1 and v0.1.2 author-v1 NO_GO decisions remain unchanged.

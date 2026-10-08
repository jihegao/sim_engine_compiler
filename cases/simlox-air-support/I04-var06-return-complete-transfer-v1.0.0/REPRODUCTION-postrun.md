# Read-only reproduction

This is a zero-new-native classification of the accepted I04.var01 original. These commands do not dispatch SIMLOX and do not rerun the accepted parent’s validators. They require the mandatory original 24 files and the separately recovered 24 read-only copies at the recorded host paths. A checkout without those host files can inspect the publication sources but cannot claim a full sealed replay.

From the repository root, in PowerShell with a Python 3.12 interpreter containing no special packages:

```powershell
$case = 'cases/simlox-air-support/I04-var06-return-complete-transfer-v1.0.0'
$py = 'C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $py -X utf8 -B "$case/author/source_gate.py"
& $py -X utf8 -B "$case/author/classify_v2.py" --sealed
& $py -X utf8 -B "$case/tests/self_check.py"
& $py -X utf8 -B "$case/review/independent_classifier.py" --sealed
& $py -X utf8 -B "$case/review/independent_self_check_v102.py"
& $py -X utf8 -B "$case/make_evidence_index.py"
```

The source gate checks the accepted parent’s 15 indexed sources, 76 dependency disk files and root-frozen Git-pair proof, 24 original raw files with unchanged attributes, 24 byte-equal read-only copies, manual/dictionary pins, parent verdict/signoff and distinct catalog500 byte identities. The classifier checks the exact input transfer row, full 117-line/103-timed native transcript and causal ledger, and selected report cells. The self-check mutates private in-memory clones below the original SHA gate and must reject every listed mutation; it does not edit historical originals. The evidence-index default command performs byte-only verification of the final published source closure and mandatory proof references; it must not write or regenerate the index.

`author/build_signature.py` is inert construction history for the frozen event-signature file. None of these verification commands imports or executes it, and default index verification never regenerates the event oracle.

The separately authored independent classifier and its original captured proof are required for bounded acceptance. The authoritative signed decision is `review/independent-verdict-v2.json` with `cli-scope-signoff-2026-10-08-v2.md`. The original author classifier and captured output contain an overbroad report-provenance field; `author/classify_v2.py` changes only that metadata key, and [the correction note](preserved-development/classify-v1-report-attribution-correction.md) preserves its original proof and limits. The original independent self-check draft is preserved as a false-assurance development result; `independent_self_check_v102.py` is the corrected active negative method. Repeating a classification capture requires a **new unique proof directory**, preserving earlier receipts and streams. Do not reuse or overwrite the accepted parent run directory or the existing recovery directory.

Original evidence is host-local and may not be present in a copied repository. The installed manual and unrelated private app context are never packaged. `gui_status=not_run`; no GUI, cross-engine, broad transfer-priority or performance conclusion follows.

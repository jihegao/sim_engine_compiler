# Read-only I03.var02 replay after catalog append

From the repository root, use bundled Python. These commands print results and do not launch SIMLOX or rewrite any frozen run/source/verdict file.

```powershell
$py = 'C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$case = 'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2'
& $py -X utf8 -B "$case/postrun_context.py"
& $py -X utf8 -B "$case/postappend_context_v2.py"
& $py -X utf8 -B "$case/make_raw_custody.py"
& $py -X utf8 -B "$case/postrun_audit.py"
& $py -X utf8 -B "$case/postappend_replay_v2.py"
& $py -X utf8 -B "$case/make_evidence_index_v2.py"
```

The original reviewer method may also be run directly with `& $py -X utf8 -B "$case/review/independent_replay_v3.py"`. It yields 14,995 checks after the 491st catalog entry; the saved native-acceptance verdict has 14,996 checks. The one-count difference is the source-code conditional for the **prepublication exact whole-file catalog** check. The remaining fields must compare recursively with exact JSON types and values, including 5,210 cells per arm, six child stages and 23 child raw seals. `postappend_replay_v2.py` requires this precise relationship; it rejects any other changed verdict field. The v2 dry builder must match [evidence-index-v2.json](evidence-index-v2.json) with `written:false`.

Restore the 34 accepted parent/context and 25 child original run bytes at paths in [raw-custody-map.json](raw-custody-map.json), preserving each size/SHA. Restore all accepted source, installed executable/manual/dictionary, and the named 490-entry historical catalog archive; the current live catalog may only append while retaining its prior entries and metadata. The 19 root/neutral-transport byte copies and eight postappend failure byte copies have explicit original/copy maps. Original unpublished tmp paths may be absent, but their named owned copies are mandatory and exact; accepted source, installed and raw run paths have no fallback.

Do not run the [v1 index builder](make_evidence_index.py) as a publication gate: its failure after append is preserved evidence, not a native result. The original v1 index/docs and all prelaunch sources are immutable. A missing pin requires byte-identical restoration. A changed typed event, report cell, metadata, source, closure or unknown formula remains NO_GO and must not be accommodated by changing a tolerance or reusing the native run. A new input/native test or broader claim requires a separate frozen contract and review.

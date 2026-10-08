# I04.var03 v1.0.1 postrun reproduction

Use the bundled Python interpreter with `-X utf8 -B` from this package. The current read-only path is:

```text
python -X utf8 -B source_gate.py --mode sealed
python -X utf8 -B copy_context.py
python -X utf8 -B copy_pure_proof.py
python -X utf8 -B make_source_inventory.py
python -X utf8 -B make_prelaunch_manifest.py
python -X utf8 -B review/independent_replay.py
python -X utf8 -B make_evidence_index.py
python -X utf8 -B make_evidence_index.py --dry
```

The frozen prospective [REPRODUCTION.md](REPRODUCTION.md) documents prelaunch commands. Its default `source_gate.py` mode is `live`, which intentionally requires the original 496-entry catalog bytes and an absent child run. Use `--mode sealed` for postrun verification. The sealed gate checks the owned local archive, distinct base Git blob, typed live catalog metadata and first 496 entries, plus global publication-ID uniqueness. Default and `--dry` index reconstruction must return the same canonical bytes after a later authorized catalog append. The independent reader uses the original accepted and child evidence; it is not a native or accepted-parent rerun.

The 153 raw originals in `raw-custody-map.json` and 15 preflight originals in `preflight-custody-map.json` remain mandatory at their sealed host paths. The small phase/audit proofs have byte-identical owned copies and optional-if-present original checks. Full app-context originals at historical indices 147 and 148 are a deliberate local-only exception: both are required at their exact local paths and are excluded from Git publication because they contain unrelated chats. The owned filtered derivatives and transformation map have distinct hashes and do not substitute for those originals. A checkout without the required host originals cannot claim full sealed replay.

For a new derived experiment, create a new package version and unique run ID, review its own input delta and full source/export/log/report oracle, and freeze a new source inventory and manifest. Keep the accepted parent and this run unchanged. Root must obtain a fresh actual SSH session 0 PowerShell 5 `-File` zero-native preflight, verify the current GUI identity, WTS state, serial mutex, absence of competing native processes and exact source map, then obtain a fresh independent GO_PRELAUNCH before one native dispatch. Preserve all original binary streams, actual integer exits and failure seals. The existing v1.0.0 excluded package and the accepted parent must not be relaunched for convenience.

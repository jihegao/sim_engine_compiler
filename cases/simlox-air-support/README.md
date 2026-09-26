# SIMLOX air-support teaching cases

This library follows issue #18. The catalog has 26 entries; this slice implements A01 and A02 only. The aircraft is a generic teaching asset, **not** a real F35/J35 or a J35-equivalent model. Native CLI behavior and GUI publication acceptance are separate statuses. The private GUI handoff is pending, and CLI probing came first.

## Find and reproduce

- [Catalog](catalog.json): mechanism, lineage and acceptance status.
- [Capabilities](capabilities.md): what is actually supported by local evidence.
- [A01](A01-single-aircraft-single-mission/README.md) and [A02](A02-single-aircraft-repeated-missions/README.md): contracts, mappings, expected timelines, immutable evidence.
- [Pairing contract](pairing-contract.json): minimal interface for AMD128; cross-engine status is unverified.
- [Known issues](known-issues/README.md): native configuration mistakes, output mapping and unresolved J35 contracts.

`native-schema.json` is a row-free table layout derived from the SHA-locked phase6 native JSON. It includes table/column names and datatypes, not source model rows. `tools/generate_native.py` builds checked `native-input.json` files from case parameters. It is a native SIMLOX table writer, not a second `spare_mvp` Project JSON interpreter. `tools/diff_native.py` proves A02 adds only two OperationProfile rows.

Large raw evidence lives on 4700-3 under `repo/data/local/simlox-case-library/v1/<case-id>/<immutable-run-id>/`, which Git ignores. To retrieve locally: `Get-ChildItem -Recurse -LiteralPath 'C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1'`. Each case evidence index lists exact run paths and SHA-256. Original exports remain byte-for-byte; the native report's trailing commas are normalized into `report-normalized.json` with both raw and derived hashes.

The runner refuses existing run directories and any active SIMLOX process. It checks the executable and input SHA, verifies import/export nonempty business rows, conversion errors, SXI/SXO size, parsed report and ENLOG before acceptance. On this host native execution has succeeded from the coordinator's SSH PowerShell launch context; direct Codex child processes had returned exit 0 without artifacts. The task-local runner retains the previously successful native working directory. Do not invoke parallel native batches or close a user's GUI.

## Publication gate

A01 and A02 reached `cli_behavior_verified` in separate final and fresh replay runs. They remain **provisional** until GUI calibration and GUI review are evidenced. A02 depends on A01 CLI behavior and may be a provisional CLI derivation; it is not described as a published child of a GUI-accepted A01. Future A03–F04 entries stay planned.

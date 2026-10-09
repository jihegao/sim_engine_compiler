from __future__ import annotations
import hashlib, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent
REPO = SUPPORT.parents[1]
CASE107 = SUPPORT / "I05-var05-scheduled-item-replacement-v1.0.7"
RAW = CASE107 / "runs/i05-var05-item-replacement-v107-ssh-20261009-01/raw"
SEAL = CASE107 / "review/v107-failure-seal.json"
GO = HERE / "review/independent-bounded-postrun-go-2026-10-09.json"
REPLAY = HERE / "review-corrected-replay.json"
INDEX_OUT = HERE / "evidence-index.json"
REVIEW_OUTPUTS_HOST_ONLY = {
    HERE / "review/independent-a09-publication-classification-v108-r2.json",
    HERE / "review/independent-a09-publication-classify-v108-r2.py",
    HERE / "review/independent-publication-content-a09-v108-r2-2026-10-09.md",
}

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def strict(path: Path):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out: raise ValueError(f"duplicate key: {k}")
            out[k] = v
        return out
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))

seal = strict(SEAL)
if sha(SEAL) != "90ab30ca55d18d1432a9b4f5ae0aab8d15375361c6855c4231ff2224bed9e7a0":
    raise SystemExit("v107 failure seal pin mismatch")
if len(list(RAW.iterdir())) != 14 or len(seal["raw_files"]) != 14:
    raise SystemExit("v107 raw directory is not exactly the sealed 14-file set")
for pin in seal["raw_files"]:
    path = RAW / Path(pin["path"]).name
    if path.stat().st_size != pin["bytes"] or sha(path) != pin["sha256"] or path.stat().st_file_attributes != pin["attributes"]:
        raise SystemExit(f"raw pin mismatch: {path.name}")
go = strict(GO)
if go.get("decision") != "GO_BOUNDED_POSTRUN" or go.get("source_run_id") != seal["run_id"]:
    raise SystemExit("independent bounded replay decision mismatch")
replay = strict(REPLAY)
if replay.get("status") != "PASS_BEHAVIOR_REPLAY_ON_SEALED_V107_RAW" or replay.get("replay_exit_code") != 0:
    raise SystemExit("corrected replay receipt mismatch")

source_files = []
for case in (CASE107, HERE):
    for path in sorted(case.rglob("*")):
        if not path.is_file() or path == INDEX_OUT or path in REVIEW_OUTPUTS_HOST_ONLY or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(REPO).as_posix()
        source_files.append({"path": rel, "bytes": path.stat().st_size,
                             "sha256": sha(path),
                             "windows_attributes": path.stat().st_file_attributes})
entry = strict(HERE / "publication-entry.json")
if entry["publication_id"] != "I05.var05.scheduled_item_replacement.1.0.8":
    raise SystemExit("publication identity mismatch")
base_index = HERE / "source-maps/publication-index-v1-before-v108.json.bytes"
base_catalog = HERE / "source-maps/catalog-v2-before-v108.json.bytes"
index = {
    "schema": "i05-var05-v108-closed-evidence-index/v1",
    "publication_id": entry["publication_id"],
    "scope_decision": "GO_BOUNDED_POSTRUN",
    "publication_state": "bounded_cli_accepted_for_reusable_publication",
    "new_native_runs": 0,
    "observed_native_run": seal["run_id"],
    "original_native_invocation_status": "NO_GO_BEHAVIOR_CHECKER_FAILURE",
    "corrected_replay_version": "1.0.8",
    "accepted_parent_runs_repeated": 0,
    "source_count": len(source_files),
    "source_files": source_files,
    "v107_failure_seal_sha256": sha(SEAL),
    "v108_replay_receipt_sha256": sha(REPLAY),
    "independent_bounded_postrun_go_sha256": sha(GO),
    "prepublication_catalog": {"bytes": base_catalog.stat().st_size, "sha256": sha(base_catalog)},
    "prepublication_index": {"bytes": base_index.stat().st_size, "sha256": sha(base_index)},
    "index_self_excluded": True,
}
INDEX_OUT.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"status":"EVIDENCE_INDEX_CREATED","source_count":len(source_files),
                  "index_bytes":INDEX_OUT.stat().st_size,"index_sha256":sha(INDEX_OUT),
                  "raw_files":len(seal["raw_files"]),"native_actions":0},sort_keys=True))

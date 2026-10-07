"""Independent read-only byte audit for the C02.var01 publication bundle."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parents[2]
INDEX = CASE / "evidence-index.json"
INDEX_SHA = "8bff77d2f543e82138e4191e6b83843f27b0b7fa684d3f919dd3399aed0f9221"
BASE = "1a80bbe5bcfb0351f27c55c7e0cf665bc761e4c6"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seal(path: Path, record: dict) -> None:
    raw = path.read_bytes()
    assert len(raw) == record["bytes"], (path, "bytes")
    assert sha(raw) == record["sha256"], (path, "sha256")


def main() -> None:
    original = INDEX.read_bytes()
    assert len(original) == 91203 and sha(original) == INDEX_SHA
    index = json.loads(original)
    assert index["schema"] == "c02-var01-personnel-zero-evidence-index/v1"
    assert index["source"] == index["source_files"]
    assert index["source_count"] == len(index["source_files"]) == 77
    assert index["raw_record_count_including_closure_invocation"] == len(index["raw_files"]) == 90
    assert index["accepted_source_ref_count"] == len(index["accepted_source_refs"]) == 47
    assert len(index["context_copies"]) == 23
    assert json.loads((CASE / "raw-custody-map.json").read_bytes()) == index["raw_files"]
    assert json.loads((CASE / "context-custody-map.json").read_bytes()) == index["context_copies"]
    assert index["child_raw_seals"] == 23 and index["accepted_context_raw_seals"] == 55
    assert index["child_run_file_count"] == 25
    assert index["native_runs"] == 1 and index["native_reruns"] == 0
    assert index["original_approved_replay_decision"] == "NO_GO_INDEPENDENT_REPLAY_BOM"
    assert index["bounded_decision"] == "GO_BOUNDED_AFTER_SEPARATE_READONLY_REPLAY_REPAIR"
    assert index["original_independent_method_sha256"] == "f3513bd42042597a49b6bf276117dc3a458d48ab079b4297b14a3be9aa19578f"
    assert index["corrected_readonly_method_sha256"] == "56f904d082c27320e906c95f29b7be7c038decbeb4dc02ee41c64c4c462a4d00"
    assert index["independent_verdict_sha256"] == "0d3369579cd8589f924b77d492090bf88f836177cb0a80b118eb7e20b1e7fc3c"
    assert index["independent_checks"] == 13434 and index["independent_report_cells"] == 10420
    assert index["run_id"] == "c02-var01-v101-personnel0-ssh-20261007-01"
    assert index["closure_sha256"] == "d418d9a3ea70b8c6358b5f94bfc99427ba84fb336f7c6bba193ef7268dcbe68d"

    paths = set()
    for entry in index["source_files"]:
        assert entry["path"] not in paths, entry["path"]
        paths.add(entry["path"])
        seal((CASE / entry["path"]).resolve(), entry)
    for entry in index["context_copies"]:
        seal((CASE / entry["copy_path"]).resolve(), entry)
        if Path(entry["original_path"]).is_file():
            seal(Path(entry["original_path"]), entry)
    raw_roles: dict[str, int] = {}
    for entry in index["raw_files"]:
        seal(Path(entry["original_path"]), entry)
        raw_roles[entry["role"]] = raw_roles.get(entry["role"], 0) + 1
    for entry in index["accepted_source_refs"]:
        local = (CASE / entry["path"]).resolve()
        seal(local, entry["local_disk"])
        rel = local.relative_to(ROOT).as_posix()
        result = subprocess.run(["git", "show", BASE + ":" + rel], cwd=ROOT,
                                capture_output=True, check=False)
        assert result.returncode == 0, (rel, "Git blob absent")
        assert len(result.stdout) == entry["published_git"]["bytes"], (rel, "Git bytes")
        assert sha(result.stdout) == entry["published_git"]["sha256"], (rel, "Git SHA")
    run = CASE / "runs" / index["run_id"]
    assert len(list(run.iterdir())) == 25
    assert sha((run / "closure.json").read_bytes()) == index["closure_sha256"]
    assert sha((run / "invocation.json").read_bytes()) == index["invocation_sha256"]
    manifest = json.loads((CASE / "prelaunch-manifest.json").read_bytes())
    assert len(manifest["source_files"]) == 155
    assert sha((CASE / "prelaunch-manifest.json").read_bytes()) == index["prelaunch_manifest_sha256"]
    print(json.dumps({"schema": "c02-var01-v101-independent-content-audit/v1",
                      "decision": "PASS", "source_files": len(paths), "context_copies": 23,
                      "raw_files": len(index["raw_files"]), "raw_roles": raw_roles,
                      "accepted_dual_refs": 47, "manifest_sources": 155,
                      "index_sha256": INDEX_SHA}, sort_keys=True))


if __name__ == "__main__":
    main()

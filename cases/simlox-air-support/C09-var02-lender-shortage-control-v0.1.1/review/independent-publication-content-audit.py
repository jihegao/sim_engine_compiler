"""Independent read-only exact-byte content audit; excluded from its own index."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
INDEX = PACKAGE / "evidence-index.json"
INDEX_SHA = "c76f768942de24e9733e61e5dcf44755430fe5b910593f842710588536d3ff50"


def digest(raw: bytes) -> dict:
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def check_file(record: dict) -> None:
    path = (PACKAGE / record["path"]).resolve()
    assert digest(path.read_bytes()) == {key: record[key] for key in ("bytes", "sha256")}, path


def main() -> None:
    assert digest(INDEX.read_bytes())["sha256"] == INDEX_SHA
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    assert index["schema"] == "simlox-air-support-evidence-index/v1"
    assert index["source_count"] == 101 and len(index["source_files"]) == 101
    assert index["raw_count"] == 130 and len(index["raw_files"]) == 130
    assert len(index["accepted_source_refs"]) == 77
    assert len({entry["path"] for entry in index["source_files"]}) == 101
    assert len({entry["path"] for entry in index["raw_files"]}) == 130
    assert index["positive_pair_accepted"] is False
    assert index["original_pair_decision"] == "NO_GO_PROSPECTIVE_PAIR"
    assert index["shortage_arm"] == "not_started_not_tested"
    assert index["new_native_runs"] == 0
    assert index["source_count"] == sum(len(index["source_files"]) for _ in [0])
    for record in index["source_files"]:
        assert "/runs/" not in record["path"] and not record["path"].endswith("evidence-index.json")
        check_file(record)
    for record in index["raw_files"]:
        check_file(record)
    base = index["accepted_source_base_commit"]
    assert len(base) == 40
    disk_git_different = 0
    for record in index["accepted_source_refs"]:
        path = (PACKAGE / record["path"]).resolve()
        assert digest(path.read_bytes()) == record["local_disk"], path
        rel = path.relative_to(REPO).as_posix()
        result = subprocess.run(["git", "show", f"{base}:{rel}"], cwd=REPO,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        assert digest(result.stdout) == record["published_git"], rel
        disk_git_different += record["local_disk"] != record["published_git"]
    custody = json.loads((PACKAGE / "raw-custody-map.json").read_text(encoding="utf-8"))
    assert custody["accepted_dependency_run_count"] == 9
    assert custody["accepted_dependency_raw_count"] == 117
    assert custody["sole_failed_ordinary"]["raw_count"] == 13
    assert custody["new_native_runs"] == 0
    custody_raw = {}
    for run in custody["accepted_dependencies"] + [custody["sole_failed_ordinary"]]:
        for key in ("closure", "invocation", "failure_seal"):
            if key in run:
                check_file(run[key])
        for record in run["raw"]:
            check_file(record)
            custody_raw[record["path"]] = record
    assert {record["path"]: record for record in index["raw_files"]} == custody_raw
    entry = json.loads((PACKAGE / "publication-entry-v1.json").read_text(encoding="utf-8"))
    for key in ("evidence", "readme", "reproduction_guide", "evidence_index", "contract", "signoff"):
        assert (PACKAGE.parent / entry[key]).is_file(), (key, entry[key])
    assert entry["new_native_runs"] == 0 and entry["positive_pair_accepted"] is False
    assert entry["original_pair_decision"] == "NO_GO_PROSPECTIVE_PAIR"
    print(json.dumps({"passed": True, "index_sha256": INDEX_SHA, "source_files": 101,
                      "accepted_source_refs": 77, "disk_git_distinct": disk_git_different,
                      "raw_files": 130, "accepted_runs": 9, "sole_failed_runs": 1,
                      "entry_links": 6}, sort_keys=True))


if __name__ == "__main__":
    main()

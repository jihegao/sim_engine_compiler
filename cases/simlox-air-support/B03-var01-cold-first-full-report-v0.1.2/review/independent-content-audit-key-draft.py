"""Independent read-only byte and publication-scope audit for B03.var01 v0.1.2."""

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = next(p for p in HERE.parents if (p / ".git").exists())
INDEX_SHA = "b0cae8348fa677c3d4ee1b0254f74361779cdede80ade1aebb49b64cb1caaf2a"
INDEX_SIZE = 116421


def identity(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def exact(path, record):
    data = path.read_bytes()
    assert identity(data) == {"bytes": record["bytes"], "sha256": record["sha256"]}, str(path)
    return data


def inside(root, rel):
    assert not Path(rel).is_absolute() and ".." not in Path(rel).parts, rel
    target = (root / rel).resolve()
    assert target.is_relative_to(root.resolve()), rel
    return target


def main():
    index_raw = (HERE / "evidence-index.json").read_bytes()
    assert identity(index_raw) == {"bytes": INDEX_SIZE, "sha256": INDEX_SHA}
    index = json.loads(index_raw)
    contract = json.loads((HERE / "contract.json").read_bytes())
    entry = json.loads((HERE / "publication-entry-draft.json").read_bytes())
    assert index["schema"] == "b03-var01-evidence-index/v0.1.2"
    assert index["source"] == index["source_files"] and index["source_count"] == len(index["source"]) == 129
    assert index["contract_sha256"] == identity((HERE / "contract.json").read_bytes())["sha256"]
    assert index["contract_sha256"] == "28765ddfeb99c595318d63cc0bd9e6a364bd2122d8a592b2fdd81a4d0a4cea44"
    assert index["publication_state"] == "reusable_published" and index["new_native_runs"] == 0
    assert index["report_cells_checked"] == 4044 and index["system_presentation_zero_cells"] == 360
    assert index["author_semantic_rejections"] == 53 and index["independent_semantic_rejections"] == 35
    assert index["author_v1_decision"] == "NO_GO_AUTHOR_METHOD_REVIEW"
    assert index["contract_v010_decision"] == "NO_GO_CONTRACT"
    assert index["contract_v011_decision"] == "NO_GO_FULL_REPORT_FORMULA_SCOPE"
    assert index["accepted_run_id"] == contract["parent_runs"][1]["run_id"]
    assert index["excluded_failed_run_id"] == contract["parent_runs"][0]["run_id"]

    seen = set()
    for record in index["source"]:
        rel = record["path"]
        assert rel not in seen and rel != "evidence-index.json" and not rel.startswith("review/independent-content")
        seen.add(rel)
        exact(inside(HERE, rel), record)
    expected_labels = {
        "contract.json", "replay_v2.py", "self_check_v2.py", "METHOD-v2.md",
        "author-verdict.json", "REPRODUCTION.md", "README-publication.md",
        "cli-scope-signoff-2026-10-07.md", "publication-entry-draft.json",
        "raw-custody-map.json", "review/independent_replay_v4.py",
        "review/independent-verdict-v012.json", "review/independent-postrun-go-2026-10-07.md",
        "review/independent-contract-go-2026-10-07.md",
    }
    assert expected_labels <= seen
    assert index["author_method_sha256"] == identity((HERE / "replay_v2.py").read_bytes())["sha256"]
    assert index["independent_method_sha256"] == identity((HERE / "review/independent_replay_v4.py").read_bytes())["sha256"]
    author_verdict = json.loads((HERE / "author-verdict.json").read_bytes())
    independent_verdict = json.loads((HERE / "review/independent-verdict-v012.json").read_bytes())
    assert author_verdict["report_cells"] == independent_verdict["full_expected_report_cells"] == 4044
    assert independent_verdict["decision"] == "GO_BOUNDED"
    assert independent_verdict["semantic_mutation_rejections"] == 35

    accepted = index["accepted_source_refs"]
    assert len(accepted) == len(contract["accepted_source_files"]) == 38
    accepted_by_path = {item["path"]: item for item in contract["accepted_source_files"]}
    assert len(accepted_by_path) == 38
    for record in accepted:
        target = (HERE / record["path"]).resolve()
        assert target.is_relative_to(REPO)
        rel = target.relative_to(REPO).as_posix()
        declared = accepted_by_path[rel]
        assert record["local_disk"] == declared["local_disk"]
        assert record["published_git_at_base"] == declared["published_git_at_base"]
        exact(target, record["local_disk"])
        git_raw = subprocess.check_output(["git", "show", f"{index['source_base_commit']}:{rel}"], cwd=REPO)
        assert identity(git_raw) == record["published_git_at_base"], rel

    raw_map = json.loads((HERE / "raw-custody-map.json").read_bytes())
    assert index["raw_record_count"] == len(index["raw_files"]) == raw_map["record_count"] == 30
    assert index["raw_files"] == raw_map["records"]
    assert sum(record["role"] == "format_corroboration_only" for record in index["raw_files"]) == 1
    assert sum(record["status"] == "excluded_failed_validation" for record in index["raw_files"]) > 0
    for record in index["raw_files"]:
        exact(Path(record["original_path"]), record)

    context = index["context_copies"]
    assert len(context) == 88
    for record in context:
        exact(inside(HERE, record["copy_path"]), record)
        original = Path(record["original_path"])
        assert original.exists() == record["original_present_at_build"]
        if original.exists():
            exact(original, record)
    for record in index["installed"].values():
        exact(Path(record["path"]), record)

    assert entry["publication_id"] == index["publication_id"]
    assert entry["case_id"] == index["case_id"] == "B03"
    assert entry["version"] == index["version"] == "0.1.2"
    assert entry["new_native_runs"] == 0
    assert entry["failed_parent_run_excluded"] == index["excluded_failed_run_id"]
    assert entry["evidence_index"] == f"{HERE.name}/evidence-index.json"
    for key in ("contract", "readme", "evidence", "reproduction_guide", "signoff"):
        assert (HERE.parent / entry[key]).is_file(), key
    assert "same-MTID" in entry["limits"] and "Historical per-child native PID/session unavailable" in entry["limits"]

    result = {"schema": "b03-var01-independent-content-audit/v0.1.2", "decision": "GO_CONTENT",
              "index_sha256": INDEX_SHA, "indexed_source_bytes": len(seen),
              "accepted_local_git_pairs": len(accepted), "raw_original_records": len(index["raw_files"]),
              "context_copies": len(context), "report_cells": 4044, "new_native_runs": 0}
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

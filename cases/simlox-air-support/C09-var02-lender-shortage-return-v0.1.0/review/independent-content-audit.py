"""Read-only byte and scope audit for the C09.var02 retrospective package.

This file is intentionally excluded from the package evidence index because it
binds that index's final SHA. It never imports the author replay/checker.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
INDEX = PKG / "evidence-index.json"
BASE = "d1d9a4dcbcfe146a0de41e01c3089dae235bb7ef"
INDEX_SHA = "546a179249ca03f98151c2274eb82be73d6890bdbf1a18bde786ce62d59becda"
CONTRACT_SHA = "18e3e6a04d5aeb328b5db4e21a6956a4bf1360fd89d9ab4b0577e57b5d7f9978"
METHOD_SHA = "02bb9d431f7cecfa0ba8f725d818cf5256d12bb25fe07e934dc095032f8e5d37"
VERDICT_SHA = "b0e8477c54efb21b074d2b9cfcb93b30682533b6118da158768837670f3a2dd6"
MEMO_SHA = "23b67a8549ba6f4d96de04ffbdcbf36bd930beb65e84691dd55d92f4efb63d71"


def identity(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read(path: Path) -> dict:
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def pin(path: Path, record: dict) -> None:
    assert identity(path.read_bytes()) == {key: record[key] for key in ("bytes", "sha256")}, path


def git_at_base(path: Path) -> bytes:
    relative = path.resolve().relative_to(REPO).as_posix()
    return subprocess.run(["git", "show", f"{BASE}:{relative}"], cwd=REPO,
                          check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def audit() -> dict:
    assert identity(INDEX.read_bytes())["sha256"] == INDEX_SHA
    index, contract = read(INDEX), read(PKG / "contract.json")
    assert identity((PKG / "contract.json").read_bytes())["sha256"] == CONTRACT_SHA
    assert (index["source_count"], index["raw_count"], len(index["accepted_source_refs"])) == (184, 156, 77)
    assert index["schema"] == "c09-var02-lender-return-retrospective-evidence-index/v1"
    assert (index["case_id"], index["variant_id"], index["new_native_runs"]) == ("C09", "C09.var02", 0)
    assert index["original_pair_decision"] == "NO_GO_PROSPECTIVE_PAIR"
    assert index["v107_child_decision"] == "NO_GO_RUN" and index["positive_pair_accepted"] is False
    assert index["retrospective_fixed_pair_classified"] is True
    assert (index["independent_report_cells"], index["independent_mutation_rejections"]) == (3508, 53)
    assert index["contract_sha256"] == CONTRACT_SHA and index["independent_method_sha256"] == METHOD_SHA
    assert index["independent_verdict_sha256"] == VERDICT_SHA
    assert index["accepted_source_base_commit"] == BASE
    source_paths, raw_paths = [], []
    for record in index["source_files"]:
        path = (PKG / record["path"]).resolve()
        pin(path, record)
        source_paths.append(path)
        assert path != INDEX and "runs" not in path.parts and "__pycache__" not in path.parts
    for record in index["raw_files"]:
        path = (PKG / record["path"]).resolve()
        pin(path, record)
        raw_paths.append(path)
    assert len(set(source_paths)) == 184 and len(set(raw_paths)) == 156
    current_sources = [path for path in source_paths if PKG in path.parents]
    assert len(current_sources) == 36 and len(source_paths) - len(current_sources) == 148
    for name, digest in (("review/independent_replay.py", METHOD_SHA),
                         ("review/independent-verdict.json", VERDICT_SHA),
                         ("review/independent-postrun-review-2026-10-07.md", MEMO_SHA)):
        path = PKG / name
        assert path in source_paths and identity(path.read_bytes())["sha256"] == digest
    refs_distinct = 0
    for record in index["accepted_source_refs"]:
        path = (PKG / record["path"]).resolve()
        assert identity(path.read_bytes()) == record["local_disk"]
        assert identity(git_at_base(path)) == record["published_git"]
        refs_distinct += record["local_disk"] != record["published_git"]
    assert refs_distinct == 2
    custody = read(PKG / "raw-custody-map.json")
    assert custody["new_native_runs"] == 0 and len(custody["owned_root_context_copies"]) == 12
    assert custody["failed_child"]["run_file_count"] == 26
    assert custody["failed_child"]["closure_raw_seal_count"] == 23
    assert custody["failed_child"]["failure_file_seal_count"] == 25
    for record in custody["owned_root_context_copies"]:
        path = PKG / "preserved-root-context" / record["path"]
        pin(path, record)
        assert path in source_paths
    for record in custody["failed_child"]["run_files"].values():
        path = (PKG / record["path"]).resolve()
        pin(path, record)
        assert path in raw_paths
    # Older failed v106 files are excluded, locally sealed dependencies. They
    # are not misreported as additional raw entries in this fixed-pair index.
    old = contract["excluded_v106"]
    assert len(old["original_run_files"]) == 11
    for record in old["original_run_files"]:
        pin((PKG / record["path"]).resolve(), record)
    v106_run = (PKG / old["original_run_files"][0]["path"]).resolve().parent
    v106_closure = read(v106_run / "closure.json")
    assert len(v106_closure["raw"]) == 8
    for name, record in v106_closure["raw"].items():
        pin(v106_run / name, record)
    assert read(v106_run / "failure-seal.json")["error"]
    verdict = read(PKG / "review/independent-verdict.json")
    assert verdict["decision"] == "GO_BOUNDED_RETROSPECTIVE_REPLAY_ONLY"
    assert verdict["original_prospective_v107"] == "NO_GO_RUN"
    assert verdict["checks"] == 3561 and verdict["failures"] == []
    assert sum(verdict["mutation_rejections"].values()) == 53
    author = read(PKG / "author-validation.json")
    assert author["decision"] == "GO_AUTHOR_REPLAY_ONLY" and author["original_run_decision"] == "NO_GO_RUN"
    assert author["control_report_cells"] == author["child_report_cells"] == 1754
    assert author["report_diff_cells_by_table"] == verdict["observed_changed_cells"]
    entry = read(PKG / "publication-entry-draft.json")
    assert entry["positive_pair_accepted"] is False and entry["new_native_runs"] == 0
    assert entry["v107_child_decision"] == "NO_GO_RUN"
    for key in ("evidence", "readme", "reproduction_guide", "evidence_index", "contract", "signoff"):
        assert (PKG.parent / entry[key]).is_file(), (key, entry[key])
    for name in ("README-publication.md", "REPRODUCTION.md"):
        guide = (PKG / name).read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", guide):
            if "://" not in target and not target.startswith("#"):
                assert (PKG / target.split("#")[0]).resolve().exists(), (name, target)
    guide = (PKG / "REPRODUCTION.md").read_text(encoding="utf-8")
    assert "review/independent_replay.py" in guide and "3,508" in guide and "53" in guide
    assert "NO_GO_RUN" in guide and "0.5" in guide and "0.125" in guide
    archive = read(PKG.parent / "C09-var02-lender-shortage-v1.0.7/preserved-root-context/publication-index-at-base.json")
    live = read(PKG.parent / "publication-index-v1.json")
    assert len(archive["entries"]) == 486 and live["entries"][:486] == archive["entries"]
    assert {k: v for k, v in live.items() if k != "entries"} == {k: v for k, v in archive.items() if k != "entries"}
    return {"decision": "GO_CONTENT_BYTE_AUDIT", "index_sha256": INDEX_SHA,
            "source_pins": 184, "current_package_source_pins": 36,
            "historical_source_pins": 148, "raw_pins": 156,
            "accepted_disk_git_refs": 77, "accepted_distinct_byte_refs": refs_distinct,
            "owned_root_context_copies": 12, "excluded_v106_original_run_files": 11,
            "excluded_v106_raw_seals": 8, "parent_catalog_entries_preserved": 486,
            "independent_report_cells": 3508, "independent_rejection_probes": 53,
            "new_native_runs": 0, "original_v107_decision": "NO_GO_RUN"}


if __name__ == "__main__":
    assert sys.argv[1:] == [], "usage: independent-content-audit.py"
    print(json.dumps(audit(), sort_keys=True, indent=2))

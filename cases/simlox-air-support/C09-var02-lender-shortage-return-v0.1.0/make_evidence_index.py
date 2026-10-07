"""Generate the bounded source/raw index only after both read-only replays pass.

The live evidence-index.json is excluded from its own source list. Later
content/staged/remote review memos are excluded to avoid an index cycle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from replay import BASE, CONTRACT, HERE, REPO, identity, read_json, replay
from self_check import check as self_check

OLD_PACKAGES = [BASE / f"C09-var02-lender-shortage-v1.0.{n}" for n in range(3, 8)]
REVIEW_PINS = {
    "review/independent_replay.py": "02bb9d431f7cecfa0ba8f725d818cf5256d12bb25fe07e934dc095032f8e5d37",
    "review/independent-verdict.json": "b0e8477c54efb21b074d2b9cfcb93b30682533b6118da158768837670f3a2dd6",
    "review/independent-postrun-review-2026-10-07.md": "23b67a8549ba6f4d96de04ffbdcbf36bd930beb65e84691dd55d92f4efb63d71",
    "review/independent-contract-go-2026-10-07.md": "e5d1f954d921310a2975006033d306e5904522a31188f51dc823c06fa9a443ca",
    "review/independent_contract_audit.py": "69127fc2d4ea76b66ac4be4a72eac514e613814cc69889cf4840f627c6815db8",
}
AUTHOR_PINS = {
    "contract.json": "18e3e6a04d5aeb328b5db4e21a6956a4bf1360fd89d9ab4b0577e57b5d7f9978",
    "author-validation.json": "2e6b9a8e296f34ed4d7ebf44dc855f50754e35ae911752c222a5c6c07f4de0e6",
    "author-self-check.json": "e9e37e4985786d72bdec0f8947786e9df571162e1c83b81cfcfb450d55407a81",
}


def rel(path: Path) -> str:
    return os.path.relpath(path, HERE).replace("\\", "/")


def source_files() -> list[dict]:
    found = []
    for directory in OLD_PACKAGES + [HERE]:
        assert directory.is_dir()
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or any(x in path.parts for x in ("runs", "__pycache__")):
                continue
            if path == HERE / "evidence-index.json":
                continue
            if path.parent.name == "review" and path.name.startswith((
                    "independent-content-", "independent-publication-",
                    "independent-staged-", "independent-remote-")):
                continue
            found.append({"path": rel(path), **identity(path)})
    paths = [r["path"] for r in found]
    assert len(paths) == len(set(paths))
    return sorted(found, key=lambda r: r["path"])


def raw_and_accepted() -> tuple[list[dict], list[dict]]:
    parent_index = BASE / "C09-var02-lender-shortage-control-v0.1.1/evidence-index.json"
    parent = read_json(parent_index)
    assert parent["source_count"] == 101 and parent["raw_count"] == 130
    assert len(parent["accepted_source_refs"]) == 77
    raw = []
    for record in parent["raw_files"]:
        original = (parent_index.parent / record["path"]).resolve()
        assert identity(original) == {"bytes": record["bytes"], "sha256": record["sha256"]}
        raw.append({"path": rel(original), "bytes": record["bytes"], "sha256": record["sha256"]})
    contract = read_json(CONTRACT)
    run_files = contract["v107_frozen_failure"]["run_files"]
    assert len(run_files) == 26
    for record in run_files.values():
        original = (HERE / record["path"]).resolve()
        assert identity(original) == {"bytes": record["bytes"], "sha256": record["sha256"]}
        raw.append({"path": rel(original), "bytes": record["bytes"], "sha256": record["sha256"]})
    refs = []
    for record in parent["accepted_source_refs"]:
        original = (parent_index.parent / record["path"]).resolve()
        assert identity(original) == record["local_disk"]
        refs.append({"path": rel(original), "local_disk": record["local_disk"],
                     "published_git": record["published_git"]})
    assert len(raw) == 156 and len(refs) == 77
    assert len({x["path"] for x in raw}) == len(raw)
    return sorted(raw, key=lambda r: r["path"]), sorted(refs, key=lambda r: r["path"])


def build() -> dict:
    for name, digest in AUTHOR_PINS.items():
        assert identity(HERE / name)["sha256"] == digest, name
    for name, digest in REVIEW_PINS.items():
        assert identity(HERE / name)["sha256"] == digest, name
    author = read_json(HERE / "author-validation.json")
    independently = read_json(HERE / "review/independent-verdict.json")
    assert author["passed"] is True and author["decision"] == "GO_AUTHOR_REPLAY_ONLY"
    assert author["original_run_decision"] == "NO_GO_RUN" and author["new_native_runs"] == 0
    assert author["control_report_cells"] == author["child_report_cells"] == 1754
    assert author["literal_pins"] == 174
    assert independently["decision"] == "GO_BOUNDED_RETROSPECTIVE_REPLAY_ONLY"
    assert independently["contract_sha256"] == AUTHOR_PINS["contract.json"]
    assert independently["method_sha256"] == REVIEW_PINS["review/independent_replay.py"]
    assert independently["total_reconciled_report_cells"] == 3508
    assert sum(independently["mutation_rejections"].values()) == 53
    assert independently["original_prospective_v107"] == "NO_GO_RUN"
    assert independently["new_native_runs"] == 0
    assert author["report_diff_cells_by_table"] == independently["observed_changed_cells"]
    result = replay()
    assert (json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8") == (
        HERE / "author-validation.json").read_bytes()
    probes = self_check()
    assert (json.dumps(probes, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8") == (
        HERE / "author-self-check.json").read_bytes()
    assert probes["semantic_rejections"] == 16
    sources = source_files()
    raw, accepted_refs = raw_and_accepted()
    assert any(r["path"] == "replay.py" for r in sources)
    assert any(r["path"] == "review/independent_replay.py" for r in sources)
    assert all((HERE / r["path"]).resolve().is_file() for r in sources)
    return {
        "schema": "c09-var02-lender-return-retrospective-evidence-index/v1",
        "case_id": "C09", "variant_id": "C09.var02", "version": "0.1.0",
        "classification": "retrospective_fixed_lender_return_contrast",
        "publication_state": "reusable_published", "new_native_runs": 0,
        "original_pair_decision": "NO_GO_PROSPECTIVE_PAIR",
        "positive_pair_accepted": False, "v107_child_decision": "NO_GO_RUN",
        "retrospective_fixed_pair_classified": True,
        "contract_sha256": AUTHOR_PINS["contract.json"],
        "author_verdict_sha256": AUTHOR_PINS["author-validation.json"],
        "author_semantic_rejections": 16,
        "independent_verdict_sha256": REVIEW_PINS["review/independent-verdict.json"],
        "independent_method_sha256": REVIEW_PINS["review/independent_replay.py"],
        "independent_report_cells": 3508,
        "independent_mutation_rejections": 53,
        "accepted_source_base_commit": "d1d9a4dcbcfe146a0de41e01c3089dae235bb7ef",
        "accepted_source_ref_count": len(accepted_refs),
        "accepted_control_and_dependencies_raw_count": 130,
        "failed_v107_run_file_count": 26,
        "failed_v107_closure_raw_count": 23,
        "failed_v107_failure_file_count": 25,
        "failed_v107_manifest_source_count": 1726,
        "raw_location_policy": "Ignored original accepted/control and failed-child run directories remain local. Restore exact SHA/size bytes using raw-custody-map.json; no native rerun or synthetic replacement. Distinct Git/local accepted source identities are separately pinned.",
        "scope": "Unchanged raw printed return label0.5 is retained separately from matched child elapsed0.125; fixed control elapsed0.5. Full typed ledgers and 1754 source/event-derived report cells per arm pass independent read-only replay. Original prospective v107 remains failed.",
        "source_count": len(sources), "source_files": sources,
        "raw_count": len(raw), "raw_files": raw,
        "accepted_source_refs": accepted_refs,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    index = build()
    data = (json.dumps(index, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / "evidence-index.json"
    if args.write:
        assert not target.exists(), "never overwrite a frozen index"
        target.write_bytes(data)
    print(json.dumps({"source_count": index["source_count"], "raw_count": index["raw_count"],
                      "accepted_source_refs": len(index["accepted_source_refs"]),
                      "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                      "written": args.write}, sort_keys=True))

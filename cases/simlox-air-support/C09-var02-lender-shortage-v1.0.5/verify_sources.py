"""Read-only verification of the merged control, all original raw and v1.0.5 source pins."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONTRACT = HERE / "contract.json"
ROOT_CONTEXT_NAMES = {
    "c09-var02-v104-owner-snapshot-initial-20261007.json",
    "c09-var02-v105-owner-snapshot-initial-20261007.json",
    "c09-var02-v103-selection-20261007.json",
    "c09-pr516-publication-closure-20261007.json",
}


def digest(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def resolve(path: str, base: Path = HERE) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (base / p).resolve()


def check(path: Path, pin: dict) -> None:
    assert digest(path) == {"bytes": pin["bytes"], "sha256": pin["sha256"]}, path


def git_digest(path: Path, commit: str) -> dict:
    rel = path.relative_to(REPO).as_posix()
    raw = subprocess.check_output(["git", "-C", str(REPO), "show", f"{commit}:{rel}"])
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def all_literal_pins(node: object, counts: dict, *, catalog_mode: str) -> None:
    if isinstance(node, dict):
        if {"path", "bytes", "sha256"} <= set(node):
            source_path = Path(node["path"])
            if catalog_mode == "sealed_replay" and node["path"] == "../publication-index-v1.json":
                check(HERE / "preserved-root-context" / "publication-index-at-base.json", node)
            elif (catalog_mode == "sealed_replay" and source_path.is_absolute() and
                  source_path.parent.name == "tmp" and source_path.name in ROOT_CONTEXT_NAMES):
                check(HERE / "preserved-root-context" / source_path.name, node)
            else:
                check(resolve(node["path"]), node)
            counts["contract_literal_pins"] += 1
        for value in node.values():
            all_literal_pins(value, counts, catalog_mode=catalog_mode)
    elif isinstance(node, list):
        for value in node:
            all_literal_pins(value, counts, catalog_mode=catalog_mode)


def verify(*, mode: str = "preflight") -> dict:
    assert mode in {"preflight", "live_run", "sealed_replay"}
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert c["schema"] == "simlox-c09-var02-lender-shortage-v105-child-contract/v1"
    assert c["base_commit"] == "d1d9a4dcbcfe146a0de41e01c3089dae235bb7ef"
    assert c["ownership"]["author_owns"]["current_package"] == HERE.name
    assert c["planned_child"]["run_id"] == "c09-var02-v105-shortage-ssh-20261007-01"
    run = HERE / c["planned_child"]["run_directory"]
    if mode == "preflight":
        assert not run.exists()
    else:
        assert run.is_dir()
        if mode == "sealed_replay":
            assert (run / "closure.json").is_file()
    counts = {"contract_literal_pins": 0, "parent_source_disk_git": 0,
              "accepted_dual_refs": 0, "parent_raw": 0, "custody_runs": 0,
              "custody_raw": 0, "custody_closures": 0, "custody_invocations": 0,
              "excluded_attribute_files": 0}
    all_literal_pins(c, counts, catalog_mode=mode)
    catalog_pin = c["published_parent"]["catalog"]
    archived = HERE / "preserved-root-context" / "publication-index-at-base.json"
    check(archived, catalog_pin)
    git_catalog = subprocess.check_output(["git", "-C", str(REPO), "show",
                                           f"{c['base_commit']}:cases/simlox-air-support/publication-index-v1.json"])
    assert len(git_catalog) == 482723 and hashlib.sha256(git_catalog).hexdigest() == "e8d50785f23c2458b86395bd782c109c691dc8aa132ae977fe374702c6411f17"
    assert json.loads(archived.read_text(encoding="utf-8-sig")) == json.loads(git_catalog)
    for receipt in c["root_selection_and_owner_receipts"].values():
        if isinstance(receipt, dict) and {"path", "bytes", "sha256"} <= set(receipt):
            check(HERE / "preserved-root-context" / Path(receipt["path"]).name, receipt)
    index_pin = c["published_parent"]["evidence_index"]
    index_path = resolve(index_pin["path"])
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["source_count"] == 101 and index["raw_count"] == 130
    assert len(index["accepted_source_refs"]) == 77
    assert index["original_pair_decision"] == "NO_GO_PROSPECTIVE_PAIR"
    assert index["positive_pair_accepted"] is False and index["shortage_arm"] == "not_started_not_tested"
    for rec in index["source_files"]:
        path = resolve(rec["path"], index_path.parent)
        check(path, rec)
        assert git_digest(path, c["base_commit"]) == {"bytes": rec["bytes"], "sha256": rec["sha256"]}, path
        counts["parent_source_disk_git"] += 1
    for rec in index["accepted_source_refs"]:
        path = resolve(rec["path"], index_path.parent)
        check(path, rec["local_disk"])
        assert git_digest(path, c["base_commit"]) == rec["published_git"], path
        counts["accepted_dual_refs"] += 1
    for rec in index["raw_files"]:
        check(resolve(rec["path"], index_path.parent), rec)
        counts["parent_raw"] += 1
    custody_pin = c["published_parent"]["raw_custody_map"]
    custody_path = resolve(custody_pin["path"])
    custody = json.loads(custody_path.read_text(encoding="utf-8"))
    assert custody["accepted_dependency_run_count"] == 9
    assert custody["accepted_dependency_raw_count"] == 117
    assert custody["sole_failed_ordinary"]["raw_count"] == 13
    for run in custody["accepted_dependencies"] + [custody["sole_failed_ordinary"]]:
        counts["custody_runs"] += 1
        for key in ("closure", "invocation"):
            rec = run[key]
            check(resolve(rec["path"], custody_path.parent), rec)
            counts["custody_closures" if key == "closure" else "custody_invocations"] += 1
        if "failure_seal" in run:
            check(resolve(run["failure_seal"]["path"], custody_path.parent), run["failure_seal"])
        for rec in run["raw"]:
            check(resolve(rec["path"], custody_path.parent), rec)
            counts["custody_raw"] += 1
    assert counts["custody_runs"] == 10 and counts["custody_raw"] == 130
    for old in ("1.0.3", "1.0.4"):
        path = HERE.parent / f"C09-var02-lender-shortage-v{old}" / ".gitattributes"
        assert path.read_bytes() == b"* -text\n", path
        counts["excluded_attribute_files"] += 1
    child_pin = c["planned_child"]["input_parent"]
    assert digest(resolve(child_pin["path"])) == {"bytes": child_pin["bytes"], "sha256": child_pin["sha256"]}
    return {"schema": "c09-var02-v105-source-verification/v1", "passed": True, "mode": mode,
            "contract_sha256": digest(CONTRACT)["sha256"], "base_commit": c["base_commit"], "counts": counts}


if __name__ == "__main__":
    try:
        result = verify(mode="sealed_replay" if "--sealed-replay" in sys.argv else "preflight")
    except Exception as exc:
        result = {"schema": "c09-var02-v105-source-verification/v1", "passed": False,
                  "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    sys.exit(0 if result["passed"] else 1)

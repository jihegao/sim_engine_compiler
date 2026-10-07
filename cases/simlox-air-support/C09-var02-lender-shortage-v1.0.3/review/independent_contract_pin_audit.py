"""Read-only independent C09.var02 v1.0.3 contract/published-parent audit."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
EXPECTED_CONTRACT = "e9c694d3e52ab78125baae955fa77e7ef9bae7900a3d212638942af13ff1c0e8"
EXPECTED_README = "1d26d969b4c073c1feaeaa4a354db4388a5db42b711fc5097868fe301cdf7a2a"


def digest(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def git_show(commit: str, path: Path) -> bytes:
    rel = path.resolve().relative_to(REPO).as_posix()
    return subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=REPO,
                          check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def main() -> None:
    assert digest((PACKAGE / "contract.json").read_bytes()) == {
        "bytes": 18351, "sha256": EXPECTED_CONTRACT}
    assert digest((PACKAGE / "README.md").read_bytes()) == {
        "bytes": 1707, "sha256": EXPECTED_README}
    contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
    base = contract["base_commit"]
    assert base == "d1d9a4dcbcfe146a0de41e01c3089dae235bb7ef"
    direct = []
    def walk(node):
        if isinstance(node, dict):
            if {"path", "bytes", "sha256"} <= set(node):
                path = Path(node["path"])
                path = path if path.is_absolute() else (PACKAGE / path).resolve()
                assert digest(path.read_bytes()) == {"bytes": node["bytes"], "sha256": node["sha256"]}, path
                direct.append(str(path))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(contract)
    index_path = PACKAGE / contract["published_parent"]["evidence_index"]["path"]
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(index["source_files"]) == 101 and len(index["raw_files"]) == 130
    assert len(index["accepted_source_refs"]) == 77
    for record in index["source_files"]:
        path = (index_path.parent / record["path"]).resolve()
        target = {k: record[k] for k in ("bytes", "sha256")}
        assert digest(path.read_bytes()) == digest(git_show(base, path)) == target, path
    for record in index["raw_files"]:
        path = (index_path.parent / record["path"]).resolve()
        assert digest(path.read_bytes()) == {k: record[k] for k in ("bytes", "sha256")}, path
    distinct = 0
    for record in index["accepted_source_refs"]:
        path = (index_path.parent / record["path"]).resolve()
        assert digest(path.read_bytes()) == record["local_disk"], path
        assert digest(git_show(base, path)) == record["published_git"], path
        distinct += record["local_disk"] != record["published_git"]
    assert distinct == 2
    custody_path = PACKAGE / contract["published_parent"]["raw_custody_map"]["path"]
    custody = json.loads(custody_path.read_text(encoding="utf-8"))
    assert custody["accepted_dependency_run_count"] == 9
    assert custody["accepted_dependency_raw_count"] == 117
    assert custody["sole_failed_ordinary"]["raw_count"] == 13
    for run in custody["accepted_dependencies"] + [custody["sole_failed_ordinary"]]:
        for key in ("closure", "invocation", "failure_seal"):
            if key in run:
                record = run[key]
                path = (custody_path.parent / record["path"]).resolve()
                assert digest(path.read_bytes()) == {k: record[k] for k in ("bytes", "sha256")}, path
        for record in run["raw"]:
            path = (custody_path.parent / record["path"]).resolve()
            assert digest(path.read_bytes()) == {k: record[k] for k in ("bytes", "sha256")}, path
    ordinary = json.loads((PACKAGE / contract["planned_child"]["input_parent"]["path"]).read_text(encoding="utf-8"))
    tables = {table["name"]: table for table in ordinary["model"]["tables"]}
    assert len(tables) == 32
    assert sum(bool(inst["rows"]) for table in tables.values() for inst in table["instances"]) == 25
    rrs = tables["ResourceRemoteSupport"]
    cols = [column["name"] for column in rrs["columns"]]
    rows = [row for inst in rrs["instances"] for row in inst["rows"]]
    selected = [dict(zip(cols, row)) for row in rows if dict(zip(cols, row)).get("RID") == "P-MECH"
                and dict(zip(cols, row)).get("STID") == "BASE-01"
                and dict(zip(cols, row)).get("RSTID") == "BASE-02"]
    assert len(selected) == 1
    assert (selected[0]["TFRS"], selected[0]["TTRS"], selected[0]["TTRSS"]) == (.25, .5, .5)
    desc = tables["ProblemDescription"]["instances"][0]["rows"][0][0]
    assert desc == "ordinary TTRSS equals TTRS"
    assert not (PACKAGE / contract["planned_child"]["run_directory"]).exists()
    selection = json.loads((REPO / "tmp/c09-var02-v103-selection-20261007.json").read_text(encoding="utf-8"))
    recorded_utc = selection["ssh_snapshot_utc"]
    contract_label = contract["ownership"]["live_precontract"]
    timezone_consistent = "13:03:41 Asia/Shanghai" in contract_label
    print(json.dumps({"contract_sha256": EXPECTED_CONTRACT, "direct_pin_records": len(direct),
                      "direct_unique_paths": len(set(direct)), "source_disk_and_git": 101,
                      "accepted_source_refs": 77, "distinct_disk_git_refs": distinct,
                      "local_raw_seals": 130, "custody_accepted_runs": 9,
                      "parent_tables": 32, "parent_populated_instances": 25,
                      "parent_rrs": {k: selected[0][k] for k in ("RID", "STID", "RSTID", "TFRS", "TTRS", "TTRSS")},
                      "child_run_absent": True, "snapshot_utc": recorded_utc,
                      "snapshot_label": contract_label, "timezone_consistent": timezone_consistent},
                     sort_keys=True))


if __name__ == "__main__":
    main()

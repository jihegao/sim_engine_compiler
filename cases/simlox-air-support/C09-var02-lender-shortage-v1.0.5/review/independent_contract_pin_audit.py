"""Independent read-only byte and topology audit for the frozen v1.0.5 contract."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
CONTRACT_SHA = "faf40af730062c6a2415e207cac9833e6534b03225d820f9e02e7f070b4f1d4e"
README_SHA = "f410a29a66ef5ce5b6e96976113b921f9668f3836c9b727254fd41d146a03e56"
BASE = "d1d9a4dcbcfe146a0de41e01c3089dae235bb7ef"


def seal(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def disk(path: Path, expected: dict) -> None:
    assert seal(path.read_bytes()) == {k: expected[k] for k in ("bytes", "sha256")}, path


def committed(path: Path) -> bytes:
    rel = path.resolve().relative_to(REPO).as_posix()
    return subprocess.run(["git", "show", f"{BASE}:{rel}"], cwd=REPO,
                          check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def main() -> None:
    assert seal((PKG / "contract.json").read_bytes()) == {"bytes": 22919, "sha256": CONTRACT_SHA}
    assert seal((PKG / "README.md").read_bytes()) == {"bytes": 2240, "sha256": README_SHA}
    c = json.loads((PKG / "contract.json").read_text(encoding="utf-8"))
    assert c["base_commit"] == BASE
    assert c["ownership"]["author_owns"]["current_package"] == PKG.name
    assert c["planned_child"]["run_id"] == "c09-var02-v105-shortage-ssh-20261007-01"
    literal = []

    def walk(node):
        if isinstance(node, dict):
            if {"path", "bytes", "sha256"} <= node.keys():
                p = Path(node["path"])
                p = p if p.is_absolute() else (PKG / p).resolve()
                disk(p, node)
                literal.append(str(p))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(c)
    idxpath = (PKG / c["published_parent"]["evidence_index"]["path"]).resolve()
    idx = json.loads(idxpath.read_text(encoding="utf-8"))
    assert (len(idx["source_files"]), len(idx["raw_files"]), len(idx["accepted_source_refs"])) == (101, 130, 77)
    for rec in idx["source_files"]:
        p = (idxpath.parent / rec["path"]).resolve()
        disk(p, rec)
        assert seal(committed(p)) == {k: rec[k] for k in ("bytes", "sha256")}
    for rec in idx["raw_files"]:
        disk((idxpath.parent / rec["path"]).resolve(), rec)
    distinct = 0
    for rec in idx["accepted_source_refs"]:
        p = (idxpath.parent / rec["path"]).resolve()
        disk(p, rec["local_disk"])
        assert seal(committed(p)) == rec["published_git"]
        distinct += rec["local_disk"] != rec["published_git"]
    assert distinct == 2
    custody_path = (PKG / c["published_parent"]["raw_custody_map"]["path"]).resolve()
    custody = json.loads(custody_path.read_text(encoding="utf-8"))
    assert (custody["accepted_dependency_run_count"], custody["accepted_dependency_raw_count"],
            custody["sole_failed_ordinary"]["raw_count"]) == (9, 117, 13)
    for run in custody["accepted_dependencies"] + [custody["sole_failed_ordinary"]]:
        for key in ("closure", "invocation", "failure_seal"):
            if key in run:
                rec = run[key]
                disk((custody_path.parent / rec["path"]).resolve(), rec)
        for rec in run["raw"]:
            disk((custody_path.parent / rec["path"]).resolve(), rec)
    parent = json.loads((PKG / c["planned_child"]["input_parent"]["path"]).read_text(encoding="utf-8"))
    tables = {t["name"]: t for t in parent["model"]["tables"]}
    assert len(tables) == 32
    assert sum(bool(i["rows"]) for t in tables.values() for i in t["instances"]) == 25
    t = tables["ResourceRemoteSupport"]
    cols = [x["name"] for x in t["columns"]]
    rows = [dict(zip(cols, r)) for i in t["instances"] for r in i["rows"]]
    chosen = [r for r in rows if (r.get("RID"), r.get("STID"), r.get("RSTID")) ==
              ("P-MECH", "BASE-01", "BASE-02")]
    assert len(chosen) == 1
    assert (chosen[0]["TFRS"], chosen[0]["TTRS"], chosen[0]["TTRSS"]) == (0.25, 0.5, 0.5)
    assert not (PKG / c["planned_child"]["run_directory"]).exists()
    old = json.loads((REPO / "tmp/c09-var02-v103-selection-20261007.json").read_text(encoding="utf-8"))
    new = json.loads((REPO / "tmp/c09-var02-v105-owner-snapshot-initial-20261007.json").read_text(encoding="utf-8"))
    assert new["utc"] == "2026-10-07T05:19:23.0382130Z"
    assert new["ssh_present"] and new["self_session"] == 0 and new["powershell_major"] == 5
    assert new["mutex_free"] and new["runner_candidates"] == []
    assert new["session_query_exit"] == 0 and new["active_gui_session1_count"] == 1
    assert len(new["native"]) == 1 and new["native"][0] == {
        "pid": 13340, "session": 1, "start_utc": "2026-09-28T10:09:56.8261381Z",
        "start_ms": 1790590196826, "responding": True}
    assert not any(new[k] for k in ("v103_run_exists", "v105_run_exists", "old_shortage_run_exists"))
    print(json.dumps({"contract_sha256": CONTRACT_SHA, "literal_pin_records": len(literal),
                      "literal_unique_paths": len(set(literal)), "parent_source_disk_git": 101,
                      "parent_raw": 130, "accepted_refs": 77, "distinct_disk_git": distinct,
                      "custody_runs": 9, "custody_accepted_raw": 117, "failed_ordinary_raw": 13,
                      "parent_tables": 32, "parent_populated_instances": 25,
                      "v105_run_absent": True, "v103_snapshot_utc": old["ssh_snapshot_utc"],
                      "v105_snapshot_utc": new["utc"],
                      "author_owns": c["ownership"]["author_owns"]}, sort_keys=True))


if __name__ == "__main__":
    main()

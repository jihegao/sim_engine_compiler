"""Read-only byte and lineage audit for the retrospective contract-only gate."""
from __future__ import annotations

import hashlib
import json
import runpy
import subprocess
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
PARENT = PKG.parent / "C09-var02-lender-shortage-control-v0.1.1"
CHILD = PKG.parent / "C09-var02-lender-shortage-v1.0.7"
RUN = CHILD / "runs/c09-var02-v107-shortage-ssh-20261007-01"
BASE = "d1d9a4dcbcfe146a0de41e01c3089dae235bb7ef"
CONTRACT_SHA = "18e3e6a04d5aeb328b5db4e21a6956a4bf1360fd89d9ab4b0577e57b5d7f9978"
INDEX_SHA = "c76f768942de24e9733e61e5dcf44755430fe5b910593f842710588536d3ff50"


def identity(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check(path: Path, record: dict) -> None:
    assert identity(path.read_bytes()) == {key: record[key] for key in ("bytes", "sha256")}, path


def json_file(path: Path):
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def literal_pins(node):
    if isinstance(node, dict):
        if "sha256" in node and "bytes" in node and ("path" in node or "repo_relative" in node):
            yield node
        for value in node.values():
            yield from literal_pins(value)
    elif isinstance(node, list):
        for value in node:
            yield from literal_pins(value)


def main() -> None:
    assert identity((PKG / "contract.json").read_bytes())["sha256"] == CONTRACT_SHA
    contract = json_file(PKG / "contract.json")
    assert contract["base_commit"] == BASE
    assert contract["case_id"] == "C09"
    direct = list(literal_pins(contract))
    assert len(direct) == 174
    for record in direct:
        if "repo_relative" in record:
            target = REPO / record["repo_relative"]
        else:
            target = Path(record["path"])
            if not target.is_absolute():
                target = (PKG / target).resolve()
        check(target, record)

    index_path = PARENT / "evidence-index.json"
    assert identity(index_path.read_bytes())["sha256"] == INDEX_SHA
    index = json_file(index_path)
    assert index["source_count"] == len(index["source_files"]) == 101
    assert index["raw_count"] == len(index["raw_files"]) == 130
    assert len(index["accepted_source_refs"]) == 77
    for record in index["source_files"] + index["raw_files"]:
        check((PARENT / record["path"]).resolve(), record)
    for record in index["accepted_source_refs"]:
        target = (PARENT / record["path"]).resolve()
        check(target, record["local_disk"])
        rel = target.relative_to(REPO).as_posix()
        published = subprocess.run(["git", "show", f"{BASE}:{rel}"], cwd=REPO,
                                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        assert identity(published) == record["published_git"], rel

    manifest = json_file(CHILD / "prelaunch-manifest.json")
    assert manifest["source_count"] == len(manifest["source_files"]) == 1726
    before = json_file(RUN / "closure.json")["source_hashes_before"]
    closure = json_file(RUN / "closure.json")
    failure = json_file(RUN / "failure-seal.json")
    assert len(closure["raw"]) == 23 and len(failure["files"]) == 25
    assert before == closure["source_hashes_after"]
    assert before == {record["key"]: record["sha256"] for record in manifest["source_files"]}
    for record in manifest["source_files"]:
        check(Path(record["path"]), record)
    for name, record in closure["raw"].items():
        check(RUN / name, record)
    for name, record in failure["files"].items():
        check(RUN / name, record)
    ordinary_input = json_file(PKG.parent / "C09-var02-lender-shortage-v1.0.2/ordinary-input.json")
    child_input = json_file(CHILD / "shortage-input.json")
    differences = []

    def recurse(left, right, parts=()):
        assert type(left) is type(right)
        if isinstance(left, dict):
            assert left.keys() == right.keys()
            for key in left:
                recurse(left[key], right[key], parts + (key,))
        elif isinstance(left, list):
            assert len(left) == len(right)
            for index, (a, b) in enumerate(zip(left, right)):
                recurse(a, b, parts + (index,))
        elif left != right:
            differences.append((parts, left, right))

    recurse(ordinary_input, child_input)
    assert differences == [
        (("model", "tables", 0, "instances", 0, "rows", 0, 0),
         "ordinary TTRSS equals TTRS", "shortage TTRSS 0.125 child test"),
        (("model", "tables", 31, "instances", 0, "rows", 0, 5), .5, .125)]
    tables = ordinary_input["model"]["tables"]
    assert tables[0]["name"] == "ProblemDescription" and tables[0]["columns"][0]["name"] == "PDESC"
    remote = tables[31]
    assert remote["name"] == "ResourceRemoteSupport"
    assert [column["name"] for column in remote["columns"]] == [
        "RID", "STID", "RSTID", "TFRS", "TTRS", "TTRSS", "NOTE"]
    assert remote["instances"][0]["rows"][0][:6] == [
        "P-MECH", "BASE-01", "BASE-02", .25, .5, .5]
    parent_run = PKG.parent / "C09-var02-lender-shortage-v1.0.2/runs/c09-var02-v102-ordinary-ssh-20261007-01"
    parent_log = (parent_run / "model.log").read_text(encoding="utf-8")
    child_log = (RUN / "model.log").read_text(encoding="utf-8")
    for log, arrival, end in ((parent_log, "9.96988", "10.2199"),
                              (child_log, "9.59488", "9.84488")):
        assert log.count("Time: 9.46988  return resource transport task 0 starts with 1 resources, transportation time: 0.5") == 1
        assert log.count(f"Time: {arrival}  return resource transport task 0 arrives with 1 resources") == 1
        assert log.count(f"Time: {arrival}  <P-MECH at <BASE-02,0>> return transport arrives: 1") == 1
        assert log.count(f"Time: {arrival}  subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> starts performing") == 1
        assert log.count(f"Time: {end}  subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> completed") == 1
    reviewer = CHILD / "review/independent_replay.py"
    assert identity(reviewer.read_bytes())["sha256"] == "1ee55b22fe01512010baeeac4c49545d1690f7279144dc0b0e20353d56590d7b"
    native_json = runpy.run_path(str(reviewer))["native_json"]
    a = native_json(parent_run / "report-raw.json")
    b = native_json(RUN / "report-raw.json")
    old_tables = {table["name"]: table for table in a["report"]["tables"]}
    new_tables = {table["name"]: table for table in b["report"]["tables"]}
    assert old_tables.keys() == new_tables.keys()
    changed = {}
    for name in old_tables:
        left, right = old_tables[name], new_tables[name]
        assert left["columns"] == right["columns"] and len(left["instances"]) == len(right["instances"])
        changed[name] = sum(x != y for li, ri in zip(left["instances"], right["instances"])
                            for lr, rr in zip(li["rows"], ri["rows"]) for x, y in zip(lr, rr))
    assert changed == {"ProblemDescription": 1, "ResultSummary": 0, "SystemResults": 12,
                       "StockTotalResults": 0, "ResourceResults": 6, "ResourceResultsTotal": 4}
    assert not (PKG / "runs").exists(), "retrospective package may not launch a child"
    print(json.dumps({"decision": "PASS_CONTRACT_BYTES_ONLY", "contract_sha256": CONTRACT_SHA,
                      "direct_pins": len(direct), "accepted_source_files": 101,
                      "accepted_dual_source_refs": 77, "accepted_raw_files": 130,
                      "failed_child_frozen_sources": 1726, "failed_child_closure_raw": 23,
                      "failed_child_failure_files": 25, "new_native_runs": 0},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

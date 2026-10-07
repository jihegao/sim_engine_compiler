"""Construct and verify the frozen C09.var02 source pair without invoking SIMLOX."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "contract.json"


def identity(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def table(doc: dict, name: str) -> dict:
    rows = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(rows) == 1, name
    return rows[0]


def columns(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def rows(t: dict) -> list[list]:
    assert len(t["instances"]) == 1 and t["instances"][0]["instance_name"] == ""
    return t["instances"][0]["rows"]


def put(t: dict, r: list, field: str, value: object) -> None:
    r[columns(t).index(field)] = value


def new_row(t: dict, values: dict) -> list:
    r = [None] * len(columns(t))
    for key, value in values.items():
        put(t, r, key, value)
    assert len(r) == len(t["columns"])
    rows(t).append(r)
    return r


def single(t: dict, field: str, value: object) -> list:
    found = [r for r in rows(t) if r[columns(t).index(field)] == value]
    assert len(found) == 1, (t["name"], field, value)
    return found[0]


def build(contract: dict, arm: str) -> dict:
    parent_meta = contract["accepted_direct_parent"]["source_files"]["remote-input.json"]
    parent_path = (HERE / parent_meta["path"]).resolve()
    assert identity(parent_path) == parent_meta["local_disk"]
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    assert len(parent["model"]["tables"]) == 32
    d = copy.deepcopy(parent)
    for spec in contract["common_source_delta_from_C09_remote"]:
        t = table(d, spec["table"])
        if "add" in spec:
            new_row(t, spec["add"])
        elif spec["table"] == "Control":
            r = rows(t)[0]
            assert len(rows(t)) == 1
            for key, (old, new) in spec["cells"].items():
                assert r[columns(t).index(key)] == old
                put(t, r, key, new)
        elif spec["table"] == "ResultCollection":
            for r in rows(t):
                if r[columns(t).index("RTYPE")] in ("MISSION", "SYSTEM"):
                    old, new = spec["cell"]["RCEND"]
                    assert r[columns(t).index("RCEND")] == old
                    put(t, r, "RCEND", new)
        else:
            raise AssertionError(spec)
    route = table(d, "ResourceRemoteSupport")
    r = single(route, "RID", "P-MECH")
    old = r[columns(route).index("TTRSS")]
    assert old == 0.125
    put(route, r, "TTRSS", contract["pair"]["arms"][arm]["TTRSS"])
    pd = table(d, "ProblemDescription")
    put(pd, rows(pd)[0], "PDESC", contract["pair"]["only_pair_deltas"][1][arm])
    assert len(d["model"]["tables"]) == 32
    return d


def table_diff(a: dict, b: dict) -> dict:
    assert list(a) == list(b) == ["model"]
    ma, mb = a["model"], b["model"]
    assert ma["database_version"] == mb["database_version"]
    aa, bb = ma["tables"], mb["tables"]
    assert [t["name"] for t in aa] == [t["name"] for t in bb]
    changed = []
    for left, right in zip(aa, bb):
        assert left["columns"] == right["columns"]
        assert [i["instance_name"] for i in left["instances"]] == [i["instance_name"] for i in right["instances"]]
        if left != right:
            changed.append({"table": left["name"], "columns": left["columns"],
                            "before_instances": left["instances"], "after_instances": right["instances"]})
    return {"database_version": ma["database_version"], "table_count": len(aa),
            "changed_table_count": len(changed), "changed_tables": changed}


def encoded(obj: object) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema"] == "simlox-c09-var02-lender-shortage-v102-contract/v1"
    pmeta = contract["accepted_direct_parent"]["source_files"]["remote-input.json"]
    parent = json.loads((HERE / pmeta["path"]).read_text(encoding="utf-8"))
    pair = {arm: build(contract, arm) for arm in ("ordinary", "shortage")}
    files = {f"{arm}-input.json": encoded(doc) for arm, doc in pair.items()}
    files["exact-diff.json"] = encoded({"schema": "c09-var02-v102-exact-diff/v1",
        "parent_to_ordinary": table_diff(parent, pair["ordinary"]),
        "parent_to_shortage": table_diff(parent, pair["shortage"]),
        "ordinary_to_shortage": table_diff(pair["ordinary"], pair["shortage"])})
    pair_delta = table_diff(pair["ordinary"], pair["shortage"])
    assert {t["table"] for t in pair_delta["changed_tables"]} == {"ProblemDescription", "ResourceRemoteSupport"}
    for name, raw in files.items():
        p = HERE / name
        if args.write:
            if p.exists():
                raise FileExistsError(p)
            p.write_bytes(raw)
        else:
            assert p.read_bytes() == raw, name
    print(json.dumps({name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                      for name, raw in files.items()}, sort_keys=True))


if __name__ == "__main__":
    main()

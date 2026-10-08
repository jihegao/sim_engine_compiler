"""Deterministic matched-pair source builder; verification is the default."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I03-var01-crew-out-in-v1.0.0" / "out-input.json"
PARENT_SHA = "7f07e30d95f88228d9551cda93c0cf53e196f7473258096a86d2fa06949c262e"
CONTRACT_SHA = "17ab577282e2186040d93195500e9df7565db51922b75468ffe62cc60c7fb30d"
DESCRIPTIONS = {
    "control_out1": "I03.var03 matched control: opening three P-CREW, one OUT at 7.75",
    "child_out2": "I03.var03 matched child: opening three P-CREW, two OUT at 7.75",
}
ORIGINAL_DESCRIPTION = "I03.var01 out: second formation at h20; crew transfer comparison"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def typed_equal(a: object, b: object) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def table(model: dict, name: str) -> dict:
    matches = [t for t in model["tables"] if t["name"] == name]
    assert len(matches) == 1 and len(matches[0]["instances"]) == 1, name
    return matches[0]


def cells(model: dict) -> dict[str, object]:
    out = {}
    for t in model["tables"]:
        assert len(t["instances"]) == 1
        for row_i, row in enumerate(t["instances"][0]["rows"]):
            assert len(row) == len(t["columns"])
            for c, value in zip(t["columns"], row):
                key = f"{t['name']}[0,{row_i}].{c['name']}"
                assert key not in out
                out[key] = value
    return out


def construct(parent: dict, arm: str) -> dict:
    assert arm in DESCRIPTIONS
    assert set(parent) == {"model"}
    model = parent["model"]
    assert set(model) == {"database_version", "tables"}
    assert model["database_version"] == 20160627
    assert len(model["tables"]) == 32
    assert len(cells(model)) == 220
    assert sum(not t["instances"][0]["rows"] for t in model["tables"]) == 11
    out = copy.deepcopy(parent)
    pd = table(out["model"], "ProblemDescription")
    assert [c["name"] for c in pd["columns"]] == ["PDESC"]
    assert pd["instances"][0]["rows"] == [[ORIGINAL_DESCRIPTION]]
    pd["instances"][0]["rows"][0][0] = DESCRIPTIONS[arm]
    allocation = table(out["model"], "ResourceAllocation")
    assert [c["name"] for c in allocation["columns"]] == ["POINT", "RID", "STID", "RQTY", "NOTE"]
    assert allocation["instances"][0]["rows"] == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]]
    allocation["instances"][0]["rows"][0][3] = 3
    transfer = table(out["model"], "ResourceTransfer")
    assert [c["name"] for c in transfer["columns"]] == ["STFID", "STTID", "RID", "TFTIME", "TFQTY", "TFDT", "NOTE"]
    assert transfer["instances"][0]["rows"] == [["BASE-01", "<OUTSIDE>", "P-CREW", 7.75, 1, 0.0, None]]
    if arm == "child_out2":
        transfer["instances"][0]["rows"][0][4] = 2
    return out


def diff(parent: dict, arm: str, out: dict) -> dict:
    assert typed_equal(out, construct(parent, arm)), "extra source or metadata drift"
    before, after = cells(parent["model"]), cells(out["model"])
    assert before.keys() == after.keys() and len(before) == 220
    changes = [{"cell": k, "before": before[k], "after": after[k]} for k in before if not typed_equal(before[k], after[k])]
    expected = [
        {"cell": "ProblemDescription[0,0].PDESC", "before": ORIGINAL_DESCRIPTION, "after": DESCRIPTIONS[arm]},
        {"cell": "ResourceAllocation[0,0].RQTY", "before": 2, "after": 3},
    ]
    if arm == "child_out2":
        expected.append({"cell": "ResourceTransfer[0,0].TFQTY", "before": 1, "after": 2})
    assert changes == expected, changes
    return {"schema": "i03-var03-source-diff/v1", "arm": arm, "parent_sha256": PARENT_SHA,
            "table_count": 32, "authored_cell_count": 220, "changes": changes,
            "all_other_values_and_metadata_type_exact": True}


def frozen_output(path: Path, body: bytes, write: bool) -> None:
    if path.exists():
        assert path.read_bytes() == body, f"frozen output differs: {path}"
    else:
        assert write, f"missing output: {path}"
        path.write_bytes(body)


def main() -> None:
    write = sys.argv[1:] == ["--write"]
    assert not sys.argv[1:] or write
    assert sha((HERE / "contract.json").read_bytes()) == CONTRACT_SHA
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA
    parent = json.loads(raw)
    results = {}
    for arm in DESCRIPTIONS:
        out = construct(parent, arm)
        d = diff(parent, arm, out)
        body = (json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        d["input_sha256"] = sha(body)
        frozen_output(HERE / f"{arm}-input.json", body, write)
        frozen_output(HERE / f"{arm}-exact-diff.json", (json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), write)
        results[arm] = {"input_sha256": sha(body), "input_bytes": len(body), "changes": len(d["changes"])}
    print(json.dumps({"schema": "i03-var03-build-result/v1", "arms": results, "native_calls": 0}, separators=(",", ":")))


if __name__ == "__main__":
    main()

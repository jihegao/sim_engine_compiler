"""Build or verify the frozen C05.var03 CBSID mission-resource pair."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "A16-two-config-reconfiguration-v1.0.0" / "native-input.json"
RESOURCE = ROOT / "C05-var02-two-resource-types-v1.0.0" / "radio-0-input.json"
PARENT_SHA = "07d92a51632b770dfda9d71fdcf042bd73642cc64433171a71e4bab8d76f1ef7"
RESOURCE_SHA = "aef07e9340e6504b7aa1d1f33e9c470572948f3c6560abe67b29dbbdcbbbaa80"
CONTRACT_SHA = "b397b217fbf19ec9b6ae9a166a7b3124144f7ec74680675b1fc47b3b69469d0f"
DESCRIPTIONS = {
    "crew": "C05.var03 v1.0.2 shared CBSID mission; configuration B needs available crew",
    "radio": "C05.var03 v1.0.2 shared CBSID mission; configuration B needs unavailable radio",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def rows(table: dict) -> list:
    assert len(table["instances"]) == 1
    return table["instances"][0]["rows"]


def make(arm: str) -> dict:
    assert sha(PARENT) == PARENT_SHA and sha(RESOURCE) == RESOURCE_SHA
    assert sha(HERE / "contract.json") == CONTRACT_SHA
    parent = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    donor = json.loads(RESOURCE.read_text(encoding="utf-8-sig"))
    obj = copy.deepcopy(parent)
    t = tables(obj)
    d = tables(donor)
    assert len(t) == 32 and "MissionResource" not in t
    assert rows(t["SystemDeployment"])[0][2] == 1
    rows(t["SystemDeployment"])[0][2] = 2
    rows(t["ProblemDescription"])[:] = [[DESCRIPTIONS[arm]]]
    mt = next(r for r in rows(t["MissionType"]) if r[0] == "CONF-A-MISSION").copy()
    mt[0:4] = ["SHARED-CONFIG-MISSION", "One A and one B CBSID configuration", 2, 2]
    rows(t["MissionType"])[:] = [mt]
    op = next(r for r in rows(t["OperationProfile"]) if r[1] == "CONF-A-MISSION").copy()
    op[1] = "SHARED-CONFIG-MISSION"
    rows(t["OperationProfile"])[:] = [op]
    ms = [r.copy() for r in rows(t["MissionSystem"]) if r[1] in ("TEACH-CONF-A", "TEACH-CONF-B")]
    assert len(ms) == 2
    for row in ms:
        row[0] = "SHARED-CONFIG-MISSION"
        row[2] = 1 if row[1] == "TEACH-CONF-A" else 2
    rows(t["MissionSystem"])[:] = ms
    for name in ("Resource", "ResourceAllocation"):
        assert rows(t[name]) == []
        assert t[name]["columns"] == d[name]["columns"]
        rows(t[name])[:] = copy.deepcopy(rows(d[name]))
    mr = copy.deepcopy(d["MissionResource"])
    rows(mr)[:] = [
        ["SHARED-CONFIG-MISSION", "TEACH-CONF-A", "MISSION-CREW", 1, None],
        ["SHARED-CONFIG-MISSION", "TEACH-CONF-B",
         "MISSION-CREW" if arm == "crew" else "MISSION-RADIO", 1, None],
    ]
    obj["model"]["tables"].append(mr)
    assert len(obj["model"]["tables"]) == 33
    return obj


def flattened_diff(a, b, path=()):
    if type(a) is not type(b):
        return [{"path": list(path), "a": a, "b": b}]
    if isinstance(a, dict):
        assert set(a) == set(b)
        return [part for key in a for part in flattened_diff(a[key], b[key], path + (key,))]
    if isinstance(a, list):
        if len(a) != len(b):
            return [{"path": list(path), "a": a, "b": b}]
        return [part for i, (v, w) in enumerate(zip(a, b))
                for part in flattened_diff(v, w, path + (i,))]
    return [] if a == b else [{"path": list(path), "a": a, "b": b}]


def write_or_verify(path: Path, obj: dict) -> None:
    data = (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode()
    if path.exists():
        assert path.read_bytes() == data, f"frozen file drift: {path}"
    else:
        path.write_bytes(data)


def main() -> None:
    control, child = make("crew"), make("radio")
    pair = flattened_diff(control, child)
    assert len(pair) == 2, pair
    assert {p["path"][-1] for p in pair} == {0, 2}, pair
    assert pair[0]["a"] != pair[0]["b"] and {pair[1]["a"], pair[1]["b"]} == {"MISSION-CREW", "MISSION-RADIO"}
    for arm, obj in (("crew", control), ("radio", child)):
        write_or_verify(HERE / f"{arm}-input.json", obj)
    parent = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    parent_tables = tables(parent)
    parent_to_arm = {}
    expected = {"ProblemDescription", "SystemDeployment", "MissionType", "OperationProfile",
                "MissionSystem", "Resource", "ResourceAllocation", "MissionResource"}
    for arm, obj in (("crew", control), ("radio", child)):
        new_tables = tables(obj)
        changed = {name for name in set(parent_tables) | set(new_tables)
                   if parent_tables.get(name) != new_tables.get(name)}
        assert changed == expected, (arm, changed)
        parent_to_arm[arm] = {
            name: {"before": parent_tables.get(name), "after": new_tables.get(name)}
            for name in sorted(changed)
        }
    write_or_verify(HERE / "exact-diff.json", {"schema": "c05-var03-v102-full-source-diff/v1",
                                                "parent_sha256": PARENT_SHA,
                                                "resource_donor_sha256": RESOURCE_SHA,
                                                "parent_to_arm": parent_to_arm,
                                                "pair_differences": pair})
    print(json.dumps({"crew_sha256": sha(HERE / "crew-input.json"),
                      "radio_sha256": sha(HERE / "radio-input.json"),
                      "diff_sha256": sha(HERE / "exact-diff.json")}))


if __name__ == "__main__":
    main()

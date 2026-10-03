"""Freeze the four appended mission rows against the accepted active-removal parent."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, OUTPUT, PARENT_INPUT, PARENT_SHA, build


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if sha(PARENT_INPUT) != PARENT_SHA:
        raise ValueError("accepted parent changed")
    left = json.loads(PARENT_INPUT.read_bytes())
    right = json.loads(OUTPUT.read_bytes())
    if right != build():
        raise ValueError("child differs from complete modeled transformation")
    lt, rt = left["model"]["tables"], right["model"]["tables"]
    if len(lt) != len(rt):
        raise ValueError("table count changed")
    added = []
    changed = []
    for a, b in zip(lt, rt):
        if a["name"] != b["name"] or a["columns"] != b["columns"] or len(a["instances"]) != len(b["instances"]):
            raise ValueError("table structure changed")
        for k, (ai, bi) in enumerate(zip(a["instances"], b["instances"])):
            ar, br = ai["rows"], bi["rows"]
            if ai["instance_name"] != bi["instance_name"] or len(br) < len(ar):
                raise ValueError(f"parent prefix changed in {a['name']}")
            for n, (old, new) in enumerate(zip(ar, br)):
                for j, (ov, nv) in enumerate(zip(old, new)):
                    if ov != nv:
                        changed.append({"table": a["name"], "instance": k, "row": n,
                                        "column": a["columns"][j]["name"], "before": ov, "after": nv})
            for row in br[len(ar):]:
                if len(row) != len(a["columns"]):
                    raise ValueError("row width changed")
                added.append({"table": a["name"], "instance": k,
                              "values": dict(zip((c["name"] for c in a["columns"]), row))})
    if [x["table"] for x in added] != ["MissionType", "OperationProfile", "MissionPreparation", "MissionTurnround"]:
        raise ValueError(f"unexpected appended tables: {[x['table'] for x in added]}")
    if changed != [{"table": "Control", "instance": 0, "row": 0, "column": "SIMPE", "before": 60.0, "after": 65.0}]:
        raise ValueError(f"unexpected parent changes: {changed}")
    out = {"schema": "simlox-f02-var04-terminal-preassignment-diff/v1",
           "parent_input_sha256": PARENT_SHA, "child_input_sha256": sha(OUTPUT),
           "changed_cells": changed, "added_rows": added}
    raw = (json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("frozen diff changed")
    else:
        path.write_bytes(raw)
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest(), "changed_cells": len(changed), "added_rows": len(added)}))


if __name__ == "__main__":
    main()

"""Freeze every cell changed by the F02.var04 slow-route cutoff."""
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
        raise ValueError("child differs from complete modeled parent transformation")
    if set(left) != set(right) or left.get("model", {}).keys() != right.get("model", {}).keys():
        raise ValueError("model topography changed")
    differences = []
    ltables, rtables = left["model"]["tables"], right["model"]["tables"]
    if len(ltables) != len(rtables):
        raise ValueError("table count changed")
    for lt, rt in zip(ltables, rtables):
        if lt["name"] != rt["name"] or lt["columns"] != rt["columns"] or len(lt["instances"]) != len(rt["instances"]):
            raise ValueError("table structure changed")
        for k, (li, ri) in enumerate(zip(lt["instances"], rt["instances"])):
            if li["instance_name"] != ri["instance_name"] or len(li["rows"]) != len(ri["rows"]):
                raise ValueError("instance structure changed")
            for i, (a, b) in enumerate(zip(li["rows"], ri["rows"])):
                if len(a) != len(b) or len(a) != len(lt["columns"]):
                    raise ValueError("row structure changed")
                for j, (av, bv) in enumerate(zip(a, b)):
                    if av != bv:
                        differences.append({"table": lt["name"], "instance": k, "row": i,
                                            "column": lt["columns"][j]["name"], "before": av, "after": bv})
    expected = [
        {"table": "Control", "instance": 0, "row": 0, "column": "SIMPE", "before": 60.0, "after": 52.0},
        {"table": "Control", "instance": 0, "row": 0, "column": "RCEND", "before": 60.0, "after": 52.0},
        {"table": "StationStructure", "instance": 0, "row": 0, "column": "TFRMS", "before": 2.0, "after": 5.0},
        {"table": "StationStructure", "instance": 0, "row": 0, "column": "TTOMS", "before": 2.0, "after": 5.0},
    ]
    expected.extend({"table": "ResultCollection", "instance": 0, "row": i, "column": "RCEND", "before": 60.0, "after": 52.0}
                    for i in range(len(rtables[[t["name"] for t in rtables].index("ResultCollection")]["instances"][0]["rows"])))
    if differences != expected:
        raise ValueError(f"not the frozen cutoff delta: {differences}")
    out = {"schema": "simlox-f02-var04-exact-parent-diff/v1", "parent_input_sha256": PARENT_SHA,
           "terminal_input_sha256": sha(OUTPUT), "changed_cells": differences}
    raw = (json.dumps(out, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("frozen diff changed")
    else:
        path.write_bytes(raw)
    print(json.dumps({"exact_diff_sha256": hashlib.sha256(raw).hexdigest(), "changed_cells": differences}))


if __name__ == "__main__":
    main()

"""Derive the paired C07 off-shift probe from accepted C03 staffing-2."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C03-shared-crew-formation-v1.0.2" / "inputs" / "staffing-2.json"
PARENT_SHA256 = "83b454bd145621f36571a87cdf8abcbccc184f07ab8f9ad5f3111651c78881e0"


def table(name: str, fields: list[tuple[str, str, bool]], row: list) -> dict:
    assert len(fields) == len(row)
    return {
        "columns": [dict(name=n, datatype=t, **({"key": True} if key else {})) for n, t, key in fields],
        "instances": [{"instance_name": "", "rows": [row]}],
        "name": name,
    }


ADDED = [
    table("Shift", [("SHID", "string", True), ("DESCR", "string", False), ("NOTE", "string", False)],
          ["DAY-OPEN", "Crew open", None]),
    table("ShiftProfile", [("SHPID", "string", True), ("SSHPID", "string", True), ("STIM", "double", True),
                           ("ETIM", "double", False), ("IQTY", "integer", False), ("IINT", "double", False),
                           ("NOTE", "string", False)],
          ["CREW-DAY", "DAY-OPEN", 7.75, 10.0, 1, None, None]),
    table("ShiftResource", [("SHID", "string", True), ("STID", "string", True), ("RID", "string", True),
                            ("QTY", "integer", False), ("MAXUT", "double", False), ("NOTE", "string", False)],
          ["DAY-OPEN", "BASE-01", "P-CREW", 2, None, None]),
    table("ResourceStationData", [("RID", "string", True), ("STID", "string", True),
                                   ("PRICE", "double", False), ("SUSTC", "double", False),
                                   ("MUTILF", "double", False), ("RMTBF", "double", False),
                                   ("RFTT", "string", False), ("RMDT", "double", False),
                                   ("RMDTD", "string", False), ("SHPID", "string", False),
                                   ("NOTE", "string", False)],
          ["P-CREW", "BASE-01", None, None, None, None, None, None, None, "CREW-DAY", None]),
]


def build(draos: str) -> dict:
    assert draos in ("Y", "N")
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    doc = copy.deepcopy(json.loads(raw))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    assert not any(t["name"] in tables for t in ADDED)
    control = tables["Control"]
    index = next(i for i, c in enumerate(control["columns"]) if c["name"] == "DRAOS")
    assert control["instances"][0]["rows"][0][index] is None
    control["instances"][0]["rows"][0][index] = draos
    tables["ProblemDescription"]["instances"][0]["rows"][0][0] = f"C07 off-shift crew availability; DRAOS={draos}"
    doc["model"]["tables"].extend(copy.deepcopy(ADDED))
    return doc


def main() -> None:
    for value in ("Y", "N"):
        path = HERE / f"draos-{value.lower()}-input.json"
        raw = (json.dumps(build(value), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists():
            assert path.read_bytes() == raw, f"frozen source differs: {path}"
        else:
            path.write_bytes(raw)
        print(value, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()

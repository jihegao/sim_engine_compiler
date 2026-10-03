"""Freeze a nested, repeated FIXED profile from accepted E10.var02."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E10-var02-empty-fixed-v1.0.0/native-input.json"
PARENT_SHA = "938cf200d04072f67fb87cdce76ad29cdf9a9166d8b09c3f090579f60d878ac0"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    return found[0]


def build() -> bytes:
    assert sha(PARENT) == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "E10.var05 nested FIXED subprofile repeated at h8 and h11; one h10 demand"
    )
    profile = table(doc, "TransportPolicyProfile")
    assert [c["name"] for c in profile["columns"] if c.get("key")] == ["TPRID", "STPRID", "STIM"]
    rows = profile["instances"][0]["rows"]
    assert rows == [
        ["DOWN-POLICY", "FIXED", 8.0, 1, 0.0, None, 1, 2.0, None, None],
        ["DOWN-POLICY", "FIXED", 11.0, 1, 0.0, None, 1, 2.0, None, None],
    ]
    rows[:] = [
        ["DOWN-POLICY", "REPEAT-FIXED", 8.0, 2, 3.0, None, None, None, None, None],
        ["REPEAT-FIXED", "FIXED", 0.0, 1, 0.0, None, 1, 2.0, None, None],
    ]
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    path = HERE / "native-input.json"
    raw = build()
    if write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    else:
        assert path.read_bytes() == raw
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()

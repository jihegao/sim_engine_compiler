"""Freeze an ONDEM support gap around the accepted parent's sole demand."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E10-var01-fixed-ondem-v1.0.1/native-input-ondem.json"
PARENT_SHA = "1ad095c4d1d371c1a2b8e7bc61d629e59459eff90ff310e5c6d1945c4cf70882"


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
        "E10.var03 E10.var01 ONDEM; support h0-9 and h11-36, gap h9-11"
    )
    profile = table(doc, "TransportPolicyProfile")
    assert [c["name"] for c in profile["columns"] if c.get("key")] == ["TPRID", "STPRID", "STIM"]
    rows = profile["instances"][0]["rows"]
    assert rows == [["DOWN-POLICY", "ONDEM", 0.0, 1, 0.0, 36.0, 1, 2.0, None, None]]
    rows[0][5] = 9.0
    rows.append(["DOWN-POLICY", "ONDEM", 11.0, 1, 0.0, 25.0, 1, 2.0, None, None])
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

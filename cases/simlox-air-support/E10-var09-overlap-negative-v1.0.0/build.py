"""Freeze one overlap between two accepted ONDEM policy windows."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E10-var03-ondem-support-gap-v1.0.0/native-input.json"
PARENT_SHA = "c79475655e9b0e0e2e5bd4aa412148b2044cb662521d95824b2276586ad712e8"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> bytes:
    assert sha(PARENT) == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    tables["ProblemDescription"]["instances"][0]["rows"][0][0] = "E10.var09 negative overlap ONDEM windows h0-12 and h11-36"
    policy = tables["TransportPolicyProfile"]
    cols = [col["name"] for col in policy["columns"]]
    rows = policy["instances"][0]["rows"]
    assert len(rows) == 2 and rows[0][cols.index("STPRID")] == rows[1][cols.index("STPRID")] == "ONDEM"
    assert rows[0][cols.index("STIM")] == 0 and rows[0][cols.index("DURN")] == 9
    assert rows[1][cols.index("STIM")] == 11 and rows[1][cols.index("DURN")] == 25
    rows[0][cols.index("DURN")] = 12.0
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    raw = build()
    output = HERE / "native-input.json"
    if write:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(raw)
    else:
        assert output.read_bytes() == raw
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()

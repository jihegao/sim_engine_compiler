"""Create a row-free SIMLOX JSON table schema from a fingerprinted local probe.

One-time source capture only. Ordinary case generation uses the checked schema.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SOURCE = Path("C:/Users/user/Documents/Codex/2026-09-26/simlox-j35-event-parity/workspace/evidence/phase6/b-zero-stock-repair/b-zero-stock-repair.json")
EXPECTED = "1b01a20111aed6c6fc96339c512147c862178967c01e67421eb380379b45f8d0"
OUT = Path(__file__).resolve().parents[1] / "native-schema.json"


def main() -> None:
    if OUT.exists():
        raise FileExistsError(OUT)
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED:
        raise ValueError("source SIMLOX JSON changed")
    source = json.loads(raw.decode("utf-8-sig"))
    for table in source["model"]["tables"]:
        for instance in table["instances"]:
            instance["rows"] = []
    OUT.write_bytes((json.dumps(source, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(OUT, hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()

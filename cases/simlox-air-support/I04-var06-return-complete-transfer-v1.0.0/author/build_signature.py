"""Construct the fixed 117-line ordered event signature from accepted bytes once."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from classify import LOG, semantic_log
from source_gate import CASE, RECOVERY, exact

TARGET = CASE / "source-maps/event-signature.json"


def candidate() -> bytes:
    log = exact(RECOVERY / "raw/between.log", LOG)
    parsed = semantic_log(log, check_signature=False, include_signature=True)
    assert parsed["lines"] == 117 and parsed["timed"] == 103
    signature = parsed["signature"]
    assert len(signature["timed"]) == 103 and len(signature["continuations"]) == 12
    return (json.dumps(signature, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    body = candidate()
    if args.write:
        with TARGET.open("xb") as f:
            f.write(body)
        os.chmod(TARGET, 0o444)
    elif TARGET.exists():
        assert TARGET.read_bytes() == body
    print(json.dumps({"schema": "i04-var06-signature-build/v100", "bytes": len(body),
                      "target_present": TARGET.exists(), "timed": 103, "continuations": 12}, sort_keys=True))

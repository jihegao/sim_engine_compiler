"""Freeze the accepted J04.var03 model while changing only CLI thread count."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "J04-var03-nreps-cap-v1.0.0/probe-input.json"
PARENT_SHA256 = "2fa710997450dcd32190145e4df3d6c0e2e81c76b1236e174af0685c0a80c991"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build() -> tuple[bytes, bytes]:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA256:
        raise ValueError("accepted parent input changed")
    doc = json.loads(raw)
    control = [table for table in doc["model"]["tables"] if table["name"] == "Control"]
    if len(control) != 1 or len(control[0]["instances"]) != 1 or len(control[0]["instances"][0]["rows"]) != 1:
        raise ValueError("Control topology differs")
    row = dict(zip((col["name"] for col in control[0]["columns"]), control[0]["instances"][0]["rows"][0], strict=True))
    if row.get("NREPS") != 32 or row.get("TCLEV") != 0.09 or row.get("RSEED") != "1" or row.get("ENLOG") != "Y":
        raise ValueError("parent control differs")
    delta = {
        "schema": "simlox-j04-var04-thread-repro-exact-diff/v1",
        "parent_case": "J04.var03@1.0.0", "parent_input_sha256": PARENT_SHA256,
        "input_sha256": sha(raw), "model_byte_delta": "none",
        "native_cli_delta": {"calc_threads_parent": 1, "calc_threads_probe": 2},
    }
    return raw, (json.dumps(delta, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source, diff = build()
    for name, raw in (("probe-input.json", source), ("probe-diff.json", diff)):
        path = HERE / name
        if args.check:
            if path.read_bytes() != raw:
                raise ValueError(f"source differs: {name}")
        else:
            path.write_bytes(raw)
    print(json.dumps({"probe-input.json": sha(source), "probe-diff.json": sha(diff)}))


if __name__ == "__main__":
    main()

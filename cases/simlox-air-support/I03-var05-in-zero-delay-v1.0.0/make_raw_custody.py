"""Original accepted, child and native transport byte custody; default verifies."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from source_gate import HERE, unique_json

MAP = HERE / "raw-custody-map.json"
RUN_ID = "i03-var05-in-zero-delay-v100-ssh-20261008-01"
RUN = HERE / "runs" / RUN_ID
TRANSPORT = HERE / "transport-evidence/ssh-native-20261008T013558073898Z-67a983c9"
TRANSPORT_FILES = ("ssh-stdout.bin", "ssh-stderr.bin", "transport-receipt.json")


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def candidate() -> dict:
    design = unique_json((HERE / "contract.json").read_bytes())
    accepted = design["source_lineage"]["mandatory_original_raw"]
    assert len(accepted) == 112
    rows = []
    for source in accepted:
        path = Path(source["path"])
        wanted = {key: source[key] for key in ("bytes", "sha256")}
        assert pin(path.read_bytes()) == wanted
        rows.append({"role": source["role"], "path": str(path), **wanted})
    closure = unique_json((RUN / "closure.json").read_bytes())
    invocation = unique_json((RUN / "invocation.json").read_bytes())
    assert len(closure["raw"]) == 23 and closure["run_id"] == invocation["run_id"] == RUN_ID
    assert pin((RUN / "invocation.json").read_bytes())["sha256"] == closure["invocation_sha256"]
    native_names = sorted(closure["raw"]) + ["invocation.json", "closure.json"]
    assert len(native_names) == 25 and len(set(native_names)) == 25
    for name in native_names:
        path = RUN / name
        wanted = pin(path.read_bytes())
        if name in closure["raw"]:
            assert wanted == {key: closure["raw"][name][key] for key in ("bytes", "sha256")}
        rows.append({"role": "new_child_original", "path": str(path.resolve(strict=True)), **wanted})
    for name in TRANSPORT_FILES:
        path = TRANSPORT / name
        rows.append({"role": "native_transport_original", "path": str(path.resolve(strict=True)),
                     **pin(path.read_bytes())})
    assert len(rows) == 140 and len({row["path"].lower() for row in rows}) == 140
    return {"schema": "i03-var05-original-raw-custody/v1", "accepted_original_raw": 112,
            "new_child_original_run_files": 25, "native_transport_originals": 3,
            "records": rows, "copies_cannot_substitute_for_originals": True}


def body(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def main() -> None:
    args = sys.argv[1:]
    assert args in ([], ["--dry"], ["--write"])
    data = body(candidate())
    if args == ["--write"]:
        assert not MAP.exists()
        MAP.write_bytes(data)
    elif args == []:
        assert MAP.read_bytes() == data
    print(json.dumps({"schema": "i03-var05-original-raw-custody/v1", "records": 140,
                      "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                      "written": args == ["--write"]}, sort_keys=True))


if __name__ == "__main__":
    main()

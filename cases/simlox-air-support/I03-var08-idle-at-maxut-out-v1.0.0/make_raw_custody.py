"""Seal mandatory accepted and new original raw bytes; default is read-only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
MAP = HERE / "raw-custody-map.json"
RUN_ID = "i03-var08-idle-maxut-out-v100-ssh-20261008-01"
RUN = HERE / "runs" / RUN_ID
PURE = HERE / "test-output/native-pure-20261008T0332454327076Z-ee38ecb5"
TRANSPORT = HERE / "transport-evidence/ssh-native-20261008T033243086709Z-7306ee53"


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def unique_json(data: bytes) -> dict:
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value
    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def candidate() -> dict:
    design = unique_json((HERE / "contract.json").read_bytes())
    accepted = design["lineage"]["mandatory_108_original_raw"]
    assert len(accepted) == 108
    rows = []
    for source in accepted:
        path = Path(source["path"])
        wanted = {key: source[key] for key in ("bytes", "sha256")}
        assert pin(path.read_bytes()) == wanted
        rows.append({"role": "accepted_original", "path": str(path), **wanted})
    closure = unique_json((RUN / "closure.json").read_bytes())
    invocation = unique_json((RUN / "invocation.json").read_bytes())
    assert closure["run_id"] == invocation["run_id"] == RUN_ID
    assert len(closure["raw"]) == 23
    assert pin((RUN / "invocation.json").read_bytes())["sha256"] == closure["invocation_sha256"]
    run_names = sorted(closure["raw"]) + ["invocation.json", "closure.json"]
    assert len(run_names) == len(set(run_names)) == 25
    for name in run_names:
        path = RUN / name
        wanted = pin(path.read_bytes())
        if name in closure["raw"]:
            assert wanted == {key: closure["raw"][name][key] for key in ("bytes", "sha256")}
        rows.append({"role": "new_run_original", "path": str(path.resolve(strict=True)), **wanted})
    pure_names = sorted(path.name for path in PURE.iterdir() if path.is_file())
    assert len(pure_names) == 11 and "pure-proof.json" in pure_names
    assert pin((PURE / "pure-proof.json").read_bytes())["sha256"] == invocation["pure_proof_sha256"]
    for name in pure_names:
        path = PURE / name
        rows.append({"role": "native_time_pure_original", "path": str(path.resolve(strict=True)),
                     **pin(path.read_bytes())})
    for name in ("ssh-stdout.bin", "ssh-stderr.bin", "transport-receipt.json"):
        path = TRANSPORT / name
        rows.append({"role": "native_transport_original", "path": str(path.resolve(strict=True)),
                     **pin(path.read_bytes())})
    assert len(rows) == 147 and len({row["path"].lower() for row in rows}) == 147
    return {"schema": "i03-var08-original-raw-custody/v1", "accepted_original_raw": 108,
            "new_run_original": 25, "native_time_pure_original": 11,
            "native_transport_original": 3, "records": rows,
            "copies_cannot_substitute_for_originals": True}


def body(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def main() -> None:
    args = sys.argv[1:]
    assert args in ([], ["--dry"], ["--write"])
    data = body(candidate())
    if args == ["--write"]:
        assert not MAP.exists()
        MAP.write_bytes(data)
    elif args == []:
        assert MAP.read_bytes() == data
    print(json.dumps({"schema": "i03-var08-original-raw-custody/v1", "records": 147,
                      "bytes": len(data), "sha256": pin(data)["sha256"],
                      "written": args == ["--write"]}, sort_keys=True))


if __name__ == "__main__":
    main()

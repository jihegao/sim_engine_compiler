"""Pin mandatory accepted and new native originals without copying bulky artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUN = REPO / "tmp/native-runs/i04v10-v101-20261008-01"
CAPTURE = REPO / "tmp/i04-var10-root-native-proofs-v101-20261008/20261008T141303055254Z-76c96921/receipt.json"
CAPTURE_PIN = {"bytes": 499813, "sha256": "82a078a33588621daeaf8641cdbe877aa2820d3d6ef3c87ee8e67aedbb554312"}
REPLAY = REPO / "tmp/i04-var10-root-sealed-replay-v101-20261008/20261008T141626170671Z-ad3cc985/receipt.json"
REPLAY_PIN = {"bytes": 9646, "sha256": "760d0d0273d3a9bcff391f2e649f4fe790516ed19553d00a7a5275619b330620"}
COPIES = REPLAY.parent / "recovered-evidence"
OUT = HERE / "preserved-raw/custody.json"


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def mandatory(path: Path, role: str, expected: dict | None = None, recovered: Path | None = None) -> dict:
    assert path.is_absolute() and path.is_file()
    actual = pin(path)
    if expected is not None:
        assert actual == {key: expected[key] for key in ("bytes", "sha256")}, str(path)
    result = {"path": str(path), **actual, "role": role,
              "original_mandatory": True, "owned_copy": None}
    if recovered is not None:
        assert recovered.is_file() and recovered.stat().st_file_attributes & 1
        assert pin(recovered) == actual
        result["recovered_copy_path"] = str(recovered)
    return result


def candidate() -> dict:
    parent = json.loads((HERE / "raw-custody-map.json").read_bytes())
    assert parent["schema"] == "i04-var10-parent-raw-custody/v101"
    assert len(parent["records"]) == 153
    rows = []
    for source in parent["records"]:
        assert source["original_mandatory"] is True and source["owned_copy"] is None
        rows.append(mandatory(Path(source["path"]), "accepted_parent_raw", source))

    assert pin(CAPTURE) == CAPTURE_PIN and pin(REPLAY) == REPLAY_PIN
    capture = json.loads(CAPTURE.read_bytes())
    replay = json.loads(REPLAY.read_bytes())
    assert capture["schema"] == "i04-var10-root-single-native-dispatch/v101"
    assert capture["native_dispatch"] is True and type(capture["actual_exit"]) is int
    assert capture["actual_exit"] == 0 and capture["decision"] == "NO_GO_PRESERVE_FAILURE"
    assert replay["schema"] == "i04-var10-root-sealed-independent-replay/v101"
    assert replay["native_dispatch"] is False and type(replay["actual_exit"]) is int
    assert replay["actual_exit"] == 0
    originals = capture["sealed_originals"]
    assert len(originals) == 39
    run_paths = sorted(RUN.iterdir(), key=lambda path: path.name)
    assert len(run_paths) == 25 and all(path.is_file() for path in run_paths)
    assert COPIES.is_dir()
    for path in run_paths:
        assert path.stat().st_file_attributes & 1
        rows.append(mandatory(path, "new_child_run", originals[str(path)], COPIES / path.name))
    native_other = sorted((Path(path) for path in originals if not Path(path).is_relative_to(RUN)),
                          key=lambda path: str(path).casefold())
    assert len(native_other) == 14
    pure_root = HERE / "test-output/native-pure-20261008T1413089213963Z-fefaab7e"
    transport_root = HERE / "transport-evidence/ssh-native-20261008T141303136291Z-136b81c6"
    assert sum(path.parent == pure_root for path in native_other) == 11
    assert sum(path.parent == transport_root for path in native_other) == 3
    for path in native_other:
        assert path.stat().st_file_attributes & 1
        rows.append(mandatory(path, "new_native_pure_transport", originals[str(path)]))
    assert len(rows) == 192
    assert len({row["path"].casefold() for row in rows}) == 192
    return {"schema": "i04-var10-v101-raw-custody/v1",
            "accepted_parent_originals": 153, "new_child_run_originals": 25,
            "native_pure_transport_originals": 14, "mandatory_original_count": 192,
            "recovered_child_copy_count": 25,
            "native_capture_receipt": {"path": str(CAPTURE), **CAPTURE_PIN,
                                       "outer_wrapper_decision": "NO_GO_PRESERVE_FAILURE",
                                       "captured_native_transport_actual_exit": 0},
            "recovered_replay_receipt": {"path": str(REPLAY), **REPLAY_PIN},
            "records": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    value = candidate()
    data = encode(value)
    if args.write:
        assert not OUT.exists()
        OUT.parent.mkdir(exist_ok=True)
        with OUT.open("xb") as stream:
            stream.write(data)
    else:
        assert OUT.read_bytes() == data
    print(json.dumps({"schema": value["schema"], "records": len(value["records"]),
                      "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                      "written": args.write}, sort_keys=True))


if __name__ == "__main__":
    main()

"""Independent read-only byte audit of the actual SSH5 preflight receipt."""

import hashlib
import json
from pathlib import Path


PKG = Path(__file__).resolve().parent.parent
REPO = PKG.parents[2]
RUN_ID = "i03-var02-idle-out-v102-ssh-20261007-01"
MANIFEST_SHA = "fa803d4b0dc7746e4ae3e72288dcdb2cc1a3d3334ca6e5adcb2df8fcb2de1da6"
RUNNER_SHA = "c5c117363458ffa38d61bc4296c07cdd5dc0b536953385e36a00c9e5570f5953"
RECEIPT_NAME = "preflight-ssh0-20261007T154508453Z.json"
RECEIPT_SHA = "e4b7134fb7c635120de4934538a94652e42c22aa6200cf0c2ebc31d55f9869bd"
TRANSPORT_SHA = "34571d878bce88b56aedbf9620f5bb155abad21ae5b56b630933ffb134dacdc1"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            assert key not in result, (path, key)
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=pairs)


def field(obj: dict, name: str, expected, kind: type) -> None:
    assert name in obj and type(obj[name]) is kind and obj[name] == expected, name


def main() -> None:
    manifest_path = PKG / "prelaunch-manifest-v2.json"
    runner_path = PKG / "run_native_ssh_v3.ps1"
    receipt_path = PKG / "review" / RECEIPT_NAME
    assert sha(manifest_path.read_bytes()) == MANIFEST_SHA
    assert sha(runner_path.read_bytes()) == RUNNER_SHA
    assert sha(receipt_path.read_bytes()) == RECEIPT_SHA
    manifest = read_json(manifest_path)
    receipt = read_json(receipt_path)
    field(receipt, "schema", "i03-var02-v102-ssh-preflight/v1", str)
    field(receipt, "run_id", RUN_ID, str)
    field(receipt, "ssh_session", 0, int)
    field(receipt, "ps_major", 5, int)
    field(receipt, "mutex_free", True, bool)
    field(receipt, "run_dirs_absent", True, bool)
    field(receipt, "native_process_started", False, bool)
    field(receipt, "wts_active_gui_count", 1, int)
    field(receipt, "accepted_raw_seals", 32, int)
    field(receipt, "accepted_closures", 1, int)
    field(receipt, "accepted_invocations", 1, int)
    field(receipt, "manifest_sha256", MANIFEST_SHA, str)
    gui = receipt["gui"]
    assert type(gui) is dict
    for name, value, kind in (("pid", 13340, int), ("session_id", 1, int),
                              ("start_unix_ms", 1790590196826, int),
                              ("responding", True, bool)):
        field(gui, name, value, kind)
    ancestors = receipt["ssh_ancestors"]
    assert type(ancestors) is list and "sshd.exe" in ancestors
    entries = manifest["source_files"]
    assert type(entries) is list and len(entries) == 179
    sources = receipt["source_hashes"]
    assert type(sources) is dict and len(sources) == 179
    assert list(sources) == [entry["key"] for entry in entries]
    for entry in entries:
        key = entry["key"]
        assert type(sources[key]) is str and sources[key] == entry["sha256"], key
        path = Path(entry["path"])
        data = path.read_bytes()
        assert len(data) == entry["bytes"] and sha(data) == sources[key], key
    map_sha = sha(json.dumps(sources, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))
    field(receipt, "source_map_sha256", map_sha, str)
    transport_dir = REPO / "tmp" / "i03-ssh-transport-v1-preflight-20261007-01"
    transport = read_json(transport_dir / "transport-receipt.json")
    field(transport, "schema", "i03-root-file-backed-ssh-transport/v1", str)
    field(transport, "mode", "preflight", str)
    field(transport, "transport_sha256", TRANSPORT_SHA, str)
    field(transport, "runner_sha256", RUNNER_SHA, str)
    field(transport, "manifest_sha256", MANIFEST_SHA, str)
    field(transport, "exit_code", 0, int)
    assert transport["command"][-2:] == [str(runner_path).replace("\\", "/"), "-PreflightOnly"]
    for name in ("ssh-stdout.bin", "ssh-stderr.bin"):
        data = (transport_dir / name).read_bytes()
        record = transport["streams"][name]
        assert record == {"bytes": len(data), "sha256": sha(data)}, name
    assert (transport_dir / "ssh-stderr.bin").read_bytes() == b""
    stdout = (transport_dir / "ssh-stdout.bin").read_bytes().decode("utf-8").strip()
    assert stdout == str(receipt_path)
    assert not (PKG / "runs" / RUN_ID).exists()
    print(json.dumps({"schema": "i03-var02-independent-prelaunch-audit/v1",
                      "decision": "GO_PRELAUNCH_EVIDENCE",
                      "manifest_sha256": MANIFEST_SHA,
                      "preflight_sha256": RECEIPT_SHA,
                      "source_map_sha256": map_sha,
                      "source_pins": len(entries),
                      "transport_exit_code": 0,
                      "run_absent": True}, sort_keys=True))


if __name__ == "__main__":
    main()

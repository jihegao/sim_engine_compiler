"""Independent read-only audit of one exact I03.var06 SSH0 preflight receipt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
RUN_ID = "i03-var06-out-dt4-v100-ssh-20261008-01"
MANIFEST_SHA = "ce196b80f2365519885fb97b77eda0b04737736f239dfac46903df99edcf42a9"
PREFLIGHT = HERE / "review/preflight-ssh0-20261007T181850319Z.json"
PREFLIGHT_SHA = "7c2d9ef740432e6b0dd7a3e145e6f4901189c53b4c59317b3568151521434b6c"
ROOT_RECEIPT = REPO / "tmp/i03-var06-root-preflight-20261007T181718Z-f21b7170/receipt.json"
ROOT_RECEIPT_SHA = "5e979fbd2f53a82d044e0cc2819842ce4698069ac5fdd348a5279450c0fef313"
TRANSPORT = HERE / "transport-evidence/ssh-preflight-20261007T181720810397Z-799d006b"
GUI = {"pid": 13340, "session_id": 1, "start_unix_ms": 1790590196826, "responding": True}


def seal(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check(path: Path, record: dict) -> bytes:
    assert path.is_file(), str(path)
    data = path.read_bytes()
    assert seal(data) == {k: record[k] for k in ("bytes", "sha256")}, str(path)
    return data


def exact(value: object, kind: type, expected: object) -> None:
    assert type(value) is kind and value == expected, (value, kind, expected)


def main() -> None:
    manifest = json.loads(check(HERE / "prelaunch-manifest.json",
                                {"bytes": 172903, "sha256": MANIFEST_SHA}))
    assert manifest["source_count"] == len(manifest["source_files"]) == 445
    expected_map = {entry["key"]: entry["sha256"] for entry in manifest["source_files"]}
    assert len(expected_map) == 445
    for entry in manifest["source_files"]:
        check(Path(entry["path"]), entry)
    expected_map_sha = hashlib.sha256(json.dumps(expected_map, ensure_ascii=False,
                                                  separators=(",", ":")).encode("utf-8")).hexdigest()
    assert expected_map_sha == "5ac0f3a4e9efd856cfbc8865b2ae937f3acc8c38172f3d56a3928b562a43a2f2"

    p = json.loads(check(PREFLIGHT, {"bytes": 69308, "sha256": PREFLIGHT_SHA}).decode("utf-8-sig"))
    assert p["schema"] == "i03-var06-out-dt4-ssh-preflight/v1" and p["run_id"] == RUN_ID
    assert p["manifest_sha256"] == MANIFEST_SHA and p["source_map_sha256"] == expected_map_sha
    assert p["source_hashes"] == expected_map and len(p["source_hashes"]) == 445
    for name, value in (("ssh_session", 0), ("ps_major", 5), ("wts_active_gui_count", 1),
                        ("accepted_raw_seals", 106), ("accepted_closures", 6),
                        ("accepted_invocations", 6)):
        exact(p[name], int, value)
    for name, value in (("mutex_free", True), ("run_dirs_absent", True),
                        ("native_process_started", False)):
        exact(p[name], bool, value)
    assert p["gui"].keys() == GUI.keys()
    for name, value in GUI.items():
        exact(p["gui"][name], type(value), value)
    assert type(p["ssh_ancestors"]) is list and "sshd.exe" in p["ssh_ancestors"]
    assert not (HERE / "runs" / RUN_ID).exists()

    root = json.loads(check(ROOT_RECEIPT, {"bytes": 4345, "sha256": ROOT_RECEIPT_SHA}))
    assert root["schema"] == "issue18-i03-var06-root-dispatch/v1"
    assert root["mode"] == "preflight" and root["decision"] == "ROOT_PREFLIGHT_DISPATCH_COMPLETED"
    exact(root["native_authorized"], bool, False)
    assert [x["name"] for x in root["calls"]] == ["guard-before", "transport", "guard-after"]
    for call in root["calls"]:
        exact(call["exit_code"], int, 0)
        check(ROOT_RECEIPT.parent / (call["name"] + "-stdout.bin"), call["stdout"])
        check(ROOT_RECEIPT.parent / (call["name"] + "-stderr.bin"), call["stderr"])
        assert call["stderr"]["bytes"] == 0
    for name in ("guard-before", "guard-after"):
        guard = json.loads((ROOT_RECEIPT.parent / (name + "-stdout.bin")).read_bytes())
        assert guard["schema"] == "issue18-i03-var06-owner-guard/v1"
        exact(guard["ssh_present"], bool, True)
        exact(guard["self_session"], int, 0)
        exact(guard["powershell_major"], int, 5)
        exact(guard["mutex_free"], bool, True)
        exact(guard["candidate_run_exists"], bool, False)
        assert guard["runner_candidates"] == [] and len(guard["native"]) == 1
        assert guard["native"][0]["pid"] == 13340 and guard["native"][0]["session"] == 1
        assert guard["native"][0]["start_ms"] == 1790590196826
        exact(guard["native"][0]["responding"], bool, True)
        exact(guard["active_gui_session1_count"], int, 1)
        exact(guard["session_query_exit"], int, 0)

    assert len(root["transport_files"]) == 3
    for path, record in root["transport_files"].items():
        assert Path(path).parent == TRANSPORT
        check(Path(path), record)
    t = json.loads((TRANSPORT / "transport-receipt.json").read_bytes())
    assert t["schema"] == "i03-var06-out-dt4-ssh-transport/v1"
    assert t["mode"] == "preflight" and t["run_id"] == RUN_ID
    exact(t["native_approved"], bool, False)
    exact(t["exit_code"], int, 0)
    assert t["error"] is None
    assert t["manifest_sha256"] == MANIFEST_SHA
    assert t["runner_sha256"] == expected_map["runner_script"]
    assert t["transport_sha256"] == seal((HERE / "ssh_transport.py").read_bytes())["sha256"]
    assert t["command"][-2:] == [str(HERE / "run_native_ssh.ps1").replace("\\", "/"), "-PreflightOnly"]
    for name, record in t["streams"].items():
        check(TRANSPORT / name, record)
    assert t["streams"]["ssh-stderr.bin"]["bytes"] == 0
    assert (TRANSPORT / "ssh-stdout.bin").read_bytes().decode("utf-8-sig").strip().endswith(PREFLIGHT.name)

    print(json.dumps({"schema": "i03-var06-independent-prelaunch-audit/v1", "passed": True,
                      "preflight_sha256": PREFLIGHT_SHA, "source_map_sha256": expected_map_sha,
                      "source_records": 445, "ssh_guard_calls": 2,
                      "transport_original_streams": 2, "native_process_started": False}, sort_keys=True))


if __name__ == "__main__":
    main()

"""Neutral fixed-file SSH dispatch; root invokes only after independent approval.

This file is source-pinned by the prelaunch manifest. It makes one SSH call,
preserves both original byte streams and never terminates a connected child.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_native_ssh.ps1"
RUN_IDS = {"control_out1": "i03-var03-control-out1-v100-ssh-20261008-01",
           "child_out2": "i03-var03-child-out2-v100-ssh-20261008-01"}


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def main() -> int:
    assert len(sys.argv) == 3 and sys.argv[1] in ("preflight", "native") and sys.argv[2] in RUN_IDS
    mode, arm = sys.argv[1:]
    run_id = RUN_IDS[arm]
    manifest_path = HERE / f"prelaunch-manifest-{arm}.json"
    approval_path = HERE / "review" / f"independent-prelaunch-go-{arm}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    assert manifest["schema"] == "i03-var03-matched-out-prelaunch-manifest/v1"
    assert manifest["arm"] == arm and manifest["run_id"] == run_id
    pins = {item["key"]: item for item in manifest["source_files"]}
    for key, path in (("runner_script", RUNNER), ("owned:ssh_transport.py", Path(__file__))):
        assert {k: pins[key][k] for k in ("bytes", "sha256")} == seal(path)
    if mode == "native":
        approval = json.loads(approval_path.read_text(encoding="utf-8-sig"))
        assert approval["schema"] == "i03-var03-matched-out-independent-prelaunch-go/v1"
        assert approval["decision"] == "GO_PRELAUNCH"
        assert approval["arm"] == arm and approval["run_id"] == run_id
        assert approval["manifest_sha256"] == seal(manifest_path)["sha256"]
        assert approval["runner_sha256"] == seal(RUNNER)["sha256"]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = HERE / "transport-evidence" / f"ssh-{mode}-{arm}-{stamp}-{uuid.uuid4().hex[:8]}"
    out.mkdir(parents=True, exist_ok=False)
    stdout = out / "ssh-stdout.bin"
    stderr = out / "ssh-stderr.bin"
    command = ["ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
               "-i", "C:/Users/user/.ssh/id_rsa", "user@127.0.0.1",
               "powershell.exe", "-NoProfile", "-NonInteractive", "-File",
               str(RUNNER).replace("\\", "/"), "-Arm", arm]
    if mode == "preflight":
        command.append("-PreflightOnly")
    started = utc()
    exit_code: int | None = None
    error: str | None = None
    try:
        with stdout.open("xb") as out_stream, stderr.open("xb") as err_stream:
            # No timeout, kill, retry or pipe decoding after connection.
            result = subprocess.run(command, cwd=HERE, stdout=out_stream, stderr=err_stream)
            exit_code = result.returncode
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    receipt = {"schema": "i03-var03-matched-out-ssh-transport/v1", "mode": mode,
               "arm": arm, "run_id": run_id, "native_approved": mode == "native",
               "transport_sha256": seal(Path(__file__))["sha256"],
               "runner_sha256": seal(RUNNER)["sha256"],
               "manifest_sha256": seal(manifest_path)["sha256"],
               "started_utc": started, "completed_utc": utc(),
               "command": command, "exit_code": exit_code, "error": error,
               "streams": {name: seal(path) if path.is_file() else None
                           for name, path in (("ssh-stdout.bin", stdout), ("ssh-stderr.bin", stderr))}}
    (out / "transport-receipt.json").write_bytes(
        (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"mode": mode, "arm": arm, "exit_code": exit_code, "evidence_dir": str(out),
                      "error": error}, ensure_ascii=False, separators=(",", ":")))
    return exit_code if type(exit_code) is int else 1


if __name__ == "__main__":
    raise SystemExit(main())

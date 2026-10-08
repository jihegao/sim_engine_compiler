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
MANIFEST = HERE / "prelaunch-manifest.json"
APPROVAL = HERE / "review" / "independent-prelaunch-go.json"
RUN_ID = "i04-var10-horizon-in-transit-v101-ssh-20261008-01"
NATIVE_RUN_DIRECTORY = r"C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\tmp\native-runs\i04v10-v101-20261008-01"


def check_native_path() -> None:
    run = Path(NATIVE_RUN_DIRECTORY)
    assert run.is_absolute() and str(run) == NATIVE_RUN_DIRECTORY
    line = "File: " + str(run / "model.sxi").replace("\\", "/")
    assert line.isascii() and len(line.encode("ascii")) == 121 <= 199
    cursor = Path(run.anchor)
    for part in run.parts[1:]:
        cursor /= part
        assert not cursor.is_symlink() and not cursor.is_junction(), "native path alias ancestor"
        if cursor.exists():
            assert not (cursor.stat().st_file_attributes & 0x400), "native path reparse ancestor"
    assert not run.exists(), "unique approved native run path already exists"


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def main() -> int:
    assert sys.argv[1:] in (["preflight"], ["native"])
    mode = sys.argv[1]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    assert set(manifest) == {
        "schema", "run_id", "native_run_directory", "file_line_ascii_bytes", "file_line_ascii_max",
        "base_commit", "contract_sha256", "execution_binding_sha256", "source_count",
        "source_files", "live_catalog_prelaunch_pin", "historical_catalog_prefix_always_checked",
        "accepted_parent_indexed_sources", "accepted_current_source_git_pairs",
        "accepted_dependency_git_pairs", "accepted_parent_manifest_roles", "accepted_parent_raw",
        "accepted_parent_preflight_originals", "total_parent_original_raw",
        "excluded_v100_source_files", "owned_context_copies", "owned_pure_proof_copies", "contract_originals",
        "converter_corrupt_file_negative_originals", "local_only_context_originals",
        "mandatory_prospective_proof_originals",
        "new_native_runs_authorized_by_manifest", "independent_method_state"}
    assert manifest["schema"] == "i04-var10-horizon-transit-prelaunch-manifest/v101"
    assert manifest["run_id"] == RUN_ID
    assert type(manifest["native_run_directory"]) is str and manifest["native_run_directory"] == NATIVE_RUN_DIRECTORY
    assert type(manifest["file_line_ascii_bytes"]) is int and manifest["file_line_ascii_bytes"] == 121
    assert type(manifest["file_line_ascii_max"]) is int and manifest["file_line_ascii_max"] == 199
    check_native_path()
    pins = {item["key"]: item for item in manifest["source_files"]}
    for key, path in (("runner_script", RUNNER), ("owned:ssh_transport.py", Path(__file__))):
        assert {k: pins[key][k] for k in ("bytes", "sha256")} == seal(path)
    if mode == "native":
        approval = json.loads(APPROVAL.read_text(encoding="utf-8-sig"))
        assert set(approval) == {"schema", "decision", "run_id", "native_run_directory",
                                 "manifest_sha256", "runner_sha256", "validator_sha256",
                                 "contract_sha256", "execution_binding_sha256", "input_sha256",
                                 "source_map_sha256", "independent_replay_sha256",
                                 "preflight_relative_path", "preflight_sha256"}
        assert approval["schema"] == "i04-var10-horizon-transit-independent-prelaunch-go/v101"
        assert approval["decision"] == "GO_PRELAUNCH"
        assert approval["run_id"] == RUN_ID
        assert type(approval["native_run_directory"]) is str and approval["native_run_directory"] == NATIVE_RUN_DIRECTORY
        assert approval["manifest_sha256"] == seal(MANIFEST)["sha256"]
        assert approval["runner_sha256"] == seal(RUNNER)["sha256"]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = HERE / "transport-evidence" / f"ssh-{mode}-{stamp}-{uuid.uuid4().hex[:8]}"
    out.mkdir(parents=True, exist_ok=False)
    stdout = out / "ssh-stdout.bin"
    stderr = out / "ssh-stderr.bin"
    command = ["ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
               "-i", "C:/Users/user/.ssh/id_rsa", "user@127.0.0.1",
               "powershell.exe", "-NoProfile", "-NonInteractive", "-File",
               str(RUNNER).replace("\\", "/")]
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
    receipt = {"schema": "i04-var10-horizon-transit-ssh-transport/v101", "mode": mode,
               "run_id": RUN_ID, "native_approved": mode == "native",
               "native_run_directory": NATIVE_RUN_DIRECTORY,
               "transport_sha256": seal(Path(__file__))["sha256"],
               "runner_sha256": seal(RUNNER)["sha256"],
               "manifest_sha256": seal(MANIFEST)["sha256"],
               "started_utc": started, "completed_utc": utc(),
               "command": command, "exit_code": exit_code, "error": error,
               "streams": {name: seal(path) if path.is_file() else None
                           for name, path in (("ssh-stdout.bin", stdout), ("ssh-stderr.bin", stderr))}}
    (out / "transport-receipt.json").write_bytes(
        (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"mode": mode, "exit_code": exit_code, "evidence_dir": str(out),
                      "error": error}, ensure_ascii=False, separators=(",", ":")))
    return exit_code if type(exit_code) is int else 1


if __name__ == "__main__":
    raise SystemExit(main())

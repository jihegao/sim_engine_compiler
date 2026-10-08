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
RUN_ID = "e02-var02-repair-deadline-v104-ssh-20261009-01"
NATIVE_RUN_DIRECTORY = r"C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\tmp\e02-var02-native-v104-20261009-01"


def check_native_path() -> None:
    run = Path(NATIVE_RUN_DIRECTORY)
    assert run.is_absolute() and str(run) == NATIVE_RUN_DIRECTORY
    line = "File: " + str(run / "model.sxi").replace("\\", "/")
    assert line.isascii() and len(line.encode("ascii")) == 119 <= 199
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
        "base_commit", "contract_sha256", "execution_binding_sha256", "input_sha256",
        "source_inventory_sha256", "runner_sha256", "validator_sha256",
        "independent_reader_sha256", "source_count", "source_files", "owned_source_count",
        "accepted_source_pair_count", "required_local_source_count", "mandatory_original_count",
        "archived_catalog_count", "converter_negative_original_count", "installed_executable_count",
        "excluded_source_count", "excluded_failed_original_count",
        "excluded_diagnostic_copy_count", "excluded_custody_receipt_count",
        "catalog_prefix_entries",
        "live_catalog_prelaunch_pin", "pure_tools", "stages", "native_commands", "pure_checkers",
        "new_native_runs_authorized_by_manifest", "independent_method_state"}
    assert manifest["schema"] == "e02-var02-prelaunch-manifest/v104"
    assert manifest["run_id"] == RUN_ID
    assert type(manifest["native_run_directory"]) is str and manifest["native_run_directory"] == NATIVE_RUN_DIRECTORY
    assert type(manifest["file_line_ascii_bytes"]) is int and manifest["file_line_ascii_bytes"] == 119
    assert type(manifest["file_line_ascii_max"]) is int and manifest["file_line_ascii_max"] == 199
    assert manifest["base_commit"] == "7b9dc461d629e28ed6f719d6c155dad9db9dca60"
    assert manifest["contract_sha256"] == "f8de374b6f78e661d9f453b96fe701db321f94686d02fbec92b8e4095f8fea3b"
    assert manifest["accepted_source_pair_count"] == 39
    assert manifest["required_local_source_count"] == 0
    assert manifest["mandatory_original_count"] == 42
    assert manifest["archived_catalog_count"] == 2
    assert manifest["converter_negative_original_count"] == 0
    assert manifest["installed_executable_count"] == 4
    assert manifest["catalog_prefix_entries"] == 503
    assert manifest["source_count"] == len(manifest["source_files"])
    for key, expected in (("excluded_source_count", 79),
                          ("excluded_failed_original_count", 40),
                          ("excluded_diagnostic_copy_count", 26),
                          ("excluded_custody_receipt_count", 1)):
        assert type(manifest[key]) is int and manifest[key] == expected
    assert manifest["source_count"] == manifest["owned_source_count"] + 231
    assert manifest["pure_tools"] == ["build.py", "source_gate.py", "self_check.py",
                                       "make_source_inventory.py", "make_prelaunch_manifest.py"]
    assert manifest["stages"] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
    assert type(manifest["native_commands"]) is int and manifest["native_commands"] == 4
    assert type(manifest["pure_checkers"]) is int and manifest["pure_checkers"] == 2
    assert type(manifest["new_native_runs_authorized_by_manifest"]) is int and manifest["new_native_runs_authorized_by_manifest"] == 0
    check_native_path()
    pins = {item["key"]: item for item in manifest["source_files"]}
    assert len(pins) == len(manifest["source_files"])
    for key, path in (("runner_script", RUNNER), ("owned:ssh_transport.py", Path(__file__))):
        assert {k: pins[key][k] for k in ("bytes", "sha256")} == seal(path)
    if mode == "native":
        approval = json.loads(APPROVAL.read_text(encoding="utf-8-sig"))
        assert set(approval) == {"schema", "decision", "run_id", "native_run_directory",
                                 "manifest_sha256", "runner_sha256", "validator_sha256",
                                 "contract_sha256", "execution_binding_sha256", "input_sha256",
                                 "source_map_sha256", "independent_reader_sha256",
                                 "preflight_relative_path", "preflight_sha256"}
        assert approval["schema"] == "e02-var02-independent-prelaunch-go/v104"
        assert approval["decision"] == "GO_PRELAUNCH"
        assert approval["run_id"] == RUN_ID
        assert type(approval["native_run_directory"]) is str and approval["native_run_directory"] == NATIVE_RUN_DIRECTORY
        assert approval["manifest_sha256"] == seal(MANIFEST)["sha256"]
        assert approval["runner_sha256"] == seal(RUNNER)["sha256"]
        assert approval["contract_sha256"] == manifest["contract_sha256"]
        assert approval["execution_binding_sha256"] == manifest["execution_binding_sha256"]
        assert approval["input_sha256"] == manifest["input_sha256"]
        assert approval["validator_sha256"] == manifest["validator_sha256"]
        assert approval["independent_reader_sha256"] == manifest["independent_reader_sha256"]
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
    receipt = {"schema": "e02-var02-ssh-transport/v104", "mode": mode,
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

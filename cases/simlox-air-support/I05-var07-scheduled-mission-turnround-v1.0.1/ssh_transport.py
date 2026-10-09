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
RUN_ID = "i05-var07-turnround-v101-ssh-20261009-01"
NATIVE_RUN_DIRECTORY = r"C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\tmp\i05-var07-native-v101-20261009-01"


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

def strict_json(path: Path) -> dict:
    body = path.read_bytes()
    assert not body.startswith(b"\xef\xbb\xbf")
    def pairs(items):
        result = {}
        for key, value in items:
            assert key not in result, ("duplicate JSON key", key)
            result[key] = value
        return result
    def nonfinite(token):
        raise AssertionError(("nonfinite JSON", token))
    value = json.loads(body.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)
    assert type(value) is dict
    return value


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def main() -> int:
    assert sys.argv[1:] in (["preflight"], ["native"])
    mode = sys.argv[1]
    manifest = strict_json(MANIFEST)
    assert set(manifest) == {
        "schema", "run_id", "native_run_directory", "file_line_ascii_bytes", "file_line_ascii_max",
        "base_commit", "contract_sha256", "execution_binding_sha256", "input_sha256",
        "source_inventory_sha256", "runner_sha256", "validator_sha256",
        "independent_reader_sha256", "source_count", "source_files", "owned_source_count",
        "selected_reference_count", "selected_unique_original_count",
        "accepted_source_pair_count", "accepted_source_pair_unique_count", "accepted_raw_count", "excluded_raw_count",
        "archived_catalog_count", "installed_source_count", "runtime_source_count", "historical_source_count",
        "catalog_prefix_entries",
        "live_catalog_prelaunch_pin", "pure_tools", "stages", "native_commands", "pure_checkers",
        "new_native_runs_authorized_by_manifest", "independent_method_state"}
    assert manifest["schema"] == "i05-var07-prelaunch-manifest/v101"
    assert manifest["run_id"] == RUN_ID
    assert type(manifest["native_run_directory"]) is str and manifest["native_run_directory"] == NATIVE_RUN_DIRECTORY
    assert type(manifest["file_line_ascii_bytes"]) is int and manifest["file_line_ascii_bytes"] == 119
    assert type(manifest["file_line_ascii_max"]) is int and manifest["file_line_ascii_max"] == 199
    assert manifest["base_commit"] == "120adb3d8912acfe9965ea04c939867721f3ede3"
    assert manifest["contract_sha256"] == "c34bb3d2b9c88763347f63e5bb111389db00e800d743ff74102e810eab6df0b7"
    assert manifest["selected_reference_count"] == 100
    assert manifest["selected_unique_original_count"] == 98
    assert manifest["accepted_source_pair_count"] == 37
    assert manifest["accepted_source_pair_unique_count"] == 35
    assert manifest["accepted_raw_count"] == 24
    assert manifest["excluded_raw_count"] == 24
    assert manifest["archived_catalog_count"] == 2
    assert manifest["installed_source_count"] == 3
    assert manifest["runtime_source_count"] == 1
    assert manifest["historical_source_count"] == 2
    assert manifest["catalog_prefix_entries"] == 505
    assert manifest["source_count"] == len(manifest["source_files"])
    assert manifest["source_count"] == manifest["owned_source_count"] + 103
    assert manifest["pure_tools"] == ["build.py", "source_gate.py", "self_check.py",
                                       "make_source_inventory.py", "make_prelaunch_manifest.py"]
    assert manifest["stages"] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
    assert type(manifest["native_commands"]) is int and manifest["native_commands"] == 4
    assert type(manifest["pure_checkers"]) is int and manifest["pure_checkers"] == 2
    assert type(manifest["new_native_runs_authorized_by_manifest"]) is int and manifest["new_native_runs_authorized_by_manifest"] == 0
    assert manifest["independent_method_state"] == "SOURCE_CONSTRUCTION_ONLY_NO_SSH_OR_NATIVE_APPROVAL"
    check_native_path()
    pins = {item["key"]: item for item in manifest["source_files"]}
    assert len(pins) == len(manifest["source_files"])
    for key, path in (("owned:run_native_ssh.ps1", RUNNER), ("owned:ssh_transport.py", Path(__file__))):
        assert {k: pins[key][k] for k in ("bytes", "sha256")} == seal(path)
    if mode == "native":
        approval = strict_json(APPROVAL)
        assert set(approval) == {"schema", "decision", "run_id", "native_run_directory",
                                 "manifest_sha256", "runner_sha256", "validator_sha256",
                                 "contract_sha256", "execution_binding_sha256", "input_sha256",
                                 "source_map_sha256", "independent_reader_sha256",
                                 "preflight_relative_path", "preflight_sha256"}
        assert approval["schema"] == "i05-var07-independent-prelaunch-go/v101"
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
    receipt = {"schema": "i05-var07-ssh-transport/v101", "mode": mode,
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

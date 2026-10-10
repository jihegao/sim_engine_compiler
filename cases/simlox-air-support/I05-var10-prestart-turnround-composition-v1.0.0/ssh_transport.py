"""One-shot SSH transport for I05.var10 v1.0.0; no timeout, kill, or retry."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[2]
RUNNER = CASE / "run_native_ssh.ps1"
MANIFEST = CASE / "prelaunch-manifest-v100-run01.json"
CONTRACT = CASE / "contract.json"
APPROVAL = CASE / "review" / "independent-prelaunch-go.json"
SSH_KEY = Path(r"C:\Users\user\.ssh\id_rsa")
SSH_TARGET = "user@127.0.0.1"
RUN_ID = "i05-var10-turnround-prestart-v100-ssh-20261010-01"
NATIVE_RUN_DIRECTORY = r"C:\Users\user\Documents\Codex\2026-10-09\i05-var08-pm-location\tmp\i05-var10-prestart-native-v100-20261010-01"


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def check_frozen_inputs(manifest: dict) -> None:
    assert manifest["schema"] == "simlox-i05-var10-prelaunch-manifest/v100"
    assert manifest["run_id"] == RUN_ID
    assert manifest["native_run_directory"] == NATIVE_RUN_DIRECTORY
    pins = {item["key"]: item for item in manifest["sources"]}
    for key, path in (("current:run_native_ssh.ps1", RUNNER),
                      ("current:contract.json", CONTRACT),
                      ("current:ssh_transport.py", Path(__file__))):
        assert {k: pins[key][k] for k in ("bytes", "sha256")} == seal(path), f"source pin differs: {key}"
    for item in manifest["sources"]:
        path = Path(item["path"])
        assert path.is_file() and seal(path) == {"bytes": item["bytes"], "sha256": item["sha256"]}, item["key"]


def check_native_approval(manifest: dict) -> None:
    approval = json.loads(APPROVAL.read_text(encoding="utf-8-sig"))
    assert approval["schema"] == "i05-var10-independent-prelaunch-go/v100"
    assert approval["decision"] == "GO_PRELAUNCH"
    assert approval["run_id"] == RUN_ID
    assert approval["native_run_directory"] == NATIVE_RUN_DIRECTORY
    assert approval["manifest_sha256"] == seal(MANIFEST)["sha256"]
    assert approval["runner_sha256"] == seal(RUNNER)["sha256"]
    assert approval["contract_sha256"] == seal(CONTRACT)["sha256"]
    assert approval["preflight_sha256"] == seal(CASE / approval["preflight_relative_path"])["sha256"]
    preflight = json.loads((CASE / approval["preflight_relative_path"]).read_text(encoding="utf-8-sig"))
    assert preflight["decision"] == "GO_PRELAUNCH_CANDIDATE"
    assert preflight["native_process_started"] is False
    assert preflight["run_directory_absent"] is True
    assert not Path(NATIVE_RUN_DIRECTORY).exists()
    assert not (CASE / "runs" / RUN_ID).exists()
    check_frozen_inputs(manifest)


def main() -> int:
    if sys.argv[1:] not in (["preflight"], ["native"]):
        raise SystemExit("mode must be exactly preflight or native")
    mode = sys.argv[1]
    contract = json.loads(CONTRACT.read_text(encoding="utf-8-sig"))
    assert contract["version"] == "1.0.0" and contract["candidate"]["run_id"] == RUN_ID
    assert contract["candidate"]["physical_directory"] == NATIVE_RUN_DIRECTORY
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    check_frozen_inputs(manifest)
    if mode == "native":
        check_native_approval(manifest)
    else:
        assert not Path(NATIVE_RUN_DIRECTORY).exists()
        assert not (CASE / "runs" / RUN_ID).exists()
    ssh = shutil.which("ssh.exe") or shutil.which("ssh")
    if not ssh or not Path(ssh).is_file():
        raise FileNotFoundError("Windows OpenSSH client not found")
    if not SSH_KEY.is_file():
        raise FileNotFoundError("authorized SSH identity file is absent")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    evidence = CASE / "review" / f"transport-{mode}-{stamp}-{uuid.uuid4().hex[:8]}"
    evidence.mkdir(parents=True, exist_ok=False)
    stdout_path, stderr_path = evidence / "ssh-stdout.bin", evidence / "ssh-stderr.bin"
    command = [ssh, "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-i", str(SSH_KEY),
               SSH_TARGET, "powershell.exe", "-NoProfile", "-NonInteractive", "-File", RUNNER.as_posix()]
    if mode == "preflight":
        command.append("-PreflightOnly")
    started = utc()
    exit_code = None
    error = None
    try:
        with stdout_path.open("xb") as out_stream, stderr_path.open("xb") as err_stream:
            result = subprocess.run(command, cwd=CASE, stdout=out_stream, stderr=err_stream)
            exit_code = result.returncode
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    source_hashes_after = {}
    source_stability_error = None
    try:
        check_frozen_inputs(manifest)
        source_hashes_after = {item["key"]: item["sha256"] for item in manifest["sources"]}
    except Exception as exc:
        source_stability_error = f"{type(exc).__name__}: {exc}"
    receipt = {"schema": "i05-var10-ssh-transport/v100", "mode": mode,
               "run_id": RUN_ID, "native_approved": mode == "native",
               "native_run_directory": NATIVE_RUN_DIRECTORY,
               "transport_sha256": seal(Path(__file__))["sha256"],
               "runner_sha256": seal(RUNNER)["sha256"], "manifest_sha256": seal(MANIFEST)["sha256"],
               "ssh_executable": str(Path(ssh).resolve()), "ssh_target": SSH_TARGET,
               "started_utc": started, "completed_utc": utc(), "command": command,
               "exit_code": exit_code, "error": error, "source_stability_error": source_stability_error,
               "source_hashes_after": source_hashes_after,
               "streams": {name: seal(path) for name, path in (("stdout", stdout_path), ("stderr", stderr_path))}}
    receipt_path = evidence / "transport-receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mode": mode, "exit_code": exit_code, "evidence_dir": str(evidence),
                      "error": error, "source_stability_error": source_stability_error},
                     ensure_ascii=False, separators=(",", ":")))
    if error or source_stability_error or not isinstance(exit_code, int):
        return 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

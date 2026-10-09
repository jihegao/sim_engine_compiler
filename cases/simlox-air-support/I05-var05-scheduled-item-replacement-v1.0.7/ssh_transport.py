"""Single fixed SSH session-0 dispatch for I05.var05; never retries or kills a child."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone, timedelta

HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_native_ssh.ps1"
MANIFEST = HERE / "prelaunch-manifest.json"
APPROVAL = HERE / "review" / "independent-prelaunch-go.json"
USER_KEY = Path.home() / ".ssh" / "id_rsa"
REMOTE = "user@127.0.0.1"
NATIVE_RUN = Path(r"C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\tmp\i05-var05-item-replacement-v107-20261009-01")


def seal(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def strict_json(path: Path) -> dict:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM is not allowed: {path}")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=pairs,
                      parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))


def main() -> int:
    if sys.argv[1:] not in (["preflight"], ["native"]):
        raise SystemExit("usage: ssh_transport.py preflight|native")
    mode = sys.argv[1]
    manifest = strict_json(MANIFEST)
    if manifest["schema"] != "i05-var05-prelaunch-manifest/v1" or manifest["native_attempt_limit"] != 1:
        raise SystemExit("prelaunch manifest identity or attempt limit differs")
    if manifest["native_run_directory"] != str(NATIVE_RUN) or NATIVE_RUN.exists():
        raise SystemExit("unique native run path identity/existence check failed before SSH")
    pins = {entry["key"]: entry for entry in manifest["source_files"]}
    for entry in manifest["source_files"]:
        path = Path(entry["path"])
        pin_now = seal(path)
        if pin_now["bytes"] != entry["bytes"] or pin_now["sha256"] != entry["sha256"] or path.stat().st_file_attributes != entry["attributes"]:
            raise SystemExit(f"source pin mismatch before SSH dispatch: {entry['key']}")
    if seal(RUNNER)["sha256"] != pins["owned:run_native_ssh.ps1"]["sha256"] or seal(Path(__file__))["sha256"] != pins["owned:ssh_transport.py"]["sha256"]:
        raise SystemExit("runner pin missing")
    if mode == "native":
        approval = strict_json(APPROVAL)
        if approval.get("schema") != "i05-var05-independent-prelaunch-go/v1" or approval.get("decision") != "GO_PRELAUNCH":
            raise SystemExit("independent prelaunch approval missing")
        if approval.get("run_id") != manifest["run_id"] or approval.get("native_run_directory") != manifest["native_run_directory"]:
            raise SystemExit("approval does not bind run ID and native directory")
        if approval.get("manifest_sha256") != seal(MANIFEST)["sha256"] or approval.get("runner_sha256") != seal(RUNNER)["sha256"]:
            raise SystemExit("approval does not bind manifest and runner")
        preflight = HERE / approval["preflight_relative_path"]
        if seal(preflight)["sha256"] != approval.get("preflight_sha256"):
            raise SystemExit("fresh preflight receipt hash mismatch")
        preflight_doc = strict_json(preflight)
        preflight_time = datetime.fromisoformat(preflight_doc["utc"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - preflight_time > timedelta(minutes=30) or preflight_time - datetime.now(timezone.utc) > timedelta(minutes=1):
            raise SystemExit("preflight receipt stale or future-dated")
        if (preflight_doc.get("manifest_sha256") != seal(MANIFEST)["sha256"] or
            preflight_doc.get("run_id") != manifest["run_id"] or
            preflight_doc.get("native_run_directory") != manifest["native_run_directory"] or
            preflight_doc.get("native_dispatch") is not False):
            raise SystemExit("preflight receipt identity differs")
        for entry in manifest["source_files"]:
            if preflight_doc["source_hashes"].get(entry["key"]) != entry["sha256"]:
                raise SystemExit(f"preflight source hash differs: {entry['key']}")
    suffix = "preflight" if mode == "preflight" else "native"
    out_path = HERE / "review" / f"ssh-{suffix}-stdout.bytes"
    err_path = HERE / "review" / f"ssh-{suffix}-stderr.bytes"
    receipt_path = HERE / "review" / f"ssh-{suffix}-transport-receipt.json"
    if any(path.exists() for path in (out_path, err_path, receipt_path)):
        raise SystemExit("transport evidence path already exists; refusing to overwrite")
    argv = ["ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-i", str(USER_KEY),
            REMOTE, "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(RUNNER)]
    if mode == "preflight":
        argv.append("-PreflightOnly")
    started = datetime.now(timezone.utc).isoformat()
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    out_path.write_bytes(stdout)
    err_path.write_bytes(stderr)
    receipt = {"schema": "i05-var05-ssh-transport-receipt/v1", "mode": mode, "started_utc": started,
               "completed_utc": datetime.now(timezone.utc).isoformat(), "argv": argv,
               "runner": seal(RUNNER), "stdout": seal(out_path), "stderr": seal(err_path),
               "ssh_exit_code": proc.returncode, "retry_count": 0, "child_termination_sent": False}
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(stdout)
    sys.stderr.buffer.write(stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())

"""Capture original binary streams for the author PURE source/method checks.

Output is unique ignored test evidence. No SSH, SIMLOX, accepted checker or
capture-helper invocation occurs here.
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
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
POWERSHELL = Path(r"C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe")


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def main() -> int:
    assert not sys.argv[1:]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = HERE / "test-output" / f"pure-proof-{stamp}-{uuid.uuid4().hex[:8]}"
    output.mkdir(parents=True, exist_ok=False)
    scripts = [
        ("build", [str(PYTHON), "-X", "utf8", "-B", str(HERE / "build.py")]),
        ("context", [str(PYTHON), "-X", "utf8", "-B", str(HERE / "copy_context.py")]),
        ("source", [str(PYTHON), "-X", "utf8", "-B", str(HERE / "source_gate.py"), "--mode", "sealed"]),
        ("self_check", [str(PYTHON), "-X", "utf8", "-B", str(HERE / "self_check.py")]),
        ("converter", [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-File", str(HERE / "test_converter_gate.ps1")]),
        ("source_inventory", [str(PYTHON), "-X", "utf8", "-B", str(HERE / "make_source_inventory.py"), "--provisional"]),
        ("manifest", [str(PYTHON), "-X", "utf8", "-B", str(HERE / "make_prelaunch_manifest.py"), "--provisional"]),
    ]
    before = {name: pin(HERE / name) for name in
              ("contract.json", "execution-contract.json", "native-input.json", "source_gate.py",
               "event_ledger.py", "report_oracle.py", "run_native_ssh.ps1")}
    steps = []
    for name, command in scripts:
        started = utc()
        proc = subprocess.run(command, cwd=HERE, capture_output=True)
        stdout = output / f"{name}.stdout.bin"
        stderr = output / f"{name}.stderr.bin"
        stdout.write_bytes(proc.stdout)
        stderr.write_bytes(proc.stderr)
        steps.append({"name": name, "command": command, "started_utc": started,
                      "ended_utc": utc(), "exit_code": proc.returncode,
                      "stdout": {"path": str(stdout), **pin(stdout)},
                      "stderr": {"path": str(stderr), **pin(stderr)}})
        if proc.returncode != 0:
            break
    after = {name: pin(HERE / name) for name in before}
    receipt = {"schema": "i03-var05-author-pure-proof/v1", "steps": steps,
               "source_pins_before": before, "source_pins_after": after,
               "source_unchanged": before == after,
               "all_exits_zero": len(steps) == len(scripts) and all(step["exit_code"] == 0 for step in steps),
               "native_calls": 0}
    target = output / "receipt.json"
    target.write_bytes((json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"receipt": str(target), "receipt_pin": pin(target),
                      "all_exits_zero": receipt["all_exits_zero"], "steps": len(steps)}))
    return 0 if receipt["all_exits_zero"] and receipt["source_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

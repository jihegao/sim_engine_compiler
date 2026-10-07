"""One-time, zero-native static proof capture; default only verifies saved bytes."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
OUT = HERE / "pure-evidence"
RECEIPT = OUT / "receipt.json"
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
POWERSHELL = "powershell.exe"
FILES = (
    ("source_build", [str(PYTHON), "-X", "utf8", "-B", str(HERE / "build.py")]),
    ("root_custody", [str(PYTHON), "-X", "utf8", "-B", str(HERE / "copy_root_evidence.py")]),
    ("source_verifier", [str(PYTHON), "-X", "utf8", "-B", str(HERE / "verify_sources.py"), "--mode", "live"]),
    ("catalog_self_check", [str(PYTHON), "-X", "utf8", "-B", str(HERE / "test_sealed_catalog.py")]),
    ("author_self_check", [str(PYTHON), "-X", "utf8", "-B", str(HERE / "self_check.py")]),
    ("independent_replay", [str(PYTHON), "-X", "utf8", "-B", str(HERE / "review/independent_replay.py")]),
    ("independent_self_check", [str(PYTHON), "-X", "utf8", "-B", str(HERE / "review/independent_self_check.py")]),
    ("checker_receipt", [POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(HERE / "test_checker_receipt.ps1")]),
    ("preflight_receipt", [POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(HERE / "test_preflight_receipt.ps1")]),
)


def seal(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def verify() -> dict:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert doc["schema"] == "i03-var11-pure-static-proof/v1"
    assert doc["native_started"] is False and len(doc["steps"]) == len(FILES)
    for record, (name, command) in zip(doc["steps"], FILES):
        assert record["name"] == name and record["command"] == command
        assert type(record["exit_code"]) is int and record["exit_code"] == 0
        for stream in ("stdout", "stderr"):
            path = OUT / f"{name}.{stream}.bin"
            assert seal(path.read_bytes()) == record[stream]
        assert record["stderr"]["bytes"] == 0, name
    return {"schema": "i03-var11-pure-static-proof-check/v1", "passed": True,
            "steps": len(FILES), "native_started": False}


def main() -> None:
    assert sys.argv[1:] in ([], ["--write"])
    if sys.argv[1:] == ["--write"]:
        assert not OUT.exists(), "original pure proof directory already exists"
        OUT.mkdir()
        steps = []
        for name, command in FILES:
            started = now()
            result = subprocess.run(command, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (OUT / f"{name}.stdout.bin").write_bytes(result.stdout)
            (OUT / f"{name}.stderr.bin").write_bytes(result.stderr)
            steps.append({"name": name, "command": command, "started_utc": started,
                          "completed_utc": now(), "exit_code": result.returncode,
                          "stdout": seal(result.stdout), "stderr": seal(result.stderr)})
        RECEIPT.write_bytes((json.dumps({"schema": "i03-var11-pure-static-proof/v1",
                                       "native_started": False, "steps": steps},
                                      ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps(verify(), separators=(",", ":")))


if __name__ == "__main__":
    main()

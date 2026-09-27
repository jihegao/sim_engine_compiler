"""Record default-GBK Windows A01/A02 commands without touching SIMLOX.

snapshot CHECKOUT JSON
run CHECKOUT RECORD_STEM MODULE [MODULE_ARGUMENTS...]
Use the existing Python 3.12 environment; all outputs must be new paths.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import inspect
import json
import locale
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as file:
        file.write(data)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def git_config(repo: Path, key: str, scope: str | None = None) -> dict:
    args = ["git", "-C", str(repo), "config", "--show-origin"]
    if scope:
        args.append(scope)
    args.extend(["--get", key])
    process = subprocess.run(args, capture_output=True, text=True)
    return {"exit_code": process.returncode, "stdout": process.stdout.strip(),
            "stderr": process.stderr.strip()}


def snapshot(repo: Path, target: Path) -> None:
    assert not target.exists(), target
    assert git(repo, "rev-parse", "HEAD") == "9e5020eeb0ea29a7e442a991e9f559b7e209d676"
    assert git(repo, "cat-file", "-t", "595cb5eee9987324b19a8c3566f201f937e05f15") == "commit"
    assert sys.flags.utf8_mode == 0, "outer Python is not in default locale mode"
    assert locale.getencoding().lower() in ("cp936", "gbk", "936"), locale.getencoding()
    assert "PYTHONUTF8" not in os.environ and "PYTHONIOENCODING" not in os.environ
    sys.path.insert(0, str(repo / "src"))
    sys.path.insert(0, str(repo))
    from experiments.simlox_pairing.provenance import source_identity
    from sim_engine_compiler.reference import SimpyReferenceRuntime
    identity = source_identity()
    record = {
        "schema": "simlox-pr22-default-gbk-source-snapshot/v1",
        "captured_at_utc": utc(), "checkout": str(repo.resolve()),
        "cwd": str(Path.cwd().resolve()),
        "head": git(repo, "rev-parse", "HEAD"),
        "branch": git(repo, "branch", "--show-current"),
        "status_porcelain": git(repo, "status", "--porcelain"),
        "git_settings": {
            "autocrlf_effective": git_config(repo, "core.autocrlf"),
            "autocrlf_local": git_config(repo, "core.autocrlf", "--local"),
            "eol_effective": git_config(repo, "core.eol"),
            "eol_local": git_config(repo, "core.eol", "--local"),
        },
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "simpy_version": importlib.metadata.version("simpy"),
        "utf8_mode": sys.flags.utf8_mode,
        "locale_encoding": locale.getencoding(),
        "preferred_encoding": locale.getpreferredencoding(False),
        "imported_runtime_file": str(Path(inspect.getfile(SimpyReferenceRuntime)).resolve()),
        "environment_selectors": {
            "PYTHONPATH": os.environ.get("PYTHONPATH"),
            "PYTHONDONTWRITEBYTECODE": os.environ.get("PYTHONDONTWRITEBYTECODE"),
            "PYTHONUTF8": os.environ.get("PYTHONUTF8"),
            "PYTHONIOENCODING": os.environ.get("PYTHONIOENCODING"),
        },
        "source_identity": identity,
    }
    assert record["status_porcelain"] == "", "checkout has changed before tests"
    assert (record["environment_selectors"]["PYTHONPATH"] == "src" and
            record["environment_selectors"]["PYTHONDONTWRITEBYTECODE"] == "1"), "required environment not set"
    write_new(target, json_bytes(record))


def run(repo: Path, stem: Path, args: list[str]) -> None:
    assert not any(Path(str(stem) + suffix).exists() for suffix in
                   (".json", ".stdout", ".stderr")), stem
    environment = dict(os.environ)
    environment["PYTHONPATH"] = "src"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("PYTHONUTF8", None)
    environment.pop("PYTHONIOENCODING", None)
    assert sys.flags.utf8_mode == 0
    assert locale.getencoding().lower() in ("cp936", "gbk", "936")
    assert git(repo, "rev-parse", "HEAD") == "9e5020eeb0ea29a7e442a991e9f559b7e209d676"
    assert git(repo, "status", "--porcelain") == ""
    sys.path.insert(0, str(repo / "src"))
    sys.path.insert(0, str(repo))
    from experiments.simlox_pairing.provenance import source_identity
    before_identity = source_identity()
    command = [sys.executable, *args]
    started = utc()
    process = subprocess.run(command, cwd=repo, env=environment, capture_output=True)
    ended = utc()
    after_identity = source_identity()
    after_status = git(repo, "status", "--porcelain")
    stdout_path = Path(str(stem) + ".stdout")
    stderr_path = Path(str(stem) + ".stderr")
    write_new(stdout_path, process.stdout)
    write_new(stderr_path, process.stderr)
    record = {
        "schema": "simlox-pr22-default-gbk-command/v1", "checkout": str(repo.resolve()),
        "cwd": str(repo.resolve()), "command": command,
        "parent_python_utf8_mode": sys.flags.utf8_mode,
        "parent_locale_encoding": locale.getencoding(),
        "parent_preferred_encoding": locale.getpreferredencoding(False),
        "environment_selectors": {
            key: environment.get(key) for key in
            ("PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PYTHONUTF8", "PYTHONIOENCODING")
        },
        "started_at_utc": started, "ended_at_utc": ended,
        "exit_code": process.returncode,
        "stdout_path": str(stdout_path.resolve()),
        "stderr_path": str(stderr_path.resolve()),
        "stdout_sha256": hashlib.sha256(process.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(process.stderr).hexdigest(),
        "stdout_bytes": len(process.stdout), "stderr_bytes": len(process.stderr),
        "source_identity_before": before_identity,
        "source_identity_after": after_identity,
        "source_identity_unchanged": before_identity == after_identity,
        "git_status_after": after_status,
    }
    write_new(Path(str(stem) + ".json"), json_bytes(record))
    assert before_identity == after_identity, "checkout source bytes changed during command"
    assert after_status == "", "checkout changed during command"
    print(json.dumps({"record": str(stem) + ".json", "exit_code": process.returncode,
                      "stdout_sha256": record["stdout_sha256"],
                      "stderr_sha256": record["stderr_sha256"]}))
    if process.returncode:
        raise SystemExit(process.returncode)


if __name__ == "__main__":
    if sys.argv[1] == "snapshot" and len(sys.argv) == 4:
        snapshot(Path(sys.argv[2]), Path(sys.argv[3]))
    elif sys.argv[1] == "run" and len(sys.argv) >= 5:
        run(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4:])
    else:
        raise SystemExit("usage: driver.py snapshot CHECKOUT JSON | run CHECKOUT STEM PYTHON_ARGS...")

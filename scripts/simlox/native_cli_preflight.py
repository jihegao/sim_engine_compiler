"""Read-only SIMLOX CLI preflight against a known-good phase7 SXI.

The sole output is a fresh JSON export and log under ignored data/local. Exit
code zero without a nonempty export is a failure, as seen on 4700-3 in P1.
"""

from __future__ import annotations

import hashlib
import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "data/local/j35-contract-probes/preflight-direct"
NATIVE_WORKDIR = Path("C:/Users/user/Documents/Codex/2026-09-26/simlox-j35-event-parity/workspace")
EXE = Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe")
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
SOURCE = Path("C:/Users/user/Documents/Codex/2026-09-26/simlox-j35-event-parity/workspace/evidence/phase7/sid8-pm-first20/sid8-pm-first20.sxi")
SOURCE_SHA = "749ad9aa0d0df57f9b5f0656621c655e0fca037093d40b0c5356a925e833fba6"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    allowed = (ROOT / "data/local/j35-contract-probes").resolve()
    if allowed not in out.parents:
        raise ValueError("Output directory must be below ignored data/local/j35-contract-probes")
    if sha256(EXE) != EXE_SHA or sha256(SOURCE) != SOURCE_SHA:
        raise ValueError("SIMLOX executable or known-good source SXI fingerprint changed")
    process_list = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Simlox.exe"], capture_output=True, text=True, check=True)
    if "Simlox.exe" in process_list.stdout:
        raise RuntimeError("A SIMLOX process is already running; leave it untouched")
    out.mkdir(parents=True, exist_ok=True)
    export = out / "known-good-roundtrip.json"
    log = out / "known-good-export.log"
    result_path = out / "result.json"
    for path in (export, log, result_path):
        if path.exists():
            raise FileExistsError(path)
    command = [str(EXE), str(SOURCE), "-silent", "-jexport", str(export), "-log", str(log), "-close"]
    began = time.perf_counter()
    completed = subprocess.run(command, cwd=NATIVE_WORKDIR, capture_output=True, text=True, timeout=120)
    result = {
        "command": command,
        "source_sha256": SOURCE_SHA,
        "executable_sha256": EXE_SHA,
        "working_directory": str(NATIVE_WORKDIR),
        "exit_code": completed.returncode,
        "wall_seconds": time.perf_counter() - began,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "export_bytes": export.stat().st_size if export.exists() else 0,
        "log_bytes": log.stat().st_size if log.exists() else 0,
    }
    result["valid"] = completed.returncode == 0 and result["export_bytes"] > 4
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"exit_code": result["exit_code"], "export_bytes": result["export_bytes"], "log_bytes": result["log_bytes"], "valid": result["valid"]}))
    if not result["valid"]:
        raise RuntimeError(f"Known-good SXI export failed validation; inspect {result_path}")


if __name__ == "__main__":
    main()

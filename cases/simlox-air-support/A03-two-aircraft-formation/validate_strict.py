"""Source-bound A03 v2 checks layered over the preserved probe validator.

``validate.py`` is retained byte-for-byte because the three historical probe
archives bind its SHA-256. New runs also bind and execute this stricter check.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate as original  # noqa: E402

EXPECTED_SUMMARY = {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": 1, "MSUF": 1}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_summary(report: dict) -> list[str]:
    try:
        rows = original.native.table_rows(report, "ResultSummary")
    except (KeyError, ValueError) as error:
        return [str(error)]
    if len(rows) != 1:
        return [f"ResultSummary must have one row, got {len(rows)}"]
    errors = []
    for field, expected in EXPECTED_SUMMARY.items():
        actual = rows[0].get(field)
        if type(actual) not in (int, float) or not math.isfinite(actual) or actual != expected:
            errors.append(f"ResultSummary.{field}: expected {expected}, got {actual!r}")
    return errors


def expected_arguments(run_dir: PureWindowsPath) -> dict[str, str]:
    source = run_dir / "input.json"
    sxi = run_dir / "model.sxi"
    sxo = run_dir / "model.sxo"
    return {
        "import": f'-silent -jimport "{source}" -save "{sxi}" -log "{run_dir / "import.log"}" -close',
        "export": f'"{sxi}" -silent -jexport "{run_dir / "roundtrip-raw.json"}" -log "{run_dir / "export.log"}" -close',
        "calc": f'"{sxi}" -silent -threads 1 -calc -log "{run_dir / "run.log"}" -close',
        "jsonreport": f'"{sxo}" -silent -jsonreport "{run_dir / "report-raw.json"}" -log "{run_dir / "report-export.log"}" -close',
    }


def utc_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0) else None


def check_invocation(invocation: dict, steps: list[dict], run_dir: Path) -> list[str]:
    errors = []
    mode = invocation.get("execution_mode", "interactive_v1")
    if mode == "interactive_v1":
        runner = HERE / "run_native.ps1"
    elif mode == "ssh_cli_v1":
        runner = HERE / "run_native_ssh.ps1"
    else:
        return [f"unsupported A03 execution mode: {mode!r}"]
    if invocation.get("runner_sha256") != sha256(runner):
        errors.append("invocation is not bound to the current native runner")
    name = invocation.get("session_name")
    session_id = invocation.get("session_id")
    if mode == "interactive_v1":
        user = invocation.get("session_user")
        line = invocation.get("session_query_line")
        if (
            not isinstance(name, str)
            or re.fullmatch(r"Console|RDP-Tcp#\d+", name, re.IGNORECASE) is None
            or type(session_id) is not int
            or session_id <= 0
            or not isinstance(user, str)
            or not user
            or not isinstance(line, str)
            or re.match(
                rf"^\s*>?\s*{re.escape(name)}\s+{re.escape(user)}\s+{session_id}\s+Active(?:\s|$)",
                line,
                re.IGNORECASE,
            ) is None
        ):
            errors.append("invocation lacks active interactive session evidence")
    elif (invocation.get("schema") != "simlox-a03-invocation/ssh-cli-v1"
          or type(session_id) is not int or session_id != 0
          or name not in (None, "")
          or invocation.get("ssh_connection_present") is not True
          or type(invocation.get("ssh_client_present")) is not bool
          or not isinstance(invocation.get("ssh_ancestor_names"), list)
          or not all(isinstance(item, str) for item in invocation["ssh_ancestor_names"])
          or "sshd.exe" not in [item.lower() for item in invocation["ssh_ancestor_names"]]
          or not isinstance(invocation.get("host_name"), str)
          or re.fullmatch(r"[A-Za-z0-9._-]+", invocation["host_name"]) is None
          or utc_timestamp(invocation.get("created_utc")) is None):
        errors.append("invocation lacks authenticated SSH session provenance")
    if mode == "ssh_cli_v1" and invocation.get("queue_mutex") != r"Global\SimloxIssue18NativeQueue":
        errors.append("SSH run lacks the host-wide queue mutex identity")
    gui = invocation.get("coexisting_gui") if mode == "ssh_cli_v1" else None
    if mode == "ssh_cli_v1":
        allow_gui = invocation.get("allow_existing_gui")
        if type(allow_gui) is not bool or allow_gui != (gui is not None):
            errors.append("SSH GUI coexistence flag and process evidence differ")
        if gui is not None:
            gui_id = gui.get("session_id") if isinstance(gui, dict) else None
            gui_line = gui.get("session_query_line") if isinstance(gui, dict) else None
            if (not isinstance(gui, dict)
                    or type(gui.get("pid")) is not int or gui["pid"] <= 0
                    or type(gui_id) is not int or gui_id <= 0
                    or not isinstance(gui_line, str)
                    or re.match(rf"^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+{gui_id}\s+(?:Active|运行中)(?:\s|$)", gui_line, re.IGNORECASE) is None
                    or utc_timestamp(gui.get("process_start_utc")) is None):
                errors.append("SSH run lacks active existing-GUI process evidence")
    original_path = invocation.get("original_run_dir")
    if not isinstance(original_path, str):
        errors.append("invocation lacks the original Windows run path")
        return errors
    original_run_dir = PureWindowsPath(original_path)
    if (not original_run_dir.is_absolute()
            or original_run_dir.name != run_dir.name
            or original_run_dir.name != invocation.get("run_id")):
        errors.append("original Windows run path does not match the run identity")
        return errors
    arguments = expected_arguments(original_run_dir)
    if not isinstance(steps, list) or any(not isinstance(step, dict) for step in steps):
        errors.append("native command sequence or exit status differs from contract")
    elif [step.get("name") for step in steps] != list(arguments):
        errors.append("native command sequence or exit status differs from contract")
    else:
        previous_end = utc_timestamp(invocation.get("created_utc")) if mode == "ssh_cli_v1" else None
        for step in steps:
            duration = step.get("wall_seconds")
            if (step.get("exit_code") != 0
                    or step.get("arguments") != arguments[step["name"]]
                    or type(duration) not in (int, float)
                    or not math.isfinite(duration)
                    or duration < 0):
                errors.append(f"native {step['name']} arguments, exit or duration differs from contract")
            if mode == "ssh_cli_v1":
                start = utc_timestamp(step.get("started_utc"))
                end = utc_timestamp(step.get("completed_utc"))
                if start is None or end is None or start > end or (previous_end is not None and start < previous_end):
                    errors.append(f"native {step['name']} lacks ordered UTC timestamps")
                previous_end = end
                if gui is not None and step.get("coexisting_gui_present_after") is not True:
                    errors.append(f"native {step['name']} did not preserve the existing GUI")
    return errors


def validate(run_dir: Path) -> dict:
    invocation = json.loads((run_dir / "invocation.json").read_text(encoding="utf-8-sig"))
    if invocation.get("strict_validator_sha256") != sha256(Path(__file__)):
        raise ValueError("invocation strict validator hash differs from acceptance source")
    base = original.validate(run_dir)
    report = json.loads(original.native.remove_trailing_commas(
        (run_dir / "report-raw.json").read_bytes()))
    steps = json.loads((run_dir / "steps.json").read_text(encoding="utf-8-sig"))
    differences = [*base["differences"], *check_summary(report),
                   *check_invocation(invocation, steps, run_dir)]
    return {**base, "schema": "simlox-a03-strict-validation/v2",
            "passed": not differences, "differences": differences,
            "strict_validator_sha256": sha256(Path(__file__))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    result = validate(args.run_dir)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

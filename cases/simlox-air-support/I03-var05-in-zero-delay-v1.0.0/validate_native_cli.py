"""Read-only IN-zero physical trace and full 5,210-cell report validator."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from build import typed_equal
from check_roundtrip import parse
from event_ledger import validate as event_validate, validate_lines as event_validate_lines
from report_oracle import check_report
from source_gate import INPUT_SHA, RUN_ID

HERE = Path(__file__).resolve().parent
SCHEMA = "i03-var05-in-zero-behavior/v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def converter(text: str, run: Path, model_stem: str = "model") -> None:
    def exact_path_line(label: str, suffix: str) -> None:
        lines = re.findall(rf"(?m)^{re.escape(label)}: ([^\r\n]+)\r?$", text)
        assert len(lines) == 1, (label, lines)
        expected = str((run.resolve() / f"{model_stem}.{suffix}")).replace("\\", "/")
        assert lines[0].replace("\\", "/") == expected, (label, lines[0], expected)

    exact_path_line("Input file", "sxi")
    exact_path_line("Output file", "sxo")
    exact_path_line("File", "sxi")
    assert len(re.findall(r"^Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0$", text, re.M)) == 1
    warnings = re.findall(r"(?m)^Form: ([^\r\n]+)\r?\n(rec [^\r\n]+)\r?$", text)
    assert warnings == [
        ("Control", "rec 1: (warning #108) Enabling simulation log may generate extensive data in log file"),
        ("System", "rec 1: (warning #126) This system contains no items: TEACH-AIR-01"),
    ], warnings
    assert len(re.findall(r"(?m)^Form: ", text)) == len(re.findall(r"(?m)^rec ", text)) == 2
    codes = [(kind.lower(), code) for kind, code in re.findall(
        r"\b(warning|error|notice|note)\s*#(\d+)", text, re.I)]
    assert codes == [("warning", "108"), ("warning", "126")], codes
    assert text.count("Input conversion completed.") == 1
    assert text.count("Starting simulation") == text.count("Saving results") == 1


def check(run: Path, log_override: list[str] | None = None, report_override: dict | None = None) -> dict:
    assert run.name == RUN_ID
    assert sha(run / "input.json") == INPUT_SHA
    assert typed_equal(parse(HERE / "native-input.json"), parse(run / "input.json"))
    log_path = run / "model.log"
    report = report_override if report_override is not None else parse(run / "report-raw.json")
    timeline = event_validate(log_path, parent=False) if log_override is None else event_validate_lines(log_override, parent=False)
    converter((run / "model-run.log").read_text(encoding="utf-8-sig"), run)
    cells = check_report(report, timeline, parent=False)
    assert timeline["microstates"]["terminal"]["local"] == 2
    assert timeline["microstates"]["terminal"]["IN_pending_local_receipt"] == 0
    return {"schema": SCHEMA, "passed": True, "issues": [],
            "run_id": RUN_ID, "input_sha256": INPUT_SHA,
            "report_cell_checks": cells, "typed_event_records": timeline["timed_events"],
            "timeline": timeline}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    try:
        result = check(args.run)
    except Exception as exc:
        result = {"schema": SCHEMA, "passed": False, "issues": [f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(0 if result["passed"] else 1)

"""Read-only gate for the single forbidden <REPAIR> preparation converter run."""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT_SHA = "e408ff21a8dc9cb7c12ae5acd50d14089846299a4382e40303c9d68edc472d7e"
RUN_ID = "b02-var04-repair-prep-v012-ssh-20261006-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(run):
    problems = []
    if run.name != RUN_ID:
        problems.append("unreviewed run identity")
    if sha(HERE / "native-input.json") != INPUT_SHA or sha(run / "input.json") != INPUT_SHA:
        problems.append("frozen/run input bytes differ")
    roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    if roundtrip.get("passed") is not True or roundtrip.get("source_sha256") != INPUT_SHA:
        problems.append("authored import/export identity not verified")
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    if [s.get("name") for s in steps[:4]] != ["import", "export", "check_import_export", "calc"] or len(steps) not in (4, 5):
        problems.append("native stage order differs")
    if len(steps) == 5 and steps[4].get("name") != "check_negative":
        problems.append("unexpected fifth stage")
    if any(s.get("status") != "completed" for s in steps[:4]):
        problems.append("a native stage did not complete")
    if any(s.get("gui_preserved") is not True for s in steps[:4]):
        problems.append("GUI guard not recorded for every stage")
    calc_exit_code = steps[3].get("exit_code") if len(steps) >= 4 else None
    if not isinstance(calc_exit_code, int):
        problems.append("calculation exit code was not recorded")
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    summary = re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
    if len(summary) != 1 or summary[0][0] != "1" or summary[0][2] != "0":
        problems.append("converter count is not exactly one error and zero notes")
    error_lines = re.findall(r"^rec\s+(\d+):\s+\(error #(\d+)\)\s+(.+)$", log, re.M)
    if len(error_lines) != 1:
        problems.append("native error line count differs")
    diagnostic = None
    if len(error_lines) == 1:
        record, code, message = error_lines[0]
        before = log[:log.index(f"rec {record}: (error #{code})")]
        forms = re.findall(r"^Form:\s*(.+)$", before, re.M)
        form = forms[-1].strip() if forms else None
        diagnostic = {"form": form, "record": int(record), "code": int(code), "message": message.strip()}
        if form not in {"TaskBreakDown", "MissionPreparation"} or record != "1":
            problems.append("error does not identify changed breakdown or linked preparation record 1")
        identifies_repair = bool(re.search(r"<REPAIR>|\brepair\b", message, re.I) and
                                 re.search(r"invalid|subtask|breakdown|preparation|prohibit|allowed|direct", message, re.I))
        identifies_link = bool(re.search(r"PREP-FIXED", message, re.I) and
                               re.search(r"invalid|subtask|breakdown|preparation", message, re.I))
        if not (identifies_repair or identifies_link):
            problems.append("error message lacks REPAIR or linked PREP-FIXED breakdown context")
    warning_lines = re.findall(r"^rec\s+\d+:\s+\(warning #(\d+)\)", log, re.M)
    if any(code not in {"108", "126"} for code in warning_lines):
        problems.append("unclassified converter warning")
    if len(summary) == 1 and int(summary[0][1]) != len(warning_lines):
        problems.append("warning count differs from lines")
    sxo = run / "model.sxo"
    if sxo.exists() and sxo.stat().st_size > 4:
        problems.append("substantive SXO exists after rejection")
    if (run / "report-raw.json").exists():
        problems.append("report exists after rejection")
    model_log = run / "model.log"
    if model_log.exists() and re.search(r"mission\s+.*(?:starts|completed)|subtask\s+.*(?:starts|completed)", model_log.read_text(encoding="utf-8-sig", errors="replace"), re.I):
        problems.append("physical mission/subtask event exists after rejection")
    return {"schema": "simlox-b02-var04-negative-validation/v3", "run_id": run.name,
            "decision": "GO_BOUNDED" if not problems else "NO_GO", "passed": not problems,
            "problems": problems, "diagnostic": diagnostic,
            "converter_summary": summary[0] if len(summary) == 1 else summary,
            "calc_exit_code": calc_exit_code,
            "input_sha256": INPUT_SHA,
            "scope": "single predefined REPAIR rejection in linked mission preparation; no simulation claim"}


def main():
    try:
        result = check(Path(sys.argv[1]))
    except Exception as exc:
        result = {"schema": "simlox-b02-var04-negative-validation/v3", "decision": "NO_GO",
                  "passed": False, "problems": [f"checker exception: {type(exc).__name__}: {exc}"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

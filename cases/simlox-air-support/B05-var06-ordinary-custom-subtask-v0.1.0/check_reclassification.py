"""Read-only author check of the already accepted B05.var03 native pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "B05-var03-predefined-inspect-v1.0.0"
PINS = {
    "ordinary-control": ("37423c0c127a014d082c740780eee8531e877c405bcd537918b8fc1e4289892b", "b05-var03-ordinary-20260930-01", "f8edd2fa92e8dc68e37a87b7f457b9fe644e89baa963424ab9a34eaf2ee14245"),
    "predefined-inspect": ("2fc3b10f9a17db8dc4cc4fa4810d79ef9231775c1fcb658303742ad15e41fc46", "b05-var03-predefined-20260930-01", "e47ddd60c4ccba0750ddebacd948a1feedfcb46322eb6f288d82843d2b3fdad4"),
}
CHECKS: dict[str, bool] = {}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name: str, condition: bool) -> None:
    CHECKS[name] = bool(condition)


def load(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Native report JSON has a trailing comma. Preserve its raw bytes.
        out = []
        quoted = escaped = False
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def tables(doc, root="model"):
    return {t["name"]: t for t in doc[root]["tables"]}


def rows(doc, name, root="model"):
    tab = tables(doc, root)[name]
    columns = [col["name"] for col in tab["columns"]]
    return [dict(zip(columns, row)) for instance in tab["instances"] for row in instance["rows"]]


def event_times(log: str, phrase: str):
    return [float(match.group(1)) for line in log.splitlines() if all(part in line for part in phrase.split("|")) and (match := re.match(r"Time: ([0-9.]+)", line))]


def close(got, want):
    return len(got) == len(want) and all(abs(a - b) < 0.00005 for a, b in zip(got, want))


def run_case(variant: str):
    source_sha, run_id, closure_sha = PINS[variant]
    source_file = SOURCE / f"{variant}-input.json"
    run = SOURCE / "runs" / run_id
    check(f"{variant} source SHA", sha(source_file) == source_sha)
    check(f"{variant} closure SHA", sha(run / "closure.json") == closure_sha)
    closure = load(run / "closure.json")
    check(f"{variant} closure identity", closure["run_id"] == run_id and closure["error"] is None)
    check(f"{variant} unchanged source", closure["source_hashes_before"] == closure["source_hashes_after"] and closure["source_hashes_before"]["input"] == source_sha)
    check(f"{variant} 12 raw seals", len(closure["raw"]) == 12)
    for filename, seal in closure["raw"].items():
        raw = run / filename
        check(f"{variant} raw {filename}", raw.stat().st_size == seal["bytes"] and sha(raw) == seal["sha256"])
    source = load(source_file)
    run_input = load(run / "input.json")
    exported = load(run / "roundtrip-raw.json")
    check(f"{variant} input identity", source == run_input)
    populated = {name: rows(source, name) for name, tab in tables(source).items() if any(instance["rows"] for instance in tab["instances"])}
    check(f"{variant} 17 populated tables", len(populated) == 17)
    for name, authored in populated.items():
        check(f"{variant} roundtrip {name}", authored == rows(exported, name))
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    for label, phrase, expected in (
        ("SEQ1 start", "seqno 1 within system preparation task|starts performing", [7]),
        ("SEQ1 complete", "seqno 1 within system preparation task|completed", [7.16667]),
        ("SEQ2 start", "seqno 2 within system preparation task|starts performing", [7.16667]),
        ("SEQ2 complete", "seqno 2 within system preparation task|completed", [7.5]),
        ("preparation end", "preparation ended, mission:", [7.5]),
        ("mission start", "mission starting,", [8]),
        ("mission success", "mission success:", [10]),
        ("mission complete", "mission completed:", [10]),
    ):
        check(f"{variant} {label}", close(event_times(log, phrase), expected))
    check(f"{variant} no failure/wait/cancel", not re.search(r"mission (cancelled|aborted):|resource request failed|failure occurred", log, re.I))
    report = load(run / "report-raw.json")
    summary = rows(report, "ResultSummary", "report")
    system = rows(report, "SystemResults", "report")
    stock = rows(report, "StockTotalResults", "report")
    check(f"{variant} summary", len(summary) == 1 and summary[0]["MSUF"] == 1 and summary[0]["MSTF"] == 1)
    check(f"{variant} bins", len(system) == len(stock) == 72)
    check(f"{variant} complete clock", all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(system)) and all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(stock)))
    check(f"{variant} terminal ready", system[-1]["ETINT"] == 36 and system[-1]["NSYRY"] == 1)
    return source, report, log


def main():
    check("contract pin", sha(HERE / "contract.json") == "7a87b8d51a44b6fc0e5ed03324e6ac362eac8ca1b264a9644b7b9a55b3122706")
    check("original independent report pin", sha(SOURCE / "review/independent-readonly-2026-09-30.json") == "ac7ce7fda400db5a6a60d73a21d9dea43b226f5894dbbd6df956c5ec9dd44c4b")
    original = load(SOURCE / "review/independent-readonly-2026-09-30.json")
    check("original independent acceptance", original["passed"] is True and original["check_count"] == 156 and original["failures"] == [])
    ordinary, ordinary_report, ordinary_log = run_case("ordinary-control")
    predefined, predefined_report, predefined_log = run_case("predefined-inspect")
    check("custom SubTaskType", {r["SUTID"] for r in rows(ordinary, "SubTaskType")} >= {"INSPECT", "SERVICE"})
    for name, doc, expected in (("ordinary", ordinary, "INSPECT"), ("predefined", predefined, "<INSPECT>")):
        task_rows = sorted([r for r in rows(doc, "TaskBreakDown") if r["TID"] == "PREP-FIXED"], key=lambda r: r["SEQ"])
        check(f"{name} task rows", [(r["SEQ"], r["SUTID"], r["DURN"]) for r in task_rows] == [(1, expected, 1 / 6), (2, "SERVICE", 1 / 3)])
    changed = [name for name in tables(ordinary) if tables(ordinary)[name] != tables(predefined)[name]]
    check("pair changed tables", sorted(changed) == ["ProblemDescription", "TaskBreakDown"])
    check("same native event log", ordinary_log == predefined_log)
    check("same full result tables", all(tables(ordinary_report, "report")[name] == tables(predefined_report, "report")[name] for name in ("ResultSummary", "SystemResults", "StockTotalResults")))
    check("different descriptions", tables(ordinary_report, "report")["ProblemDescription"] != tables(predefined_report, "report")["ProblemDescription"])
    failures = [name for name, passed in CHECKS.items() if not passed]
    result = {"schema": "simlox-b05-var06-author-readonly-reclassification/v1", "passed": not failures, "check_count": len(CHECKS), "failures": failures, "new_native_run_count": 0, "source_case": "B05.var03", "ordinary_run_id": PINS["ordinary-control"][1], "predefined_run_id": PINS["predefined-inspect"][1]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps(result, indent=2))
    return not failures


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)

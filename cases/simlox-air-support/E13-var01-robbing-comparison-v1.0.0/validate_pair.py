"""Read-only author replay of the frozen E13.var01 enabled/control pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ARMS = {
    "enabled": ("E13-var01-two-item-robbing-probe-v0.1.2", "e13-var01-two-item-probe-v012-ssh-20261004-01"),
    "control": ("E13-var01-two-item-no-robbing-control-v0.1.3", "e13-var01-no-robbing-control-v013-ssh-20261004-01"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # SIMLOX's report writer emits trailing commas. Parse a copy only.
        out: list[str] = []
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


def tables(doc: dict, key: str) -> dict:
    return {t["name"]: t for t in doc[key]["tables"]}


def cells(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def main() -> None:
    checks = 0
    failures: list[str] = []

    def check(ok: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(message)

    data = {}
    for label, (package, run_id) in ARMS.items():
        base = ROOT / package
        run = base / "runs" / run_id
        contract = json.loads((base / "contract.json").read_text(encoding="utf-8"))
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        input_doc = native(base / "native-input.json")
        exported = native(run / "roundtrip-raw.json")
        report = native(run / "report-raw.json")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        check(closure["run_id"] == run_id and closure["error"] is None, f"{label}: native closure")
        check(sha(base / "native-input.json") == contract["native_input_sha256"], f"{label}: input pin")
        check(sha(base / "exact-diff.json") == contract["exact_diff_sha256"], f"{label}: diff pin")
        check(closure["source_hashes_before"] == closure["source_hashes_after"], f"{label}: source changed during run")
        check(closure["source_hashes_before"]["input"] == contract["native_input_sha256"], f"{label}: closure input")
        check(closure["source_hashes_before"]["contract"] == sha(base / "contract.json"), f"{label}: closure contract")
        check(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{label}: invocation seal")
        check(len(closure["raw"]) == 12, f"{label}: raw count")
        for name, meta in closure["raw"].items():
            path = run / name
            check(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"{label}: raw {name}")
        authored = tables(input_doc, "model")
        roundtrip = tables(exported, "model")
        populated = [name for name, t in authored.items() if cells(t)]
        check(len(populated) == 20, f"{label}: 20 populated tables")
        for name in populated:
            check(authored[name]["columns"] == roundtrip[name]["columns"] and cells(authored[name]) == cells(roundtrip[name]), f"{label}: roundtrip {name}")
        check(json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"], f"{label}: roundtrip checker")
        check("Errors: 0" in (run / "model.log").read_text(encoding="utf-8-sig", errors="replace") or "Errors: 0" in (run / "run.log").read_text(encoding="utf-8-sig", errors="replace"), f"{label}: converter errors")
        check("(warning #108)" in (run / "run.log").read_text(encoding="utf-8-sig", errors="replace"), f"{label}: warning 108")
        check("Import completed!" in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"), f"{label}: import")
        check("Export completed!" in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"), f"{label}: export")
        reports = tables(report, "report")
        check(all(name in reports for name in ("ResultSummary", "SystemResults", "StockTotalResults")), f"{label}: report tables")
        check(len(cells(reports["SystemResults"])) == 72 and len(cells(reports["StockTotalResults"])) == 72, f"{label}: report intervals")
        data[label] = {"package": package, "run_id": run_id, "closure_sha256": sha(run / "closure.json"), "input": authored,
                       "reports": reports, "log": log}

    yes, no = data["enabled"], data["control"]
    for name in yes["input"]:
        if name not in no["input"]:
            check(False, f"control missing {name}")
            continue
        a, b = cells(yes["input"][name]), cells(no["input"][name])
        if name == "ProblemDescription":
            check(len(a) == len(b) == 1 and set(a[0]) == set(b[0]) == {"PDESC"}, "description only")
        elif name == "Control":
            check(len(a) == len(b) == 1 and {k: v for k, v in a[0].items() if k != "ENROB"} == {k: v for k, v in b[0].items() if k != "ENROB"} and a[0]["ENROB"] == "Y" and b[0]["ENROB"] == "N", "ENROB only")
        else:
            check(a == b and yes["input"][name]["columns"] == no["input"][name]["columns"], f"paired source {name}")
    common = [
        "Time: 8.09414 <TEACH-AIR-01,0> critical random failure added",
        "subitem failed: <TEACH-LRU-01,0,0>",
        "Time: 8.15663 <TEACH-AIR-01,1> critical random failure added",
        "subitem failed: <TEACH-LRU-02,0,1>",
        "Time: 8.35496 <TEACH-LRU-01,0,BASE-01,0> Start repair of item <TEACH-LRU-01,0,0>",
        "Time: 8.47992 <TEACH-LRU-02,0,BASE-01,0> Start repair of item <TEACH-LRU-02,0,1>",
    ]
    for fragment in common:
        for label in ARMS:
            check(fragment in data[label]["log"], f"{label}: pre-decision {fragment}")
    ylog, nlog = yes["log"], no["log"]
    for fragment in (
        "Time: 8.47992 <TEACH-AIR-01,BASE-01,0> system SURP task 1 on <TEACH-AIR-01,1> starts to rob",
        "Time: 8.47992  robbing task 4 on <TEACH-AIR-01,0> started",
        "Time: 8.64659  system SURP task 1 on <TEACH-AIR-01,1> subitem received <TEACH-LRU-02,0,2>",
        "Time: 8.97992 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,1>",
        "Time: 12.4799  robbing task 4 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-02,0,1>",
        "Time: 20.6883 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>",
    ):
        check(fragment in ylog, f"enabled: {fragment}")
    check("starts to rob" not in nlog and "robbing task" not in nlog, "control: no robbing")
    check("Time: 12.8133 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,1>" in nlog, "control recipient ready")
    check("Time: 20.6883 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in nlog, "control donor ready")
    check(abs((12.8133 - 8.97992) - 3.83338) < 1e-8, "recipient benefit")
    ra, rb = yes["reports"], no["reports"]
    check(cells(ra["ResultSummary"]) == cells(rb["ResultSummary"]), "ResultSummary equality")
    check(cells(ra["StockTotalResults"]) == cells(rb["StockTotalResults"]), "all 72 stock intervals equal")
    sys_a, sys_b = cells(ra["SystemResults"]), cells(rb["SystemResults"])
    differing = [(i, col) for i, (a, b) in enumerate(zip(sys_a, sys_b)) for col in a if a[col] != b[col]]
    check(len(differing) == 42, "42 differing SystemResults cells")
    check(set(i for i, _ in differing) == set(range(16, 26)), "SystemResults difference window")
    check(any(col == "NROBT" for _, col in differing), "NROBT separates arms")
    result = {"schema": "simlox-e13-var01-author-paired-validation/v1", "passed": not failures,
              "checks": checks, "failures": failures, "arms": {label: {k: data[label][k] for k in ("package", "run_id", "closure_sha256")} for label in ARMS},
              "recipient_ready_hours": {"enabled": 8.97992, "control": 12.8133, "benefit": 3.83338},
              "donor_ready_hours": {"enabled": 20.6883, "control": 20.6883},
              "system_report_changed_cells": len(differing), "stock_report_changed_cells": 0,
              "raw_location_policy": "local_only_ignored_runs_not_committed"}
    path = HERE / "author-validation-2026-10-04.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "checks": checks, "failures": failures}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Author read-only replay of a sealed D11.var02 native run."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas, table_rows  # noqa: E402

ADVANCE = HERE.name == "D11-var02-dtim-defer-v1.0.0"
TAG = "defer" if ADVANCE else "control"
PARENT = HERE.parent / ("D11-var02-dtim-control-v1.0.0" if ADVANCE else "D11-var01-atim-control-v1.0.0") / "native-input.json"
PARENT_SHA = "29e7cdb16e9ab376641edf774a5fc91eb9c44283fd997fa435b79b48423fe901" if ADVANCE else "94c0addbaff610b656b25dd328949ea9710ab9a593cafebe488f7bfca665ead8"
INPUT_SHA = "5288d185639174b07c8a062d0ebae7e53cf9bfccbe6936884e58ad15807e9b29" if ADVANCE else "29e7cdb16e9ab376641edf774a5fc91eb9c44283fd997fa435b79b48423fe901"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
DICTIONARY_SHA = "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
FLIGHTS = [(8, 12), (16, 17), (20, 21), (24, 25)] + ([(25.25, 26.25)] if ADVANCE else []) + [(26.5, 27.5)]
ASSIGNED = [(7, 12), (15, 17), (19, 21), (23, 25)] + ([(25, 27.5)] if ADVANCE else [(26, 27.5)])
PM_TASK_START = 25.0
PM_WORK_START = 27.5 if ADVANCE else 25.0
PM_WORK_END = PM_WORK_START + 1


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fraction(a: float, b: float, spans: list[tuple[float, float]]) -> float:
    return sum(max(0.0, min(b, y) - max(a, x)) for x, y in spans) / (b - a)


def main() -> None:
    run = Path(sys.argv[1]).resolve()
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected, "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float, tol: float = 3e-5) -> None:
        checks.append({"name": name, "passed": abs(actual - expected) <= tol, "actual": actual,
                       "expected": expected, "tolerance": tol})

    try:
        contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
        invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
        roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
        report = json.loads(remove_trailing_commas((run / "report-raw.json").read_bytes()))
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck("parent SHA", sha(PARENT), PARENT_SHA)
        ck("frozen input SHA", sha(HERE / "native-input.json"), INPUT_SHA)
        ck("copied run input SHA", sha(run / "input.json"), INPUT_SHA)
        ck("contract source pins", (contract["input_sha256"], contract["parent_input_sha256"]),
           (INPUT_SHA, PARENT_SHA))
        ck("installed manual SHA", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")), MANUAL_SHA)
        ck("installed dictionary SHA", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")), DICTIONARY_SHA)
        ck("installed executable SHA", sha(Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")), EXE_SHA)
        ck("run identity", (invocation["case_id"], invocation["run_id"], invocation["input_sha256"], invocation["parent_sha256"]),
           ("D11", run.name, INPUT_SHA, PARENT_SHA))
        ck("SSH context", (invocation["session_id"], invocation["ssh_connection_present"],
                           "sshd.exe" in invocation["ssh_ancestor_names"]), (0, True, True))
        ck("GUI identity", (invocation["gui"]["pid"], invocation["gui"]["session_id"]), (13340, 1))
        ck("host-wide queue", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        ck("five steps", [s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"])
        ck("steps succeeded with GUI preserved", all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), True)
        ck("roundtrip passed", roundtrip["passed"], True)
        ck("roundtrip 18 populated tables", len(roundtrip["populated_tables"]), 18)
        ck("closure error", closure["error"], None)
        ck("invocation seal", closure["invocation_sha256"], sha(run / "invocation.json"))
        ck("source pins remained fixed", closure["source_hashes_after"], closure["source_hashes_before"])
        ck("source pin input", closure["source_hashes_before"]["input"], INPUT_SHA)
        ck("source pin parent", closure["source_hashes_before"]["parent"], PARENT_SHA)
        ck("source pin contract", closure["source_hashes_before"]["contract"], sha(HERE / "contract.json"))
        ck("raw count", len(closure["raw"]), 12)
        for name, seal in sorted(closure["raw"].items()):
            ck(f"raw seal {name}", (sha(run / name), (run / name).stat().st_size), (seal["sha256"], seal["bytes"]))
        ck("conversion errors and classified warnings", ("Errors: 0, Warnings: 2, Notes: 0" in calc,
           "warning #108" in calc, "warning #126" in calc), (True, True, True))
        ck("nonempty SXO", (run / "model.sxo").stat().st_size > 4, True)

        def times(pattern: str) -> list[float]:
            return [float(x) for x in re.findall(pattern, log, re.MULTILINE)]

        ck("mission starts", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|SHORT-MISSION),[^\n]+> mission starting, duration: [14] : <TEACH-AIR-01,0>$"), [a for a, _ in FLIGHTS])
        ck("mission completions", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|SHORT-MISSION),[^\n]+> mission completed: <TEACH-AIR-01,0>$"), [b for _, b in FLIGHTS])
        ck("mission successes", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|SHORT-MISSION),[^\n]+> mission success: $"), [b for _, b in FLIGHTS])
        ck("cancellation", times(r"^Time: ([\d.]+) <SHORT-MISSION,TEACH-UNIT,0,0,4> mission cancelled: $"), [] if ADVANCE else [25.5833])
        ck("PM status labels", re.findall(r"^ \.MS4 (Critical|Non-Critical) $", log, re.MULTILINE),
           ["Non-Critical", "Non-Critical", "Critical"] if ADVANCE else ["Critical"])
        ck("PM task created", times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started$"), [PM_TASK_START])
        ck("PM identity", len(re.findall(r"^Time: [\d.]+  system PM task \d+ on <TEACH-AIR-01,0> PMID: MS4$", log, re.MULTILINE)), 1)
        ck("PM task ended", times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed$"), [PM_WORK_END])
        ck("PM subtask work starts", times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours$"), [PM_WORK_START])
        ck("PM subtask work ends", times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> completed$"), [PM_WORK_END])
        ck("PM paused", times(r"^Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> system PM task \d+ on <TEACH-AIR-01,0> paused\.$"), [25.0] if ADVANCE else [])
        ck("PM continued on critical", times(r"^Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> system PM task \d+ on <TEACH-AIR-01,0> continued  : PM task has become critical$"), [27.5] if ADVANCE else [])
        ck("no failure event", bool(re.search(r"failure (?:occurred|identified|generated)", log, re.I)), False)

        summary = table_rows(report, "ResultSummary")
        ck("one summary", len(summary), 1)
        for key in ("MTMF", "STMF"):
            near(f"summary {key}", summary[0][key], 1 if ADVANCE else 8 / 9)
        for key in ("MSTF", "MSUF"):
            near(f"summary {key}", summary[0][key], 1 if ADVANCE else 5 / 6)
        ck("summary horizon", summary[0]["RTIUP"], 60)
        systems = table_rows(report, "SystemResults")
        stocks = table_rows(report, "StockTotalResults")
        ck("120 System and Stock bins", (len(systems), len(stocks)), (120, 120))
        ck("System boundaries", [(r["STINT"], r["ETINT"]) for r in systems], [(i / 2, (i + 1) / 2) for i in range(120)])
        ck("Stock boundaries", [(r["STINT"], r["ETINT"]) for r in stocks], [(i / 2, (i + 1) / 2) for i in range(120)])
        ck("report PM initiation marker", [r["STINT"] for r in systems if r["NPMS"]], [25])
        ck("report PM completion marker", [r["STINT"] for r in systems if r["NPMT"]], [PM_WORK_END])
        for i, (s, st) in enumerate(zip(systems, stocks, strict=True)):
            a, b = i / 2, (i + 1) / 2
            flying = fraction(a, b, FLIGHTS)
            pm = fraction(a, b, [(PM_WORK_START, PM_WORK_END)])
            assigned = fraction(a, b, ASSIGNED)
            near(f"bin {i} flight occupancy", s["NSYMO"], flying)
            near(f"bin {i} PM occupancy", s["NSYPM"], pm)
            near(f"bin {i} PM unready", s["NSYUA"], pm)
            near(f"bin {i} mission assigned", s["NSYMA"], assigned)
            near(f"bin {i} ready", s["NSYRY"], 1 - assigned - pm)
            near(f"bin {i} available", s["NSYA"], 1 - pm)
            near(f"bin {i} backorder", st["NBO"], 0)
            near(f"bin {i} stock demand", st["NDF"], 0)
            near(f"bin {i} PNB baseline", st["PNB"], 1)
            for key in ("NFAIL", "NREPT", "NDAM"):
                near(f"bin {i} {key}", s[key], 0)
        near("flight aircraft-hours", sum(s["NSYMO"] * .5 for s in systems), 9 if ADVANCE else 8)
        near("PM aircraft-hours", sum(s["NSYPM"] * .5 for s in systems), 1)
        ck("terminal ready", (systems[-1]["NSYRY"], systems[-1]["NSYPM"], stocks[-1]["NBO"]), (1, 0, 0))
    except Exception as exc:
        checks.append({"name": "replay exception", "passed": False, "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})
    result = {"schema": "simlox-d11-dtim-author-readonly/v1", "case_id": "D11", "variant_id": "D11.var02",
              "run_id": run.name, "passed": all(c["passed"] for c in checks), "checks_count": len(checks),
              "failures": [c for c in checks if not c["passed"]], "source_sha256": INPUT_SHA,
              "publication_state": "not_published"}
    out = HERE / "review" / "author-validation-2026-10-01.json"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "failures": result["failures"]}, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()

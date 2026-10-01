"""Author read-only replay of a sealed D11.var03 ENREG native run."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas, table_rows  # noqa: E402

CONFIG = {
    "D11-var03-enreg-drift-v1.0.0": ("D03-calendar-pm-v1.0.0", "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32", "61643f14212e7195437da7d95da91458472b29ac65555287cf968c66aee61bb1", False, False, 50.5),
    "D11-var03-enreg-regular-v1.0.0": ("D11-var03-enreg-drift-v1.0.0", "61643f14212e7195437da7d95da91458472b29ac65555287cf968c66aee61bb1", "3e64d0d817e1185cc95f826f0c5940bbfcf1bb9ee3f7af79d2046b91e11a2370", False, True, 48.0),
    "D11-var03-enreg-long-drift-v1.0.0": ("D03-calendar-pm-v1.0.0", "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32", "76836c8b1dd8f9d5552e9fb908b766e80995bc9fdcd7b7967f75a73de6f6b7c5", True, False, 74.5),
    "D11-var03-enreg-long-regular-v1.0.0": ("D11-var03-enreg-long-drift-v1.0.0", "76836c8b1dd8f9d5552e9fb908b766e80995bc9fdcd7b7967f75a73de6f6b7c5", "a7f41c9e202c136760ea22c67aecf5abe52a55331c60590694ca012521a34f30", True, True, 72.0),
}
PARENT_NAME, PARENT_SHA, INPUT_SHA, LONG, REGULAR, SECOND_PM = CONFIG[HERE.name]
PARENT = HERE.parent / PARENT_NAME / "native-input.json"
HORIZON = 84 if LONG else 60
FLIGHTS = [(8, 10), (20, 22), (23.5, 49.5 if LONG else 25.5)]
ASSIGNED = [(7, 10), (19, 22), (22.5, 49.5 if LONG else 25.5)]
FIRST_PM = 49.5 if LONG else 25.5
PM_SPANS = [(FIRST_PM, FIRST_PM + 1), (SECOND_PM, SECOND_PM + 1)]


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
        ck("input SHA", sha(HERE / "native-input.json"), INPUT_SHA)
        ck("copied input SHA", sha(run / "input.json"), INPUT_SHA)
        ck("contract pins", (contract["input_sha256"], contract["parent_input_sha256"]), (INPUT_SHA, PARENT_SHA))
        ck("manual SHA", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")), "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3")
        ck("dictionary SHA", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")), "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0")
        ck("executable SHA", sha(Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")), "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0")
        ck("run identity", (invocation["case_id"], invocation["run_id"], invocation["input_sha256"], invocation["parent_sha256"]), ("D11", run.name, INPUT_SHA, PARENT_SHA))
        ck("SSH context", (invocation["session_id"], invocation["ssh_connection_present"], "sshd.exe" in invocation["ssh_ancestor_names"]), (0, True, True))
        ck("GUI identity", (invocation["gui"]["pid"], invocation["gui"]["session_id"]), (13340, 1))
        ck("host-wide queue", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        ck("five steps", [s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"])
        ck("steps and GUI", all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), True)
        ck("roundtrip passed", roundtrip["passed"], True)
        ck("18 populated tables", len(roundtrip["populated_tables"]), 18)
        ck("closure error", closure["error"], None)
        ck("invocation seal", closure["invocation_sha256"], sha(run / "invocation.json"))
        ck("source stable", closure["source_hashes_after"], closure["source_hashes_before"])
        ck("source pin input", closure["source_hashes_before"]["input"], INPUT_SHA)
        ck("source pin parent", closure["source_hashes_before"]["parent"], PARENT_SHA)
        ck("source pin contract", closure["source_hashes_before"]["contract"], sha(HERE / "contract.json"))
        ck("raw count", len(closure["raw"]), 12)
        for name, seal in sorted(closure["raw"].items()):
            ck(f"raw seal {name}", (sha(run / name), (run / name).stat().st_size), (seal["sha256"], seal["bytes"]))
        ck("zero conversion errors and expected warnings", ("Errors: 0, Warnings: 2, Notes: 0" in calc,
            "warning #108" in calc, "warning #126" in calc), (True, True, True))
        ck("nonempty SXO", (run / "model.sxo").stat().st_size > 4, True)

        def times(pattern: str) -> list[float]:
            return [float(x) for x in re.findall(pattern, log, re.MULTILINE)]

        ck("mission starts", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|LONG-MISSION),[^\n]+> mission starting, duration: (?:2|26) : <TEACH-AIR-01,0>$"), [a for a, _ in FLIGHTS])
        ck("mission completions", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|LONG-MISSION),[^\n]+> mission completed: <TEACH-AIR-01,0>$"), [b for _, b in FLIGHTS])
        ck("mission successes", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|LONG-MISSION),[^\n]+> mission success: $"), [b for _, b in FLIGHTS])
        ck("no cancel/abort", bool(re.search(r"mission (?:cancelled|canceled|aborted)", log, re.I)), False)
        ck("two PM task starts", times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started$"), [FIRST_PM, SECOND_PM])
        ck("two CAL24 identities", len(re.findall(r"^Time: [\d.]+  system PM task \d+ on <TEACH-AIR-01,0> PMID: CAL24$", log, re.MULTILINE)), 2)
        ck("two PM task ends", times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed$"), [FIRST_PM + 1, SECOND_PM + 1])
        ck("PM work starts", times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours$"), [FIRST_PM, SECOND_PM])
        ck("PM work ends", times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> completed$"), [FIRST_PM + 1, SECOND_PM + 1])
        ck("no catch-up task at 48 after long delay", ("Time: 48  system PM task" in log), False if LONG else REGULAR)
        ck("no failure", bool(re.search(r"failure (?:occurred|identified|generated)", log, re.I)), False)
        summary = table_rows(report, "ResultSummary")
        ck("one summary", len(summary), 1)
        for key in ("MTMF", "MSTF", "MSUF", "STMF"):
            near(f"summary {key}", summary[0][key], 1)
        ck("summary horizon", summary[0]["RTIUP"], HORIZON)
        systems, stocks = table_rows(report, "SystemResults"), table_rows(report, "StockTotalResults")
        ck("System/Stock bin counts", (len(systems), len(stocks)), (2 * HORIZON, 2 * HORIZON))
        ck("System boundaries", [(r["STINT"], r["ETINT"]) for r in systems], [(i / 2, (i + 1) / 2) for i in range(2 * HORIZON)])
        ck("Stock boundaries", [(r["STINT"], r["ETINT"]) for r in stocks], [(i / 2, (i + 1) / 2) for i in range(2 * HORIZON)])
        ck("PM initiation markers", [r["STINT"] for r in systems if r["NPMS"]], [24, SECOND_PM])
        ck("PM completion markers", [r["STINT"] for r in systems if r["NPMT"]], [FIRST_PM + 1, SECOND_PM + 1])
        for i, (s, st) in enumerate(zip(systems, stocks, strict=True)):
            a, b = i / 2, (i + 1) / 2
            flying, pm, assigned = fraction(a, b, FLIGHTS), fraction(a, b, PM_SPANS), fraction(a, b, ASSIGNED)
            near(f"bin {i} flight", s["NSYMO"], flying)
            near(f"bin {i} PM", s["NSYPM"], pm)
            near(f"bin {i} PM unready", s["NSYUA"], pm)
            near(f"bin {i} assigned", s["NSYMA"], assigned)
            near(f"bin {i} ready", s["NSYRY"], 1 - assigned - pm)
            near(f"bin {i} available", s["NSYA"], 1 - pm)
            near(f"bin {i} backorder", st["NBO"], 0)
            near(f"bin {i} stock demand", st["NDF"], 0)
            near(f"bin {i} PNB baseline", st["PNB"], 1)
            for key in ("NFAIL", "NREPT", "NDAM"):
                near(f"bin {i} {key}", s[key], 0)
        near("flight hours", sum(s["NSYMO"] * .5 for s in systems), 30 if LONG else 6)
        near("PM hours", sum(s["NSYPM"] * .5 for s in systems), 2)
        ck("terminal ready/no PM/no backorder", (systems[-1]["NSYRY"], systems[-1]["NSYPM"], stocks[-1]["NBO"]), (1, 0, 0))
    except Exception as exc:
        checks.append({"name": "replay exception", "passed": False, "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})
    result = {"schema": "simlox-d11-enreg-author-readonly/v1", "case_id": "D11", "variant_id": "D11.var03",
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

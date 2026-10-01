"""Author read-only replay of the sealed ATIM=1 acceptance run."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas, table_rows  # noqa: E402

PARENT = HERE.parent / "D11-var01-atim-control-v1.0.0" / "native-input.json"
PARENT_SHA = "94c0addbaff610b656b25dd328949ea9710ab9a593cafebe488f7bfca665ead8"
INPUT_SHA = "babd0a2b2d196eca238c647f645c63961e1410e511fe16e5f84d21b33e1d8c96"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
DICTIONARY_SHA = "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
RUN_ID = "d11-atim-one-v100-ssh-20261001-02"
FLIGHTS = [(8, 12), (16, 17), (20, 21), (48, 49), (52, 53)]
ASSIGNED = [(7, 12), (15, 17), (19, 21), (47, 49), (51, 53)]
PM_STARTS = [12, 13, 14, 15, 18, 19, *range(22, 48), 50, 51, *range(54, 61)]
PM_ENDS = [13, 14, 15, 18, 19, *range(22, 48), 50, 51, *range(54, 61)]
PM_WORK = [(12, 15), (17, 19), (21, 47), (49, 51), (53, 60)]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    run = Path(sys.argv[1]).resolve()
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected, "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float, tol: float = 3e-5) -> None:
        checks.append({"name": name, "passed": abs(actual - expected) <= tol,
                       "actual": actual, "expected": expected, "tolerance": tol})

    try:
        contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
        invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
        roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
        report = json.loads(remove_trailing_commas((run / "report-raw.json").read_bytes()))
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck("run ID", run.name, RUN_ID)
        ck("parent SHA", sha(PARENT), PARENT_SHA)
        ck("input SHA", sha(HERE / "native-input.json"), INPUT_SHA)
        ck("copied input SHA", sha(run / "input.json"), INPUT_SHA)
        ck("contract pins", (contract["input_sha256"], contract["parent_input_sha256"]), (INPUT_SHA, PARENT_SHA))
        ck("installed manual SHA", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")), MANUAL_SHA)
        ck("installed dictionary SHA", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")), DICTIONARY_SHA)
        ck("installed executable SHA", sha(Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")), EXE_SHA)
        ck("native identity", (invocation["case_id"], invocation["run_id"], invocation["input_sha256"], invocation["parent_sha256"]),
           ("D11", RUN_ID, INPUT_SHA, PARENT_SHA))
        ck("SSH session and ancestor", (invocation["session_id"], invocation["ssh_connection_present"],
                                         "sshd.exe" in invocation["ssh_ancestor_names"]), (0, True, True))
        ck("host queue", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        ck("GUI identity", (invocation["gui"]["pid"], invocation["gui"]["session_id"]), (13340, 1))
        ck("five successful guarded steps", len(steps) == 5 and all(s["status"] == "completed" and s["exit_code"] == 0
                                                             and s["gui_preserved"] for s in steps), True)
        ck("roundtrip", (roundtrip["passed"], len(roundtrip["populated_tables"])), (True, 18))
        ck("closure error", closure["error"], None)
        ck("invocation seal", closure["invocation_sha256"], sha(run / "invocation.json"))
        ck("source pins stable", closure["source_hashes_after"], closure["source_hashes_before"])
        ck("source pins", (closure["source_hashes_before"]["input"], closure["source_hashes_before"]["parent"],
                            closure["source_hashes_before"]["contract"]),
           (INPUT_SHA, PARENT_SHA, sha(HERE / "contract.json")))
        ck("raw artifact count", len(closure["raw"]), 12)
        for name, seal in sorted(closure["raw"].items()):
            ck(f"raw seal {name}", (sha(run / name), (run / name).stat().st_size),
               (seal["sha256"], seal["bytes"]))
        ck("zero conversion errors and expected warnings", ("Errors: 0, Warnings: 2, Notes: 0" in calc,
             "warning #108" in calc, "warning #126" in calc), (True, True, True))
        ck("nonempty SXO", (run / "model.sxo").stat().st_size > 4, True)

        def times(pattern: str) -> list[float]:
            return [float(x) for x in re.findall(pattern, log, re.MULTILINE)]

        ck("mission starts", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|SHORT-MISSION),[^\n]+> mission starting, duration: [14] : <TEACH-AIR-01,0>$"), [a for a, _ in FLIGHTS])
        ck("mission completions", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|SHORT-MISSION),[^\n]+> mission completed: <TEACH-AIR-01,0>$"), [b for _, b in FLIGHTS])
        ck("mission successes", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|SHORT-MISSION),[^\n]+> mission success: $"), [b for _, b in FLIGHTS])
        ck("no abort/cancel", bool(re.search(r"mission (?:aborted|cancelled|canceled)", log, re.I)), False)
        ck("PM task starts", times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started$"), PM_STARTS)
        ck("PM identity count", len(re.findall(r"^Time: [\d.]+  system PM task \d+ on <TEACH-AIR-01,0> PMID: MS4$", log, re.MULTILINE)), 41)
        ck("PM task completions", times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed$"), PM_ENDS)
        ck("PM pauses", times(r"^Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> system PM task \d+ on <TEACH-AIR-01,0> paused\.$"), [15, 19, 47, 51])
        ck("PM continuations", times(r"^Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> system PM task \d+ on <TEACH-AIR-01,0> continued $"), [17, 21, 49, 53])
        ck("PM subtask work starts", times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours$"),
           [12, 13, 14, 17, 18, 21, *range(22, 47), 49, 50, 53, *range(54, 61)])
        ck("PM subtask completions", times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> completed$"), PM_ENDS)
        summary = table_rows(report, "ResultSummary")
        ck("one summary row", len(summary), 1)
        for key in ("MTMF", "MSTF", "MSUF", "STMF"):
            near(f"summary {key}", summary[0][key], 1)
        ck("summary horizon", summary[0]["RTIUP"], 60)
        systems = table_rows(report, "SystemResults")
        stocks = table_rows(report, "StockTotalResults")
        ck("120 System/Stock bins", (len(systems), len(stocks)), (120, 120))
        for i, (s, st) in enumerate(zip(systems, stocks, strict=True)):
            t = i / 2
            assigned = any(a <= t < b for a, b in ASSIGNED)
            flying = any(a <= t < b for a, b in FLIGHTS)
            pm = any(a <= t < b for a, b in PM_WORK)
            near(f"bin {i} start", s["STINT"], t)
            near(f"bin {i} end", s["ETINT"], t + .5)
            near(f"stock bin {i} start", st["STINT"], t)
            near(f"stock bin {i} end", st["ETINT"], t + .5)
            near(f"bin {i} mission", s["NSYMO"], float(flying))
            near(f"bin {i} PM work", s["NSYPM"], float(pm))
            near(f"bin {i} PM unready", s["NSYUA"], float(pm))
            near(f"bin {i} assigned", s["NSYMA"], float(assigned))
            near(f"bin {i} ready", s["NSYRY"], float(not (assigned or pm)))
            near(f"bin {i} available", s["NSYA"], float(not pm))
            near(f"bin {i} NBO", st["NBO"], 0)
            near(f"bin {i} NDF", st["NDF"], 0)
            near(f"bin {i} PNB", st["PNB"], 1)
            for key in ("NFAIL", "NREPT", "NDAM"):
                near(f"bin {i} {key}", s[key], 0)
        near("flight hours", sum(s["NSYMO"] * .5 for s in systems), 8)
        near("PM hours", sum(s["NSYPM"] * .5 for s in systems), 40)
        ck("terminal active PM", (systems[-1]["NSYRY"], systems[-1]["NSYPM"], stocks[-1]["NBO"]), (0, 1, 0))
    except Exception as exc:
        checks.append({"name": "replay exception", "passed": False, "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})
    result = {"schema": "simlox-d11-atim-one-author-readonly/v1", "case_id": "D11", "variant_id": "D11.var01",
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

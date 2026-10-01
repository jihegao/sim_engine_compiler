"""Author replay of a sealed related-PM MNOCC branch; no native execution."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas, table_rows  # noqa: E402

PARENT = HERE.parent / "D10-var01-missions-v1.0.0" / "native-input.json"
PARENT_SHA = "6607991260e3f911d0121c7949443409a57937e95f80c7e4f3a2faa6ac20ba72"
INPUT_SHAS = {
    2: "1c724ffacc4d0a443520e91e882af1598062ce2d672913b32e278dfe62bdcb94",
    3: "685b556d620c616eab3df02c34e160349f6cf4d7038a7085ff6394ba3c470ed9",
}
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
DICTIONARY_SHA = "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
POPULATED = 18
ALL_PM_STARTS = [17.0, 21.0, 53.0]
ALL_PM_ENDS = [18.0, 22.0, 54.0]
ALL_REPORT_PM_MARKERS = [17.0, 21.0, 53.0]
ALL_PM_IDS = ["MS2", "MS3", "MS2"]
MISSION_SPANS = [(8.0, 12.0), (16.0, 17.0), (20.0, 21.0), (48.0, 49.0), (52.0, 53.0)]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    run = Path(sys.argv[1]).resolve()
    limit = int(sys.argv[2])
    if limit not in INPUT_SHAS or run.name != f"d11-mnocc-related-{limit}-v100-ssh-20261001-02":
        raise ValueError("run ID and limit mismatch")
    input_sha = INPUT_SHAS[limit]
    pm_starts = ALL_PM_STARTS[:limit]
    pm_ends = ALL_PM_ENDS[:limit]
    report_pm_markers = ALL_REPORT_PM_MARKERS[:limit]
    pm_ids = ALL_PM_IDS[:limit]
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
        ck("parent SHA", sha(PARENT), PARENT_SHA)
        ck("frozen input SHA", sha(HERE / f"native-related-cap-{limit}.json"), input_sha)
        ck("copied run input SHA", sha(run / "input.json"), input_sha)
        ck("contract source pins", (contract["input_sha256"][f"MS2_MNOCC={limit}"], contract["parent_input_sha256"]),
           (input_sha, PARENT_SHA))
        ck("installed manual SHA", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")), MANUAL_SHA)
        ck("installed dictionary SHA", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")), DICTIONARY_SHA)
        ck("installed executable SHA", sha(Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")), EXE_SHA)
        ck("run identity", (invocation["case_id"], invocation["run_id"], invocation["input_sha256"], invocation["parent_sha256"]),
           ("D11", run.name, input_sha, PARENT_SHA))
        ck("SSH context", (invocation["session_id"], invocation["ssh_connection_present"],
                           "sshd.exe" in invocation["ssh_ancestor_names"]), (0, True, True))
        ck("GUI identity", (invocation["gui"]["pid"], invocation["gui"]["session_id"]), (13340, 1))
        ck("host-wide queue", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        ck("steps", [x["name"] for x in steps],
           ["import", "export", "calc", "jsonreport", "check_import_export"])
        ck("five successful guarded steps", all(x["status"] == "completed" and x["exit_code"] == 0
                                                 and x["gui_preserved"] for x in steps), True)
        ck("roundtrip passed", roundtrip["passed"], True)
        ck("roundtrip populated tables", len(roundtrip["populated_tables"]), POPULATED)
        ck("closure has no error", closure["error"], None)
        ck("invocation seal", closure["invocation_sha256"], sha(run / "invocation.json"))
        ck("source pins remained fixed", closure["source_hashes_after"], closure["source_hashes_before"])
        ck("source pin input", closure["source_hashes_before"]["input"], input_sha)
        ck("source pin parent", closure["source_hashes_before"]["parent"], PARENT_SHA)
        ck("source pin contract", closure["source_hashes_before"]["contract"], sha(HERE / "contract.json"))
        ck("raw count", len(closure["raw"]), 12)
        for name, seal in sorted(closure["raw"].items()):
            ck(f"raw seal {name}", (sha(run / name), (run / name).stat().st_size),
               (seal["sha256"], seal["bytes"]))
        ck("conversion errors and expected warnings",
           ("Errors: 0, Warnings: 2, Notes: 0" in calc, "warning #108" in calc,
            "warning #126" in calc), (True, True, True))
        ck("nonempty native SXO", (run / "model.sxo").stat().st_size > 4, True)

        def times(pattern: str) -> list[float]:
            return [float(x) for x in re.findall(pattern, log, flags=re.MULTILINE)]

        ck("mission start events", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|SHORT-MISSION),[^\n]+> mission starting, duration: [14] : <TEACH-AIR-01,0>$"),
           [x[0] for x in MISSION_SPANS])
        ck("mission completion events", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|SHORT-MISSION),[^\n]+> mission completed: <TEACH-AIR-01,0>$"),
           [x[1] for x in MISSION_SPANS])
        ck("mission success events", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|SHORT-MISSION),[^\n]+> mission success: $"),
           [x[1] for x in MISSION_SPANS])
        ck("PM starts", times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started$"), pm_starts)
        ck("PM identity sequence", re.findall(r"^Time: [\d.]+  system PM task \d+ on <TEACH-AIR-01,0> PMID: (MS[23])$", log, re.MULTILINE), pm_ids)
        ck("PM ends", times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed$"), pm_ends)
        ck("PM subtask starts", times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours$"), pm_starts)
        ck("PM subtask ends", times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> completed$"), pm_ends)
        ck("no mission abort/cancel", bool(re.search(r"mission (?:aborted|cancelled|canceled)", log, re.I)), False)
        ck("no failure event", bool(re.search(r"failure (?:occurred|identified|generated)", log, re.I)), False)
        summary = table_rows(report, "ResultSummary")
        ck("one successful summary", len(summary), 1)
        for key in ("MTMF", "MSTF", "MSUF", "STMF"):
            near(f"summary {key}", summary[0][key], 1.0)
        ck("summary horizon", summary[0]["RTIUP"], 60)
        systems = table_rows(report, "SystemResults")
        stocks = table_rows(report, "StockTotalResults")
        ck("120 System and Stock bins", (len(systems), len(stocks)), (120, 120))
        ck("System bin boundaries", [(r["STINT"], r["ETINT"]) for r in systems],
           [(i / 2, (i + 1) / 2) for i in range(120)])
        ck("Stock bin boundaries", [(r["STINT"], r["ETINT"]) for r in stocks],
           [(i / 2, (i + 1) / 2) for i in range(120)])
        ck("report PM start markers", [r["STINT"] for r in systems if r["NPMS"]], report_pm_markers)
        ck("report PM completion markers", [r["STINT"] for r in systems if r["NPMT"]], pm_ends)
        for i, (s, st) in enumerate(zip(systems, stocks, strict=True)):
            t = i / 2
            flying = any(a <= t < b for a, b in MISSION_SPANS)
            pm = any(a <= t < b for a, b in zip(pm_starts, pm_ends, strict=True))
            reserved = any(a - 1 <= t < b for a, b in MISSION_SPANS)
            near(f"bin {i} flight occupancy", s["NSYMO"], float(flying))
            near(f"bin {i} PM occupancy", s["NSYPM"], float(pm))
            near(f"bin {i} unready PM occupancy", s["NSYUA"], float(pm))
            near(f"bin {i} ready", s["NSYRY"], float(not (reserved or pm)))
            near(f"bin {i} available", s["NSYA"], float(not pm))
            near(f"bin {i} mission assigned", s["NSYMA"], float(reserved))
            near(f"bin {i} stock backorders", st["NBO"], 0)
            near(f"bin {i} stock demand", st["NDF"], 0)
            near(f"bin {i} PNB baseline", st["PNB"], 1)
            for key in ("NFAIL", "NREPT", "NDAM"):
                near(f"bin {i} {key}", s[key], 0)
        near("flight aircraft-hours", sum(s["NSYMO"] * 0.5 for s in systems), 8)
        near("PM aircraft-hours", sum(s["NSYPM"] * 0.5 for s in systems), len(pm_starts))
        ck("terminal ready and no active PM", (systems[-1]["NSYRY"], systems[-1]["NSYPM"], stocks[-1]["NBO"]), (1, 0, 0))
    except Exception as exc:
        checks.append({"name": "replay exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})
    result = {"schema": "simlox-d11-mnocc-related-author-readonly/v1", "case_id": "D11", "variant_id": "D11.var04", "mnocc": limit,
              "run_id": run.name, "passed": all(c["passed"] for c in checks),
              "checks_count": len(checks), "failures": [c for c in checks if not c["passed"]],
              "source_sha256": input_sha, "publication_state": "not_published"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    out = HERE / "review" / f"author-validation-related-{limit}-2026-10-01.json"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(raw)
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "failures": result["failures"]}, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()

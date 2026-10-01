"""Validate one G02.var01 native run against its fixed-seed event and ledger scope."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT_SHA = "5ef40eb302544e551282dd7dd3617a6ae160954f600dea605f26140ea551a19e"
PARENT_SHA = "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78"
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    source = path.read_text(encoding="utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for i, char in enumerate(source):
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
        elif char == "," and re.match(r"\s*[}\]]", source[i + 1:]):
            continue
        else:
            out.append(char)
    return json.loads("".join(out))


def records(report: dict, name: str) -> list[dict]:
    matches = [t for t in report["report"]["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"report table missing/duplicated: {name}")
    table = matches[0]
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def close(a: object, b: float, tolerance: float = 2e-5) -> bool:
    return isinstance(a, (int, float)) and math.isclose(float(a), b, rel_tol=0, abs_tol=tolerance)


def validate(run: Path) -> dict:
    checks: dict[str, bool] = {}

    def ck(name: str, value: bool) -> None:
        checks[name] = bool(value)

    invocation, closure, steps = (load(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
    source = invocation["source_hashes_before"]
    ck("exact_input", sha(run / "input.json") == sha(HERE / "native-input.json") == INPUT_SHA)
    ck("parent", source["parent"] == sha(HERE.parent / "D06-explicit-position-direct-repair-v1.0.0/native-input.json") == PARENT_SHA)
    ck("source_seals", source == closure["source_hashes_before"] == closure["source_hashes_after"]
       and source["input"] == INPUT_SHA and source["contract"] == sha(HERE / "contract.json")
       and source["builder"] == sha(HERE / "build.py")
       and source["checker"] == sha(HERE / "check_roundtrip.py")
       and source["runner_script"] == sha(HERE / "run_native_ssh.ps1"))
    ck("invocation_closure", closure["run_id"] == invocation["run_id"] == run.name
       and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None)
    ck("ssh_gui_queue", invocation["session_id"] == 0 and invocation["ssh_connection_present"]
       and "sshd.exe" in invocation["ssh_ancestor_names"]
       and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
       and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0)
    ck("five_steps", [s["name"] for s in steps] ==
       ["import", "export", "calc", "jsonreport", "check_import_export"]
       and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    ck("raw_seals", set(closure["raw"]) == RAW and all(
       (run / n).stat().st_size == entry["bytes"] and sha(run / n) == entry["sha256"]
       for n, entry in closure["raw"].items()))
    ck("roundtrip", load(run / "roundtrip-validation.json")["passed"] is True)
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("zero_conversion_errors", "Errors: 0, Warnings: 1, Notes: 0" in conversion
       and "(warning #108)" in conversion and (run / "model.sxo").stat().st_size > 4)
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    failures = [(float(t), mode, pos) for t, mode, pos in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,0> critical CM failure mode added, now\s+1 failures:\s+Failure Mode: (FM-POS-[AB]) on materiel: <(POS-[AB]),0>", log)]
    ck("position_specific_failures", len(failures) == 3
       and [(mode, pos) for _, mode, pos in failures] ==
       [("FM-POS-B", "POS-B"), ("FM-POS-B", "POS-B"), ("FM-POS-A", "POS-A")]
       and [round(t, 4) for t, _, _ in failures] == [8.6276, 20.8222, 33.0996])
    ck("mission_outcomes", log.count(" mission aborted:") == 3
       and " mission success:" not in log and "Time: 24  Start of day no 1" in log)
    starts = [(float(t), int(i), mode) for t, i, mode in re.findall(
        r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> FMID: (FM-POS-[AB])", log)]
    endings = [(float(t), int(i)) for t, i in re.findall(
        r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> completed", log)]
    ck("matching_direct_cm", len(starts) == len(endings) == 3
       and [i for _, i, _ in starts] == [0, 1, 2]
       and [mode for _, _, mode in starts] == [mode for _, mode, _ in failures]
       and all(i == j and close(end - start, 0.5, 1e-4)
               for (start, i, _), (end, j) in zip(starts, endings)))
    ck("terminal_event", "Time: 34.0996 <TEACH-AIR-01,BASE-01,0> System ready" in log)
    report = native(run / "report-raw.json")
    ck("report_tables", {t["name"] for t in report["report"]["tables"]} ==
       {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    summary = records(report, "ResultSummary")
    ck("summary", len(summary) == 1 and summary[0]["NREP"] == 1
       and close(summary[0]["RTIUP"], 36) and close(summary[0]["MTMF"], 0.6748974919))
    system, stock = records(report, "SystemResults"), records(report, "StockTotalResults")
    ck("aligned_bins", len(system) == len(stock) == 72 and all(
       close(r["STINT"], i * 0.5) and close(r["ETINT"], (i + 1) * 0.5)
       and close(stock[i]["STINT"], i * 0.5) and close(stock[i]["ETINT"], (i + 1) * 0.5)
       for i, r in enumerate(system)))
    ck("failure_repair_ledger", close(sum(r["NFAIL"] for r in system), 3)
       and close(sum(r["NREPT"] for r in system), 3)
       and close(sum(r["SYDT"] or 0 for r in system), 1.5)
       and close(0.5 * sum(r["NSYRP"] or 0 for r in system), 1.5))
    ck("stock_zero", all(close(r[k], 0) for r in stock
       for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")))
    ck("terminal_ready", close(system[-1]["NSYRY"], 1)
       and close(system[-1]["NSYRP"], 0) and close(system[-1]["NSYMO"], 0))
    return {"schema": "simlox-g02-var01-position-modes-author-validation/v1",
            "run_id": run.name, "passed": all(checks.values()), "checks": checks,
            "failures": [name for name, passed in checks.items() if not passed],
            "source_validator_sha256": sha(Path(__file__)), "closure_sha256": sha(run / "closure.json"),
            "report_sha256": sha(run / "report-raw.json"), "model_log_sha256": sha(run / "model.log"),
            "observed_failures": failures, "observed_cm_starts": starts, "observed_cm_ends": endings}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(args.run)
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.output:
        if args.output.exists() and args.output.read_bytes() != raw:
            raise ValueError("validation output already differs")
        args.output.write_bytes(raw)
    print(json.dumps({"passed": result["passed"], "checks": len(result["checks"]),
                      "failures": result["failures"], "run_id": result["run_id"]}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

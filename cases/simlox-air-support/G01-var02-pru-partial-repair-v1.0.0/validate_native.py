"""Read-only author replay for one frozen G01.var02 primary PRU branch."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G01-var03-du-discard-reorder-v1.0.0/native-input.json"
PARENT_SHA = "c409f4b210b9f60e5f36bf6b15f56aaba95f4b08b4f6b6de290b60d65086d7d9"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
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


def rows(doc: dict, name: str, namespace: str) -> list[dict]:
    matches = [t for t in doc[namespace]["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"missing or duplicate {name}")
    t = matches[0]
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row)) for inst in t["instances"] for row in inst["rows"]]


def validate(run: Path) -> dict:
    problems: list[str] = []
    checks = 0

    def ck(label: str, good: bool) -> None:
        nonlocal checks
        checks += 1
        if not good:
            problems.append(label)

    contract = load(HERE / "contract.json")
    input_sha = contract["native_input_sha256"]
    seed = contract["configuration"]["seed"]
    if seed not in ("1", "2"):
        raise ValueError("unsupported frozen seed")
    ck("contract and parent", contract["parent"]["input_sha256"] == PARENT_SHA and sha(PARENT) == PARENT_SHA)
    ck("frozen input", sha(HERE / "native-input.json") == sha(run / "input.json") == input_sha)
    invocation, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("invocation identity", invocation["case_id"] == "G01" and invocation["run_id"] == run.name)
    ck("invocation source", invocation["input_sha256"] == input_sha and invocation["parent_sha256"] == PARENT_SHA)
    for field, name in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"), ("checker_sha256", "check_roundtrip.py"), ("runner_script_sha256", "run_native_ssh.ps1")):
        ck(f"bound {name}", invocation[field] == sha(HERE / name))
    ck("native executable", invocation["simlox_exe_sha256"] == EXE_SHA)
    ck("session and queue", invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    ck("GUI identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    ck("closure", closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"])
    ck("raw set", set(closure["raw"]) == RAW)
    for name, record in closure["raw"].items():
        p = run / name
        ck(f"sealed {name}", p.is_file() and p.stat().st_size == record["bytes"] and sha(p) == record["sha256"])
    ck("five guarded steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    roundtrip = load(run / "roundtrip-validation.json")
    ck("22-table roundtrip", roundtrip["passed"] is True and roundtrip["differences"] == [] and len(roundtrip["populated_tables"]) == 22)
    exported = native(run / "roundtrip-raw.json")
    item = rows(exported, "Item", "model")
    ck("PRU item", len(item) == 1 and item[0]["IID"] == "TEACH-PRU-01" and item[0]["TYPE"] == "PRU")
    repair = rows(exported, "ItemRepair", "model")
    ck("partial repair", len(repair) == 1 and repair[0]["IID"] == "TEACH-PRU-01" and repair[0]["STID"] == "DEPOT-01" and repair[0]["DIRPT"] == 1 and repair[0]["DIRPF"] == 0.5)
    reorder = rows(exported, "ItemReorder", "model")
    ck("partial discard and lead", len(reorder) == 1 and reorder[0]["IID"] == "TEACH-PRU-01" and reorder[0]["STID"] == "DEPOT-01" and reorder[0]["DISCF"] == 0.5 and reorder[0]["LEADT"] == 1)
    ck("seed", rows(exported, "Control", "model")[0]["RSEED"] == seed)
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("zero conversion errors", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1}))
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    if seed == "1":
        ck("PRU 3 depot repair", "Time: 12.1667 <TEACH-PRU-01,0,DEPOT-01,0> Start repair of item <TEACH-PRU-01,0,3>" in log and "Time: 13.1667 <TEACH-PRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-PRU-01,0,3>" in log)
        ck("repaired individual returned", "Time: 13.1667 <TEACH-PRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-PRU-01,0,3> to stock" in log)
        ck("no discard or reorder", "Item discarded:" not in log and "reorder task" not in log)
        ck("base replenishment", "Time: 12 <TEACH-PRU-01,0,BASE-01,0> Replacement item arrives <TEACH-PRU-01,0,0>" in log)
    else:
        ck("PRU 3 depot discard", "Time: 23.4887 <TEACH-PRU-01,0,DEPOT-01,0> Item discarded: <TEACH-PRU-01,0,3>" in log)
        ck("discarded individual never repaired", not re.search(r"(?:Start repair of item|Finished repair of item|Put back replacement item) <TEACH-PRU-01,0,3>", log))
        ck("one-hour reorder", "Time: 23.4887 <TEACH-PRU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1" in log and "Time: 24.4887 <TEACH-PRU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1" in log)
        ck("new depot item", "Time: 24.4887 <TEACH-PRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-PRU-01,0,4>" in log)
        ck("later repair unfinished", "Time: 35.6549 <TEACH-PRU-01,0,DEPOT-01,0> Start repair of item <TEACH-PRU-01,0,5>" in log and "Finished repair of item <TEACH-PRU-01,0,5>" not in log)
    ck("system exchange", "remove subitem subtask" in log and "fit subitem subtask" in log and "System ready <TEACH-AIR-01,0>" in log)
    ck("no backorder event", "backorder" not in log.lower())
    report = native(run / "report-raw.json")
    summary = rows(report, "ResultSummary", "report")
    systems = rows(report, "SystemResults", "report")
    stocks = rows(report, "StockTotalResults", "report")
    expected_failures = 1 if seed == "1" else 2
    expected_msuf = 2 / 3 if seed == "1" else 1 / 3
    ck("summary", len(summary) == 1 and summary[0]["NREP"] == 1 and abs(summary[0]["MSUF"] - expected_msuf) < 1e-6)
    ck("system bins", len(systems) == 72 and all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(systems)))
    ck("stock bins", len(stocks) == 72 and all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(stocks)))
    ck("failures and system repairs", sum(row["NFAIL"] for row in systems) == expected_failures and sum(row["NREPT"] for row in systems) == expected_failures and systems[-1]["NSYRY"] == systems[-1]["NSYA"] == 1)
    ck("stock report", sum(row["NDF"] for row in stocks) == expected_failures and all(row["NBO"] == 0 for row in stocks))
    return {"schema": "simlox-g01-var02-pru-author-validation/v1", "case_id": "G01", "variant_id": "G01.var02", "run_id": run.name, "seed": seed, "passed": not problems, "checks": checks, "differences": problems, "input_sha256": input_sha, "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "publication_state": "not_published"}


if __name__ == "__main__":
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)

"""Read-only author replay for G01.var03 DU discard and depot reorder."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E01-local-spare-explicit-replacement-v1.0.0/native-input.json"
INPUT_SHA = "c409f4b210b9f60e5f36bf6b15f56aaba95f4b08b4f6b6de290b60d65086d7d9"
PARENT_SHA = "84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931"
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


def rows(doc: dict, name: str, namespace: str) -> list[dict]:
    matches = [t for t in doc[namespace]["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"missing or duplicate {name}")
    table = matches[0]
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, r)) for instance in table["instances"] for r in instance["rows"]]


def validate(run: Path) -> dict:
    differences = []
    checks = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            differences.append(label)

    contract = load(HERE / "contract.json")
    ck("frozen contract", contract["native_input_sha256"] == INPUT_SHA and contract["parent"]["input_sha256"] == PARENT_SHA)
    ck("source bytes", sha(HERE / "native-input.json") == sha(run / "input.json") == INPUT_SHA and sha(PARENT) == PARENT_SHA)
    invocation, closure, steps = (load(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck("invocation identity", invocation.get("case_id") == "G01" and invocation.get("case_version") == "1.0.0-candidate" and invocation.get("run_id") == run.name)
    ck("invocation source", invocation.get("input_sha256") == INPUT_SHA and invocation.get("parent_sha256") == PARENT_SHA)
    for field, name in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"), ("checker_sha256", "check_roundtrip.py"), ("runner_script_sha256", "run_native_ssh.ps1")):
        ck(f"bound {name}", invocation.get(field) == sha(HERE / name))
    ck("native executable", invocation.get("simlox_exe_sha256") == EXE_SHA)
    ck("session-0 SSH", invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") is True and "sshd.exe" in invocation.get("ssh_ancestor_names", []))
    ck("GUI identity and mutex", invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1 and invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue")
    ck("closure bound", closure.get("invocation_sha256") == sha(run / "invocation.json") and closure.get("error") is None)
    ck("source unchanged", closure.get("source_hashes_before") == closure.get("source_hashes_after") == invocation.get("source_hashes_before"))
    ck("raw set", set(closure.get("raw", {})) == RAW)
    for name, info in closure.get("raw", {}).items():
        p = run / name
        ck(f"sealed {name}", p.is_file() and p.stat().st_size == info.get("bytes") and sha(p) == info.get("sha256"))
    ck("five guarded stages", [x.get("name") for x in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(x.get("status") == "completed" and x.get("exit_code") == 0 and x.get("gui_preserved") is True for x in steps))
    roundtrip = load(run / "roundtrip-validation.json")
    ck("21-table roundtrip", roundtrip.get("passed") is True and roundtrip.get("differences") == [] and len(roundtrip.get("populated_tables", [])) == 21)
    exported = native(run / "roundtrip-raw.json")
    items = rows(exported, "Item", "model")
    ck("DU source type", len([r for r in items if r["IID"] == "TEACH-DU-01" and r["TYPE"] == "DU"]) == 1)
    ck("no DU repair row", not any(r["IID"] == "TEACH-DU-01" for r in rows(exported, "ItemRepair", "model")))
    ck("DU installed directly", rows(exported, "ItemStructure", "model")[0]["IID"] == "TEACH-DU-01" and rows(exported, "ItemStructure", "model")[0]["MID"] == "TEACH-AIR-01")
    ck("reorder station and lead", rows(exported, "ItemReorder", "model") == [{"IID": "TEACH-DU-01", "STID": "DEPOT-01", "LEADT": 1.0, "DISCF": None, "ORDSC": None, "ROINT": None, "REOPF": None, "MINRS": None, "MAXRS": None, "LEADTD": None, "NOTE": None}])
    ck("depot stock policy", any(r["IID"] == "TEACH-DU-01" and r["STID"] == "DEPOT-01" and r["STSIZ"] == 2 and r["ROSIZ"] == 1 for r in rows(exported, "StockAllocation", "model")))
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("zero conversion errors", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1}))
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    lines = log.splitlines()

    def one(fragment: str) -> bool:
        return sum(fragment in line for line in lines) == 1

    def ordered(*fragments: str) -> bool:
        positions = [[i for i, line in enumerate(lines) if frag in line] for frag in fragments]
        return all(len(p) == 1 for p in positions) and [p[0] for p in positions] == sorted(p[0] for p in positions)

    ck("one critical system failure", len(re.findall(r"^Time: [\d.]+ <TEACH-AIR-01,0> critical random failure added", log, re.M)) == 1)
    ck("installed DU failed", sum("subitem failed: <TEACH-DU-01,0,3> connection path: TEACH-AIR-01 - TEACH-AIR-01 - TEACH-DU-01" in line for line in lines) == 2)
    ck("local DU exchange", ordered("Time: 10 <TEACH-DU-01,0,BASE-01,0> Item demand arrives", "Time: 10 <TEACH-DU-01,0,BASE-01,0> Take replacement item <TEACH-DU-01,0,2> from stock", "Time: 10  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> started", "Time: 10.1667  fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> started", "Time: 10.5  system SURP task 0 on <TEACH-AIR-01,0> completed"))
    ck("failed DU discarded", one("Time: 10.1667 <TEACH-DU-01,0,BASE-01,0> Item discarded: <TEACH-DU-01,0,3>"))
    ck("no DU repair or restock", not re.search(r"item DIRP task \d+ on <TEACH-DU-01,0,3>|Put back replacement item <TEACH-DU-01,0,3>", log))
    ck("depot issue and reorder", ordered("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock", "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1", "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1", "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 1 item(s) arrives"))
    ck("individual stock conservation", one("Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,4>") and one("Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>") and "Stock at: <TEACH-DU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,4>," in log and "Stock at: <TEACH-DU-01,0,BASE-01,0> Level: 1 Items:<TEACH-DU-01,0,0>," in log)
    ck("missions and no backorder", sum("mission success:" in line for line in lines) == 2 and sum("mission aborted:" in line for line in lines) == 1 and "backorder" not in log.lower())
    report = native(run / "report-raw.json")
    summary = rows(report, "ResultSummary", "report")
    system = rows(report, "SystemResults", "report")
    stock = rows(report, "StockTotalResults", "report")
    ck("summary", len(summary) == 1 and summary[0]["NREP"] == 1 and abs(summary[0]["MSUF"] - 2 / 3) < 1e-6)
    ck("system bins", len(system) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(system)))
    ck("system result", sum(r["NFAIL"] for r in system) == 1 and sum(r["NREPT"] for r in system) == 1 and sum(r["NSYRP"] for r in system) == 1 and system[-1]["NSYRY"] == system[-1]["NSYA"] == 1)
    ck("stock bins", len(stock) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(stock)))
    ck("aggregate stock result", sum(r["NDF"] for r in stock) == 1 and all(r["NBO"] == 0 for r in stock))
    return {"schema": "simlox-g01-var03-du-v100-author-validation/v1", "case_id": "G01", "variant_id": "G01.var03", "run_id": run.name, "passed": not differences, "checks": checks, "differences": differences, "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "publication_state": "not_published"}


if __name__ == "__main__":
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)

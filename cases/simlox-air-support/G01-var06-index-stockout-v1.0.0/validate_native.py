"""Read-only author replay of one G01.var06 indexed similar-item stockout."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/g01-var06-stockout-v100-ssh-20261001-01"
PARENT = HERE.parent / "G01-var06-similar-vs-identical-v1.0.1/native-similar.json"
INPUT_SHA = "1f36f741513f21cf16a5c0a9665a670909fe2013ecf2d82cc6711ef00fda543a"
PARENT_SHA = "65f0d216cf30dddbda24d9a58617ef5049ccd520891363c6b3bba06161f6c472"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
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


def rows(doc: dict, name: str, root: str) -> list[dict]:
    t = next(t for t in doc[root]["tables"] if t["name"] == name)
    cols = [c["name"] for c in t["columns"]]
    return [dict(zip(cols, r)) for inst in t["instances"] for r in inst["rows"]]


def validate() -> dict:
    errors: list[str] = []
    count = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal count
        count += 1
        if not ok:
            errors.append(label)

    contract = load(HERE / "contract.json")
    ck("frozen source/parent", contract["native_input_sha256"] == sha(HERE / "native-input.json") == sha(RUN / "input.json") == INPUT_SHA and contract["parent"]["input_sha256"] == sha(PARENT) == PARENT_SHA)
    invocation, closure, steps = (load(RUN / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck("invocation identity", invocation.get("run_id") == RUN.name and invocation.get("case_id") == "G01" and invocation.get("case_version") == "1.0.0-candidate" and invocation.get("variant_id") == "G01.var06" and invocation.get("branch_kind") == "stockout")
    ck("source bound", invocation.get("input_sha256") == INPUT_SHA and invocation.get("parent_sha256") == PARENT_SHA)
    for field, file in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"), ("checker_sha256", "check_roundtrip.py"), ("runner_script_sha256", "run_native_ssh.ps1")):
        ck(f"bound {file}", invocation.get(field) == sha(HERE / file))
    ck("guarded session", invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") is True and "sshd.exe" in invocation.get("ssh_ancestor_names", []) and invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue" and invocation.get("simlox_exe_sha256") == EXE_SHA)
    ck("GUI preserved", invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1)
    ck("closure", closure.get("invocation_sha256") == sha(RUN / "invocation.json") and closure.get("error") is None and closure.get("source_hashes_before") == closure.get("source_hashes_after") == invocation.get("source_hashes_before"))
    ck("raw file set", set(closure.get("raw", {})) == RAW)
    for file, rec in closure.get("raw", {}).items():
        path = RUN / file
        ck(f"sealed {file}", path.is_file() and path.stat().st_size == rec.get("bytes") and sha(path) == rec.get("sha256"))
    ck("five guarded steps", [s.get("name") for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s.get("status") == "completed" and s.get("exit_code") == 0 and s.get("gui_preserved") is True for s in steps))
    rt = load(RUN / "roundtrip-validation.json")
    ck("20-table source roundtrip", rt.get("passed") is True and rt.get("differences") == [] and len(rt.get("populated_tables", [])) == 20)
    exported = native_json(RUN / "roundtrip-raw.json")
    item = rows(exported, "Item", "model")[0]
    structure = rows(exported, "ItemStructure", "model")[0]
    stock = rows(exported, "StockAllocation", "model")[0]
    repair = rows(exported, "ItemRepair", "model")[0]
    ck("exported stockout geometry", item["NSIMI"] == 2 and structure["QTYPM"] == 1 and stock["STSIZ"] == 1 and repair["DIRPT"] == 30)
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("clean conversion", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1}))
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("one spare in each indexed pool", "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log and "Stock at: <TEACH-LRU-01,1,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,1,1>" in log)
    failures = re.findall(r"^Time: ([\d.]+) <TEACH-AIR-01,0> critical random failure added, now\s+1 failures:\s+subitem failed: <TEACH-LRU-01,(\d+),(\d+)>", log, re.M)
    ck("two index-1 aircraft failures", failures == [("8.94145", "1", "2"), ("21.4698", "1", "3")])
    ck("first matching spare issued", "Time: 9.44145 <TEACH-LRU-01,1,BASE-01,0> Take replacement item <TEACH-LRU-01,1,1> from stock" in log and "Stock at: <TEACH-LRU-01,1,BASE-01,0> Level: 0 Items:" in log)
    ck("first repair extends beyond horizon", "Time: 9.60812  direct repair subtask 2 seqno 0 within item DIRP task 1 on <TEACH-LRU-01,1,2> starts performing, planned to last for 30 hours" in log and "item DIRP task 1 on <TEACH-LRU-01,1,2> completed" not in log)
    ck("second index-1 backorder", "Time: 21.9698 <TEACH-LRU-01,1,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,1,3>" in log and "Time: 21.9698 <TEACH-LRU-01,1,BASE-01,0> Backorder added" in log)
    ck("index-0 spare remains unused", len(re.findall(r"Stock at: <TEACH-LRU-01,0,BASE-01,0>", log)) == 1 and "Take replacement item <TEACH-LRU-01,0," not in log and "Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0," not in log)
    ck("no substitute issued to second demand", len(re.findall(r"Take replacement item <TEACH-LRU-01,\d+,\d+> from stock", log)) == 1 and "Backorders at: <TEACH-LRU-01,1,BASE-01,0> Nbr: 1" in log)
    ck("unfinished second repair and aircraft task", "Time: 22.1365  direct repair subtask 5 seqno 0 within item DIRP task 3 on <TEACH-LRU-01,1,3> starts performing, planned to last for 30 hours" in log and "fit subitem subtask 4 seqno 2 within system SURP task 2 on <TEACH-AIR-01,0> wait for subitem" in log and not re.search(r"^Time: [\d.]+  system SURP task 2 on <TEACH-AIR-01,0> completed", log, re.M))
    ck("mission outcomes", log.count("mission aborted:") == 2 and log.count("mission cancelled:") == 1 and "mission success:" not in log)
    report = native_json(RUN / "report-raw.json")
    summary, systems, stocks = (rows(report, n, "report") for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck("summary", len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["MSUF"] == 0)
    ck("system report", len(systems) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(systems)) and sum(r["NFAIL"] for r in systems) == 2 and sum(r["NREPT"] for r in systems) == 1 and systems[-1]["NSYRY"] == systems[-1]["NSYA"] == 0)
    ck("stock report terminal backorder", len(stocks) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(stocks)) and stocks[-1]["NBO"] == 1 and any(r["NBO"] > 0 for r in stocks))
    return {"schema": "simlox-g01-var06-index-stockout-v100-author-validation/v1", "case_id": "G01", "variant_id": "G01.var06", "passed": not errors, "checks": count, "differences": errors, "native_run_id": RUN.name, "input_sha256": INPUT_SHA, "model_log_sha256": sha(RUN / "model.log"), "report_sha256": sha(RUN / "report-raw.json"), "publication_state": "not_published"}


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)

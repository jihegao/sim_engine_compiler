"""Read-only author replay of paired G01.var06 native identity and stock routing."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E01-local-spare-explicit-replacement-v1.0.0/native-input.json"
PARENT_SHA = "84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
INPUTS = {
    "identical": ("native-identical.json", "fbec730d2279dfa501186101a64d061f21a580e8ce50ad4695fce2f454fa4347"),
    "similar": ("native-similar.json", "65f0d216cf30dddbda24d9a58617ef5049ccd520891363c6b3bba06161f6c472"),
}
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
    ck("contract/parent", contract["variant_id"] == "G01.var06" and contract["case_version"] == "1.0.1-candidate" and contract["parent"]["input_sha256"] == sha(PARENT) == PARENT_SHA)
    artifacts = {}
    for kind, (name, expected) in INPUTS.items():
        run = HERE / "runs" / f"g01-var06-{kind}-v101-ssh-20261001-01"
        ck(f"{kind} source", contract["native_inputs_sha256"][kind] == sha(HERE / name) == sha(run / "input.json") == expected)
        invocation, closure, steps = (load(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{kind} identity", invocation.get("run_id") == run.name and invocation.get("case_id") == "G01" and invocation.get("case_version") == "1.0.1-candidate" and invocation.get("variant_id") == "G01.var06" and invocation.get("branch_kind") == kind)
        ck(f"{kind} input/parent bound", invocation.get("input_sha256") == expected and invocation.get("parent_sha256") == PARENT_SHA)
        for field, file in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"), ("checker_sha256", "check_roundtrip.py"), ("runner_script_sha256", "run_native_ssh.ps1")):
            ck(f"{kind} bound {file}", invocation.get(field) == sha(HERE / file))
        ck(f"{kind} guarded", invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") is True and "sshd.exe" in invocation.get("ssh_ancestor_names", []) and invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue" and invocation.get("simlox_exe_sha256") == EXE_SHA)
        ck(f"{kind} GUI", invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1)
        ck(f"{kind} closure", closure.get("invocation_sha256") == sha(run / "invocation.json") and closure.get("error") is None and closure.get("source_hashes_before") == closure.get("source_hashes_after") == invocation.get("source_hashes_before"))
        ck(f"{kind} raw set", set(closure.get("raw", {})) == RAW)
        for file, record in closure.get("raw", {}).items():
            path = run / file
            ck(f"{kind} sealed {file}", path.is_file() and path.stat().st_size == record.get("bytes") and sha(path) == record.get("sha256"))
        ck(f"{kind} five steps", [s.get("name") for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s.get("status") == "completed" and s.get("exit_code") == 0 and s.get("gui_preserved") is True for s in steps))
        rt = load(run / "roundtrip-validation.json")
        ck(f"{kind} roundtrip", rt.get("passed") is True and rt.get("differences") == [] and len(rt.get("populated_tables", [])) == 20)
        exported = native_json(run / "roundtrip-raw.json")
        item = rows(exported, "Item", "model")[0]
        structure = rows(exported, "ItemStructure", "model")[0]
        stock = rows(exported, "StockAllocation", "model")[0]
        system = rows(exported, "System", "model")[0]
        ck(f"{kind} source geometry", item["NSIMI"] == (2 if kind == "similar" else None) and structure["QTYPM"] == (1 if kind == "similar" else 2) and stock["STSIZ"] == 2 and system["FRT"] == 600000)
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{kind} clean conversion", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1}))
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        failures = re.findall(r"^Time: ([\d.]+) <TEACH-AIR-01,0> critical random failure added, now\s+1 failures:\s+subitem failed: <TEACH-LRU-01,(\d+),(\d+)>", log, re.M)
        demand = re.findall(r"Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,(\d+),(\d+)>", log)
        issue = re.findall(r"Take replacement item <TEACH-LRU-01,(\d+),(\d+)> from stock", log)
        ck(f"{kind} three failure/demand/issue chains", len(failures) == len(demand) == len(issue) == 3 and [(g, i) for _, g, i in failures] == demand and [g for g, _ in demand] == [g for g, _ in issue])
        ck(f"{kind} distinct failed and issued physical ids", len({i for _, _, i in failures}) == 3 and len({i for _, i in issue}) == 3 and {i for _, _, i in failures}.isdisjoint({i for _, i in issue[:2]}))
        ck(f"{kind} missions/repair/no backorder", log.count("mission aborted:") == 3 and log.count("mission success:") == 0 and len(re.findall(r"^Time: [\d.]+  item DIRP task \d+ on <TEACH-LRU-01,\d+,\d+> completed", log, re.M)) == 3 and "backorder" not in log.lower())
        report = native_json(run / "report-raw.json")
        summary, systems, stocks = (rows(report, n, "report") for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{kind} summary", len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["MSUF"] == 0)
        ck(f"{kind} 72 system bins", len(systems) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(systems)) and sum(r["NFAIL"] for r in systems) == sum(r["NREPT"] for r in systems) == 3)
        ck(f"{kind} 72 stock bins", len(stocks) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 and r["NBO"] == 0 for i, r in enumerate(stocks)))
        artifacts[kind] = {"run": run.name, "failures": failures, "demand": demand, "issue": issue, "summary": summary, "systems": systems, "stocks": stocks, "log": log, "report_sha256": sha(run / "report-raw.json"), "model_log_sha256": sha(run / "model.log")}
    identical, similar = artifacts["identical"], artifacts["similar"]
    ck("paired failure times", [x[0] for x in identical["failures"]] == [x[0] for x in similar["failures"]] == ["8.94145", "21.4698", "32.9809"])
    ck("paired reports equal", all(identical[n] == similar[n] for n in ("summary", "systems", "stocks")))
    ck("identical one pool", "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 2 Items:<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,1>" in identical["log"] and "Stock at: <TEACH-LRU-01,1,BASE-01,0>" not in identical["log"] and [x[0] for x in identical["demand"]] == ["0", "0", "0"])
    ck("similar two pools", "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 2 Items:<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,1>" in similar["log"] and "Stock at: <TEACH-LRU-01,1,BASE-01,0> Level: 2 Items:<TEACH-LRU-01,1,2>,<TEACH-LRU-01,1,3>" in similar["log"] and [x[0] for x in similar["demand"]] == ["1", "1", "0"] and [x[0] for x in similar["issue"]] == ["1", "1", "0"])
    return {"schema": "simlox-g01-var06-v101-author-validation/v1", "case_id": "G01", "variant_id": "G01.var06", "passed": not errors, "checks": count, "differences": errors, "runs": {k: {n: v[n] for n in ("run", "failures", "demand", "issue", "report_sha256", "model_log_sha256")} for k, v in artifacts.items()}, "publication_state": "not_published"}


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)

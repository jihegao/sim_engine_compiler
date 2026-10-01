"""Read-only author acceptance replay for the bounded G01.var04 native run."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G01-var01-lru-sru-v1.0.1/native-input.json"
INPUT_SHA = "3bff001536557156d3b417c273065b8dfcc439d7e57dc626b20d635e12c83b14"
PARENT_SHA = "9c25a414615ac4ea523ee989385a913c692923e04bc41c6984b6866e86204bb9"
PARENT_RUN = HERE.parent / "G01-var01-lru-sru-v1.0.1/runs/g01-var01-v101-ssh-20261001-01"
PARENT_LOG_SHA = "2b022be07466fb1c8b47ac47b56980f4ee11c94720ec6305bf69181b73022217"
PARENT_REPORT_SHA = "20c6dab5e91903bcea8778a9b11b14a9b81d16fe281f53dcf9b11c36856c047a"
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


def report_rows(report: dict, name: str) -> list[dict]:
    tables = [t for t in report["report"]["tables"] if t["name"] == name]
    if len(tables) != 1:
        raise ValueError(f"missing/duplicate report {name}")
    table = tables[0]
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def validate(run: Path) -> dict:
    errors = []
    count = 0

    def ck(label: str, value: bool):
        nonlocal count
        count += 1
        if not value:
            errors.append(label)

    contract = load(HERE / "contract.json")
    ck("contract source and parent", contract["native_input_sha256"] == INPUT_SHA and contract["parent"]["input_sha256"] == PARENT_SHA)
    ck("frozen source and accepted parent", sha(HERE / "native-input.json") == INPUT_SHA and sha(PARENT) == PARENT_SHA)
    ck("run source", sha(run / "input.json") == INPUT_SHA)
    invocation, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("invocation case/run", invocation.get("case_id") == "G01" and invocation.get("run_id") == run.name)
    ck("invocation input/parent", invocation.get("input_sha256") == INPUT_SHA and invocation.get("parent_sha256") == PARENT_SHA)
    for field, name in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"), ("checker_sha256", "check_roundtrip.py"), ("runner_script_sha256", "run_native_ssh.ps1")):
        ck(f"bound {name}", invocation.get(field) == sha(HERE / name))
    ck("native executable", invocation.get("simlox_exe_sha256") == EXE_SHA)
    ck("guarded session 0", invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") is True and "sshd.exe" in invocation.get("ssh_ancestor_names", []))
    ck("original GUI", invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1)
    ck("global queue", invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue")
    ck("closure bound", closure.get("invocation_sha256") == sha(run / "invocation.json") and closure.get("error") is None)
    ck("source stable", closure.get("source_hashes_before") == closure.get("source_hashes_after") == invocation.get("source_hashes_before"))
    ck("sealed raw file set", set(closure.get("raw", {})) == RAW)
    for name, record in closure.get("raw", {}).items():
        path = run / name
        ck(f"sealed {name}", path.is_file() and path.stat().st_size == record.get("bytes") and sha(path) == record.get("sha256"))
    ck("five guarded steps", [s.get("name") for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s.get("status") == "completed" and s.get("exit_code") == 0 and s.get("gui_preserved") is True for s in steps))
    roundtrip = load(run / "roundtrip-validation.json")
    ck("roundtrip", roundtrip.get("passed") is True and roundtrip.get("differences") == [] and len(roundtrip.get("populated_tables", [])) == 21)
    exported = native_json(run / "roundtrip-raw.json")
    def table_rows(doc, name):
        table = next(t for t in doc["model"]["tables"] if t["name"] == name)
        return [dict(zip([c["name"] for c in table["columns"]], row)) for instance in table["instances"] for row in instance["rows"]]
    item_rows = table_rows(exported, "Item")
    assy = [row for row in item_rows if row["IID"] == "TEACH-ASSY-01"]
    ck("assembly has only identity and description", len(assy) == 1 and assy[0]["TYPE"] == "ASSY" and all(value is None for key, value in assy[0].items() if key not in {"IID", "DESCR", "TYPE"}))
    links = {(row["IID"], row["MID"]) for row in table_rows(exported, "ItemStructure")}
    ck("physical assembly hierarchy", links == {("TEACH-ASSY-01", "TEACH-AIR-01"), ("TEACH-LRU-01", "TEACH-ASSY-01"), ("TEACH-SRU-01", "TEACH-LRU-01")})
    ck("general LRU SURP time differs", table_rows(exported, "ItemRepair")[0]["IID"] == "TEACH-LRU-01" and table_rows(exported, "ItemRepair")[0]["SURPT"] == 1.5)
    replacement = table_rows(exported, "ItemReplacement")
    ck("direct logistic system-to-LRU route", len(replacement) == 2 and any(row["MID"] == "TEACH-AIR-01" and row["IID"] == "TEACH-LRU-01" and row["STID"] == "BASE-01" and row["SURPT"] == 0.5 and row["SURPTID"] == "E01-SURP" for row in replacement))
    ck("LRU-to-SRU route retained", any(row["MID"] == "TEACH-LRU-01" and row["IID"] == "TEACH-SRU-01" and row["SURPT"] == 0.75 for row in replacement))
    ck("assembly absent from logistics input", all(row["IID"] != "TEACH-ASSY-01" for name in ("ItemReplacement", "ItemRepair", "StockAllocation") for row in table_rows(exported, name)))
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("zero conversion errors", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1}))
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    lines = log.splitlines()
    ck("ASSY only in physical failure paths", sum("TEACH-ASSY-01" in line for line in lines) == 2 and all("connection path:" in line for line in lines if "TEACH-ASSY-01" in line))
    ck("no ASSY material events", not any("TEACH-ASSY-01" in line and any(token in line for token in ("Stock at:", "Item demand", "Take replacement", "Put back", "requiring maintenance")) for line in lines))
    def one(part):
        return sum(part in line for line in lines) == 1
    def ordered(*parts):
        positions = []
        for part in parts:
            found = [i for i, line in enumerate(lines) if part in line]
            if len(found) != 1:
                return False
            positions.append(found[0])
        return positions == sorted(positions)
    ck("one critical failure", len(re.findall(r"^Time: [\d.]+ <TEACH-AIR-01,0> critical random failure added", log, re.M)) == 1)
    ck("nested failed identity", one("Item requiring maintenance arrives <TEACH-LRU-01,0,2> from position <TEACH-AIR-01,BASE-01,0> subitem failed: <TEACH-SRU-01,0,3>"))
    ck("system spare and tasks", ordered("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Item demand arrives", "Take replacement item <TEACH-LRU-01,0,1> from stock", "Time: 10  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> started", "Time: 10.1667  fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> started", "Time: 10.5  system SURP task 0 on <TEACH-AIR-01,0> completed"))
    ck("system timing", one("Time: 10.1667  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed") and one("Time: 10.5  fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> completed"))
    ck("aircraft restored", one("Time: 10.5 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>"))
    ck("LRU/SRU demand and issue", ordered("Time: 10.1667  item SURP task 1 on <TEACH-LRU-01,0,2> started", "Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0> item requiring maintenance is <TEACH-SRU-01,0,3>", "Take replacement item <TEACH-SRU-01,0,0> from stock"))
    ck("LRU replacement timing", one("Time: 10.1667  remove subitem subtask 2 seqno 0 within item SURP task 1 on <TEACH-LRU-01,0,2> starts performing, planned to last for 0.375 hours") and one("Time: 10.5417  fit subitem subtask 3 seqno 1 within item SURP task 1 on <TEACH-LRU-01,0,2> starts performing, planned to last for 0.375 hours") and one("Time: 10.9167  item SURP task 1 on <TEACH-LRU-01,0,2> completed"))
    ck("SRU direct repair", ordered("Time: 10.5417  item DIRP task 2 on <TEACH-SRU-01,0,3> started", "Time: 11.5417  item DIRP task 2 on <TEACH-SRU-01,0,3> completed"))
    ck("repaired LRU/SRU restock", one("Time: 10.9167 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,2> to stock") and one("Time: 11.5417 <TEACH-SRU-01,0,BASE-01,0> Put back replacement item <TEACH-SRU-01,0,3> to stock"))
    ck("inventory level closure", "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,2>," in log and "Stock at: <TEACH-SRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-SRU-01,0,3>," in log and "backorder" not in log.lower())
    ck("mission sequence", one("mission aborted:") and sum("mission success:" in line for line in lines) == 2)
    report = native_json(run / "report-raw.json")
    summary, system, stock = (report_rows(report, name) for name in ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck("mission metrics", len(summary) == 1 and summary[0]["NREP"] == 1 and abs(summary[0]["MSUF"] - 2 / 3) < 1e-6)
    ck("system timeline", len(system) == 72 and all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(system)))
    ck("failure and restoration metrics", sum(r["NFAIL"] for r in system) == 1 and sum(r["NREPT"] for r in system) == 1 and sum(r["NSYRP"] for r in system) == 1 and system[-1]["NSYRY"] == system[-1]["NSYA"] == 1)
    ck("stock timeline and no outstanding", len(stock) == 72 and all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 and row["NBO"] == 0 for i, row in enumerate(stock)))
    ck("accepted parent raw fingerprints", sha(PARENT_RUN / "model.log") == PARENT_LOG_SHA and sha(PARENT_RUN / "report-raw.json") == PARENT_REPORT_SHA)
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("only ASSY added to event connection paths", log.replace(" - TEACH-ASSY-01", "") == parent_log)
    parent_report = native_json(PARENT_RUN / "report-raw.json")
    ck("parent business report unchanged", all(report_rows(report, name) == report_rows(parent_report, name) for name in ("ResultSummary", "SystemResults", "StockTotalResults")))
    return {"schema": "simlox-g01-var04-v100-author-validation/v1", "case_id": "G01", "variant_id": "G01.var04", "run_id": run.name, "passed": not errors, "checks": count, "differences": errors, "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "scope": "one_assy_wrapped_lru_sru_chain_cli_candidate", "publication_state": "not_published"}


if __name__ == "__main__":
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)

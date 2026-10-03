"""Author replay for the fixed-seed ACTIVE 1-of-2 NRLRQ crossing."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G10-var01-active-single-link-v1.0.0"
PARENT_RUN = PARENT / "runs/g10-var01-active-v100-ssh-20261003-01"
INPUT_SHA = "df9966f1bee58561b1bd54d05ced353abefc37efcd7559c47af5c63683aaa718"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "model_Prelife.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(doc: dict, root: str, name: str) -> list[dict]:
    table = next(t for t in doc[root]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def times(log: str, pattern: str) -> list[float]:
    return [float(x) for x in re.findall(r"^Time: ([\d.]+) " + pattern, log, re.M)]


def validate(run: Path) -> dict:
    errors: list[str] = []
    checks = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            errors.append(label)

    contract = load(HERE / "contract.json")
    ck("frozen input", sha(HERE / "native-input.json") == sha(run / "input.json") == contract["native_input_sha256"] == INPUT_SHA)
    ck("accepted parent", sha(PARENT / "native-input.json") == contract["parent"]["input_sha256"] and sha(PARENT_RUN / "closure.json") == contract["parent"]["native_closure_sha256"] and sha(PARENT / "cli-scope-signoff-2026-10-03.md") == contract["parent"]["signoff_sha256"])
    invocation, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("run identity", invocation.get("case_id") == "G10" and invocation.get("case_version") == "1.0.0-candidate" and invocation.get("run_id") == run.name)
    ck("source parent bound", invocation.get("input_sha256") == INPUT_SHA and invocation.get("parent_sha256") == contract["parent"]["input_sha256"])
    for key, path in (("contract", HERE / "contract.json"), ("builder", HERE / "build.py"), ("checker", HERE / "check_roundtrip.py"), ("runner_script", HERE / "run_native_ssh.ps1"), ("parent_signoff", PARENT / "cli-scope-signoff-2026-10-03.md"), ("parent_closure", PARENT_RUN / "closure.json"), ("manual", Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")), ("dictionary", Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"))):
        ck(f"bound source {key}", invocation["source_hashes_before"].get(key) == sha(path))
    ck("SSH0/queue/GUI", invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") is True and "sshd.exe" in invocation.get("ssh_ancestor_names", []) and invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue" and invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1)
    ck("clean closure", closure.get("error") is None and closure.get("invocation_sha256") == sha(run / "invocation.json") and closure.get("source_hashes_before") == closure.get("source_hashes_after") == invocation.get("source_hashes_before"))
    ck("complete raw set", set(closure["raw"]) == RAW)
    for name, seal in closure["raw"].items():
        path = run / name
        ck(f"sealed {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    ck("five native steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    rt = load(run / "roundtrip-validation.json")
    ck("22-table roundtrip", rt["passed"] and rt["differences"] == [] and len(rt["populated_tables"]) == 22)
    source, exported = (parse_native(path) for path in (HERE / "native-input.json", run / "roundtrip-raw.json"))
    ck("all populated business rows", all(populated(exported).get(name) == table for name, table in populated(source).items()))
    red = rows(exported, "model", "Redundancy")
    ck("ACTIVE one-of-two threshold", len(red) == 1 and red[0]["RLID"] == "TEACH-LRU-01" and red[0]["SID"] == "TEACH-AIR-01" and red[0]["NRL"] == 2 and red[0]["NRLRQ"] == 1 and red[0]["ACPA"] == "ACTIVE" and red[0]["TSWOV"] == 0)
    items = {r["IID"]: r for r in rows(exported, "model", "Item")}
    system = rows(exported, "model", "System")
    ck("matched traditional FRT hierarchy", len(system) == 1 and system[0]["FRT"] == 1800000 and all(items[i]["FRT"] == 900000 and items[i]["OPID"] == "OPHOURS" for i in ("TEACH-LRU-01", "TEACH-SRU-01")) and any(r["IID"] == "TEACH-LRU-01" and r["MID"] == "TEACH-AIR-01" and r["QTYPM"] == 2 for r in rows(exported, "model", "ItemStructure")))
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("clean conversion", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and len(re.findall(r"\(warning #108\)", runlog)) == 1 and len(re.findall(r"\(warning #\d+\)", runlog)) == 1 and "(error #" not in runlog)

    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    faults = re.findall(r"^Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) random failure added, now\s*\n(.*?)(?=^Time:|\Z)", log, re.M | re.S)
    expected = [(8.31382, "noncritical", (3,)), (9.56251, "critical", (3, 5)), (20.4287, "noncritical", (7,)), (20.4361, "critical", (7, 9)), (32.1791, "noncritical", (11,)), (32.4288, "critical", (11, 13))]
    observed = [(float(t), severity, tuple(int(x) for x in re.findall(r"subitem failed: <TEACH-LRU-01,0,(\d+)>", block))) for t, severity, block in faults]
    ck("six native link-fault states", len(observed) == len(expected) and all(abs(t-e) < .0001 and s == es and ids == ei for (t, s, ids), (e, es, ei) in zip(observed, expected)))
    ck("no repair before each second link failure", all(observed[i+1][0] < first_repair for i, first_repair in ((0, 10), (2, 20.8722), (4, 32.8576))))
    ck("three critical mission aborts", times(log, r"<BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission aborted:") == [9.56251, 20.4361, 32.4288] and "mission success:" not in log)
    ck("all three aborted missions return", times(log, r"<BASIC-MISSION,TEACH-UNIT,0,0,\d+> aborted mission completed:") == [10, 20.8722, 32.8576])
    starts = times(log, r" system SURP task \d+ on <TEACH-AIR-01,0> started")
    ends = times(log, r" system SURP task \d+ on <TEACH-AIR-01,0> completed")
    ck("two parallel half-hour system replacements per mission", starts == [10, 10, 20.8722, 20.8722, 32.8576, 32.8576] and ends == [10.5, 10.5, 21.3722, 21.3722, 33.3576, 33.3576])
    ck("partial then full system repair", times(log, r"<TEACH-AIR-01,BASE-01,0> System partially repaired") == [10.5, 21.3722, 33.3576] and times(log, r"<TEACH-AIR-01,BASE-01,0> System ready") == [10.5, 21.3722, 33.3576])
    ck("six LRU and three SRU stock issues", len(re.findall(r"Take replacement item <TEACH-LRU-01,0,\d+> from stock", log)) == 6 and len(re.findall(r"Take replacement item <TEACH-SRU-01,0,\d+> from stock", log)) == 3)
    ck("three SRU backorders clear", times(log, r"<TEACH-SRU-01,0,BASE-01,0> Backorder added") == [10.1667, 21.0388, 33.0243] and times(log, r"<TEACH-SRU-01,0,BASE-01,0> Backorder removed, waiting time was 1.375") == [11.5417, 22.4138, 34.3993])
    ck("all nested repairs complete", len(times(log, r" item SURP task \d+ on <TEACH-LRU-01,0,\d+> completed")) == 6 and len(times(log, r" item DIRP task \d+ on <TEACH-SRU-01,0,\d+> completed")) == 6)
    lru_levels = re.findall(r"Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: (\d+) Items:([^\n]*)", log)
    sru_levels = re.findall(r"Stock at: <TEACH-SRU-01,0,BASE-01,0> Level: (\d+) Items:([^\n]*)", log)
    ck("terminal physical stocks", lru_levels[-1][0] == "2" and "<TEACH-LRU-01,0,11>" in lru_levels[-1][1] and "<TEACH-LRU-01,0,13>" in lru_levels[-1][1] and sru_levels[-1][0] == "1" and "<TEACH-SRU-01,0,14>" in sru_levels[-1][1])

    report = parse_native(run / "report-raw.json")
    summary, systems, stocks = (rows(report, "report", name) for name in ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck("one repetition no successful missions", len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["MSUF"] == 0)
    ck("72 contiguous System bins", len(systems) == 72 and all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(systems)))
    ck("six failures and replacements", {i:r["NFAIL"] for i,r in enumerate(systems) if r["NFAIL"]} == {16:1,19:1,40:2,64:2} and {i:r["NREPT"] for i,r in enumerate(systems) if r["NREPT"]} == {21:2,42:2,66:2})
    ck("three downtime intervals", [i for i,r in enumerate(systems) if r["NSYDT"]] == [20,41,65] and sum(r["NSYDT"] for r in systems) == 3)
    ck("terminal aircraft ready", systems[-1]["NSYRY"] == systems[-1]["NSYA"] == 1 and systems[-1]["NSYRP"] == 0)
    ck("72 contiguous Stock bins", len(stocks) == 72 and all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i,r in enumerate(stocks)))
    ck("six aggregate system stock demands", {i:r["NDF"] for i,r in enumerate(stocks) if r["NDF"]} == {20:2,41:2,65:2} and {i:r["NWT"] for i,r in enumerate(stocks) if r["NWT"]} == {20:2,41:2,65:2})
    ck("aggregate Stock NBO distinct from SRU event backorders", all(r["NBO"] == 0 for r in stocks) and log.count("Backorder added") == 3)
    return {"schema": "simlox-g10-var03-v100-author-validation/v1", "case_id": "G10", "variant_id": "G10.var03", "run_id": run.name, "passed": not errors, "checks": checks, "differences": errors, "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "publication_state": "not_published"}


if __name__ == "__main__":
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)

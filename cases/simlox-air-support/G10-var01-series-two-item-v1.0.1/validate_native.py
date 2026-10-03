"""Author replay of the frozen two-item series-link native run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G10-var03-nrlrq-crossing-v1.0.0"
PARENT_RUN = PARENT / "runs/g10-var03-nrlrq-crossing-v100-ssh-20261003-01"
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
    input_sha = contract["native_input_sha256"]
    ck("frozen input", sha(HERE / "native-input.json") == sha(run / "input.json") == input_sha)
    ck("accepted parent", sha(PARENT / "native-input.json") == contract["parent"]["input_sha256"] and sha(PARENT_RUN / "closure.json") == contract["parent"]["native_closure_sha256"] and sha(PARENT / "cli-scope-signoff-2026-10-03.md") == contract["parent"]["signoff_sha256"])
    invocation, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("run identity", invocation.get("case_id") == "G10" and invocation.get("case_version") == "1.0.1-candidate" and invocation.get("run_id") == run.name)
    ck("source parent bound", invocation.get("input_sha256") == input_sha and invocation.get("parent_sha256") == contract["parent"]["input_sha256"])
    bound = (("contract", HERE / "contract.json"), ("builder", HERE / "build.py"), ("checker", HERE / "check_roundtrip.py"), ("runner_script", HERE / "run_native_ssh.ps1"), ("parent_signoff", PARENT / "cli-scope-signoff-2026-10-03.md"), ("parent_closure", PARENT_RUN / "closure.json"), ("manual", Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")), ("dictionary", Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")))
    for key, path in bound:
        ck(f"bound source {key}", invocation["source_hashes_before"].get(key) == sha(path))
    ck("SSH0/queue/GUI", invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") is True and "sshd.exe" in invocation.get("ssh_ancestor_names", []) and invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue" and invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1)
    ck("clean closure", closure.get("error") is None and closure.get("invocation_sha256") == sha(run / "invocation.json") and closure.get("source_hashes_before") == closure.get("source_hashes_after") == invocation.get("source_hashes_before"))
    ck("complete raw set", set(closure["raw"]) == RAW)
    for name, seal in closure["raw"].items():
        path = run / name
        ck(f"sealed {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    ck("five native steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    rt = load(run / "roundtrip-validation.json")
    ck("23-table roundtrip", rt["passed"] and rt["differences"] == [] and len(rt["populated_tables"]) == 23 and "RedundancyLink" in rt["populated_tables"])
    source, exported = (parse_native(path) for path in (HERE / "native-input.json", run / "roundtrip-raw.json"))
    ck("all populated business rows", all(populated(exported).get(name) == table for name, table in populated(source).items()))
    red = rows(exported, "model", "Redundancy")
    links = rows(exported, "model", "RedundancyLink")
    ck("ACTIVE 1-of-2 series", len(red) == 1 and red[0]["RLID"] == "G10-SER-LINK" and red[0]["SID"] == "TEACH-AIR-01" and red[0]["NRL"] == 2 and red[0]["NRLRQ"] == 1 and red[0]["ACPA"] == "ACTIVE" and red[0]["TSWOV"] == 0 and {(r["RLID"], r["IID"], r["QTYPL"]) for r in links} == {("G10-SER-LINK", "TEACH-LRU-01", 1), ("G10-SER-LINK", "TEACH-AUX-01", 1)})
    items = {r["IID"]: r for r in rows(exported, "model", "Item")}
    system = rows(exported, "model", "System")
    structure = rows(exported, "model", "ItemStructure")
    ck("physical quantity and mother FRT", len(system) == 1 and system[0]["FRT"] == 3600000 and all(items[i]["FRT"] == 900000 and items[i]["OPID"] == "OPHOURS" for i in ("TEACH-LRU-01", "TEACH-AUX-01", "TEACH-SRU-01")) and all(any(r["IID"] == iid and r["MID"] == "TEACH-AIR-01" and r["QTYPM"] == 2 for r in structure) for iid in ("TEACH-LRU-01", "TEACH-AUX-01")))
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("clean conversion", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and len(re.findall(r"\(warning #108\)", runlog)) == 1 and len(re.findall(r"\(warning #\d+\)", runlog)) == 1 and "(error #" not in runlog)

    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    faults = re.findall(r"^Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) random failure added, now\s*\n(.*?)(?=^Time:|\Z)", log, re.M | re.S)
    observed = [(float(t), severity, tuple(re.findall(r"subitem failed: <(TEACH-(?:LRU|AUX)-01),0,(\d+)>", block))) for t, severity, block in faults]
    expected = [(8.15691, "noncritical", (("TEACH-LRU-01", "5"),)), (8.57314, "critical", (("TEACH-LRU-01", "5"), ("TEACH-AUX-01", "7"))), (20.1635, "noncritical", (("TEACH-AUX-01", "8"),)), (20.6165, "noncritical", (("TEACH-AUX-01", "8"), ("TEACH-LRU-01", "9"))), (32.2754, "noncritical", (("TEACH-LRU-01", "11"),)), (32.3336, "critical", (("TEACH-LRU-01", "11"), ("TEACH-AUX-01", "13")))]
    ck("physical fault sequence and link threshold", len(observed) == len(expected) and all(abs(t-e) < .0001 and s == es and ids == ei for (t, s, ids), (e, es, ei) in zip(observed, expected)))
    ck("missions and returns", times(log, r"<BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission aborted:") == [8.57314, 32.3336] and times(log, r"<BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission success:") == [22] and times(log, r"<BASIC-MISSION,TEACH-UNIT,0,0,\d+> aborted mission completed:") == [9.07314, 32.6672])
    ck("six half-hour system replacements", times(log, r" system SURP task \d+ on <TEACH-AIR-01,0> started") == [9.07314, 9.07314, 22, 22, 32.6672, 32.6672] and times(log, r" system SURP task \d+ on <TEACH-AIR-01,0> completed") == [9.57314, 9.57314, 22.5, 22.5, 33.1672, 33.1672])
    ck("partial then full system repair", times(log, r"<TEACH-AIR-01,BASE-01,0> System partially repaired") == [9.57314, 22.5, 33.1672] and times(log, r"<TEACH-AIR-01,BASE-01,0> System ready") == [9.57314, 22.5, 33.1672])
    ck("physical LRU AUX SRU stock issues", [len(re.findall(r"Take replacement item <" + iid + r",0,\d+> from stock", log)) for iid in ("TEACH-LRU-01", "TEACH-AUX-01", "TEACH-SRU-01")] == [3, 3, 3])
    ck("nested and direct repair completion", len(times(log, r" item SURP task \d+ on <TEACH-LRU-01,0,\d+> completed")) == 3 and len(times(log, r" item DIRP task \d+ on <TEACH-AUX-01,0,\d+> completed")) == 3 and len(times(log, r" item DIRP task \d+ on <TEACH-SRU-01,0,\d+> completed")) == 3)
    ck("no backorder", "Backorder added" not in log and "Backorder removed" not in log)
    for iid in ("TEACH-LRU-01", "TEACH-AUX-01", "TEACH-SRU-01"):
        levels = re.findall(r"Stock at: <" + iid + r",0,BASE-01,0> Level: (\d+) Items:([^\n]*)", log)
        ck(f"terminal {iid} stock", bool(levels) and int(levels[-1][0]) == (1 if iid == "TEACH-SRU-01" else 2))
    ck("terminal log readiness", "Time: 33.1672 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log and "Time: 33.1672 <TEACH-UNIT at <BASE-01,0>> systems ready: 1" in log)

    report = parse_native(run / "report-raw.json")
    summary, systems, stocks = (rows(report, "report", name) for name in ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck("one of three missions successful", len(summary) == 1 and summary[0]["NREP"] == 1 and abs(summary[0]["MSUF"] - 1/3) < 1e-6)
    ck("72 contiguous System bins", len(systems) == 72 and all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(systems)))
    ck("six failures and replacements", {i:r["NFAIL"] for i,r in enumerate(systems) if r["NFAIL"]} == {16:1,17:1,40:1,41:1,64:2} and {i:r["NREPT"] for i,r in enumerate(systems) if r["NREPT"]} == {19:2,45:2,66:2})
    ck("three downtime intervals", [i for i,r in enumerate(systems) if r["NSYDT"]] == [18,44,65] and sum(r["NSYDT"] for r in systems) == 3)
    ck("terminal aircraft ready", systems[-1]["NSYRY"] == systems[-1]["NSYA"] == 1 and systems[-1]["NSYRP"] == 0)
    ck("72 contiguous Stock bins", len(stocks) == 72 and all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i,r in enumerate(stocks)))
    ck("six stock demands and waits", {i:r["NDF"] for i,r in enumerate(stocks) if r["NDF"]} == {18:2,44:2,65:2} and {i:r["NWT"] for i,r in enumerate(stocks) if r["NWT"]} == {18:2,44:2,65:2})
    ck("no aggregate stock backorder", all(r["NBO"] == 0 for r in stocks))
    return {"schema": "simlox-g10-var01-series-v101-author-validation/v1", "case_id": "G10", "variant_id": "G10.var01", "run_id": run.name, "passed": not errors, "checks": checks, "differences": errors, "input_sha256": input_sha, "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "publication_state": "not_published"}


if __name__ == "__main__":
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)

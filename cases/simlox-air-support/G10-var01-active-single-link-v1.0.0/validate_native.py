"""Read-only author replay of the first G10 native active-redundancy run."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G01-var05-qty-two-v1.0.0"
INPUT_SHA = "7e990242656119f9424fcf390ae8c46eb23e4751dbe6fb44bd80b3bb4cf307d1"
PARENT_SHA = "ef21268a1f4c024e0c5bea24136509446e356ea3214dedd694c67825f376f984"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
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
    count = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal count
        count += 1
        if not ok:
            errors.append(label)

    contract = load(HERE / "contract.json")
    ck("frozen input", sha(HERE / "native-input.json") == sha(run / "input.json") == contract["native_input_sha256"] == INPUT_SHA)
    ck("accepted parent", sha(PARENT / "native-input.json") == contract["parent"]["input_sha256"] == PARENT_SHA)
    inv, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("run identity", inv.get("case_id") == "G10" and inv.get("case_version") == "1.0.0-candidate" and inv.get("run_id") == run.name)
    ck("input and parent bound", inv.get("input_sha256") == INPUT_SHA and inv.get("parent_sha256") == PARENT_SHA)
    for key, path in (("contract", HERE / "contract.json"), ("builder", HERE / "build.py"), ("checker", HERE / "check_roundtrip.py"), ("runner_script", HERE / "run_native_ssh.ps1"), ("parent_signoff", PARENT / "cli-scope-signoff-2026-10-01.md"), ("parent_closure", PARENT / "runs/g01-var05-qty-v100-ssh-20261001-01/closure.json"), ("manual", Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")), ("dictionary", Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"))):
        ck(f"sealed source {key}", inv["source_hashes_before"].get(key) == sha(path))
    ck("native executable", inv.get("simlox_exe_sha256") == EXE_SHA)
    ck("session-0 guarded", inv.get("session_id") == 0 and inv.get("ssh_connection_present") is True and "sshd.exe" in inv.get("ssh_ancestor_names", []) and inv.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue")
    ck("GUI preserved", inv.get("gui", {}).get("pid") == 13340 and inv.get("gui", {}).get("session_id") == 1)
    ck("closure and source stability", closure.get("invocation_sha256") == sha(run / "invocation.json") and closure.get("error") is None and closure.get("source_hashes_before") == closure.get("source_hashes_after") == inv.get("source_hashes_before"))
    ck("complete raw artifact set", set(closure.get("raw", {})) == RAW)
    for name, record in closure["raw"].items():
        path = run / name
        ck(f"raw seal {name}", path.is_file() and path.stat().st_size == record["bytes"] and sha(path) == record["sha256"])
    ck("five completed steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    rt = load(run / "roundtrip-validation.json")
    ck("22-table source roundtrip", rt["passed"] and rt["differences"] == [] and len(rt["populated_tables"]) == 22)
    source, exported = (parse_native(path) for path in (HERE / "native-input.json", run / "roundtrip-raw.json"))
    ck("populated source tables exact", all(populated(exported).get(name) == value for name, value in populated(source).items()))
    control = rows(exported, "model", "Control")
    redundancy = rows(exported, "model", "Redundancy")
    structure = rows(exported, "model", "ItemStructure")
    ck("RELOP REDUNDANCY", len(control) == 1 and control[0]["RELOP"] == "REDUNDANCY")
    ck("ACTIVE 1-of-2 link", redundancy == [{"RLID": "TEACH-LRU-01", "SID": "TEACH-AIR-01", "NRL": 2, "NRLRQ": 1, "ACPA": "ACTIVE", "TSWOV": 0, "NOTE": None}])
    ck("two installed physical LRUs", any(r["MID"] == "TEACH-AIR-01" and r["IID"] == "TEACH-LRU-01" and r["QTYPM"] == 2 for r in structure))
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("zero conversion errors", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1}) and not re.search(r"\(error #", runlog))
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    failures = re.findall(r"noncritical random failure added, now\s+1 failures:\s+subitem failed: <TEACH-LRU-01,0,(\d+)>", log)
    first_failure = times(log, r"<TEACH-AIR-01,0> noncritical random failure added")
    successes = times(log, r"<BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission success:")
    ck("two distinct noncritical LRU failures", len(failures) == 2 and len(set(failures)) == 2 and len(first_failure) == 2)
    ck("no critical failure or mission abort", "critical random failure added" not in log.replace("noncritical random failure added", "") and "mission aborted:" not in log)
    ck("failures precede successful mission ends", len(successes) == 3 and len(first_failure) == 2 and first_failure[0] < successes[0] and first_failure[1] < successes[1] and successes == [10.0, 22.0, 34.0])
    system_start = times(log, r" system SURP task \d+ on <TEACH-AIR-01,0> started")
    system_end = times(log, r" system SURP task \d+ on <TEACH-AIR-01,0> completed")
    lru_start = times(log, r" item SURP task \d+ on <TEACH-LRU-01,0,\d+> started")
    lru_end = times(log, r" item SURP task \d+ on <TEACH-LRU-01,0,\d+> completed")
    sru_start = times(log, r" item DIRP task \d+ on <TEACH-SRU-01,0,\d+> started")
    sru_end = times(log, r" item DIRP task \d+ on <TEACH-SRU-01,0,\d+> completed")
    ck("system replacement after successful return", len(system_start) == len(system_end) == 2 and system_start == [10.0, 22.0] and system_end == [10.5, 22.5])
    ck("LRU repair path", len(lru_start) == len(lru_end) == 2 and all(abs(b-a-.75) < .0002 for a,b in zip(lru_start,lru_end)))
    ck("SRU direct repair path", len(sru_start) == len(sru_end) == 2 and all(abs(b-a-1) < .0002 for a,b in zip(sru_start,sru_end)))
    issued_lru = re.findall(r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock", log)
    issued_sru = re.findall(r"Take replacement item <TEACH-SRU-01,0,(\d+)> from stock", log)
    ck("two distinct LRU stock issues", issued_lru == ["1", "2"] and set(issued_lru).isdisjoint(failures))
    ck("two SRU stock issues", issued_sru == ["0", "4"])
    ck("stock closes and no backorder", "Level: 2 Items:<TEACH-LRU-01,0,3>,<TEACH-LRU-01,0,5>" in log and "Level: 1 Items:<TEACH-SRU-01,0,6>" in log and "backorder" not in log.lower())
    report = parse_native(run / "report-raw.json")
    summary = rows(report, "report", "ResultSummary")
    systems = rows(report, "report", "SystemResults")
    stocks = rows(report, "report", "StockTotalResults")
    ck("one repetition all missions succeed", len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["MSUF"] == 1)
    ck("72 contiguous system bins", len(systems) == 72 and all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i,r in enumerate(systems)))
    ck("two native failures and system replacements", sum(r["NFAIL"] for r in systems) == 2 and sum(r["NREPT"] for r in systems) == 2)
    ck("terminal aircraft ready", systems[-1]["NSYRY"] == systems[-1]["NSYA"] == 1 and systems[-1]["NSYRP"] == 0)
    ck("72 contiguous stock bins with no backorders", len(stocks) == 72 and all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 and r["NBO"] == 0 for i,r in enumerate(stocks)))
    ck("two aggregate system-level stock demands", sum(r["NDF"] for r in stocks) == 2)
    return {"schema": "simlox-g10-var01-v100-author-validation/v1", "case_id": "G10", "variant_id": "G10.var01", "run_id": run.name, "passed": not errors, "checks": count, "differences": errors, "failed_installed_lru_ids": failures, "issued_lru_ids": issued_lru, "issued_sru_ids": issued_sru, "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "publication_state": "not_published"}


if __name__ == "__main__":
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)

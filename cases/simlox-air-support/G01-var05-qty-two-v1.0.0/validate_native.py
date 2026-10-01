"""Read-only author acceptance replay for G01.var05 two installed LRUs."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G01-var01-lru-sru-v1.0.1/native-input.json"
INPUT_SHA = "ef21268a1f4c024e0c5bea24136509446e356ea3214dedd694c67825f376f984"
PARENT_SHA = "9c25a414615ac4ea523ee989385a913c692923e04bc41c6984b6866e86204bb9"
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
    table = next(t for t in doc[root]["tables"] if t["name"] == name)
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, r)) for instance in table["instances"] for r in instance["rows"]]


def validate(run: Path) -> dict:
    errors: list[str] = []
    count = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal count
        count += 1
        if not ok:
            errors.append(label)

    contract = load(HERE / "contract.json")
    ck("source hashes", sha(HERE / "native-input.json") == sha(run / "input.json") == contract["native_input_sha256"] == INPUT_SHA)
    ck("accepted parent", sha(PARENT) == contract["parent"]["input_sha256"] == PARENT_SHA)
    invocation, closure, steps = (load(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck("run identity", invocation.get("case_id") == "G01" and invocation.get("case_version") == "1.0.0-candidate" and invocation.get("run_id") == run.name)
    ck("input/parent bound", invocation.get("input_sha256") == INPUT_SHA and invocation.get("parent_sha256") == PARENT_SHA)
    for field, name in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"), ("checker_sha256", "check_roundtrip.py"), ("runner_script_sha256", "run_native_ssh.ps1")):
        ck(f"bound {name}", invocation.get(field) == sha(HERE / name))
    ck("native executable", invocation.get("simlox_exe_sha256") == EXE_SHA)
    ck("guarded session", invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") is True and "sshd.exe" in invocation.get("ssh_ancestor_names", []) and invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue")
    ck("GUI preserved", invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1)
    ck("closure", closure.get("invocation_sha256") == sha(run / "invocation.json") and closure.get("error") is None and closure.get("source_hashes_before") == closure.get("source_hashes_after") == invocation.get("source_hashes_before"))
    ck("raw set", set(closure.get("raw", {})) == RAW)
    for name, record in closure.get("raw", {}).items():
        path = run / name
        ck(f"sealed {name}", path.is_file() and path.stat().st_size == record.get("bytes") and sha(path) == record.get("sha256"))
    ck("five native steps", [s.get("name") for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s.get("status") == "completed" and s.get("exit_code") == 0 and s.get("gui_preserved") is True for s in steps))
    rt = load(run / "roundtrip-validation.json")
    ck("source roundtrip", rt.get("passed") is True and rt.get("differences") == [] and len(rt.get("populated_tables", [])) == 21)
    exported = native_json(run / "roundtrip-raw.json")
    structure = rows(exported, "ItemStructure", "model")
    system = rows(exported, "System", "model")
    stock = rows(exported, "StockAllocation", "model")
    ck("two LRU positions", len([r for r in structure if r["MID"] == "TEACH-AIR-01" and r["IID"] == "TEACH-LRU-01" and r["QTYPM"] == 2]) == 1)
    ck("matched system rate", len(system) == 1 and system[0]["FRT"] == 600000)
    ck("two LRU spares", len([r for r in stock if r["IID"] == "TEACH-LRU-01" and r["STSIZ"] == 2]) == 1)
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion clean", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1}))
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    failures = re.findall(r"critical random failure added, now\s+1 failures:\s+subitem failed: <TEACH-LRU-01,0,(\d+)>", log)
    removed = re.findall(r"Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)> from position <TEACH-AIR-01,BASE-01,0> subitem failed: <TEACH-SRU-01,0,(\d+)>", log)
    issues = re.findall(r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock", log)
    ck("two distinct failed installed LRUs", len(failures) == len(set(failures)) == 2 and len(removed) == 2 and {r[0] for r in removed} == set(failures))
    ck("spares distinct from installed", "Level: 2 Items:<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,2>" in log and len(issues) == 2 and set(issues).isdisjoint(failures))
    ck("two SRU repair paths", len(re.findall(r"^Time: [\d.]+  item SURP task \d+ on <TEACH-LRU-01,0,\d+> completed", log, re.M)) == 2 and len(re.findall(r"^Time: [\d.]+  item DIRP task \d+ on <TEACH-SRU-01,0,\d+> completed", log, re.M)) == 2)
    ck("inventory returns", "Level: 2 Items:<TEACH-LRU-01,0,2>,<TEACH-LRU-01,0,3>" in log and "Level: 2 Items:<TEACH-LRU-01,0,3>,<TEACH-LRU-01,0,5>" in log)
    ck("missions and no backorder", log.count("mission aborted:") == 2 and log.count("mission success:") == 1 and "backorder" not in log.lower())
    report = native_json(run / "report-raw.json")
    summary, systems, stocks = (rows(report, n, "report") for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck("summary", len(summary) == 1 and summary[0]["NREP"] == 1 and abs(summary[0]["MSUF"] - 1 / 3) < 1e-6)
    ck("72 system bins", len(systems) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(systems)))
    ck("two failures and repairs", sum(r["NFAIL"] for r in systems) == 2 and sum(r["NREPT"] for r in systems) == 2 and abs(sum(r["NSYRP"] * 0.5 for r in systems) - 1) < 1e-6 and systems[-1]["NSYRY"] == systems[-1]["NSYA"] == 1)
    ck("72 stock bins no outstanding", len(stocks) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 and r["NBO"] == 0 for i, r in enumerate(stocks)))
    return {"schema": "simlox-g01-var05-v100-author-validation/v1", "case_id": "G01", "variant_id": "G01.var05", "run_id": run.name, "passed": not errors, "checks": count, "differences": errors, "failed_installed_lru_ids": failures, "issued_spare_lru_ids": issues, "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "publication_state": "not_published"}


if __name__ == "__main__":
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)

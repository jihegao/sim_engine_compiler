"""Independent, read-only replay of the sealed D06 native CLI run.

Uses only Python's standard library. It never imports the case builder, checker,
or author validator, and it never invokes SIMLOX.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
PARENT = CASE.parent / "D01-installed-lru-direct-repair-v1.0.0" / "native-input.json"
RUN_ID = "d06-position-cm-v100-ssh-20260930-02"
RUN = CASE / "runs" / RUN_ID
OUTPUT = CASE / "review" / "independent-position-2026-09-30.json"
EXPECTED_SOURCE = "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78"
EXPECTED_PARENT = "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path, *, native: bool = False):
    source = path.read_text(encoding="utf-8-sig")
    if native:
        # This SIMLOX 2017 exporter emits a comma before closing brackets.
        source = re.sub(r",\s*([}\]])", r"\1", source)
    return json.loads(source)


def tables(document, key="model"):
    return {table["name"]: table for table in document[key]["tables"]}


def rows(table):
    columns = [column["name"] for column in table["columns"]]
    return [dict(zip(columns, row)) for part in table["instances"] for row in part["rows"]]


def log_events(log: str, fragment: str):
    return [float(m.group(1)) for line in log.splitlines()
            if (m := re.match(r"Time: ([0-9.]+) ", line)) and fragment in line]


def log_events_exact(log: str, expression: str):
    return [float(m.group(1)) for line in log.splitlines()
            if (m := re.fullmatch(r"Time: ([0-9.]+)  " + expression, line))]


def main():
    checks = []

    def check(name, actual, expected, *, tolerance=None):
        if tolerance is None:
            passed = actual == expected
        else:
            passed = abs(actual - expected) <= tolerance
        checks.append({"name": name, "passed": passed, "actual": actual, "expected": expected})

    contract = read_json(CASE / "contract.json")
    source = read_json(CASE / "native-input.json")
    parent = read_json(PARENT)
    diff = read_json(CASE / "parent-diff.json")
    invocation = read_json(RUN / "invocation.json")
    closure = read_json(RUN / "closure.json")
    steps = read_json(RUN / "steps.json")
    exported = read_json(RUN / "roundtrip-raw.json", native=True)
    report = read_json(RUN / "report-raw.json", native=True)
    model_log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    import_log = (RUN / "import.log").read_text(encoding="utf-8-sig")
    export_log = (RUN / "export.log").read_text(encoding="utf-8-sig")

    source_hash = digest(CASE / "native-input.json")
    parent_hash = digest(PARENT)
    check("frozen child input SHA", source_hash, EXPECTED_SOURCE)
    check("accepted installed-LRU parent SHA", parent_hash, EXPECTED_PARENT)
    check("contract input and parent binding", [contract["native_input_sha256"], contract["parent"]["input_sha256"]], [source_hash, parent_hash])
    check("parent diff source binding", [diff["child_input_sha256"], diff["parent_input_sha256"]], [source_hash, parent_hash])
    check("run input byte identity", digest(RUN / "input.json"), source_hash)
    check("invocation source identity", [invocation["input_sha256"], invocation["parent_sha256"]], [source_hash, parent_hash])
    check("run identity", [invocation["run_id"], closure["run_id"]], [RUN_ID, RUN_ID])
    check("closure binds invocation", closure["invocation_sha256"], digest(RUN / "invocation.json"))
    check("source hashes unchanged during run", closure["source_hashes_before"], closure["source_hashes_after"])
    check("invocation and closure fingerprints agree", invocation["source_hashes_before"], closure["source_hashes_before"])
    local_sources = {"input": CASE / "native-input.json", "parent": PARENT,
                     "contract": CASE / "contract.json", "builder": CASE / "build.py",
                     "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1"}
    for key, path in local_sources.items():
        check(f"sealed local {key} bytes", digest(path), closure["source_hashes_before"][key])
    raw_hashes = closure["raw"]
    check("closure lists 12 raw files", len(raw_hashes), 12)
    for name, claim in sorted(raw_hashes.items()):
        path = RUN / name
        check(f"sealed raw file {name}", [path.stat().st_size, digest(path)], [claim["bytes"], claim["sha256"]])
    check("closure completed without error", closure["error"], None)
    check("session-0 SSH and GUI guard", [invocation["execution_mode"], invocation["session_id"], invocation["ssh_connection_present"], invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["queue_mutex"]],
          ["ssh_cli_v1", 0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"])
    check("five recorded steps including checker", [s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"])
    check("all recorded steps passed and guarded GUI", all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), True)
    check("import/export completion markers", ["Import completed!" in import_log, "Export completed!" in export_log], [True, True])
    check("conversion errors/warnings/notes", re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log).groups(), ("0", "1", "0"))
    check("only expected logging warning", re.findall(r"warning #(\d+)", run_log), ["108"])

    pt, ct, et = tables(parent), tables(source), tables(exported)
    changed = sorted(name for name in pt.keys() & ct.keys() if pt[name] != ct[name])
    added = sorted(ct.keys() - pt.keys())
    check("exact changed parent tables", changed, sorted(diff["changed_tables_only"]))
    check("exact added tables", added, sorted(diff["added_tables_only"]))
    check("no parent tables deleted", sorted(pt.keys() - ct.keys()), [])
    check("unchanged parent table count", len(pt) - len(changed), 24)
    check("parent diff records exact changed tables", all(diff["changed_tables"][name] == {"parent": pt[name], "child": ct[name]} for name in changed), True)
    check("parent diff records exact added tables", all(diff["added_tables"][name] == ct[name] for name in added), True)
    populated = [name for name, table in ct.items() if any(part["rows"] for part in table["instances"])]
    check("18 source row-containing tables", len(populated), 18)
    check("all row-containing tables roundtrip exactly", all(ct[name] == et.get(name) for name in populated), True)
    check("no source tables missing from export", sorted(ct.keys() - et.keys()), [])

    system = rows(ct["System"])
    item = rows(ct["Item"])
    positions = rows(ct["MaterielPosition"])
    structure = rows(ct["MaterielStructure"])
    modes = rows(ct["FailureMode"])
    locations = rows(ct["CMLocation"])
    check("two named positions", [row["MPID"] for row in positions], ["POS-A", "POS-B"])
    check("positions and shared LRU wired to aircraft", [(r["MID"], r["MMID"], r["QTYPM"]) for r in structure],
          [("POS-A", "TEACH-AIR-01", 1), ("POS-B", "TEACH-AIR-01", 1), ("TEACH-LRU-01", "POS-A", 1), ("TEACH-LRU-01", "POS-B", 1)])
    check("single critical position-A failure mode", [(r["FMID"], r["MID"], r["FRQ"], r["OPID"], r["CRITF"]) for r in modes],
          [("FM-POS-A", "POS-A", 300000.0, "OPHOURS", 1.0)])
    check("mode maps to system CM at base", [(r["FMID"], r["ID"], r["STID"], r["CMT"], r["CMF"]) for r in locations],
          [("FM-POS-A", "TEACH-AIR-01", "BASE-01", 0.5, 1.0)])
    check("traditional system and item FRT absent", [system[0]["FRT"], item[0]["FRT"]], [None, None])
    check("traditional repair/stock/replacement branches absent", all(not rows(ct[name]) for name in ["ItemStructure", "SystemRepair", "ItemRepair", "StockAllocation", "ItemReplacement"]), True)
    check("position-B failure mode absent", all(r["MID"] != "POS-B" for r in modes), True)

    failures = log_events(model_log, "critical CM failure mode added")
    check("exact observed failure times", failures, [9.8829, 33.8602])
    check("failure lines carry one FM-POS-A on POS-A", model_log.count("Failure Mode: FM-POS-A on materiel: <POS-A,0>"), 4)
    check("no other named failure modes in log", sorted(set(re.findall(r"Failure Mode: ([^ ]+)", model_log))), ["FM-POS-A"])
    check("two aborted missions", log_events(model_log, "mission aborted:"), [9.8829, 33.8602])
    check("one successful middle mission", log_events(model_log, "mission success:"), [22.0])
    check("mission launches", log_events(model_log, "mission starting, duration: 2"), [8.0, 20.0, 32.0])
    check("failed-aircraft returns", log_events(model_log, "System arrives <TEACH-AIR-01,0>,") , [10.0, 22.0, 34.0])
    check("two system CM starts", log_events_exact(model_log, r"system CM task [01] on <TEACH-AIR-01,0> started"), [10.0, 34.0])
    check("both CM tasks name FM-POS-A", model_log.count("FMID: FM-POS-A"), 2)
    check("CM subtasks perform for 0.5h", log_events(model_log, "starts performing, planned to last for 0.5 hours"), [10.0, 34.0])
    check("two system CM completions", log_events_exact(model_log, r"system CM task [01] on <TEACH-AIR-01,0> completed"), [10.5, 34.5])
    check("maintained aircraft returns ready", log_events(model_log, "Maintained system arrives") , [10.5, 34.5])
    check("no item repair or spare issue event", not re.search(r"item CM task|item repair task|stock issued|spare issued|ItemRepair", model_log, re.I), True)

    rt = tables(report, "report")
    summary = rows(rt["ResultSummary"])
    system_rows = rows(rt["SystemResults"])
    stock_rows = rows(rt["StockTotalResults"])
    check("one report summary and 72 half-hour system/stock bins", [len(summary), len(system_rows), len(stock_rows)], [1, 72, 72])
    for name, data in [("system", system_rows), ("stock", stock_rows)]:
        check(f"{name} report aligned 0-36 half-hour bins", [(r["STINT"], r["ETINT"]) for r in data], [(i / 2, (i + 1) / 2) for i in range(72)])
    check("report two failures and two repairs", [sum(r["NFAIL"] for r in system_rows), sum(r["NREPT"] for r in system_rows)], [2, 2])
    check("failure and repair completion bins", [[r["STINT"] for r in system_rows if r["NFAIL"]], [r["STINT"] for r in system_rows if r["NREPT"]]], [[9.5, 33.5], [10.5, 34.5]])
    check("direct-repair occupancy bins", [r["STINT"] for r in system_rows if r["NSYRP"]], [10.0, 34.0])
    check("no PM or replacement report activity", [sum(r[key] or 0 for r in system_rows) for key in ("NPMT", "NPMS", "NROBT", "NRCFG")], [0, 0, 0, 0])
    check("stock/backorder ledger remains zero", all(r["NBO"] == 0 and r["NDF"] == 0 and r["NDD"] == 0 and r["NDR"] == 0 for r in stock_rows), True)
    check("two half-hour turnaround values", [r["SYDT"] for r in system_rows if r["SYDT"] is not None], [0.5, 0.5])
    check("report ready at terminal", [system_rows[-1]["NSYRY"], system_rows[-1]["NSYRP"], system_rows[-1]["NSYUA"]], [1, 0, 0])
    check("result summary horizon and one repetition", [summary[0]["NREP"], summary[0]["RTILW"], summary[0]["RTIUP"]], [1, 0, 36])

    result = {
        "schema": "simlox-d06-independent-position-readonly/v1",
        "reviewer": "independent read-only reviewer; no author validator imports or native calls",
        "case_id": "D06", "run_id": RUN_ID,
        "passed": all(c["passed"] for c in checks),
        "passed_count": sum(c["passed"] for c in checks),
        "failed_count": sum(not c["passed"] for c in checks),
        "checks": checks,
        "hashes": {"input": source_hash, "parent": parent_hash,
                   "invocation": digest(RUN / "invocation.json"),
                   "closure": digest(RUN / "closure.json"),
                   "model_log": digest(RUN / "model.log"),
                   "report_raw": digest(RUN / "report-raw.json")},
        "observed": {"failure_hours": failures, "abort_hours": [9.8829, 33.8602],
                     "direct_cm_intervals": [[10, 10.5], [34, 34.5]],
                     "successful_mission": [20, 22],
                     "terminal_ready_aircraft": system_rows[-1]["NSYRY"],
                     "conversion": {"errors": 0, "warnings": 1, "warning_codes": [108]}},
        "limits": [
            "Evidence supports one explicit FMID on POS-A mapped to system CMLocation; it does not isolate position B failure behavior.",
            "No direct component replacement, stock issue, ItemRepair, alternate CM location, or resource-constrained task is exercised.",
            "CMLocation.CMT is the observed calendar turnaround, not separately measured technician effort.",
            "The excluded -01 run used different input/checker hashes and ended with roundtrip checker exit 1; only sealed -02 is accepted.",
            "Native CLI and log/report evidence do not establish GUI visual behavior or cross-engine equivalence.",
        ],
        "publication_state": "independent_review_only",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": [c for c in checks if not c["passed"]],
                      "output": str(OUTPUT)}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

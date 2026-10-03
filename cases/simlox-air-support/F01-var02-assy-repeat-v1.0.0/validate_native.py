"""Read-only author replay of F01.var02 structural ASSY repeated-reissue run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/f01-var02-assy-v100-ssh-20261004-01"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
       "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
       "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(report: dict, name: str) -> list[dict]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for ins in table["instances"] for row in ins["rows"]]


def events(log: str, pattern: str) -> list[tuple]:
    return [(float(m.group(1)), *m.groups()[1:]) for m in re.finditer(pattern, log, re.M)]


def main() -> None:
    failures: list[str] = []
    checks = 0

    def ck(ok: bool, label: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(label)

    contract = load(HERE / "contract.json")
    diff = load(HERE / "exact-diff.json")
    parent = contract["accepted_behavior_parent"]
    reference = contract["accepted_structural_reference"]
    parent_dir = ROOT / parent["package"]
    reference_dir = ROOT / reference["package"]
    parent_run = parent_dir / "runs" / parent["run_id"]
    ck(contract["case_id"] == "F01" and contract["variant_id"] == "F01.var02", "contract identity")
    ck(sha(HERE / "native-input.json") == contract["native_input_sha256"], "frozen source")
    ck(sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen diff")
    ck(sha(parent_dir / parent["input"]) == parent["input_sha256"], "parent input")
    ck(sha(parent_run / "closure.json") == parent["closure_sha256"], "parent native closure")
    ck(sha(parent_dir / "evidence-index.json") == parent["evidence_index_sha256"], "parent index")
    ck(sha(reference_dir / "native-input.json") == reference["input_sha256"], "structural reference input")
    ck(sha(reference_dir / "runs" / reference["run_id"] / "closure.json") == reference["closure_sha256"], "structural reference native closure")
    ck(sha(reference_dir / "evidence-index.json") == reference["evidence_index_sha256"], "structural reference index")
    ck([x["table"] for x in diff["assy_from_f01_var01"]["changed_tables"]] ==
       ["ProblemDescription", "Item", "ItemStructure", "ItemReplacement"], "four-table physical delta")
    ck([x["table"] for x in diff["rate_from_g01_var04"]["changed_tables"]] ==
       ["ProblemDescription", "System", "Item"], "rate-only structural reference delta")
    ck(diff["assy_from_f01_var01"]["left_sha256"] == parent["input_sha256"] and
       diff["assy_from_f01_var01"]["right_sha256"] == contract["native_input_sha256"], "diff endpoints")

    source = parse_native(HERE / "native-input.json")
    table = {t["name"]: t for t in source["model"]["tables"]}
    item = table["Item"]
    item_cols = [c["name"] for c in item["columns"]]
    assy = [r for r in item["instances"][0]["rows"] if r[item_cols.index("IID")] == "TEACH-ASSY-01"]
    ck(len(assy) == 1 and {item_cols[i] for i, v in enumerate(assy[0]) if v is not None} ==
       {"IID", "DESCR", "TYPE"} and assy[0][item_cols.index("TYPE")] == "ASSY", "logistics-inert ASSY configuration")
    for name in ("ItemRepair", "StockAllocation", "ItemReplacement"):
        ck("TEACH-ASSY-01" not in json.dumps(table[name]["instances"]), f"no ASSY {name} row")

    invocation, closure, steps = (load(RUN / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck(invocation["run_id"] == closure["run_id"] == RUN.name and invocation["variant_id"] == "F01.var02", "run identity")
    ck(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0")
    ck(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "queue and GUI")
    ck(closure["error"] is None and closure["invocation_sha256"] == sha(RUN / "invocation.json"), "native closure")
    ck(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stable across native")
    source_seals = {"input": "native-input.json", "parent": str(parent_dir / parent["input"]),
                    "parent_closure": str(parent_run / "closure.json"),
                    "parent_evidence_index": str(parent_dir / "evidence-index.json"),
                    "structural_reference": str(reference_dir / "native-input.json"),
                    "structural_reference_closure": str(reference_dir / "runs" / reference["run_id"] / "closure.json"),
                    "structural_reference_evidence_index": str(reference_dir / "evidence-index.json"),
                    "exact_diff": "exact-diff.json", "contract": "contract.json", "builder": "build.py",
                    "diff_builder": "describe_diff.py", "checker": "check_roundtrip.py", "runner_script": "run_native_ssh.ps1"}
    for key, name in source_seals.items():
        path = Path(name) if Path(name).is_absolute() else HERE / name
        ck(closure["source_hashes_before"][key] == sha(path), f"source seal {key}")
    ck(set(closure["raw"]) == RAW, "12 raw files")
    for name, meta in closure["raw"].items():
        path = RUN / name
        ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"raw seal {name}")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and
       all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "five guarded steps")
    ck((RUN / "model.sxi").stat().st_size > 1000 and (RUN / "model.sxo").stat().st_size > 1000, "nonempty model/output")
    roundtrip = load(RUN / "roundtrip-validation.json")
    authored = populated(source)
    exported = populated(parse_native(RUN / "roundtrip-raw.json"))
    ck(roundtrip["passed"] and not roundtrip["differences"] and len(authored) == 21, "21-table native roundtrip")
    for name, content in authored.items():
        ck(exported.get(name) == content, f"roundtrip {name}")
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and runlog.count("(warning #108)") == 1, "conversion zero error")

    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    old = (parent_run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck(log.count("TEACH-ASSY-01") == 4 and all("connection path:" in line for line in log.splitlines() if "TEACH-ASSY-01" in line), "four physical ASSY paths only")
    ck(log.replace(" - TEACH-ASSY-01", "") == old, "complete parent event ledger parity after ASSY path normalization")
    ck(not re.search(r"^Time: .*TEACH-ASSY-01.*(?:demand|stock|repair|task|failed)", log, re.M), "no ASSY transaction or task")
    fault = events(log, r"^Time: ([\d.]+) <TEACH-AIR-01,0> critical random failure added")
    lru_demand = events(log, r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,(\d+)>")
    lru_issue = events(log, r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock")
    lru_return = events(log, r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock")
    sru_demand = events(log, r"^Time: ([\d.]+) <TEACH-SRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0> item requiring maintenance is <TEACH-SRU-01,0,(\d+)>")
    sru_issue = events(log, r"^Time: ([\d.]+) <TEACH-SRU-01,0,BASE-01,0> Take replacement item <TEACH-SRU-01,0,(\d+)> from stock")
    sru_return = events(log, r"^Time: ([\d.]+) <TEACH-SRU-01,0,BASE-01,0> Put back replacement item <TEACH-SRU-01,0,(\d+)> to stock")
    ck(all(len(x) == 2 for x in (fault, lru_demand, lru_issue, lru_return, sru_demand, sru_issue, sru_return)), "two complete nested cycles")
    if all(len(x) == 2 for x in (lru_demand, lru_issue, lru_return, sru_demand, sru_issue, sru_return)):
        for i in range(2):
            ck(lru_demand[i][1] == lru_return[i][1] and lru_demand[i][0] <= lru_issue[i][0] < lru_return[i][0], f"LRU physical repair {i}")
            ck(sru_demand[i][1] == sru_return[i][1] and sru_demand[i][0] <= sru_issue[i][0] < sru_return[i][0], f"SRU physical repair {i}")
        ck(lru_issue[1][1] == lru_return[0][1] and lru_return[0][0] < lru_issue[1][0], "repaired LRU reissued")
        ck(sru_issue[1][1] == sru_return[0][1] and sru_return[0][0] < sru_issue[1][0], "repaired SRU reissued")
    surp_start = events(log, r"^Time: ([\d.]+)  item SURP task \d+ on <TEACH-LRU-01,0,(\d+)> started")
    surp_end = events(log, r"^Time: ([\d.]+)  item SURP task \d+ on <TEACH-LRU-01,0,(\d+)> completed")
    dirp_start = events(log, r"^Time: ([\d.]+)  item DIRP task \d+ on <TEACH-SRU-01,0,(\d+)> started")
    dirp_end = events(log, r"^Time: ([\d.]+)  item DIRP task \d+ on <TEACH-SRU-01,0,(\d+)> completed")
    ck(all(len(x) == 2 for x in (surp_start, surp_end, dirp_start, dirp_end)), "two SURP and DIRP tasks")
    for i in range(min(map(len, (surp_start, surp_end, dirp_start, dirp_end)))):
        ck(surp_start[i][1] == surp_end[i][1] and abs(surp_end[i][0] - surp_start[i][0] - .75) < 1e-4, f"specific SURP time {i}")
        ck(dirp_start[i][1] == dirp_end[i][1] and abs(dirp_end[i][0] - dirp_start[i][0] - 1) < 1e-4, f"SRU DIRP time {i}")
    ck(log.count("planned to last for 0.375 hours") == 4, "four SRU replacement half-steps")
    ck("Backorder added" not in log and "requests resources: no resources needed" in log, "no backorder/resource scarcity")
    ck(len(events(log, r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission aborted:")) == 2 and
       len(events(log, r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:")) == 1, "mission outcomes")

    report = parse_native(RUN / "report-raw.json")
    parent_report = parse_native(parent_run / "report-raw.json")
    child_tables = {t["name"]: t for t in report["report"]["tables"]}
    parent_tables = {t["name"]: t for t in parent_report["report"]["tables"]}
    ck(child_tables.keys() == parent_tables.keys() == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table set")
    ck(child_tables["ProblemDescription"] != parent_tables["ProblemDescription"], "description differs")
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        ck(child_tables[name] == parent_tables[name], f"every {name} field equals accepted parent")
    summary, system, stock = (rows(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck(len(summary) == 1 and abs(summary[0]["MSUF"] - 1 / 3) < 1e-6, "one of three missions successful")
    ck(len(system) == len(stock) == 72, "72 System and Stock bins")
    for i, (sy, st) in enumerate(zip(system, stock)):
        ck(sy["STINT"] == st["STINT"] == i / 2 and sy["ETINT"] == st["ETINT"] == (i + 1) / 2, f"interval {i}")
        ck(st["NBO"] == 0, f"no backorder bin {i}")
    ck(sum(x["NFAIL"] for x in system) == sum(x["NREPT"] for x in system) == 2, "two failures/system repairs")
    ck(sum(x["NDF"] for x in stock) == 2 and system[-1]["NSYRY"] == 1, "two stock demands/terminal ready")

    result = {"schema": "simlox-f01-var02-author-replay/v1", "case_id": "F01.var02", "passed": not failures,
              "checks_passed": checks - len(failures), "checks_total": checks, "failures": failures,
              "run_id": RUN.name, "closure_sha256": sha(RUN / "closure.json"),
              "assy_path_lines": log.count("TEACH-ASSY-01"),
              "normalized_event_log_equal_parent": log.replace(" - TEACH-ASSY-01", "") == old,
              "non_description_report_equal_parent": all(child_tables[n] == parent_tables[n] for n in ("ResultSummary", "SystemResults", "StockTotalResults")),
              "repaired_lru_reissue": len(lru_issue) == len(lru_return) == 2 and lru_issue[1][1] == lru_return[0][1],
              "repaired_sru_reissue": len(sru_issue) == len(sru_return) == 2 and sru_issue[1][1] == sru_return[0][1]}
    (HERE / "author-validation-2026-10-04.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("passed", "checks_passed", "checks_total", "failures")}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

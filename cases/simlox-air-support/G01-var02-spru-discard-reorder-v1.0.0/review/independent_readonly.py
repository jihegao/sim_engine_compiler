"""Independent standard-library replay of the sealed G01.var02 SPRU runs.

This module reads source and native artifacts only. It never imports case code or
executes SIMLOX. Copy the same file into the companion case's review directory.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
SEED7 = "discard-reorder" in CASE.name
RUN_ID = (
    "g01-var02-spru-discard-v100-ssh-20261001-01"
    if SEED7 else "g01-var02-spru-v100-ssh-20261001-01"
)
RUN = CASE / "runs" / RUN_ID
PARENT = BASE / "G01-var03-dp-discard-reorder-v1.0.0" / "native-input.json"
OTHER = BASE / (
    "G01-var02-spru-partial-repair-v1.0.0" if SEED7
    else "G01-var02-spru-discard-reorder-v1.0.0"
) / "native-input.json"
REPORT = CASE / "review" / "independent-readonly-2026-10-01.json"
checks = 0
failures: list[str] = []


def check(condition: bool, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native: bool = False):
    text = path.read_text(encoding="utf-8-sig")
    # SIMLOX's JSON exporter emits trailing commas in otherwise valid JSON.
    if native:
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def tables(obj, key: str):
    return {t["name"]: t for t in obj[key]["tables"]}


def rows(table):
    return [r for instance in table["instances"] for r in instance["rows"]]


def records(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]


def near(actual, expected, label: str, tol=2e-5):
    check(actual is not None and abs(actual - expected) <= tol,
          f"{label}: {actual!r} versus {expected!r}")


def at(log: str, time: float, fragment: str) -> bool:
    return any(abs(float(t) - time) < 2e-4 and fragment in line
               for t, line in re.findall(r"^Time: ([0-9.]+) (.*)$", log, re.M))


def bin_fraction(start: float, end: float, index: int) -> float:
    return max(0.0, min(end, (index + 1) / 2) - max(start, index / 2)) * 2


def main() -> None:
    source_path = CASE / "native-input.json"
    source = load(source_path)
    parent = load(PARENT)
    other = load(OTHER)
    contract = load(CASE / "contract.json")
    input_hash = "bebd3a755f8142c2f4a0170c74e200fd068c00a689b71d8b45ddac78a5fe5541" if SEED7 else "61bf4bdcc18d3e039f7fcff835854030fa21c67f906e35ea4a01b6a48700bcb8"
    check(sha(PARENT) == "a51598aed393f01fa4a6e28103ee4eed8aadec53114e3ed72e466f4a5126f226", "accepted parent SHA")
    check(sha(source_path) == input_hash, "frozen input SHA")
    check(contract["native_input_sha256"] == input_hash, "contract input SHA")
    check(contract["parent"]["input_sha256"] == sha(PARENT), "contract parent SHA")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
    check(sha(manual) == contract["source"]["manual_pdf_sha256"], "installed manual SHA")
    check(sha(dictionary) == contract["source"]["dictionary_sha256"], "installed dictionary SHA")
    st, pt, ot = tables(source, "model"), tables(parent, "model"), tables(other, "model")
    changed = {name for name in st.keys() | pt.keys() if st.get(name) != pt.get(name)}
    check(changed == {"ProblemDescription", "Item", "ItemStructure", "ItemRepair", "ItemReorder", "StockAllocation", "ItemReplacement"} | ({"Control"} if SEED7 else set()), "exact parent table delta")
    pair_changed = {name for name in st.keys() | ot.keys() if st.get(name) != ot.get(name)}
    check(pair_changed == {"Control"}, "seed-only pair table delta")
    seed_row = records(st["Control"])[0]
    other_row = records(ot["Control"])[0]
    check({k: v for k, v in seed_row.items() if k != "RSEED"} == {k: v for k, v in other_row.items() if k != "RSEED"}, "seed-only field delta")
    check(seed_row["RSEED"] == ("7" if SEED7 else "1"), "seed value")
    items = {r["IID"]: r for r in records(st["Item"])}
    check(items["TEACH-LRU-01"]["TYPE"] == "LRU", "mother LRU type")
    check(items["TEACH-SPRU-01"]["TYPE"] == "SPRU", "secondary SPRU type")
    structure = records(st["ItemStructure"])
    check(any(r["IID"] == "TEACH-LRU-01" and r["MID"] == "TEACH-AIR-01" and r["QTYPM"] == 1 for r in structure), "LRU installed in system")
    check(any(r["IID"] == "TEACH-SPRU-01" and r["MID"] == "TEACH-LRU-01" and r["QTYPM"] == 1 for r in structure), "SPRU installed in LRU")
    rep = next(r for r in records(st["ItemRepair"]) if r["IID"] == "TEACH-SPRU-01")
    check(all(rep[k] == v for k, v in {"STID": "DEPOT-01", "DIRPT": 1, "DIRPF": .5, "SURPF": 1}.items()), "SPRU depot repair policy")
    reorder = next(r for r in records(st["ItemReorder"]) if r["IID"] == "TEACH-SPRU-01")
    check(all(reorder[k] == v for k, v in {"STID": "DEPOT-01", "LEADT": 1, "DISCF": .5}.items()), "SPRU depot reorder policy")
    allocation = {(r["IID"], r["STID"]): r for r in records(st["StockAllocation"])}
    check(all(allocation[key]["STSIZ"] == value for key, value in {
        ("TEACH-SPRU-01", "BASE-01"): 1, ("TEACH-SPRU-01", "DEPOT-01"): 2,
        ("TEACH-LRU-01", "BASE-01"): 1}.items()), "opening stock allocation")
    check(allocation[("TEACH-SPRU-01", "DEPOT-01")]["ROSIZ"] == 1, "one-unit reorder")
    replacement = records(st["ItemReplacement"])
    check(any(r["MID"] == "TEACH-LRU-01" and r["IID"] == "TEACH-SPRU-01" and r["STID"] == "BASE-01" and r["SURPT"] == .75 for r in replacement), "SPRU item-specific replacement")

    invocation = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    check(invocation["run_id"] == RUN_ID == closure["run_id"], "run identity")
    check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
    check(invocation["input_sha256"] == input_hash, "invocation input SHA")
    check(invocation["parent_sha256"] == sha(PARENT), "invocation parent SHA")
    check(invocation["contract_sha256"] == sha(CASE / "contract.json"), "invocation contract SHA")
    for key, path in {"input": source_path, "parent": PARENT,
                      "contract": CASE / "contract.json", "builder": CASE / "build.py",
                      "checker": CASE / "check_roundtrip.py",
                      "runner_script": CASE / "run_native_ssh.ps1",
                      "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
                      "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")}.items():
        check(invocation["source_hashes_before"][key] == sha(path), f"invocation {key} source SHA")
        check(closure["source_hashes_before"][key] == sha(path), f"closure before {key} SHA")
        check(closure["source_hashes_after"][key] == sha(path), f"closure after {key} SHA")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "whole source seal stable")
    for name, meta in closure["raw"].items():
        path = RUN / name
        check(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"raw seal {name}")
    check(sha(RUN / "input.json") == input_hash, "raw source exact")
    check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True, "SSH session-zero provenance")
    check("sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "SSH ancestry and mutex")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "preserved GUI identity")
    steps = load(RUN / "steps.json")
    check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "five native stages")
    for step in steps:
        check(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] is True, f"stage {step['name']}")
    check(closure["error"] is None and closure["scope"] == "five_step_native_candidate", "closure success scope")

    exported = tables(load(RUN / "roundtrip-raw.json", native=True), "model")
    populated = [name for name, table in st.items() if rows(table)]
    check(len(populated) == 23, "23 row-containing source tables")
    for name in populated:
        check(exported.get(name) == st[name], f"native exact table roundtrip {name}")
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog, "zero conversion errors and one warning")
    check("warning #108" in runlog and "Saving results" in runlog, "expected warning and result save")
    check((RUN / "model.sxo").stat().st_size > 100000, "nontrivial SXO")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    check(len(log) > 10000, "nonempty native event log")
    stock_updates = re.findall(r"^  Stock at: <(TEACH-(?:SPRU|LRU)-01,0,(?:BASE|DEPOT)-01,0)> Level: (\d+) Items:(.*)$", log, re.M)
    levels: dict[str, list[int]] = {}
    for key, level, individuals in stock_updates:
        levels.setdefault(key, []).append(int(level))
        check(len(re.findall(r"<TEACH-(?:SPRU|LRU)-01,0,\d+>", individuals)) == int(level), f"stock individual count {key} level {level}")
    expected_levels = {
        "TEACH-LRU-01,0,BASE-01,0": [1, 0, 1] + ([0, 1, 0, 1] if SEED7 else []),
        "TEACH-SPRU-01,0,BASE-01,0": [1, 0, 1] + ([0, 1, 0, 1] if SEED7 else []),
        "TEACH-SPRU-01,0,DEPOT-01,0": [2, 1, 2] + ([1, 2, 1] if SEED7 else []),
    }
    check(levels == expected_levels, "exact physical stock level transitions")
    check("<TEACH-SPRU-01,0,10>" not in stock_updates[-1][2] if SEED7 else True, "unfinished SPRU 10 excluded from stock")
    report = load(RUN / "report-raw.json", native=True)["report"]["tables"]
    rt = {t["name"]: t for t in report}
    check(set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table set")
    summary = records(rt["ResultSummary"])[0]
    near(summary["NREP"], 1, "one repetition")
    near(summary["RTIUP"], 36, "36-hour horizon")
    near(summary["MSUF"], 0 if SEED7 else 2 / 3, "mission success fraction")
    near(summary["MTMF"], .4990522861480713 if SEED7 else 1, "reported mean time between failures")
    systems = records(rt["SystemResults"])
    stocks = records(rt["StockTotalResults"])
    check(len(systems) == len(stocks) == 72, "72 system and stock bins")
    for i, (system, stock) in enumerate(zip(systems, stocks)):
        for record in (system, stock):
            near(record["STINT"], i / 2, f"bin {i} start")
            near(record["ETINT"], (i + 1) / 2, f"bin {i} end")
        near(stock["PNB"], 1, f"bin {i} PNB baseline")
        for key in ("NBO", "NDD", "NDR", "NDP", "NLD"):
            near(stock[key], 0, f"bin {i} stock {key}")
    if SEED7:
        failures_at = [8.07061, 21.2482, 32.6049]
        completed_at = [8.14122, 21.7482, 33.1049]
        ready_at = [8.64122, 22.2482, 33.6049]
        spru = [(5, 10.6829, 11.6829), (7, 24.2898, 25.2898), (10, 35.6466, None)]
        near(summary["STMF"], .4990522861480713, "system failure metric")
    else:
        failures_at = [9.8829]
        completed_at = [10]
        ready_at = [10.5]
        spru = [(5, 12.5417, 13.5417)]
        near(summary["STMF"], 1, "system failure metric")
    for i, t in enumerate(failures_at):
        check(at(log, t, f"<BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission aborted"), f"mission {i} abort at {t}")
        near(systems[int(t * 2)]["NFAIL"], 1, f"mission {i} failure bin")
    for i, t in enumerate(ready_at):
        check(at(log, t, "System ready <TEACH-AIR-01,0>"), f"aircraft restored {i}")
        near(systems[int(t * 2)]["NREPT"], 1, f"repair-completion bin {i}")
    if SEED7:
        for idx in range(3):
            check(at(log, [8.30789, 21.9148, 33.2716][idx], f"Item requiring maintenance arrives <TEACH-LRU-01,0,{[4,6,9][idx]}>"), f"removed LRU identity {idx}")
            check(f"subitem failed: <TEACH-SPRU-01,0,{[5,7,10][idx]}>" in log, f"nested failed SPRU identity {idx}")
    else:
        check("subitem failed: <TEACH-SPRU-01,0,5>" in log, "nested failed SPRU 5")
    for individual, arrived, finished in spru:
        check(at(log, arrived, f"Item requiring maintenance arrives <TEACH-SPRU-01,0,{individual}>"), f"SPRU {individual} depot arrival")
        if individual != 7:
            check(at(log, arrived, f"Start repair of item <TEACH-SPRU-01,0,{individual}>"), f"SPRU {individual} repair start")
        if individual == 7:
            check(at(log, arrived, "Item discarded: <TEACH-SPRU-01,0,7>"), "SPRU 7 discarded")
            check(at(log, arrived, "reorder task 0 started, reorder time: 1"), "SPRU 7 reorder start")
            check(at(log, finished, "reorder task 0 completed, total time was 1"), "one-hour reorder")
            check(at(log, finished, "Put back replacement item <TEACH-SPRU-01,0,8> to stock"), "new SPRU 8 stock arrival")
            check("Finished repair of item <TEACH-SPRU-01,0,7>" not in log and "Put back replacement item <TEACH-SPRU-01,0,7>" not in log, "discarded SPRU 7 never returned")
        elif finished is not None:
            check(at(log, finished, f"Finished repair of item <TEACH-SPRU-01,0,{individual}>"), f"SPRU {individual} repair finishes")
            check(at(log, finished, f"Put back replacement item <TEACH-SPRU-01,0,{individual}> to stock"), f"same SPRU {individual} returned")
            near(finished - arrived, 1, f"SPRU {individual} one-hour direct repair")
        else:
            check(f"Finished repair of item <TEACH-SPRU-01,0,{individual}>" not in log and f"Put back replacement item <TEACH-SPRU-01,0,{individual}>" not in log, "SPRU 10 unfinished at horizon")
            check(36 - arrived < 1, "SPRU 10 lacks full repair hour before horizon")
    check("Item discarded:" in log if SEED7 else "Item discarded:" not in log, "discard branch distinction")
    check("reorder task" in log if SEED7 else "reorder task" not in log, "reorder branch distinction")
    for i, rec in enumerate(systems):
        ready_spans = ([(0, 7), (ready_at[0], 19), (ready_at[1], 31), (ready_at[2], 36)]
                       if SEED7 else [(0, 7), (ready_at[0], 19), (22, 31), (34, 36)])
        expected_ready = sum(bin_fraction(a, b, i) for a, b in ready_spans)
        near(rec["NSYRY"], expected_ready, f"bin {i} aircraft ready fraction", 5e-4)
        mission_spans = [(7, completed_at[0])] if not SEED7 else [(7, completed_at[0]), (19, completed_at[1]), (31, completed_at[2])]
        if not SEED7:
            mission_spans += [(19, 22), (31, 34)]
        mission_fraction = sum(bin_fraction(a, b, i) for a, b in mission_spans)
        near(rec["NSYMA"], mission_fraction, f"bin {i} mission allocation", 5e-4)
        near(rec["NSYA"], expected_ready + mission_fraction, f"bin {i} aircraft available", 5e-4)
        operating_spans = list(zip([8, 20, 32], completed_at if SEED7 else [10, 22, 34]))
        operating_fraction = sum(bin_fraction(a, b, i) for a, b in operating_spans)
        for key in ("NSYMO", "FTMO", "STACC"):
            near(rec[key], operating_fraction, f"bin {i} {key} mission time", 5e-4)
        near(rec["NSYMR"], sum(bin_fraction(a, b, i) for a, b in [(7, 8), (19, 20), (31, 32)]), f"bin {i} mission reserve", 5e-4)
        repair_spans = list(zip(completed_at, ready_at))
        near(rec["NSYRP"], sum(bin_fraction(a, b, i) for a, b in repair_spans), f"bin {i} aircraft replacement", 5e-4)
        near(rec["NSYUA"], sum(bin_fraction(a, b, i) for a, b in repair_spans), f"bin {i} aircraft unavailable", 5e-4)
        near(rec["NFAIL"], sum(int(i == int(t * 2)) for t in failures_at), f"bin {i} failures")
        near(rec["NREPT"], sum(int(i == int(t * 2)) for t in ready_at), f"bin {i} repairs")
        near(rec["NSYDT"], sum(int(i == int(t * 2)) for t in completed_at), f"bin {i} downtime count")
        downtime_events = sum(int(i == int(t * 2)) for t in completed_at)
        if downtime_events:
            near(rec["SYDT"], .5 * downtime_events, f"bin {i} downtime metric")
        else:
            check(rec["SYDT"] is None, f"bin {i} undefined downtime metric without event")
        near(stocks[i]["NDF"], sum(int(i == int(t * 2)) for t in completed_at), f"bin {i} stock demand failures")
        near(stocks[i]["NWT"], sum(int(i == int(t * 2)) for t in completed_at), f"bin {i} stock demand events")
        checked_system = {"UNID", "SID", "STINT", "ETINT", "NSYRY", "NSYMA", "NSYMO", "NSYMR", "NSYUA", "NSYA", "FTMO", "NSYRP", "NREPT", "NFAIL", "STACC", "SYDT", "NSYDT"}
        for key, value in rec.items():
            if key not in checked_system:
                check(value in (0, None), f"bin {i} other system metric {key}")
        for key, value in stocks[i].items():
            if key not in {"STINT", "ETINT", "PNB", "NDF", "NWT", "NBO", "NDD", "NDR", "NDP", "NLD"}:
                check(value in (0, None), f"bin {i} other stock metric {key}")
    check(systems[-1]["NSYRY"] == 1 and systems[-1]["NSYRP"] == 0 and stocks[-1]["NBO"] == 0, "terminal aircraft ready and no backorder")
    result = {
        "schema": "independent-g01-var02-spru-readonly/v1", "case": CASE.name,
        "run_id": RUN_ID, "verdict": "GO" if not failures else "NO-GO",
        "passed": not failures, "check_count": checks, "failures": failures,
        "source_sha256": sha(source_path), "run_closure_sha256": sha(RUN / "closure.json"),
        "native_log_sha256": sha(RUN / "model.log"), "native_report_sha256": sha(RUN / "report-raw.json"),
        "scope": "Observed seed-7 SPRU repair, discard/reorder, and unfinished late repair" if SEED7 else "Observed seed-1 nested SPRU direct-repair branch",
        "limitations": ["No probability or 50/50 frequency inference from two fixed seeds.",
                        "No completed repair claim for SPRU 10 at h36." if SEED7 else "No discard/reorder event in this seed.",
                        "Default report aggregates stock totals; individual physical identity is bound by the native event log."],
    }
    REPORT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks, "failures": failures,
                      "script_sha256": sha(Path(__file__)), "report_sha256": sha(REPORT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()

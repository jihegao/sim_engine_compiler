"""Independent, read-only J08 replay from frozen source and native raw bytes."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
PARENT = ROOT / "F02-var01-var02-integrated-fleet-v1.0.2"
PRECEDENT = ROOT / "I02-var01-in-transfer-v1.0.2"
NATIVE = CASE / "runs/j08-ledger-v100-ssh-20261004-01"
FULL = CASE / "runs/j08-item-full-v100-ssh-20261004-01"
SELECTED = CASE / "runs/j08-item-report-v100-ssh-20261004-01"
OUTPUT = CASE / "review/independent-verdict.json"
failures: list[str] = []
checks = 0


def check(condition: bool, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    data = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", data))


def table(doc, name: str, top: str):
    return next(t for t in doc[top]["tables"] if t["name"] == name)


def rows(doc, name: str, top: str):
    t = table(doc, name, top)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, r)) for inst in t["instances"] for r in inst["rows"]]


def overlap(a: float, b: float, c: float, d: float) -> float:
    return max(0.0, min(b, d) - max(a, c))


def near(a, b, tolerance=1e-4):
    return a is not None and abs(float(a) - float(b)) <= tolerance


def guarded(run: Path, expected_raw: int, expected_steps: int | None = None):
    invocation = load(run / "invocation.json")
    closure = load(run / "closure.json")
    check(sha(run / "invocation.json") == closure["invocation_sha256"], f"{run.name} invocation seal")
    check(closure["run_id"] == invocation["run_id"] == run.name, f"{run.name} identity")
    check(closure["source_hashes_before"] == closure["source_hashes_after"], f"{run.name} stable source")
    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], f"{run.name} SSH0")
    check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{run.name} mutex")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{run.name} GUI")
    check(closure["error"] is None, f"{run.name} closure error")
    check(len(closure["raw"]) == expected_raw, f"{run.name} raw count")
    for name, meta in sorted(closure["raw"].items()):
        p = run / name
        check(p.is_file() and p.stat().st_size == meta["bytes"] and sha(p) == meta["sha256"], f"{run.name}/{name} raw seal")
    if expected_steps is not None:
        steps = load(run / "steps.json")
        check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "native step names")
        for s in steps:
            check(s["status"] == "completed" and s["exit_code"] == 0 and s.get("gui_preserved", True) and s["error"] is None, f"native {s['name']}")
    return invocation, closure


def main():
    contract = load(CASE / "contract.json")
    parent_path = PARENT / "risk-input.json"
    parent_run = PARENT / "runs/f02-pair-v102-risk-ssh-20261004-01"
    sources = {
        "input": CASE / "native-input.json",
        "parent": parent_path,
        "parent_closure": parent_run / "closure.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-10-04.md",
        "report_precedent": PRECEDENT / "cli-scope-signoff-2026-10-02.md",
        "contract": CASE / "contract.json",
        "exact_diff": CASE / "exact-diff.json",
        "build.py": CASE / "build.py",
        "describe_diff.py": CASE / "describe_diff.py",
        "check_roundtrip.py": CASE / "check_roundtrip.py",
        "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
    }
    ni, nc = guarded(NATIVE, 12, 5)
    for key, path in sorted(sources.items()):
        check(sha(path) == nc["source_hashes_before"][key] == ni["source_hashes_before"][key], f"source {key}")
    check(sha(parent_path) == contract["accepted_parent"]["input_sha256"], "parent pin")
    check(sha(CASE / "native-input.json") == contract["child_input_sha256"], "child pin")
    check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "diff pin")
    check((NATIVE / "input.json").read_bytes() == (CASE / "native-input.json").read_bytes(), "native input copy")
    original = load(parent_path)
    child = load(CASE / "native-input.json")
    expected = copy.deepcopy(original)
    item = table(expected, "Item", "model")
    ix = [c["name"] for c in item["columns"]].index("TRACK")
    for row in item["instances"][0]["rows"]:
        if row[0] in ("TEACH-LRU-01", "TEACH-SRU-01"):
            check(row[ix] is None, f"parent {row[0]} untracked")
            row[ix] = "Y"
    table(expected, "ResultCollection", "model")["instances"][0]["rows"].append(["ITEM", 0.5, 0, 60.0, None, None])
    check(child == expected, "complete exact parent-to-child model delta")
    check(set(load(CASE / "exact-diff.json")["changed_tables"]) == {"Item", "ResultCollection"}, "declared diff tables")
    exported = load(NATIVE / "roundtrip-raw.json")
    source_tables = {t["name"]: t for t in child["model"]["tables"]}
    export_tables = {t["name"]: t for t in exported["model"]["tables"]}
    row_tables = 0
    for name, authored in sorted(source_tables.items()):
        if any(i["rows"] for i in authored["instances"]):
            row_tables += 1
            check(export_tables[name] == authored, f"exact populated-table roundtrip {name}")
    check(row_tables == 30, "30 authored row tables")
    check((NATIVE / "model.sxo").stat().st_size > 4, "valid result file")
    run_text = (NATIVE / "run.log").read_text(encoding="utf-8-sig")
    check("Errors: 0, Warnings: 1, Notes: 0" in run_text, "converter counts")
    check("warning #108" in run_text and not re.search(r"\b(error|warning)\s*#(?!108\b)\d+", run_text, re.I), "converter warning classification")
    check((NATIVE / "model.log").read_bytes() == (parent_run / "model.log").read_bytes(), "parent event log parity")
    check((NATIVE / "report-raw.json").read_bytes() == (parent_run / "report-raw.json").read_bytes(), "parent default report parity")

    fi, fc = guarded(FULL, 2)
    si, sc = guarded(SELECTED, 2)
    for run, inv, clo, setting in [
        (FULL, fi, fc, CASE / "runs/report-settings/item-position-results.sxs"),
        (SELECTED, si, sc, CASE / "runs/report-settings/item-position-selected.sxs"),
    ]:
        check(inv["source_run_id"] == NATIVE.name and inv["source_closure_sha256"] == sha(NATIVE / "closure.json"), f"{run.name} source closure")
        check(clo["source_hashes_before"]["sxo"] == sha(NATIVE / "model.sxo"), f"{run.name} SXO pin")
        check(clo["source_hashes_before"]["settings"] == sha(setting), f"{run.name} settings pin")
        check(clo["exit_code"] == 0 and "-rpts" in inv["arguments"] and "-rjexport" in inv["arguments"], f"{run.name} selected report success")
    check(fc["source_hashes_before"]["runner"] == sha(CASE / "run_item_report_full_ssh.ps1"), "full runner source pin")
    selected_report = load(SELECTED / "item-report-raw.json")
    full_report = load(FULL / "item-report-raw.json")
    check("ItemResults" not in [t["name"] for t in selected_report["report"]["tables"]], "selected selector excluded: no item rows")
    check("ItemResults" in [t["name"] for t in full_report["report"]["tables"]], "full selector item rows")
    default_report = load(NATIVE / "report-raw.json")
    for name in ["ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"]:
        check(rows(full_report, name, "report") == rows(default_report, name, "report"), f"full/default {name} row parity")

    log = (NATIVE / "model.log").read_text(encoding="utf-8-sig")
    def has(pattern):
        return re.search(pattern, log, re.M) is not None
    physical = [
        r"Time: 47\.9896 .*Backorder added",
        r"Time: 47\.9896 .*Take replacement item <TEACH-LRU-01,0,2> from stock",
        r"Time: 47\.9896 .*transport task 0 starts with 1 items/systems, transport time: 2",
        r"Time: 49\.9896 .*Replacement item arrives <TEACH-LRU-01,0,2>",
        r"Time: 49\.9896 .*Backorder removed, waiting time was 2",
        r"Time: 50\.9063 .*Put back replacement item <TEACH-LRU-01,0,4> to stock",
    ]
    for pattern in physical:
        check(has(pattern), f"physical {pattern}")
    item_rows = rows(full_report, "ItemResults", "report")
    stock_rows = rows(full_report, "StockTotalResults", "report")
    resource_rows = rows(full_report, "ResourceResults", "report")
    check(len(item_rows) == len(stock_rows) == len(resource_rows) == 120, "120 aligned report bins")
    for i, (ir, sr, rr) in enumerate(zip(item_rows, stock_rows, resource_rows)):
        a, b = i / 2, (i + 1) / 2
        check(ir["IID"] == "TEACH-LRU-01" and ir["STID"] == "DEPOT-01" and ir["STINT"] == a and ir["ETINT"] == b, f"item identity/bin {i}")
        check(ir["STSZ"] == 2 and ir["NBO"] == 0, f"depot nominal and BO {i}")
        check(near(ir["STOHA"], 2 - 2 * overlap(47.9896, 50.9063, a, b)), f"depot on-hand {i}")
        check(ir["NDF"] == int(i == 95) and ir["NWT"] == int(i == 95) and ir["NRP"] == int(i == 101), f"depot issue/return marker {i}")
        check(sr["STINT"] == a and sr["ETINT"] == b, f"stock bin {i}")
        check(near(sr["NBO"], 2 * overlap(47.9896, 49.9896, a, b)), f"base backorder occupancy {i}")
        check(sr["NDF"] == int(i == 95) and sr["NWT"] == int(i == 95), f"stock issue markers {i}")
        check(rr["STINT"] == a and rr["ETINT"] == b and rr["NR"] == 2 and rr["NRA"] == 2, f"resource capacity/bin {i}")

    booked = []
    active = {}
    requested = {}
    waiting = []
    for line in log.splitlines():
        m = re.match(r"Time: ([\d.]+)\s+(.*)", line)
        if not m:
            continue
        t, msg = float(m[1]), m[2]
        r = re.search(r"<(P-CREW|P-MAINT) at <BASE-01,0>> (allocated to|deallocated from)", msg)
        if r:
            if r[2] == "allocated to":
                check(r[1] not in active, f"resource {r[1]} booking overlap at {t}")
                active[r[1]] = t
            else:
                check(r[1] in active, f"resource {r[1]} released after booking at {t}")
                if r[1] in active:
                    booked.append((active.pop(r[1]), t))
        q = re.search(r"subtask (\d+) seqno .* requests resources$", msg)
        if q:
            requested[q[1]] = t
        got = re.search(r"subtask (\d+) seqno .* resource received$", msg)
        if got and got[1] in requested:
            waiting.append((requested.pop(got[1]), t))
    check(not active and len(booked) == 13, "13 closed resource leases")
    positive_wait = [(a, b) for a, b in waiting if b > a]
    check(len(positive_wait) == 4, "four positive queued requests")
    check(near(sum(b-a for a, b in booked), 8, 1e-4), "eight booked resource-hours")
    check(near(sum(b-a for a, b in positive_wait), 2.5, 1e-6), "2.5 waiting resource-hours")
    for i, rr in enumerate(resource_rows):
        a, b = i/2, (i+1)/2
        use = sum(overlap(x, y, a, b) for x, y in booked) * 2
        wait = sum(overlap(x, y, a, b) for x, y in positive_wait) * 2
        check(near(rr["NRUM"], use, 1.2e-4), f"booked resource bin {i}")
        check(near(rr["NRW"], wait, 1e-6), f"waiting resource bin {i}")
    it = rows(full_report, "ItemResultsTotal", "report")[0]
    rt = rows(full_report, "ResourceResultsTotal", "report")[0]
    check(near(it["STOHA"], 2 - (50.9063-47.9896)/60, 1e-4) and it["STSZ"] == 2 and it["NBO"] == 0, "item horizon mean vs nominal")
    check(near(rt["NRUM"] * 60, 8) and near(rt["NRW"] * 60, 2.5), "resource horizon integrals")
    check(item_rows[-1]["STOHA"] == 2 and stock_rows[-1]["NBO"] == 0 and resource_rows[-1]["NRW"] == 0 and resource_rows[-1]["NRUM"] == 0, "terminal item/stock/resource ledger")
    check(has(r"Time: 5[01]\.[\d]+ .*System ready <TEACH-AIR-01,0>"), "repaired aircraft ready")
    summary = rows(full_report, "ResultSummary", "report")[0]
    check(summary["NREP"] == 1 and summary["RTIUP"] == 60 and near(summary["MSTF"], .75) and near(summary["MSUF"], .5), "one-rep summary outcome")

    result = {
        "case": "J08-item-stock-resource-ledger-v1.0.0",
        "passed": not failures,
        "verdict": "GO — bounded J08 item/stock/resource ledger observation" if not failures else "NO-GO",
        "checks_passed": checks-len(failures), "checks_total": checks, "failures": failures,
        "evidence": {
            "native_closure_sha256": sha(NATIVE / "closure.json"),
            "full_report_closure_sha256": sha(FULL / "closure.json"),
            "excluded_selected_closure_sha256": sha(SELECTED / "closure.json"),
            "native_report_sha256": sha(NATIVE / "report-raw.json"),
            "full_report_sha256": sha(FULL / "item-report-raw.json"),
            "depot_lru_stock_issue_hour": 47.9896, "depot_lru_stock_return_hour": 50.9063,
            "base_backorder_hours": 2, "resource_booked_hours": 8, "resource_waiting_hours": 2.5,
        },
        "limits": [
            "One seed, one tracked LRU/depot ItemResults position, one sixty-hour horizon; J08 as a whole remains open.",
            "Selected-selector export is an excluded diagnostic because it contains no ItemResults; full-selector report is the accepted observation.",
            "ItemResultsTotal.STOHA is a time mean, not terminal physical stock; depot ItemResults.NBO=0 does not contradict the BASE-01 backorder in StockTotalResults.",
            "ResourceResults.NRA is not interpreted as the free-worker complement of NRUM; booked and queued work are checked from event intervals.",
            "Native model.log uses rounded time text; occupancy checks allow 0.00012 resource or stock units for boundary rounding.",
        ],
    }
    OUTPUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks_passed": result["checks_passed"], "checks_total": checks, "failures": failures}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

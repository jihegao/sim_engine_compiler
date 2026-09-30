"""Independent, read-only replay of the sealed C10.var05 five-hour pair.

Uses only Python's standard library. It does not import case author code or run SIMLOX.
The sole output is the adjacent deterministic JSON review artifact.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
AIR = CASE.parent
ROOT = CASE.parents[2]
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
RUNS = {
    "five-hour-control": "c10-mission-five-hour-control-20260930-01",
    "five-hour-failure": "c10-mission-five-hour-failure-20260930-01",
}
EXPECTED = {
    "parent": "d2ea6e874eff82f1e50f271051010985c28adfba7aab94d2a0a0b343b989e865",
    "control": "cd3a757cda6464584a8edd4542533019068551fc8bab47e6fe0058cb3785a00c",
    "failure": "876abeefe8bea39458bc93f3f809c88e9c97e03adf47cbbeff607f994f543396",
}
checks: list[dict] = []


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path):
    # SIMLOX's exporter uses trailing commas. Remove only commas outside strings.
    s = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = escaped = False
    for i, ch in enumerate(s):
        if quoted:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
            out.append(ch)
        elif ch == "," and re.match(r"\s*[}\]]", s[i + 1:]):
            continue
        else:
            out.append(ch)
    return json.loads("".join(out))


def check(name: str, ok: bool, detail=None):
    checks.append({"name": name, "pass": bool(ok), "detail": detail})


def table_map(doc, outer="model"):
    return {t["name"]: t for t in doc[outer]["tables"]}


def rows(table):
    return [(inst.get("instance_name", ""), row)
            for inst in table["instances"] for row in inst.get("rows", [])]


def populated(doc, outer="model"):
    return {n: rows(t) for n, t in table_map(doc, outer).items() if rows(t)}


def values(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for _, row in rows(table)]


def near(a, b, tol=2e-5):
    return a is not None and math.isclose(float(a), float(b), rel_tol=0, abs_tol=tol)


def occupancy(start, end, lo, hi):
    return max(0.0, min(end, hi) - max(start, lo)) / (hi - lo)


def report_table(report, name):
    return values(table_map(report, "report")[name])


parent_path = AIR / "C05-mission-resource-v1.0.0" / "capacity-2-input.json"
files = {
    "parent": parent_path,
    "control": CASE / "five-hour-control-input.json",
    "failure": CASE / "five-hour-failure-input.json",
}
source_sha = {k: sha(v) for k, v in files.items()}
for k in EXPECTED:
    check(f"frozen_{k}_sha", source_sha[k] == EXPECTED[k], source_sha[k])

parent, control, failure = (load(files[k]) for k in ("parent", "control", "failure"))
contract = load(CASE / "contract.json")
diff = load(CASE / "exact-diff.json")
check("contract_parent_and_inputs", contract["parent_input_sha256"] == EXPECTED["parent"]
      and contract["input_sha256"] == {"five-hour-control": EXPECTED["control"],
                                      "five-hour-failure": EXPECTED["failure"]})
check("diff_parent_and_inputs", diff["parent_input_sha256"] == EXPECTED["parent"]
      and diff["control_input_sha256"] == EXPECTED["control"]
      and diff["failure_input_sha256"] == EXPECTED["failure"])


def changed_cells(a, b):
    x, y = table_map(a), table_map(b)
    changed = []
    for name in sorted(set(x) | set(y)):
        if name not in x or name not in y:
            changed.append((name, "table added" if name in y else "table removed"))
            continue
        if x[name]["columns"] != y[name]["columns"]:
            changed.append((name, "columns"))
        ar, br = rows(x[name]), rows(y[name])
        if len(ar) != len(br):
            changed.append((name, f"rows {len(ar)}->{len(br)}"))
        for ri, (aa, bb) in enumerate(zip(ar, br)):
            if aa[0] != bb[0]:
                changed.append((name, f"instance[{ri}]"))
            for ci, (av, bv) in enumerate(zip(aa[1], bb[1])):
                if av != bv:
                    changed.append((name, f"{x[name]['columns'][ci]['name']}[{ri}]"))
    return changed


pc = changed_cells(parent, control)
cf = changed_cells(control, failure)
check("exact_parent_to_control_delta", pc == [
    ("MissionType", "DESCR[0]"), ("MissionType", "DURN[0]"),
    ("ProblemDescription", "PDESC[0]")], pc)
check("exact_control_to_failure_delta", cf == [
    ("ProblemDescription", "PDESC[0]"), ("ResourceStationData", "table added")], cf)
check("failure_resource_fault_parameters", values(table_map(failure)["ResourceStationData"]) == [{
    "RID": "MISSION-CREW", "STID": "BASE-01", "PRICE": None, "SUSTC": None,
    "MUTILF": None, "RMTBF": 3.0, "RFTT": "OPERATION", "RMDT": 0.25,
    "RMDTD": None, "SHPID": None, "NOTE": None}])
check("matched_five_hour_scenario", values(table_map(control)["MissionType"])[0]["DURN"] == 5.0
      and values(table_map(failure)["MissionType"])[0]["DURN"] == 5.0
      and values(table_map(control)["ResourceAllocation"])[0]["RQTY"] == 2
      and values(table_map(failure)["ResourceAllocation"])[0]["RQTY"] == 2)

review_runs = {}
for variant, run_id in RUNS.items():
    rd = CASE / "runs" / run_id
    inv, closure, steps = (load(rd / f) for f in ("invocation.json", "closure.json", "steps.json"))
    source = files["control" if variant.endswith("control") else "failure"]
    expected_count = 16 if variant.endswith("control") else 17
    check(f"{variant}_invocation_identity", inv["variant"] == variant
          and inv["run_id"] == run_id and inv["input_sha256"] == sha(source)
          and inv["parent_sha256"] == EXPECTED["parent"])
    check(f"{variant}_ssh_gui_queue", inv["execution_mode"] == "ssh_cli_v1"
          and inv["session_id"] == 0 and inv["ssh_connection_present"] is True
          and "sshd.exe" in inv["ssh_ancestor_names"]
          and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
          and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    check(f"{variant}_five_steps", [s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"]
          and all(s["exit_code"] == 0 and s["status"] == "completed"
                  and s["gui_preserved"] is True for s in steps))
    check(f"{variant}_closure_invocation", closure["run_id"] == run_id
          and closure["invocation_sha256"] == sha(rd / "invocation.json")
          and closure["error"] is None)
    check(f"{variant}_source_seal", inv["source_hashes_before"] ==
          closure["source_hashes_before"] == closure["source_hashes_after"]
          and inv["source_hashes_before"]["input"] == sha(source)
          and inv["source_hashes_before"]["parent"] == EXPECTED["parent"]
          and inv["source_hashes_before"]["contract"] == sha(CASE / "contract.json")
          and inv["source_hashes_before"]["builder"] == sha(CASE / "build.py")
          and inv["source_hashes_before"]["checker"] == sha(CASE / "check_roundtrip.py")
          and inv["source_hashes_before"]["runner_script"] == sha(CASE / "run_native_ssh.ps1"))
    raw_bad = []
    for name, seal in closure["raw"].items():
        path = rd / name
        if not path.is_file() or path.stat().st_size != seal["bytes"] or sha(path) != seal["sha256"]:
            raw_bad.append(name)
    check(f"{variant}_twelve_raw_seals", len(closure["raw"]) == 12 and not raw_bad,
          {"count": len(closure["raw"]), "bad": raw_bad})
    check(f"{variant}_run_input_copy", sha(rd / "input.json") == sha(source))
    raw_source = native_json(rd / "roundtrip-raw.json")
    a, b = table_map(load(source)), table_map(raw_source)
    # Empty/all-null source placeholders acquire native defaults on export.
    # The 16/17 actual row-containing business tables must roundtrip exactly.
    row_bad = [n for n, t in a.items() if n in populated(load(source))
               and (n not in b or rows(t) != rows(b[n])
                    or t["columns"] != b[n]["columns"])]
    check(f"{variant}_exact_source_roundtrip", not row_bad and len(populated(load(source))) == expected_count,
          {"row_containing_source_tables": len(populated(load(source))), "bad_tables": row_bad})
    check(f"{variant}_conversion_zero_errors", "Errors: 0, Warnings: 2" in (rd / "run.log").read_text(errors="replace")
          and (rd / "model.sxo").stat().st_size > 1000)
    report = native_json(rd / "report-raw.json")
    sysrows = report_table(report, "SystemResults")
    stock = report_table(report, "StockTotalResults")
    resource = report_table(report, "ResourceResults")
    summary = report_table(report, "ResultSummary")[0]
    totals = report_table(report, "ResourceResultsTotal")[0]
    check(f"{variant}_report_bins", len(sysrows) == len(stock) == len(resource) == 72
          and all(near(r["STINT"], i / 2) and near(r["ETINT"], (i + 1) / 2)
                  for rr in (sysrows, stock, resource) for i, r in enumerate(rr)))
    failed = variant.endswith("failure")
    ret = 12.904970943927765 if failed else 13.0
    ftime = 11.654970943927765
    repaired = 13.154970943927765
    expected = {
        "NSYRY": lambda lo, hi: 2 * (occupancy(0, 7, lo, hi) + occupancy(ret, 36, lo, hi)),
        "NSYMA": lambda lo, hi: 2 * occupancy(7, ret, lo, hi),
        "NSYMR": lambda lo, hi: 2 * occupancy(7, 8, lo, hi),
        "NSYMO": lambda lo, hi: 2 * occupancy(8, ret, lo, hi),
        "STACC": lambda lo, hi: 2 * occupancy(8, ret, lo, hi),
        "FTMO": lambda lo, hi: occupancy(8, ret, lo, hi),
    }
    sys_bad = []
    for i, row in enumerate(sysrows):
        lo, hi = i / 2, (i + 1) / 2
        for key, fn in expected.items():
            if not near(row[key], fn(lo, hi)):
                sys_bad.append((i, key, row[key], fn(lo, hi)))
        if not near(row["NFAIL"], 0):
            sys_bad.append((i, "NFAIL", row["NFAIL"], 0))
    check(f"{variant}_all_system_bin_occupancies", not sys_bad, sys_bad[:6])
    res_bad = []
    for i, row in enumerate(resource):
        lo, hi = i / 2, (i + 1) / 2
        rf = occupancy(ftime, repaired, lo, hi) if failed else 0
        exp = {"NR": 2, "NRMA": 2 * occupancy(7, 8, lo, hi),
               "NRMO": occupancy(8, ftime if failed else 13, lo, hi)
               + occupancy(8, ret, lo, hi), "NRF": rf, "NRA": 2 - rf,
               "NRUM": 0, "NRW": 0}
        for key, value in exp.items():
            if not near(row[key], value):
                res_bad.append((i, key, row[key], value))
    check(f"{variant}_all_resource_bin_occupancies", not res_bad, res_bad[:6])
    stock_bad = [(i, k, row[k]) for i, row in enumerate(stock)
                 for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")
                 if not near(row[k], 0)]
    check(f"{variant}_stock_ledger_zero", not stock_bad, stock_bad[:6])
    check(f"{variant}_summary", summary["NREP"] == 1 and near(summary["RTIUP"], 36)
          and summary["MSTF"] == 1 and summary["MSUF"] == (0 if failed else 1)
          and near(summary["MTMF"], (ret - 8) / 5)
          and near(summary["STMF"], (ret - 8) / 5))
    check(f"{variant}_resource_total_integrals", near(totals["NRMO"] * 36,
          8.55994188785553 if failed else 10) and near(totals["NRF"] * 36,
          1.5 if failed else 0) and near(totals["NRMA"] * 36, 2))
    check(f"{variant}_terminal_ledgers", near(sysrows[-1]["NSYRY"], 2)
          and near(sysrows[-1]["NSYMO"], 0) and near(resource[-1]["NR"], 2)
          and near(resource[-1]["NRA"], 2) and near(resource[-1]["NRF"], 0))
    log = (rd / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    if failed:
        phrases = ["Time: 11.655", "MISSION-CREW at <BASE-01,0>> Failed",
                   "resource failure on MISSION-CREW when on mission",
                   "<TEACH-AIR-01,0> aborts its mission", "mission aborted:",
                   "Time: 12.905", "Time: 13.155", "MISSION-CREW at <BASE-01,0>> Repaired"]
        check("failure_event_chain", all(p in log for p in phrases),
              [p for p in phrases if p not in log])
        check("failure_one_fault_and_one_repair", log.count("resource failure on MISSION-CREW when on mission") == 1
              and log.count("MISSION-CREW at <BASE-01,0>> Failed") == 1
              and log.count("MISSION-CREW at <BASE-01,0>> Repaired") == 1)
        check("failure_both_aircraft_return", log.count("Time: 12.905 <TEACH-AIR-01,BASE-01,0> System arrives") == 2
              and "mission aborted: <TEACH-AIR-01,1>" in log)
    else:
        check("control_success_events", "Time: 13" in log and "mission success:" in log.lower()
              and "mission aborted" not in log.lower() and "resource failure" not in log.lower())
    review_runs[variant] = {
        "run_id": run_id, "closure_sha256": sha(rd / "closure.json"),
        "report_sha256": sha(rd / "report-raw.json"),
        "summary": {k: summary[k] for k in ("NREP", "MTMF", "MSTF", "MSUF", "STMF")},
        "integrals": {k: sum(float(r[k] or 0) * 0.5 for r in resource)
                      for k in ("NRMO", "NRMA", "NRF", "NRW")},
    }

result = {
    "schema": "c10-var05-independent-readonly-review/v1",
    "reviewer": "independent static/raw reviewer; no author validator imports",
    "decision": "GO" if all(c["pass"] for c in checks) else "NO-GO",
    "passed": sum(c["pass"] for c in checks), "total": len(checks),
    "checks": checks, "source_sha256": source_sha, "runs": review_runs,
    "scope": "One fixed-seed, five-hour, two-aircraft formation with two mission crew. The in-flight crew failure aborts the formation; aircraft operating occupancy continues until return. Resource repair completion at 13.155 is 0.25 hour after return, not 0.25 hour after failure.",
    "limitations": [
        "Session, SSH ancestry, mutex and GUI preservation are attested by sealed runner records; this review did not observe the live desktop.",
        "The failed crew's exact repair-task start is not directly reported; the 12.905-to-13.155 interval is consistent with RMDT=0.25.",
        "No frequency, independence or general resource-failure policy is inferred from one seed.",
        "Native report uses half-hour bin averages; a last-bin average alone is not a point-in-time terminal event.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(f"{result['decision']} {result['passed']}/{result['total']}")
print(f"script_sha256={sha(Path(__file__))}")
print(f"report_sha256={sha(OUT)}")

"""Independent standard-library replay of the frozen F03.var01 native pair."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
PARENT = ROOT / "F02-var01-var02-integrated-fleet-v1.0.2"
STAFF = CASE / "runs/f03-v101-staffed-ssh-20261004-01"
ZERO = CASE / "runs/f03-v101-unstaffed-ssh-20261004-01"
OUT = CASE / "review/independent-verdict.json"
failures: list[str] = []
checks = 0


def check(ok, label):
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", p.read_text(encoding="utf-8-sig")))


def table(doc, name, root):
    return next(t for t in doc[root]["tables"] if t["name"] == name)


def rows(doc, name, root):
    t = table(doc, name, root)
    keys = [c["name"] for c in t["columns"]]
    return [dict(zip(keys, r)) for instance in t["instances"] for r in instance["rows"]]


def overlap(x, y, a, b):
    return max(0.0, min(y, b) - max(x, a))


def near(x, y, tol=1e-4):
    return x is not None and abs(float(x) - float(y)) <= tol


def events(run):
    text = (run / "model.log").read_text(encoding="utf-8-sig")
    return text, [(float(m[1]), m[2]) for line in text.splitlines() if (m := re.match(r"Time: ([\d.]+)\s+(.*)", line))]


def native(run):
    inv, clo = load(run / "invocation.json"), load(run / "closure.json")
    check(sha(run / "invocation.json") == clo["invocation_sha256"], f"{run.name} invocation seal")
    check(inv["run_id"] == clo["run_id"] == run.name, f"{run.name} ID")
    check(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"], f"{run.name} SSH0")
    check(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{run.name} mutex")
    check(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, f"{run.name} GUI")
    check(clo["source_hashes_before"] == clo["source_hashes_after"] and clo["error"] is None, f"{run.name} source stability")
    check(len(clo["raw"]) == 12, f"{run.name} 12 raw files")
    for key, info in sorted(clo["raw"].items()):
        p = run / key
        check(p.is_file() and p.stat().st_size == info["bytes"] and sha(p) == info["sha256"], f"{run.name}/{key} raw seal")
    steps = load(run / "steps.json")
    check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{run.name} step sequence")
    for s in steps:
        check(s["status"] == "completed" and s["exit_code"] == 0 and s["error"] is None and s.get("gui_preserved", True), f"{run.name} {s['name']} success")
    conv = (run / "run.log").read_text(encoding="utf-8-sig")
    check("Errors: 0, Warnings: 1, Notes: 0" in conv and "warning #108" in conv, f"{run.name} converter")
    check(not re.search(r"\b(error|warning)\s*#(?!108\b)\d+", conv, re.I), f"{run.name} no extra diagnostic")
    check((run / "model.sxo").stat().st_size > 4, f"{run.name} valid SXO")
    return inv, clo


def lease_and_wait(log, zero_crew):
    active = {}
    booked = []
    requested = {}
    wait = []
    for t, msg in log:
        m = re.search(r"<(P-CREW|P-MAINT) at <(BASE-01|BASE-02),0>> (allocated to|deallocated from)", msg)
        if m:
            key = (m[2], m[1])
            if m[3] == "allocated to":
                check(key not in active, f"overlapping booking {key} h{t}")
                active[key] = t
            else:
                check(key in active, f"unmatched release {key} h{t}")
                if key in active:
                    booked.append((key, active.pop(key), t))
        req = re.search(r"subtask (\d+) seqno .* requests resources$", msg)
        if req:
            requested[req[1]] = t
        got = re.search(r"subtask (\d+) seqno .* resource received$", msg)
        if got and got[1] in requested:
            wait.append((requested.pop(got[1]), t))
    check(not active, "all physical resource bookings released")
    # The zero-capacity BASE-02 request has no resource-received event; it expires with mission cancellation.
    if zero_crew:
        check(any(abs(t-7) < 1e-6 for t in requested.values()), "zero-crew h7 request unresolved")
        wait.append((7.0, 8.5))
    return booked, [(a, b) for a, b in wait if b > a]


def main():
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    parent_file = PARENT / "deterministic-input.json"
    parent_run = PARENT / "runs/f02-pair-v102-det-ssh-20261004-01"
    sources = {
        "staffed": CASE / "staffed-input.json", "unstaffed": CASE / "unstaffed-input.json",
        "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
        "parent": parent_file, "parent_closure": parent_run / "closure.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-10-04.md",
        "A17_input": ROOT / "A17-multi-unit-group-v1.0.0/native-input.json",
        "A17_signoff": ROOT / "A17-multi-unit-group-v1.0.0/cli-scope-signoff-2026-09-29.md",
        "E07_signoff": ROOT / "E07-item-specific-transport-v1.0.1/cli-scope-signoff-2026-10-01.md",
        "I01_signoff": ROOT / "I01-var01-resource-points-v1.0.0/cli-scope-signoff-2026-10-02.md",
        "build.py": CASE / "build.py", "describe_diff.py": CASE / "describe_diff.py",
        "check_roundtrip.py": CASE / "check_roundtrip.py", "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
    }
    observed = {}
    for arm, run in [("staffed", STAFF), ("unstaffed", ZERO)]:
        inv, clo = native(run)
        for key, p in sorted(sources.items()):
            check(sha(p) == clo["source_hashes_before"][key] == inv["source_hashes_before"][key], f"{arm} source pin {key}")
        check((run / "input.json").read_bytes() == (CASE / f"{arm}-input.json").read_bytes(), f"{arm} frozen input copy")
        authored = load(CASE / f"{arm}-input.json")
        exported = load(run / "roundtrip-raw.json")
        exported_by_name = {t["name"]: t for t in exported["model"]["tables"]}
        count = 0
        for t in authored["model"]["tables"]:
            if any(i["rows"] for i in t["instances"]):
                count += 1
                check(t == exported_by_name[t["name"]], f"{arm} roundtrip {t['name']}")
        check(count == 30, f"{arm} 30 authored row tables")
        report = load(run / "report-raw.json")
        logtext, log = events(run)
        observed[arm] = {"source": authored, "report": report, "text": logtext, "events": log, "run": run}
    check(sha(parent_file) == contract["accepted_parent"]["input_sha256"], "accepted parent SHA")
    check(sha(CASE / "staffed-input.json") == contract["inputs_sha256"]["staffed"], "staffed SHA")
    check(sha(CASE / "unstaffed-input.json") == contract["inputs_sha256"]["unstaffed"], "unstaffed SHA")
    check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "exact diff SHA")
    parent = load(parent_file)
    staff = observed["staffed"]["source"]
    zero = observed["unstaffed"]["source"]
    parent_tables = {t["name"]: t for t in parent["model"]["tables"]}
    staff_tables = {t["name"]: t for t in staff["model"]["tables"]}
    changes = set()
    appended = 0
    for name, pt in sorted(parent_tables.items()):
        ct = staff_tables[name]
        if pt != ct:
            changes.add(name)
            check(pt["columns"] == ct["columns"], f"{name} inherited columns")
            if name != "ProblemDescription":
                a = pt["instances"][0]["rows"]
                b = ct["instances"][0]["rows"]
                check(b[:len(a)] == a and len(b) > len(a), f"{name} parent rows then additions")
                appended += len(b)-len(a)
    check(changes == set(diff["parent_changed_tables"]) and len(changes) == 14, "exact 14-table parent delta")
    check(appended == 14, "fourteen physical/model rows appended")
    expected_zero = copy.deepcopy(staff)
    table(expected_zero, "ProblemDescription", "model")["instances"][0]["rows"] = table(zero, "ProblemDescription", "model")["instances"][0]["rows"]
    alloc = table(expected_zero, "ResourceAllocation", "model")
    rkeys = [c["name"] for c in alloc["columns"]]
    qty = rkeys.index("RQTY")
    chosen = [r for r in alloc["instances"][0]["rows"] if r[rkeys.index("RID")] == "P-CREW" and r[rkeys.index("STID")] == "BASE-02"]
    check(len(chosen) == 1 and chosen[0][qty] == 1, "unique staffed BASE-02 crew row")
    chosen[0][qty] = 0
    check(expected_zero == zero, "whole-model pair differs only crew capacity and description")
    check(set(diff["pair_changed_tables"]) == {"ProblemDescription", "ResourceAllocation"}, "pair diff declaration")

    base1 = []
    reports = {}
    for arm in ("staffed", "unstaffed"):
        o = observed[arm]
        log = o["events"]
        text = o["text"]
        def event(t, pattern):
            return any(abs(time-t) < 1e-4 and re.search(pattern, msg) for time, msg in log)
        checks_local = [
            (7, r"BASE2-MISSION,TEACH-UNIT-2,0,0,0> mission allocates system: <TEACH-AIR-01,2>"),
            (7, r"<TEACH-AIR-01,2> preparation started"),
            (24, r"<P-MAINT at <BASE-02,0>> allocated to maintenance task"),
            (25, r"<P-MAINT at <BASE-02,0>> deallocated from"),
            (49, r"<P-MAINT at <BASE-02,0>> allocated to maintenance task"),
            (50, r"<P-MAINT at <BASE-02,0>> deallocated from"),
            (60, r"resource shift 3 ended at <P-CREW at <BASE-02,0>>"),
        ]
        for t, pattern in checks_local:
            check(event(t, pattern), f"{arm} event h{t} {pattern}")
        if arm == "staffed":
            local = [(7, r"<P-CREW at <BASE-02,0>> allocated"), (7.5, r"<P-CREW at <BASE-02,0>> deallocated"),
                     (7.5, r"<TEACH-AIR-01,2> preparation ended"), (8, r"BASE2-MISSION.*mission starting, duration: 2"),
                     (10, r"BASE2-MISSION.*mission success"), (10, r"BASE2-MISSION.*mission completed: <TEACH-AIR-01,2>"),
                     (11, r"System ready <TEACH-AIR-01,2>")]
            check(not re.search(r"BASE2-MISSION.*mission cancelled", text), "staffed no local cancellation")
        else:
            local = [(8.5, r"BASE2-MISSION.*mission cancelled"), (8.5, r"System ready <TEACH-AIR-01,2>")]
            check("Availability test on  <P-CREW at <BASE-02,0>> request for: 1 failed" in text, "zero-crew availability test failed")
            check(not re.search(r"BASE2-MISSION.*mission starting", text), "zero crew no local launch")
            check(not re.search(r"<P-CREW at <BASE-02,0>> allocated to maintenance task", text), "zero crew no lease")
        for t, pattern in local:
            check(event(t, pattern), f"{arm} local event h{t} {pattern}")
        base1_lines = [(t, msg) for t, msg in log if re.search(r"<(RISK-MISSION|BASIC-MISSION),TEACH-UNIT,0,0,[1-4]> (mission starting|mission success|mission completed)", msg)]
        base1.append(base1_lines)
        check(len([1 for _,msg in base1_lines if "mission starting" in msg]) == 4, f"{arm} BASE-01 four starts")
        check(len([1 for _,msg in base1_lines if "mission success" in msg]) == 4, f"{arm} BASE-01 four successes")
        check(len([1 for _,msg in base1_lines if "mission completed" in msg]) == 4, f"{arm} BASE-01 four completions")
        check(all("TEACH-AIR-01,2" not in msg for _,msg in base1_lines), f"{arm} BASE-01 aircraft isolation")
        check(event(28.5, r"<P-MAINT at <BASE-01,0>> allocated") and event(53.5, r"<P-MAINT at <BASE-01,0>> allocated"), f"{arm} BASE-01 PM worker timing")
        check(not re.search(r"Backorder added|Take replacement item .* from stock|Item demand arrives", text), f"{arm} no stock demand")
        r = o["report"]
        system = rows(r, "SystemResults", "report")
        stock = rows(r, "StockTotalResults", "report")
        resource = rows(r, "ResourceResults", "report")
        summary = rows(r, "ResultSummary", "report")[0]
        rt = rows(r, "ResourceResultsTotal", "report")[0]
        reports[arm] = (system, stock, resource, summary, rt)
        check(len(system) == len(stock) == len(resource) == 120, f"{arm} 120 bins")
        booked, waiting = lease_and_wait(log, arm == "unstaffed")
        check(near(sum(y-x for _,x,y in booked), 10.5 if arm == "staffed" else 10), f"{arm} booked resource-hours")
        check(near(sum(y-x for x,y in waiting), 3 if arm == "staffed" else 4.5), f"{arm} waiting resource-hours")
        for i,(sy,st,rs) in enumerate(zip(system,stock,resource)):
            a,b=i/2,(i+1)/2
            check(sy["STINT"] == st["STINT"] == rs["STINT"] == a and sy["ETINT"] == st["ETINT"] == rs["ETINT"] == b, f"{arm} aligned bin {i}")
            check(near(sy["NSYA"] + sy["NSYUA"], 3, 1e-4), f"{arm} three aircraft conserved bin {i}")
            check(st["NBO"] == 0 and st["NDF"] == 0 and st["NWT"] == 0, f"{arm} no stock movement bin {i}")
            check(rs["NR"] == (4 if arm == "staffed" else 3), f"{arm} resource pool bin {i}")
            use = 2*sum(overlap(x,y,a,b) for _,x,y in booked)
            wait = 2*sum(overlap(x,y,a,b) for x,y in waiting)
            check(near(rs["NRUM"],use,1.2e-4), f"{arm} lease occupancy bin {i}")
            check(near(rs["NRW"],wait,1.2e-4), f"{arm} queue occupancy bin {i}")
        check(near(rt["NRUM"]*60,10.5 if arm=="staffed" else 10) and near(rt["NRW"]*60,3 if arm=="staffed" else 4.5), f"{arm} resource totals")
        check(near(summary["MSTF"],1 if arm=="staffed" else .8) and near(summary["MSUF"],1 if arm=="staffed" else .8), f"{arm} mission summary")
        check(near(system[-1]["NSYRY"],3) and stock[-1]["NBO"]==0 and resource[-1]["NRUM"]==0 and resource[-1]["NRW"]==0, f"{arm} terminal ready/stock/crew")
    check(base1[0] == base1[1], "BASE-01 mission lifecycle byte-level line parity")
    sys_a,stock_a,res_a,_,_ = reports["staffed"]
    sys_b,stock_b,res_b,_,_ = reports["unstaffed"]
    check(stock_a == stock_b, "all stock report rows pair parity")
    expected_system_delta = {
        "NSYMP": {15,16}, "NSYMR": {15}, "NPSUC": {15}, "NSYMO": {16,17,18,19},
        "FTMO": {16,17,18,19}, "STACC": {16,17,18,19}, "NSYRY": {17,18,19,20,21},
        "NSYMA": {17,18,19,20,21}, "NSYMT": {20,21},
    }
    actual_system_delta = {key:{i for i,(a,b) in enumerate(zip(sys_a,sys_b)) if a[key]!=b[key]} for key in sys_a[0]}
    check({k:v for k,v in actual_system_delta.items() if v} == expected_system_delta, "system report difference confined to local mission chronology")
    for i,(a,b) in enumerate(zip(res_a,res_b)):
        check(a["NR"]-b["NR"] == a["NRA"]-b["NRA"] == 1, f"crew capacity difference bin {i}")
        check(near(a["NRUM"]-b["NRUM"], int(i==14)), f"crew usage difference bin {i}")
        check(near(b["NRW"]-a["NRW"], int(i in (14,15,16))), f"crew waiting difference bin {i}")
    result = {
        "case":"F03-var01-two-base-crew-v1.0.0", "passed":not failures,
        "verdict":"GO — bounded two-base crew-capacity contrast" if not failures else "NO-GO",
        "checks_passed":checks-len(failures), "checks_total":checks, "failures":failures,
        "evidence":{"staffed_closure_sha256":sha(STAFF/"closure.json"),"unstaffed_closure_sha256":sha(ZERO/"closure.json"),
                    "staffed_report_sha256":sha(STAFF/"report-raw.json"),"unstaffed_report_sha256":sha(ZERO/"report-raw.json"),
                    "staffed_base02_mission":"success h8–10", "unstaffed_base02_mission":"cancel h8.5 after h7 crew request failure",
                    "resource_booked_hours":{"staffed":10.5,"unstaffed":10},
                    "resource_waiting_hours":{"staffed":3,"unstaffed":4.5}},
        "limits":["One fixed seed, two bases, three aircraft and one BASE-02 crew capacity field; no larger-network or location/stock configuration inference.",
                  "ResourceResults is aggregate across both bases; per-base leases and waits are reconstructed from typed event lines, not reported as separate base rows.",
                  "ResourceResults.NRA is not treated as the free-worker complement of booked NRUM.",
                  "Report bins are half-hour averages; exact same-time ordering inside a bin is not inferred from the aggregate table."],
    }
    OUT.write_bytes((json.dumps(result,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({k:result[k] for k in ("verdict","checks_passed","checks_total","failures")},indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

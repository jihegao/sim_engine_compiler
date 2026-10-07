"""Frozen, read-only C05.var03 native result gate. No SIMLOX invocation."""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

from check_roundtrip import INPUT_SHA, parse

HERE = Path(__file__).resolve().parent
CONTRACT_SHA = "cc3aa75b3c4f6cec8fff57c0de28abf9ed552f4c0bc836e581295856ca30f283"
RUN_IDS = {"crew": "c05-var03-v101-crew-ssh-20261007-01",
           "radio": "c05-var03-v101-radio-ssh-20261007-01"}
SHAPES = {"ProblemDescription": (1, 1), "ResultSummary": (1, 11),
          "SystemResults": (72, 40), "StockTotalResults": (72, 16),
          "ResourceResults": (72, 16), "ResourceResultsTotal": (1, 14)}
ROOT = HERE.parent
C05_POS = ROOT / "C05-mission-resource-v1.0.0/runs/c05-capacity-2-20260930-01/report-raw.json"
C05_NEG = ROOT / "C05-mission-resource-v1.0.0/runs/c05-capacity-1-20260930-01/report-raw.json"
A16 = ROOT / "A16-two-config-reconfiguration-v1.0.0/runs/a16-two-config-v100-20261001-01/report-raw.json"


class Gate:
    def __init__(self):
        self.checks = 0
        self.failures: list[str] = []

    def check(self, yes: bool, label: str) -> None:
        self.checks += 1
        if not yes:
            self.failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def near(a, b, tol=3e-5):
    if isinstance(a, (int, float)) and not isinstance(a, bool) and isinstance(b, (int, float)) and not isinstance(b, bool):
        return math.isfinite(a) and abs(a - b) <= tol
    return type(a) is type(b) and a == b


def overlap(a: float, b: float, c: float, d: float) -> float:
    return max(0.0, min(b, d) - max(a, c))


def report_tables(path: Path) -> dict:
    tables = parse(path)["report"]["tables"]
    assert len(tables) == len({t["name"] for t in tables})
    return {t["name"]: t for t in tables}


def col(table: dict, name: str) -> int:
    return [c["name"] for c in table["columns"]].index(name)


def rows(table: dict) -> list[list]:
    assert len(table["instances"]) == 1
    return table["instances"][0]["rows"]


def records(path: Path) -> list[tuple[float, str]]:
    result = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        m = re.match(r"Time:\s*([0-9.eE+-]+)\s+(.*)", line)
        if m:
            result.append((float(m.group(1)), m.group(2)))
    return result


def at(rec: list[tuple[float, str]], token: str, time: float | None = None, tol=1e-4):
    return [(t, s) for t, s in rec if token in s and (time is None or abs(t-time) <= tol)]


def first_time(rec, token: str) -> float:
    hit = at(rec, token)
    assert len(hit) == 1, (token, hit)
    return hit[0][0]


def accepted_seals(g: Gate, contract: dict) -> None:
    for key, pin in contract["accepted_native_runs"].items():
        run = Path(pin["path"])
        for name in ("closure", "invocation"):
            file = run / ("closure.json" if name == "closure" else "invocation.json")
            g.check(file.stat().st_size == pin[name]["bytes"] and sha(file) == pin[name]["sha256"], f"accepted {key}/{name}")
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        g.check(closure["run_id"] == pin["run_id"] and len(closure["raw"]) == len(pin["raw"]), f"accepted {key} raw names")
        for name, item in pin["raw"].items():
            file = run / name
            g.check(file.stat().st_size == item["bytes"] and sha(file) == item["sha256"], f"accepted {key}/{name}")


def child_seals(g: Gate, run: Path, arm: str) -> tuple[dict, dict]:
    inv = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    g.check(inv["run_id"] == closure["run_id"] == run.name == RUN_IDS[arm], "run identity")
    g.check(closure["invocation_sha256"] == sha(run / "invocation.json"), "invocation seal")
    g.check(not closure.get("error"), "closure error")
    g.check(inv["session_id"] == 0 and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "SSH0/mutex")
    for witness in (inv.get("gui"),):
        g.check(witness["pid"] == 13340 and witness["session_id"] == 1 and
                witness["start_unix_ms"] == 1790590196826 and witness["responding"] is True, "protected GUI")
    g.check(sha(run / "input.json") == sha(HERE / f"{arm}-input.json") == INPUT_SHA[arm], "input copy")
    g.check(closure["source_hashes_before"] == closure["source_hashes_after"], "source before/after")
    for name, item in closure["raw"].items():
        file = run / name
        g.check(file.stat().st_size == item["bytes"] and sha(file) == item["sha256"], f"raw seal {name}")
    g.check(len(closure["raw"]) >= 12, "raw count")
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    g.check([s["name"] for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"], "six ordered stages")
    for s in steps:
        g.check(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True,
                f"stage complete {s['name']}")
        if s["name"] in ("import", "export", "calc", "jsonreport"):
            g.check(s["child_session_id"] == 0 and isinstance(s["child_pid"], int) and s["child_pid"] > 0,
                    f"native SSH0 {s['name']}")
    rt = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    g.check(rt.get("passed") is True and rt.get("authored_row_tables") == 24 and rt.get("source_sha256") == INPUT_SHA[arm],
            "exact 24-table roundtrip")
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    g.check("Input conversion completed. Errors: 0, Warnings: 4, Notes: 0" in log, "converter 0/4/0")
    warnings = re.findall(r"warning\s*#(\d+)", log, re.I)
    g.check(sorted(warnings) == ["108", "2053", "2053", "2053"], "exact warning set")
    for iid in ("TEACH-LRU-01", "TEACH-LRU-A", "TEACH-LRU-B"):
        g.check(iid in log, f"item warning {iid}")
    return inv, closure


def event_ledger(g: Gate, run: Path, arm: str) -> dict:
    rec = records(run / "model.log")
    g.check(len(at(rec, "mission ordered: SHARED-CONFIG-MISSION", 7)) == 1, "one h7 order")
    g.check(len(at(rec, "mission created:", 7)) == 1, "one h7 mission object")
    g.check(len(at(rec, "mission activated, systems requested: 2", 7)) == 1, "two requested")
    launch = at(rec, "mission starting, duration: 2", 8)
    success = at(rec, "mission success:", 10)
    cancel = at(rec, "mission cancelled:")
    if arm == "crew":
        g.check(len(launch) == len(success) == 1 and not cancel, "h8 launch/h10 success")
        g.check("TEACH-CONF-A" in launch[0][1] and "TEACH-CONF-B" in launch[0][1] if launch else False,
                "both CBSID participants")
    else:
        g.check(not launch and not success and len(cancel) == 1 and 7 <= cancel[0][0] < 10,
                "radio shortage cancellation without launch")
    for rid, capacity, expected in (("MISSION-CREW", 2, "OK"), ("MISSION-RADIO", 0, "failed")):
        witness = [line for _, line in rec if rid in line and "Availability test" in line]
        if rid == "MISSION-RADIO" and arm == "radio":
            g.check(any("request for: 1" in line and expected in line for line in witness), "radio request failed")
        if rid == "MISSION-RADIO":
            g.check(not at(rec, f"<{rid} at <BASE-01,0>> allocated to mission"), "zero radio never booked")
        g.check(capacity in (0, 2), f"capacity source {rid}")
    booked = at(rec, "<MISSION-CREW at <BASE-01,0>> allocated to mission assigned: 1")
    released = at(rec, "<MISSION-CREW at <BASE-01,0>> deallocated from")
    g.check(len(booked) == len(released) == (2 if arm == "crew" else 1), "crew booking/release cardinality")
    g.check(all(t == 7 for t, _ in booked), "crew booked h7")
    g.check(all((abs(t-10) < 1e-4 if arm == "crew" else abs(t-cancel[0][0]) < 1e-4) for t, _ in released),
            "crew released on completion/cancel")
    reconfig = at(rec, "reconfig started, mission:")
    reconfig_end = at(rec, "reconfig ended, mission:")
    g.check(len(reconfig) == len(reconfig_end) and len(reconfig) >= 1, "observed reconfiguration starts/ends")
    g.check(any("TEACH-CONF-A" in line for _, line in rec), "physical A CBSID visible")
    if arm == "crew":
        g.check(any("TEACH-CONF-B" in line for _, line in rec), "physical B CBSID visible")
    takes = [(t, m.group(1), m.group(2)) for t, line in rec
             if (m := re.search(r"Take replacement item <(TEACH-LRU-[AB]),0,(\d+)> from stock", line))]
    returns = [(t, m.group(1), m.group(2)) for t, line in rec
               if (m := re.search(r"Put back replacement item <(TEACH-LRU-[AB]),0,(\d+)> to stock", line))]
    g.check(len(takes) >= 1 and len({(x[1], x[2]) for x in takes}) == len(takes), "unique observed stock-take IDs")
    for kind in ("TEACH-LRU-A", "TEACH-LRU-B"):
        used = sum(x[1] == kind for x in takes)
        back = sum(x[1] == kind for x in returns)
        g.check(0 <= 1-used+back <= 1, f"{kind} opening-to-terminal count")
    g.check(not any("backorder" in line.lower() or "failure occurs" in line.lower() for _, line in rec),
            "no backorder/failure")
    return {"records": rec, "booked": booked, "released": released,
            "reconfig": reconfig, "reconfig_end": reconfig_end,
            "takes": takes, "returns": returns,
            "cancel_time": cancel[0][0] if cancel else None}


def full_report(g: Gate, run: Path, arm: str, ledger: dict) -> None:
    current = report_tables(run / "report-raw.json")
    g.check(set(current) == set(SHAPES), "six default tables")
    c05 = report_tables(C05_POS if arm == "crew" else C05_NEG)
    a16 = report_tables(A16)
    checked = 0
    for name, (nrows, ncols) in SHAPES.items():
        if name not in current:
            continue
        t = current[name]
        reference = c05[name]
        g.check(t["columns"] == reference["columns"], f"{name} column schema")
        got = rows(t)
        g.check(len(got) == nrows, f"{name} row count")
        for i in range(min(len(got), nrows)):
            g.check(len(got[i]) == ncols, f"{name} row width {i}")
            for j in range(min(len(got[i]), ncols)):
                value = got[i][j]
                g.check(value is None or isinstance(value, (str, int, float)) and
                        (not isinstance(value, float) or math.isfinite(value)), f"{name}[{i},{j}] valid")
                checked += 1
        if name in ("SystemResults", "StockTotalResults", "ResourceResults"):
            for i, row in enumerate(got):
                if len(row) == ncols:
                    g.check(near(row[col(t, "STINT")], i*.5) and near(row[col(t, "ETINT")], (i+1)*.5),
                            f"{name} interval {i}")
    g.check(checked == 5210, f"all report cells inspected: {checked}")
    if set(current) != set(SHAPES):
        return
    g.check(rows(current["ProblemDescription"])[0][0] ==
            ("C05.var03 v1.0.1 shared CBSID mission; configuration B needs available crew" if arm == "crew" else
             "C05.var03 v1.0.1 shared CBSID mission; configuration B needs unavailable radio"), "report description")
    for j, target in enumerate(rows(c05["ResultSummary"])[0]):
        g.check(near(rows(current["ResultSummary"])[0][j], target), f"summary cell {j}")
    # All unchanged fields are tied to accepted C05 reports. Mechanism fields are
    # independently checked below from timed native records, not copied from a child report.
    system_dynamic = {"NSYRY", "NSYMA", "NSYMO", "NSYMC", "NSYMR", "NSYA", "FTMO", "NRCFG", "STREQ", "STACC"}
    stock_dynamic = {"NDR", "NWT"}
    resource_dynamic = {"NR", "NRMO", "NRMA", "NRA", "NRN"}
    for name, dynamic in (("SystemResults", system_dynamic), ("StockTotalResults", stock_dynamic),
                          ("ResourceResults", resource_dynamic)):
        table = current[name]
        ref = a16[name] if name == "StockTotalResults" else c05[name]
        for i, (row, before) in enumerate(zip(rows(table), rows(ref))):
            for j, column in enumerate(table["columns"]):
                if column["name"] not in dynamic:
                    g.check(near(row[j], before[j]), f"{name} stable {i}/{column['name']}")
    # Physical stock demands are point events, so the corresponding half-hour
    # NDR/NWT bins contain the number of observed local A/B stock takes.
    st = current["StockTotalResults"]
    for i, row in enumerate(rows(st)):
        demand = sum(i*.5-1e-6 <= t < (i+1)*.5-1e-6 for t, _, _ in ledger["takes"])
        for field in ("NDR", "NWT"):
            g.check(near(row[col(st, field)], demand), f"stock {field} bin {i}")
    # Two resources exist in both arms; the only used mission resource is crew.
    resource = current["ResourceResults"]
    bookings = [(t, end[0]) for (t, _), end in zip(ledger["booked"], ledger["released"])]
    flight_end = 10 if arm == "crew" else -1
    for i, row in enumerate(rows(resource)):
        a, b = i*.5, (i+1)*.5
        assigned = sum(overlap(a,b,start,min(end,8 if arm == "crew" else end))/.5 for start,end in bookings)
        operating = sum(overlap(a,b,8,flight_end)/.5 for _ in bookings) if arm == "crew" else 0
        for field, expected in (("NR",2),("NRA",2),("NRN",2),("NRMA",assigned),("NRMO",operating)):
            g.check(near(row[col(resource, field)], expected), f"resource {field} bin {i}")
    total = current["ResourceResultsTotal"]
    rt = rows(total)[0]
    for field, expected in (("NR",2),("NRA",2),("NRN",2),
                            ("NRMA", sum(min(end,8 if arm == "crew" else end)-start for start,end in bookings)/36),
                            ("NRMO", (2*2/36 if arm == "crew" else 0))):
        g.check(near(rt[col(total,field)], expected), f"resource total {field}")
    for j, value in enumerate(rows(c05["ResourceResultsTotal"])[0]):
        if total["columns"][j]["name"] not in resource_dynamic:
            g.check(near(rt[j], value), f"resource total stable {j}")
    # Mission timing and physical allocation are checked from the log. Integrated
    # report occupancy must agree with the same event durations.
    system = current["SystemResults"]
    sr = rows(system)
    for field, expected in (("NSYA",72),("NSYMO",8 if arm == "crew" else 0)):
        g.check(near(sum(r[col(system,field)]*.5 for r in sr), expected), f"system integral {field}")
    g.check(near(sr[-1][col(system,"NSYRY")], 2) and near(sr[-1][col(system,"NSYA")],2), "terminal two ready")
    g.check(near(rows(st)[-1][col(st,"NBO")],0), "terminal zero backorder")


def validate(run: Path, arm: str) -> dict:
    g = Gate()
    g.check(arm in RUN_IDS and run.name == RUN_IDS[arm], "reserved arm/run")
    g.check(sha(HERE / "contract.json") == CONTRACT_SHA, "frozen contract")
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8-sig"))
    accepted_seals(g, contract)
    child_seals(g, run, arm)
    ledger = event_ledger(g, run, arm)
    full_report(g, run, arm, ledger)
    return {"schema":"c05-var03-v101-author-validation/v1", "run_id":run.name, "arm":arm,
            "decision":"GO_BOUNDED" if not g.failures else "NO_GO", "checks":g.checks,
            "passed":g.checks-len(g.failures), "failures":g.failures,
            "observed_stock_ids":{"takes":ledger["takes"],"returns":ledger["returns"]},
            "scope":"one fixed two-CBSID mission/resource contrast, native CLI only"}


if __name__ == "__main__":
    try:
        result = validate(Path(sys.argv[1]), sys.argv[2])
    except Exception as exc:
        result = {"schema":"c05-var03-v101-author-validation/v1", "decision":"NO_GO", "checks":1,
                  "passed":0,"failures":[f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["decision"] == "GO_BOUNDED" else 1)

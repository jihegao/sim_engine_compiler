"""Frozen, read-only C05.var03 native result gate. No SIMLOX invocation."""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

from check_roundtrip import INPUT_SHA, parse
from report_oracle import check_full_report

HERE = Path(__file__).resolve().parent
CONTRACT_SHA = "cc3aa75b3c4f6cec8fff57c0de28abf9ed552f4c0bc836e581295856ca30f283"
RUN_IDS = {"crew": "c05-var03-v101-crew-ssh-20261007-01",
           "radio": "c05-var03-v101-radio-ssh-20261007-01"}
SHAPES = {"ProblemDescription": (1, 1), "ResultSummary": (1, 11),
          "SystemResults": (72, 40), "StockTotalResults": (72, 16),
          "ResourceResults": (72, 16), "ResourceResultsTotal": (1, 14)}
ROOT = HERE.parent
C05_POS = ROOT / "C05-mission-resource-v1.0.0/runs/c05-capacity-2-20260930-01/report-raw.json"
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
        elif result:
            t, previous = result[-1]
            result[-1] = (t, previous + "\n" + line)
    return result


def at(rec: list[tuple[float, str]], token: str, time: float | None = None, tol=1e-4):
    return [(t, s) for t, s in rec if token in s and (time is None or abs(t-time) <= tol)]


def first_time(rec, token: str) -> float:
    hit = at(rec, token)
    assert len(hit) == 1, (token, hit)
    return hit[0][0]


def diagnostic_rows(log: str) -> list[tuple[str,int,str,str]]:
    form = ""
    result = []
    for line in log.splitlines():
        marker = re.match(r"Form:\s*(\S+)\s*$", line)
        if marker:
            form = marker.group(1)
        detail = re.match(r"rec\s+(\d+):\s*\(warning\s*#(\d+)\)\s*(.*)$", line, re.I)
        if detail:
            result.append((form, int(detail.group(1)), detail.group(2), detail.group(3).strip()))
    return result


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


def child_seals(g: Gate, run: Path, arm: str, sealed: bool) -> tuple[dict, dict | None]:
    inv = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig")) if sealed else None
    g.check(inv["run_id"] == run.name == RUN_IDS[arm], "run identity")
    g.check(inv["session_id"] == 0 and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "SSH0/mutex")
    for witness in (inv.get("gui"),):
        g.check(witness["pid"] == 13340 and witness["session_id"] == 1 and
                witness["start_unix_ms"] == 1790590196826 and witness["responding"] is True, "protected GUI")
    g.check(sha(run / "input.json") == sha(HERE / f"{arm}-input.json") == INPUT_SHA[arm], "input copy")
    if sealed:
        g.check(closure["run_id"] == inv["run_id"] and closure["invocation_sha256"] == sha(run / "invocation.json"), "sealed invocation")
        g.check(not closure.get("error"), "closure error")
        g.check(closure["source_hashes_before"] == closure["source_hashes_after"], "source before/after")
        for name, item in closure["raw"].items():
            file = run / name
            g.check(file.stat().st_size == item["bytes"] and sha(file) == item["sha256"], f"raw seal {name}")
        g.check(len(closure["raw"]) >= 13, "13 sealed raw files")
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    g.check([s["name"] for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"], "six ordered stages")
    for s in steps:
        pending = not sealed and s["name"] == "check_behavior"
        g.check(pending or s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True,
                f"stage complete {s['name']}")
        if s["name"] in ("import", "export", "calc", "jsonreport"):
            g.check(s["child_session_id"] == 0 and isinstance(s["child_pid"], int) and s["child_pid"] > 0,
                    f"native SSH0 {s['name']}")
    rt = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    g.check(rt.get("passed") is True and rt.get("authored_row_tables") == 24 and rt.get("source_sha256") == INPUT_SHA[arm],
            "exact 24-table roundtrip")
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    g.check("Input conversion completed. Errors: 0, Warnings: 4, Notes: 0" in log, "converter 0/4/0")
    diagnostics = diagnostic_rows(log)
    expected = [("Control",1,"108","Enabling simulation log may generate extensive data in log file")]
    expected += [("Item",i,"2053",f"FRT is zero for: {iid}") for i,iid in
                 enumerate(("TEACH-LRU-01","TEACH-LRU-A","TEACH-LRU-B"),1)]
    g.check(diagnostics == expected, "exact Form/rec/code/message warning attribution")
    return inv, closure


def event_ledger(g: Gate, run: Path, arm: str) -> dict:
    rec = records(run / "model.log")
    g.check(len(at(rec, "mission ordered: SHARED-CONFIG-MISSION", 7)) == 1, "one h7 order")
    g.check(len(at(rec, "mission created:", 7)) == 1, "one h7 mission object")
    g.check(len(at(rec, "mission activated, systems requested: 2", 7)) == 1, "two requested")
    launch = at(rec, "mission starting, duration: 2")
    success = at(rec, "mission success:", 10)
    cancel = at(rec, "mission cancelled:")
    if arm == "crew":
        g.check(len(launch) == len(at(rec,"mission starting,")) == len(success) == 1 and
                abs(launch[0][0]-8) < 1e-4 and not cancel, "h8 launch/h10 success")
        members = re.findall(r"<(TEACH-CONF-[AB]),(\d+)>", launch[0][1]) if launch else []
        g.check(len(members) == 2 and {name for name, _ in members} == {"TEACH-CONF-A","TEACH-CONF-B"}
                and len(set(members)) == 2, "one A and one B configured launch")
        allocations = at(rec,"mission allocates system:")
        base_ids = [re.findall(r"mission allocates system: <TEACH-AIR-01,(\d+)>",body) for _,body in allocations]
        g.check(len(base_ids) == 2 and all(base_ids) and {x[0] for x in base_ids} == {"0","1"},
                "two distinct base aircraft allocated")
        g.check(len(at(rec,"mission completed:",10)) == 1 and
                all(len(at(rec,f"System arrives <{name},{ident}>",10)) == 1 for name,ident in members),
                "h10 completed/physical returns")
    else:
        g.check(not at(rec,"mission starting,") and not at(rec,"mission success:") and
                not at(rec,"mission completed:") and len(cancel) == 1 and 7 <= cancel[0][0] < 10,
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
    g.check((len(booked) == len(released) == 2) if arm == "crew" else
            (len(booked) == len(released) and len(booked) <= 1), "crew booking/release cardinality")
    g.check(all(7-1e-4 <= t < 10 for t, _ in booked), "crew booked within allocation window")
    g.check(all((abs(t-10) < 1e-4 if arm == "crew" else abs(t-cancel[0][0]) < 1e-4) for t, _ in released),
            "crew released on completion/cancel")
    reconfig = at(rec, "reconfig started, mission:")
    reconfig_end = at(rec, "reconfig ended, mission:")
    g.check(len(reconfig) == len(reconfig_end) and
            (len(reconfig) == 2 if arm == "crew" else len(reconfig) <= 1), "observed reconfiguration starts/ends")
    if arm == "crew" or reconfig:
        g.check(any("TEACH-CONF-A" in line for _, line in rec), "physical A CBSID visible")
    if arm == "crew":
        g.check(any("TEACH-CONF-B" in line for _, line in rec), "physical B CBSID visible")
        ids = [re.findall(r"<TEACH-AIR-01,(\d+)>", text) for _,text in reconfig]
        g.check(len(ids) == 2 and all(x for x in ids) and {x[0] for x in ids} == {"0","1"},
                "distinct base reconfiguration owners")
        linked = []
        for suffix in ("A","B"):
            demand = [(t, re.search(r"pos <TEACH-AIR-01,BASE-01,(\d+)>", body)) for t,body in rec
                      if f"<TEACH-LRU-{suffix},0,BASE-01,0> Reconfiguration item demand arrives" in body]
            demand = [(t,m.group(1)) for t,m in demand if m]
            prep = [(t,m.group(1)) for t,body in rec
                    if (m := re.search(rf"<TEACH-CONF-{suffix},(\d+)> preparation started, mission: <SHARED-CONFIG-MISSION,",body))]
            if len(demand) != 1 or len(prep) != 1:
                g.check(False,f"{suffix} demand/preparation unique linkage")
                continue
            base = demand[0][1]
            starts = [t for t,body in reconfig if f"<TEACH-AIR-01,{base}> reconfig started" in body]
            ends = [t for t,body in reconfig_end if f"<TEACH-AIR-01,{base}> reconfig ended" in body]
            g.check(len(starts)==len(ends)==1 and starts[0] >= demand[0][0]-1e-4 and
                    starts[0] <= ends[0] <= prep[0][0] <= 8+1e-4 and
                    (f"TEACH-CONF-{suffix}",prep[0][1]) in members,
                    f"{suffix} base demand/reconfig end/configured prep/launch")
            linked.append(base)
        g.check(set(linked)=={"0","1"},"A/B demand edges reach distinct base aircraft")
    takes = [(t, m.group(1), m.group(2)) for t, line in rec
             if (m := re.search(r"Take replacement item <(TEACH-LRU-[AB]),0,(\d+)> from stock", line))]
    returns = [(t, m.group(1), m.group(2)) for t, line in rec
               if (m := re.search(r"Put back replacement item <(TEACH-LRU-[AB]),0,(\d+)> to stock", line))]
    g.check((len(takes) == 2 if arm == "crew" else len(takes) <= 1) and
            len({(x[1], x[2]) for x in takes}) == len(takes), "unique observed stock-take IDs")
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
    check_full_report(g, run / "report-raw.json", run / "model.log", arm)

def validate(run: Path, arm: str, sealed: bool = False) -> dict:
    g = Gate()
    g.check(arm in RUN_IDS and run.name == RUN_IDS[arm], "reserved arm/run")
    g.check(sha(HERE / "contract.json") == CONTRACT_SHA, "frozen contract")
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8-sig"))
    accepted_seals(g, contract)
    child_seals(g, run, arm, sealed)
    ledger = event_ledger(g, run, arm)
    full_report(g, run, arm, ledger)
    return {"schema":"c05-var03-v101-author-validation/v1", "run_id":run.name, "arm":arm,
            "decision":"GO_BOUNDED" if not g.failures else "NO_GO", "checks":g.checks,
            "passed":g.checks-len(g.failures), "failures":g.failures,
            "observed_stock_ids":{"takes":ledger["takes"],"returns":ledger["returns"]},
            "provenance":"sealed-closure" if sealed else "preclosure-live-behavior-gate",
            "scope":"one fixed two-CBSID mission/resource contrast, native CLI only"}


if __name__ == "__main__":
    try:
        result = validate(Path(sys.argv[1]), sys.argv[2], len(sys.argv) >= 4 and sys.argv[3] == "--sealed")
    except Exception as exc:
        result = {"schema":"c05-var03-v101-author-validation/v1", "decision":"NO_GO", "checks":1,
                  "passed":0,"failures":[f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["decision"] == "GO_BOUNDED" else 1)

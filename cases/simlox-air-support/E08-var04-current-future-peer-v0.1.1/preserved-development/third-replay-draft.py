"""Read-only, source/event-derived replay of the two sealed E08.var04 arms.

The native report is never used to construct an expected cell. This module is
intentionally separate from either accepted parent's validator.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = HERE.parent
CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
BASE = CONTRACT["base_commit"]
TABLE_ORDER_DEFAULT = ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"]
TABLE_ORDER_SELECTED = ["ProblemDescription", "ResultSummary", "MissionResults", "MissionResultsTotal",
                        "FixedMissionResults", "FixedMissionResultsTotal", "SystemResults", "ItemResults",
                        "ItemResultsTotal", "StockTotalResults"]
COLS = {
    "ProblemDescription": "PDESC",
    "ResultSummary": "NREP RTILW RTIUP MTMF RSMTMF MSTF RSMSTF MSUF RSMSUF STMF RSSTMF",
    "MissionResults": "UNID MTID STINT ETINT MTREQ MTACC MTF MTLOW STREQ STACC STF STLOW",
    "MissionResultsTotal": "UNID MTID MTREQ MTACC MTF MTLOW STREQ STACC STF STLOW",
    "FixedMissionResults": "UNID MTID STIM NMREQ NMSTA NMSUC MTREQ MTACC MTF FMSTA FMSUC NSYRQ NSYST NSYSU AVSTD MTOT NSYOT STOT STREQ NSYMO STACC STF STOTD NPSTA NPSUC",
    "FixedMissionResultsTotal": "UNID MTID NMREQ NMSTA NMSUC MTREQ MTACC MTF FMSTA FMSUC NSYRQ NSYST NSYSU AVSTD MTOT NSYOT STOT STREQ NSYMO STACC STF NPSTA NPSUC",
    "SystemResults": "UNID SID STINT ETINT NSYRY NSYMA NSYMO NSYMC NSYMP NSYMT NSYMS NSYMR NSYUA NSYA NSYAL FTMO NSYRP NSYPM NSYTP NSYWR NSYWI NSYLA NSYUH NREPT NPMT NFAIL NDAM NPMS NROBT NRCFG STREQ STACC STF STLOW SYDT SYDTU NSYDT NSYSW NPSTA NPSUC",
    "ItemResults": "IID STID STINT ETINT STSZ STOHA NBO ROS ROST WT WTT WTS PNB NDF NDD NDR NDP NLD NRP NRO NPM NCS NWT NRB",
    "ItemResultsTotal": "IID STID STSZ STOHA NBO ROS ROST WT WTT WTS PNB NDF NDD NDR NDP NLD NRP NRO NPM NCS NWT NRB",
    "StockTotalResults": "STINT ETINT NBO NBOU ROS ROST WT WTT WTS PNB NDF NDD NDR NDP NLD NWT",
}
COLS = {k: v.split() for k, v in COLS.items()}
STRING_COLS = {"PDESC", "UNID", "MTID", "SID", "IID", "STID"}
KEY_COLS = {"UNID", "MTID", "SID", "IID", "STID", "STINT", "ETINT", "STIM"}
NULLABLE = {"NBOU", "ROS", "ROST", "WT", "WTT", "WTS", "SYDT", "SYDTU", "STLOW", "MTLOW"}
STATIONS = ["BASE-01", "BASE-02", "DEPOT-01"]


def digest(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def parse_native(path: Path):
    """Strip native trailing commas outside quoted strings on an in-memory copy."""
    text = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = escaped = False
    for i, ch in enumerate(text):
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
        elif ch == ',':
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            if j < len(text) and text[j] in "]}":
                continue
            out.append(ch)
        else:
            out.append(ch)
    return json.loads("".join(out))


def repo_path(relative: str) -> Path:
    p = (ROOT / relative).resolve()
    check(p.is_relative_to(ROOT.resolve()), f"path escapes repository: {relative}")
    return p


def verify_pin(record: dict) -> None:
    p = repo_path(record["path"])
    check(p.is_file(), f"missing pinned file: {p}")
    if "local_disk" in record:
        check(digest(p) == record["local_disk"], f"local pin mismatch: {p}")
        published = record.get("published_git_at_base")
        if published is not None:
            result = subprocess.run(["git", "show", f"{BASE}:{record['path']}"], cwd=ROOT,
                                    capture_output=True, check=True)
            check({"bytes": len(result.stdout), "sha256": hashlib.sha256(result.stdout).hexdigest()} == published,
                  f"Git byte identity mismatch: {record['path']}")
    else:
        check(digest(p) == {"bytes": record["bytes"], "sha256": record["sha256"]},
              f"pin mismatch: {p}")


def verify_all_pins() -> int:
    count = 0
    for parent in CONTRACT["accepted_parents"]:
        for entry in parent["source_files"] + [parent["evidence_index"], parent["independent_verdict"], parent["signoff"]]:
            verify_pin(entry)
            count += 1
        for run in parent["runs"]:
            base = repo_path(run["local_run_directory"])
            for name, pin in run["files"].items():
                check(digest(base / name) == pin, f"sealed run mismatch: {run['run_id']}/{name}")
                count += 1
        for selector in parent["station_selectors"]:
            verify_pin(selector)
            count += 1
    for donor in CONTRACT["schema_dependencies"]:
        for name in ("accepted_source", "evidence_index", "signoff"):
            verify_pin(donor[name])
            count += 1
    for entry in CONTRACT["excluded_v010_contract_repair"]["old_exact_files"]:
        verify_pin(entry)
        count += 1
    for name in ("root_no_go_receipt", "root_selection_code"):
        verify_pin(CONTRACT["excluded_v010_contract_repair"][name])
        count += 1
    for name in ("root_selection_receipt", "root_parent_raw_rehash_receipt"):
        verify_pin(CONTRACT["ownership"][name])
        count += 1
    return count


@dataclass(frozen=True)
class Event:
    time: float
    token: str
    line: int
    text: str

    @property
    def uncertainty(self) -> float:
        if self.token in {"0", "7", "8", "9", "10", "10.5", "11", "15.5", "19", "20", "22", "31", "32", "34", "36"}:
            # These exact values are additionally tied to authored schedules or
            # whole-hour route terms. Mere integer spelling alone is insufficient.
            return 0.0
        return 0.5 * 10.0 ** (-len(self.token.partition(".")[2])) if "." in self.token else 0.5


def events(path: Path) -> list[Event]:
    records = []
    for i, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        m = re.match(r"Time:\s+([0-9]+(?:\.[0-9]+)?)\s+(.*)", line)
        if m:
            records.append(Event(float(m.group(1)), m.group(1), i, m.group(2)))
        elif records:
            records[-1] = replace(records[-1], text=records[-1].text + "\n" + line)
    return records


def one(records: list[Event], pattern: str, label: str) -> Event:
    matched = [r for r in records if re.search(pattern, r.text)]
    check(len(matched) == 1, f"{label}: expected one event, got {len(matched)}")
    return matched[0]


def must_before(*evs: Event) -> None:
    check(all(a.line < b.line for a, b in zip(evs, evs[1:])), "physical event order")


def at(ev: Event, hour: float, label: str, allowance: float = 0.00006) -> None:
    check(abs(ev.time - hour) <= allowance, f"{label}: time {ev.time} != {hour}")


def input_tables(path: Path) -> dict:
    return {t["name"]: t for t in parse_native(path)["model"]["tables"]}


def model_gate(current: Path, future: Path) -> None:
    a, b = input_tables(current), input_tables(future)
    check(len(a) == 34 and len(b) == 35 and set(b) - set(a) == {"ItemTransfer"}, "authored table topology")
    check({name for name in a if a[name] != b[name]} == {"ProblemDescription", "StockAllocation"},
          "only listed shared tables change")
    sa, sb = a["StockAllocation"]["instances"][0]["rows"], b["StockAllocation"]["instances"][0]["rows"]
    check(sa[:2] == sb[:2] and sa[2][:3] == sb[2][:3] == ["AIR_BASIC", "TEACH-LRU-01", "BASE-02"]
          and sa[2][3] == 1 and sb[2][3] == 0 and sa[2][4:] == sb[2][4:], "sole stock cell")
    check(b["ItemTransfer"]["instances"][0]["rows"] ==
          [["DEPOT-01", "BASE-02", "TEACH-LRU-01", 9.0, 1, 2.0, None]], "sole scheduled transfer")
    ca = a["Control"]["instances"][0]["rows"][0]
    cb = b["Control"]["instances"][0]["rows"][0]
    check(ca == cb and ca[8] == "Y" and ca[1] == 36 and ca[4] == 0.5, "common Control")
    check(a["LateralSupport"] == b["LateralSupport"] and
          a["LateralSupport"]["instances"][0]["rows"][0][:4] == ["LAT-01", 0.5, "N", "IMMEDIATE"],
          "common lateral policy")


def physical_gate(records: list[Event], role: str) -> dict:
    failure = one(records, r"critical random failure added", "critical failure")
    arrival = one([r for r in records if r.time == 10],
                  r"System arrives <TEACH-AIR-01,0>", "first aircraft arrival")
    backorder = one(records, r"<TEACH-LRU-01,0,BASE-01,0> Backorder added", "BASE-01 backorder")
    clear = one(records, r"<TEACH-LRU-01,0,BASE-01,0> Backorder removed", "BASE-01 clearance")
    remove_end = one(records, r"remove subitem subtask .* completed", "component removal")
    fit_work = one(records, r"fit subitem subtask .* starts performing", "component fit work")
    fit_end = one(records, r"fit subitem subtask .* completed", "component fit end")
    ready = one(records, r"Maintained system arrives <TEACH-AIR-01,0>", "maintained aircraft ready")
    at(failure, 9.8829, "failure")
    at(arrival, 10, "arrival")
    at(backorder, 10, "backorder")
    at(remove_end, 10.1667, "removal")
    must_before(failure, arrival, backorder, remove_end, clear, fit_work, fit_end, ready)
    at(ready, 10.8333 if role == "current_stock" else 15.5, "ready")
    if role == "current_stock":
        chosen = one(records, r"Lateral support from: <TEACH-LRU-01,0,BASE-02,0>", "peer selected")
        taken = one(records, r"<TEACH-LRU-01,0,BASE-02,0> Take replacement item <TEACH-LRU-01,0,1>", "peer ID1 take")
        receipt = one(records, r"<TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>", "peer ID1 arrival")
        depot_take = one(records, r"<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0>", "depot ID0 take")
        replenish = one(records, r"<TEACH-LRU-01,0,BASE-02,0> Put back replacement item <TEACH-LRU-01,0,0>", "peer replenishment")
        at(chosen, 10, "peer choice")
        at(receipt, 10.5, "peer arrival")
        at(clear, 10.5, "peer wait ended")
        at(replenish, 11, "replenishment")
        must_before(backorder, chosen, taken, receipt, clear, fit_work)
        check(depot_take.line < replenish.line, "depot replenishment path")
        check(not any("item transfer task" in e.text for e in records), "current arm has no scheduled ItemTransfer")
        return {"failure": failure, "repair_start": arrival, "remove_end": remove_end, "receipt": receipt,
                "ready": ready, "backorder": backorder, "clear": clear, "depot_take": depot_take,
                "peer_take": taken, "peer_putback": replenish}
    transfer_start = one(records, r"item transfer task 0 \(BETWEEN\).* starts with 1 items, transfer time: 2", "future scheduled transfer start")
    transfer_arrival = one(records, r"item transfer task 0 \(BETWEEN\).* arrives with 1 items", "future scheduled transfer arrival")
    depot_take = one(records, r"<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0>", "future depot ID0 take")
    peer_putback = one(records, r"<TEACH-LRU-01,0,BASE-02,0> Put back replacement item <TEACH-LRU-01,0,0>", "future peer ID0 arrival")
    depot_clear = one(records, r"<TEACH-LRU-01,0,DEPOT-01,0> Backorder removed", "future depot backorder clearance")
    receipt = one(records, r"<TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>", "future repaired ID1 arrival")
    at(transfer_start, 9, "transfer start")
    at(transfer_arrival, 11, "transfer arrival")
    at(peer_putback, 11, "peer stock receipt")
    at(depot_clear, 14.1667, "depot repair/backorder end")
    at(receipt, 15.1667, "ordinary arrival")
    at(clear, 15.1667, "ordinary wait ended")
    must_before(depot_take, transfer_start, backorder, transfer_arrival, peer_putback,
                depot_clear, receipt, clear, fit_work, ready)
    check(not any("Lateral support from:" in e.text for e in records), "no future lateral shipment")
    return {"failure": failure, "repair_start": arrival, "remove_end": remove_end, "receipt": receipt,
            "ready": ready, "backorder": backorder, "clear": clear, "depot_take": depot_take,
            "peer_putback": peer_putback, "transfer_start": transfer_start,
            "transfer_arrival": transfer_arrival, "depot_clear": depot_clear}


@dataclass(frozen=True)
class Metric:
    value: object
    edges: tuple[Event, ...] = ()
    denominator: float | None = None
    class_name: str = "exact"


def M(value, *edges: Event, denominator: float | None = None, class_name: str = "exact") -> Metric:
    return Metric(value, tuple(edges), denominator, class_name)


def span_metric(start: float, end: float, lo: float, hi: float,
                edges: tuple[Event, ...], denominator: float) -> Metric:
    value = max(0.0, min(end, hi) - max(start, lo)) / denominator
    if abs(value - round(value)) < 1e-12:
        return M(round(value))
    return M(value, *edges, denominator=denominator,
             class_name="half_hour_time_weighted_fraction_absolute" if denominator == 0.5
             else "thirty_six_hour_mean_from_printed_edges_absolute")


def interval_sum(lo: float, hi: float, spans: list[tuple[float, float, tuple[Event, ...]]],
                 denominator: float = 0.5) -> Metric:
    value = sum(max(0.0, min(end, hi) - max(start, lo)) for start, end, _ in spans) / denominator
    if abs(value - round(value)) < 1e-12:
        return M(round(value))
    edges = tuple(e for start, end, es in spans if min(end, hi) > max(start, lo) for e in es)
    return M(value, *edges, denominator=denominator,
             class_name="half_hour_time_weighted_fraction_absolute" if denominator == 0.5
             else "thirty_six_hour_mean_from_printed_edges_absolute")


def sum_metric(*metrics: Metric) -> Metric:
    value = sum(float(x.value) for x in metrics)
    if abs(value - round(value)) < 1e-12:
        return M(round(value))
    return M(value, *(e for metric in metrics for e in metric.edges),
             denominator=metrics[0].denominator, class_name=metrics[0].class_name)


def opposite(metric: Metric) -> Metric:
    value = 1 - float(metric.value)
    if abs(value - round(value)) < 1e-12:
        return M(round(value))
    return M(value, *metric.edges, denominator=metric.denominator, class_name=metric.class_name)


def duration(start: Event, end: Event) -> Metric:
    value = end.time - start.time
    if abs(value - round(value)) < 1e-12:
        return M(round(value))
    return M(value, start, end, denominator=1.0, class_name="elapsed_hours_from_printed_edges_absolute")


def base_row(table: str) -> dict[str, Metric]:
    row = {col: M(0) for col in COLS[table]}
    nullable_by_table = {
        "MissionResults": {"MTLOW", "STLOW", "MTF", "STF"},
        "MissionResultsTotal": {"MTLOW", "STLOW"},
        "SystemResults": {"SYDT"},
        "ItemResults": {"ROS", "ROST", "WT", "WTT", "WTS"},
        "ItemResultsTotal": {"ROS", "ROST", "WT", "WTT", "WTS"},
        "StockTotalResults": {"NBOU", "ROS", "ROST", "WT", "WTT", "WTS"},
    }
    for col in nullable_by_table.get(table, ()):
        row[col] = M(None)
    return row


def source_fields(model: dict) -> dict:
    def values(name: str):
        table = model[name]
        names = [c["name"] for c in table["columns"]]
        return [dict(zip(names, row)) for ins in table["instances"] for row in ins["rows"]]
    control = values("Control")[0]
    missions = values("OperationProfile")
    desc = values("ProblemDescription")[0]["PDESC"]
    stocks = {r["STID"]: r["STSIZ"] for r in values("StockAllocation")}
    return {"control": control, "missions": missions, "description": desc, "stocks": stocks}


def mission_gate(records: list[Event], source: dict) -> dict:
    starts = [r for r in records if "mission starting, duration: 2" in r.text]
    check([r.time for r in starts] == [8, 20, 32], "three source-scheduled mission starts")
    prep = [r for r in records if "preparation started, mission:" in r.text]
    check([r.time for r in prep] == [7, 19, 31], "three preparations")
    aborts = [r for r in records if "mission aborted:" in r.text]
    successes = [r for r in records if "mission success:" in r.text]
    check(len(aborts) == 1 and len(successes) == 2 and
          [r.time for r in successes] == [22, 34], "one abort and two successes")
    check([r["STIM"] for r in source["missions"]] == [8.0, 20.0, 32.0], "authored mission schedule")
    return {"prep": prep, "starts": starts, "aborts": aborts, "successes": successes}


def expected_summary(source: dict, mission: dict) -> dict:
    row = base_row("ResultSummary")
    row.update({"NREP": M(source["control"]["NREPS"]), "RTILW": M(0),
                "RTIUP": M(source["control"]["RCEND"]), "MTMF": M(1), "MSTF": M(1),
                "MSUF": M(len(mission["successes"]) / len(mission["starts"])), "STMF": M(1)})
    return row


def expected_fixed_rows(mission: dict) -> tuple[list[dict], dict]:
    rows = []
    for idx, start in enumerate(mission["starts"]):
        success = int(idx != 0)
        row = base_row("FixedMissionResults")
        row.update({"UNID": M("Total over all Units"), "MTID": M("Total over all Missions"),
                    "STIM": M(start.time), "NMREQ": M(1), "NMSTA": M(1), "NMSUC": M(success),
                    "MTREQ": M(2), "MTACC": M(2), "MTF": M(1), "FMSTA": M(1),
                    "FMSUC": M(success), "NSYRQ": M(1), "NSYST": M(1), "NSYSU": M(success),
                    "MTOT": M(1), "NSYOT": M(1), "STOT": M(1), "STREQ": M(2),
                    "NSYMO": M(1), "STACC": M(2), "STF": M(1)})
        rows.append(row)
    total = base_row("FixedMissionResultsTotal")
    total.update({"UNID": M("Total over all Units"), "MTID": M("Total over all Missions"),
                  "NMREQ": M(3), "NMSTA": M(3), "NMSUC": M(2), "MTREQ": M(6), "MTACC": M(6),
                  "MTF": M(1), "FMSTA": M(1), "FMSUC": M(2 / 3), "NSYRQ": M(3),
                  "NSYST": M(3), "NSYSU": M(2), "MTOT": M(3), "NSYOT": M(3), "STOT": M(3),
                  "STREQ": M(6), "NSYMO": M(3), "STACC": M(6), "STF": M(1)})
    return rows, total


def expected_missions(mission: dict) -> tuple[list[dict], dict]:
    rows = []
    for bin_index in range(72):
        lo, hi = bin_index / 2, (bin_index + 1) / 2
        active = any(start.time <= lo < start.time + 2 for start in mission["starts"])
        row = base_row("MissionResults")
        row.update({"UNID": M("Total over all Units"), "MTID": M("Total over all Missions"),
                    "STINT": M(lo), "ETINT": M(hi), "MTREQ": M(int(active)),
                    "MTACC": M(int(active)), "STREQ": M(int(active)), "STACC": M(int(active)),
                    "MTF": M(1) if active else M(None), "STF": M(1) if active else M(None)})
        rows.append(row)
    total = base_row("MissionResultsTotal")
    total.update({"UNID": M("Total over all Units"), "MTID": M("Total over all Missions"),
                  "MTREQ": M(6 / 36), "MTACC": M(6 / 36), "STREQ": M(6 / 36),
                  "STACC": M(6 / 36), "MTF": M(1), "STF": M(1)})
    return rows, total


def expected_system(physical: dict, mission: dict) -> list[dict]:
    ready = physical["ready"]
    out = physical["repair_start"]
    remove_end = physical["remove_end"]
    receipt = physical["receipt"]
    ready_spans = [(0, 7, ()), (ready.time, 19, (ready,)), (22, 31, ()), (34, 36, ())]
    assigned_spans = [(7, 10, ()), (19, 22, ()), (31, 34, ())]
    mission_spans = [(r.time, r.time + 2, ()) for r in mission["starts"]]
    prep_spans = [(7, 8, ()), (19, 20, ()), (31, 32, ())]
    unavailable = [(out.time, ready.time, (out, ready))]
    repairing = [(out.time, remove_end.time, (out, remove_end)),
                 (receipt.time, ready.time, (receipt, ready))]
    waiting = [(remove_end.time, receipt.time, (remove_end, receipt))]
    rows = []
    for i in range(72):
        lo, hi = i / 2, (i + 1) / 2
        row = base_row("SystemResults")
        row.update({"UNID": M("Total over all Units"), "SID": M("Total over all Systems"),
                    "STINT": M(lo), "ETINT": M(hi),
                    "NSYRY": interval_sum(lo, hi, ready_spans),
                    "NSYMA": interval_sum(lo, hi, assigned_spans),
                    "NSYMO": interval_sum(lo, hi, mission_spans),
                    "NSYMR": interval_sum(lo, hi, prep_spans),
                    "NSYUA": interval_sum(lo, hi, unavailable),
                    "NSYRP": interval_sum(lo, hi, repairing),
                    "NSYWI": interval_sum(lo, hi, waiting),
                    "FTMO": interval_sum(lo, hi, mission_spans),
                    "STACC": interval_sum(lo, hi, mission_spans),
                    "NFAIL": M(int(lo <= physical["failure"].time < hi)),
                    "NREPT": M(int(lo <= ready.time < hi)),
                    "NSYDT": M(int(lo <= out.time < hi))})
        row["NSYA"] = opposite(row["NSYUA"])
        if lo <= out.time < hi:
            row["SYDT"] = duration(out, ready)
        rows.append(row)
    return rows


def station_spans(role: str, physical: dict, station: str) -> tuple[list, list, list]:
    """Nominal stock, physical on-hand and backorder intervals from typed moves."""
    horizon = 36.0
    if station == "BASE-01":
        nominal = []
        onhand = []  # Replacement is handed directly to the waiting SURP fit task.
        backorders = [(physical["backorder"].time, physical["clear"].time,
                       (physical["backorder"], physical["clear"]))]
    elif station == "BASE-02" and role == "current_stock":
        nominal = [(0, horizon, ())]
        onhand = [(0, physical["peer_take"].time, ()),
                  (physical["peer_putback"].time, horizon, (physical["peer_putback"],))]
        backorders = []
    elif station == "DEPOT-01" and role == "current_stock":
        nominal = [(0, horizon, ())]
        putback = physical["depot_repair"]
        onhand = [(0, physical["depot_take"].time, ()),
                  (putback.time, horizon, (putback,))]
        backorders = []
    elif station == "BASE-02":
        nominal = [(physical["transfer_arrival"].time, horizon, (physical["transfer_arrival"],))]
        onhand = [(physical["peer_putback"].time, horizon, (physical["peer_putback"],))]
        backorders = []
    elif station == "DEPOT-01":
        nominal = [(0, physical["transfer_start"].time, ())]
        onhand = [(0, physical["depot_take"].time, ())]
        backorders = [(physical["depot_backorder"].time, physical["depot_clear"].time,
                       (physical["depot_backorder"], physical["depot_clear"]))]
    else:
        raise AssertionError(f"unexpected station {station}")
    return nominal, onhand, backorders


def demand_at(role: str, physical: dict, station: str) -> tuple[Event, Event | None] | None:
    if station == "BASE-01":
        return physical["backorder"], physical["clear"]
    if station == "DEPOT-01" and role == "scheduled_future_stock":
        return physical["depot_backorder"], physical["depot_clear"]
    if role == "current_stock" and station in {"BASE-02", "DEPOT-01"}:
        return physical["demand_" + station.lower().replace("-", "")], None
    return None


def item_bin(role: str, physical: dict, station: str, i: int) -> dict:
    lo, hi = i / 2, (i + 1) / 2
    nominal, onhand, backorders = station_spans(role, physical, station)
    row = base_row("ItemResults")
    row.update({"IID": M("TEACH-LRU-01"), "STID": M(station), "STINT": M(lo), "ETINT": M(hi),
                "STSZ": interval_sum(lo, hi, nominal),
                "STOHA": interval_sum(lo, hi, onhand),
                "NBO": interval_sum(lo, hi, backorders)})
    row["PNB"] = opposite(row["NBO"])
    demand = demand_at(role, physical, station)
    if demand and lo <= demand[0].time < hi:
        row.update({"NDF": M(1), "NWT": M(1)})
        if demand[1] is not None:
            wait = duration(*demand)
            row.update({"ROS": M(1), "ROST": M(1), "WT": wait,
                        "WTT": wait, "WTS": wait})
        if role == "current_stock" and station == "BASE-02":
            row["NLD"] = M(1)
    if station == "DEPOT-01" and lo <= physical["depot_repair"].time < hi:
        row["NRP"] = M(1)
    return row


def item_total(role: str, physical: dict, station: str) -> dict:
    nominal, onhand, backorders = station_spans(role, physical, station)
    row = base_row("ItemResultsTotal")
    row.update({"IID": M("TEACH-LRU-01"), "STID": M(station),
                "STSZ": interval_sum(0, 36, nominal, denominator=36),
                "STOHA": interval_sum(0, 36, onhand, denominator=36),
                "NBO": interval_sum(0, 36, backorders, denominator=36)})
    row["PNB"] = opposite(row["NBO"])
    demand = demand_at(role, physical, station)
    if demand:
        row.update({"NDF": M(1), "NWT": M(1)})
        if demand[1] is not None:
            wait = duration(*demand)
            row.update({"ROS": M(1), "ROST": M(1), "WT": wait,
                        "WTT": wait, "WTS": wait})
        if role == "current_stock" and station == "BASE-02":
            row["NLD"] = M(1)
    if station == "DEPOT-01":
        row["NRP"] = M(1)
    return row


def stock_total_bin(role: str, physical: dict, i: int) -> dict:
    """StockTotal aggregates the station directly supporting the aircraft.

    The lateral draw is a separate NLD event. An upstream transfer backorder is
    retained in that station's ItemResults, not double-counted as BASE-01 stock.
    """
    base = item_bin(role, physical, "BASE-01", i)
    row = base_row("StockTotalResults")
    for name in COLS["StockTotalResults"]:
        if name in base:
            row[name] = base[name]
    if role == "current_stock" and i == 20:
        row["NLD"] = M(1)
    return row


def enrich_physical(records: list[Event], physical: dict, role: str) -> None:
    physical["depot_repair"] = one(records, r"<TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item", "depot repair")
    at(physical["depot_repair"], 14.1667, "depot repair")
    if role == "current_stock":
        physical["demand_base02"] = one(records, r"<TEACH-LRU-01,0,BASE-02,0> Item demand arrives", "peer demand")
        physical["demand_depot01"] = one(records, r"<TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives", "depot demand")
        at(physical["demand_base02"], 10, "peer demand")
        at(physical["demand_depot01"], 10, "depot demand")
        must_before(physical["demand_base02"], physical["peer_take"])
        must_before(physical["demand_depot01"], physical["depot_take"])
        check(any("<TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,2>" in r.text
                  for r in records if abs(r.time - physical["depot_repair"].time) < 0.00006),
              "repaired physical ID2 returns to depot stock")
    else:
        physical["depot_backorder"] = one(records, r"<TEACH-LRU-01,0,DEPOT-01,0> Backorder added", "depot backorder")
        at(physical["depot_backorder"], 10, "depot backorder")
        must_before(physical["depot_backorder"], physical["depot_clear"])
    # Three station openings are typed, each with one physical IID and the
    # source-declared quantity; a changed identity cannot pass via the reports.
    openings = [r for r in records if "Stock initiated" in r.text]
    check(len(openings) == 3, "three station stock openings")
    expected = {"BASE-01": (0, ""), "DEPOT-01": (1, "<TEACH-LRU-01,0,0>")}
    expected["BASE-02"] = ((1, "<TEACH-LRU-01,0,1>") if role == "current_stock" else (0, ""))
    for station, (qty, item) in expected.items():
        ev = one(openings, rf"<TEACH-LRU-01,0,{station},0> Stock initiated", f"{station} opening")
        check(f"Stock at: <TEACH-LRU-01,0,{station},0> Level: {qty} Items:{item}" in ev.text,
              f"{station} opening quantity and physical ID")


def expected_report(role: str, source: dict, physical: dict, mission: dict,
                    station: str | None) -> dict[str, list[dict]]:
    result = {"ProblemDescription": [{"PDESC": M(source["description"])}],
              "ResultSummary": [expected_summary(source, mission)],
              "SystemResults": expected_system(physical, mission),
              "StockTotalResults": [stock_total_bin(role, physical, i) for i in range(72)]}
    if station is not None:
        mission_rows, mission_total = expected_missions(mission)
        fixed_rows, fixed_total = expected_fixed_rows(mission)
        result.update({"MissionResults": mission_rows, "MissionResultsTotal": [mission_total],
                       "FixedMissionResults": fixed_rows, "FixedMissionResultsTotal": [fixed_total],
                       "ItemResults": [item_bin(role, physical, station, i) for i in range(72)],
                       "ItemResultsTotal": [item_total(role, physical, station)]})
    return result


def metric_bound(metric: Metric) -> float:
    value = metric.value
    if isinstance(value, (str, bool)) or value is None:
        return 0.0
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise AssertionError(f"invalid expected metric {value!r}")
    # Integer-valued whole-bin occupancy and source counts are exact, even
    # when a printed event occurs at a boundary. No blanket boundary slack.
    if float(value).is_integer():
        return 0.0
    if metric.class_name == "exact":
        return 5e-7  # Native float serialization of a source ratio (e.g. 2/3).
    if not metric.denominator or metric.denominator <= 0:
        raise AssertionError("fractional metric without declared denominator")
    computed = sum(edge.uncertainty for edge in metric.edges) / metric.denominator + 5e-7
    ceiling = CONTRACT["report_reconstruction"]["numeric_bound_ceiling"].get(metric.class_name)
    if ceiling is None or computed > ceiling:
        raise AssertionError(f"unknown or excessive numeric bound {metric.class_name}: {computed}")
    return computed


def same_cell(actual, metric: Metric, label: str) -> None:
    expected = metric.value
    if expected is None or isinstance(expected, str):
        check(type(actual) is type(expected) and actual == expected, f"{label}: {actual!r} != {expected!r}")
        return
    check(type(actual) in (int, float) and math.isfinite(float(actual)), f"{label}: wrong numeric type")
    allowed = metric_bound(metric)
    check(abs(float(actual) - float(expected)) <= allowed,
          f"{label}: {actual!r} != {expected!r} (bound {allowed})")


def expected_columns(table_name: str) -> list[dict]:
    result = []
    for name in COLS[table_name]:
        dtype = "string" if name in STRING_COLS else ("integer" if name == "NREP" else "double")
        col = {"datatype": dtype, "name": name}
        if name in KEY_COLS:
            col["key"] = True
        result.append(col)
    return result


def compare_report(report: dict, expected: dict[str, list[dict]], station: str | None) -> int:
    tables = report["report"]["tables"]
    order = TABLE_ORDER_DEFAULT if station is None else TABLE_ORDER_SELECTED
    check([t["name"] for t in tables] == order, f"{station}: native table order")
    checked = 0
    for table in tables:
        name = table["name"]
        check(table["columns"] == expected_columns(name), f"{station}/{name}: column metadata")
        check(len(table["instances"]) == 1 and table["instances"][0]["instance_name"] == "",
              f"{station}/{name}: instance metadata")
        rows = table["instances"][0]["rows"]
        want = expected[name]
        check(len(rows) == len(want), f"{station}/{name}: row count")
        for ri, (values, expected_row) in enumerate(zip(rows, want)):
            check(len(values) == len(COLS[name]) and list(expected_row) == COLS[name],
                  f"{station}/{name}/{ri}: column count/order")
            for ci, field in enumerate(COLS[name]):
                same_cell(values[ci], expected_row[field], f"{station}/{name}/{ri}/{field}")
                checked += 1
    check(checked == (4044 if station is None else 6766), f"{station}: expected cell total")
    return checked


def report_values(report: dict) -> dict:
    return {(table["name"], row_index, ci): value
            for table in report["report"]["tables"]
            for row_index, row in enumerate(table["instances"][0]["rows"])
            for ci, value in enumerate(row)}


def run_gate(parent: dict, run: dict, source_input: Path | None) -> None:
    path = repo_path(run["local_run_directory"])
    closure = parse_native(path / "closure.json")
    invocation = parse_native(path / "invocation.json")
    check(closure.get("error") is None and closure.get("invocation_sha256") == digest(path / "invocation.json")["sha256"],
          f"{run['run_id']}: sealed closure")
    check(closure.get("source_hashes_before") == closure.get("source_hashes_after") ==
          invocation.get("source_hashes_before"), f"{run['run_id']}: source stability")
    check(invocation.get("session_id") == 0 and "sshd.exe" in invocation.get("ssh_ancestor_names", [])
          and invocation.get("queue_mutex") == r"Global\SimloxIssue18NativeQueue"
          and invocation.get("gui", {}).get("pid") == 13340
          and invocation.get("gui", {}).get("session_id") == 1, f"{run['run_id']}: session/GUI/mutex")
    if source_input is not None:
        check(invocation.get("input_sha256") == digest(source_input)["sha256"] ==
              digest(path / "input.json")["sha256"], f"{run['run_id']}: source binding")
        steps = parse_native(path / "steps.json")
        check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"]
              and all(s.get("exit_code") == 0 and s.get("gui_preserved") for s in steps),
              f"{run['run_id']}: five native stages")
        check("Input conversion completed. Errors: 0" in
              (path / "run.log").read_text(encoding="utf-8-sig"), f"{run['run_id']}: converter")
        source_tables = input_tables(source_input)
        roundtrip = input_tables(path / "roundtrip-raw.json")
        def populated(tables):
            return {name: {"columns": table["columns"],
                           "rows": [row for ins in table["instances"] for row in ins["rows"]]}
                    for name, table in tables.items()
                    if any(ins["rows"] for ins in table["instances"])}
        before, after = populated(source_tables), populated(roundtrip)
        check(len(before) == (24 if parent["role"] == "current_stock" else 25) and
              all(after.get(name) == table for name, table in before.items()),
              f"{run['run_id']}: authored tables roundtrip")


def replay() -> dict:
    source_pins = verify_all_pins()
    parent_current, parent_future = CONTRACT["accepted_parents"]
    current_input = repo_path(CONTRACT["source_comparison"]["current_input"]["path"])
    future_input = repo_path(CONTRACT["source_comparison"]["future_input"]["path"])
    model_gate(current_input, future_input)
    inputs = [(parent_current, "current_stock", "on", current_input),
              (parent_future, "scheduled_future_stock", "off", future_input)]
    native_reports = {}
    total_cells = 0
    for parent, role, contrast, source_input in inputs:
        source = source_fields(input_tables(source_input))
        model_run = next(r for r in parent["runs"] if r["role"] == "native" and r["contrast"] == contrast)
        run_gate(parent, model_run, source_input)
        runpath = repo_path(model_run["local_run_directory"])
        event_records = events(runpath / "model.log")
        physical = physical_gate(event_records, role)
        enrich_physical(event_records, physical, role)
        mission = mission_gate(event_records, source)
        native_reports[(role, None)] = parse_native(runpath / "report-raw.json")
        total_cells += compare_report(native_reports[(role, None)],
                                      expected_report(role, source, physical, mission, None), None)
        for run in parent["runs"]:
            if run["role"] != "station_report" or run["contrast"] != contrast:
                continue
            run_gate(parent, run, None)
            station = run["station"].replace("-", "").upper()
            station = {"BASE01": "BASE-01", "BASE02": "BASE-02", "DEPOT": "DEPOT-01"}[station]
            path = repo_path(run["local_run_directory"])
            native_reports[(role, station)] = parse_native(path / "item-report-raw.json")
            total_cells += compare_report(native_reports[(role, station)],
                                          expected_report(role, source, physical, mission, station), station)
        check(all((role, s) in native_reports for s in STATIONS), f"{role}: all three station selectors")
    check(total_cells == 48684, "48,684 expected report cells checked")
    deltas = {}
    for station in [None, *STATIONS]:
        a = report_values(native_reports[("current_stock", station)])
        b = report_values(native_reports[("scheduled_future_stock", station)])
        check(a.keys() == b.keys(), f"{station}: paired table topology")
        counts = {}
        for key in a:
            if a[key] != b[key]:
                counts[key[0]] = counts.get(key[0], 0) + 1
        key = "default" if station is None else station
        expected_diff = CONTRACT["report_reconstruction"]["observed_difference_counts_for_crosscheck_only"][key]
        check({**counts, "total": sum(counts.values())} == expected_diff, f"{key}: descriptive changed cells")
        deltas[key] = counts
    return {"schema": "e08-var04-author-readonly-replay/v1", "decision": "AUTHOR_PASS_PENDING_INDEPENDENT",
            "source_pin_checks": source_pins, "report_cells_checked": total_cells,
            "direct_arms": ["E08.var01/on current stock", "E08.var03/off scheduled future stock"],
            "new_native_runs": 0, "paired_cell_differences": deltas}


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2, sort_keys=True))

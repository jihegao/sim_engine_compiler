"""Independent read-only E08.var04 replay from source and typed native events.

No parent checker is imported. The expected report rows below are constructed from
the two frozen authored models and their physical event logs, never from another
native report. Raw reports are only read at the final comparison boundary.
"""

import hashlib
import copy
import json
import math
import pathlib
import re
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[4]
PACKAGE = pathlib.Path(__file__).resolve().parents[1]
CONTRACT_PATH = PACKAGE / "contract.json"
CONTRACT_SHA = "b95349ff646d5faaf2d754cce2624e39735bdf772865f294a93828140596bad3"


def insist(condition, label):
    if not condition:
        raise AssertionError(label)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pin(path, expected):
    data = path.read_bytes()
    insist(len(data) == expected["bytes"] and sha(data) == expected["sha256"], f"pin {path}")
    return data


def tolerant_json_bytes(data):
    """Parse native trailing commas on a normalized copy, never changing raw bytes."""
    source = data.decode("utf-8-sig")
    out = []
    quoted = False
    escaped = False
    for index, char in enumerate(source):
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
        elif char == ",":
            look = index + 1
            while look < len(source) and source[look].isspace():
                look += 1
            if look == len(source) or source[look] not in "}]":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def table(model, name):
    matches = [entry for entry in model["tables"] if entry["name"] == name]
    insist(len(matches) == 1, f"source table {name}")
    return matches[0]


def source_rows(model, name):
    return [row for instance in table(model, name)["instances"] for row in instance["rows"]]


def source_map(model, name):
    entity = table(model, name)
    cols = [column["name"] for column in entity["columns"]]
    return [dict(zip(cols, row)) for row in source_rows(model, name)]


def rows(entity):
    return [row for instance in entity["instances"] for row in instance["rows"]]


def unique_time(lines, expression, label):
    matches = []
    regex = re.compile(expression)
    for index, line in enumerate(lines):
        matched = regex.search(line)
        if matched:
            matches.append((float(matched.group(1)), index, matched))
    insist(len(matches) == 1, f"{label}: {len(matches)}")
    return matches[0]


def event_times(lines, expression):
    regex = re.compile(expression)
    result = []
    for index, line in enumerate(lines):
        matched = regex.search(line)
        if matched:
            result.append((float(matched.group(1)), index))
    return result


def coverage(windows, start, end):
    return sum(max(0.0, min(end, right) - max(start, left)) for left, right in windows)


def fraction(windows, start, end):
    value = coverage(windows, start, end) / (end - start)
    if abs(value) < 1e-12:
        return 0.0, "exact"
    if abs(value - 1) < 1e-12:
        return 1.0, "exact"
    return value, "half_hour"


def event_count(times, start, end):
    return sum(start <= time < end for time in times)


def lexical_line(lines, token):
    return [index for index, line in enumerate(lines) if token in line]


def stock_windows(initial, events):
    state = initial
    position = 0.0
    windows = []
    for when, change in sorted(events, key=lambda item: item[0]):
        insist(0 <= position <= when <= 36, "ordered stock event")
        windows.append((position, when, state))
        state += change
        insist(state >= 0, "negative stock/backorders")
        position = when
    windows.append((position, 36.0, state))
    return windows


def weighted(windows, start, end):
    return sum(max(0.0, min(end, right) - max(start, left)) * value
               for left, right, value in windows) / (end - start)


def station_ledger(arm):
    lines = arm["lines"]
    stations = ("BASE-01", "BASE-02", "DEPOT-01")
    changes = {station: {"physical": [], "backorder": [], "nominal": []} for station in stations}
    demand = {station: [] for station in stations}
    repair = {station: [] for station in stations}
    stock_ids = {}
    taken = []
    returned = []
    current_time = None
    for line_number, line in enumerate(lines):
        prefix = re.match(r"^Time: ([0-9.]+) (.*)$", line)
        if prefix:
            current_time = float(prefix.group(1))
            body = prefix.group(2)
            stock_station = re.search(r"<TEACH-LRU-01,0,(BASE-01|BASE-02|DEPOT-01),0>", body)
            if stock_station:
                station = stock_station.group(1)
                item_take = re.search(r"Take replacement item <TEACH-LRU-01,0,([0-9]+)> from stock", body)
                item_put = re.search(r"Put back replacement item <TEACH-LRU-01,0,([0-9]+)> to stock", body)
                if item_take:
                    identity = int(item_take.group(1))
                    changes[station]["physical"].append((current_time, -1))
                    taken.append((current_time, station, identity, line_number))
                if item_put:
                    identity = int(item_put.group(1))
                    changes[station]["physical"].append((current_time, 1))
                    returned.append((current_time, station, identity, line_number))
                if "Item demand arrives from pos" in body:
                    demand[station].append(current_time)
                if "Backorder added" in body:
                    changes[station]["backorder"].append((current_time, 1))
                if "Backorder removed" in body:
                    changes[station]["backorder"].append((current_time, -1))
                if "Finished repair of item" in body:
                    repair[station].append(current_time)
            continue
        if "Stock at:" in line and current_time == 0:
            item = re.search(r"Stock at: <TEACH-LRU-01,0,(BASE-01|BASE-02|DEPOT-01),0> Level: ([0-9]+) Items:(.*)$", line)
            if item:
                station, level, rest = item.groups()
                identities = [int(value) for value in re.findall(r"<TEACH-LRU-01,0,([0-9]+)>", rest)]
                insist(int(level) == len(identities) == arm["stock"][station], "opening physical stock")
                stock_ids[station] = identities
    insist(set(stock_ids) == set(stations), "all opening stock rows")
    insist(len(set(identity for group in stock_ids.values() for identity in group)) == sum(len(group) for group in stock_ids.values()), "opening physical IDs unique")
    transfer = [] if arm["current"] else source_map(arm["source"], "ItemTransfer")
    for row in transfer:
        insist(row["TFQTY"] == 1, "transfer quantity")
        changes[row["STFID"]]["nominal"].append((row["TFTIME"], -1))
        changes[row["STTID"]]["nominal"].append((row["TFTIME"] + row["TFDT"], 1))
    ledger = {}
    for station in stations:
        nominal = stock_windows(arm["stock"][station], changes[station]["nominal"])
        physical = stock_windows(len(stock_ids[station]), changes[station]["physical"])
        backorders = stock_windows(0, changes[station]["backorder"])
        insist(all(value in (0, 1) for _, _, value in nominal + physical + backorders), f"station capacity {station}")
        insist(weighted(backorders, 35.5, 36) == 0, f"terminal backorder {station}")
        ledger[station] = {"nominal": nominal, "physical": physical, "backorders": backorders,
                           "demand": demand[station], "repair": repair[station]}
    insist([len(demand[station]) for station in stations] == ([1, 1, 1] if arm["current"] else [1, 0, 1]), "typed demand counts")
    insist(repair["DEPOT-01"] == [14.1667], "depot repair completion")
    insist(not repair["BASE-01"] and not repair["BASE-02"], "no base item repair")
    insist(sum(len(group) for group in stock_ids.values()) == (2 if arm["current"] else 1), "opening item quantity")
    # Bound the observed serial trace without asserting that native-generated repair
    # IDs preserve the opening serial after a removal/replacement cycle.
    insist([(time, station, identity) for time, station, identity, _ in taken] ==
           ([(10.0, "BASE-02", 1), (10.0, "DEPOT-01", 0)] if arm["current"] else
            [(9.0, "DEPOT-01", 0)]), "typed stock take trace")
    insist([(time, station, identity) for time, station, identity, _ in returned] ==
           ([(11.0, "BASE-02", 0), (14.1667, "DEPOT-01", 2)] if arm["current"] else
            [(11.0, "BASE-02", 0)]), "typed stock return trace")
    insist(not set(identity for group in stock_ids.values() for identity in group).intersection(
        {2} if arm["current"] else {1}), "failed item has generated ID")
    arm["taken"] = taken
    arm["returned"] = returned
    arm["stock_ids"] = stock_ids
    return ledger


def parsed_arm(parent, contract):
    arm = parent["direct_contrast"]
    current = parent["role"] == "current_stock"
    run = next(run for run in parent["runs"] if run["role"] == "native" and run["contrast"] == arm)
    directory = ROOT / run["local_run_directory"]
    for filename, expected in run["files"].items():
        pin(directory / filename, expected)
    log_bytes = (directory / "model.log").read_bytes()
    log = log_bytes.decode("utf-8-sig", errors="strict")
    lines = log.splitlines()
    source_path = ROOT / contract["source_comparison"]["current_input" if current else "future_input"]["path"]
    source = tolerant_json_bytes(source_path.read_bytes())["model"]
    insist(source["database_version"] == 20160627, "database version")
    control = source_map(source, "Control")[0]
    lateral = source_map(source, "LateralSupport")[0]
    mission_type = source_map(source, "MissionType")[0]
    profile = source_map(source, "OperationProfile")
    stock = {row["STID"]: row["STSIZ"] for row in source_map(source, "StockAllocation") if row["IID"] == "TEACH-LRU-01"}
    insist(control["ENLAT"] == "Y" and lateral["DLAYL"] == "N" and lateral["LSRUL"] == "IMMEDIATE", "source lateral mode")
    insist(mission_type["MTID"] == "BASIC-MISSION" and mission_type["NOS"] == 1 and mission_type["DURN"] == 2, "mission type")
    schedule = sorted(row["STIM"] for row in profile if row["SPRID"] == "BASIC-MISSION")
    insist(schedule == [8, 20, 32] and control["SIMPE"] == 36, "schedule/horizon")
    insist(stock["BASE-01"] == 0 and stock["DEPOT-01"] == 1 and stock["BASE-02"] == (1 if current else 0), "opening allocation")
    if current:
        insist(not source_rows(source, "ItemTransfer") if any(t["name"] == "ItemTransfer" for t in source["tables"]) else True, "no scheduled transfer")
    else:
        transfer = source_map(source, "ItemTransfer")
        insist(len(transfer) == 1 and tuple(transfer[0][key] for key in ("STFID", "STTID", "IID", "TFTIME", "TFQTY", "TFDT")) == ("DEPOT-01", "BASE-02", "TEACH-LRU-01", 9, 1, 2), "scheduled transfer")

    ordered = event_times(lines, r"^Time: ([0-9.]+) <TEACH-UNIT> mission ordered: BASIC-MISSION$")
    started = event_times(lines, r"^Time: ([0-9.]+) <BASIC-MISSION,[^>]+> mission starting, duration: 2")
    completed = event_times(lines, r"^Time: ([0-9.]+) <BASIC-MISSION,[^>]+> (?:aborted mission completed|mission completed):")
    succeeded = event_times(lines, r"^Time: ([0-9.]+) <BASIC-MISSION,[^>]+> mission success:")
    insist([time for time, _ in ordered] == [7, 19, 31], "mission orders")
    insist([time for time, _ in started] == schedule, "mission starts")
    insist([time for time, _ in completed] == [10, 22, 34], "mission completions")
    insist([time for time, _ in succeeded] == [22, 34], "mission successes")
    failure, failure_line, _ = unique_time(lines, r"^Time: ([0-9.]+) <TEACH-AIR-01,0> critical random failure added", "critical failure")
    insist(failure == 9.8829 and started[0][1] < failure_line < completed[0][1], "failure mission order")
    repair_start, rs_line, _ = unique_time(lines, r"^Time: ([0-9.]+)  system SURP task 0 on <TEACH-AIR-01,0> started$", "SURP start")
    remove_done, rd_line, _ = unique_time(lines, r"^Time: ([0-9.]+)  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed$", "remove complete")
    fit_work, fw_line, _ = unique_time(lines, r"^Time: ([0-9.]+)  fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> starts performing", "fit work")
    repair_done, rp_line, _ = unique_time(lines, r"^Time: ([0-9.]+)  system SURP task 0 on <TEACH-AIR-01,0> completed$", "SURP complete")
    backorder_open, bo_line, _ = unique_time(lines, r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Backorder added", "BASE-01 backorder open")
    backorder_done, bc_line, _ = unique_time(lines, r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was", "BASE-01 backorder close")
    insist((repair_start, remove_done, fit_work, repair_done, backorder_open, backorder_done) == (10, 10.1667, 10.5 if current else 15.1667, 10.8333 if current else 15.5, 10, 10.5 if current else 15.1667), "repair/backorder chronology")
    insist(rs_line < rd_line < fw_line < rp_line and bo_line < bc_line, "repair line order")
    if current:
        insist(len(lexical_line(lines, "Lateral support from: <TEACH-LRU-01,0,BASE-02,0>")) == 1, "typed lateral route")
        insist(len(lexical_line(lines, "Take replacement item <TEACH-LRU-01,0,1> from stock")) == 1, "peer ID1 take")
        insist(len(lexical_line(lines, "Replacement item arrives <TEACH-LRU-01,0,1>")) == 1, "BASE-01 ID1 receive")
    else:
        insist(not lexical_line(lines, "Lateral support from:"), "no future lateral shipment")
        insist(len(lexical_line(lines, "item transfer task 0 (BETWEEN)  created:")) == 1, "scheduled transfer task")
        insist(len(lexical_line(lines, "Put back replacement item <TEACH-LRU-01,0,0> to stock")) == 1, "future peer ID0 stock")

    mission = [(float(started[i][0]), float(completed[i][0])) for i in range(3)]
    assignment = [(float(ordered[i][0]), float(completed[i][0])) for i in range(3)]
    preparation = [(float(ordered[i][0]), float(started[i][0])) for i in range(3)]
    ready = [(0.0, float(ordered[0][0])), (repair_done, float(ordered[1][0])), (float(completed[1][0]), float(ordered[2][0])), (float(completed[2][0]), 36.0)]
    arm_data = {
        "current": current, "run": run, "directory": directory, "lines": lines, "source": source,
        "mission_type": mission_type, "description": source_rows(source, "ProblemDescription")[0][0],
        "orders": [time for time, _ in ordered], "starts": [time for time, _ in started],
        "completions": [time for time, _ in completed], "successes": [time for time, _ in succeeded],
        "failure": failure, "repair_start": repair_start, "remove_done": remove_done,
        "fit_work": fit_work, "repair_done": repair_done, "backorder_open": backorder_open,
        "backorder_done": backorder_done, "mission": mission, "assignment": assignment,
        "preparation": preparation, "ready": ready, "stock": stock,
    }
    arm_data["station_ledger"] = station_ledger(arm_data)
    if current:
        lateral, lateral_line, _ = unique_time(lines, r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Lateral support from: <TEACH-LRU-01,0,BASE-02,0>$", "current peer selection")
        ship_start, ship_line, _ = unique_time(lines, r"^Time: ([0-9.]+)  transport task 0 starts with 1 items/systems, transport time: 0.5$", "current peer departure")
        ship_arrive, arrive_line, _ = unique_time(lines, r"^Time: ([0-9.]+)  transport task 0 arrives with 1 items/systems$", "current peer arrival")
        peer_receive, receive_line, _ = unique_time(lines, r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>$", "current peer ID1 receive")
        insist((lateral, ship_start, ship_arrive, peer_receive) == (10, 10, 10.5, 10.5), "current typed peer timeline")
        insist(bo_line < lateral_line < ship_line < arrive_line < receive_line < bc_line < fw_line, "current peer line edges")
        insist(any("transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-02,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  transport task 0" in line for line in lines), "current peer task request ID")
    else:
        transfer_start, ts_line, _ = unique_time(lines, r"^Time: ([0-9.]+)  item transfer task 0 \(BETWEEN\)  starts with 1 items, transfer time: 2$", "future scheduled transfer start")
        transfer_arrive, ta_line, _ = unique_time(lines, r"^Time: ([0-9.]+)  item transfer task 0 \(BETWEEN\)  arrives with 1 items$", "future scheduled transfer arrival")
        depot_wait, dw_line, _ = unique_time(lines, r"^Time: ([0-9.]+) <TEACH-LRU-01,0,DEPOT-01,0> Backorder added", "future depot shortage")
        depot_fill, df_line, _ = unique_time(lines, r"^Time: ([0-9.]+) <TEACH-LRU-01,0,DEPOT-01,0> Backorder removed", "future depot fill")
        ordinary_start, os_line, _ = unique_time(lines, r"^Time: ([0-9.]+)  transport task 2 starts with 1 items/systems, transport time: 1$", "future ordinary departure")
        ordinary_arrive, oa_line, _ = unique_time(lines, r"^Time: ([0-9.]+)  transport task 2 arrives with 1 items/systems$", "future ordinary arrival")
        insist((transfer_start, transfer_arrive, depot_wait, depot_fill, ordinary_start, ordinary_arrive) == (9, 11, 10, 14.1667, 14.1667, 15.1667), "future typed timeline")
        insist(ts_line < dw_line < ta_line < df_line < os_line < oa_line < bc_line < fw_line, "future typed line edges")
        insist(any("transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  transport task 2" in line for line in lines), "future ordinary task request ID")
    return arm_data


def expected_summary(arm):
    successes = len(arm["successes"])
    attempts = len(arm["starts"])
    return [{
        "NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": 1, "RSMTMF": 0,
        "MSTF": 1, "RSMSTF": 0, "MSUF": successes / attempts,
        "RSMSUF": 0, "STMF": 1, "RSSTMF": 0,
    }]


def expected_missions(arm):
    result = []
    for index in range(72):
        left, right = index / 2, (index + 1) / 2
        occupied, cls = fraction(arm["mission"], left, right)
        insist(cls == "exact", "source-fixed mission interval")
        result.append({
            "UNID": "Total over all Units", "MTID": "Total over all Missions",
            "STINT": left, "ETINT": right, "MTREQ": occupied, "MTACC": occupied,
            "MTF": 1 if occupied else None, "MTLOW": None,
            "STREQ": occupied, "STACC": occupied,
            "STF": 1 if occupied else None, "STLOW": None,
        })
    return result


def expected_missions_total(arm):
    occupied = sum(right - left for left, right in arm["mission"]) / 36
    return [{"UNID": "Total over all Units", "MTID": "Total over all Missions",
             "MTREQ": occupied, "MTACC": occupied, "MTF": 1, "MTLOW": None,
             "STREQ": occupied, "STACC": occupied, "STF": 1, "STLOW": None}]


def expected_fixed(arm):
    duration = arm["mission_type"]["DURN"]
    nos = arm["mission_type"]["NOS"]
    result = []
    for start in arm["starts"]:
        success = int(start + duration in arm["successes"])
        result.append({
            "UNID": "Total over all Units", "MTID": "Total over all Missions", "STIM": start,
            "NMREQ": 1, "NMSTA": 1, "NMSUC": success,
            "MTREQ": duration, "MTACC": duration, "MTF": 1,
            "FMSTA": 1, "FMSUC": success, "NSYRQ": nos,
            "NSYST": nos, "NSYSU": success * nos, "AVSTD": 0,
            "MTOT": 1, "NSYOT": nos, "STOT": 1,
            "STREQ": duration, "NSYMO": nos,
            "STACC": duration, "STF": 1, "STOTD": 0,
            "NPSTA": 0, "NPSUC": 0,
        })
    return result


def expected_fixed_total(fixed):
    totals = {name: 0 for name in fixed[0] if name not in ("UNID", "MTID", "STIM")}
    for row in fixed:
        for name in totals:
            totals[name] += row[name]
    totals["FMSUC"] = totals["FMSUC"] / len(fixed)
    totals["FMSTA"] = 1
    totals["MTF"] = 1
    totals["STF"] = 1
    totals["AVSTD"] = 0
    totals["NSYMO"] = len(fixed)
    totals.pop("STOTD")
    return [{"UNID": "Total over all Units", "MTID": "Total over all Missions", **totals}]


def expected_system(arm):
    result = []
    active_repair = [(arm["repair_start"], arm["remove_done"]), (arm["fit_work"], arm["repair_done"])]
    wait_item = [(arm["remove_done"], arm["fit_work"])]
    unavailable = [(arm["repair_start"], arm["repair_done"])]
    for index in range(72):
        left, right = index / 2, (index + 1) / 2
        row = {name: 0 for name in SYSTEM_COLUMNS if name not in ("UNID", "SID", "STINT", "ETINT", "SYDT")}
        row.update({"UNID": "Total over all Units", "SID": "Total over all Systems", "STINT": left, "ETINT": right, "SYDT": None})
        for field, windows in [
            ("NSYRY", arm["ready"]), ("NSYMA", arm["assignment"]),
            ("NSYMO", arm["mission"]), ("NSYMR", arm["preparation"]),
            ("NSYUA", unavailable),
            ("FTMO", arm["mission"]), ("NSYRP", active_repair),
            ("NSYWI", wait_item), ("STACC", arm["mission"]),
        ]:
            row[field] = fraction(windows, left, right)[0]
        row["NSYA"] = 1 - row["NSYUA"]
        row["NFAIL"] = event_count([arm["failure"]], left, right)
        row["NREPT"] = event_count([arm["repair_done"]], left, right)
        row["NSYDT"] = event_count([arm["repair_start"]], left, right)
        if row["NSYDT"]:
            row["SYDT"] = arm["repair_done"] - arm["repair_start"]
        result.append(row)
    return result


SYSTEM_COLUMNS = (
    "UNID SID STINT ETINT NSYRY NSYMA NSYMO NSYMC NSYMP NSYMT NSYMS NSYMR NSYUA NSYA NSYAL FTMO NSYRP NSYPM NSYTP NSYWR NSYWI NSYLA NSYUH NREPT NPMT NFAIL NDAM NPMS NROBT NRCFG STREQ STACC STF STLOW SYDT SYDTU NSYDT NSYSW NPSTA NPSUC"
).split()


ITEM_COLUMNS = (
    "IID STID STINT ETINT STSZ STOHA NBO ROS ROST WT WTT WTS PNB NDF NDD NDR NDP NLD NRP NRO NPM NCS NWT NRB"
).split()
ITEM_TOTAL_COLUMNS = [name for name in ITEM_COLUMNS if name not in ("STINT", "ETINT")]
STOCK_COLUMNS = "STINT ETINT NBO NBOU ROS ROST WT WTT WTS PNB NDF NDD NDR NDP NLD NWT".split()
SUMMARY_COLUMNS = "NREP RTILW RTIUP MTMF RSMTMF MSTF RSMSTF MSUF RSMSUF STMF RSSTMF".split()
MISSION_COLUMNS = "UNID MTID STINT ETINT MTREQ MTACC MTF MTLOW STREQ STACC STF STLOW".split()
MISSION_TOTAL_COLUMNS = [name for name in MISSION_COLUMNS if name not in ("STINT", "ETINT")]
FIXED_COLUMNS = "UNID MTID STIM NMREQ NMSTA NMSUC MTREQ MTACC MTF FMSTA FMSUC NSYRQ NSYST NSYSU AVSTD MTOT NSYOT STOT STREQ NSYMO STACC STF STOTD NPSTA NPSUC".split()
FIXED_TOTAL_COLUMNS = [name for name in FIXED_COLUMNS if name not in ("STIM", "STOTD")]
TABLE_COLUMNS = {
    "ProblemDescription": ["PDESC"], "ResultSummary": SUMMARY_COLUMNS,
    "MissionResults": MISSION_COLUMNS, "MissionResultsTotal": MISSION_TOTAL_COLUMNS,
    "FixedMissionResults": FIXED_COLUMNS, "FixedMissionResultsTotal": FIXED_TOTAL_COLUMNS,
    "SystemResults": SYSTEM_COLUMNS, "ItemResults": ITEM_COLUMNS,
    "ItemResultsTotal": ITEM_TOTAL_COLUMNS, "StockTotalResults": STOCK_COLUMNS,
}


def metadata_columns(table_name):
    result = []
    for name in TABLE_COLUMNS[table_name]:
        datatype = "integer" if table_name == "ResultSummary" and name == "NREP" else "string" if name in ("PDESC", "UNID", "MTID", "SID", "IID", "STID") else "double"
        column = {"datatype": datatype, "name": name}
        key = (name in ("UNID", "MTID", "SID", "IID", "STID") or
               name in ("STINT", "ETINT") and table_name in ("MissionResults", "SystemResults", "ItemResults", "StockTotalResults") or
               name == "STIM" and table_name == "FixedMissionResults")
        if key:
            column["key"] = True
        result.append(column)
    return result


def numeric_class(table_name, name, expected):
    if expected is None or isinstance(expected, (str, bool)):
        return "exact"
    insist(math.isfinite(expected), f"finite expected {table_name}.{name}")
    if name in ("STINT", "ETINT", "STIM"):
        return "exact"
    if expected == 0 or float(expected).is_integer():
        if name in ("SYDT", "WT", "WTT", "WTS") and expected != 0:
            return "elapsed"
        return "exact"
    if table_name in ("SystemResults", "ItemResults", "StockTotalResults") and name in (
        "NSYRY", "NSYMA", "NSYMO", "NSYMR", "NSYUA", "NSYA", "FTMO", "NSYRP", "NSYWI", "STACC",
        "STSZ", "STOHA", "NBO", "PNB"):
        return "half_hour"
    if table_name == "ItemResultsTotal" and name in ("STSZ", "STOHA", "NBO", "PNB"):
        return "thirty_six_hour"
    if name in ("SYDT", "WT", "WTT", "WTS"):
        return "elapsed"
    if (table_name, name) in (("ResultSummary", "MSUF"), ("MissionResultsTotal", "MTREQ"),
                              ("MissionResultsTotal", "MTACC"), ("MissionResultsTotal", "STREQ"),
                              ("MissionResultsTotal", "STACC"), ("FixedMissionResultsTotal", "FMSUC")):
        return "serialization"
    raise AssertionError(f"unknown numeric formula {table_name}.{name}: {expected}")


def printed_edge_uncertainty(time):
    # Whole and half-hour edges are authored schedule/transfer/transport constants
    # in these two sealed arms. Other native event edges have the printed precision.
    if abs(time * 2 - round(time * 2)) < 1e-10:
        return 0.0
    token = str(time)
    insist("." in token, f"nonintegral printed edge {token}")
    return 0.5 * 10 ** -len(token.split(".", 1)[1])


def propagated_limit(category, arm, station, table_name, name, row_number, ceilings):
    serial = ceilings["report_serialization_allowance_absolute"]
    if category == "serialization":
        return serial
    if category == "half_hour":
        start, end = row_number / 2, (row_number + 1) / 2
        if table_name == "SystemResults":
            relevant = (arm["repair_start"], arm["remove_done"], arm["fit_work"], arm["repair_done"])
        else:
            ledger = arm["station_ledger"]["BASE-01" if table_name == "StockTotalResults" else station]
            windows = ledger["nominal"] + ledger["physical"] + ledger["backorders"]
            relevant = tuple(time for left, right, _ in windows for time in (left, right))
        uncertainty = sum(printed_edge_uncertainty(time) for time in set(relevant) if start < time < end)
        value = uncertainty / 0.5 + serial
        ceiling = ceilings["half_hour_time_weighted_fraction_absolute"]
    elif category == "thirty_six_hour":
        ledger = arm["station_ledger"][station]
        windows = ledger["nominal"] + ledger["physical"] + ledger["backorders"]
        relevant = {time for left, right, _ in windows for time in (left, right)}
        value = sum(printed_edge_uncertainty(time) for time in relevant) / 36 + serial
        ceiling = ceilings["thirty_six_hour_mean_from_printed_edges_absolute"]
    elif category == "elapsed":
        if name == "SYDT":
            relevant = (arm["repair_start"], arm["repair_done"])
        else:
            ledger = arm["station_ledger"]["BASE-01" if table_name == "StockTotalResults" else station]
            relevant = {time for left, right, value in ledger["backorders"] if value for time in (left, right)}
        value = sum(printed_edge_uncertainty(time) for time in set(relevant)) + serial
        ceiling = ceilings["elapsed_hours_from_printed_edges_absolute"]
    else:
        raise AssertionError(f"unclassified propagated bound {category}")
    insist(value <= ceiling, f"propagated {category} bound {value} exceeds frozen {ceiling}")
    return value


def compare_cell(table_name, name, observed, expected, limit):
    category = numeric_class(table_name, name, expected)
    if category == "exact":
        insist(type(observed) is type(expected) or
               type(observed) in (int, float) and type(expected) in (int, float) and
               not isinstance(observed, bool) and not isinstance(expected, bool),
               f"type {table_name}.{name}: {observed!r}/{expected!r}")
        insist(observed == expected, f"exact {table_name}.{name}: {observed!r}/{expected!r}")
        return
    insist(type(observed) in (int, float) and math.isfinite(observed), f"numeric type {table_name}.{name}")
    insist(abs(observed - expected) <= limit,
           f"{category} {table_name}.{name}: {observed!r}/{expected!r} > {limit}")


def expected_tables(arm, station=None):
    fixed = expected_fixed(arm)
    result = {"ProblemDescription": [{"PDESC": arm["description"]}],
              "ResultSummary": expected_summary(arm),
              "SystemResults": expected_system(arm),
              "StockTotalResults": expected_stock_total(arm)}
    if station is not None:
        result.update({"MissionResults": expected_missions(arm),
                       "MissionResultsTotal": expected_missions_total(arm),
                       "FixedMissionResults": fixed,
                       "FixedMissionResultsTotal": expected_fixed_total(fixed),
                       "ItemResults": expected_item(arm, station),
                       "ItemResultsTotal": expected_item_total(arm, station)})
    return result


def compare_report(arm, station, path, contract, *, supplied_tables=None):
    output = supplied_tables if supplied_tables is not None else tolerant_json_bytes(path.read_bytes())["report"]["tables"]
    wanted = expected_tables(arm, station)
    shape = contract["report_reconstruction"]["selected_station_per_arm" if station else "default_per_direct_arm"]
    insist([table["name"] for table in output] == shape["table_order"], f"table order {station}")
    count = 0
    ceilings = contract["report_reconstruction"]["numeric_bound_ceiling"]
    for entity, dimension in zip(output, shape["dimensions"]):
        table_name = entity["name"]
        insist(entity["columns"] == metadata_columns(table_name), f"column metadata {table_name}")
        insist(len(entity["instances"]) == 1, f"instance count {table_name}")
        instance_name = "" if station is not None or table_name in ("ProblemDescription", "ResultSummary") else (
            "Total over all Units;Total over all Systems;0.00;36.00" if table_name == "SystemResults" else "0.00;36.00;")
        insist(entity["instances"][0]["instance_name"] == instance_name, f"instance name {table_name}")
        actual_rows = rows(entity)
        expected_rows = wanted[table_name]
        insist(len(actual_rows) == dimension[0] == len(expected_rows), f"row count {table_name}")
        insist(len(entity["columns"]) == dimension[1], f"column count {table_name}")
        for row_number, (observed, expected) in enumerate(zip(actual_rows, expected_rows)):
            insist(len(observed) == dimension[1] and set(expected) == set(TABLE_COLUMNS[table_name]),
                   f"row schema {table_name}:{row_number}")
            for name, value in zip(TABLE_COLUMNS[table_name], observed):
                try:
                    category = numeric_class(table_name, name, expected[name])
                    limit = 0 if category == "exact" else propagated_limit(category, arm, station, table_name, name, row_number, ceilings)
                    compare_cell(table_name, name, value, expected[name], limit)
                except AssertionError as exc:
                    raise AssertionError(f"{path.name}:{station}:{table_name}[{row_number}].{name}: {exc}") from exc
                count += 1
    return count


def reject(label, operation):
    try:
        operation()
    except AssertionError:
        return
    raise AssertionError(f"negative fixture falsely accepted: {label}")


def mutation_probes(contract, arms):
    """Mutate parsed in-memory evidence, so a raw-file hash gate cannot mask semantic gaps."""
    current, future = arms
    probes = 0
    current_tables = tolerant_json_bytes((current["directory"] / "report-raw.json").read_bytes())["report"]["tables"]
    future_depot_run = next(run for run in contract["accepted_parents"][1]["runs"]
                            if run["role"] == "station_report" and run["contrast"] == "off" and run["station"] == "depot")
    future_depot_path = ROOT / future_depot_run["local_run_directory"] / "item-report-raw.json"
    future_depot_tables = tolerant_json_bytes(future_depot_path.read_bytes())["report"]["tables"]
    current_peer_run = next(run for run in contract["accepted_parents"][0]["runs"]
                            if run["role"] == "station_report" and run["contrast"] == "on" and run["station"] == "base02")
    current_peer_path = ROOT / current_peer_run["local_run_directory"] / "item-report-raw.json"
    current_peer_tables = tolerant_json_bytes(current_peer_path.read_bytes())["report"]["tables"]

    def changed(tables, table_name, row_number, field, value):
        altered = copy.deepcopy(tables)
        entity = next(table for table in altered if table["name"] == table_name)
        position = next(index for index, column in enumerate(entity["columns"]) if column["name"] == field)
        rows(entity)[row_number][position] = value
        return altered

    cases = [
        ("whole-bin zero residue", current, None, current["directory"] / "report-raw.json",
         changed(current_tables, "SystemResults", 0, "NSYMO", 1e-9)),
        ("integer count residue", current, None, current["directory"] / "report-raw.json",
         changed(current_tables, "SystemResults", 19, "NFAIL", 1.000000001)),
        ("null to numeric", current, None, current["directory"] / "report-raw.json",
         changed(current_tables, "SystemResults", 0, "SYDT", 0)),
        ("no-demand null to zero", current, "BASE-02", current_peer_path,
         changed(current_peer_tables, "ItemResults", 0, "ROS", 0)),
        ("immediately served demand zero to null", current, "BASE-02", current_peer_path,
         changed(current_peer_tables, "ItemResults", 20, "ROS", None)),
        ("36h stock mean beyond bound", future, "DEPOT-01", future_depot_path,
         changed(future_depot_tables, "ItemResultsTotal", 0, "STOHA", expected_item_total(future, "DEPOT-01")[0]["STOHA"] + 0.0001)),
        ("event-edge bin fraction beyond propagated bound", current, None, current["directory"] / "report-raw.json",
         changed(current_tables, "SystemResults", 20, "NSYRP", expected_system(current)[20]["NSYRP"] + 0.0002)),
        ("elapsed downtime beyond bound", current, None, current["directory"] / "report-raw.json",
         changed(current_tables, "SystemResults", 20, "SYDT", expected_system(current)[20]["SYDT"] + 0.0006)),
    ]
    for label, arm, station, path, tables in cases:
        reject(label, lambda a=arm, s=station, p=path, t=tables: compare_report(a, s, p, contract, supplied_tables=t))
        probes += 1

    altered = copy.deepcopy(current_tables)
    altered[2]["instances"][0]["instance_name"] = "incorrect aggregate"
    reject("instance identity", lambda: compare_report(current, None, current["directory"] / "report-raw.json", contract, supplied_tables=altered))
    probes += 1
    altered_arm = copy.deepcopy(current)
    altered_arm["lines"] = [line.replace("Take replacement item <TEACH-LRU-01,0,1> from stock",
                                         "Take replacement item <TEACH-LRU-01,0,9> from stock") for line in current["lines"]]
    reject("wrong physical stock ID", lambda: station_ledger(altered_arm))
    probes += 1
    altered_arm = copy.deepcopy(future)
    altered_arm["lines"] = [line for line in future["lines"] if "Stock at: <TEACH-LRU-01,0,DEPOT-01,0>" not in line]
    reject("missing physical opening", lambda: station_ledger(altered_arm))
    probes += 1
    altered_arm = copy.deepcopy(current)
    altered_arm["lines"] = [line.replace("<TEACH-LRU-01,0,BASE-02,0> Put back replacement item <TEACH-LRU-01,0,0>",
                                         "<TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,0>") for line in current["lines"]]
    reject("wrong physical return station", lambda: station_ledger(altered_arm))
    probes += 1
    return probes


def verify_provenance(contract):
    """Rehash accepted local/Git identities and sealed historical run artifacts."""
    base = contract["base_commit"]
    counts = {"local_pins": 0, "git_pins": 0, "run_files": 0,
              "closures": 0, "invocations": 0, "roundtrip_tables": 0}
    installed = {
        "simlox_exe_sha256": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual_pdf_sha256": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "dictionary_sha256": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    }
    for label, path in installed.items():
        insist(sha(path.read_bytes()) == contract["installed"][label], f"installed {label}")

    def walk(value):
        if isinstance(value, dict):
            if "path" in value and "local_disk" in value:
                relative = value["path"]
                pin(ROOT / relative, value["local_disk"])
                counts["local_pins"] += 1
                published = value.get("published_git_at_base")
                if published is not None:
                    git_data = subprocess.check_output(["git", "show", f"{base}:{relative}"], cwd=ROOT)
                    insist(len(git_data) == published["bytes"] and sha(git_data) == published["sha256"], f"published {relative}")
                    counts["git_pins"] += 1
            elif "path" in value and "bytes" in value and "sha256" in value:
                pin(ROOT / value["path"], value)
                counts["local_pins"] += 1
            elif "path" in value and "sha256" in value and len(value) == 2:
                insist(sha((ROOT / value["path"]).read_bytes()) == value["sha256"], f"hash-only {value['path']}")
                counts["local_pins"] += 1
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(contract)
    for parent in contract["accepted_parents"]:
        native = next(run for run in parent["runs"] if run["role"] == "native" and run["contrast"] == parent["direct_contrast"])
        native_directory = ROOT / native["local_run_directory"]
        model = tolerant_json_bytes((native_directory / "input.json").read_bytes())["model"]
        roundtrip = tolerant_json_bytes((native_directory / "roundtrip-raw.json").read_bytes())["model"]
        original_tables = {entry["name"]: entry for entry in model["tables"]}
        exported_tables = {entry["name"]: entry for entry in roundtrip["tables"]}
        insist(set(original_tables) == set(exported_tables), "roundtrip table names")
        for name, original in original_tables.items():
            if rows(original):
                insist(original == exported_tables[name], f"roundtrip row-containing {name}")
                counts["roundtrip_tables"] += 1
        for run in parent["runs"]:
            directory = ROOT / run["local_run_directory"]
            for filename, expected in run["files"].items():
                pin(directory / filename, expected)
                counts["run_files"] += 1
            invocation = json.loads((directory / "invocation.json").read_text(encoding="utf-8-sig"))
            closure = json.loads((directory / "closure.json").read_text(encoding="utf-8-sig"))
            insist(invocation["run_id"] == closure["run_id"] == run["run_id"], "historical run identity")
            insist(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "historical SSH0 lineage")
            insist(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "historical queue mutex")
            insist(invocation["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"}, "historical GUI identity")
            insist(closure["invocation_sha256"] == sha((directory / "invocation.json").read_bytes()), "closure invocation seal")
            insist(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "historical source stability")
            insist(closure["error"] is None, "historical closure error")
            for filename, expected in closure["raw"].items():
                pin(directory / filename, expected)
            if run["role"] == "native":
                steps = json.loads((directory / "steps.json").read_text(encoding="utf-8-sig"))
                insist([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "historical native steps")
                insist(all(type(step["exit_code"]) is int and step["exit_code"] == 0 and step["gui_preserved"] is True and step["error"] is None for step in steps), "historical recorded step outcomes")
                check = json.loads((directory / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
                insist(check["passed"] is True and check["differences"] == [], "historical roundtrip status")
            else:
                insist(type(closure["exit_code"]) is int and closure["exit_code"] == 0, "historical selected-report exit")
                selected_source = next(candidate for candidate in parent["runs"] if candidate["role"] == "native" and candidate["contrast"] == run["contrast"])
                selected_source_dir = ROOT / selected_source["local_run_directory"]
                insist(invocation["source_run_id"] == selected_source["run_id"], "selected report source run")
                insist(invocation["source_closure_sha256"] == sha((selected_source_dir / "closure.json").read_bytes()), "selected report closure link")
            counts["closures"] += 1
            counts["invocations"] += 1
    insist(counts["run_files"] == 104 and counts["git_pins"] == 49 and counts["closures"] == 16 and counts["invocations"] == 16, f"provenance totals {counts}")
    return counts


def compare_source_and_context(contract):
    current_path = ROOT / contract["source_comparison"]["current_input"]["path"]
    future_path = ROOT / contract["source_comparison"]["future_input"]["path"]
    current = tolerant_json_bytes(current_path.read_bytes())["model"]
    future = tolerant_json_bytes(future_path.read_bytes())["model"]
    left = {table["name"]: table for table in current["tables"]}
    right = {table["name"]: table for table in future["tables"]}
    insist(len(left) == 34 and len(right) == 35 and set(right) - set(left) == {"ItemTransfer"}, "authored source topology")
    delta = []
    for name, old in left.items():
        new = right[name]
        insist(old["columns"] == new["columns"], f"authored column stability {name}")
        insist(len(old["instances"]) == len(new["instances"]), f"authored instance stability {name}")
        for old_instance, new_instance in zip(old["instances"], new["instances"]):
            insist(old_instance["instance_name"] == new_instance["instance_name"], f"authored instance name {name}")
            insist(len(old_instance["rows"]) == len(new_instance["rows"]), f"authored row stability {name}")
            for row_number, (old_row, new_row) in enumerate(zip(old_instance["rows"], new_instance["rows"])):
                for column, (old_value, new_value) in zip(old["columns"], zip(old_row, new_row)):
                    if old_value != new_value:
                        delta.append((name, row_number, column["name"], old_value, new_value))
    insist(delta == [
        ("ProblemDescription", 0, "PDESC", contract["source_comparison"]["complete_authored_model_delta"][0]["from"], contract["source_comparison"]["complete_authored_model_delta"][0]["to"]),
        ("StockAllocation", 2, "STSIZ", 1, 0),
    ], f"authored source delta {delta}")
    insist(rows(right["ItemTransfer"]) == [contract["source_comparison"]["complete_authored_model_delta"][2]["row"]], "scheduled transfer sole row")

    # DLAYL context is a separate accepted comparison; it does not establish
    # a positive timing effect for the two direct arms.
    future_parent = next(parent for parent in contract["accepted_parents"] if parent["role"] == "scheduled_future_stock")
    off = next(run for run in future_parent["runs"] if run["role"] == "native" and run["contrast"] == "off")
    on = next(run for run in future_parent["runs"] if run["role"] == "native" and run["contrast"] == "on")
    off_dir, on_dir = ROOT / off["local_run_directory"], ROOT / on["local_run_directory"]
    insist((off_dir / "model.log").read_bytes() == (on_dir / "model.log").read_bytes(), "DLAYL mate physical log identity")
    off_report = tolerant_json_bytes((off_dir / "report-raw.json").read_bytes())["report"]["tables"]
    on_report = tolerant_json_bytes((on_dir / "report-raw.json").read_bytes())["report"]["tables"]
    insist([table["name"] for table in off_report] == [table["name"] for table in on_report], "DLAYL mate report tables")
    differences = []
    for off_table, on_table in zip(off_report, on_report):
        insist(off_table["columns"] == on_table["columns"], "DLAYL mate report metadata")
        for row_number, (old_row, new_row) in enumerate(zip(rows(off_table), rows(on_table))):
            for name, old_value, new_value in zip([column["name"] for column in off_table["columns"]], old_row, new_row):
                if old_value != new_value:
                    differences.append((off_table["name"], row_number, name))
    insist(differences == [("ProblemDescription", 0, "PDESC")], f"DLAYL mate report differences {differences}")
    return {"authored_cell_deltas": len(delta), "added_tables": 1, "DLAYL_mate_non_description_differences": 0}


def waiting_hours(backorder_windows):
    return sum((right - left) * value for left, right, value in backorder_windows)


def expected_item(arm, station):
    ledger = arm["station_ledger"][station]
    wait = waiting_hours(ledger["backorders"])
    result = []
    for index in range(72):
        left, right = index / 2, (index + 1) / 2
        requested = event_count(ledger["demand"], left, right)
        wait_report = wait if requested else None
        row = {name: 0 for name in ITEM_COLUMNS if name not in ("IID", "STID", "STINT", "ETINT", "ROS", "ROST", "WT", "WTT", "WTS")}
        row.update({"IID": "TEACH-LRU-01", "STID": station, "STINT": left, "ETINT": right,
                    "ROS": int(wait > 0) if requested else None,
                    "ROST": int(wait > 0) if requested else None,
                    "WT": wait_report, "WTT": wait_report,
                    "WTS": wait_report if wait_report else None})
        row["STSZ"] = weighted(ledger["nominal"], left, right)
        row["STOHA"] = weighted(ledger["physical"], left, right)
        row["NBO"] = weighted(ledger["backorders"], left, right)
        row["PNB"] = 1 - row["NBO"]
        row["NDF"] = requested
        row["NWT"] = requested
        row["NLD"] = requested if arm["current"] and station == "BASE-02" else 0
        row["NRP"] = event_count(ledger["repair"], left, right)
        result.append(row)
    return result


def expected_item_total(arm, station):
    ledger = arm["station_ledger"][station]
    wait = waiting_hours(ledger["backorders"])
    demand_count = len(ledger["demand"])
    row = {name: 0 for name in ITEM_TOTAL_COLUMNS if name not in ("IID", "STID", "ROS", "ROST", "WT", "WTT", "WTS")}
    row.update({"IID": "TEACH-LRU-01", "STID": station})
    row["STSZ"] = weighted(ledger["nominal"], 0, 36)
    row["STOHA"] = weighted(ledger["physical"], 0, 36)
    row["NBO"] = weighted(ledger["backorders"], 0, 36)
    row["PNB"] = 1 - row["NBO"]
    row["NDF"] = demand_count
    row["NWT"] = demand_count
    row["NLD"] = demand_count if arm["current"] and station == "BASE-02" else 0
    row["NRP"] = len(ledger["repair"])
    if demand_count:
        row.update({"ROS": int(wait > 0), "ROST": int(wait > 0), "WT": wait, "WTT": wait,
                    "WTS": wait if wait else None})
    else:
        row.update({"ROS": None, "ROST": None, "WT": None, "WTT": None, "WTS": None})
    return [row]


def expected_stock_total(arm):
    """StockTotal counts direct system demand; propagated station demand stays in ItemResults."""
    ledger = arm["station_ledger"]["BASE-01"]
    wait = waiting_hours(ledger["backorders"])
    result = []
    for index in range(72):
        left, right = index / 2, (index + 1) / 2
        requested = event_count(ledger["demand"], left, right)
        wait_report = wait if requested and wait > 0 else None
        row = {name: 0 for name in STOCK_COLUMNS if name not in ("STINT", "ETINT", "NBOU", "ROS", "ROST", "WT", "WTT", "WTS")}
        row.update({"STINT": left, "ETINT": right, "NBOU": None,
                    "ROS": 1 if wait_report is not None else None,
                    "ROST": 1 if wait_report is not None else None,
                    "WT": wait_report, "WTT": wait_report, "WTS": wait_report})
        row["NBO"] = weighted(ledger["backorders"], left, right)
        row["PNB"] = 1 - row["NBO"]
        row["NDF"] = requested
        row["NWT"] = requested
        row["NLD"] = requested if arm["current"] else 0
        result.append(row)
    return result


if __name__ == "__main__":
    try:
        insist(len(sys.argv) in (1, 2) and (len(sys.argv) == 1 or sys.argv[1] == "--write-verdict"), "usage: independent_replay.py [--write-verdict]")
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8-sig"))
        insist(sha(CONTRACT_PATH.read_bytes()) == CONTRACT_SHA, "contract hash")
        provenance = verify_provenance(contract)
        comparison = compare_source_and_context(contract)
        total = 0
        arms = []
        for parent in contract["accepted_parents"]:
            arm = parsed_arm(parent, contract)
            arms.append(arm)
            total += compare_report(arm, None, arm["directory"] / "report-raw.json", contract)
            for selected in (run for run in parent["runs"] if run["role"] == "station_report" and run["contrast"] == parent["direct_contrast"]):
                selected_dir = ROOT / selected["local_run_directory"]
                for filename, expected in selected["files"].items():
                    pin(selected_dir / filename, expected)
                station = {"base01": "BASE-01", "base02": "BASE-02", "base-01": "BASE-01", "base-02": "BASE-02", "depot": "DEPOT-01"}[selected["station"]]
                total += compare_report(arm, station, selected_dir / "item-report-raw.json", contract)
        insist(total == 48684, "full report cell count")
        probes = mutation_probes(contract, arms)
        verdict = {
            "schema": "e08-var04-independent-readonly-replay/v1",
            "decision": "GO_BOUNDED",
            "contract_sha256": CONTRACT_SHA,
            "script_sha256": sha(pathlib.Path(__file__).read_bytes()),
            "full_expected_report_cells": total,
            "direct_arms": 2,
            "selected_station_reports": 6,
            "provenance": provenance,
            "source_and_context": comparison,
            "semantic_mutation_rejections": probes,
            "current_repair_done_h": arms[0]["repair_done"],
            "future_repair_done_h": arms[1]["repair_done"],
            "limitations": [
                "Retrospective comparison of two accepted runs with co-varying stock and scheduled transfer inputs.",
                "Historical invocation records SSH session zero and integer step exits; they do not record each child PID/session.",
                "DLAYL context mate has identical physical log and non-description report cells, so no positive DLAYL timing effect is inferred.",
            ],
        }
        encoded = (json.dumps(verdict, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
        if len(sys.argv) == 2:
            (PACKAGE / "review" / "independent-verdict.json").write_bytes(encoded)
        else:
            sys.stdout.buffer.write(encoded)
    except Exception as exc:
        print(f"NO_GO: {exc!r}", file=sys.stderr)
        raise

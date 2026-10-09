#!/usr/bin/env python3
"""Replay I05.var05 physical events against every half-hour report ledger."""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
INPUT = PACKAGE / "native-input.json"
INPUT_SHA = "c30b0849ad46a6351e4c94a2964f0f6f16274b6b926508b8fe47ecd9a5323480"
EPS = 0.00011
PARENT_OPENING_SPARE = "0"  # accepted H02.var04 fallback log: first physical stock issue
EXPECTED_REPORT_COLUMNS = {
    "ProblemDescription": ["PDESC"],
    "ResultSummary": ["NREP", "RTILW", "RTIUP", "MTMF", "RSMTMF", "MSTF", "RSMSTF", "MSUF", "RSMSUF", "STMF", "RSSTMF"],
    "SystemResults": ["UNID", "SID", "STINT", "ETINT", "NSYRY", "NSYMA", "NSYMO", "NSYMC", "NSYMP", "NSYMT", "NSYMS", "NSYMR", "NSYUA", "NSYA", "NSYAL", "FTMO", "NSYRP", "NSYPM", "NSYTP", "NSYWR", "NSYWI", "NSYLA", "NSYUH", "NREPT", "NPMT", "NFAIL", "NDAM", "NPMS", "NROBT", "NRCFG", "STREQ", "STACC", "STF", "STLOW", "SYDT", "SYDTU", "NSYDT", "NSYSW", "NPSTA", "NPSUC"],
    "StockTotalResults": ["STINT", "ETINT", "NBO", "NBOU", "ROS", "ROST", "WT", "WTT", "WTS", "PNB", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT"],
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_native(path: Path) -> dict:
    text = path.read_bytes().decode("utf-8-sig", errors="strict")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # SIMLOX's known trailing-comma writer form is normalized in memory only.
        out: list[str] = []
        quoted = escaped = False
        for i, char in enumerate(text):
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
            elif char == "," and text[i + 1 :].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def near(a: object, b: float, tolerance: float = EPS) -> bool:
    return not isinstance(a, bool) and isinstance(a, (int, float)) and math.isfinite(float(a)) and abs(float(a) - b) <= tolerance


def exact_count(value: object, field: str, row_index: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{field} is not a finite numeric count at report row {row_index}")
    number = float(value)
    if number < 0 or not number.is_integer():
        raise ValueError(f"{field} is not a nonnegative integer count at report row {row_index}: {value!r}")
    return int(number)


def table_rows(doc: dict, name: str) -> tuple[list[str], list[list[object]]]:
    matches = [table for table in doc["report"]["tables"] if table["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"report table cardinality differs: {name}")
    table = matches[0]
    columns = [column["name"] for column in table["columns"]]
    if len(columns) != len(set(columns)):
        raise ValueError(f"duplicate report column names: {name}")
    rows = [row for instance in table["instances"] for row in instance["rows"]]
    if any(len(row) != len(columns) for row in rows):
        raise ValueError(f"nonrectangular report table: {name}")
    return columns, rows


def to_records(columns: list[str], rows: list[list[object]]) -> list[dict[str, object]]:
    return [dict(zip(columns, row, strict=True)) for row in rows]


def timed_events(lines: list[str], pattern: str) -> list[tuple[float, str, int]]:
    found = []
    for index, line in enumerate(lines):
        time = re.match(r"^Time: ([0-9]+(?:\.[0-9]+)?)\s+", line)
        match = re.search(pattern, line)
        if time and match:
            found.append((float(time.group(1)), match.group(1), index))
    return found


def bin_counts(events: list[tuple[float, str, int]]) -> list[int]:
    counts = [0] * 72
    for time, _, _ in events:
        index = min(int(math.floor((time + 1e-9) / 0.5)), 71)
        if time < 0 or time >= 36:
            raise ValueError(f"event lies outside the 36-hour report horizon: {time}")
        counts[index] += 1
    return counts


def main() -> None:
    run = Path(sys.argv[1]).resolve()
    if sha(INPUT) != INPUT_SHA:
        raise SystemExit("frozen native input hash changed")
    log_path, report_path = run / "model.log", run / "report-raw.json"
    lines = log_path.read_text(encoding="utf-8", errors="strict").splitlines()
    if not lines or lines[0].startswith("\ufeff"):
        raise SystemExit("model.log empty or UTF-8 BOM present")
    timed = [(float(m.group(1)), line) for line in lines if (m := re.match(r"^Time: ([0-9]+(?:\.[0-9]+)?)\s+", line))]
    if not timed:
        raise SystemExit("no timed physical event lines")

    damage = timed_events(lines, r"Damage BATTLE-HIT occured\. Damaged items: <TEACH-LRU-01,0,(\d+)>")
    demand = timed_events(lines, r"Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,(\d+)>$")
    issued = timed_events(lines, r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock\s*$")
    removed = timed_events(lines, r"Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)> from position <TEACH-AIR-01,BASE-01,0> damaged\s+")
    repair_start = timed_events(lines, r"Start repair of item <TEACH-LRU-01,0,(\d+)>$")
    repair_subtask = timed_events(lines, r"direct repair subtask \d+ seqno 0 within item DIRP task \d+ on <TEACH-LRU-01,0,(\d+)> starts performing, planned to last for 1 hours$")
    repair_done = timed_events(lines, r"Finished repair of item <TEACH-LRU-01,0,(\d+)>$")
    arrived = timed_events(lines, r"Replacement item arrives <TEACH-LRU-01,0,(\d+)>$")
    returned = timed_events(lines, r"Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock\s*$")

    tasks: dict[str, dict[str, float]] = {}
    for time, line in timed:
        match = re.search(r"system SURP task (\d+) on <TEACH-AIR-01,0> (started|completed)", line)
        if match:
            slot = tasks.setdefault(match.group(1), {})
            key = match.group(2)
            if key in slot:
                raise SystemExit(f"duplicate system SURP task {key}: {match.group(1)}")
            slot[key] = time
    if len(damage) != 3 or not (len(damage) == len(demand) == len(issued) == len(removed) == len(repair_start) == len(repair_subtask) == len(repair_done) == len(arrived) == len(returned) == len(tasks) == 3):
        raise SystemExit("expected three closed damage, replacement, repair, and stock cycles")
    if any(set(value) != {"started", "completed"} for value in tasks.values()):
        raise SystemExit("system SURP task starts/completions are incomplete")
    task_pairs = sorted(((v["started"], v["completed"], key) for key, v in tasks.items()))
    if any(start <= 5.0 or near(start, 5.0) for start, _, _ in task_pairs):
        raise SystemExit("hour-5 data change incorrectly triggered an immediate replacement task")
    if any(not near(end - start, 1.5) for start, end, _ in task_pairs):
        raise SystemExit("a post-change System SURP task did not last 1.5 hours")

    identity_series = (damage, demand, removed, repair_start, repair_subtask, repair_done, arrived, returned)
    expected_damaged = [identity for _, identity, _ in damage]
    if any([identity for _, identity, _ in series] != expected_damaged for series in identity_series[1:]):
        raise SystemExit("damaged item identity does not reconcile through demand, repair, arrival, and return")
    draw_ids = [identity for _, identity, _ in issued]
    return_ids = [identity for _, identity, _ in returned]
    if draw_ids[0] != PARENT_OPENING_SPARE or draw_ids[1:] != return_ids[:-1]:
        raise SystemExit("physical opening-spare draw and subsequent repaired-item stock flow differ")

    stock_snapshots = []
    for time, identity, line_index in issued:
        if line_index + 1 >= len(lines) or not re.fullmatch(r"\s+Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:\s*", lines[line_index + 1]):
            raise SystemExit("stock level-zero snapshot does not immediately follow spare issue")
        stock_snapshots.append({"event":"issue","time_hours":time,"physical_item_id":identity,"snapshot":lines[line_index + 1].strip()})
    for time, identity, line_index in returned:
        expected = rf"\s+Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,{re.escape(identity)}>,\s*"
        if line_index + 1 >= len(lines) or not re.fullmatch(expected, lines[line_index + 1]):
            raise SystemExit("returned physical item does not immediately appear in the stock level-one snapshot")
        stock_snapshots.append({"event":"return","time_hours":time,"physical_item_id":identity,"snapshot":lines[line_index + 1].strip()})
    cycles = []
    for index in range(3):
        d_time, damaged, _ = damage[index]
        q_time, demanded, _ = demand[index]
        i_time, spare, _ = issued[index]
        x_time, removed_id, _ = removed[index]
        r_time, repair_id, _ = repair_start[index]
        s_time, repair_subtask_id, _ = repair_subtask[index]
        c_time, repaired, _ = repair_done[index]
        a_time, arrived_id, _ = arrived[index]
        p_time, returned_id, _ = returned[index]
        task_start, task_end, task_id = task_pairs[index]
        if not (d_time < q_time and near(q_time, i_time) and i_time <= x_time <= r_time <= s_time < c_time):
            raise SystemExit(f"physical item and spare event chronology differs for cycle {index + 1}")
        if not (near(c_time - s_time, 1.0) and near(c_time, a_time) and near(c_time, p_time) and near(task_start, i_time) and near(task_end, c_time)):
            raise SystemExit(f"repair duration, task completion, arrival, or stock return differs for cycle {index + 1}")
        if not (damaged == demanded == removed_id == repair_id == repair_subtask_id == repaired == arrived_id == returned_id):
            raise SystemExit(f"physical item serial differs inside cycle {index + 1}")
        if index and (spare != return_ids[index - 1] or i_time < returned[index - 1][0]):
            raise SystemExit("next cycle draws the opening spare before the prior repair returned")
        cycles.append({"cycle":index+1,"damage_time_hours":d_time,"demand_time_hours":q_time,
                       "spare_issue_time_hours":i_time,"spare_id":spare,"damaged_item_id":damaged,
                       "direct_repair_start_hours":s_time,"direct_repair_end_hours":c_time,
                       "system_surp_start_hours":task_start,"system_surp_end_hours":task_end,
                       "system_surp_task_id":task_id,"stock_return_time_hours":p_time})

    report = parse_native(report_path)
    table_names = [table["name"] for table in report["report"]["tables"]]
    if len(table_names) != len(set(table_names)) or set(table_names) != set(EXPECTED_REPORT_COLUMNS):
        raise SystemExit("raw report table roster differs from accepted parent")
    for table_name, expected_columns in EXPECTED_REPORT_COLUMNS.items():
        columns, _ = table_rows(report, table_name)
        if columns != expected_columns:
            raise SystemExit(f"raw report column names/order differ from accepted parent: {table_name}")
    summary_columns, summary_rows = table_rows(report, "ResultSummary")
    system_columns, system_rows = table_rows(report, "SystemResults")
    stock_columns, stock_rows = table_rows(report, "StockTotalResults")
    summary, system, stock = to_records(summary_columns, summary_rows), to_records(system_columns, system_rows), to_records(stock_columns, stock_rows)
    if len(summary) != 1 or len(system) != 72 or len(stock) != 72:
        raise SystemExit("ResultSummary/System/Stock report row count differs")
    if len(system) != 72 or len(stock) != 72 or len(system_columns) != 40 or len(stock_columns) != 16:
        raise SystemExit("System and Stock report must preserve 72 bins and accepted columns")
    for index in range(72):
        if system[index]["UNID"] != "Total over all Units" or system[index]["SID"] != "Total over all Systems":
            raise SystemExit(f"SystemResults total-row identity differs at row {index}")
        if not (near(system[index]["STINT"], index * 0.5) and near(system[index]["ETINT"], (index + 1) * 0.5)
                and near(stock[index]["STINT"], index * 0.5) and near(stock[index]["ETINT"], (index + 1) * 0.5)):
            raise SystemExit(f"System/Stock report half-hour boundary differs at row {index}")
    if any(isinstance(value, float) and not math.isfinite(value) for table in report["report"]["tables"] for instance in table["instances"] for row in instance["rows"] for value in row):
        raise SystemExit("raw report contains non-finite numeric cells")

    damage_bins = bin_counts(damage)
    task_completion_events = [(end, key, -1) for start, end, key in task_pairs]
    completion_bins = bin_counts(task_completion_events)
    demand_bins = bin_counts(demand)
    ndam_bins = [exact_count(row["NDAM"], "NDAM", index) for index, row in enumerate(system)]
    nrept_bins = [exact_count(row["NREPT"], "NREPT", index) for index, row in enumerate(system)]
    ndd_bins = [exact_count(row["NDD"], "NDD", index) for index, row in enumerate(stock)]
    nwt_bins = [exact_count(row["NWT"], "NWT", index) for index, row in enumerate(stock)]
    nbo_bins = [exact_count(row["NBO"], "NBO", index) for index, row in enumerate(stock)]
    if ndam_bins != damage_bins:
        raise SystemExit("SystemResults NDAM bins do not match timed physical damage events")
    if nrept_bins != completion_bins:
        raise SystemExit("SystemResults NREPT bins do not match timed replacement-task completions")
    if ndd_bins != demand_bins or nwt_bins != demand_bins:
        raise SystemExit("StockTotalResults demand/wait bins do not match physical spare-demand events")
    if sum(ndam_bins) != 3 or sum(nrept_bins) != 3:
        raise SystemExit("System report damage/replacement totals differ from three physical cycles")
    if sum(ndd_bins) != 3 or sum(nwt_bins) != 3 or any(nbo_bins):
        raise SystemExit("Stock report demand/wait totals differ from three physical cycles")
    if any(not near(row["PNB"], 1) for row in stock):
        raise SystemExit("stock report has a backorder or nominal-stock discrepancy")
    if any(not near(sum(float(row[key] or 0) for key in ("NSYA", "NSYUA", "NSYLA")), 1) or
           not near(sum(float(row[key] or 0) for key in ("NSYRY", "NSYMA", "NSYUA", "NSYLA")), 1) for row in system):
        raise SystemExit("system state partition does not reconcile in every report bin")
    system_repair_hours = 0.5 * sum(float(row["NSYRP"] or 0) for row in system)
    task_hours = sum(end - start for start, end, _ in task_pairs)
    if not near(system_repair_hours, task_hours, 0.0002) or not near(system_repair_hours, 4.5, 0.0002):
        raise SystemExit("integrated SystemResults repair exposure does not equal the raw task-duration ledger")
    if any(not near(row["NFAIL"] or 0, 0) or not near(row["NSYLA"] or 0, 0) for row in system):
        raise SystemExit("system report contains a failure or lost-aircraft state outside the contract")
    if not near(system[-1]["NSYRY"], 1) or not near(summary[0]["MSTF"], 1) or not near(summary[0]["MSUF"], 0):
        raise SystemExit("terminal readiness or result summary differs")
    typed_cells = sum(len(table["columns"]) * sum(len(instance["rows"]) for instance in table["instances"]) for table in report["report"]["tables"])
    if typed_cells != 4044:
        raise SystemExit(f"full raw report typed cell count differs: {typed_cells}")

    ledger = {"schema":"i05-var05-physical-stock-ledger/v3","input_sha256":INPUT_SHA,
        "event_log_sha256":sha(log_path),"report_sha256":sha(report_path),"cycles":cycles,
        "stock_snapshots":stock_snapshots,"system_surp_tasks":task_pairs,
        "report_system_columns":system_columns,"report_system_rows":system_rows,
        "report_stock_columns":stock_columns,"report_stock_rows":stock_rows,
        "report_event_reconciliation":{"NDAM_bins":damage_bins,"NREPT_bins":completion_bins,
           "NDD_bins":demand_bins,"NWT_bins":demand_bins,"NBO_bins":nbo_bins,"system_repair_hours":system_repair_hours,
           "raw_task_hours":task_hours,"all_72_state_partitions_pass":True,"all_stock_PNB_one_no_backorders":True},
        "report_typed_cells":typed_cells,"publication_state":"not_published"}
    ledger_path = run / "physical-stock-ledger.json"
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"schema":"i05-var05-native-cli-check/v3","status":"PASS_BOUNDED_EVENT_AND_SELECTED_REPORT_FIELDS",
        "input_sha256":INPUT_SHA,"model_log_sha256":sha(log_path),"report_sha256":sha(report_path),
        "physical_log_lines":len(lines),"timed_lines":len(timed),"replacement_tasks":len(task_pairs),
        "task_durations_hours":[round(end-start,6) for start,end,_ in task_pairs],"damage_cycles":len(damage),
        "stock_report_bins":len(stock),"system_report_bins":len(system),"report_typed_cell_count":typed_cells,
        "report_column_schema_matches_accepted_parent":True,
        "report_value_scope":["STINT","ETINT","UNID","SID","NDAM","NREPT","NDD","NWT","NBO","PNB","NSYRY","NSYMA","NSYUA","NSYA","NSYRP","NFAIL","NSYLA","ResultSummary.MSTF","ResultSummary.MSUF"],
        "system_repair_exposure_hours":system_repair_hours,"physical_stock_ledger_sha256":sha(ledger_path),
        "native_actions":0,"issues":[]},sort_keys=True))


if __name__ == "__main__":
    main()

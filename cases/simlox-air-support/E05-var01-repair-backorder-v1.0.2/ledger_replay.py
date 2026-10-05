"""Task-linked physical and interval ledger checks for one E05.var01 run.

This parser uses printed event times only. Native logs round them, so identity and
ordering are exact while duration/interval comparisons allow 0.001 hour for the
printed timestamps and 0.003 for float32 half-hour report fractions.
"""

from __future__ import annotations

from collections import Counter
import re


STOCK = "<TEACH-LRU-01,0,BASE-01,0>"
AIR = "<TEACH-AIR-01,0>"
POSITION = "<TEACH-AIR-01,BASE-01,0>"
ITEM = r"<TEACH-LRU-01,0,(?P<item>\d+)>"
HORIZON = 36.0
TIME_TOL = 0.001
BIN_TOL = 0.003


def overlap(a: float, b: float, lo: float, hi: float) -> float:
    return max(0.0, min(b, hi) - max(a, lo))


def approx(a: float, b: float, tol: float = TIME_TOL) -> bool:
    return abs(a - b) <= tol


def audit(log: str, system_rows: list[dict], stock_rows: list[dict]) -> dict:
    lines = log.splitlines()
    failures: list[str] = []
    checks = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(label)

    def scan(body: str) -> list[dict]:
        expression = re.compile(r"^Time: (?P<time>[0-9.]+) " + body + r"\s*$")
        found = []
        for line_no, line in enumerate(lines):
            match = expression.fullmatch(line)
            if match:
                found.append({"time": float(match["time"]), "line": line_no,
                              **{key: value for key, value in match.groupdict().items() if key != "time"}})
        return found

    def single(label: str, found: list[dict]) -> dict | None:
        ck(label, len(found) == 1)
        return found[0] if len(found) == 1 else None

    demands = scan(re.escape(STOCK) + r" Item demand arrives from pos " + re.escape(POSITION)
                   + r" item requiring maintenance is <TEACH-LRU-01,0,(?P<failed>\d+)>")
    task_starts = scan(r" system SURP task (?P<task>\d+) on " + re.escape(AIR) + r" started")
    issues = scan(re.escape(STOCK) + r" Take replacement item " + ITEM + r" from stock")
    puts = scan(re.escape(STOCK) + r" Put back replacement item " + ITEM + r" to stock")
    bo_adds = scan(re.escape(STOCK) + r" Backorder added")
    bo_removes = scan(re.escape(STOCK) + r" Backorder removed, waiting time was (?P<wait>[0-9.]+)")
    receives = scan(r" system SURP task (?P<task>\d+) on " + re.escape(AIR)
                    + r" subitem received " + ITEM)
    removed_items = scan(re.escape(STOCK) + r" Item requiring maintenance arrives " + ITEM
                         + r" from position " + re.escape(POSITION) + r" direct repair failure .*no PMTasks")
    repair_starts = scan(re.escape(STOCK) + r" Start repair of item " + ITEM)
    repair_finishes = scan(re.escape(STOCK) + r" Finished repair of item " + ITEM)
    arrivals = scan(re.escape(STOCK) + r" Replacement item arrives " + ITEM)
    repair_work = scan(r" direct repair subtask (?P<sub>\d+) seqno 0 within item DIRP task "
                       + r"(?P<task>\d+) on " + ITEM
                       + r" starts performing, planned to last for (?P<hours>[0-9.]+) hours")
    item_task_starts = scan(r" item DIRP task (?P<task>\d+) on " + ITEM + r" started")
    item_task_completes = scan(r" item DIRP task (?P<task>\d+) on " + ITEM + r" completed")
    repair_sub_starts = scan(r" direct repair subtask (?P<sub>\d+) seqno 0 within item DIRP task "
                             + r"(?P<task>\d+) on " + ITEM + r" started")
    repair_sub_done = scan(r" direct repair subtask (?P<sub>\d+) seqno 0 within item DIRP task "
                           + r"(?P<task>\d+) on " + ITEM + r" completed")
    remove_work = scan(r" remove subitem subtask (?P<sub>\d+) seqno 1 within system SURP task "
                       + r"(?P<task>\d+) on " + re.escape(AIR)
                       + r" starts performing, planned to last for (?P<hours>[0-9.]+) hours")
    remove_done = scan(r" remove subitem subtask (?P<sub>\d+) seqno 1 within system SURP task "
                       + r"(?P<task>\d+) on " + re.escape(AIR) + r" completed")
    fit_started = scan(r" fit subitem subtask (?P<sub>\d+) seqno 2 within system SURP task "
                       + r"(?P<task>\d+) on " + re.escape(AIR) + r" started")
    fit_wait = scan(r" fit subitem subtask (?P<sub>\d+) seqno 2 within system SURP task "
                    + r"(?P<task>\d+) on " + re.escape(AIR) + r" wait for subitem")
    fit_work = scan(r" fit subitem subtask (?P<sub>\d+) seqno 2 within system SURP task "
                    + r"(?P<task>\d+) on " + re.escape(AIR)
                    + r" starts performing, planned to last for (?P<hours>[0-9.]+) hours")
    fit_done = scan(r" fit subitem subtask (?P<sub>\d+) seqno 2 within system SURP task "
                    + r"(?P<task>\d+) on " + re.escape(AIR) + r" completed")
    system_task_done = scan(r" system SURP task (?P<task>\d+) on " + re.escape(AIR) + r" completed")
    repair_enter = scan(re.escape(POSITION) + r" System to repair " + re.escape(AIR))
    all_system_ready = scan(re.escape(POSITION) + r" System ready " + re.escape(AIR))
    repair_exit = [x for x in all_system_ready
                   if any(approx(x["time"], done["time"]) for done in system_task_done)]
    ready_in = scan(re.escape(AIR) + r" nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>")
    ready_out = scan(re.escape(AIR) + r" nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>")
    critical = scan(re.escape(AIR) + r" critical random failure added, now.*")
    system_arrivals = scan(re.escape(POSITION) + r" System arrives " + re.escape(AIR) + r",.*")
    failure_arrivals = [x for x in system_arrivals
                        if any("subitem failed:" in line for line in lines[x["line"]+1:x["line"]+4])]

    def adjacent_failed_id(label: str, header: dict) -> str | None:
        following = lines[header["line"]+1:header["line"]+4]
        matches = [re.fullmatch(r"  subitem failed: <TEACH-LRU-01,0,(\d+)> connection path: .*", line)
                   for line in following]
        values = [match[1] for match in matches if match]
        ck(label, len(values) == 1)
        return values[0] if len(values) == 1 else None

    ck("at least two demands and one shortage", len(demands) >= 2 and len(bo_adds) >= 1)
    ck("unambiguous demand times", len({x["time"] for x in demands}) == len(demands))
    ck("one SURP start per demand", len(task_starts) == len(demands))
    ck("every demand supplied or backordered", len(demands) == len(issues) + len(bo_adds))
    ck("all removed items enter repair", len(repair_starts) == len(removed_items) == len(demands))
    ck("all repair work declared 13 hours", len(repair_work) == len(repair_starts)
       and all(approx(float(x["hours"]), 13) for x in repair_work))
    ck("all immediate or cleared demands received", len(receives) == len(issues) + len(bo_removes))
    ck("all finish events returned", len(repair_finishes) == len(arrivals) == len(item_task_completes))
    ck("system repair state entries", len(repair_enter) == len(demands))
    ck("system repair state exits", len(repair_exit) == len(system_task_done))
    ck("one critical failure and failed arrival per demand",
       len(critical) == len(failure_arrivals) == len(demands))

    critical_ids = [adjacent_failed_id(f"critical failed item line {x['line']}", x)
                    for x in critical]
    arrival_ids = [adjacent_failed_id(f"arriving failed item line {x['line']}", x)
                   for x in failure_arrivals]
    for i, demand in enumerate(demands):
        if i >= len(critical) or i >= len(failure_arrivals):
            continue
        ck(f"failure/demand/arrival identity {i}", critical_ids[i] is not None
           and critical_ids[i] == arrival_ids[i] == demand["failed"]
           and critical[i]["time"] < demand["time"]
           and approx(failure_arrivals[i]["time"], demand["time"]))
        if i == 0:
            ck("initial installed identity precedes first failure", not fit_done
               or fit_done[0]["time"] > critical[i]["time"])
        else:
            preceding = [x for x in fit_done if x["time"] < critical[i]["time"]]
            previous_task = task_starts[i-1]["task"] if i-1 < len(task_starts) else None
            previous_receipt = [x for x in receives if x["task"] == previous_task]
            ck(f"preceding fit and receipt completed before failure {i}", bool(preceding)
               and preceding[-1]["task"] == previous_task
               and len(previous_receipt) == 1
               and previous_receipt[0]["time"] <= preceding[-1]["time"])

    # One aircraft and stock position: require FIFO matches to be unambiguous.
    pending: list[dict] = []
    pairs: list[tuple[dict, dict]] = []
    for event in sorted([(x["time"], x["line"], 1, x) for x in bo_adds]
                        + [(x["time"], x["line"], -1, x) for x in bo_removes]):
        _, _, direction, row = event
        if direction == 1:
            pending.append(row)
            ck(f"backorder queue unambiguous line {row['line']}", len(pending) == 1)
        else:
            ck(f"backorder removal has prior add line {row['line']}", bool(pending))
            if pending:
                start = pending.pop(0)
                ck(f"printed wait line {row['line']}", approx(float(row["wait"]), row["time"]-start["time"]))
                pairs.append((start, row))
    ck("all backorders clear before horizon", not pending and len(bo_adds) == len(bo_removes))

    task_ids: set[int] = set()
    route_waits: list[tuple[float, float, bool]] = []
    for demand in demands:
        time, failed = demand["time"], demand["failed"]
        task = single(f"SURP at demand {time}", [x for x in task_starts if approx(x["time"], time)])
        if task is None:
            continue
        task_id = task["task"]
        ck(f"distinct SURP task {task_id}", int(task_id) not in task_ids)
        task_ids.add(int(task_id))
        issue = [x for x in issues if approx(x["time"], time)]
        shortage = [x for x in bo_adds if approx(x["time"], time)]
        ck(f"exact demand route {task_id}", len(issue)+len(shortage) == 1)
        receipt = single(f"one receipt {task_id}", [x for x in receives if x["task"] == task_id])
        if len(issue) == 1:
            ck(f"immediate physical receipt {task_id}", receipt is not None
               and issue[0]["item"] == receipt["item"] and approx(receipt["time"], time))
            route_waits.append((time, 0.0, False))
        elif len(shortage) == 1:
            pair = [p for p in pairs if p[0]["line"] == shortage[0]["line"]]
            ck(f"backorder clears {task_id}", len(pair) == 1)
            if pair:
                cleared = pair[0][1]
                ck(f"backorder receipt {task_id}", receipt is not None
                   and approx(receipt["time"], cleared["time"])
                   and len([x for x in arrivals if approx(x["time"], cleared["time"])
                            and receipt is not None and x["item"] == receipt["item"]]) == 1)
                route_waits.append((time, cleared["time"]-time, True))
        rem = single(f"remove work {task_id}", [x for x in remove_work if x["task"] == task_id])
        done = single(f"remove completion {task_id}", [x for x in remove_done if x["task"] == task_id])
        if rem and done:
            ck(f"10 minute removal {task_id}", approx(rem["time"], time)
               and approx(float(rem["hours"]), 1/6) and approx(done["time"]-rem["time"], 1/6)
               and rem["sub"] == done["sub"])
            ck(f"removed failed identity {task_id}", len([x for x in removed_items
               if x["item"] == failed and approx(x["time"], done["time"])]) == 1)
            ck(f"failed item repair starts {task_id}", len([x for x in repair_starts
               if x["item"] == failed and approx(x["time"], done["time"])]) == 1)
            ck(f"DIRP identity/work {task_id}", len([x for x in item_task_starts
               if x["item"] == failed and approx(x["time"], done["time"])]) == 1
               and len([x for x in repair_work if x["item"] == failed
                        and approx(x["time"], done["time"])]) == 1)
        fit_starts = [x for x in fit_started if x["task"] == task_id]
        ck(f"fit task start count {task_id}", len(fit_starts) == (2 if shortage and receipt else 1))
        fit_subs = {x["sub"] for x in fit_starts}
        ck(f"one fit subtask identity {task_id}", len(fit_subs) == 1)
        if fit_starts and done:
            ck(f"fit task follows removal {task_id}", approx(fit_starts[0]["time"], done["time"]))
            if shortage and receipt and len(fit_starts) == 2:
                ck(f"fit restarts after receipt {task_id}", approx(fit_starts[1]["time"], receipt["time"]))
        waits = [x for x in fit_wait if x["task"] == task_id]
        ck(f"fit waits iff shortage {task_id}", len(waits) == (1 if shortage else 0)
           and (not waits or (done is not None and approx(waits[0]["time"], done["time"])
                              and waits[0]["sub"] in fit_subs)))
        work = [x for x in fit_work if x["task"] == task_id]
        finish = [x for x in fit_done if x["task"] == task_id]
        completed = [x for x in system_task_done if x["task"] == task_id]
        if receipt is not None and done is not None:
            ck(f"one physical fit {task_id}", len(work) == len(finish) == len(completed) == 1)
            if len(work) == len(finish) == len(completed) == 1:
                expected_start = max(done["time"], receipt["time"])
                ck(f"20 minute fit and completion {task_id}", approx(work[0]["time"], expected_start)
                   and work[0]["sub"] in fit_subs and finish[0]["sub"] == work[0]["sub"]
                   and approx(float(work[0]["hours"]), 1/3)
                   and approx(finish[0]["time"]-work[0]["time"], 1/3)
                   and approx(completed[0]["time"], finish[0]["time"])
                   and len([x for x in repair_exit if approx(x["time"], finish[0]["time"])]) == 1)
        else:
            ck(f"unfinished task has no fit/completion {task_id}", not work and not finish and not completed)

    # Each direct-repair start either finishes after 13 hours before the horizon,
    # or remains genuinely in progress at hour 36. Match physical IDs exactly.
    pending_repairs = []
    ck("one DIRP start/work per removed item", len(item_task_starts) == len(repair_sub_starts)
       == len(repair_work) == len(repair_starts))
    ck("distinct DIRP task IDs", len({x["task"] for x in item_task_starts}) == len(item_task_starts))
    ck("one DIRP/subtask completion per repaired item", len(item_task_completes)
       == len(repair_sub_done) == len(repair_finishes))
    for start in repair_starts:
        identity = start["item"]
        finish = [x for x in repair_finishes if x["item"] == identity]
        arrivals_for_item = [x for x in arrivals if x["item"] == identity]
        task = single(f"DIRP task start for item {identity}", [x for x in item_task_starts
                     if x["item"] == identity and approx(x["time"], start["time"])])
        work_start = single(f"DIRP subtask start for item {identity}", [x for x in repair_sub_starts
                            if x["item"] == identity and approx(x["time"], start["time"])])
        work = single(f"DIRP work for item {identity}", [x for x in repair_work
                      if x["item"] == identity and approx(x["time"], start["time"])])
        if task and work_start and work:
            ck(f"DIRP task/subtask start lineage {identity}", task["task"] == work_start["task"]
               == work["task"] and work_start["sub"] == work["sub"])
        due = start["time"] + 13
        if due < HORIZON - TIME_TOL:
            ck(f"completed repair {identity}", len(finish) == len(arrivals_for_item) == 1)
            if len(finish) == len(arrivals_for_item) == 1:
                task_done = [x for x in item_task_completes if x["item"] == identity]
                sub_done = [x for x in repair_sub_done if x["item"] == identity]
                ck(f"DIRP task/subtask completion lineage {identity}", task is not None
                   and work_start is not None and len(task_done) == len(sub_done) == 1
                   and task_done[0]["task"] == sub_done[0]["task"] == task["task"]
                   and sub_done[0]["sub"] == work_start["sub"]
                   and approx(task_done[0]["time"], finish[0]["time"])
                   and approx(sub_done[0]["time"], finish[0]["time"]))
                ck(f"repair13/return {identity}", approx(finish[0]["time"], due)
                   and approx(arrivals_for_item[0]["time"], finish[0]["time"]))
                put = [x for x in puts if x["item"] == identity and approx(x["time"], finish[0]["time"])]
                received = [x for x in receives if x["item"] == identity
                            and approx(x["time"], finish[0]["time"])]
                ck(f"repair return route {identity}", len(put)+len(received) == 1)
        else:
            ck(f"unfinished repair {identity}", not finish and not arrivals_for_item
               and not [x for x in item_task_completes if x["item"] == identity]
               and not [x for x in repair_sub_done if x["item"] == identity])
            pending_repairs.append(identity)
    ck("all system replacements complete", len(system_task_done) == len(demands))
    terminal_fit_receipt_id = None
    if fit_done and system_task_done:
        terminal_task = system_task_done[-1]["task"]
        terminal_receipts = [x for x in receives if x["task"] == terminal_task]
        ck("terminal completed fit receipt", fit_done[-1]["task"] == terminal_task
           and len(terminal_receipts) == 1 and terminal_receipts[0]["time"] <= fit_done[-1]["time"])
        if len(terminal_receipts) == 1:
            terminal_fit_receipt_id = terminal_receipts[0]["item"]
    ck("one bridge to first actual shortage", bool(repair_starts and bo_adds and pairs
       and repair_starts[0]["time"] < bo_adds[0]["time"] < pairs[0][1]["time"]
       and len([x for x in receives if x["item"] == repair_starts[0]["item"]
                and approx(x["time"], pairs[0][1]["time"])]) == 1))

    # Complete on-hand and backorder membership is drawn from adjacent raw log
    # lines. Aggregate StockTotalResults is used only for its documented metrics.
    on_hand = {0}
    bo_level = 0
    opening = [i for i, line in enumerate(lines) if line.startswith("Time: 0 " + STOCK + " Stock initiated")]
    ck("single opening physical ID0", len(opening) == 1 and opening[0]+1 < len(lines)
       and lines[opening[0]+1] == "  Stock at: " + STOCK + " Level: 1 Items:<TEACH-LRU-01,0,0>,")
    for i, line in enumerate(lines):
        change = re.match(r"^Time: [0-9.]+ " + re.escape(STOCK)
                          + r" (Take replacement item|Put back replacement item) <TEACH-LRU-01,0,(\d+)>", line)
        bo_add = line.startswith("Time: ") and " " + STOCK + " Backorder added" in line
        bo_remove = line.startswith("Time: ") and " " + STOCK + " Backorder removed" in line
        if change:
            identity = int(change[2])
            if change[1] == "Take replacement item":
                ck(f"issued ID {identity} held at line {i}", identity in on_hand)
                on_hand.discard(identity)
            else:
                ck(f"restocked ID {identity} not already held line {i}", identity not in on_hand)
                on_hand.add(identity)
            next_line = lines[i+1] if i+1 < len(lines) else ""
            expected_ids = set(map(int, re.findall(r"<TEACH-LRU-01,0,(\d+)>", next_line)))
            ck(f"stock level and member IDs line {i}", next_line.startswith(
                "  Stock at: " + STOCK + " Level: " + str(len(on_hand)) + " Items:")
                and expected_ids == on_hand)
        if bo_add or bo_remove:
            bo_level += 1 if bo_add else -1
            next_line = lines[i+1] if i+1 < len(lines) else ""
            ck(f"backorder level line {i}", bo_level >= 0 and next_line.startswith(
                "  Backorders at: " + STOCK + " Nbr: " + str(bo_level)))
    ck("terminal stock/backorder closure", bo_level == len(bo_adds)-len(bo_removes)
       and len(on_hand) <= 1)

    def segments(rows: list[dict], initial: int = 0) -> list[tuple[float, float, int]]:
        level, previous, result = initial, 0.0, []
        for row in sorted(rows, key=lambda x: (x["time"], x["line"])):
            t = row["time"]
            ck(f"timeline chronological line {row['line']}", previous <= t <= HORIZON)
            if t > previous:
                result.append((previous, t, level))
            level += row["delta"]
            ck(f"timeline level line {row['line']}", 0 <= level <= 1)
            previous = t
        if previous < HORIZON:
            result.append((previous, HORIZON, level))
        return result

    def weighted(parts: list[tuple[float, float, int]], lo: float, hi: float) -> float:
        return sum(overlap(a, b, lo, hi)*level for a, b, level in parts)/(hi-lo)

    ready_parts = segments([{**x, "delta": 1} for x in ready_in]
                           + [{**x, "delta": -1} for x in ready_out])
    repair_parts = segments([{**x, "delta": 1} for x in repair_enter]
                            + [{**x, "delta": -1} for x in repair_exit])
    bo_parts = segments([{**x, "delta": 1} for x in bo_adds]
                        + [{**x, "delta": -1} for x in bo_removes])
    ck("ready terminal event state", bool(ready_parts) and ready_parts[-1][2]
       == (1 if len(repair_enter) == len(repair_exit) else 0))
    ck("repair terminal state", bool(repair_parts) and repair_parts[-1][2]
       == len(repair_enter)-len(repair_exit))
    ck("backorder terminal state", bool(bo_parts) and bo_parts[-1][2] == bo_level)
    ck("critical failure count", len(critical) >= len(demands))

    ck("72 rows each", len(system_rows) == len(stock_rows) == 72)
    for i, (system, stock) in enumerate(zip(system_rows, stock_rows)):
        lo, hi = i/2, (i+1)/2
        ck(f"SystemResults identities/bin {i}", system["UNID"] == "Total over all Units"
           and system["SID"] == "Total over all Systems"
           and approx(system["STINT"], lo, 1e-8) and approx(system["ETINT"], hi, 1e-8))
        ck(f"StockTotalResults bin {i}", approx(stock["STINT"], lo, 1e-8)
           and approx(stock["ETINT"], hi, 1e-8))
        ck(f"SystemResults ready/repair {i}", approx(system["NSYRY"], weighted(ready_parts, lo, hi), BIN_TOL)
           and approx(system["NSYUA"], weighted(repair_parts, lo, hi), BIN_TOL))
        ck(f"SystemResults failure count {i}", system["NFAIL"] == sum(lo <= x["time"] < hi for x in critical))
        ck(f"SystemResults partition {i}", approx(
            system["NSYMA"] + system["NSYRY"] + system["NSYUA"] + system["NSYLA"], 1, BIN_TOL)
            and approx(sum(system[k] for k in ("NSYRP","NSYPM","NSYWI","NSYWR","NSYTP","NSYUH")),
                       system["NSYUA"], BIN_TOL))
        expected_nbo = weighted(bo_parts, lo, hi)
        expected_pnb = sum(overlap(a, b, lo, hi) for a, b, level in bo_parts if level == 0)/(hi-lo)
        ck(f"StockTotalResults BO/PNB {i}", approx(stock["NBO"], expected_nbo, BIN_TOL)
           and approx(stock["PNB"], expected_pnb, BIN_TOL))
        demands_in_bin = [x for x in demands if lo <= x["time"] < hi]
        waits_in_bin = [x for x in route_waits if lo <= x[0] < hi]
        ck(f"StockTotalResults demand {i}", stock["NDF"] == len(demands_in_bin)
           and len(waits_in_bin) == len(demands_in_bin))
        if waits_in_bin:
            shortages = [x for x in waits_in_bin if x[2]]
            ck(f"StockTotalResults ROS/WT {i}", stock["ROS"] is not None
               and approx(stock["ROS"], len(shortages)/len(waits_in_bin), BIN_TOL)
               and stock["WT"] is not None
               and approx(stock["WT"], sum(x[1] for x in waits_in_bin)/len(waits_in_bin), BIN_TOL))
            if shortages:
                ck(f"StockTotalResults shortage wait {i}", stock["WTS"] is not None
                   and approx(stock["WTS"], sum(x[1] for x in shortages)/len(shortages), BIN_TOL))
        else:
            ck(f"StockTotalResults no demand metrics {i}", stock["ROS"] is None and stock["WT"] is None)

    return {"passed": not failures, "checks": checks, "failures": failures,
            "demands": len(demands), "backorders_added": len(bo_adds),
            "backorders_removed": len(bo_removes), "repair_starts": len(repair_starts),
            "repair_finishes": len(repair_finishes), "pending_repair_ids": pending_repairs,
            "on_hand_ids_at_horizon": sorted(on_hand), "backorders_at_horizon": bo_level,
            "terminal_fit_receipt_id": terminal_fit_receipt_id,
            "installed_item_identity_after_fit": "unobservable_in_cli_log",
            "printed_time_tolerance_hours": TIME_TOL,
            "float32_bin_tolerance": BIN_TOL}

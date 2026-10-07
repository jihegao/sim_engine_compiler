"""Pure in-memory adversarial checks for independent I03.var02 replay."""

import json
import struct
from copy import deepcopy

import independent_replay_v2 as replay


def synthetic_child_log():
    lines = ["SIMLOX LOG FILE", "36"]
    def add(t, body):
        lines.append(f"Time: {t} {body}")
    for air in (0, 1):
        add(0, f"<TEACH-AIR-01,{air}> Next random failure will occur 1e+010")
        add(0, f"<TEACH-AIR-01,{air}> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>")
    add(0, "<TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
    add(0, "Start of day no 0")
    def queue(t, count, task=None):
        add(t, "<BASE-01,0> trig missions and tasks waiting for resources")
        lines.extend(["  Missions waiting for resources at: <BASE-01,0>  ",
                      f"  Tasks waiting for resources at: <BASE-01,0> {count}"])
        if task is not None:
            lines.append(f"  < subtask {task} seqno 1 within system preparation task {task} on <TEACH-AIR-01,1>, C, 0.5>")
    queue(0, 0)
    add(0, "resource shift 0 created at <P-CREW at <BASE-01,0>>")
    add(0, "resource shift 0 starting at <P-CREW at <BASE-01,0>> no shift period")
    lines.extend(["  Free resources at: <BASE-01,0> P-CREW 2",
                  "  Missions and tasks using resources at: <BASE-01,0> 0"])
    queue(0, 0)
    add(6, "resource transfer task 0 (OUT)  created: starting from  <P-CREW at <BASE-01,0>>")
    add(6, "<P-CREW at <BASE-01,0>> Resource transfer demand arrives from OUT-transfer ")
    add(6, "resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 0")
    add(6, "resource transfer task 0 (OUT)  arrives with 1 resources")
    for wave, start in enumerate((7.5, 19.5)):
        mid = f"<BASIC-MISSION,TEACH-UNIT,0,0,{wave}>"
        add(start, "<TEACH-UNIT> mission ordered: BASIC-MISSION")
        add(start, f"{mid} mission created: ")
        add(start, f"{mid} mission activated, systems requested: 2")
        for air in (0, 1):
            add(start, f"{mid} mission allocates system: <TEACH-AIR-01,{air}>")
            add(start, f"<TEACH-AIR-01,{air}> nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>")
            add(start, f"<TEACH-AIR-01,{air}> releases excess resources (if any)")
            add(start, f"<TEACH-AIR-01,{air}> preparation started, mission: {mid}")
        def task(air, action, t):
            ident = 2 * wave + air
            return add(t, f"subtask {ident} seqno 1 within system preparation task {ident} on <TEACH-AIR-01,{air}> {action}")
        def availability(air, result, t):
            task(air, "resource availability test", t)
            lines.append(f"  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 {result} ")
        def book(air, t):
            task(air, "books resources", t)
            add(t, "<P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0")
            lines.extend(["  Missions and tasks using resources at: <BASE-01,0> 1",
                          f"  < subtask {2*wave+air} seqno 1 within system preparation task {2*wave+air} on <TEACH-AIR-01,{air}>, C, 1, 0.5>"])
            task(air, "starts performing, planned to last for 0.5 hours", t)
        def finish(air, t):
            task(air, "completed", t)
            task(air, "frees resources", t)
            add(t, "<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1")
            ident = 2 * wave + air
            add(t, f"system preparation task {ident} on <TEACH-AIR-01,{air}> completed")
            add(t, f"<TEACH-AIR-01,{air}> preparation ended, mission: {mid}")
        add(start, f"system preparation task {2*wave} on <TEACH-AIR-01,0> started")
        task(0, "started", start)
        task(0, "requests resources", start)
        availability(0, "OK", start)
        book(0, start)
        add(start, f"system preparation task {2*wave+1} on <TEACH-AIR-01,1> started")
        task(1, "started", start)
        task(1, "requests resources", start)
        availability(1, "failed", start)
        finish(0, start + .5)
        queue(start + .5, 1, 2*wave+1)
        availability(1, "OK", start + .5)
        task(1, "resource received", start + .5)
        book(1, start + .5)
        queue(start + .5, 0)
        finish(1, start + 1)
        queue(start + 1, 0)
        launch = start + 1
        add(launch, f"{mid} mission starting, duration: 1 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
        add(launch + .25, f"{mid} task starting: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
        add(launch + .75, f"{mid} task completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
        add(launch + 1, f"{mid} mission success: ")
        add(launch + 1, f"{mid} mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
        for air in (0, 1):
            add(launch + 1, f"<TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,{air}>, mission success, ")
            lines.extend([" no failures ", " no PMTasks"])
            add(launch + 1, f"<TEACH-AIR-01,{air}> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>")
            add(launch + 1, f"<TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,{air}>")
            add(launch + 1, f"<TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,{air}>")
            if air == 0:
                add(launch + 1, "<TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>")
            else:
                add(launch + 1, "<TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
            add(launch + 1, "<TEACH-AIR-01,BASE-01,0> Repair task priority list:")
    add(24, "Start of day no 1")
    queue(24, 0)
    add(36, "resource shift 0 ended at <P-CREW at <BASE-01,0>> time gap to next = 0")
    return ("\n".join(lines) + "\n").encode()


def synthetic_report(contract, model):
    rows = replay.expected_report(contract, model, "idle", replay.source_prediction())
    template = replay.native_json((replay.PARENT_RUN / "out-report-raw.json").read_bytes())
    doc = deepcopy(template)
    for table in doc["report"]["tables"]:
        name = table["name"]
        columns = [c["name"] for c in table["columns"]]
        table["instances"][0]["rows"] = [[row[c] for c in columns] for row in rows[name]]
    return doc


def must_reject(label, call):
    try:
        call()
    except (AssertionError, ValueError, KeyError, IndexError, TypeError):
        return label
    raise AssertionError("negative escaped: " + label)


def run():
    contract = json.loads((replay.PKG / "contract.json").read_text(encoding="utf-8"))
    a = replay.Audit()
    replay.source_pins(contract, a)
    parent, model = replay.parent_and_prediction(contract, a)
    replay.child_input_check(model, deepcopy(model), a)
    synthetic_export = replay.native_json((replay.PARENT_RUN / "out-roundtrip-raw.json").read_bytes())
    for table in synthetic_export["model"]["tables"]:
        if table["name"] == "ProblemDescription":
            table["instances"][0]["rows"][0][0] = next(
                t for t in model["model"]["tables"] if t["name"] == "ProblemDescription")["instances"][0]["rows"][0][0]
        elif table["name"] == "ResourceTransfer":
            table["instances"][0]["rows"][0][3] = 6.0
    replay.roundtrip(model, synthetic_export, a, "predicted child export")
    replay.parent_replay(contract, parent, a)
    clean = synthetic_report(contract, model)
    replay.compare_report(contract, model, clean, "idle", a, replay.source_prediction())
    raw = synthetic_child_log()
    timeline = replay.child_physical(raw, a)
    a.ok(timeline == replay.source_prediction(), "physical fixture drives report oracle")
    rejects = []
    def bad_report(label, table, row, column, new):
        mutant = deepcopy(clean)
        t = next(t for t in mutant["report"]["tables"] if t["name"] == table)
        ci = next(i for i, c in enumerate(t["columns"]) if c["name"] == column)
        t["instances"][0]["rows"][row][ci] = new
        rejects.append(must_reject(label, lambda: replay.compare_report(contract, model, mutant, "idle", replay.Audit(), timeline)))
    bad_report("whole occupancy residue", "SystemResults", 16, "NSYMO", 1e-9)
    bad_report("stock null becomes zero", "StockTotalResults", 0, "ROS", 0)
    bad_report("stock PNB one becomes zero", "StockTotalResults", 0, "PNB", 0)
    bad_report("ResourceTotal one ULP", "ResourceResultsTotal", 0, "NRW",
               struct.unpack("<f", struct.pack("<I", struct.unpack("<I", struct.pack("<f", 1/36))[0] + 1))[0])
    bad_report("resource terminal busy", "ResourceResults", 71, "NRUM", 1e-9)
    bad_report("bool numeric", "SystemResults", 0, "NSYRY", True)
    mutant = deepcopy(model)
    next(t for t in mutant["model"]["tables"] if t["name"] == "ResourceTransfer")["instances"][0]["rows"][0][4] = 2
    rejects.append(must_reject("third source cell",
                               lambda: replay.child_input_check(model, mutant, replay.Audit())))
    mutant = deepcopy(synthetic_export)
    mutant["model"]["tables"][0]["columns"][0]["key"] = 1
    rejects.append(must_reject("roundtrip key bool to integer",
                               lambda: replay.roundtrip(model, mutant, replay.Audit(), "mutant")))
    mutant = deepcopy(synthetic_export)
    mutant["model"]["tables"].append(deepcopy(mutant["model"]["tables"][0]))
    rejects.append(must_reject("roundtrip duplicate table",
                               lambda: replay.roundtrip(model, mutant, replay.Audit(), "mutant")))
    mutant = deepcopy(clean)
    mutant["report"]["tables"][2]["columns"][0]["key"] = 1
    rejects.append(must_reject("column bool metadata", lambda: replay.compare_report(contract, model, mutant, "idle", replay.Audit(), timeline)))
    mutant = deepcopy(clean)
    mutant["report"]["tables"][2]["instances"][0]["instance_name"] += "X"
    rejects.append(must_reject("instance name", lambda: replay.compare_report(contract, model, mutant, "idle", replay.Audit(), timeline)))
    mutant = deepcopy(clean)
    mutant["report"]["tables"].append(deepcopy(mutant["report"]["tables"][-1]))
    rejects.append(must_reject("duplicate table", lambda: replay.compare_report(contract, model, mutant, "idle", replay.Audit(), timeline)))
    mutant = deepcopy(clean)
    mutant["report"]["tables"][2]["columns"].append(deepcopy(mutant["report"]["tables"][2]["columns"][-1]))
    rejects.append(must_reject("extra report column", lambda: replay.compare_report(contract, model, mutant, "idle", replay.Audit(), timeline)))
    lines = raw.decode().splitlines()
    def bad_log(label, old, new):
        changed = lines.copy()
        idx = next(i for i, line in enumerate(changed) if old in line)
        changed[idx] = changed[idx].replace(old, new)
        rejects.append(must_reject(label, lambda: replay.child_physical(("\n".join(changed)+"\n").encode(), replay.Audit())))
    bad_log("transfer quantity zero", "starts with 1 resources", "starts with 0 resources")
    bad_log("wrong station", "<P-CREW at <BASE-01,0>>", "<P-CREW at <BASE-02,0>>")
    bad_log("failed crew request omitted", "request for: 1 failed", "request for: 1 OK")
    bad_log("booked quantity two", "allocated to maintenance task: 1", "allocated to maintenance task: 2")
    bad_log("wrong aircraft owner", "on <TEACH-AIR-01,1> started", "on <TEACH-AIR-01,0> started")
    mutant = lines.copy()
    first_launch = next(i for i, line in enumerate(mutant) if
                        line.startswith("Time: 8.5 ") and "mission starting," in line)
    second_wave = next(i for i, line in enumerate(mutant) if line.startswith("Time: 19.5 "))
    for i in range(first_launch, second_wave):
        for old, new in (("Time: 8.5 ", "Time: 9.5 "),
                         ("Time: 8.75 ", "Time: 9.75 "),
                         ("Time: 9.25 ", "Time: 10.25 "),
                         ("Time: 9.5 ", "Time: 10.5 ")):
            if mutant[i].startswith(old):
                mutant[i] = new + mutant[i][len(old):]
                break
    rejects.append(must_reject("chronological first launch after h9 ceiling",
                               lambda: replay.child_physical(("\n".join(mutant)+"\n").encode(), replay.Audit())))
    bad_log("duplicate mission edge", "mission activated, systems requested: 2", "mission activated, systems requested: 3")
    bad_log("wrong mission success", "Time: 9.5 <BASIC-MISSION", "Time: 9.4 <BASIC-MISSION")
    mutant = lines.copy()
    first = next(i for i, line in enumerate(mutant) if "Availability test on" in line)
    mutant.insert(first + 1, mutant[first])
    rejects.append(must_reject("duplicate untimed availability continuation",
                               lambda: replay.child_physical(("\n".join(mutant)+"\n").encode(), replay.Audit())))
    mutant = lines.copy()
    first = next(i for i, line in enumerate(mutant) if line.startswith("Time: 8.0 ") and "deallocated from" in line)
    second = next(i for i, line in enumerate(mutant) if line.startswith("Time: 8.0 ") and "allocated to maintenance task" in line)
    mutant[first], mutant[second] = mutant[second], mutant[first]
    rejects.append(must_reject("equal-time book before release",
                               lambda: replay.child_physical(("\n".join(mutant)+"\n").encode(), replay.Audit())))
    rejects.append(must_reject("duplicate JSON key", lambda: replay.native_json(b'{"x":1,"x":2}')))
    rejects.append(must_reject("nonfinite JSON", lambda: replay.native_json(b'{"x":NaN}')))
    print(json.dumps({"schema": "i03-var02-independent-self-check/v1", "status": "STATIC_ONLY",
                      "checks": a.checks, "parent_cells": 5210, "predicted_child_cells": 5210,
                      "synthetic_physical": True, "negative_rejections": len(rejects),
                      "rejected": rejects}, indent=2, sort_keys=True))


if __name__ == "__main__":
    run()

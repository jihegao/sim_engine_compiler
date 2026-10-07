"""Read-only, predeclared C09.var02 physical and complete-report gate.

The runner calls live mode after the report export and before closure sealing.
The same file can be rerun in sealed mode after the closure exists. It invokes
no native process and never edits run artifacts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse
from report_oracle import (RESOURCE_FIELDS, RESOURCE_TOTAL_FIELDS, STOCK_FIELDS,
                           SUMMARY_FIELDS, SYSTEM_FIELDS, compare, derive, events)
from verify_sources import verify as verify_sources

HERE = Path(__file__).resolve().parent
INPUT_SHA = {
    "ordinary": "b971efb41492789f32475aae7fa9f37c0e30e9461203b48d37e08e2747e8d2e3",
    "shortage": "fc65462d65c0fea1017f81e41dc283a9a1f666e7b1f42aeb262fc6f5b8384bff",
}
TABLE_COLUMNS = {"ProblemDescription": ["PDESC"], "ResultSummary": SUMMARY_FIELDS,
                 "SystemResults": SYSTEM_FIELDS, "StockTotalResults": STOCK_FIELDS,
                 "ResourceResults": RESOURCE_FIELDS, "ResourceResultsTotal": RESOURCE_TOTAL_FIELDS}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_tables(path: Path, horizon: float = 12) -> dict[str, list[dict]]:
    return output_tables_doc(parse(path), horizon)


def output_tables_doc(doc: dict, horizon: float) -> dict[str, list[dict]]:
    assert set(doc) == {"report"}
    tables = doc["report"]["tables"]
    assert [t["name"] for t in tables] == list(TABLE_COLUMNS), "six-table report order"
    out = {}
    for t in tables:
        name = t["name"]
        fields = [c["name"] for c in t["columns"]]
        assert fields == TABLE_COLUMNS[name], (name, fields)
        expected_instance = {
            "ProblemDescription": "", "ResultSummary": "",
            "SystemResults": f"Total over all Units;Total over all Systems;0.00;{horizon:.2f}",
            "StockTotalResults": f"0.00;{horizon:.2f};",
            "ResourceResults": f"Total over all Resources;Total over all Stations;0.00;{horizon:.2f}",
            "ResourceResultsTotal": f"Total over all Resources;Total over all Stations;0.00;{horizon:.2f}",
        }[name]
        assert len(t["instances"]) == 1 and t["instances"][0]["instance_name"] == expected_instance, name
        rows = t["instances"][0]["rows"]
        assert len(rows) == (int(horizon * 2) if name in {"SystemResults", "StockTotalResults", "ResourceResults"} else 1)
        assert all(len(r) == len(fields) for r in rows)
        out[name] = [dict(zip(fields, r)) for r in rows]
    assert sum(len(r) for rows in out.values() for r in rows) == 26 + int(horizon * 2) * 72
    return out


def diagnostics(text: str) -> None:
    assert "Input conversion completed. Errors: 0, Warnings: 3, Notes: 1" in text
    form = ""
    seen = []
    for line in text.splitlines():
        if line.startswith("Form: "):
            form = line.removeprefix("Form: ").strip()
        m = re.match(r"rec (\d+): \((warning|notice) #(\d+)\)", line)
        if m:
            seen.append((form, int(m.group(1)), m.group(2), int(m.group(3))))
    assert seen == [("Control", 1, "warning", 108),
                    ("ResourceRemoteSupport", 1, "notice", 292),
                    ("System", 1, "warning", 126),
                    ("System", 2, "warning", 126)], seen
    assert not re.search(r"\(error #\d+\)", text, re.I)


def source_shape(run: Path, arm: str) -> None:
    assert sha(HERE / f"{arm}-input.json") == sha(run / "input.json") == INPUT_SHA[arm]
    authored = parse(run / "input.json")
    assert len(authored["model"]["tables"]) == 32
    tm = {t["name"]: t for t in authored["model"]["tables"]}
    def row(name: str, key: str, value: object) -> dict:
        t = tm[name]; columns = [c["name"] for c in t["columns"]]
        match = [dict(zip(columns, r)) for i in t["instances"] for r in i["rows"]
                 if r[columns.index(key)] == value]
        assert len(match) == 1, (name, key, value)
        return match[0]
    control = row("Control", "RSEED", "1")
    assert control["SIMPE"] == control["RCEND"] == 12 and control["ENPM"] == "Y"
    assert row("System", "SID", "HOME-AIR")["FRT"] == 0
    assert row("SystemDeployment", "SID", "HOME-AIR")["QTYPS"] == 1
    assert row("Unit", "UNID", "HOME-UNIT")["STID"] == "BASE-02"
    assert row("OperationProfile", "PRID", "HOME-ZERO")["IQTY"] == 0
    assert row("MaterielPM", "PMID", "HOME-PM9")["PMINT"] == 9
    assert row("PMLocation", "PMID", "HOME-PM9")["STID"] == "BASE-02"
    assert row("SubTaskResource", "TID", "HOME-PM")["RID"] == "P-MECH"
    assert row("ResourceRemoteSupport", "RID", "P-MECH")["TTRSS"] == (0.5 if arm == "ordinary" else 0.125)


def physical(log: str, arm: str) -> dict:
    ev = events(log)
    def find(pattern: str) -> list:
        return [e for e in ev if re.search(pattern, e.text)]
    def one(pattern: str):
        found = find(pattern)
        assert len(found) == 1, (pattern, len(found))
        return found[0]
    assert len(find(r"HOME-UNIT.*mission (ordered|created|activated|starting)")) == 0
    pm_start = one(r"^\s*system PM task \d+ on <HOME-AIR,\d+> started")
    pm_id = one(r"^\s*system PM task \d+ on <HOME-AIR,\d+> PMID: HOME-PM9")
    pm_task = int(re.search(r"system PM task (\d+)", pm_start.text).group(1))
    assert int(re.search(r"system PM task (\d+)", pm_id.text).group(1)) == pm_task
    assert abs(pm_start.time - 9) < 0.0002 and pm_id.time == pm_start.time
    request = [e for e in ev if re.search(rf"within system PM task {pm_task} on <HOME-AIR,\d+>", e.text) and
               "resource availability test" in e.text and
               re.search(r"<P-MECH at <BASE-02,\d+>> request for:\s*1 failed", e.text)]
    assert request, "HOME P-MECH failed availability not observed"
    request_subtasks = {int(re.search(r"subtask (\d+) seqno", e.text).group(1)) for e in request}
    assert len(request_subtasks) == 1
    pm_subtask = next(iter(request_subtasks))
    wait_start = one(r"<HOME-AIR,\d+> nbr resourcewait increased")
    wait_end = one(r"<HOME-AIR,\d+> nbr resourcewait decreased")
    assert request[0].time <= wait_start.time <= wait_end.time
    perform = one(rf"subtask {pm_subtask} seqno 1 within system PM task {pm_task} on <HOME-AIR,\d+> starts performing")
    subtask_complete = one(rf"subtask {pm_subtask} seqno 1 within system PM task {pm_task} on <HOME-AIR,\d+> completed")
    complete = one(rf"^\s*system PM task {pm_task} on <HOME-AIR,\d+> completed")
    assert wait_end.time <= perform.time < complete.time <= 12
    assert subtask_complete.time == complete.time
    assert abs(complete.time - perform.time - 0.25) <= 0.0002
    def transport(kind: str) -> list[tuple]:
        starts = find(rf"\b{kind} resource transport task \d+ starts with 1 resources")
        arrivals = find(rf"\b{kind} resource transport task \d+ arrives with 1 resources")
        created = find(rf"\b{kind} resource transport task \d+ created:")
        assert starts and len(starts) == len(arrivals) == len(created)
        def keyed(found: list) -> dict[int, object]:
            pairs = [(int(re.search(r"transport task (\d+)", e.text).group(1)), e) for e in found]
            assert len({key for key,_ in pairs}) == len(pairs), kind
            return dict(pairs)
        by_start, by_arrival, by_created = keyed(starts), keyed(arrivals), keyed(created)
        assert set(by_start) == set(by_arrival) == set(by_created), kind
        pairs = [(by_created[key], by_start[key], by_arrival[key], key) for key in by_start]
        assert all((c.time,c.line) < (s.time,s.line) < (a.time,a.line) for c,s,a,_ in pairs)
        source, destination = (("BASE-02", "BASE-01") if kind == "remote" else
                               ("BASE-01", "BASE-02"))
        for created_event, _, _, _ in pairs:
            assert re.search(rf"starting from\s+<P-MECH at <{source},\d+>>\s+aiming for\s+"
                             rf"<P-MECH at <{destination},\d+>>", created_event.text), created_event
        return sorted(pairs, key=lambda x: (x[1].time,x[1].line))
    outward = transport("remote")
    returning = transport("return")
    assert len(outward) == len(returning)
    for _,a,b,_ in outward:
        assert abs(b.time-a.time-0.25) <= 0.0002
    expected = 0.5 if arm == "ordinary" else 0.125
    # Transport IDs identify the three edges within each task. A return task
    # receives a different ID from its outward task, so associate them through
    # the observed one-unit lender occupancy rather than positional list zip.
    timeline = sorted([(s.time,s.line,"out",(s,a,task_id)) for _,s,a,task_id in outward] +
                      [(s.time,s.line,"return",(s,a,task_id)) for _,s,a,task_id in returning])
    active = None
    cycles = []
    for _, _, kind, (start, arrival, task_id) in timeline:
        if kind == "out":
            assert active is None, "second outward trip before lender unit returned"
            active = (start, arrival, task_id)
        else:
            assert active is not None, "return without an observed outward loan"
            o_start, o_arrive, o_id = active
            assert (o_arrive.time,o_arrive.line) <= (start.time,start.line)
            cycles.append((o_start,o_arrive,start,arrival,o_id,task_id))
            active = None
    assert active is None and len(cycles) == len(outward)
    remote_pool_arrivals = find(r"<P-MECH at <BASE-01,\d+>> remote transport arrives: 1")
    home_pool_arrivals = find(r"<P-MECH at <BASE-02,\d+>> return transport arrives: 1")
    assert len(remote_pool_arrivals) == len(outward) and len(home_pool_arrivals) == len(returning)
    for _,out_arrive,_,return_arrive,_,_ in cycles:
        assert sum(e.time == out_arrive.time and e.line > out_arrive.line for e in remote_pool_arrivals) == 1
        assert sum(e.time == return_arrive.time and e.line > return_arrive.line for e in home_pool_arrivals) == 1
    qualifying = [(o,a,r,z,o_id,r_id) for o,a,r,z,o_id,r_id in cycles
                  if any((a.time,a.line) < (req.time,req.line) < (r.time,r.line) and
                         (wait_start.time,wait_start.line) <= (r.time,r.line) and
                         (z.time,z.line) <= (wait_end.time,wait_end.line)
                         for req in request)]
    assert qualifying, "no lender-shortage-attributed return"
    assert any(abs(z.time-r.time-expected) <= 0.0002 and
               z.time <= perform.time for _,_,r,z,_,_ in qualifying), "TTRSS return duration"
    assert not find(r"(?:Stock initiated|Replacement item arrives|Take replacement item|Put back replacement item)"), "unexpected item stock"
    return {"pm_started":pm_start.time,"pm_wait_started":wait_start.time,"pm_work_started":perform.time,
            "pm_completed":complete.time,"pm_task_id":pm_task,"pm_subtask_id":pm_subtask,
            "outward_count":len(outward),"return_count":len(returning),
            "qualifying_return_task_ids":[r_id for *_,r_id in qualifying],
            "qualifying_return_hours":[round(z.time-r.time,6) for _,_,r,z,_,_ in qualifying]}


def provenance(run: Path, arm: str) -> dict:
    ids = {"ordinary":"c09-var02-v102-ordinary-ssh-20261007-01",
           "shortage":"c09-var02-v102-shortage-ssh-20261007-01"}
    assert run.name == ids[arm]
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    assert invocation["run_id"] == run.name and invocation["arm"] == arm
    assert invocation["session_id"] == 0 and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue"
    assert invocation["gui"] == {"pid":13340,"session_id":1,"start_unix_ms":1790590196826,"responding":True}
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    assert [s["name"] for s in steps][:5] == ["import","export","check_import_export","calc","jsonreport"]
    assert len(steps) in (5,6)
    assert all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps[:5])
    assert all(s["child_session_id"] == 0 for s in steps[:5] if s["name"] in {"import","export","calc","jsonreport"})
    if len(steps) == 6:
        assert steps[5]["name"] == "check_behavior" and steps[5]["status"] in {"started","completed"}
    mode = "live"
    closure_path = run / "closure.json"
    if closure_path.exists():
        mode = "sealed"
        closure = json.loads(closure_path.read_text(encoding="utf-8-sig"))
        assert closure["run_id"] == run.name and closure["invocation_sha256"] == sha(run / "invocation.json")
        assert closure["source_hashes_before"] == closure["source_hashes_after"]
        assert not closure["error"]
        assert len(steps) == 6 and steps[5]["status"] == "completed" and steps[5]["exit_code"] == 0
        for name, pin in closure["raw"].items():
            path = run / name
            assert path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"], name
    return {"mode":mode,"step_count":len(steps),"closure_sha256":sha(closure_path) if closure_path.exists() else None}


def validate(run: Path, arm: str) -> dict:
    assert arm in INPUT_SHA
    verify_sources()
    source_shape(run, arm)
    prov = provenance(run, arm)
    rt = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    assert rt["passed"] and rt["authored_row_tables"] == 25 and not rt["issues"]
    diagnostics((run / "run.log").read_text(encoding="utf-8-sig", errors="replace"))
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ledger = physical(log, arm)
    actual = output_tables(run / "report-raw.json")
    source = parse(HERE / f"{arm}-input.json")
    description = next(t for t in source["model"]["tables"] if t["name"] == "ProblemDescription")["instances"][0]["rows"][0][0]
    expected = derive(log, horizon=12, fleet=3, description=description)
    errors = compare(expected, actual, horizon=12, log=log)
    assert not errors, errors[:20]
    assert actual["SystemResults"][-1]["NSYRY"] == 3
    assert actual["SystemResults"][-1]["NSYUA"] == actual["SystemResults"][-1]["NSYWR"] == 0
    assert actual["ResourceResults"][-1]["NR"] == actual["ResourceResults"][-1]["NRN"] == 3
    assert actual["ResourceResults"][-1]["NRW"] == actual["ResourceResults"][-1]["NRRT"] == 0
    return {"schema":"c09-var02-v102-author-validation/v1","passed":True,"arm":arm,"run_id":run.name,
            "source_sha256":INPUT_SHA[arm],"source_seals":verify_sources()["counts"],
            "provenance":prov,"physical_ledger":ledger,"report_cells":1754}


if __name__ == "__main__":
    try:
        verdict = validate(Path(sys.argv[1]), sys.argv[2])
    except Exception as exc:
        verdict = {"schema":"c09-var02-v102-author-validation/v1","passed":False,
                   "error":f"{type(exc).__name__}: {exc}"}
    print(json.dumps(verdict,ensure_ascii=False,indent=2,sort_keys=True))
    sys.exit(0 if verdict["passed"] else 1)

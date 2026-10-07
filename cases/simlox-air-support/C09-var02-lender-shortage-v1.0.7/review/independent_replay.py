"""Reviewer-owned, read-only C09.var02 v1.0.7 physical and report replay.

`--self-check` replays the sealed accepted ordinary control and in-memory faults.
The default additionally requires a sealed new child and fails closed while absent.
This file never imports an author checker or writes a verdict/raw artifact.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import stat
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
CONTROL = PKG.parent / "C09-var02-lender-shortage-control-v0.1.1"
OLD = PKG.parent / "C09-var02-lender-shortage-v1.0.2"
PARENT_RUN = OLD / "runs/c09-var02-v102-ordinary-ssh-20261007-01"
CHILD_RUN = PKG / "runs/c09-var02-v107-shortage-ssh-20261007-01"
BASE = "d1d9a4dcbcfe146a0de41e01c3089dae235bb7ef"
CONTRACT_SHA = "2051fca4baf9555adaab28d870726eee97fe38ac61537630d6b63d2b89a5bb99"
INDEX_SHA = "c76f768942de24e9733e61e5dcf44755430fe5b910593f842710588536d3ff50"
PARENT_CLOSURE_SHA = "30a99a36775224096dae27e938495dae5e12bb441cd493c2312baf5bef58d5df"
PARENT_FAILURE_SHA = "43a64a32e56abdcf312482c16d56b391f6bb5eb0d939efa272a330e4ff86c73e"
ROOT_CONTEXT = PKG / "preserved-root-context"


def seal(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def direct_contract_pins(node):
    if isinstance(node, dict):
        if {"path", "bytes", "sha256"} <= node.keys():
            yield node
        for value in node.values():
            yield from direct_contract_pins(value)
    elif isinstance(node, list):
        for value in node:
            yield from direct_contract_pins(value)


def git_bytes(path: Path) -> bytes:
    relative = path.resolve().relative_to(REPO).as_posix()
    return subprocess.run(["git", "show", f"{BASE}:{relative}"], cwd=REPO,
                          check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def native_json(path: Path):
    source = path.read_bytes().decode("utf-8-sig")
    # Native jsonreport may leave syntax commas; preserve quoted commas exactly.
    out = []
    quoted = escaped = False
    for i, char in enumerate(source):
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
            j = i + 1
            while j < len(source) and source[j].isspace():
                j += 1
            if j == len(source) or source[j] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def exact_pin(path: Path, record: dict):
    assert seal(path.read_bytes()) == {k: record[k] for k in ("bytes", "sha256")}, path


def verify_parent_index() -> dict:
    assert seal((PKG / "contract.json").read_bytes())["sha256"] == CONTRACT_SHA
    contract = native_json(PKG / "contract.json")
    assert contract["base_commit"] == BASE
    assert contract["planned_child"]["run_id"] == CHILD_RUN.name
    catalog_path = (PKG / contract["published_parent"]["catalog"]["path"]).resolve()
    historical_catalog = ROOT_CONTEXT / "publication-index-at-base.json"
    # The contract pins the historical CRLF disk identity; the base Git blob is
    # a distinct LF identity. A later publication append may change the live file.
    exact_pin(historical_catalog, contract["published_parent"]["catalog"])
    archived = native_json(historical_catalog)
    assert json.loads(git_bytes(catalog_path).decode("utf-8-sig")) == archived
    live = native_json(catalog_path)
    assert len(archived["entries"]) == 486
    assert live["entries"][:486] == archived["entries"]
    assert {k: v for k, v in live.items() if k != "entries"} == {k: v for k, v in archived.items() if k != "entries"}
    direct = []

    def walk(node):
        if isinstance(node, dict):
            if {"path", "bytes", "sha256"} <= node.keys():
                path = Path(node["path"])
                path = path if path.is_absolute() else (PKG / path).resolve()
                if path == catalog_path:
                    exact_pin(historical_catalog, node)
                elif path.parent.name == "tmp":
                    # Only contract-enumerated historical tmp receipts may use
                    # byte-identical package custody after publication.
                    exact_pin(ROOT_CONTEXT / path.name, node)
                    if path.is_file():
                        exact_pin(path, node)
                else:
                    exact_pin(path, node)
                direct.append(path)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(contract)
    assert len(direct) == 131
    idxpath = CONTROL / "evidence-index.json"
    assert seal(idxpath.read_bytes())["sha256"] == INDEX_SHA
    index = native_json(idxpath)
    assert (len(index["source_files"]), len(index["raw_files"]), len(index["accepted_source_refs"])) == (101, 130, 77)
    for item in index["source_files"]:
        path = (CONTROL / item["path"]).resolve()
        exact_pin(path, item)
        assert seal(git_bytes(path)) == {k: item[k] for k in ("bytes", "sha256")}, path
    for item in index["raw_files"]:
        exact_pin((CONTROL / item["path"]).resolve(), item)
    distinct = 0
    for item in index["accepted_source_refs"]:
        path = (CONTROL / item["path"]).resolve()
        assert seal(path.read_bytes()) == item["local_disk"]
        assert seal(git_bytes(path)) == item["published_git"]
        distinct += item["local_disk"] != item["published_git"]
    assert distinct == 2
    assert seal((PARENT_RUN / "closure.json").read_bytes())["sha256"] == PARENT_CLOSURE_SHA
    assert seal((PARENT_RUN / "failure-seal.json").read_bytes())["sha256"] == PARENT_FAILURE_SHA
    closure = native_json(PARENT_RUN / "closure.json")
    assert len(closure["raw"]) == 13
    for name, record in closure["raw"].items():
        exact_pin(PARENT_RUN / name, record)
    return contract


def source_child(parent: dict, child: dict, contract: dict):
    expected = deepcopy(parent)
    tables = {t["name"]: t for t in expected["model"]["tables"]}
    assert len(tables) == 32
    assert sum(bool(i["rows"]) for t in tables.values() for i in t["instances"]) == 25
    table = tables["ResourceRemoteSupport"]
    columns = [c["name"] for c in table["columns"]]
    matches = []
    for instance in table["instances"]:
        for row in instance["rows"]:
            mapped = dict(zip(columns, row))
            if (mapped.get("RID"), mapped.get("STID"), mapped.get("RSTID")) == ("P-MECH", "BASE-01", "BASE-02"):
                matches.append(row)
    assert len(matches) == 1 and matches[0][columns.index("TTRSS")] == .5
    matches[0][columns.index("TTRSS")] = .125
    desc = tables["ProblemDescription"]["instances"][0]["rows"][0]
    assert desc[0] == "ordinary TTRSS equals TTRS"
    desc[0] = "shortage TTRSS 0.125 child test"
    assert child == expected, "child source differs beyond the two frozen cells"
    assert len(contract["planned_child"]["exact_changed_cells"]) == 2


def roundtrip(input_model: dict, output_model: dict):
    authored = input_model["model"]["tables"]
    exported = output_model["model"]["tables"]
    assert len(authored) == len(exported) == 32
    populated = 0
    for left, right in zip(authored, exported):
        assert left["name"] == right["name"] and left["columns"] == right["columns"]
        assert len(left["instances"]) == len(right["instances"])
        for li, ri in zip(left["instances"], right["instances"]):
            assert li["instance_name"] == ri["instance_name"]
            if li["rows"]:
                assert li["rows"] == ri["rows"]
                populated += 1
            else:
                assert not any(any(cell is not None for cell in row) for row in ri["rows"])
    assert populated == 25


def lines_with_continuations(raw: str) -> list[str]:
    result = []
    for line in raw.splitlines():
        if line.startswith("Time: "):
            result.append(line)
        elif result and line.startswith(("  ", "\t")):
            result[-1] += " " + line.strip()
    return result


def one(lines: list[str], pattern: str) -> tuple[float, int, str]:
    compiled = re.compile(r"^Time: ([0-9.]+)\s+" + pattern + r".*$")
    found = [(float(m.group(1)), i, line) for i, line in enumerate(lines)
             if (m := compiled.match(line))]
    assert len(found) == 1, (pattern, found)
    return found[0]


def later_repair_cycles(lines: list[str]) -> list[dict]:
    """Parse additional completed borrower repair/loan cycles after first HOME PM.

    This deliberately derives intervals from typed task IDs and event order. A
    surprising extra task fails closed until its edges can be reconciled; it is
    never silently ignored when constructing report expectations.
    """
    events = []
    for line in lines:
        m = re.match(r"^Time: ([0-9.]+)\s+(.*)$", line)
        if m:
            events.append((float(m.group(1)), m.group(2)))
    relevant = [e for e in events if re.search(
        r"(?:remote|return) resource transport task|^\s*<P-MECH at|system (?:DIRP|PM) task|"
        r"direct repair subtask|nbr resourcewait|nbr ready (?:increased|decreased)", e[1])]
    if not any("resource transport task" in text for _, text in relevant):
        assert all(re.search(r"<HOME-AIR,2> nbr ready increased at unit", text)
                   for _, text in relevant), relevant
        return []
    if any("system PM task" in text for _, text in relevant):
        raise AssertionError("later PM requires explicit task/stock ledger extension")

    starts = {}
    ends = {}
    for kind in ("remote", "return"):
        for task, phase, verb in ((starts, "start", "starts with"), (ends, "end", "arrives with")):
            for t, text in relevant:
                m = re.search(rf"{kind} resource transport task (\d+) {verb} 1 resources", text)
                if m:
                    key = (kind, int(m.group(1)))
                    assert key not in task, (key, phase)
                    task[key] = t
    assert starts and starts.keys() == ends.keys(), "unpaired later transport tasks"
    ordered = sorted(starts, key=lambda key: starts[key])
    assert len(ordered) % 2 == 0
    assert all(ordered[i][0] == "remote" and ordered[i + 1][0] == "return"
               for i in range(0, len(ordered), 2))
    cycles = []
    for i in range(0, len(ordered), 2):
        outward, returning = ordered[i:i + 2]
        o0, o1 = starts[outward], ends[outward]
        r0, r1 = starts[returning], ends[returning]
        assert o0 < o1 <= r0 < r1 <= 12, (outward, returning)
        assert abs(o1 - o0 - .25) <= .0001
        declared = [float(m.group(1)) for t, text in relevant if t == r0 and
                    (m := re.search(rf"return resource transport task {returning[1]} starts with 1 resources, transportation time: ([0-9.]+)", text))]
        assert len(declared) == 1 and abs(r1 - r0 - declared[0]) <= .0001
        created_out = [text for _, text in relevant if re.search(
            rf"remote resource transport task {outward[1]} created: starting from\s+"
            r"<P-MECH at <BASE-02,\d+>>\s+aiming for\s+<P-MECH at <BASE-01,\d+>>", text)]
        created_return = [text for _, text in relevant if re.search(
            rf"return resource transport task {returning[1]} created: starting from\s+"
            r"<P-MECH at <BASE-01,\d+>>\s+aiming for\s+<P-MECH at <BASE-02,\d+>>", text)]
        assert len(created_out) == len(created_return) == 1
        receipts_out = [(t, text) for t, text in relevant if "<P-MECH at <BASE-01," in text and
                        "remote transport arrives: 1" in text and t == o1]
        receipts_return = [(t, text) for t, text in relevant if "<P-MECH at <BASE-02," in text and
                           "return transport arrives: 1" in text and t == r1]
        assert len(receipts_out) == len(receipts_return) == 1
        cycles.append({"out_id": outward[1], "return_id": returning[1], "out_start": o0,
                       "out_end": o1, "return_start": r0, "return_end": r1,
                       "return_declared": declared[0]})
    assert all(cycles[i]["return_end"] <= cycles[i + 1]["out_start"]
               for i in range(len(cycles) - 1)), "one mechanic loaned twice"

    repairs = {}
    for t, text in relevant:
        m = re.search(r"^\s*system DIRP task (\d+) on <TEACH-AIR-01,(\d+)> (started|completed)", text)
        if m:
            task_id, aircraft = map(int, m.group(1, 2))
            record = repairs.setdefault(task_id, {"aircraft": aircraft})
            assert record["aircraft"] == aircraft and m.group(3) not in record
            record[m.group(3)] = t
        m = re.search(r"direct repair subtask (\d+) seqno 1 within system DIRP task (\d+) on <TEACH-AIR-01,(\d+)> (starts performing|completed)", text)
        if m:
            subtask, task_id, aircraft = map(int, m.group(1, 2, 3))
            record = repairs.setdefault(task_id, {"aircraft": aircraft})
            assert record["aircraft"] == aircraft and record.setdefault("subtask", subtask) == subtask
            key = "work_start" if m.group(4) == "starts performing" else "work_end"
            assert key not in record
            record[key] = t
        m = re.search(r"direct repair subtask (\d+) seqno 1 within system DIRP task (\d+) on <TEACH-AIR-01,(\d+)> (books|frees) resources", text)
        if m:
            subtask, task_id, aircraft = map(int, m.group(1, 2, 3))
            record = repairs.setdefault(task_id, {"aircraft": aircraft})
            assert record["aircraft"] == aircraft and record.setdefault("subtask", subtask) == subtask
            key = "booked" if m.group(4) == "books" else "freed"
            assert key not in record
            record[key] = t
    alloc = [(t, text) for t, text in relevant if re.search(
        r"^\s*<P-MECH at <BASE-01,\d+>> allocated to maintenance task:\s*1\s+available now:\s*0", text)]
    release = [(t, text) for t, text in relevant if re.search(
        r"^\s*<P-MECH at <BASE-01,\d+>> deallocated from\s+maintenance task:\s*1\s+available now:\s*1", text)]
    used_tasks = set()
    for cycle in cycles:
        candidates = [(task_id, repair) for task_id, repair in repairs.items()
                      if {"started", "completed", "work_start", "work_end", "booked", "freed",
                          "subtask", "aircraft"} <= repair.keys()
                      and cycle["out_end"] <= repair["work_start"]
                      and repair["work_end"] <= cycle["return_start"]]
        candidates.sort(key=lambda pair: (pair[1]["work_start"], pair[0]))
        assert candidates, "loan has no linked repair"
        linked = []
        previous_end = cycle["out_end"]
        for task_id, repair in candidates:
            assert task_id not in used_tasks and previous_end <= repair["work_start"]
            used_tasks.add(task_id)
            assert repair["started"] <= repair["work_start"]
            assert repair["work_end"] == repair["completed"]
            assert repair["booked"] == repair["work_start"] and repair["freed"] == repair["work_end"]
            assert abs(repair["work_end"] - repair["work_start"] - .5) <= .0001
            aircraft = repair["aircraft"]
            wait_up = [(t, text) for t, text in relevant if re.search(
                rf"<TEACH-AIR-01,{aircraft}> nbr resourcewait increased", text) and t == repair["started"]]
            wait_down = [(t, text) for t, text in relevant if re.search(
                rf"<TEACH-AIR-01,{aircraft}> nbr resourcewait decreased", text) and t == repair["work_start"]]
            ready_down = [(t, text) for t, text in relevant if re.search(
                rf"<TEACH-AIR-01,{aircraft}> nbr ready decreased at unit", text) and t == repair["started"]]
            ready_up = [(t, text) for t, text in relevant if re.search(
                rf"<TEACH-AIR-01,{aircraft}> nbr ready increased at unit", text) and t == repair["completed"]]
            assert len(wait_up) == len(wait_down) == len(ready_down) == len(ready_up) == 1
            assert sum(t == repair["work_start"] for t, _ in alloc) == 1
            assert sum(t == repair["work_end"] for t, _ in release) == 1
            linked.append({"repair_task": task_id, "aircraft": aircraft,
                           "wait_start": repair["started"], "work_start": repair["work_start"],
                           "work_end": repair["work_end"]})
            previous_end = repair["work_end"]
        assert linked[-1]["work_end"] == cycle["return_start"]
        cycle["repairs"] = linked
    assert len(used_tasks) == len(repairs)
    assert len(alloc) == len(release) == len(used_tasks), "unlinked mechanic booking"
    return cycles


def trace(log_text: str) -> dict:
    all_lines = lines_with_continuations(log_text)
    completed = [i for i, text in enumerate(all_lines) if re.search(
        r"^Time: [0-9.]+\s+system PM task 3 on <HOME-AIR,2> completed", text)]
    assert len(completed) == 1
    lines = all_lines[:completed[0] + 1]
    rules = {
        "prep": r"system preparation task 0 on <TEACH-AIR-01,0> started",
        "launch": r"system preparation task 0 on <TEACH-AIR-01,0> completed",
        "arrival": r".*aborted mission completed:",
        "teach_wait": r"<TEACH-AIR-01,0> nbr resourcewait increased",
        "outward_start": r"remote resource transport task 3 starts with 1 resources",
        "outward_end": r"remote resource transport task 3 arrives with 1 resources",
        "teach_repair": r"direct repair subtask 2 seqno 1 within system DIRP task 2 on <TEACH-AIR-01,0> starts performing",
        "teach_done": r"direct repair subtask 2 seqno 1 within system DIRP task 2 on <TEACH-AIR-01,0> completed",
        "home_wait": r"<HOME-AIR,2> nbr resourcewait increased",
        "return_start": r"return resource transport task 0 starts with 1 resources",
        "return_end": r"return resource transport task 0 arrives with 1 resources",
        "home_regrant": r"subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> resource received",
        "home_pm": r"subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> starts performing",
        "home_done": r"subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> completed",
        "home_task_done": r"system PM task 3 on <HOME-AIR,2> completed",
    }
    observed = {key: one(lines, pattern) for key, pattern in rules.items()}
    t = {key: value[0] for key, value in observed.items()}
    # ID, station, request, booking and release edges are linked to this one cycle.
    necessary = {
        "outward_create": r"remote resource transport task 3 created: starting from  <P-MECH at <BASE-02,0>> aiming for  <P-MECH at <BASE-01,0>>",
        "outward_receipt": r"<P-MECH at <BASE-01,0>> remote transport arrives: 1",
        "return_create": r"return resource transport task 0 created: starting from  <P-MECH at <BASE-01,0>> aiming for  <P-MECH at <BASE-02,0>>",
        "return_receipt": r"<P-MECH at <BASE-02,0>> return transport arrives: 1",
        "borrow_alloc": r"<P-MECH at <BASE-01,0>> allocated to maintenance task: 1  available now: 0",
        "borrow_release": r"<P-MECH at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
        "home_alloc": r"<P-MECH at <BASE-02,0>> allocated to maintenance task: 1  available now: 0",
        "home_release": r"<P-MECH at <BASE-02,0>> deallocated from  maintenance task: 1  available now: 1",
        "pm_due": r"system PM task 3 on <HOME-AIR,2> started",
        "pm_test_failed": r"subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> resource availability test Availability test on  <P-MECH at <BASE-02,0>> request for: 1 failed",
        "pm_test_ok": r"subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> resource availability test Availability test on  <P-MECH at <BASE-02,0>> request for: 1 OK",
        "pm_book": r"subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> books resources",
        "borrow_book": r"direct repair subtask 2 seqno 1 within system DIRP task 2 on <TEACH-AIR-01,0> books resources",
    }
    matched = {key: one(lines, pattern) for key, pattern in necessary.items()}
    assert sum("Availability test on  <P-MECH at <BASE-02,0>> request for: 1 failed" in x for x in lines) == 1
    assert sum("<P-MECH at <BASE-02,0>> Resource remote demand arrives from pool  <P-MECH at <BASE-01,0>>" in x for x in lines) == 1
    assert matched["outward_create"][1] < observed["teach_wait"][1] < observed["outward_start"][1]
    assert observed["outward_end"][1] <= matched["outward_receipt"][1] < matched["borrow_alloc"][1]
    assert matched["borrow_release"][1] < matched["return_create"][1] < observed["return_start"][1]
    assert observed["return_end"][1] <= matched["return_receipt"][1] < matched["home_alloc"][1]
    assert matched["home_alloc"][1] < observed["home_pm"][1] < observed["home_done"][1] < matched["home_release"][1]
    assert matched["pm_due"][1] < matched["pm_test_failed"][1] < matched["pm_test_ok"][1] < matched["pm_book"][1] < matched["home_alloc"][1]
    assert matched["borrow_book"][1] < matched["borrow_alloc"][1]
    assert matched["pm_test_failed"][0] == t["home_wait"] == 9
    assert matched["pm_test_ok"][0] == t["home_regrant"]
    assert t["prep"] == 7.5 and t["launch"] == 8 and t["home_wait"] == 9
    assert t["arrival"] == t["teach_wait"] == t["outward_start"]
    assert t["outward_end"] == t["teach_repair"] == matched["borrow_alloc"][0]
    assert t["teach_done"] == t["return_start"] == matched["borrow_release"][0]
    assert t["return_end"] <= t["home_regrant"] <= t["home_pm"] == matched["home_alloc"][0]
    assert t["home_done"] == t["home_task_done"] == matched["home_release"][0]
    assert t["teach_wait"] < 9 < t["return_end"] < t["home_done"] < 12
    assert abs(t["outward_end"] - t["outward_start"] - .25) < .0001
    assert abs(t["teach_done"] - t["teach_repair"] - .5) < .0001
    assert abs(t["home_done"] - t["home_pm"] - .25) < .0001
    for key in ("outward_start", "return_start"):
        declared = re.search(r"transportation time: ([0-9.]+)", observed[key][2])
        assert declared, (key, observed[key][2])
        elapsed = t["outward_end"] - t["outward_start"] if key == "outward_start" else t["return_end"] - t["return_start"]
        assert abs(elapsed - float(declared.group(1))) < .0001
    # Fail closed if a second trip/PM would need an additional state ledger.
    assert sum("remote resource transport task " in x and "starts with 1 resources" in x for x in lines) == 1
    assert sum("return resource transport task " in x and "starts with 1 resources" in x for x in lines) == 1
    assert sum(bool(re.match(r"^Time: [0-9.]+\s+system PM task \d+ on <HOME-AIR,2> started", x))
               for x in lines) == 1
    assert sum("<P-MECH at <BASE-01,0>> allocated to maintenance task: 1" in x for x in lines) == 1
    assert sum("<P-MECH at <BASE-02,0>> allocated to maintenance task: 1" in x for x in lines) == 1
    assert sum("<P-MECH at <BASE-01,0>> deallocated from  maintenance task: 1" in x for x in lines) == 1
    assert sum("<P-MECH at <BASE-02,0>> deallocated from  maintenance task: 1" in x for x in lines) == 1
    crew_alloc = [x for x in lines if "<P-CREW at <BASE-01,0>> allocated to maintenance task: 1" in x]
    crew_release = [x for x in lines if "<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1" in x]
    assert len(crew_alloc) == len(crew_release) == 2
    assert any("available now: 1" in x for x in crew_alloc) and any("available now: 0" in x for x in crew_alloc)
    assert any("available now: 1" in x for x in crew_release) and any("available now: 2" in x for x in crew_release)
    assert t["outward_start"] <= t["outward_end"] <= t["teach_repair"] <= t["teach_done"] <= t["return_start"] <= t["return_end"] <= t["home_pm"] <= t["home_done"]
    later = later_repair_cycles(all_lines[completed[0] + 1:])
    # Every printed mechanic booking must be owned by the selected borrower,
    # HOME PM, or a fully linked later repair. Balanced same-time orphan pairs
    # have zero report exposure, so report reconciliation cannot catch them.
    later_repair_count = sum(len(cycle["repairs"]) for cycle in later)
    for station, expected_count in (("BASE-01", 1 + later_repair_count), ("BASE-02", 1)):
        for verb in ("allocated to maintenance task:", "deallocated from  maintenance task:"):
            observed_count = sum(f"<P-MECH at <{station},0>> {verb} 1" in line for line in all_lines)
            assert observed_count == expected_count, (station, verb, observed_count)
    return {"times": t, "lines": all_lines, "matched": matched, "later_cycles": later}


def printed_u(value: float, exact: bool = False) -> float:
    if exact:
        return 0.0
    token = str(value)
    assert "." in token and "e" not in token
    return .5 * 10 ** (-len(token.partition(".")[2]))


def bound(value: float, edges: dict, uncertainty: dict, terms: dict, denominator: float,
          ceiling: float, a: float = 0, b: float = 12) -> float:
    uncertainty_time = sum(abs(coef) * uncertainty[key] / denominator for key, coef in terms.items()
                           if a < edges[key] < b)
    serialization = 5e-7 if uncertainty_time or not float(value).is_integer() else 0.0
    result = uncertainty_time + serialization
    assert result <= ceiling + 1e-15, (value, result, ceiling)
    return result


def equal(actual, expected, tolerance: float = 0.0) -> bool:
    if expected is None or isinstance(expected, str):
        return type(actual) is type(expected) and actual == expected
    if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual):
        return False
    return abs(actual - expected) <= tolerance


def overlap(s: float, e: float, a: float, b: float) -> float:
    return max(0.0, min(e, b) - max(s, a))


def report_plan(source: dict, trace_data: dict) -> dict:
    t = trace_data["times"]
    edges = {"prep": t["prep"], "launch": t["launch"], "arrival": t["arrival"],
             "loan_arrival": t["teach_repair"], "repair_end": t["teach_done"],
             "home_wait": t["home_wait"], "return_arrival": t["return_end"], "home_done": t["home_done"]}
    uncertainty = {key: printed_u(value, key in {"prep", "launch", "home_wait"}) for key, value in edges.items()}
    system_terms = {
        "NSYRY": {"arrival": 1, "repair_end": 1, "home_done": 1},
        "NSYMA": {"prep": 2, "arrival": 2}, "NSYMO": {"launch": 2, "arrival": 2},
        "NSYRP": {"loan_arrival": 1, "repair_end": 1},
        "NSYPM": {"return_arrival": 1, "home_done": 1},
        "NSYWR": {"arrival": 1, "loan_arrival": 1, "home_wait": 1, "return_arrival": 1},
        "NSYUA": {"arrival": 1, "repair_end": 1, "home_wait": 1, "home_done": 1},
        "NSYA": {"arrival": 1, "repair_end": 1, "home_wait": 1, "home_done": 1},
        "STACC": {"launch": 2, "arrival": 2}, "FTMO": {"launch": 2 / 3, "arrival": 2 / 3},
    }
    resource_terms = {
        "NR": {"arrival": 1, "loan_arrival": 1, "repair_end": 1, "return_arrival": 1},
        "NRA": {"arrival": 1, "loan_arrival": 1, "repair_end": 1, "return_arrival": 1},
        "NRUM": {"prep": 2, "launch": 2, "loan_arrival": 1, "repair_end": 1,
                  "return_arrival": 1, "home_done": 1},
        "NRW": {"arrival": 1, "loan_arrival": 1, "home_wait": 1, "return_arrival": 1},
        "NRRI": {"loan_arrival": 1, "repair_end": 1},
        "NRRO": {"loan_arrival": 1, "repair_end": 1},
        "NRRT": {"arrival": 1, "loan_arrival": 1, "repair_end": 1, "return_arrival": 1},
    }
    plan = {name: [] for name in ("SystemResults", "StockTotalResults", "ResourceResults",
                                  "ResourceResultsTotal", "ResultSummary", "ProblemDescription")}
    from_control = {c["name"] for c in native_json(PARENT_RUN / "report-raw.json")["report"]["tables"][2]["columns"]}
    for i in range(24):
        a, b = i / 2, (i + 1) / 2
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems", "STINT": a, "ETINT": b}
        # Native's forty fields are otherwise zero or nullable SYDT; validate topology separately.
        expected.update({field: (None if field == "SYDT" else 0) for field in from_control if field not in expected})
        expected.update({
            "NSYMA": 2 * overlap(t["prep"], t["arrival"], a, b) / .5,
            "NSYMO": 2 * overlap(t["launch"], t["arrival"], a, b) / .5,
            "NSYMP": 2 if i == 15 else 0,
            "NSYWR": (overlap(t["teach_wait"], t["teach_repair"], a, b) + overlap(t["home_wait"], t["home_pm"], a, b)) / .5,
            "NSYRP": overlap(t["teach_repair"], t["teach_done"], a, b) / .5,
            "NSYPM": overlap(t["home_pm"], t["home_done"], a, b) / .5,
            "NREPT": 1 if i == 18 else 0, "NPMT": 1 if i == int(t["home_done"] * 2) else 0,
            "NFAIL": 1 if i == 16 else 0, "NPMS": 1 if i == 18 else 0,
            "NPSTA": 2 if i == 15 else 0, "NPSUC": 2 if i == 16 else 0,
            "NSYDT": 1 if i in (17, 18) else 0,
            "SYDT": (t["teach_done"] - t["teach_wait"] if i == 17 else
                     t["home_done"] - t["home_wait"] if i == 18 else None),
        })
        expected["NSYUA"] = expected["NSYWR"] + expected["NSYRP"] + expected["NSYPM"]
        expected["NSYRY"] = 3 - expected["NSYMA"] - expected["NSYUA"]
        expected["NSYA"] = 3 - expected["NSYUA"]
        expected["FTMO"] = expected["NSYMO"] / 3
        expected["STACC"] = expected["NSYMO"]
        tolerances = {}
        for field, value in expected.items():
            if field in system_terms:
                tolerances[field] = bound(value, edges, uncertainty, system_terms[field], .5,
                                          .00012 if field == "FTMO" else .00035, a, b)
            elif field == "SYDT" and value is not None:
                terms = {"arrival": 1, "repair_end": 1} if i == 17 else {"home_wait": 1, "home_done": 1}
                tolerances[field] = bound(value, edges, uncertainty, terms, 1, .0001)
            else:
                tolerances[field] = 0.0
        if i == 18 and t["home_wait"] == 9 and t["home_pm"] >= 9.5:
            assert expected["NSYWR"] == 1 and tolerances["NSYWR"] == 0
            tolerances["NSYWR"] = 3e-6
        plan["SystemResults"].append((expected, tolerances))
        stock = {"STINT": a, "ETINT": b, "PNB": 1, "NBO": 0, "NBOU": None,
                 "ROS": None, "ROST": None, "WT": None, "WTT": None, "WTS": None,
                 "NDF": 0, "NDD": 0, "NDR": 0, "NDP": 0, "NLD": 0, "NWT": 0}
        plan["StockTotalResults"].append((stock, {field: 0 for field in stock}))
        transport = (overlap(t["outward_start"], t["outward_end"], a, b) +
                     overlap(t["return_start"], t["return_end"], a, b)) / .5
        loan = overlap(t["teach_repair"], t["teach_done"], a, b) / .5
        work = (2 * overlap(t["prep"], t["launch"], a, b) + loan * .5 +
                overlap(t["home_pm"], t["home_done"], a, b)) / .5
        wait = expected["NSYWR"]
        resource = {"RID": "Total over all Resources", "STID": "Total over all Stations",
                    "STINT": a, "ETINT": b, "NR": 3 - transport, "NRMO": 0, "NRMA": 0,
                    "NRUM": work, "NRLA": 0, "NRW": wait, "NRA": 3 - transport,
                    "NRN": 3, "NRF": 0, "NRRI": loan, "NRRT": transport, "NRRO": loan}
        resource_tol = {field: (bound(value, edges, uncertainty, resource_terms[field], .5, .00035, a, b)
                               if field in resource_terms else 0.0) for field, value in resource.items()}
        if i == 18 and t["home_wait"] == 9 and t["home_pm"] >= 9.5:
            assert resource["NRW"] == 1 and resource_tol["NRW"] == 0
            resource_tol["NRW"] = 3e-6
        plan["ResourceResults"].append((resource, resource_tol))
    transport_hours = (t["outward_end"] - t["outward_start"]) + (t["return_end"] - t["return_start"])
    work_hours = 2 * (t["launch"] - t["prep"]) + (t["teach_done"] - t["teach_repair"]) + (t["home_done"] - t["home_pm"])
    wait_hours = (t["teach_repair"] - t["teach_wait"]) + (t["home_pm"] - t["home_wait"])
    loan_hours = t["teach_done"] - t["teach_repair"]
    total = {"RID": "Total over all Resources", "STID": "Total over all Stations",
             "NR": 3 - transport_hours / 12, "NRMO": 0, "NRMA": 0, "NRUM": work_hours / 12,
             "NRLA": 0, "NRW": wait_hours / 12, "NRA": 3 - transport_hours / 12,
             "NRN": 3, "NRF": 0, "NRRI": loan_hours / 12, "NRRT": transport_hours / 12,
             "NRRO": loan_hours / 12}
    total_tol = {field: (bound(value, edges, uncertainty, resource_terms[field], 12, .00005)
                         if field in resource_terms else 0.0) for field, value in total.items()}
    plan["ResourceResultsTotal"].append((total, total_tol))
    summary = {"NREP": 1, "RTILW": 0, "RTIUP": 12, "MTMF": t["arrival"] - t["launch"],
               "RSMTMF": 0, "MSTF": 1, "RSMSTF": 0, "MSUF": 0, "RSMSUF": 0,
               "STMF": t["arrival"] - t["launch"], "RSSTMF": 0}
    summary_tol = {field: (bound(value, edges, uncertainty, {"launch": 1, "arrival": 1}, 1, .00005)
                           if field in ("MTMF", "STMF") else 0.0) for field, value in summary.items()}
    plan["ResultSummary"].append((summary, summary_tol))
    source_tables = {tab["name"]: tab for tab in source["model"]["tables"]}
    desc = source_tables["ProblemDescription"]["instances"][0]["rows"][0][0]
    plan["ProblemDescription"].append(({"PDESC": desc}, {"PDESC": 0.0}))
    # Later linked counterfactual repair/loan cycles extend the same complete
    # expected report. They are never selected by report values.
    for cycle in trace_data["later_cycles"]:
        for i in range(24):
            a, b = i / 2, (i + 1) / 2
            wait = sum(overlap(repair["wait_start"], repair["work_start"], a, b)
                       for repair in cycle["repairs"]) / .5
            work = sum(overlap(repair["work_start"], repair["work_end"], a, b)
                       for repair in cycle["repairs"]) / .5
            outward = overlap(cycle["out_start"], cycle["out_end"], a, b) / .5
            returning = overlap(cycle["return_start"], cycle["return_end"], a, b) / .5
            loan = overlap(cycle["out_end"], cycle["return_start"], a, b) / .5
            system, system_tol = plan["SystemResults"][i]
            resource, resource_tol = plan["ResourceResults"][i]
            for field, delta in {"NSYWR": wait, "NSYRP": work, "NSYUA": wait + work,
                                 "NSYRY": -wait - work, "NSYA": -wait - work}.items():
                system[field] += delta
            for field, delta in {"NR": -outward - returning, "NRA": -outward - returning,
                                 "NRUM": work, "NRW": wait, "NRRI": loan,
                                 "NRRO": loan, "NRRT": outward + returning}.items():
                resource[field] += delta
            def interval_uncertainty(first: float, last: float) -> float:
                return sum(printed_u(edge) / .5 for edge in (first, last) if a < edge < b)
            def uncertainty(*names: str) -> float:
                result = 0.0
                for name in names:
                    if name in ("wait", "work"):
                        for repair in cycle["repairs"]:
                            first = repair["wait_start"] if name == "wait" else repair["work_start"]
                            last = repair["work_start"] if name == "wait" else repair["work_end"]
                            result += interval_uncertainty(first, last)
                    else:
                        first, last = {"outward": (cycle["out_start"], cycle["out_end"]),
                                       "returning": (cycle["return_start"], cycle["return_end"]),
                                       "loan": (cycle["out_end"], cycle["return_start"])}[name]
                        result += interval_uncertainty(first, last)
                return result
            for field, pieces in {"NSYWR": ("wait",), "NSYRP": ("work",),
                                  "NSYUA": ("wait", "work"), "NSYRY": ("wait", "work"),
                                  "NSYA": ("wait", "work")}.items():
                system_tol[field] += uncertainty(*pieces)
            for field, pieces in {"NR": ("outward", "returning"),
                                  "NRA": ("outward", "returning"), "NRUM": ("work",),
                                  "NRW": ("wait",), "NRRI": ("loan",), "NRRO": ("loan",),
                                  "NRRT": ("outward", "returning")}.items():
                resource_tol[field] += uncertainty(*pieces)
            assert all(system_tol[k] <= .00035 for k in ("NSYWR", "NSYRP", "NSYUA", "NSYRY", "NSYA"))
            assert all(resource_tol[k] <= .00035 for k in ("NR", "NRA", "NRUM", "NRW", "NRRI", "NRRO", "NRRT"))
            for repair in cycle["repairs"]:
                if i == int(repair["wait_start"] * 2):
                    system["NFAIL"] += 1
                    prior_count = system["NSYDT"]
                    prior_total = (system["SYDT"] or 0) * prior_count
                    system["NSYDT"] += 1
                    downtime = repair["work_end"] - repair["wait_start"]
                    system["SYDT"] = (prior_total + downtime) / system["NSYDT"]
                    system_tol["SYDT"] = system_tol.get("SYDT", 0) + (
                        printed_u(repair["work_end"]) + printed_u(repair["wait_start"])) / system["NSYDT"]
                if i == int(repair["work_end"] * 2):
                    system["NREPT"] += 1
        total, total_tol = plan["ResourceResultsTotal"][0]
        for field in ("NR", "NRA", "NRUM", "NRW", "NRRI", "NRRO", "NRRT"):
            total[field] = sum(row[field] for row, _ in plan["ResourceResults"]) / 24
            total_tol[field] = (sum(tol[field] for _, tol in plan["ResourceResults"]) / 24 +
                                (5e-7 if not float(total[field]).is_integer() else 0))
            assert total_tol[field] <= .00005
    return plan


def compare_report(report: dict, reference_report: dict, plan: dict) -> int:
    actual_tables = report["report"]["tables"]
    reference_tables = reference_report["report"]["tables"]
    assert len(actual_tables) == len(reference_tables) == 6
    rows = {"ProblemDescription": 1, "ResultSummary": 1, "SystemResults": 24,
            "StockTotalResults": 24, "ResourceResults": 24, "ResourceResultsTotal": 1}
    widths = {"ProblemDescription": 1, "ResultSummary": 11, "SystemResults": 40,
              "StockTotalResults": 16, "ResourceResults": 16, "ResourceResultsTotal": 14}
    compared = 0
    for actual, reference in zip(actual_tables, reference_tables):
        name = actual["name"]
        assert name == reference["name"] and name in plan
        assert actual["columns"] == reference["columns"]
        assert len(actual["columns"]) == widths[name]
        assert len(actual["instances"]) == len(reference["instances"]) == 1
        instance, ref_instance = actual["instances"][0], reference["instances"][0]
        assert instance["instance_name"] == ref_instance["instance_name"]
        assert len(instance["rows"]) == len(plan[name]) == rows[name]
        fields = [column["name"] for column in actual["columns"]]
        for index, (row, (expected, tolerance)) in enumerate(zip(instance["rows"], plan[name])):
            assert len(row) == len(fields) and set(expected) == set(fields), (name, index)
            for field, value in zip(fields, row):
                assert equal(value, expected[field], tolerance[field]), (name, index, field, value,
                                                                           expected[field], tolerance[field])
                compared += 1
    assert compared == 1754
    return compared


def probe_faults(reference_report: dict, plan: dict, raw_log: str) -> int:
    report = deepcopy(reference_report)
    table_map = {tab["name"]: tab for tab in report["report"]["tables"]}
    tests = [("SystemResults", 0, "FTMO", 1e-9), ("SystemResults", 0, "NPMT", 1e-9),
             ("SystemResults", 0, "UNID", "OTHER"), ("StockTotalResults", 0, "NBOU", 0),
             ("StockTotalResults", 0, "PNB", 2), ("SystemResults", 18, "NSYWR", 1.00001),
             ("ResourceResults", 18, "NRW", .99999), ("SystemResults", 16, "FTMO", .6667)]
    for name, row_index, field in (("SystemResults", 19, "NSYPM"),
                                    ("ResourceResults", 19, "NRUM"),
                                    ("ResourceResults", 18, "NRRT"),
                                    ("ResourceResultsTotal", 0, "NRUM"),
                                    ("ResultSummary", 0, "MTMF"),
                                    ("SystemResults", 17, "SYDT")):
        value, tolerance = plan[name][row_index]
        tests.append((name, row_index, field, value[field] + tolerance[field] + 1e-5))
    for name, row_index, field, bad in tests:
        table = table_map[name]
        fields = [c["name"] for c in table["columns"]]
        value = table["instances"][0]["rows"][row_index][fields.index(field)]
        table["instances"][0]["rows"][row_index][fields.index(field)] = bad
        try:
            compare_report(report, reference_report, plan)
        except AssertionError:
            pass
        else:
            raise AssertionError(("mutant report accepted", name, row_index, field))
        table["instances"][0]["rows"][row_index][fields.index(field)] = value
    rejected_log_faults = 0
    for needle in (
        "return resource transport task 0 arrives with 1 resources",
        "subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> starts performing",
        "<P-MECH at <BASE-01,0>> deallocated from  maintenance task: 1",
    ):
        assert needle in raw_log
        mutant = raw_log.replace(needle, "MISSING EDGE", 1)
        try:
            trace(mutant)
        except AssertionError:
            rejected_log_faults += 1
        else:
            raise AssertionError(("mutant physical event accepted", needle))
    for needle, replacement in (
        ("return resource transport task 0 starts with 1 resources, transportation time: 0.5",
         "return resource transport task 0 starts with 1 resources, transportation time: 0.125"),
        ("aiming for  <P-MECH at <BASE-02,0>>", "aiming for  <P-MECH at <BASE-03,0>>"),
        ("return resource transport task 0 created", "return resource transport task 1 created"),
        ("return resource transport task 0 arrives with 1 resources",
         "return resource transport task 0 arrives with 2 resources"),
        ("subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> starts performing",
         "subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,1> starts performing"),
    ):
        assert needle in raw_log
        mutant = raw_log.replace(needle, replacement, 1)
        try:
            trace(mutant)
        except AssertionError:
            rejected_log_faults += 1
        else:
            raise AssertionError(("mutant physical event accepted", needle))
    booking = "Time: 8.96988  <P-MECH at <BASE-01,0>> allocated to maintenance task: 1  available now: 0"
    assert booking in raw_log
    try:
        trace(raw_log + "\n" + booking)
    except AssertionError:
        rejected_log_faults += 1
    else:
        raise AssertionError("double P-MECH booking accepted")
    assert compare_report(reference_report, reference_report, plan) == 1754
    assert rejected_log_faults == 9
    return len(tests) + rejected_log_faults


def verified_parent(contract: dict):
    parent_source = native_json(OLD / "ordinary-input.json")
    parent_report = native_json(PARENT_RUN / "report-raw.json")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8")
    parent_trace = trace(parent_log)
    assert abs(parent_trace["times"]["return_end"] - parent_trace["times"]["return_start"] - .5) < .0001
    parent_plan = report_plan(parent_source, parent_trace)
    assert compare_report(parent_report, parent_report, parent_plan) == 1754
    assert probe_faults(parent_report, parent_plan, parent_log) == 23
    return parent_source, parent_report, parent_trace


def validate_pair(parent_trace: dict, child_trace: dict):
    prefix = ("prep", "launch", "arrival", "teach_wait", "outward_start", "outward_end",
              "teach_repair", "teach_done", "home_wait", "return_start")
    for key in prefix:
        assert child_trace["times"][key] == parent_trace["times"][key], ("changed prefix", key)
    assert abs(parent_trace["times"]["return_end"] - parent_trace["times"]["return_start"] - .5) <= .0001
    assert abs(child_trace["times"]["return_end"] - child_trace["times"]["return_start"] - .125) <= .0001
    assert child_trace["times"]["return_end"] < parent_trace["times"]["return_end"]
    assert child_trace["times"]["return_end"] <= child_trace["times"]["home_pm"]
    assert child_trace["times"]["home_pm"] < child_trace["times"]["home_done"] <= 12
    if (abs(child_trace["times"]["return_start"] - 9.46988) <= .00002 and
            child_trace["times"]["home_pm"] == child_trace["times"]["return_end"]):
        assert abs(child_trace["times"]["return_end"] - 9.59488) <= .00002
        assert abs(child_trace["times"]["home_done"] - 9.84488) <= .00002


def synthetic_gate_check(parent_source: dict, parent_report: dict, parent_trace: dict) -> int:
    """Pure in-memory branch fixtures; synthetic data is never native evidence."""
    raw_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8")
    assert "Time: 9.96988" in raw_log and "Time: 10.2199" in raw_log
    simulated = raw_log.replace("Time: 9.96988", "Time: 9.59488").replace("Time: 10.2199", "Time: 9.84488")
    simulated = simulated.replace("return resource transport task 0 starts with 1 resources, transportation time: 0.5",
                                  "return resource transport task 0 starts with 1 resources, transportation time: 0.125")
    child_trace = trace(simulated)
    validate_pair(parent_trace, child_trace)
    mock_child = deepcopy(parent_source)
    tabs = {t["name"]: t for t in mock_child["model"]["tables"]}
    t = tabs["ResourceRemoteSupport"]
    cols = [c["name"] for c in t["columns"]]
    rows = [r for i in t["instances"] for r in i["rows"]]
    changed = [r for r in rows if (r[cols.index("RID")], r[cols.index("STID")],
                                  r[cols.index("RSTID")]) == ("P-MECH", "BASE-01", "BASE-02")]
    assert len(changed) == 1
    changed[0][cols.index("TTRSS")] = .125
    tabs["ProblemDescription"]["instances"][0]["rows"][0][0] = "shortage TTRSS 0.125 child test"
    source_child(parent_source, mock_child, native_json(PKG / "contract.json"))
    plan = report_plan(mock_child, child_trace)
    assert sum(len(expected) for rows in plan.values() for expected, _ in rows) == 1754
    assert abs(plan["SystemResults"][19][0]["NSYPM"] - .5) < 1e-8
    assert abs(plan["ResourceResults"][19][0]["NRRT"] - .18976) < 1e-8
    # Counterfactual later TEACH repair: same task/resource/station topology,
    # outside the fixed-seed native trace. The first HOME PM remains the only
    # HOME PM in this 12 h horizon. This probes full physical/report code paths.
    extra = """Time: 10.5 <TEACH-AIR-01,0> critical random failure added, now
Time: 10.5  system DIRP task 4 on <TEACH-AIR-01,0> started
Time: 10.5 <TEACH-AIR-01,0> nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>
Time: 10.5  direct repair subtask 5 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,0> requests resources
Time: 10.5  remote resource transport task 6 created: starting from  <P-MECH at <BASE-02,0>> aiming for  <P-MECH at <BASE-01,0>>
Time: 10.5 <TEACH-AIR-01,0> nbr resourcewait increased:
Time: 10.5  remote resource transport task 6 starts with 1 resources, transportation time: 0.25
Time: 10.75  remote resource transport task 6 arrives with 1 resources
Time: 10.75  <P-MECH at <BASE-01,0>> remote transport arrives: 1
Time: 10.75 <TEACH-AIR-01,0> nbr resourcewait decreased:
Time: 10.75  direct repair subtask 5 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,0> books resources
Time: 10.75  <P-MECH at <BASE-01,0>> allocated to maintenance task: 1  available now: 0
Time: 10.75  direct repair subtask 5 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours
Time: 11.25  direct repair subtask 5 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,0> completed
Time: 11.25  direct repair subtask 5 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,0> frees resources
Time: 11.25  <P-MECH at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1
Time: 11.25  return resource transport task 7 created: starting from  <P-MECH at <BASE-01,0>> aiming for  <P-MECH at <BASE-02,0>>
Time: 11.25  system DIRP task 4 on <TEACH-AIR-01,0> completed
Time: 11.25 <TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>
Time: 11.25  return resource transport task 7 starts with 1 resources, transportation time: 0.5
Time: 11.75  return resource transport task 7 arrives with 1 resources
Time: 11.75  <P-MECH at <BASE-02,0>> return transport arrives: 1
"""
    # Five-decimal synthetic event text has an explicit half-ULP below each
    # predeclared computed-fraction ceiling; these are not observed native times.
    extra = (extra.replace("10.5", "10.46988").replace("10.75", "10.71988")
                  .replace("11.25", "11.21988").replace("11.75", "11.71988"))
    marker = "Time: 12  resource shift 0 ended"
    assert simulated.count(marker) == 1
    with_extra = simulated.replace(marker, extra + marker)
    extra_trace = trace(with_extra)
    assert len(extra_trace["later_cycles"]) == 1
    assert extra_trace["later_cycles"][0]["return_declared"] == .5
    extra_plan = report_plan(mock_child, extra_trace)
    assert sum(len(expected) for rows in extra_plan.values() for expected, _ in rows) == 1754
    # A return at 11.71988 closes the resource state before h12, while the
    # [11.5,12) native report remains a fractional interval average.
    last_resource = extra_plan["ResourceResults"][-1][0]
    assert 0 < last_resource["NRRT"] < 1 and 2 < last_resource["NR"] < 3
    assert extra_trace["later_cycles"][-1]["return_end"] < 12
    fixture_report = deepcopy(parent_report)
    for table in fixture_report["report"]["tables"]:
        name = table["name"]
        fields = [column["name"] for column in table["columns"]]
        table["instances"][0]["rows"] = [[expected[field] for field in fields]
                                         for expected, _ in extra_plan[name]]
    assert compare_report(fixture_report, parent_report, extra_plan) == 1754
    # A separate counterfactual uses one additional loan for two sequential
    # repairs. It exercises the allowed immediately reused mechanic without
    # asserting that the fixed-seed native run can produce a second failure.
    first_repair = extra.split("Time: 11.21988  return resource transport task 7 created:")[0]
    first_repair = (first_repair.replace("10.46988", "9.86988")
                                .replace("10.71988", "10.11988")
                                .replace("11.21988", "10.61988"))
    second_repair = """Time: 10.61988  system DIRP task 4 on <TEACH-AIR-01,0> completed
Time: 10.61988 <TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>
Time: 10.61988  system DIRP task 5 on <TEACH-AIR-01,1> started
Time: 10.61988 <TEACH-AIR-01,1> nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>
Time: 10.61988 <TEACH-AIR-01,1> nbr resourcewait increased:
Time: 10.61988 <TEACH-AIR-01,1> nbr resourcewait decreased:
Time: 10.61988  direct repair subtask 6 seqno 1 within system DIRP task 5 on <TEACH-AIR-01,1> books resources
Time: 10.61988  <P-MECH at <BASE-01,0>> allocated to maintenance task: 1  available now: 0
Time: 10.61988  direct repair subtask 6 seqno 1 within system DIRP task 5 on <TEACH-AIR-01,1> starts performing, planned to last for 0.5 hours
Time: 11.11988  direct repair subtask 6 seqno 1 within system DIRP task 5 on <TEACH-AIR-01,1> completed
Time: 11.11988  direct repair subtask 6 seqno 1 within system DIRP task 5 on <TEACH-AIR-01,1> frees resources
Time: 11.11988  <P-MECH at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1
Time: 11.11988  system DIRP task 5 on <TEACH-AIR-01,1> completed
Time: 11.11988 <TEACH-AIR-01,1> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>
Time: 11.11988  return resource transport task 7 created: starting from  <P-MECH at <BASE-01,0>> aiming for  <P-MECH at <BASE-02,0>>
Time: 11.11988  return resource transport task 7 starts with 1 resources, transportation time: 0.5
Time: 11.61988  return resource transport task 7 arrives with 1 resources
Time: 11.61988  <P-MECH at <BASE-02,0>> return transport arrives: 1
"""
    with_two_repairs = simulated.replace(marker, first_repair + second_repair + marker)
    two_trace = trace(with_two_repairs)
    assert len(two_trace["later_cycles"]) == 1
    assert len(two_trace["later_cycles"][0]["repairs"]) == 2
    two_plan = report_plan(mock_child, two_trace)
    assert sum(len(expected) for rows in two_plan.values() for expected, _ in rows) == 1754
    assert 0 < two_plan["ResourceResults"][-1][0]["NRRT"] < 1
    rejected = 0
    for altered in (parent_trace, {"times": {**child_trace["times"], "teach_done": 9.47088}}):
        try:
            validate_pair(parent_trace, altered)
        except AssertionError:
            rejected += 1
        else:
            raise AssertionError("invalid paired branch accepted")
    mock_child_bad = deepcopy(mock_child)
    bad_tabs = {t["name"]: t for t in mock_child_bad["model"]["tables"]}
    bad_t = bad_tabs["ResourceRemoteSupport"]
    bad_cols = [c["name"] for c in bad_t["columns"]]
    for instance in bad_t["instances"]:
        for row in instance["rows"]:
            if (row[bad_cols.index("RID")], row[bad_cols.index("STID")],
                row[bad_cols.index("RSTID")]) == ("P-MECH", "BASE-01", "BASE-02"):
                row[bad_cols.index("TTRSS")] = .5
    try:
        source_child(parent_source, mock_child_bad, native_json(PKG / "contract.json"))
    except AssertionError:
        rejected += 1
    else:
        raise AssertionError("source without .125 TTRSS accepted")
    for bad in (with_extra.replace("return resource transport task 7 arrives with 1 resources",
                                   "return resource transport task 7 arrives with 2 resources"),
                with_extra.replace("<P-MECH at <BASE-02,0>> return transport arrives: 1\nTime: 12",
                                   "Time: 12"),
                with_extra.replace("return resource transport task 7 created:",
                                   "return resource transport task 8 created:")):
        try:
            trace(bad)
        except AssertionError:
            rejected += 1
        else:
            raise AssertionError("unlinked later-cycle fixture accepted")
    orphan = ("Time: 11.8  <P-MECH at <BASE-02,0>> allocated to maintenance task: 1  available now: 0\n"
              "Time: 11.8  <P-MECH at <BASE-02,0>> deallocated from  maintenance task: 1  available now: 1\n")
    try:
        trace(with_extra.replace(marker, orphan + marker))
    except AssertionError:
        rejected += 1
    else:
        raise AssertionError("balanced orphan mechanic booking accepted")
    wrong_second_book = with_two_repairs.replace(
        "direct repair subtask 6 seqno 1 within system DIRP task 5 on <TEACH-AIR-01,1> books resources",
        "direct repair subtask 6 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,1> books resources")
    assert wrong_second_book != with_two_repairs
    try:
        trace(wrong_second_book)
    except AssertionError:
        rejected += 1
    else:
        raise AssertionError("second repair wrong task booking accepted")
    bad_report = deepcopy(fixture_report)
    resource_table = next(table for table in bad_report["report"]["tables"] if table["name"] == "ResourceResults")
    nrtt_index = [column["name"] for column in resource_table["columns"]].index("NRRT")
    resource_table["instances"][0]["rows"][22][nrtt_index] += .01
    try:
        compare_report(bad_report, parent_report, extra_plan)
    except AssertionError:
        rejected += 1
    else:
        raise AssertionError("changed later-cycle report cell accepted")
    assert rejected == 9
    return rejected


def verified_child(contract: dict, parent_source: dict, parent_report: dict, parent_trace: dict) -> dict:
    assert CHILD_RUN.is_dir(), "new native child absent; fail closed"
    manifest_path = PKG / "prelaunch-manifest.json"
    approval_path = PKG / "review/independent-prelaunch-go.json"
    assert manifest_path.is_file() and approval_path.is_file(), "no frozen prelaunch approval"
    manifest = native_json(manifest_path)
    approval = native_json(approval_path)
    closure = native_json(CHILD_RUN / "closure.json")
    invocation = native_json(CHILD_RUN / "invocation.json")
    assert manifest["schema"] == "c09-var02-v107-prelaunch-manifest/v1"
    assert manifest["contract_sha256"] == CONTRACT_SHA and manifest["run_id"] == CHILD_RUN.name
    assert manifest["source_count"] == len(manifest["source_files"]) == 1726
    manifest_sha = seal(manifest_path.read_bytes())["sha256"]
    assert approval["schema"] == "c09-var02-v107-independent-prelaunch-go/v1"
    assert approval["decision"] == "GO_PRELAUNCH"
    assert approval["run_id"] == CHILD_RUN.name and approval["manifest_sha256"] == manifest_sha
    assert approval["contract_sha256"] == CONTRACT_SHA
    assert approval["independent_replay_sha256"] == seal(Path(__file__).read_bytes())["sha256"]
    assert approval["runner_sha256"] == seal((PKG / "run_native_ssh.ps1").read_bytes())["sha256"]
    assert approval["validator_sha256"] == seal((PKG / "validate_native_cli.py").read_bytes())["sha256"]
    assert approval["input_sha256"] == seal((PKG / "shortage-input.json").read_bytes())["sha256"]
    assert re.fullmatch(r"review[/\\]preflight-ssh0-\d{8}T\d{9}Z\.json",
                        approval["preflight_relative_path"])
    owned_review = PKG / "review"
    preflight_path = (PKG / approval["preflight_relative_path"]).resolve()
    for owned_part in (PKG, owned_review, preflight_path):
        assert not (owned_part.stat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    assert preflight_path.is_relative_to(owned_review.resolve())
    assert seal(preflight_path.read_bytes())["sha256"] == approval["preflight_sha256"]
    preflight = native_json(preflight_path)
    assert preflight["schema"] == "c09-var02-v107-ssh-preflight/v1"
    assert preflight["run_id"] == CHILD_RUN.name and preflight["run_dirs_absent"] is True
    assert type(preflight["ssh_session"]) is int and preflight["ssh_session"] == 0
    assert type(preflight["ps_major"]) is int and preflight["ps_major"] == 5
    assert type(preflight["ssh_ancestors"]) is list and "sshd.exe" in preflight["ssh_ancestors"]
    assert preflight["mutex_free"] is True and preflight["native_process_started"] is False
    assert type(preflight["wts_active_gui_count"]) is int and preflight["wts_active_gui_count"] == 1
    assert preflight["gui"] == {"pid": 13340, "session_id": 1, "start_unix_ms": 1790590196826, "responding": True}
    for key, expected in (("accepted_raw_seals", 130), ("accepted_closures", 10),
                          ("accepted_invocations", 10)):
        assert type(preflight[key]) is int and preflight[key] == expected
    assert preflight["manifest_sha256"] == manifest_sha
    pins = {item["key"]: item for item in manifest["source_files"]}
    assert len(pins) == len(manifest["source_files"])
    assert closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"]
    assert set(pins) == set(closure["source_hashes_before"])
    assert preflight["source_hashes"] == closure["source_hashes_before"]
    assert approval["source_map_sha256"] == preflight["source_map_sha256"]
    independent_source_map_sha = hashlib.sha256(json.dumps(
        preflight["source_hashes"], separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    assert independent_source_map_sha == preflight["source_map_sha256"]
    custody = native_json(ROOT_CONTEXT / "actual-ssh5-helper-test-custody.json")
    assert custody["raw_file_count"] == len(custody["raw"]) == 10
    assert custody["schema"] == "c09-var02-v107-actual-ssh5-helper-custody/v1"
    exact_pin(PKG / custody["receipt_owned_copy"], custody["receipt_identity"])
    if Path(custody["receipt_original"]).is_file():
        exact_pin(Path(custody["receipt_original"]), custody["receipt_identity"])
    helper_copies = {Path(record["original_path"]): record for record in custody["raw"]}
    assert len(helper_copies) == 10
    for record in helper_copies.values():
        exact_pin(PKG / record["owned_copy_path"], record)
        if Path(record["original_path"]).is_file():
            exact_pin(Path(record["original_path"]), record)
    for key, item in pins.items():
        original_path = Path(item["path"])
        # The mutable shared catalog is pinned by its byte-exact owned archive;
        # root tmp receipts have corresponding owned archives for later replay.
        if original_path.name == "publication-index-v1.json" and original_path.parent == PKG.parent:
            observed_path = PKG / "preserved-root-context/publication-index-at-base.json"
        elif original_path.parent.name == "tmp" and original_path.name in {
            Path(pin["path"]).name for pin in direct_contract_pins(contract)
            if Path(pin["path"]).parent.name == "tmp"
        }:
            observed_path = ROOT_CONTEXT / original_path.name
        elif key.startswith("helper_test_original_raw:"):
            assert original_path in helper_copies
            record = helper_copies[original_path]
            assert {name: item[name] for name in ("bytes", "sha256")} == {
                name: record[name] for name in ("bytes", "sha256")}
            observed_path = PKG / record["owned_copy_path"]
        else:
            observed_path = original_path
        exact_pin(observed_path, item)
        assert closure["source_hashes_before"][key] == item["sha256"]
    assert closure["schema"] == "c09-var02-v107-closure/v1"
    assert invocation["schema"] == "c09-var02-v107-invocation/v1"
    assert closure["manifest_sha256"] == manifest_sha
    assert closure["approval_sha256"] == seal(approval_path.read_bytes())["sha256"]
    assert closure["approved_preflight_sha256"] == approval["preflight_sha256"]
    assert closure["invocation_sha256"] == seal((CHILD_RUN / "invocation.json").read_bytes())["sha256"]
    assert closure["run_id"] == invocation["run_id"] == CHILD_RUN.name
    assert invocation["manifest_sha256"] == manifest_sha
    assert invocation["approval_sha256"] == closure["approval_sha256"]
    assert invocation["approved_preflight_sha256"] == approval["preflight_sha256"]
    assert Path(invocation["approved_preflight_path"]).resolve() == preflight_path
    assert invocation["independent_replay_sha256"] == approval["independent_replay_sha256"]
    assert invocation["runner_script_sha256"] == approval["runner_sha256"]
    assert invocation["input_sha256"] == approval["input_sha256"]
    assert invocation["contract_sha256"] == CONTRACT_SHA
    assert invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0
    assert invocation["gui"] == {"pid": 13340, "session_id": 1, "start_unix_ms": 1790590196826, "responding": True}
    assert "sshd.exe" in invocation["ssh_ancestors"]
    assert invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue"
    assert [x["name"] for x in invocation["planned_commands"]] == ["import", "export", "calc", "jsonreport"]
    assert len(closure["raw"]) == 23 and closure["error"] in (None, "")
    assert not (CHILD_RUN / "failure-seal.json").exists()
    for name, record in closure["raw"].items():
        exact_pin(CHILD_RUN / name, record)
    steps = native_json(CHILD_RUN / "steps.json")
    assert [s["name"] for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
    assert all(type(s["exit_code"]) is int and s["exit_code"] == 0 for s in steps)
    assert all(s["gui_preserved"] and s["status"] == "completed" for s in steps)
    assert all(type(s["child_session_id"]) is int and s["child_session_id"] == 0
               and type(s["child_pid"]) is int and s["child_pid"] > 0
               and s["capture_error"] in (None, "")
               and s["stdout_path"] and s["stderr_path"] for s in steps)
    for step in steps:
        for stream in ("stdout_path", "stderr_path"):
            stream_path = Path(step[stream]).resolve()
            assert stream_path.parent == CHILD_RUN.resolve()
            assert stream_path.name in closure["raw"]
    roundtrip_verdict = native_json(CHILD_RUN / "roundtrip-validation.json")
    assert roundtrip_verdict["schema"] == "c09-var02-v107-roundtrip/v1"
    assert roundtrip_verdict["passed"] is True and roundtrip_verdict["issues"] == []
    assert roundtrip_verdict["arm"] == "shortage"
    assert type(roundtrip_verdict["authored_row_tables"]) is int and roundtrip_verdict["authored_row_tables"] == 25
    assert roundtrip_verdict["source_sha256"] == approval["input_sha256"]
    assert roundtrip_verdict["export_sha256"] == seal((CHILD_RUN / "roundtrip-raw.json").read_bytes())["sha256"]
    author_verdict = native_json(CHILD_RUN / "author-validation.json")
    assert author_verdict["schema"] == "c09-var02-v107-author-validation/v1"
    assert author_verdict["passed"] is True and author_verdict["decision"] == "GO_BOUNDED_PROSPECTIVE_CHILD"
    assert author_verdict["run_id"] == CHILD_RUN.name
    assert all(type(author_verdict[name]) is int and author_verdict[name] == value
               for name, value in (("child_report_cells", 1754), ("control_report_cells", 1754),
                                   ("new_native_runs", 1)))
    input_model = native_json(CHILD_RUN / "input.json")
    source_child(parent_source, input_model, contract)
    roundtrip(input_model, native_json(CHILD_RUN / "roundtrip-raw.json"))
    run_log = (CHILD_RUN / "run.log").read_text(encoding="utf-8")
    assert "Input conversion completed. Errors: 0, Warnings: 3, Notes: 1" in run_log
    assert run_log.count("(warning #108)") == 1 and run_log.count("(warning #126)") == 2
    assert run_log.count("(notice #292)") == 1
    child_log = (CHILD_RUN / "model.log").read_text(encoding="utf-8")
    child_trace = trace(child_log)
    validate_pair(parent_trace, child_trace)
    child_report = native_json(CHILD_RUN / "report-raw.json")
    child_plan = report_plan(input_model, child_trace)
    assert compare_report(child_report, parent_report, child_plan) == 1754
    return {"child_source_sha256": seal((CHILD_RUN / "input.json").read_bytes())["sha256"],
            "child_closure_sha256": seal((CHILD_RUN / "closure.json").read_bytes())["sha256"],
            "child_raw_seals": 23, "report_cells": 1754,
            "return_duration": child_trace["times"]["return_end"] - child_trace["times"]["return_start"]}


def main():
    assert sys.argv[1:] in ([], ["--self-check"]), "usage: independent_replay.py [--self-check]"
    contract = verify_parent_index()
    parent_source, parent_report, parent_trace = verified_parent(contract)
    synthetic_rejections = synthetic_gate_check(parent_source, parent_report, parent_trace)
    result = {"mode": "accepted-control-only" if sys.argv[1:] else "prospective-child",
              "contract_sha256": CONTRACT_SHA, "accepted_parent_cells": 1754,
              "accepted_parent_raw_seals": 130, "parent_mutation_rejections": 23,
              "synthetic_branch_rejections": synthetic_rejections,
              "original_prospective_pair": "NO_GO", "v106_child": "NO_GO_RUN"}
    if not sys.argv[1:]:
        result.update(verified_child(contract, parent_source, parent_report, parent_trace))
        result["decision"] = "GO_BOUNDED_REPLAY_ONLY"
    else:
        assert not CHILD_RUN.exists(), "self-check is only for prelaunch child absence"
        result["decision"] = "READY_FOR_FROZEN_CHILD_REVIEW_NOT_APPROVAL"
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

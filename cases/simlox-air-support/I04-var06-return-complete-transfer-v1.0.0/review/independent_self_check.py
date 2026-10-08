"""Private semantic clones beneath the independent reader's original-byte gate."""

from __future__ import annotations

import json
from pathlib import Path

import independent_classifier as reader


def replace_once(data: bytes, old: bytes, new: bytes) -> bytes:
    assert data.count(old) == 1, old
    return data.replace(old, new, 1)


def move_before(data: bytes, needle: bytes, anchor: bytes) -> bytes:
    lines = data.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if needle in line]
    anchors = [i for i, line in enumerate(lines) if anchor in line]
    assert len(matches) == len(anchors) == 1
    item = lines.pop(matches[0])
    new_anchor = next(i for i, line in enumerate(lines) if anchor in line)
    lines.insert(new_anchor, item)
    return b"".join(lines)


def assert_reject(name: str, fn, data: bytes):
    try:
        fn(data)
    except (AssertionError, ValueError, UnicodeError, KeyError, IndexError):
        return name
    raise AssertionError(f"semantic mutant accepted: {name}")


def report_mutant(data: bytes, alter):
    marker = b"         },\r\n      ]"
    assert data.count(marker) == 1
    obj = json.loads(data.replace(marker, b"         }\r\n      ]"))
    alter(obj["report"]["tables"])
    # The parser's one native trailing comma remains present; the changed JSON
    # is private memory only and never written to the accepted parent.
    rendered = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    assert rendered.endswith(b"]}}")
    return rendered[:-3] + b",]}}"


def main() -> None:
    positive = reader.sealed()
    assert positive["full_lines"] == 117 and positive["timed_lines"] == 103
    log = (reader.SCRATCH / "raw/between.log").read_bytes()
    report = (reader.SCRATCH / "raw/between-report-raw.json").read_bytes()
    marker = b"         },\r\n      ]"
    assert report.count(marker) == 1
    pristine_tables = json.loads(report.replace(marker, b"         }\r\n      ]"))["report"]["tables"]
    assert reader.check_selected_tables(pristine_tables)["checked_values"] == 12
    checks = []
    def no(name, data):
        checks.append(assert_reject(name, reader.parse_semantic, data))

    # All clones intentionally bypass the outer original SHA check. Every
    # changed event still reaches the independent grammar/order/state logic.
    no("transfer before return", move_before(log,
        b"system transfered out: <TEACH-AIR-01,0>",
        b"Time: 10 <TEACH-AIR-01,0> turnround ended, mission: <BASIC-MISSION,TEACH-GROUP,0,0,0>"))
    no("transfer before ready decrease", move_before(log,
        b"system transfered out: <TEACH-AIR-01,0>",
        b"Time: 10 <TEACH-AIR-01,0> nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>"))
    no("wrong departure ID", replace_once(log,
        b"system transfered out: <TEACH-AIR-01,0>",
        b"system transfered out: <TEACH-AIR-01,1>"))
    no("wrong departure unit", replace_once(log,
        b"<TEACH-UNIT at <BASE-01,0>> system transfered out:",
        b"<TEACH-UNIT-2 at <BASE-02,0>> system transfered out:"))
    no("early departure time", replace_once(log,
        b"Time: 10 <TEACH-UNIT at <BASE-01,0>> system transfered out:",
        b"Time: 8.5 <TEACH-UNIT at <BASE-01,0>> system transfered out:"))
    departure = next(line for line in log.splitlines(keepends=True) if b"system transfered out:" in line)
    no("duplicate departure", log.replace(departure, departure * 2, 1))
    no("missing departure", log.replace(departure, b"", 1))
    no("wrong arrival ID", replace_once(log,
        b"system transfered in: <TEACH-AIR-01,0>",
        b"system transfered in: <TEACH-AIR-01,1>"))
    no("wrong arrival unit", replace_once(log,
        b"<TEACH-UNIT-2 at <BASE-02,0>> system transfered in:",
        b"<TEACH-UNIT at <BASE-01,0>> system transfered in:"))
    no("mistimed arrival", replace_once(log,
        b"Time: 10.5 <TEACH-UNIT-2 at <BASE-02,0>> system transfered in:",
        b"Time: 10 <TEACH-UNIT-2 at <BASE-02,0>> system transfered in:"))
    arrival = next(line for line in log.splitlines(keepends=True) if b"system transfered in:" in line)
    no("missing arrival", log.replace(arrival, b"", 1))
    no("duplicate arrival", log.replace(arrival, arrival * 2, 1))
    no("source ready wrong unit", replace_once(log,
        b"Time: 10 <TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>",
        b"Time: 10 <TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT-2 at <BASE-02,0>>"))
    no("target ready wrong ID", replace_once(log,
        b"Time: 10.5 <TEACH-AIR-01,0> nbr ready increased",
        b"Time: 10.5 <TEACH-AIR-01,1> nbr ready increased"))
    no("wrong station descriptor", replace_once(log,
        b"Time: 10 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>",
        b"Time: 10 <TEACH-AIR-01,BASE-02,0> System arrives <TEACH-AIR-01,0>"))
    no("source ready count", replace_once(log,
        b"Time: 10 <TEACH-UNIT-2 at <BASE-02,0>> systems ready: 1 :<TEACH-AIR-01,1>",
        b"Time: 10 <TEACH-UNIT-2 at <BASE-02,0>> systems ready: 2 :<TEACH-AIR-01,1>"))
    no("target ready count", replace_once(log,
        b"Time: 10.5 <TEACH-UNIT-2 at <BASE-02,0>> systems ready: 2",
        b"Time: 10.5 <TEACH-UNIT-2 at <BASE-02,0>> systems ready: 1"))
    no("mission identity", replace_once(log,
        b"Time: 19 <BASIC-MISSION,TEACH-GROUP,0,0,1> mission created",
        b"Time: 19 <BASIC-MISSION,TEACH-GROUP,0,0,0> mission created"))
    no("mission completion order", move_before(log,
        b"mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>",
        b"Time: 10 <BASIC-MISSION,TEACH-GROUP,0,0,0> mission success:"))
    no("preparation order", move_before(log,
        b"Time: 7 <TEACH-AIR-01,0> preparation ended, mission: <BASIC-MISSION,TEACH-GROUP,0,0,0>",
        b"Time: 7 <TEACH-AIR-01,0> preparation started, mission: <BASIC-MISSION,TEACH-GROUP,0,0,0>"))
    no("turnround after arrival", move_before(log,
        b"Time: 10 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>, mission success",
        b"Time: 10 <TEACH-AIR-01,0> turnround ended, mission: <BASIC-MISSION,TEACH-GROUP,0,0,0>"))
    no("untimed continuation moved", log.replace(
        b" no failures \r\n no PMTasks\r\n",
        b" no PMTasks\r\n no failures \r\n", 1))
    no("unknown timed line", replace_once(log,
        b"Time: 24  Start of day no 1",
        b"Time: 24  mysterious transfer priority"))
    no("extra timed line", log + b"Time: 24  Start of day no 1\r\n")
    no("wrong aircraft in allocation", replace_once(log,
        b"Time: 7 <BASIC-MISSION,TEACH-GROUP,0,0,0> mission allocates system: <TEACH-AIR-01,0>",
        b"Time: 7 <BASIC-MISSION,TEACH-GROUP,0,0,0> mission allocates system: <TEACH-AIR-01,1>"))
    no("target allocation before arrival", move_before(log,
        b"Time: 19 <BASIC-MISSION,TEACH-GROUP,0,0,1> mission allocates system: <TEACH-AIR-01,0>",
        b"Time: 10.5 <TEACH-UNIT-2 at <BASE-02,0>> system transfered in:"))

    def rn(name, mutate):
        checks.append(assert_reject(name, reader.check_selected_tables, report_mutant(report, mutate)))
    def row(tables, index):
        return tables[2]["instances"][0]["rows"][index]
    rn("row20 ready bool", lambda t: row(t, 20).__setitem__(4, True))
    rn("row21 available bool", lambda t: row(t, 21).__setitem__(13, True))
    rn("row20 time", lambda t: row(t, 20).__setitem__(2, 10.5))
    rn("row21 time", lambda t: row(t, 21).__setitem__(3, 11.5))
    rn("row20 ready count", lambda t: row(t, 20).__setitem__(4, 2))
    rn("row21 available count", lambda t: row(t, 21).__setitem__(13, 1))
    rn("row21 maintenance", lambda t: row(t, 21).__setitem__(5, 1))
    rn("row20 null count", lambda t: row(t, 20).__setitem__(4, None))
    rn("row21 identity", lambda t: row(t, 21).__setitem__(0, "TEACH-UNIT"))
    rn("wrong report instance", lambda t: t[2]["instances"][0].__setitem__("instance_name", "0.00;11.00"))
    rn("wrong column name", lambda t: t[2]["columns"][4].__setitem__("name", "NSYWR"))
    assert len(checks) == 37 and len(set(checks)) == len(checks)
    print(json.dumps({"decision": "PASS_INDEPENDENT_PRIVATE_NEGATIVES", "rejected": len(checks), "sealed_positive": True, "native_calls": 0, "accepted_checker_calls": 0}, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()

"""Read-only, source-bound C02.var01 native report and physical-log verdict."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse, sha
from report_oracle import check_report

HERE = Path(__file__).resolve().parent
PARENT_RUN = Path(r"C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support\C02-joint-resources-v1.0.2\runs\c02-v102-single-both-ssh-20260929-02")
PARENT_REPORT_SHA = "f0879b5c66c95568bf13bc942f59eeaa34c83f8842d02a76e59c0eb3fc5cc732"
PARENT_LOG_SHA = "f5d59ca8277d006c312405837b92b2d06f944364abd785697d287146235787bb"
INPUT_SHA = "bab34055ae4f2ee3efac4fa9cb8f545ba2355daad0751a7d5508947f17d3cec2"
SCHEMA = "c02-var01-v101-behavior/v1"
TIME = re.compile(r"^Time:\s+([0-9.]+)\s+(.*)$")
SEQ = "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0>"
MISSION = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"


def records(log: str) -> list[tuple[float, str]]:
    result: list[tuple[float, str]] = []
    for line in log.splitlines():
        m = TIME.match(line)
        if m:
            result.append((float(m.group(1)), m.group(2)))
        elif result and line.startswith((" ", "\t")):
            t, body = result[-1]
            result[-1] = (t, body + "\n" + line.strip())
    return result


def hits(events: list[tuple[float, str]], text: str) -> list[tuple[float, str]]:
    return [(t, body) for t, body in events if text in body]


def only(events: list[tuple[float, str]], text: str, when: float | None = None) -> float:
    found = hits(events, text)
    if when is not None:
        found = [(t, body) for t, body in found if t == when]
    assert len(found) == 1, (text, found)
    if when is not None:
        assert found[0][0] == when, (text, found[0][0])
    return found[0][0]


def position(events: list[tuple[float, str]], text: str, when: float) -> int:
    matches = [i for i, (t, body) in enumerate(events) if t == when and text in body]
    assert len(matches) == 1, (text, when, matches)
    return matches[0]


def converter(run_log: str) -> int:
    text = run_log
    assert re.search(r"Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0", text)
    warnings = re.findall(r"Form:\s*(\w+)\s*\nrec\s*(\d+):\s*\(warning\s*#(\d+)\)", text)
    assert warnings == [("Control", "1", "108"), ("System", "1", "126")], warnings
    assert re.findall(r"\bwarning\s*#(\d+)", text) == ["108", "126"]
    assert not re.findall(r"\bnotice\s*#(\d+)", text)
    assert "Starting simulation" in text and "Saving results" in text
    return 3


def event_gate(events: list[tuple[float, str]], control: bool) -> float | None:
    only(events, "<TEACH-UNIT> mission ordered: BASIC-MISSION", 7)
    only(events, MISSION + " mission created:", 7)
    only(events, MISSION + " mission activated, systems requested: 1", 7)
    only(events, MISSION + " mission allocates system: <TEACH-AIR-01,0>", 7)
    only(events, "<TEACH-AIR-01,0> preparation started, mission:", 7)
    only(events, SEQ + " requests resources", 7)
    test_time = only(events, SEQ + " resource availability test", 7)
    test = [body for t, body in events if t == test_time and SEQ + " resource availability test" in body][0]
    crew = "Availability test on  <P-CREW at <BASE-01,0>> request for: 1 "
    device = "Availability test on  <E-GSE at <BASE-01,0>> request for: 1 "
    assert test.count(crew) == test.count(device) == 1
    assert test.index(crew) < test.index(device)
    assert (crew + ("OK" if control else "failed")) in test
    assert (device + "OK") in test
    assert not hits(events, "Availability test on  <P-OTHER")
    assert len(hits(events, "mission ordered:")) == 1
    assert len(hits(events, "mission created:")) == 1
    assert not any("Stock" in body or "Replacement item" in body for _, body in events)
    sequence = ["<TEACH-UNIT> mission ordered: BASIC-MISSION", MISSION + " mission created:",
                MISSION + " mission activated, systems requested: 1",
                MISSION + " mission allocates system: <TEACH-AIR-01,0>",
                "<TEACH-AIR-01,0> preparation started, mission:",
                SEQ + " requests resources", SEQ + " resource availability test"]
    assert [position(events, item, 7) for item in sequence] == sorted(position(events, item, 7) for item in sequence)
    if control:
        only(events, SEQ + " books resources", 7)
        for rid in ("P-CREW", "E-GSE"):
            only(events, f"<{rid} at <BASE-01,0>> allocated to maintenance task: 1", 7)
            only(events, f"<{rid} at <BASE-01,0>> deallocated from  maintenance task: 1", 7.5)
        only(events, SEQ + " starts performing, planned to last for 0.5 hours", 7)
        only(events, SEQ + " completed", 7.5)
        only(events, MISSION + " mission starting, duration: 2", 8)
        only(events, MISSION + " mission success:", 10)
        only(events, MISSION + " mission completed:", 10)
        sequence += [SEQ + " books resources", "<P-CREW at <BASE-01,0>> allocated to maintenance task: 1",
                     "<E-GSE at <BASE-01,0>> allocated to maintenance task: 1",
                     SEQ + " starts performing, planned to last for 0.5 hours"]
        assert [position(events, item, 7) for item in sequence] == sorted(position(events, item, 7) for item in sequence)
        assert position(events, SEQ + " completed", 7.5) < position(events, SEQ + " frees resources", 7.5)
        assert position(events, SEQ + " frees resources", 7.5) < position(events, "<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1", 7.5)
        assert not hits(events, "mission cancelled:")
        return None
    assert not hits(events, "books resources")
    assert not hits(events, "allocated to maintenance task:")
    assert not hits(events, "deallocated from  maintenance task:")
    assert not hits(events, "starts performing")
    assert not hits(events, SEQ + " completed")
    assert not hits(events, "mission starting")
    assert not hits(events, "mission success:")
    assert not hits(events, "mission completed:")
    cancel = only(events, MISSION + " mission cancelled:")
    assert 7 < cancel <= 8 + 1 / 3
    only(events, SEQ + " resource waiting stopped", cancel)
    only(events, "<TEACH-AIR-01,0> preparation ended, mission:", cancel)
    only(events, "<TEACH-AIR-01,0> nbr ready increased at unit:", cancel)
    only(events, "System arrives <TEACH-AIR-01,0>", cancel)
    terminal_sequence = [MISSION + " mission cancelled:", SEQ + " resource waiting stopped",
                         "<TEACH-AIR-01,0> preparation ended, mission:",
                         "System arrives <TEACH-AIR-01,0>",
                         "<TEACH-AIR-01,0> nbr ready increased at unit:"]
    assert [position(events, item, cancel) for item in terminal_sequence] == sorted(position(events, item, cancel) for item in terminal_sequence)
    assert max(t for t, _ in events) <= 36
    return cancel


def check_parent() -> dict:
    assert sha(PARENT_RUN / "report-raw.json") == PARENT_REPORT_SHA
    assert sha(PARENT_RUN / "model.log") == PARENT_LOG_SHA
    events = records((PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace"))
    assert event_gate(events, True) is None
    converter((PARENT_RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace"))
    return {"cells": check_report(parse(PARENT_RUN / "report-raw.json"), True, None), "event_records": len(events)}


def check_child(run: Path) -> dict:
    assert sha(run / "input.json") == INPUT_SHA
    text = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    events = records(text)
    cancel = event_gate(events, False)
    printed = re.findall(r"^Time:\s+([0-9.]+)\s+" + re.escape(MISSION) + r" mission cancelled:", text, re.M)
    assert len(printed) == 1 and float(printed[0]) == cancel
    converter((run / "run.log").read_text(encoding="utf-8-sig", errors="replace"))
    cells = check_report(parse(run / "report-raw.json"), False, cancel, printed[0])
    return {"cells": cells, "event_records": len(events),
            "cancellation_hour_printed": cancel, "cancellation_token": printed[0]}


def validate(run: Path) -> dict:
    parent = check_parent()
    child = check_child(run)
    return {"schema": SCHEMA, "passed": True, "run_id": run.name,
            "input_sha256": INPUT_SHA, "parent": parent, "child": child,
            "report_cell_checks": parent["cells"] + child["cells"]}


if __name__ == "__main__":
    try:
        result = validate(Path(sys.argv[1]))
    except Exception as exc:
        result = {"schema": SCHEMA, "passed": False,
                  "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, separators=(",", ":")))
    sys.exit(0 if result["passed"] else 1)

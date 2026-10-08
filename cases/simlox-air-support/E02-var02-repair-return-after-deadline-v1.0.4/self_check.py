"""Private under-hash E02.var02 oracle mutations; no native or parent checker calls."""

from __future__ import annotations

import copy
import json
from typing import Callable

from check_roundtrip import source_oracles
from event_ledger import semantic
from model_common import HERE, PATTERN_PIN, REPORT_PIN, INPUT_PIN, compare_tables, exact, strict_json


def rejected(action: Callable[[], object], label: str) -> None:
    try:
        action()
    except (AssertionError, ValueError, KeyError, TypeError, UnicodeError):
        return
    raise AssertionError(f"private clone was accepted: {label}")


def run() -> dict[str, object]:
    assert source_oracles() == {"authored": 274, "exported": 369,
                                 "delta": "ItemRepair[TEACH-LRU-01,BASE-01].DIRPT 1.0 to 10.75"}
    patterns = strict_json(exact(HERE / "preserved-oracle/log-patterns.json", PATTERN_PIN))
    template = (HERE / "preserved-oracle/expected-log-template.bin").read_bytes()
    assert template.count(b"{{FINITE_GT34}}") == 1
    positive = template.replace(b"{{FINITE_GT34}}", b"1e+010")
    assert semantic(positive, patterns)["timed_lines"] == 99
    log_cases = {
        "second-cancellation-time": (b"Time: 20.3333 " , b"Time: 20.5000 "),
        "wrong-aircraft-id": (b"System ready <TEACH-AIR-01,0>", b"System ready <TEACH-AIR-01,1>"),
        "missing-repair-completion": (b"Finished repair of item", b"Repair remains pending "),
        "wrong-owner-station": (b"<TEACH-LRU-01,0,BASE-01,0>", b"<TEACH-LRU-01,0,BASE-02,0>"),
        "third-mission-failure": (b"mission success: ", b"mission failed:  "),
        "premature-random-failure": (b"1e+010", b"33"),
        "bounded-marker-at-34": (b"Time: 32 <TEACH-AIR-01,0> Next random failure will occur 1e+010",
                                 b"Time: 32 <TEACH-AIR-01,0> Next random failure will occur 34"),
    }
    count = 0
    for label, (old, new) in log_cases.items():
        assert old in positive and old != new
        clone = positive.replace(old, new, 1)
        assert clone != positive
        rejected(lambda c=clone: semantic(c, patterns), label)
        count += 1
    lines = positive.split(b"\r\n")
    assert len(lines) == 124
    swapped = lines.copy(); swapped[65], swapped[66] = swapped[66], swapped[65]
    rejected(lambda: semantic(b"\r\n".join(swapped), patterns), "same-hour-mission-order")
    count += 1
    missing_continuation = lines.copy(); missing_continuation.pop(68)
    rejected(lambda: semantic(b"\r\n".join(missing_continuation), patterns), "missing-cancellation-continuation")
    count += 1
    reordered_continuation = lines.copy(); reordered_continuation[68], reordered_continuation[69] = reordered_continuation[69], reordered_continuation[68]
    rejected(lambda: semantic(b"\r\n".join(reordered_continuation), patterns), "reordered-cancellation-continuation")
    count += 1
    extra_continuation = lines.copy(); extra_continuation.insert(72, b" Systems in assign buffer: ")
    rejected(lambda: semantic(b"\r\n".join(extra_continuation), patterns), "extra-cancellation-continuation")
    count += 1
    rejected(lambda: semantic(positive.replace(b"\r\n", b"\n"), patterns), "LF-only")
    count += 1
    rejected(lambda: semantic(positive + b"Time: 35 extra\r\n", patterns), "extra-event")
    count += 1
    expected = strict_json(exact(HERE / "preserved-oracle/expected-report.json", REPORT_PIN))
    tables = expected["report"]["tables"]
    assert compare_tables(tables, copy.deepcopy(tables), tolerance=1e-5) == 4044
    mutations = [
        (1, 0, 0, 0, True, "summary-int-bool"),
        (2, 0, 20, 23, False, "system-double-bool"),
        (2, 0, 20, 36, None, "system-counter-null"),
        (3, 0, 20, 6, "10.6667", "stock-wait-string"),
        (3, 0, 20, 6, 999.0, "stock-wait-number"),
        (3, 0, 20, 4, 0.0, "stock-ros-fraction"),
        (2, 0, 42, 23, 0.0, "repair-completion-count"),
        (2, 0, 41, 23, 1.0, "wrong-prior-repair-bin"),
    ]
    for table, instance, row, cell, value, label in mutations:
        clone = copy.deepcopy(tables)
        old = clone[table]["instances"][instance]["rows"][row][cell]
        assert type(old) is not type(value) or old != value
        clone[table]["instances"][instance]["rows"][row][cell] = value
        rejected(lambda c=clone: compare_tables(tables, c, tolerance=1e-5), label)
        count += 1
    for label, mutate in (
        ("extra-report-column-key", lambda x: x[2]["columns"][0].update(extra=1)),
        ("missing-report-column", lambda x: x[2]["columns"].pop()),
        ("row-list-to-dict", lambda x: x[1]["instances"][0]["rows"].__setitem__(0, {0: 1})),
        ("rows-list-to-dict", lambda x: x[1]["instances"][0].__setitem__("rows", {0: [1]})),
    ):
        clone = copy.deepcopy(tables); mutate(clone)
        rejected(lambda c=clone: compare_tables(tables, c), label)
        count += 1
    authored = strict_json(exact(HERE / "native-input.json", INPUT_PIN))["model"]["tables"]
    for label, edit in (
        ("input-DIRPT-bool", lambda row: row.__setitem__(2, True)),
        ("input-DIRPT-wrong", lambda row: row.__setitem__(2, 10.0)),
        ("input-IID-wrong", lambda row: row.__setitem__(0, "TEACH-LRU-02")),
        ("input-STID-wrong", lambda row: row.__setitem__(1, "BASE-02")),
    ):
        clone = copy.deepcopy(authored)
        item = next(t for t in clone if t["name"] == "ItemRepair")
        row = item["instances"][0]["rows"][0]
        edit(row)
        rejected(lambda c=clone: compare_tables(authored, c), label)
        count += 1
    return {"schema": "e02-var02-private-negative-self-check/v104", "passed": True,
            "meaningful_rejections": count, "positive_log": "123/99",
            "positive_report_cells": 4044, "native_calls": 0, "accepted_checker_calls": 0}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))

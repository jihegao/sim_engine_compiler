"""Read-only semantic probes against the author replay's production gates."""

from __future__ import annotations

import copy
import json
from dataclasses import replace

import replay as r


def rejected(label, action):
    try:
        action()
    except (AssertionError, StopIteration, KeyError, ValueError):
        return label
    raise AssertionError(f"mutation escaped production gate: {label}")


def run():
    baseline = r.replay()  # Seals and all 48,684 cells precede in-memory probes.
    rejected_labels = []
    arm = r.CONTRACT["accepted_parents"][0]
    native = next(x for x in arm["runs"] if x["role"] == "native" and x["contrast"] == "on")
    path = r.repo_path(native["local_run_directory"])
    records = r.events(path / "model.log")
    source = r.source_fields(r.input_tables(path / "input.json"))
    physical = r.physical_gate(records, "current_stock")
    r.enrich_physical(records, physical, "current_stock")
    mission = r.mission_gate(records, source)
    report = r.parse_native(path / "report-raw.json")
    expected = r.expected_report("current_stock", source, physical, mission, None)

    def report_change(table, row, column, value):
        changed = copy.deepcopy(report)
        t = next(t for t in changed["report"]["tables"] if t["name"] == table)
        index = r.COLS[table].index(column)
        t["instances"][0]["rows"][row][index] = value
        return lambda: r.compare_report(changed, expected, None)

    rejected_labels.append(rejected("whole-bin zero", report_change("SystemResults", 0, "NSYMO", 1e-9)))
    rejected_labels.append(rejected("whole-bin count", report_change("SystemResults", 0, "NSYRY", 0.999999999)))
    rejected_labels.append(rejected("null identity", report_change("SystemResults", 0, "SYDT", 0)))
    rejected_labels.append(rejected("source description", report_change("ProblemDescription", 0, "PDESC", "tampered")))
    bad = copy.deepcopy(report)
    bad["report"]["tables"][2]["instances"][0]["instance_name"] = ""
    rejected_labels.append(rejected("native instance metadata", lambda: r.compare_report(bad, expected, None)))
    bad = copy.deepcopy(report)
    bad["report"]["tables"][2]["columns"][0]["name"] = "wrong"
    rejected_labels.append(rejected("column metadata", lambda: r.compare_report(bad, expected, None)))

    def altered_text(old, new):
        changed = [replace(e, text=e.text.replace(old, new)) for e in records]
        return lambda: r.physical_gate(changed, "current_stock")

    rejected_labels.append(rejected("peer physical item identity", altered_text(
        "Take replacement item <TEACH-LRU-01,0,1>", "Take replacement item <TEACH-LRU-01,0,9>")))
    rejected_labels.append(rejected("transport destination", altered_text(
        "transport task 0 created from <BASE-02,0> to <BASE-01,0>",
        "transport task 0 created from <BASE-02,0> to <DEPOT-01,0>")))
    rejected_labels.append(rejected("transport quantity", altered_text(
        "transport task 0 starts with 1 items/systems", "transport task 0 starts with 2 items/systems")))
    rejected_labels.append(rejected("transport request item", altered_text(
        "transport request <<TEACH-LRU-01,0,1>", "transport request <<TEACH-LRU-01,0,9>")))

    station_run = next(x for x in arm["runs"] if x["role"] == "station_report" and
                       x["contrast"] == "on" and x["station"] == "base02")
    station_report = r.parse_native(r.repo_path(station_run["local_run_directory"]) / "item-report-raw.json")
    station_expected = r.expected_report("current_stock", source, physical, mission, "BASE-02")
    changed = copy.deepcopy(station_report)
    item = next(t for t in changed["report"]["tables"] if t["name"] == "ItemResults")
    item["instances"][0]["rows"][20][r.COLS["ItemResults"].index("WTS")] = 0
    rejected_labels.append(rejected("no-wait WTS null convention",
                                    lambda: r.compare_report(changed, station_expected, "BASE-02")))
    changed = copy.deepcopy(station_report)
    item = next(t for t in changed["report"]["tables"] if t["name"] == "ItemResults")
    item["instances"][0]["rows"][20][r.COLS["ItemResults"].index("ROS")] = None
    rejected_labels.append(rejected("demand with immediate service ROS zero",
                                    lambda: r.compare_report(changed, station_expected, "BASE-02")))

    current = r.repo_path(r.CONTRACT["source_comparison"]["current_input"]["path"])
    future = r.repo_path(r.CONTRACT["source_comparison"]["future_input"]["path"])
    original = r.input_tables
    def changed_tables(path):
        tables = copy.deepcopy(original(path))
        if path == future:
            tables["StockAllocation"]["instances"][0]["rows"][2][3] = 2
        return tables
    r.input_tables = changed_tables
    try:
        rejected_labels.append(rejected("authored stock source delta", lambda: r.model_gate(current, future)))
    finally:
        r.input_tables = original

    return {"schema": "e08-var04-author-self-check/v1", "decision": "PASS",
            "baseline_cells": baseline["report_cells_checked"], "semantic_rejections": len(rejected_labels),
            "rejected_mutations": rejected_labels, "new_native_runs": 0}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))

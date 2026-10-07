"""In-memory semantic/provenance mutations after original sealed-byte verification."""
from __future__ import annotations

import copy
import json
import struct

from json_codec import parse
from replay_v101 import RUN, ordered_process_history, physical_and_reports, replay
from source_gate_v101 import check as check_source
from source_gate_v101 import PARENT, AUTHORED


def replace_one(text: str, before: str, after: str) -> str:
    assert text.count(before) >= 1, (before, text.count(before))
    return text.replace(before, after, 1)


def check() -> dict:
    baseline = replay()
    assert baseline["decision"] == "GO_BOUNDED_RETROSPECTIVE_COUNTEREXAMPLE"
    assert baseline["behavior"]["parent_cells"] == baseline["behavior"]["child_cells"] == 5210
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    report = parse(RUN / "report-raw.json")
    parent = parse(PARENT)
    child = parse(AUTHORED)
    exported = parse(RUN / "roundtrip-raw.json")
    steps = parse(RUN / "steps.json")
    invocation = parse(RUN / "invocation.json")
    rejected = []

    def reject(name: str, action) -> None:
        try:
            action()
        except (AssertionError, ValueError, KeyError, TypeError):
            rejected.append(name)
        else:
            raise AssertionError(f"mutation escaped production gate: {name}")

    def log_probe(name: str, old: str, new: str) -> None:
        candidate = replace_one(log, old, new)
        assert candidate != log, name
        reject(name, lambda: physical_and_reports(child_log=candidate))

    log_probe("printed4_to0", "transfer time: 4", "transfer time: 0")
    log_probe("arrival_h10_to_h6", "Time: 10  resource transfer task 0 (OUT)  arrives", "Time: 6  resource transfer task 0 (OUT)  arrives")
    log_probe("wrong_arrival_task", "Time: 10  resource transfer task 0 (OUT)  arrives", "Time: 10  resource transfer task 1 (OUT)  arrives")
    log_probe("wrong_transfer_quantity", "starts with 1 resources, transfer time: 4", "starts with 2 resources, transfer time: 4")
    log_probe("wrong_departure_station", "created: starting from  <P-CREW at <BASE-01,0>>", "created: starting from  <P-CREW at <BASE-02,0>>")
    log_probe("backorder_instead_of_demand", "Resource transfer demand arrives from OUT-transfer", "Resource transfer backorder added")
    log_probe("alter_local_available", "allocated to maintenance task: 1  available now: 0", "allocated to maintenance task: 1  available now: 1")
    log_probe("alter_untimed_continuation", "no failures", "one failure")
    reject("duplicate_out_start", lambda: physical_and_reports(child_log=log.replace(
        "Time: 6  resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 4",
        "Time: 6  resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 4\nTime: 6  resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 4", 1)))

    def report_probe(name: str, table: int, row: int, field: str, replacement) -> None:
        candidate = copy.deepcopy(report)
        t = candidate["report"]["tables"][table]
        idx = [col["name"] for col in t["columns"]].index(field)
        t["instances"][0]["rows"][row][idx] = replacement
        reject(name, lambda: physical_and_reports(child_report=candidate))

    report_probe("whole_bin_tiny_positive", 2, 0, "NSYMO", 1e-9)
    bits = struct.unpack("<I", struct.pack("<f", 1.1666666269302368))[0]
    next_binary32 = struct.unpack("<f", struct.pack("<I", bits + 1))[0]
    report_probe("resource_mean_next_binary32", 5, 0, "NR", next_binary32)
    report_probe("empty_stock_null_to_zero", 3, 0, "WTS", 0)
    report_probe("description_not_authored", 0, 0, "PDESC", "counterexample changed")
    metadata = copy.deepcopy(report)
    metadata["report"]["tables"][2]["columns"][0]["datatype"] = "integer"
    reject("report_metadata_datatype", lambda: physical_and_reports(child_report=metadata))
    duplicate_instance = copy.deepcopy(report)
    duplicate_instance["report"]["tables"][2]["instances"].append(copy.deepcopy(duplicate_instance["report"]["tables"][2]["instances"][0]))
    reject("duplicate_report_instance", lambda: physical_and_reports(child_report=duplicate_instance))
    mutated_source = copy.deepcopy(child)
    mutated_source["model"]["database_version"] = True
    reject("source_metadata_bool_int", lambda: check_source(parent=parent, child=mutated_source, exported=exported))
    normalized_export = copy.deepcopy(exported)
    table = next(t for t in normalized_export["model"]["tables"] if t["name"] == "ResourceTransfer")
    table["instances"][0]["rows"][0][5] = 0.0
    reject("export_TFDT_normalized", lambda: check_source(parent=parent, child=child, exported=normalized_export))
    altered_steps = copy.deepcopy(steps)
    altered_steps[-1]["exit_code"] = 0
    reject("original_checker_exit_rewritten", lambda: ordered_process_history(steps_override=altered_steps))
    altered_invocation = copy.deepcopy(invocation)
    altered_invocation["approval_sha256"] = "0" * 64
    reject("original_approval_changed", lambda: ordered_process_history(invocation_override=altered_invocation))
    assert len(rejected) == 19
    return {"schema": "i03-var06-v101-self-check/v1", "passed": True,
            "parent_cells": 5210, "child_cells": 5210, "rejected_mutations": len(rejected),
            "mutation_names": rejected}


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))

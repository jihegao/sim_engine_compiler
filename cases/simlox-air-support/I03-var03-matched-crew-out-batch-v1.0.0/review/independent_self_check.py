"""Independent in-memory PURE source/report/log semantic probes; no native evidence."""
import importlib.util
import hashlib
import json
import math
import struct
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("independent_replay", HERE / "independent_replay.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def reject(label, fn):
    try:
        fn()
    except (AssertionError, ValueError, KeyError, TypeError):
        return label
    raise AssertionError("semantic mutation escaped: " + label)


def replace_once(raw, old, new):
    assert raw.count(old) == 1, (old, raw.count(old))
    return raw.replace(old, new, 1)


def adjacent_f32(value, direction):
    """One adjacent IEEE-754 binary32 value, without report-derived tolerance."""
    assert direction in (-1, 1) and math.isfinite(float(value))
    bits = struct.unpack("<I", struct.pack("<f", float(value)))[0]
    if bits == 0:
        return struct.unpack("<f", struct.pack("<I", 1 if direction > 0 else 0x80000001))[0]
    assert bits < 0x7f7fffff and float(value) > 0
    return struct.unpack("<f", struct.pack("<I", bits + direction))[0]

def protocol_fixtures():
    """Pure JSON protocol fixtures call the same reviewer receipt predicates as sealed replay."""
    source_map = {name: r.digest(path.read_bytes())["sha256"] for name, path in (
        ("runner_script", r.CASE / "run_native_ssh.ps1"),
        ("behavior_validator", r.CASE / "validate_native_cli.py"),
        ("prospective_contract", r.CONTRACT),
        ("control_input", r.CASE / "control_out1-input.json"),
        ("child_input", r.CASE / "child_out2-input.json"),
        ("independent_replay", HERE / "independent_replay.py"))}
    map_sha = hashlib.sha256(json.dumps(source_map, separators=(",", ":")).encode()).hexdigest()
    negatives = []
    for role in r.ROLES:
        wants = r.expected_approval(role, source_map, map_sha, "a" * 64)
        approval = {"schema": "i03-var03-matched-out-independent-prelaunch-go/v1", "decision": "GO_PRELAUNCH",
                    "arm": role, "run_id": r.RUN_IDS[role], **wants,
                    "preflight_relative_path": f"review/preflight-ssh0-{role}-20261008T010101001Z.json",
                    "preflight_sha256": "b" * 64}
        pre = {"schema": "i03-var03-matched-out-ssh-preflight/v1", "arm": role,
               "run_id": r.RUN_IDS[role], "manifest_sha256": wants["manifest_sha256"],
               "source_map_sha256": wants["source_map_sha256"], "source_hashes": deepcopy(source_map),
               "ssh_session": 0, "ps_major": 5, "wts_active_gui_count": 1,
               "mutex_free": True, "selected_run_dir_absent": True,
               "native_process_started": False, "ssh_ancestors": ["powershell.exe", "sshd.exe"],
               "gui": {"pid": 13340, "session_id": 1, "start_unix_ms": 1790590196826, "responding": True},
               "accepted_parent_raw": 34, "accepted_prerequisite_raw": 78,
               "accepted_nonclosure_raw": 101, "accepted_closures": 7, "accepted_invocations": 4,
               "accepted_total_original_raw": 112,
               "sealed_control_original_files": 0 if role == "control_out1" else 25,
               "total_mandatory_original_raw": 112 if role == "control_out1" else 137,
               "control_run_state": "absent_before_control" if role == "control_out1" else "sealed_existing_control"}
        r.validate_approval_data(role, approval, wants)
        r.validate_preflight_data(role, pre, wants, source_map)
        def change_approval(label, key, value):
            wrong = deepcopy(approval)
            wrong[key] = value
            negatives.append(reject(role + " " + label, lambda wrong=wrong: r.validate_approval_data(role, wrong, wants)))
        def change_preflight(label, key, value):
            wrong = deepcopy(pre)
            wrong[key] = value
            negatives.append(reject(role + " " + label, lambda wrong=wrong: r.validate_preflight_data(role, wrong, wants, source_map)))
        change_approval("wrong run approval", "run_id", "unexpected-run")
        change_approval("method pin approval", "independent_replay_sha256", "c" * 64)
        change_approval("source map approval", "source_map_sha256", "c" * 64)
        change_approval("preflight traversal", "preflight_relative_path", "review/../outside.json")
        change_preflight("session bool", "ssh_session", False)
        change_preflight("run present", "selected_run_dir_absent", False)
        change_preflight("GUI bool identity", "gui", {**pre["gui"], "pid": True})
        change_preflight("source map entry", "source_hashes", {**source_map, "runner_script": "c" * 64})
        change_preflight("source map digest", "source_map_sha256", "c" * 64)
        change_preflight("wrong control state", "control_run_state", "sealed_existing_control" if role == "control_out1" else "absent_before_control")
    return negatives


def main():
    contract = r.parse_json(r.CONTRACT.read_bytes())
    parent, arms = r.parent_and_predictions(contract)
    base_report = r.parse_json((r.PARENT_RUN / "out-report-raw.json").read_bytes(), native=True)
    assert r.check_report(contract, parent, "accepted_parent", r.predicted_timeline("accepted_parent"), base_report) == 5210
    accepted = (r.PARENT_RUN / "out.log").read_bytes()
    assert r.physical_from_original(accepted, "accepted_parent")["typed_events"] == 180
    control = (r.CASE / "synthetic-control_out1.log").read_bytes()
    child = (r.CASE / "synthetic-child_out2.log").read_bytes()
    assert r.physical_from_original(control, "control_out1")["typed_events"] == 173
    assert r.physical_from_original(child, "child_out2")["typed_events"] == 180
    for role, model in arms.items():
        r.verify_input(model, r.parse_json((r.CASE / (role + "-input.json")).read_bytes()))
        result = r.make_expected_report(contract, model, role, r.predicted_timeline(role))
        assert sum(len(row) for rows in result.values() for row in rows) == 5210
    labels = []
    converter_raw = (r.PARENT_RUN / "out-run.log").read_bytes()
    r.check_converter_log(converter_raw, r.PARENT_RUN, "out.sxi", "out.sxo")
    path_edges = (("converter wrong Input file", "Input file: " + str(r.PARENT_RUN / "out.sxi"),
                   "Input file: " + str(r.PARENT_RUN / "other.sxi")),
                  ("converter wrong Output file", "Output file: " + str(r.PARENT_RUN / "out.sxo"),
                   "Output file: " + str(r.PARENT_RUN / "other.sxo")),
                  ("converter wrong File source", "File: " + (r.PARENT_RUN / "out.sxi").as_posix(),
                   "File: " + (r.PARENT_RUN / "other.sxi").as_posix()))
    for label, old, new in path_edges:
        changed = replace_once(converter_raw, old.encode(), new.encode())
        labels.append(reject(label, lambda changed=changed: r.check_converter_log(changed, r.PARENT_RUN, "out.sxi", "out.sxo")))
    accepted_export = r.parse_json((r.PARENT_RUN / "out-roundtrip-raw.json").read_bytes(), native=True)
    assert r.verify_roundtrip(parent, accepted_export) == 220
    wrong_export = deepcopy(accepted_export)
    export_quantity = r.table(wrong_export, "model", "ResourceTransfer")["instances"][0]["rows"][0]
    assert type(export_quantity[4]) is int and export_quantity[4] == 1
    export_quantity[4] = 1.0
    labels.append(reject("integer transfer export rendered float",
                         lambda: r.verify_roundtrip(parent, wrong_export)))
    wrong = deepcopy(arms["child_out2"])
    r.table(wrong, "model", "ResourceTransfer")["instances"][0]["rows"][0][4] = 1
    labels.append(reject("child quantity source", lambda: r.verify_input(arms["child_out2"], wrong)))
    wrong = deepcopy(arms["control_out1"])
    r.table(wrong, "model", "ResourceAllocation")["instances"][0]["rows"][0][3] = True
    labels.append(reject("bool source number", lambda: r.verify_input(arms["control_out1"], wrong)))
    wrong = deepcopy(base_report)
    r.table(wrong, "report", "ResultSummary")["instances"][0]["rows"][0][0] = 1.0
    labels.append(reject("integer summary rendered float", lambda: r.check_report(contract, parent, "accepted_parent", r.predicted_timeline("accepted_parent"), wrong)))
    wrong = deepcopy(base_report)
    r.table(wrong, "report", "SystemResults")["instances"][0]["rows"][0][23] = True
    labels.append(reject("bool system count", lambda: r.check_report(contract, parent, "accepted_parent", r.predicted_timeline("accepted_parent"), wrong)))
    wrong = deepcopy(base_report)
    rows = r.table(wrong, "report", "StockTotalResults")["instances"][0]["rows"]
    idx = contract["report_gate"]["topology"][3]["columns"].index("WTS")
    rows[0][idx] = 0
    labels.append(reject("undefined stock null replaced zero", lambda: r.check_report(contract, parent, "accepted_parent", r.predicted_timeline("accepted_parent"), wrong)))
    wrong = deepcopy(base_report)
    t = r.table(wrong, "report", "ResourceResultsTotal")
    names = contract["report_gate"]["topology"][5]["columns"]
    idx = names.index("NRUM")
    t["instances"][0]["rows"][0][idx] = math.nextafter(t["instances"][0]["rows"][0][idx], math.inf)
    labels.append(reject("resource mean next representable float", lambda: r.check_report(contract, parent, "accepted_parent", r.predicted_timeline("accepted_parent"), wrong)))
    wrong = deepcopy(base_report)
    wrong["report"]["tables"].append(deepcopy(wrong["report"]["tables"][-1]))
    labels.append(reject("duplicate report table", lambda: r.check_report(contract, parent, "accepted_parent", r.predicted_timeline("accepted_parent"), wrong)))
    wrong = deepcopy(base_report)
    r.table(wrong, "report", "SystemResults")["columns"].append({"name": "EXTRA", "datatype": "double"})
    labels.append(reject("extra report metadata", lambda: r.check_report(contract, parent, "accepted_parent", r.predicted_timeline("accepted_parent"), wrong)))
    pairs = [
        ("child residual backorder qty2", child, b"Nbr: 0", b"Nbr: 2", "child_out2"),
        ("child second release free2", child, b"Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> frees resources\nTime: 8  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1", b"Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> frees resources\nTime: 8  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 2", "child_out2"),
        ("child transfer quantity0", child, b"task 1 (OUT)  starts with 1 resources", b"task 1 (OUT)  starts with 0 resources", "child_out2"),
        ("control unknown event", control, b"Time: 7.75  resource transfer task 0", b"Time: 7.75  unknown native event\nTime: 7.75  resource transfer task 0", "control_out1"),
        ("control duplicate lifecycle", control, b"Time: 8  system preparation task 0", b"Time: 8.0  system preparation task 0 on <TEACH-AIR-01,0> started\nTime: 8  system preparation task 0", "control_out1"),
        ("child wrong mission launch", child, b"Time: 20.5 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting", b"Time: 20.25 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting", "child_out2"),
    ]
    for label, raw, old, new, role in pairs:
        assert raw.count(old) >= 1, label
        changed = raw.replace(old, new, 1)
        labels.append(reject(label, lambda changed=changed, role=role: r.physical_from_original(changed, role)))
    extra = [
        ("child failed availability changed OK", child, b"request for: 1 failed", b"request for: 1 OK", "child_out2"),
        ("child waiting queue quantity0", child, b"Tasks waiting for resources at: <BASE-01,0> 1", b"Tasks waiting for resources at: <BASE-01,0> 0", "child_out2"),
        ("control wrong ready snapshot", control, b"systems ready: 1 :<TEACH-AIR-01,0>", b"systems ready: 2 :<TEACH-AIR-01,0>", "control_out1"),
        ("child remote check duplicate", child, b"Time: 20.5  subtask 3 seqno 1 check return remote resources", b"Time: 20.5  subtask 3 seqno 1 check return remote resources\nTime: 20.5  subtask 3 seqno 1 check return remote resources", "child_out2"),
        ("child wrong waiting task owner", child, b"< subtask 3 seqno 1 within system preparation task 3 on <TEACH-AIR-01,1>, C, 0.5>", b"< subtask 2 seqno 1 within system preparation task 2 on <TEACH-AIR-01,0>, C, 0.5>", "child_out2"),
        ("child wrong booked task listing", child, b"< subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1>, C, 1, 0.5>", b"< subtask 2 seqno 1 within system preparation task 2 on <TEACH-AIR-01,0>, C, 1, 0.5>", "child_out2"),
        ("child backorder snapshot wrong owner", child, b"Time: 7.75  <P-CREW at <BASE-01,0>> Resource transfer backorder added \n  Resource transfer backorders at:  <P-CREW at <BASE-01,0>> Nbr: 1 Backorders:<OUT,7.75>,\nTime: 7.75  resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 0", b"Time: 7.75  <P-CREW at <BASE-01,0>> Resource transfer backorder added \nTime: 7.75  resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 0\n  Resource transfer backorders at:  <P-CREW at <BASE-01,0>> Nbr: 1 Backorders:<OUT,7.75>,", "child_out2"),
    ]
    for label, raw, old, new, role in extra:
        assert raw.count(old) >= 1, label
        changed = raw.replace(old, new, 1)
        labels.append(reject(label, lambda changed=changed, role=role: r.physical_from_original(changed, role)))
    total = r.table(base_report, "report", "ResourceResultsTotal")
    names = contract["report_gate"]["topology"][5]["columns"]
    for field in ("NR", "NRA", "NRN", "NRUM", "NRW"):
        for direction in (-1, 1):
            wrong = deepcopy(base_report)
            row = r.table(wrong, "report", "ResourceResultsTotal")["instances"][0]["rows"][0]
            i = names.index(field)
            row[i] = adjacent_f32(row[i], direction)
            labels.append(reject("mean one binary32 ULP " + field + (" below" if direction < 0 else " above"),
                                 lambda wrong=wrong: r.check_report(contract, parent, "accepted_parent", r.predicted_timeline("accepted_parent"), wrong)))
    assert len(labels) == 35
    protocol = protocol_fixtures()
    assert len(protocol) == 20
    print(json.dumps({"mode": "PURE_SYNTHETIC_STATIC_ONLY", "parent_report_cells": 5210,
                      "predicted_cells_per_arm": 5210, "semantic_rejections": len(labels),
                      "protocol_rejections": len(protocol), "rejected": labels + protocol,
                      "new_native_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()


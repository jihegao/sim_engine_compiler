"""Pure mutations of the independent I04.var10 v1.0.1 semantic predicates.

This exercises independent source, export, log and report checks without a
SIMLOX call. The full native/provenance gate remains in independent_replay.
"""
from __future__ import annotations

import copy
import json

import independent_replay as reader


def rejects(label, action):
    try:
        action()
    except (AssertionError, UnicodeError, ValueError, KeyError, TypeError):
        return label
    raise AssertionError(f"accepted negative clone: {label}")


def main():
    contract = reader.contract()
    oracles = reader.oracles(contract)
    source = reader.verify_source(contract, oracles["source-delta.json"])
    export = reader.strict_json((reader.PKG / "child-roundtrip-oracle.json").read_bytes())
    reader.verify_export(contract, export)
    log_lines = reader.expected_log(contract, oracles["log-oracle.json"])
    log = ("\r\n".join(log_lines) + "\r\n").encode("utf-8")
    reader.verify_log(contract, oracles["log-oracle.json"], log)
    report = reader.report_expected(contract, oracles["report-oracle.json"])
    assert reader.report_equal(report, oracles["report-oracle.json"])
    failures = []

    def source_clone(label, edit):
        clone = copy.deepcopy(source)
        edit(clone)
        failures.append(rejects(label, lambda: reader.verify_source(
            contract, oracles["source-delta.json"], clone)))

    def export_clone(label, edit):
        clone = copy.deepcopy(export)
        edit(clone)
        failures.append(rejects(label, lambda: reader.verify_export(contract, clone)))

    def log_clone(label, edit):
        clone = list(log_lines)
        edit(clone)
        data = ("\r\n".join(clone) + "\r\n").encode("utf-8")
        failures.append(rejects(label, lambda: reader.verify_log(
            contract, oracles["log-oracle.json"], data)))

    def report_clone(label, edit):
        clone = copy.deepcopy(report)
        edit(clone)
        failures.append(rejects(label, lambda: reader.report_equal(clone, report)))

    source_clone("source horizon", lambda m: reader.table(m, "Control")["instances"][0]["rows"][0].__setitem__(
        next(i for i, c in enumerate(reader.table(m, "Control")["columns"]) if c["name"] == "RCEND"), 36.0))
    source_clone("source profile restored", lambda m: reader.table(m, "OperationProfile")["instances"][0]["rows"].append(
        contract["source_changes"][6]["parent"]))
    source_clone("source table order", lambda m: m["model"]["tables"].reverse())
    export_clone("export table order", lambda m: m["model"]["tables"].reverse())
    export_clone("export metadata", lambda m: m["model"]["tables"][0]["columns"][0].__setitem__("datatype", "double"))
    export_clone("export instance", lambda m: m["model"]["tables"][0]["instances"][0].__setitem__("instance_name", "other"))
    export_clone("export placeholder", lambda m: m["model"]["tables"][0]["instances"][0]["rows"][0].__setitem__(0, "unexpected"))
    export_clone("export Boolean double", lambda m: reader.table(m, "Control")["instances"][0]["rows"][0].__setitem__(
        next(i for i, c in enumerate(reader.table(m, "Control")["columns"]) if c["name"] == "RCEND"), True))
    log_clone("log horizon", lambda x: x.__setitem__(1, "36"))
    log_clone("log extra arrival", lambda x: x.append("Time: 11 system transfered in: <TEACH-AIR-01,0>."))
    log_clone("log transfer identity", lambda x: x.__setitem__(60, x[60].replace("<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>")))
    log_clone("log order", lambda x: x.__setitem__(59, x[60]))
    report_clone("report instance horizon", lambda r: r["report"]["tables"][2]["instances"][0].__setitem__(
        "instance_name", "Total over all Units;Total over all Systems;0.00;36.00"))
    report_clone("report summary", lambda r: r["report"]["tables"][1]["instances"][0]["rows"][0].__setitem__(2, 36.0))
    report_clone("report terminal transit", lambda r: r["report"]["tables"][2]["instances"][0]["rows"][21].__setitem__(
        next(i for i, c in enumerate(r["report"]["tables"][2]["columns"]) if c["name"] == "NSYA"), 2.0))
    report_clone("report null", lambda r: r["report"]["tables"][3]["instances"][0]["rows"][21].__setitem__(
        next(i for i, c in enumerate(r["report"]["tables"][3]["columns"]) if c["name"] == "WT"), 0.0))
    report_clone("report bin order", lambda r: r["report"]["tables"][2]["instances"][0]["rows"].reverse())
    report_clone("report extra column", lambda r: r["report"]["tables"][2]["columns"].append({"name": "EXTRA", "datatype": "double"}))
    failures.append(rejects("duplicate JSON key", lambda: reader.strict_json(b'{"a":1,"a":2}')))
    failures.append(rejects("nonfinite JSON", lambda: reader.strict_json(b'{"a":NaN}')))
    failures.append(rejects("truncated log", lambda: reader.verify_log(
        contract, oracles["log-oracle.json"], b"\n".join(log.splitlines()[:-1]) + b"\n")))
    old_run = str(reader.PARENT_RUN)
    old_forward = old_run.replace("\\", "/")
    converter = (reader.PARENT_RUN / "model-run.log").read_bytes().decode("utf-8-sig")
    assert converter.count(old_run) == 2 and converter.count(old_forward) == 1
    converter = converter.replace(old_run, str(reader.RUN)).replace(
        old_forward, str(reader.RUN).replace("\\", "/"))
    converter = converter.replace("\r\n", "\n")
    reader.verify_converter(converter.encode("utf-8"))
    failures.append(rejects("converter File backslash", lambda: reader.verify_converter(
        converter.replace("File: " + str(reader.RUN / "model.sxi").replace("\\", "/"),
                          "File: " + str(reader.RUN / "model.sxi")).encode("utf-8"))))
    failures.append(rejects("converter Input forward slash", lambda: reader.verify_converter(
        converter.replace("Input file: " + str(reader.RUN / "model.sxi"),
                          "Input file: " + str(reader.RUN / "model.sxi").replace("\\", "/")).encode("utf-8"))))
    failures.append(rejects("converter wrong extension", lambda: reader.verify_converter(
        converter.replace("File: " + str(reader.RUN / "model.sxi").replace("\\", "/"),
                          "File: " + str(reader.RUN / "model.sxo").replace("\\", "/")).encode("utf-8"))))
    failures.append(rejects("converter extra warning", lambda: reader.verify_converter(
        converter.replace("Converting input data ...\n", "Converting input data ...\nWarning: extra\n").encode("utf-8"))))
    input_sha = "a" * 64
    export_sha = "b" * 64
    roundtrip = {"schema": "i04-var10-horizon-transit-roundtrip/v101", "passed": True,
                 "run_id": reader.RUN_ID, "native_run_directory": str(reader.RUN),
                 "tables": 34, "authored_rows": 21, "exported_rows": 39,
                 "authored_cells": 211, "exported_cells": 395,
                 "all_null_placeholder_tables": 18, "issues": [],
                 "input_sha256": input_sha, "export_sha256": export_sha}
    behavior = {"schema": "i04-var10-horizon-transit-behavior/v101", "passed": True,
                "run_id": reader.RUN_ID, "native_run_directory": str(reader.RUN),
                "input_sha256": input_sha, "export_sha256": export_sha,
                "report_cell_checks": 1244, "timed_event_records": 53,
                "log_lines": 61, "terminal": copy.deepcopy(reader.TERMINAL),
                "issues": [], "native_calls": 0}
    reader.verify_checker_receipts(roundtrip, behavior, input_sha, export_sha)

    def receipt_clone(label, kind, edit):
        a, b = copy.deepcopy(roundtrip), copy.deepcopy(behavior)
        edit(a if kind == "roundtrip" else b)
        failures.append(rejects(label, lambda: reader.verify_checker_receipts(
            a, b, input_sha, export_sha)))

    receipt_clone("roundtrip missing native path", "roundtrip", lambda r: r.pop("native_run_directory"))
    receipt_clone("roundtrip path alias", "roundtrip", lambda r: r.__setitem__(
        "native_run_directory", str(reader.RUN).replace("\\", "/")))
    receipt_clone("roundtrip path Boolean", "roundtrip", lambda r: r.__setitem__("native_run_directory", True))
    receipt_clone("roundtrip unknown field", "roundtrip", lambda r: r.__setitem__("extra", 1))
    receipt_clone("roundtrip Boolean count", "roundtrip", lambda r: r.__setitem__("authored_rows", True))
    receipt_clone("behavior missing native path", "behavior", lambda r: r.pop("native_run_directory"))
    receipt_clone("behavior wrong path", "behavior", lambda r: r.__setitem__("native_run_directory", "wrong"))
    receipt_clone("behavior path list", "behavior", lambda r: r.__setitem__("native_run_directory", []))
    receipt_clone("behavior unknown field", "behavior", lambda r: r.__setitem__("extra", 1))
    receipt_clone("behavior wrong terminal", "behavior", lambda r: r["terminal"].__setitem__("transit_terminal", 0))
    receipt_clone("behavior terminal Boolean", "behavior", lambda r: r["terminal"].__setitem__("transit_terminal", True))
    receipt_clone("behavior Boolean count", "behavior", lambda r: r.__setitem__("native_calls", False))
    ordered = [{"relative_path": name} for name in reader.owned_names(provisional=False)]
    reader.assert_inventory_order(ordered, reader.owned_names(provisional=False))
    reordered = copy.deepcopy(ordered)
    reordered[0], reordered[-1] = reordered[-1], reordered[0]
    failures.append(rejects("inventory memo order", lambda: reader.assert_inventory_order(
        reordered, reader.owned_names(provisional=False))))
    source_map = {"sample": "c" * 64}
    source_sha = reader.source_map_sha(source_map)
    preflight = {
        "schema": "i04-var10-horizon-transit-ssh-preflight/v101", "run_id": reader.RUN_ID,
        "native_run_directory": str(reader.RUN), "run_dirs_absent": True,
        "file_line_ascii_bytes": 121, "file_line_ascii_max": 199,
        "native_run_path_ancestors_no_reparse": True, "ssh_session": 0, "ps_major": 5,
        "ssh_ancestors": ["sshd.exe"], "mutex_free": True, "wts_active_gui_count": 1,
        "gui": copy.deepcopy(reader.GUI), "accepted_parent_raw": 153,
        "accepted_parent_preflight_originals": 15, "excluded_v100_source_files": 24,
        "total_parent_original_raw": 168, "manifest_sha256": "d" * 64,
        "source_map_sha256": source_sha, "source_hashes": source_map,
        "source_hashes_after_pure": source_map, "pure_proof_directory": "synthetic",
        "pure_proof_path": "synthetic", "pure_proof_sha256": "e" * 64,
        "pure_checks": [{"synthetic": i} for i in range(5)], "native_process_started": False,
    }
    reader.preflight_core(preflight, "d" * 64, source_map, source_sha)

    def preflight_clone(label, edit):
        clone = copy.deepcopy(preflight)
        edit(clone)
        failures.append(rejects(label, lambda: reader.preflight_core(
            clone, "d" * 64, source_map, source_sha)))

    preflight_clone("preflight path array", lambda r: r.__setitem__("native_run_directory", []))
    preflight_clone("preflight path alias", lambda r: r.__setitem__(
        "native_run_directory", str(reader.RUN).replace("\\", "/")))
    preflight_clone("preflight missing path", lambda r: r.pop("native_run_directory"))
    preflight_clone("preflight Boolean count", lambda r: r.__setitem__("accepted_parent_raw", True))
    preflight_clone("preflight unknown field", lambda r: r.__setitem__("extra", 1))
    assert len(failures) == len(set(failures)) == 43
    print(f"INDEPENDENT_SEMANTIC_PURE_PASS 34/21/211 61/53 1244 negatives={len(failures)}")


if __name__ == "__main__":
    main()

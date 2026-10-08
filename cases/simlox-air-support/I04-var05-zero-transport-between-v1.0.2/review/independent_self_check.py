"""PURE reviewer mutations; never runs SIMLOX or an accepted parent checker."""
from __future__ import annotations

import copy
import json

import independent_replay as reader


def rejects(label, action):
    try:
        action()
    except (AssertionError, ValueError, UnicodeError, KeyError, TypeError):
        return label
    raise AssertionError(f"semantic mutation accepted: {label}")


def self_check():
    contract = reader.load_contract()
    log_oracle, report_oracle = reader.load_oracles(contract)
    source, _ = reader.verify_source(contract)
    expected_report = reader.report_values(contract, report_oracle)
    expected_export = reader.expected_export(source)
    reader.verify_export(source, expected_export)
    reader.verify_report(contract, report_oracle, expected_report)
    forms = reader.proposed_log_bytes(log_oracle)
    assert len(forms) == 4
    for form in forms:
        reader.verify_log(contract, log_oracle, form)
    tested = []

    def source_mutation(label, update):
        modified = copy.deepcopy(source)
        update(modified)
        tested.append(rejects(label, lambda: reader.verify_source(contract, actual_override=modified)))

    def export_mutation(label, update):
        modified = copy.deepcopy(expected_export)
        update(modified)
        tested.append(rejects(label, lambda: reader.verify_export(source, modified)))

    def report_mutation(label, update):
        modified = copy.deepcopy(expected_report)
        update(modified)
        tested.append(rejects(label, lambda: reader.verify_report(contract, report_oracle, modified)))

    def trace_mutation(label, update):
        lines = forms[0].decode("utf-8").splitlines()
        update(lines)
        modified = ("\r\n".join(lines) + "\r\n").encode("utf-8")
        tested.append(rejects(label, lambda: reader.verify_log(contract, log_oracle, modified)))

    source_mutation("wrong_transfer_duration", lambda x: x["model"]["tables"][10]["instances"][0]["rows"][0].__setitem__(5, .5))
    source_mutation("boolean_transfer_duration", lambda x: x["model"]["tables"][10]["instances"][0]["rows"][0].__setitem__(5, False))
    source_mutation("wrong_transfer_key_flag", lambda x: x["model"]["tables"][10]["columns"][0].__setitem__("key", False))
    source_mutation("extra_source_table", lambda x: x["model"]["tables"].append(copy.deepcopy(x["model"]["tables"][-1])))
    source_mutation("changed_transfer_owner", lambda x: x["model"]["tables"][10]["instances"][0]["rows"][0].__setitem__(1, "WRONG"))

    export_mutation("missing_null_placeholder", lambda x: x["model"]["tables"][1]["instances"][0]["rows"].clear())
    export_mutation("extra_export_column", lambda x: x["model"]["tables"][17]["columns"].append({"name": "EXTRA", "datatype": "double"}))
    export_mutation("boolean_export_double", lambda x: x["model"]["tables"][17]["instances"][0]["rows"][0].__setitem__(5, False))
    export_mutation("wrong_export_instance", lambda x: x["model"]["tables"][17]["instances"][0].__setitem__("instance_name", "wrong"))

    trace_mutation("early_arrival", lambda x: x.__setitem__(61, x[61].replace("10.5", "10.0", 1)))
    trace_mutation("wrong_target_owner", lambda x: x.__setitem__(61, x[61].replace("TEACH-UNIT-2", "TEACH-UNIT")))
    trace_mutation("missing_departure", lambda x: x.pop(60))
    trace_mutation("arrival_before_departure", lambda x: x.insert(60, x.pop(61)))
    trace_mutation("duplicate_arrival", lambda x: x.insert(62, x[61]))
    trace_mutation("duplicate_optional_ready_line", lambda x: x.__setitem__(slice(61, 61), [
        "Time: 10.5 <TEACH-UNIT at <BASE-01,0>> systems ready: 0 :",
        "Time: 10.5 <TEACH-UNIT at <BASE-01,0>> systems ready: 0 :"]))
    trace_mutation("mission_changed", lambda x: x.__setitem__(68, x[68].replace("BASIC-MISSION", "WRONG")))
    trace_mutation("truncated_trace", lambda x: x.pop())

    system = expected_report["tables"][2]["instances"][0]["rows"]
    system_columns = [c["name"] for c in expected_report["tables"][2]["columns"]]
    report_mutation("wrong_half_hour_ready", lambda x: x["tables"][2]["instances"][0]["rows"][21].__setitem__(system_columns.index("NSYRY"), 1.0))
    report_mutation("wrong_half_hour_in_unit", lambda x: x["tables"][2]["instances"][0]["rows"][21].__setitem__(system_columns.index("NSYA"), 1.0))
    report_mutation("boolean_report_double", lambda x: x["tables"][2]["instances"][0]["rows"][21].__setitem__(system_columns.index("NSYA"), True))
    report_mutation("nonfinite_report_cell", lambda x: x["tables"][2]["instances"][0]["rows"][21].__setitem__(system_columns.index("NSYA"), float("inf")))
    report_mutation("missing_report_interval", lambda x: x["tables"][2]["instances"][0]["rows"].pop())
    report_mutation("extra_report_metadata", lambda x: x["tables"][2]["columns"][0].__setitem__("extra", 1))
    report_mutation("null_to_zero", lambda x: x["tables"][2]["instances"][0]["rows"][21].__setitem__(system_columns.index("SYDT"), 0))
    report_mutation("summary_integer_to_bool", lambda x: x["tables"][1]["instances"][0]["rows"][0].__setitem__(0, True))

    for label, blob in [
        ("duplicate_json_key", b'{"x":1,"x":2}'),
        ("nan_json", b'{"x":NaN}'),
        ("overflow_json", b'{"x":1e999}'),
        ("unexpected_trailing_comma", b'{"x":[1,]}'),
    ]:
        tested.append(rejects(label, lambda blob=blob: reader.strict_json(blob)))
    archive = reader.strict_json((reader.PACKAGE / "preserved-context/catalog-local-497.json.bytes").read_bytes())
    current = reader.strict_json((reader.ROOT / "cases/simlox-air-support/publication-index-v1.json").read_bytes())
    assert reader.catalog_prefix(archive, current) == 497
    def catalog_mutation(label, update):
        mutated = copy.deepcopy(current)
        update(mutated)
        tested.append(rejects(label, lambda: reader.catalog_prefix(archive, mutated)))
    catalog_mutation("catalog_prefix_cell", lambda x: x["entries"][0].__setitem__("publication_id", "wrong"))
    catalog_mutation("catalog_metadata_type", lambda x: x.__setitem__("as_of", 1))
    catalog_mutation("catalog_duplicate_id", lambda x: x["entries"].append(copy.deepcopy(x["entries"][0])))
    core = reader.PACKAGE / "prospective-contract.json"
    data = core.read_bytes()
    seal = {"key": "a", "path": str(core.resolve(strict=True)),
            "bytes": len(data), "sha256": reader.digest(data)}
    pair = [seal, dict(seal, key="b")]
    assert reader.role_row_semantics(pair, rehash=True) == {
        "source_roles": 2, "unique_physical_paths": 1}
    def roles_mutation(label, update):
        rows = copy.deepcopy(pair)
        update(rows)
        tested.append(rejects(label, lambda: reader.role_row_semantics(rows, rehash=False)))
    roles_mutation("role_key_casefold_collision", lambda x: x[1].__setitem__("key", "A"))
    roles_mutation("duplicate_path_conflicting_sha", lambda x: x[1].__setitem__("sha256", "0" * 64))
    roles_mutation("duplicate_path_conflicting_size", lambda x: x[1].__setitem__("bytes", x[1]["bytes"] + 1))
    roles_mutation("role_size_bool", lambda x: x[1].__setitem__("bytes", True))
    roles_mutation("role_relative_path", lambda x: x[1].__setitem__("path", "prospective-contract.json"))
    roles_mutation("role_lexical_alias", lambda x: x[1].__setitem__(
        "path", str(reader.PACKAGE / "review" / ".." / "prospective-contract.json")))
    source_map = {"a": "1" * 64, "b": "2" * 64}
    source_sha = reader.source_map_sha(source_map)
    assert source_sha != reader.source_map_sha(dict(reversed(list(source_map.items()))))
    receipt = {
        "schema": "i04-var05-zero-between-ssh-preflight/v102", "run_id": reader.RUN_ID,
        "run_dirs_absent": True, "ssh_session": 0, "ps_major": 5,
        "ssh_ancestors": ["sshd.exe"], "mutex_free": True, "wts_active_gui_count": 1,
        "gui": copy.deepcopy(reader.GUI), "accepted_raw_seals": 168,
        "accepted_nonclosure_raw": 152, "accepted_closures": 8,
        "accepted_invocations": 8, "excluded_failed_witness_raw": 34,
        "failed_preflight_originals": 18, "total_original_raw": 220,
        "native_run_directory": str(reader.RUN), "file_line_ascii_bytes": 121,
        "file_line_ascii_max": 199, "native_run_path_ancestors_no_reparse": True,
        "manifest_sha256": "3" * 64,
        "source_map_sha256": source_sha, "source_hashes": copy.deepcopy(source_map),
        "source_hashes_after_pure": copy.deepcopy(source_map),
        "pure_proof_directory": "synthetic", "pure_proof_path": "synthetic/pure-proof.json",
        "pure_proof_sha256": "4" * 64, "pure_checks": [None] * 5,
        "native_process_started": False,
    }
    assert reader.preflight_core(receipt, "3" * 64, source_map, source_sha)
    def receipt_mutation(label, update):
        mutated = copy.deepcopy(receipt)
        update(mutated)
        tested.append(rejects(label, lambda: reader.preflight_core(mutated, "3" * 64,
                                                                      source_map, source_sha)))
    receipt_mutation("preflight_gui_session_bool", lambda x: x["gui"].__setitem__("session_id", True))
    receipt_mutation("preflight_gui_responding_integer", lambda x: x["gui"].__setitem__("responding", 1))
    receipt_mutation("preflight_wts_bool", lambda x: x.__setitem__("wts_active_gui_count", True))
    receipt_mutation("preflight_raw_count_bool", lambda x: x.__setitem__("accepted_raw_seals", True))
    receipt_mutation("preflight_native_started", lambda x: x.__setitem__("native_process_started", True))
    receipt_mutation("preflight_run_present", lambda x: x.__setitem__("run_dirs_absent", False))
    receipt_mutation("preflight_mutex_busy", lambda x: x.__setitem__("mutex_free", False))
    receipt_mutation("preflight_source_changed", lambda x: x["source_hashes"].__setitem__("a", "0" * 64))
    receipt_mutation("preflight_source_order", lambda x: x.__setitem__(
        "source_hashes", dict(reversed(list(x["source_hashes"].items())))))
    receipt_mutation("preflight_after_pure_changed", lambda x: x["source_hashes_after_pure"].__setitem__("b", "0" * 64))
    receipt_mutation("preflight_missing_pure_check", lambda x: x["pure_checks"].pop())
    receipt_mutation("preflight_stale_native_path", lambda x: x.__setitem__("native_run_directory", "C:\\stale"))
    receipt_mutation("preflight_file_line_bool", lambda x: x.__setitem__("file_line_ascii_bytes", True))
    receipt_mutation("preflight_file_line_overlong", lambda x: x.__setitem__("file_line_ascii_bytes", 205))
    receipt_mutation("preflight_reparse_ancestor", lambda x: x.__setitem__("native_run_path_ancestors_no_reparse", False))
    receipt_mutation("preflight_failed_originals_missing", lambda x: x.__setitem__("excluded_failed_witness_raw", 0))
    prospective_run = reader.RUN
    original_converter = (reader.PARENT_RUN / "model-run.log").read_bytes().decode("utf-8-sig")
    assert original_converter.count(str(reader.PARENT_RUN)) == 2
    assert original_converter.count(str(reader.PARENT_RUN).replace("\\", "/")) == 1
    rebound = original_converter.replace(str(reader.PARENT_RUN), str(prospective_run))
    rebound = rebound.replace(str(reader.PARENT_RUN).replace("\\", "/"),
                              str(prospective_run).replace("\\", "/")).encode("utf-8")
    assert reader.verify_converter(rebound, prospective_run)["converter_lines"] == 17
    def converter_mutation(label, change):
        altered = change(rebound)
        tested.append(rejects(label, lambda: reader.verify_converter(altered, prospective_run)))
    converter_mutation("converter_extra_unnumbered_warning", lambda x: x.replace(
        b"Starting simulation...", b"Warning: unexpected diagnostic\r\nStarting simulation..."))
    converter_mutation("converter_stale_path", lambda x: x.replace(
        str(prospective_run).encode(), str(reader.PARENT_RUN).encode(), 1))
    converter_mutation("converter_corrupt_file_tail", lambda x: x.replace(
        ("File: " + prospective_run.as_posix() + "/model.sxi").encode("ascii"),
        ("File: " + prospective_run.as_posix() + "/modelfa5827d9a210").encode("ascii"), 1))
    converter_mutation("converter_warning_count", lambda x: x.replace(
        b"Warnings: 2", b"Warnings: 3"))
    converter_mutation("converter_wrong_owner", lambda x: x.replace(
        b"Form: System", b"Form: Resource"))
    planned = {"program": str(reader.SIMLOX), "arguments": "synthetic argv"}
    step = {"sequence": 3, "name": "calc", "program": planned["program"],
            "arguments": planned["arguments"], "started_utc": "2026-10-08T00:00:00Z",
            "completed_utc": "2026-10-08T00:00:01Z", "child_pid": 7,
            "child_session_id": 0, "exit_code": 0, "capture_error": None,
            "stdout_path": "synthetic/stdout", "stderr_path": "synthetic/stderr",
            "stdout_bytes": 0, "stderr_bytes": 0, "stdout_sha256": "0" * 64,
            "stderr_sha256": "0" * 64, "converter_log_bytes": 100,
            "converter_log_sha256": "1" * 64, "converter_log_validated": True,
            "gui_preserved": True, "status": "completed", "error": None}
    previous = reader.utc("2026-10-08T00:00:00Z")
    assert reader.stage_core(step, 3, "calc", planned, previous) >= previous
    def step_mutation(label, update):
        mutated = copy.deepcopy(step)
        update(mutated)
        tested.append(rejects(label, lambda: reader.stage_core(mutated, 3, "calc", planned, previous)))
    step_mutation("calc_exit_bool", lambda x: x.__setitem__("exit_code", False))
    step_mutation("calc_converter_unvalidated", lambda x: x.__setitem__("converter_log_validated", False))
    step_mutation("calc_converter_size_bool", lambda x: x.__setitem__("converter_log_bytes", True))
    step_mutation("calc_stale_argv", lambda x: x.__setitem__("arguments", "other"))
    step_mutation("calc_stderr_nonempty", lambda x: x.__setitem__("stderr_bytes", 1))
    step_mutation("calc_gui_lost", lambda x: x.__setitem__("gui_preserved", False))
    names = reader.owned_names()
    ordered = [{"relative_path": name} for name in names]
    assert reader.require_ordered_relative_paths(ordered, names) == len(names)
    moved = copy.deepcopy(ordered)
    memo = "review/independent-method-static-go-2026-10-08.md"
    memo_row = next(row for row in moved if row["relative_path"] == memo)
    moved.remove(memo_row)
    moved.append(memo_row)
    assert {row["relative_path"] for row in moved} == set(names)
    tested.append(rejects("v101_same_membership_memo_moved_to_last", lambda:
                          reader.require_ordered_relative_paths(moved, names)))
    assert len(tested) == 66
    return {"decision": "PASS_PURE_SEMANTIC_REJECTIONS_ONLY",
            "positive_log_forms": 4, "positive_report_cells": 4044,
            "semantic_rejections": len(tested)}


if __name__ == "__main__":
    print(json.dumps(self_check(), sort_keys=True))

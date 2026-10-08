"""In-memory semantic negative checks for independent I03.var05 reader.

Each mutation is sent directly to the semantic gate after a clean pure baseline;
no fabricated actual run directory or native evidence is created.
"""

import copy
import json
import os
from pathlib import Path
import struct
import tempfile

import independent_replay as reader


def rejects(label, callback, record):
    try:
        callback()
    except (AssertionError, ValueError, UnicodeError, KeyError, TypeError):
        record.append(label)
        return
    raise AssertionError(("semantic mutation escaped", label))


def f32_adjacent(value, sign):
    bit = struct.unpack("<I", struct.pack("<f", value))[0]
    if bit == 0 and sign < 0:
        return struct.unpack("<f", struct.pack("<I", 0x80000001))[0]
    return struct.unpack("<f", struct.pack("<I", bit + sign))[0]


def synthetic_sealed_protocol(pure, rejected):
    """Exercise the entire sealed reader on scratch files, never the reserved run."""
    original_run = reader.RUN
    with tempfile.TemporaryDirectory(prefix="i03-var05-pure-protocol-") as folder:
        run = Path(folder) / original_run.name
        run.mkdir()
        reader.RUN = run
        try:
            write = lambda name, data: (run / name).write_bytes(data)
            encoded = lambda value: json.dumps(value, ensure_ascii=False,
                separators=(",", ":")).encode()
            parent_export = reader.accepted_parent_roundtrip(pure["parent"], reader.Audit())
            export = copy.deepcopy(parent_export)
            by_name = {table["name"]: table for table in export["model"]["tables"]}
            by_name["ProblemDescription"]["instances"][0]["rows"][0][0] = \
                reader.model_description(pure["prediction"])
            by_name["ResourceTransfer"]["instances"][0]["rows"][1][5] = 0
            child_report = reader.make_pure_child_report(pure["contract"], pure["canonical_report"])
            _, predicted_lines = reader.predicted_log_lines(reader.Audit())
            parent_log = (reader.PARENT_RUN / "out_in-run.log").read_text(encoding="utf-8-sig")
            converter = parent_log.replace(str(reader.PARENT_RUN), str(run)).replace(
                str(reader.PARENT_RUN).replace("\\", "/"), str(run).replace("\\", "/"))
            converter = converter.replace("out_in.sxi", "model.sxi").replace("out_in.sxo", "model.sxo")
            initial = {"input.json": encoded(pure["prediction"]),
                "model.sxi": b"PURE synthetic model source", "model.sxo": b"PURE synthetic model result",
                "import.log": b"Import completed!", "export.log": b"Export completed!",
                "roundtrip-raw.json": encoded(export), "model.log": ("\n".join(predicted_lines) + "\n").encode(),
                "model-run.log": converter.encode(), "report-raw.json": encoded(child_report),
                "report-export.log": b"PURE synthetic report export"}
            for name, data in initial.items():
                write(name, data)
            os.chmod(run / "model-run.log", 0o444)
            input_sha = reader.sha(initial["input.json"])
            rt = {"schema": "i03-var05-in-zero-roundtrip/v1", "passed": True,
                "issues": [], "input_sha256": input_sha,
                "export_sha256": reader.sha(initial["roundtrip-raw.json"]),
                "table_objects": 32, "row_containing_tables": 21,
                "all_null_placeholder_tables": 11}
            terminal = {"local": 2, "nominal": 2, "booked": 0, "reserved_OUT": 0,
                "departed_OUT": 1, "IN_started_unarrived": 0, "IN_task_arrived": 1,
                "IN_pending_local_receipt": 0, "locally_received_IN": 1}
            behavior = {"schema": "i03-var05-in-zero-behavior/v1", "passed": True,
                "issues": [], "run_id": run.name, "input_sha256": input_sha,
                "report_cell_checks": 5210, "typed_event_records": 184,
                "timeline": {"out_request": 7.75, "out_departure": 8, "in_start": 10,
                    "in_task_arrival": 10, "in_local_receipt": 10, "terminal_local": 2,
                    "terminal_ready": 2, "raw_lines": 250, "timed_events": 184,
                    "microstates": {"terminal": terminal}}}
            write("roundtrip-validation.json", encoded(rt))
            write("author-validation.json", encoded(behavior))
            manifest_raw, approval_raw, preflight_raw = b"PURE manifest", b"PURE approval", b"PURE preflight"
            source_map = {"child_input": input_sha, "child_contract": reader.V4_SHA,
                "runner_script": "a" * 64, "independent_replay": "b" * 64}
            plan = reader.planned_steps()
            steps = []
            for index, item in enumerate(plan):
                name = item["name"]
                stdout_name = ("roundtrip-validation.json" if index == 2 else
                    "author-validation.json" if index == 5 else name + "-stdout.txt")
                stderr_name = name + "-stderr.txt"
                if index not in (2, 5):
                    write(stdout_name, b"PURE stage stdout")
                write(stderr_name, b"")
                step = {"sequence": index, **item,
                    "started_utc": f"2026-10-08T00:00:{index * 2:02d}+00:00",
                    "completed_utc": f"2026-10-08T00:00:{index * 2 + 1:02d}+00:00",
                    "child_pid": 20000 + index, "child_session_id": 0,
                    "exit_code": 0, "capture_error": None,
                    "stdout_path": str(run / stdout_name),
                    "stderr_path": str(run / stderr_name),
                    "stdout_bytes": (run / stdout_name).stat().st_size,
                    "stdout_sha256": reader.sha((run / stdout_name).read_bytes()),
                    "stderr_bytes": 0, "stderr_sha256": reader.sha(b""),
                    "converter_log_bytes": len(initial["model-run.log"]) if index == 3 else None,
                    "converter_log_sha256": reader.sha(initial["model-run.log"]) if index == 3 else None,
                    "converter_log_validated": index == 3,
                    "gui_preserved": True, "status": "completed", "error": None}
                steps.append(step)
            write("steps.json", encoded(steps))
            preflight_path = Path(folder) / "PURE-preflight.json"
            invocation = {"schema": "i03-var05-in-zero-invocation/v1",
                "run_id": run.name, "original_run_dir": str(run), "session_id": 0,
                "ssh_ancestors": ["sshd.exe"],
                "queue_mutex": r"Global\SimloxIssue18NativeQueue",
                "working_directory": r"C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace",
                "gui": {"pid": 13340, "session_id": 1,
                    "start_unix_ms": 1790590196826, "responding": True},
                "manifest_sha256": reader.sha(manifest_raw),
                "approval_sha256": reader.sha(approval_raw),
                "approved_preflight_sha256": reader.sha(preflight_raw),
                "approved_preflight_path": str(preflight_path),
                "independent_replay_sha256": source_map["independent_replay"],
                "runner_script_sha256": source_map["runner_script"],
                "contract_sha256": reader.V4_SHA, "input_sha256": input_sha,
                "source_hashes_before": source_map,
                "planned_commands": [plan[i] for i in (0, 1, 3, 4)],
                "planned_checkers": [plan[i] for i in (2, 5)],
                "publication_state": "not_published"}
            write("invocation.json", encoded(invocation))
            def reseal():
                raw = {p.name: reader.file_pin(p) for p in run.iterdir()
                    if p.is_file() and p.name not in ("invocation.json", "closure.json")}
                closure = {"schema": "i03-var05-in-zero-closure/v1", "run_id": run.name,
                    "manifest_sha256": reader.sha(manifest_raw),
                    "approval_sha256": reader.sha(approval_raw),
                    "approved_preflight_sha256": reader.sha(preflight_raw),
                    "invocation_sha256": reader.sha((run / "invocation.json").read_bytes()),
                    "source_hashes_before": source_map, "source_hashes_after": source_map,
                    "raw": raw, "step_error": None, "error": None,
                    "publication_state": "not_published"}
                write("closure.json", encoded(closure))
                return raw
            raw = reseal()
            files, verified_raw, _ = reader.run_inventory_and_steps(
                manifest_raw, source_map, approval_raw, {}, preflight_raw,
                preflight_path, reader.Audit())
            reader.sealed_content(pure, source_map, files, verified_raw, reader.Audit())
            # The closure is rebuilt after each mutation, so semantic rejection
            # cannot be credited to an obsolete raw SHA.
            original_report = (run / "report-raw.json").read_bytes()
            report_mutated = copy.deepcopy(child_report)
            report_mutated["report"]["tables"][4]["instances"][0]["rows"][20][4] = 0
            write("report-raw.json", encoded(report_mutated))
            reseal()
            files, verified_raw, _ = reader.run_inventory_and_steps(
                manifest_raw, source_map, approval_raw, {}, preflight_raw,
                preflight_path, reader.Audit())
            rejects("sealed_report_cell_after_reseal", lambda: reader.sealed_content(
                pure, source_map, files, verified_raw, reader.Audit()), rejected)
            write("report-raw.json", original_report)
            reseal()
            return 25
        finally:
            os.chmod(run / "model-run.log", 0o666)
            reader.RUN = original_run


def main():
    baseline = reader.Audit()
    pure = reader.pure_source_event_report(baseline)
    contract, parent, prediction = pure["contract"], pure["parent"], pure["prediction"]
    canonical = pure["canonical_report"]
    child_report = reader.make_pure_child_report(contract, canonical)
    _, lines = reader.predicted_log_lines(reader.Audit())
    rejected = []

    parser_bad = {
        "duplicate_json_key": b'{"model":{},"model":{}}',
        "nan_constant": b'{"model":NaN}',
        "infinity_constant": b'{"model":Infinity}',
        "overflow_exponent": b'{"model":{"x":1e999}}',
        "malformed_root": b'["model"]',
    }
    for name, raw in parser_bad.items():
        if name == "malformed_root":
            rejects(name, lambda raw=raw: reader.recursive_same(reader.parse_json(raw), prediction, reader.Audit()), rejected)
        else:
            rejects(name, lambda raw=raw: reader.parse_json(raw), rejected)
    rejects("extra_native_trailing_comma", lambda: reader.parse_json(b'{"report":{"tables":[],},}', native=True), rejected)

    archive = reader.parse_json((reader.CASE / "preserved-context/c017.bytes").read_bytes())
    live = reader.parse_json((reader.ROOT / "cases/simlox-air-support/publication-index-v1.json").read_bytes())
    current_audit = reader.Audit()
    reader.catalog_semantics(archive, live, current_audit)
    appended = copy.deepcopy(live)
    synthetic = copy.deepcopy(appended["entries"][-1])
    synthetic["publication_id"] = "I03.var05.synthetic_append_in_memory_only"
    appended["entries"].append(synthetic)
    append_audit = reader.Audit()
    reader.catalog_semantics(archive, appended, append_audit)
    assert append_audit.checks == current_audit.checks, "valid append must not drop a catalog check"
    for name, mutation in (
        ("catalog_prefix_value", lambda d: d["entries"][0].__setitem__("publication_id", "wrong")),
        ("catalog_metadata_type", lambda d: d.__setitem__("catalog_snapshot", True)),
        ("catalog_duplicate_id", lambda d: d["entries"].append(copy.deepcopy(d["entries"][0]))),
        ("catalog_short_prefix", lambda d: d.__setitem__("entries", d["entries"][:493])),
    ):
        doc = copy.deepcopy(live)
        mutation(doc)
        rejects(name, lambda doc=doc: reader.catalog_semantics(archive, doc, reader.Audit()), rejected)

    source_mutations = {
        "TFDT_bool": lambda doc: doc["model"]["tables"][23]["instances"][0]["rows"][1].__setitem__(5, False),
        "TFDT_wrong_zero": lambda doc: doc["model"]["tables"][23]["instances"][0]["rows"][1].__setitem__(5, 0.5),
        "source_extra_table": lambda doc: doc["model"]["tables"].append(copy.deepcopy(doc["model"]["tables"][0])),
        "source_duplicate_instance": lambda doc: doc["model"]["tables"][23]["instances"].append(copy.deepcopy(doc["model"]["tables"][23]["instances"][0])),
        "source_database_bool": lambda doc: doc["model"].__setitem__("database_version", True),
        "source_extra_root_key": lambda doc: doc.__setitem__("extra", 1),
    }
    for name, mutation in source_mutations.items():
        doc = copy.deepcopy(prediction)
        mutation(doc)
        rejects(name, lambda doc=doc: reader.recursive_same(doc, prediction, reader.Audit()), rejected)

    accepted_export = reader.accepted_parent_roundtrip(parent, reader.Audit())
    export_mutations = {
        "export_duplicate_table": lambda doc: doc["model"]["tables"].append(copy.deepcopy(doc["model"]["tables"][0])),
        "export_bad_placeholder": lambda doc: doc["model"]["tables"][5]["instances"][0]["rows"][0].__setitem__(0, 0),
        "export_bool_double": lambda doc: doc["model"]["tables"][2]["instances"][0]["rows"][0].__setitem__(1, True),
        "export_column_key_type": lambda doc: doc["model"]["tables"][23]["columns"][0].__setitem__("key", 1),
        "export_wrong_instance": lambda doc: doc["model"]["tables"][23]["instances"][0].__setitem__("instance_name", "WRONG"),
    }
    for name, mutation in export_mutations.items():
        doc = copy.deepcopy(accepted_export)
        mutation(doc)
        raw = json.dumps(doc, ensure_ascii=False).encode()
        rejects(name, lambda raw=raw: reader.check_roundtrip(parent, raw, reader.Audit()), rejected)

    log_mutations = {
        "h10_printed_delay_half": ("transfer time: 0", "transfer time: 0.5"),
        "h10_arrival_late": ("Time: 10  resource transfer task 2 (IN)  arrives", "Time: 10.5  resource transfer task 2 (IN)  arrives"),
        "h10_receipt_wrong_quantity": ("transfer arrives: 1", "transfer arrives: 2"),
        "h8_release_free_two": ("available now: 1", "available now: 2"),
        "h8_backorder_missing": ("Resource transfer backorder removed", "Resource transfer backorder LOST"),
        "wrong_horizon": ("36", "35"),
        "other_event_unknown": ("mission starting, duration: 1", "mission starting, duration: 9"),
    }
    for name, (old, new) in log_mutations.items():
        change = list(lines)
        if name == "wrong_horizon":
            change[1] = new
        else:
            hits = [i for i, line in enumerate(change) if old in line]
            assert hits, (name, old)
            change[hits[0]] = change[hits[0]].replace(old, new, 1)
        raw = ("\n".join(change) + "\n").encode()
        rejects(name, lambda raw=raw: reader.check_typed_child_log(raw, reader.Audit()), rejected)
    for name, mutation in (
        ("duplicate_IN_receipt", lambda x: x.insert(next(i for i,v in enumerate(x) if "transfer arrives: 1" in v), next(v for v in x if "transfer arrives: 1" in v))),
        ("missing_IN_arrival", lambda x: x.pop(next(i for i,v in enumerate(x) if "task 2 (IN)  arrives" in v))),
        ("reorder_receipt_before_arrival", lambda x: x.insert(next(i for i,v in enumerate(x) if "task 2 (IN)  arrives" in v), x.pop(next(i for i,v in enumerate(x) if "transfer arrives: 1" in v)))),
        ("extra_same_template_ready", lambda x: x.append(next(v for v in x if "System ready" in v))),
    ):
        change = list(lines)
        mutation(change)
        raw = ("\n".join(change) + "\n").encode()
        rejects(name, lambda raw=raw: reader.check_typed_child_log(raw, reader.Audit()), rejected)
    def swap_lines(text, first, second):
        i = next(i for i, value in enumerate(text) if first in value)
        j = next(i for i, value in enumerate(text) if second in value)
        assert i != j
        text[i], text[j] = text[j], text[i]

    for name, first, second in (
        ("swap_h7_5_booking_owners", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> books resources", "subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> books resources"),
        ("h8_backorder_before_first_release", "Resource transfer backorder removed", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> frees resources"),
        ("h8_depart_before_second_release", "resource transfer task 1 (OUT)  starts with 1 resources", "subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> frees resources"),
    ):
        changed = list(lines)
        swap_lines(changed, first, second)
        raw = ("\n".join(changed) + "\n").encode()
        rejects(name, lambda raw=raw: reader.check_typed_child_log(raw, reader.Audit()), rejected)

    def report_change(name, table, row, column, value):
        doc = copy.deepcopy(child_report)
        t = next(t for t in doc["report"]["tables"] if t["name"] == table)
        ci = [c["name"] for c in t["columns"]].index(column)
        t["instances"][0]["rows"][row][ci] = value
        rejects(name, lambda doc=doc: reader.check_report(contract, "child", doc, canonical, reader.Audit()), rejected)

    report_change("NREP_float", "ResultSummary", 0, "NREP", 1.0)
    report_change("System_zero_residue", "SystemResults", 0, "NSYWR", 1e-9)
    report_change("System_identity_wrong", "SystemResults", 0, "UNID", "wrong")
    report_change("Stock_null_to_zero", "StockTotalResults", 0, "WTS", 0)
    report_change("Stock_presentation_wrong", "StockTotalResults", 0, "PNB", 0)
    report_change("Resource_h10_old", "ResourceResults", 20, "NR", 1)
    report_change("Resource_h10_nominal_old", "ResourceResults", 20, "NRN", 1)
    report_change("Resource_early_return", "ResourceResults", 19, "NRA", 2)
    report_change("Resource_wrong_identity", "ResourceResults", 20, "STID", "wrong")
    report_change("Total_null", "ResourceResultsTotal", 0, "NR", None)
    total = next(t for t in child_report["report"]["tables"] if t["name"] == "ResourceResultsTotal")
    cols = [c["name"] for c in total["columns"]]
    for name in ("NR", "NRA", "NRN", "NRUM", "NRW"):
        value = total["instances"][0]["rows"][0][cols.index(name)]
        for direction in (-1, 1):
            report_change(f"Total_{name}_{direction:+d}ULP", "ResourceResultsTotal", 0, name, f32_adjacent(value, direction))
    doc = copy.deepcopy(child_report)
    doc["report"]["tables"][2]["columns"][0]["key"] = 1
    rejects("report_bool_key_to_int", lambda: reader.check_report(contract, "child", doc, canonical, reader.Audit()), rejected)
    doc = copy.deepcopy(child_report)
    doc["report"]["tables"].append(copy.deepcopy(doc["report"]["tables"][0]))
    rejects("report_extra_table", lambda: reader.check_report(contract, "child", doc, canonical, reader.Audit()), rejected)
    doc = copy.deepcopy(child_report)
    doc["report"]["tables"][4]["instances"][0]["rows"][20][4] = float("inf")
    rejects("report_nonfinite", lambda: reader.check_report(contract, "child", doc, canonical, reader.Audit()), rejected)

    # These are in-memory protocol fixtures, never an approval or native run.
    manifest_raw = b'{"synthetic":"protocol-only"}'
    source_map = {key: str(i) * 64 for i, key in enumerate((
        "runner_script", "behavior_validator", "execution_binding", "child_input",
        "independent_replay"), 1)}
    source_map_sha = reader.sha(json.dumps(source_map,
        separators=(",", ":")).encode())
    approval = {"schema": "i03-var05-in-zero-independent-prelaunch-go/v1",
        "decision": "GO_PRELAUNCH", "run_id": reader.RUN.name,
        "manifest_sha256": reader.sha(manifest_raw),
        "runner_sha256": source_map["runner_script"],
        "validator_sha256": source_map["behavior_validator"],
        "contract_sha256": reader.V4_SHA,
        "execution_binding_sha256": source_map["execution_binding"],
        "input_sha256": source_map["child_input"],
        "source_map_sha256": source_map_sha,
        "independent_replay_sha256": source_map["independent_replay"]}
    reader.approval_fields(approval, manifest_raw, source_map, source_map_sha, reader.Audit())
    for name, mutation in (
        ("approval_wrong_run", lambda d: d.__setitem__("run_id", "other")),
        ("approval_wrong_manifest", lambda d: d.__setitem__("manifest_sha256", "0" * 64)),
        ("approval_wrong_method", lambda d: d.__setitem__("independent_replay_sha256", "0" * 64)),
        ("approval_wrong_source_map", lambda d: d.__setitem__("source_map_sha256", "0" * 64)),
    ):
        doc = copy.deepcopy(approval)
        mutation(doc)
        rejects(name, lambda doc=doc: reader.approval_fields(
            doc, manifest_raw, source_map, source_map_sha, reader.Audit()), rejected)
    preflight = {"schema": "i03-var05-in-zero-ssh-preflight/v1",
        "run_id": reader.RUN.name, "manifest_sha256": reader.sha(manifest_raw),
        "source_map_sha256": source_map_sha, "source_hashes": source_map,
        "ssh_session": 0, "ps_major": 5, "mutex_free": True,
        "run_dirs_absent": True, "native_process_started": False,
        "wts_active_gui_count": 1, "ssh_ancestors": ["sshd.exe"],
        "gui": {"pid": 13340, "session_id": 1,
                "start_unix_ms": 1790590196826, "responding": True},
        "accepted_raw_seals": 112, "accepted_nonclosure_raw": 101,
        "accepted_closures": 7, "accepted_invocations": 4,
        "excluded_failed_witness_raw": 0, "total_original_raw": 112}
    reader.preflight_fields(preflight, manifest_raw, source_map, source_map_sha, reader.Audit())
    for name, mutation in (
        ("preflight_session_bool", lambda d: d.__setitem__("ssh_session", False)),
        ("preflight_wrong_gui", lambda d: d["gui"].__setitem__("pid", 1)),
        ("preflight_mutex_busy", lambda d: d.__setitem__("mutex_free", False)),
        ("preflight_native_started", lambda d: d.__setitem__("native_process_started", True)),
        ("preflight_wrong_source_map", lambda d: d["source_hashes"].__setitem__("child_input", "0" * 64)),
        ("preflight_wrong_raw_total", lambda d: d.__setitem__("total_original_raw", 111)),
        ("preflight_missing_sshd", lambda d: d.__setitem__("ssh_ancestors", ["powershell.exe"])),
    ):
        doc = copy.deepcopy(preflight)
        mutation(doc)
        rejects(name, lambda doc=doc: reader.preflight_fields(
            doc, manifest_raw, source_map, source_map_sha, reader.Audit()), rejected)
    clean_pin = {"bytes": 20, "sha256": "a" * 64}
    calc = {"converter_log_bytes": 20, "converter_log_sha256": "a" * 64,
            "converter_log_validated": True}
    reader.calc_seal_fields(calc, clean_pin, clean_pin, True, reader.Audit())
    for name, mutation in (
        ("calc_seal_wrong_bytes", lambda c, r: c.__setitem__("converter_log_bytes", 21)),
        ("calc_seal_wrong_sha", lambda c, r: c.__setitem__("converter_log_sha256", "b" * 64)),
        ("calc_seal_unvalidated", lambda c, r: c.__setitem__("converter_log_validated", False)),
        ("calc_closure_wrong_sha", lambda c, r: r.__setitem__("sha256", "b" * 64)),
    ):
        modified_calc, modified_raw = copy.deepcopy(calc), copy.deepcopy(clean_pin)
        mutation(modified_calc, modified_raw)
        rejects(name, lambda c=modified_calc, r=modified_raw: reader.calc_seal_fields(
            c, r, clean_pin, True, reader.Audit()), rejected)
    rejects("calc_log_not_readonly", lambda: reader.calc_seal_fields(
        calc, clean_pin, clean_pin, False, reader.Audit()), rejected)
    parent_converter = (reader.PARENT_RUN / "out_in-run.log").read_text(encoding="utf-8-sig")
    rebound = parent_converter.replace(str(reader.PARENT_RUN), str(reader.RUN)).replace(
        str(reader.PARENT_RUN).replace("\\", "/"), str(reader.RUN).replace("\\", "/"))
    rebound = rebound.replace("out_in.sxi", "model.sxi").replace("out_in.sxo", "model.sxo")
    reader.check_converter_log(rebound.encode(), reader.Audit())
    for name, old, new in (
        ("converter_stale_input", "model.sxi", "old.sxi"),
        ("converter_wrong_warning", "warning #126", "warning #999"),
        ("converter_extra_note", "Form: System", "rec 1: (note #999) injected\nForm: System"),
        ("converter_wrong_count", "Warnings: 2", "Warnings: 3"),
    ):
        candidate = rebound.replace(old, new, 1).encode()
        rejects(name, lambda data=candidate: reader.check_converter_log(data, reader.Audit()), rejected)

    synthetic_files = synthetic_sealed_protocol(pure, rejected)

    print(json.dumps({"decision": "STATIC_ONLY_SELF_CHECK", "baseline_checks": baseline.checks,
        "parent_report_cells": pure["parent_report_cells"],
        "prospective_child_report_cells": pure["prospective_child_report_cells"],
        "semantic_rejections": len(rejected), "rejected": rejected,
        "scratch_protocol_files": synthetic_files, "native_started": False}, sort_keys=True))


if __name__ == "__main__":
    main()

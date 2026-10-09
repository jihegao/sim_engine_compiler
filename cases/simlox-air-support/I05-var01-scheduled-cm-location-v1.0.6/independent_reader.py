"""Independent full-log and typed-report replay for I05.var01 v1.0.6."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINS = json.loads((HERE / "parent-evidence-pins.json").read_text(encoding="utf-8"))
CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
EVENT = json.loads((HERE / "event-oracle.json").read_text(encoding="utf-8"))
REPORT = json.loads((HERE / "report-oracle.json").read_text(encoding="utf-8"))
PARENT_RUN = Path(PINS["accepted_d06_run"]["original_run_directory"])
PARENT_LOG = PARENT_RUN / "model.log"
PARENT_REPORT = PARENT_RUN / "report-raw.json"
PROJECTION_PATH = HERE / REPORT["parent_projection"]["path"]
PROJECTION_SHA = REPORT["parent_projection"]["sha256"]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def remove_exporter_trailing_commas(raw: bytes) -> bytes:
    """Normalize a private parse buffer only; callers retain the raw bytes."""
    return re.sub(rb",(?=\s*[}\]])", b"", raw)


def read_parent_raws() -> tuple[bytes, bytes]:
    log = PARENT_LOG.read_bytes()
    report = PARENT_REPORT.read_bytes()
    log_pin = PINS["accepted_d06_run"]["model_log"]
    report_pin = PINS["accepted_d06_run"]["report_raw"]
    if len(log) != log_pin["bytes"] or sha(log) != log_pin["sha256"]:
        raise ValueError("accepted D06 parent model.log byte pin differs")
    if len(report) != report_pin["bytes"] or sha(report) != report_pin["sha256"]:
        raise ValueError("accepted D06 parent report raw byte pin differs")
    return log, report


def expected_child_log(parent: bytes) -> bytes:
    """Apply only the four declared child substitutions, preserving line endings."""
    lines = parent.splitlines(keepends=True)
    for change in EVENT["line_substitutions"]:
        old = change["parent"].encode("utf-8")
        new = change["child"].encode("utf-8")
        hits = 0
        for index, line in enumerate(lines):
            body = line.rstrip(b"\r\n")
            ending = line[len(body):]
            if body == old:
                lines[index] = new + ending
                hits += 1
        if hits != 1:
            raise ValueError(f"parent log must contain one exact {change['event']} source line; found {hits}")
    return b"".join(lines)


def parse_report(raw: bytes) -> dict:
    parsed = json.loads(remove_exporter_trailing_commas(raw).decode("utf-8-sig"))
    if set(parsed) != {"report"} or set(parsed["report"]) != {"tables"}:
        raise ValueError("report root/schema differs")
    return parsed


def projection() -> dict:
    raw = PROJECTION_PATH.read_bytes()
    if sha(raw) != PROJECTION_SHA:
        raise ValueError("pinned parent report projection SHA differs")
    value = json.loads(raw.decode("utf-8"))
    if value.get("typed_cell_count") != REPORT["full_scope_count"]:
        raise ValueError("parent projection typed-cell count differs")
    return value


def table_rows(tables: list[dict], name: str) -> tuple[list[dict], list[list[object]]]:
    found = [table for table in tables if table.get("name") == name]
    if len(found) != 1 or len(found[0].get("instances", [])) != 1:
        raise ValueError(f"report must contain one {name} table and one instance")
    return found[0]["columns"], found[0]["instances"][0]["rows"]


def projected_child_tables() -> list[dict]:
    baseline = projection()["tables"]
    result = copy.deepcopy(baseline)
    pd, pd_rows = table_rows(result, "ProblemDescription")
    if [column["name"] for column in pd] != ["PDESC"] or len(pd_rows) != 1:
        raise ValueError("parent ProblemDescription topology differs")
    pd_rows[0][0] = CONTRACT["candidate"]["description"]

    system_columns, system_rows = table_rows(result, "SystemResults")
    _, baseline_system_rows = table_rows(baseline, "SystemResults")
    positions = {column["name"]: index for index, column in enumerate(system_columns)}
    if not {"STINT", "ETINT"}.issubset(positions):
        raise ValueError("SystemResults interval keys are missing")
    for rule in REPORT["system_row_projection"]:
        target = [row for row in system_rows
                  if row[positions["STINT"]] == rule["target_interval"][0]
                  and row[positions["ETINT"]] == rule["target_interval"][1]]
        source = [row for row in baseline_system_rows
                  if row[positions["STINT"]] == rule["source_interval"][0]
                  and row[positions["ETINT"]] == rule["source_interval"][1]]
        if len(target) != 1 or len(source) != 1:
            raise ValueError(f"report interval projection is ambiguous: {rule}")
        target_row, source_row = target[0], source[0]
        start, end = target_row[positions["STINT"]], target_row[positions["ETINT"]]
        if len(target_row) != len(source_row):
            raise ValueError("SystemResults projected row width differs")
        target_row[:] = source_row[:]
        target_row[positions["STINT"]] = start
        target_row[positions["ETINT"]] = end
    downtime = REPORT["system_downtime_projection"]
    periods = downtime["periods"]
    if any(type(p["start"]) not in (int, float) or type(p["end"]) not in (int, float)
           or p["end"] <= p["start"] for p in periods):
        raise ValueError("invalid frozen completed downtime period")
    for row in system_rows:
        starts = [p for p in periods if row[positions["STINT"]] <= p["start"] < row[positions["ETINT"]]]
        row[positions["NSYDT"]] = len(starts)
        row[positions["SYDT"]] = (sum(p["end"] - p["start"] for p in starts) / len(starts)) if starts else None
    if sum(row[positions["NSYDT"]] for row in system_rows) != len(periods):
        raise ValueError("downtime period is outside the declared result bins")
    return result


def typed_cell_count(tables: list[dict]) -> int:
    total = 0
    for table in tables:
        columns, rows = table_rows(tables, table["name"])
        if any(len(row) != len(columns) for row in rows):
            raise ValueError(f"{table['name']} contains a wrong-width row")
        total += len(columns) * len(rows)
    return total


def log_semantics_pass(raw: bytes, arm: str) -> bool:
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    expected_duration = "0.5" if arm == "parent" else "1.5"
    expected_complete = ["10.5", "34.5"] if arm == "parent" else ["11.5", "35.5"]
    failures = re.findall(r"^Time: ([\d.]+) <TEACH-AIR-01,0> critical CM failure mode added", text, re.M)
    starts = re.findall(r"^Time: ([\d.]+)  system CM task \d+ on <TEACH-AIR-01,0> started$", text, re.M)
    task_completions = re.findall(r"^Time: ([\d.]+)  system CM task \d+ on <TEACH-AIR-01,0> completed$", text, re.M)
    work = re.findall(r"^Time: ([\d.]+)  subtask \d+ seqno 0 within system CM task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for ([\d.]+) hours$", text, re.M)
    subtask_completions = re.findall(r"^Time: ([\d.]+)  subtask \d+ seqno 0 within system CM task \d+ on <TEACH-AIR-01,0> completed$", text, re.M)
    mission_aborts = re.findall(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission aborted:", text, re.M)
    mission_successes = re.findall(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:", text, re.M)
    mode_rows = re.findall(r"Failure Mode: FM-POS-A on materiel: <POS-A,0>", text)
    at_hour_five = re.findall(r"^Time: 5(?:\.0+)?(?:\s|$)", text, re.M)
    return (failures == ["9.8829", "33.8602"]
            and starts == ["10", "34"]
            and task_completions == expected_complete
            and [duration for _, duration in work] == [expected_duration, expected_duration]
            and [when for when, _ in work] == ["10", "34"]
            and subtask_completions == expected_complete
            and mission_aborts == failures
            and mission_successes == ["22"]
            and len(mode_rows) == 4
            and not at_hour_five)


def validate_log(raw: bytes, arm: str, parent: bytes) -> bool:
    if arm == "parent":
        return raw == parent and log_semantics_pass(raw, "parent")
    if arm == "child":
        return raw == expected_child_log(parent) and log_semantics_pass(raw, "child")
    raise ValueError(f"unknown log arm {arm}")


def reconciliation_passes(raw: bytes) -> bool:
    actual = child_reconciliation(raw)
    expected = REPORT["expected_child_reconciliation"]
    return (actual["failure_rows"] == expected["failure_rows"]
            and actual["repair_completion_rows"] == expected["repair_completion_rows"]
            and abs(actual["repair_aircraft_hours"] - expected["repair_aircraft_hours"]) <= 1e-6
            and actual["downtime_period_count"] == expected["downtime_period_count"]
            and abs(actual["registered_downtime_hours"] - expected["registered_downtime_hours"]) <= 1e-6
            and actual["terminal_ready"] == expected["terminal_ready"]
            and actual["terminal_in_repair"] == expected["terminal_in_repair"]
            and actual["stock_totals"] == expected["stock_totals"]
            and actual["summary_mission_success_fraction"] == expected["summary_mission_success_fraction"]
            and actual["problem_description"] == CONTRACT["candidate"]["description"])


def typed_structure_equal(actual: object, expected: object) -> bool:
    """Compare JSON structures without Python's bool/int/float equality aliases."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            typed_structure_equal(actual[key], expected[key]) for key in expected)
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            typed_structure_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def validate_report(raw: bytes, arm: str) -> bool:
    actual = parse_report(raw)["report"]["tables"]
    expected = projection()["tables"] if arm == "parent" else projected_child_tables()
    base_pass = typed_cell_count(actual) == REPORT["full_scope_count"] and typed_structure_equal(actual, expected)
    return base_pass and (arm == "parent" or reconciliation_passes(raw))


def child_reconciliation(raw: bytes) -> dict:
    tables = parse_report(raw)["report"]["tables"]
    system_columns, system_rows = table_rows(tables, "SystemResults")
    values = [dict(zip([c["name"] for c in system_columns], row, strict=True)) for row in system_rows]
    stock_columns, stock_rows = table_rows(tables, "StockTotalResults")
    stock = [dict(zip([c["name"] for c in stock_columns], row, strict=True)) for row in stock_rows]
    summary_columns, summary_rows = table_rows(tables, "ResultSummary")
    summary = dict(zip([c["name"] for c in summary_columns], summary_rows[0], strict=True))
    hours = sum((row["NSYRP"] or 0) * (row["ETINT"] - row["STINT"]) for row in values)
    totals = {field: sum(row[field] or 0 for row in stock)
              for field in ("NBO", "NDD", "NDR", "NDP", "NLD")}
    return {
        "failure_rows": sum(row["NFAIL"] or 0 for row in values),
        "repair_completion_rows": sum(row["NREPT"] or 0 for row in values),
        "repair_aircraft_hours": hours,
        "downtime_period_count": sum(row["NSYDT"] for row in values),
        "registered_downtime_hours": sum(row["SYDT"] * row["NSYDT"] for row in values if row["SYDT"] is not None),
        "terminal_ready": values[-1]["NSYRY"],
        "terminal_in_repair": values[-1]["NSYRP"],
        "stock_totals": totals,
        "summary_mission_success_fraction": summary["MSUF"],
        "problem_description": table_rows(tables, "ProblemDescription")[1][0][0],
    }


def self_check() -> dict:
    parent_log, parent_report = read_parent_raws()
    child_log = expected_child_log(parent_log)
    parent_tables = projection()["tables"]
    child_tables = projected_child_tables()
    child_report = (json.dumps({"report": {"tables": child_tables}}, ensure_ascii=False,
                               separators=(",", ":")) + "\n").encode("utf-8")
    checks = {
        "parent_log_parent_arm_positive": validate_log(parent_log, "parent", parent_log),
        "synthetic_child_log_child_arm_positive": validate_log(child_log, "child", parent_log),
        "parent_log_child_arm_negative": not validate_log(parent_log, "child", parent_log),
        "synthetic_child_log_parent_arm_negative": not validate_log(child_log, "parent", parent_log),
        "parent_report_parent_arm_positive": validate_report(parent_report, "parent"),
        "synthetic_child_report_child_arm_positive": validate_report(child_report, "child"),
        "parent_report_child_arm_negative": not validate_report(parent_report, "child"),
        "synthetic_child_report_parent_arm_negative": not validate_report(child_report, "parent"),
    }
    def wrong_duration_mutant(raw: bytes, arm: str, wrong_duration: str) -> tuple[bytes, dict]:
        matches = [item for item in EVENT["line_substitutions"] if item["event"] == "task_0_subtask_duration"]
        if len(matches) != 1: raise ValueError("duration mutant requires exactly one task_0_subtask_duration oracle")
        expected_line = matches[0][arm]
        prefix = "planned to last for "
        if expected_line.count(prefix) != 1 or not expected_line.endswith(" hours"):
            raise ValueError("duration mutant source line lacks one terminal duration literal")
        correct = expected_line.rsplit(prefix, 1)[1][:-len(" hours")]
        old_literal, new_literal = prefix + correct + " hours", prefix + wrong_duration + " hours"
        if correct == wrong_duration or expected_line.count(old_literal) != 1:
            raise ValueError("duration mutant must change one distinct duration literal")
        mutated_line = expected_line.replace(old_literal, new_literal, 1)
        before = raw.splitlines(keepends=True)
        after = list(before)
        hits, changed_line = 0, None
        for index, line in enumerate(before):
            body = line.rstrip(b"\r\n"); ending = line[len(body):]
            if body == expected_line.encode("utf-8"):
                after[index] = mutated_line.encode("utf-8") + ending; hits += 1; changed_line = index + 1
        if hits != 1: raise ValueError(f"duration mutant must identify one {arm} target line; found {hits}")
        mutated = b"".join(after)
        changed = [i for i,(a,b) in enumerate(zip(before,after,strict=True)) if a != b]
        verified = (len(before)==len(after) and changed==[changed_line-1]
                    and before[changed_line-1].rstrip(b"\r\n")==expected_line.encode("utf-8")
                    and after[changed_line-1].rstrip(b"\r\n")==mutated_line.encode("utf-8")
                    and mutated_line==expected_line.replace(old_literal,new_literal,1))
        audit={'event':'task_0_subtask_duration','arm':arm,'line_number_1_based':changed_line,
               'original_duration_hours':correct,'mutated_duration_hours':wrong_duration,
               'old_literal':old_literal,'new_literal':new_literal,'target_line_occurrences':hits,
               'changed_line_count':len(changed),'line_count_preserved':len(before)==len(after),
               'non_target_lines_byte_identical':len(changed)==1 and changed==[changed_line-1],
               'mutation_target_verified':verified,
               'original_line_sha256':hashlib.sha256(before[changed_line-1]).hexdigest(),
               'mutated_line_sha256':hashlib.sha256(after[changed_line-1]).hexdigest()}
        if not verified: raise AssertionError("duration mutant changed bytes outside its single duration target")
        return mutated,audit

    wrong_child, child_duration_audit = wrong_duration_mutant(child_log, "child", "0.25")
    checks["wrong_child_duration_negative"] = (child_duration_audit["mutation_target_verified"]
                                                and not validate_log(wrong_child, "child", parent_log))
    wrong_completion = child_log.replace(EVENT["line_substitutions"][3]["child"].encode("utf-8"),
                                         EVENT["line_substitutions"][3]["parent"].encode("utf-8"), 1)
    checks["wrong_child_system_completion_negative"] = not validate_log(wrong_completion, "child", parent_log)
    wrong_postrepair = child_log.replace(EVENT["line_substitutions"][4]["child"].encode("utf-8"),
                                         EVENT["line_substitutions"][4]["parent"].encode("utf-8"), 1)
    checks["wrong_child_postrepair_timestamp_negative"] = not validate_log(wrong_postrepair, "child", parent_log)
    wrong_parent, parent_duration_audit = wrong_duration_mutant(parent_log, "parent", "0.25")
    checks["wrong_parent_duration_negative"] = (parent_duration_audit["mutation_target_verified"]
                                                 and not validate_log(wrong_parent, "parent", parent_log))
    mutated_tables = copy.deepcopy(child_tables)
    mutant_columns, mutant_rows = table_rows(mutated_tables, "SystemResults")
    nsyrp = next(i for i, column in enumerate(mutant_columns) if column["name"] == "NSYRP")
    target_index = next(i for i, row in enumerate(mutant_rows) if row[2:4] == [10.5, 11.0])
    mutant_rows[target_index][nsyrp] = 0
    mutant_report = (json.dumps({"report": {"tables": mutated_tables}}, ensure_ascii=False,
                                separators=(",", ":")) + "\n").encode("utf-8")
    checks["wrong_extension_cell_negative"] = not validate_report(mutant_report, "child")
    completion_mutant = copy.deepcopy(child_tables)
    completion_columns, completion_rows = table_rows(completion_mutant, "SystemResults")
    completion_positions = {column["name"]: index for index, column in enumerate(completion_columns)}
    completion_row = next(row for row in completion_rows
                          if row[completion_positions["STINT"]] == 11.5
                          and row[completion_positions["ETINT"]] == 12.0)
    completion_row[completion_positions["NREPT"]] = 0
    completion_report = (json.dumps({"report": {"tables": completion_mutant}}, ensure_ascii=False,
                                    separators=(",", ":")) + "\n").encode("utf-8")
    checks["wrong_completion_count_negative"] = not validate_report(completion_report, "child")
    float_mutant = copy.deepcopy(parent_tables)
    float_columns, float_rows = table_rows(float_mutant, "SystemResults")
    float_pos = {column["name"]: index for index, column in enumerate(float_columns)}
    base_row = next(row for row in float_rows if row[float_pos["STINT"]] == 0.0)
    if type(base_row[float_pos["NSYRY"]]) is not int:
        raise ValueError("parent NSYRY type-mutant fixture is no longer an integer token")
    base_row[float_pos["NSYRY"]] = float(base_row[float_pos["NSYRY"]])
    float_report = (json.dumps({"report": {"tables": float_mutant}}, ensure_ascii=False,
                               separators=(",", ":")) + "\n").encode("utf-8")
    checks["int_to_float_alias_negative"] = not validate_report(float_report, "parent")
    bool_mutant = copy.deepcopy(parent_tables)
    stock_columns, stock_rows = table_rows(bool_mutant, "StockTotalResults")
    stock_pos = {column["name"]: index for index, column in enumerate(stock_columns)}
    stock_rows[0][stock_pos["NBO"]] = False
    bool_report = (json.dumps({"report": {"tables": bool_mutant}}, ensure_ascii=False,
                              separators=(",", ":")) + "\n").encode("utf-8")
    checks["int_to_bool_alias_negative"] = not validate_report(bool_report, "parent")
    metadata_mutant = copy.deepcopy(parent_tables)
    system_table = next(table for table in metadata_mutant if table["name"] == "SystemResults")
    if system_table["columns"][0].get("key") is not True:
        raise ValueError("parent SystemResults key metadata mutant is no longer boolean true")
    system_table["columns"][0]["key"] = 1
    metadata_report = (json.dumps({"report": {"tables": metadata_mutant}}, ensure_ascii=False,
                                  separators=(",", ":")) + "\n").encode("utf-8")
    checks["metadata_bool_to_int_alias_negative"] = not validate_report(metadata_report, "parent")
    def report_mutation(name: str, table_name: str, interval: float, column_name: str, value: object) -> None:
        mutated = copy.deepcopy(child_tables)
        columns, rows = table_rows(mutated, table_name)
        by_name = {column["name"]: i for i, column in enumerate(columns)}
        row = next(row for row in rows if row[by_name["STINT"]] == interval)
        old = row[by_name[column_name]]
        if typed_structure_equal(old, value):
            raise ValueError("negative report mutation did not change the target")
        row[by_name[column_name]] = value
        raw = json.dumps({"report": {"tables": mutated}}, ensure_ascii=False).encode("utf-8")
        checks[name] = not validate_report(raw, "child")
    report_mutation("wrong_start_bin_downtime_negative", "SystemResults", 10.0, "SYDT", 0.5)
    report_mutation("fake_continuation_downtime_count_negative", "SystemResults", 10.5, "NSYDT", 1)
    report_mutation("nonnull_continuation_downtime_negative", "SystemResults", 11.0, "SYDT", 0.5)
    report_mutation("wrong_second_start_count_negative", "SystemResults", 34.0, "NSYDT", 0)
    report_mutation("unrelated_stock_cell_negative", "StockTotalResults", 0.0, "NBO", 1)
    if not all(checks.values()):
        raise AssertionError({key: value for key, value in checks.items() if not value})
    return {"decision": "GO_METHOD_REPLAY" if all(checks.values()) else "NO_GO",
            "checks_passed": sum(checks.values()), "checks_total": len(checks),
            "checks": checks, "duration_mutation_audits": {"child": child_duration_audit, "parent": parent_duration_audit},
            "synthetic_report_reconciliation": child_reconciliation(child_report),
            "native_dispatch": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--arm", choices=("parent", "child"))
    parser.add_argument("--model-log", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        if args.self_check:
            result = self_check()
        else:
            if not args.arm or not args.model_log or not args.report:
                parser.error("--arm, --model-log and --report are required outside --self-check")
            parent_log, _ = read_parent_raws()
            log_raw = args.model_log.read_bytes()
            report_raw = args.report.read_bytes()
            log_ok = validate_log(log_raw, args.arm, parent_log)
            report_ok = validate_report(report_raw, args.arm)
            result = {"decision": "GO_BOUNDED" if log_ok and report_ok else "NO_GO",
                      "arm": args.arm, "model_log_sha256": sha(log_raw),
                      "report_raw_sha256": sha(report_raw), "log_projection_passed": log_ok,
                      "full_typed_report_projection_passed": report_ok,
                      "report_cell_count": typed_cell_count(parse_report(report_raw)["report"]["tables"])}
            if args.arm == "child" and report_ok:
                result["reconciliation"] = child_reconciliation(report_raw)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["decision"] != "NO_GO" else 1
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        print(json.dumps({"decision": "NO_GO", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
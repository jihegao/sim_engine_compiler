"""Independent, standard-library-only replay of the three G06.var04 native runs.

Reads frozen sources and raw native artifacts. Writes only the adjacent verdict JSON.
It intentionally imports none of the candidate's builder, checker, or validator code.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
OUT = Path(__file__).with_name("independent-readonly-2026-10-02.json")
SOURCES = {
    "continuous_Y": ROOT / "G05-unavailable-standby-v1.0.3" / "unavailable-input.json",
    "fixed_Y": CASE / "fixed-input.json",
    "fixed_N": CASE / "fixed-deferred-input.json",
}
RUNS = {
    "continuous_Y": ROOT / "G05-unavailable-standby-v1.0.3" / "runs" / "g05-unavailable-v103-ssh-20261002-01",
    "fixed_Y": CASE / "runs" / "g06-fixed-y-v100-ssh-20261002-01",
    "fixed_N": CASE / "runs" / "g06-fixed-n-v100-ssh-20261002-01",
}
EXPECTED_SOURCE_SHA = {
    "continuous_Y": "b0d79caeb71dbf991291b9122dff3139bc52c27e2c014b5bf624632539101f0d",
    "fixed_Y": "ce407655c86e0af85460ba30d32eb28ffc93f54c1acc68bbf4d6fcbee79e723b",
    "fixed_N": "06a3cb45320c90f4a90027f562c17e86be46b25bd62b9106b1f6ab0cbcc99aa8",
}
STEP_NAMES = ["import", "export", "calc", "jsonreport", "check_import_export"]
REPORT_NAMES = ["ResultSummary", "SystemResults", "StockTotalResults"]


class Checks:
    def __init__(self) -> None:
        self.total = 0
        self.failures: list[str] = []

    def test(self, condition: bool, label: str) -> None:
        self.total += 1
        if not condition:
            self.failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_bytes())


def report_tables(path: Path) -> dict:
    # This native exporter sometimes leaves terminal commas. Repair only in memory.
    raw = path.read_text(encoding="utf-8-sig")
    parsed = json.loads(re.sub(r",(?=\s*[}\]])", "", raw))
    return {table["name"]: table for table in parsed["report"]["tables"]}


def source_tables(document: dict) -> dict:
    return {table["name"]: table for table in document["model"]["tables"]}


def authored_tables(document: dict) -> dict:
    return {
        name: table
        for name, table in source_tables(document).items()
        if any(instance["rows"] for instance in table["instances"])
    }


def rows(table: dict) -> list:
    assert len(table["instances"]) == 1
    return table["instances"][0]["rows"]


def named_rows(table: dict) -> tuple[list[str], list]:
    return [column["name"] for column in table["columns"]], rows(table)


def times(log: str, pattern: str) -> list[float]:
    return [float(x) for x in re.findall(pattern, log, flags=re.MULTILINE)]


def cm_times(log: str) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
    started: dict[str, list[float]] = {"FM-POS-A": [], "FM-POS-B": []}
    complete: dict[str, list[float]] = {"FM-POS-A": [], "FM-POS-B": []}
    task_mode: dict[str, str] = {}
    lines = log.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"Time: ([\d.]+)\s+system CM task (\d+) on .* started$", line)
        if match and index + 1 < len(lines):
            next_line = lines[index + 1]
            mode_match = re.match(
                r"Time: [\d.]+\s+system CM task " + match.group(2)
                + r" on .* FMID: (FM-POS-[AB])$", next_line
            )
            if mode_match:
                mode = mode_match.group(1)
                task_mode[match.group(2)] = mode
                started[mode].append(float(match.group(1)))
        done = re.match(r"Time: ([\d.]+)\s+system CM task (\d+) on .* completed$", line)
        if done and done.group(2) in task_mode:
            complete[task_mode[done.group(2)]].append(float(done.group(1)))
    return started, complete


def close(a: float, b: float, tolerance: float = 0.00011) -> bool:
    return abs(a - b) <= tolerance


def one_at(values: list[float], expected: float) -> bool:
    return len(values) == 1 and close(values[0], expected)


def compare_cells(checks: Checks, first: dict, second: dict, label: str,
                  expected_differences: dict[tuple[str, int, str], tuple] | None = None) -> int:
    expected_differences = expected_differences or {}
    seen: set[tuple[str, int, str]] = set()
    actual_difference_count = 0
    for name in REPORT_NAMES:
        left, right = first[name], second[name]
        columns = [column["name"] for column in left["columns"]]
        checks.test(columns == [column["name"] for column in right["columns"]], f"{label} {name} columns")
        first_rows, second_rows = rows(left), rows(right)
        checks.test(len(first_rows) == len(second_rows), f"{label} {name} row count")
        for row_index, (a_row, b_row) in enumerate(zip(first_rows, second_rows)):
            checks.test(len(a_row) == len(b_row), f"{label} {name} row {row_index} width")
            for column_index, (a_value, b_value) in enumerate(zip(a_row, b_row)):
                key = (name, row_index, columns[column_index])
                if a_value != b_value:
                    actual_difference_count += 1
                if key in expected_differences:
                    seen.add(key)
                    checks.test((a_value, b_value) == expected_differences[key], f"{label} {key} expected delta")
                else:
                    checks.test(a_value == b_value, f"{label} {key} equality")
    checks.test(seen == set(expected_differences), f"{label} all expected differences observed")
    return actual_difference_count


def main() -> None:
    checks = Checks()
    contract = load(CASE / "contract.json")
    exact_diff = load(CASE / "exact-diff.json")
    checks.test(contract["continuous_parent"]["sha256"] == EXPECTED_SOURCE_SHA["continuous_Y"], "contract parent hash")
    checks.test(contract["fixed_sources_sha256"]["Y"] == EXPECTED_SOURCE_SHA["fixed_Y"], "contract fixed Y hash")
    checks.test(contract["fixed_sources_sha256"]["N"] == EXPECTED_SOURCE_SHA["fixed_N"], "contract fixed N hash")
    checks.test(contract["exact_diff_sha256"] == sha(CASE / "exact-diff.json"), "contract exact diff hash")
    checks.test(exact_diff["parent_sha256"] == EXPECTED_SOURCE_SHA["continuous_Y"], "diff parent hash")
    checks.test(exact_diff["source_sha256"] == EXPECTED_SOURCE_SHA["fixed_Y"], "diff fixed Y hash")
    checks.test(exact_diff["deferred_sha256"] == EXPECTED_SOURCE_SHA["fixed_N"], "diff fixed N hash")

    documents = {name: load(path) for name, path in SOURCES.items()}
    table_sets = {name: source_tables(document) for name, document in documents.items()}
    for name, path in SOURCES.items():
        checks.test(sha(path) == EXPECTED_SOURCE_SHA[name], f"{name} frozen source hash")
        checks.test(len(authored_tables(documents[name])) == 23, f"{name} 23 authored tables")
    changed_parent_y = sorted(k for k in table_sets["continuous_Y"] if table_sets["continuous_Y"][k] != table_sets["fixed_Y"][k])
    changed_y_n = sorted(k for k in table_sets["fixed_Y"] if table_sets["fixed_Y"][k] != table_sets["fixed_N"][k])
    checks.test(changed_parent_y == ["MissionType", "ProblemDescription"], "continuous to fixed Y table delta")
    checks.test(changed_y_n == ["ProblemDescription", "RBDParallel"], "fixed Y to N table delta")
    for name, before, after in (
        ("parent_to_fixed", "continuous_Y", "fixed_Y"),
        ("fixed_y_to_n", "fixed_Y", "fixed_N"),
    ):
        for table_name, declared in exact_diff[name].items():
            checks.test(rows(table_sets[before][table_name]) == declared["before"], f"{name} {table_name} before")
            checks.test(rows(table_sets[after][table_name]) == declared["after"], f"{name} {table_name} after")
    mission_columns, parent_mission = named_rows(table_sets["continuous_Y"]["MissionType"])
    _, fixed_mission = named_rows(table_sets["fixed_Y"]["MissionType"])
    checks.test(parent_mission[0][mission_columns.index("MPAT")] == "CONTINUOUS", "parent continuous MPAT")
    checks.test(fixed_mission[0][mission_columns.index("MPAT")] is None, "fixed default MPAT")
    for field in ("TFOUT", "TFRET"):
        checks.test(parent_mission[0][mission_columns.index(field)] is None, f"parent {field} empty")
        checks.test(fixed_mission[0][mission_columns.index(field)] == 0.25, f"fixed {field} fraction")
    for name, expected in (("fixed_Y", "Y"), ("fixed_N", "N")):
        columns, value = named_rows(table_sets[name]["RBDParallel"])
        checks.test(value[0][columns.index("ONLM")] == expected, f"{name} ONLM")

    reports: dict[str, dict] = {}
    logs: dict[str, str] = {}
    fingerprints: dict[str, dict] = {}
    observed: dict[str, dict] = {}
    gui_ids: set[tuple] = set()
    for name, run in RUNS.items():
        closure = load(run / "closure.json")
        invocation = load(run / "invocation.json")
        steps = load(run / "steps.json")
        checks.test(closure["error"] is None, f"{name} closure error absent")
        checks.test(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{name} invocation seal")
        checks.test(closure["source_hashes_before"] == closure["source_hashes_after"], f"{name} stable source fingerprints")
        checks.test(closure["source_hashes_before"]["input"] == EXPECTED_SOURCE_SHA[name], f"{name} source fingerprint")
        checks.test(sha(run / "input.json") == EXPECTED_SOURCE_SHA[name], f"{name} copied source hash")
        checks.test(len(closure["raw"]) == 12, f"{name} twelve raw seals")
        for raw_name, seal in sorted(closure["raw"].items()):
            raw = run / raw_name
            checks.test(raw.exists(), f"{name} {raw_name} exists")
            if raw.exists():
                checks.test(raw.stat().st_size == seal["bytes"], f"{name} {raw_name} length")
                checks.test(sha(raw) == seal["sha256"], f"{name} {raw_name} sha")
        checks.test([step["name"] for step in steps] == STEP_NAMES, f"{name} five steps")
        for step in steps:
            checks.test(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True,
                        f"{name} {step['name']} completed and GUI preserved")
        checks.test(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0,
                    f"{name} session zero SSH")
        checks.test(invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"],
                    f"{name} sshd lineage")
        checks.test(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{name} host mutex")
        gui = invocation["gui"]
        checks.test(gui["pid"] == 13340 and gui["session_id"] > 0, f"{name} GUI PID/session")
        gui_ids.add((gui["pid"], gui["session_id"], gui["start_utc"]))
        if name != "continuous_Y":
            checks.test(closure["source_hashes_before"]["contract"] == sha(CASE / "contract.json"),
                        f"{name} frozen contract binding")
            checks.test(closure["source_hashes_before"]["exact_diff"] == sha(CASE / "exact-diff.json"),
                        f"{name} frozen diff binding")
        authored = authored_tables(load(run / "input.json"))
        exported = source_tables(load(run / "roundtrip-raw.json"))
        checks.test(len(authored) == 23, f"{name} 23 input row tables")
        for table_name, table in sorted(authored.items()):
            checks.test(table_name in exported and table == exported[table_name], f"{name} {table_name} exact roundtrip")
        run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        checks.test("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in run_log,
                    f"{name} zero converter errors one warning")
        checks.test("(warning #108)" in run_log, f"{name} warning 108 classified")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        logs[name] = log
        starts, completions = cm_times(log)
        event = {
            "mission_start": times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]* mission starting, duration:"),
            "mission_success": times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]* mission success:"),
            "mission_complete": times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]* mission completed:"),
            "B_to_A_start": times(log, r"Time: ([\d.]+) [^\n]*\[POS-B -> POS-A\]>. switch over started"),
            "B_to_A_stop": times(log, r"Time: ([\d.]+) [^\n]*\[POS-B -> POS-A\]>. Switch over stopped"),
            "A_to_C_start": times(log, r"Time: ([\d.]+) [^\n]*\[POS-A -> POS-C\]>. switch over started"),
            "A_to_C_stop": times(log, r"Time: ([\d.]+) [^\n]*\[POS-A -> POS-C\]>. Switch over stopped"),
            "cm_start": starts,
            "cm_complete": completions,
        }
        observed[name] = event
        for key, expected in (("mission_start", 8), ("mission_success", 34), ("mission_complete", 34),
                              ("B_to_A_start", 8.94145), ("B_to_A_stop", 9.44145),
                              ("A_to_C_start", 17.5636), ("A_to_C_stop", 18.0636)):
            checks.test(one_at(event[key], expected), f"{name} {key} timing")
        for mode in ("FM-POS-A", "FM-POS-B"):
            checks.test(f"Failure Mode: {mode}" in log, f"{name} {mode} fault identity")
        if name == "continuous_Y":
            checks.test(one_at(starts["FM-POS-B"], 8.94145), "continuous B CM starts at failure")
            checks.test(one_at(starts["FM-POS-A"], 17.5636), "continuous A CM starts at failure")
            checks.test(one_at(completions["FM-POS-A"], 18.0636), "continuous A CM completes online")
        else:
            checks.test(one_at(starts["FM-POS-B"], 34), f"{name} B CM starts on return")
            checks.test(one_at(starts["FM-POS-A"], 34), f"{name} A CM starts on return")
            checks.test(one_at(completions["FM-POS-A"], 34.5), f"{name} A CM completes on ground")
        checks.test(completions["FM-POS-B"] == [], f"{name} B CM still open at horizon")
        reports[name] = report_tables(run / "report-raw.json")
        checks.test(set(REPORT_NAMES).issubset(reports[name]), f"{name} report tables exist")
        checks.test(len(rows(reports[name]["ResultSummary"])) == 1, f"{name} one summary row")
        for report_name in ("SystemResults", "StockTotalResults"):
            series = rows(reports[name][report_name])
            checks.test(len(series) == 72, f"{name} {report_name} 72 intervals")
            columns = [column["name"] for column in reports[name][report_name]["columns"]]
            for index, series_row in enumerate(series):
                checks.test(close(series_row[columns.index("STINT")], index * .5, 1e-8),
                            f"{name} {report_name} interval {index} start")
                checks.test(close(series_row[columns.index("ETINT")], (index + 1) * .5, 1e-8),
                            f"{name} {report_name} interval {index} end")
        stock_cols, stock_rows = named_rows(reports[name]["StockTotalResults"])
        for index, stock_row in enumerate(stock_rows):
            for column in ("NBO", "WT"):
                checks.test(stock_row[stock_cols.index(column)] in (0, None), f"{name} stock {index} {column} zero")
        summary_cols, summary_rows = named_rows(reports[name]["ResultSummary"])
        summary = dict(zip(summary_cols, summary_rows[0]))
        checks.test(summary["NREP"] == 1 and summary["MTMF"] == 1, f"{name} one replication and MTMF")
        checks.test(close(summary["STMF"], 25 / 26, 1e-6), f"{name} STMF 25/26")
        checks.test((summary["MSTF"], summary["MSUF"]) == ((0, 0) if name == "continuous_Y" else (1, 1)),
                    f"{name} native summary classification")
        system_cols, system_rows = named_rows(reports[name]["SystemResults"])
        for column, expected in (("NSYRP", 1), ("NSYRY", 0), ("NSYUA", 1)):
            checks.test(system_rows[-1][system_cols.index(column)] == expected, f"{name} terminal {column}")
        for column, expected in (("NSYMO", 25), ("NSYSW", 1)):
            value = sum((row[system_cols.index(column)] or 0) * .5 for row in system_rows)
            checks.test(close(value, expected, 1e-5), f"{name} {column} aircraft-hours")
        fingerprints[name] = {
            "source_sha256": EXPECTED_SOURCE_SHA[name],
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "model_log_sha256": sha(run / "model.log"),
            "report_raw_sha256": sha(run / "report-raw.json"),
        }
    checks.test(len(gui_ids) == 1, "same preserved GUI identity across three runs")
    checks.test(sha(RUNS["fixed_Y"] / "model.log") == sha(RUNS["fixed_N"] / "model.log"),
                "fixed Y/N event logs byte-identical")
    fixed_cell_differences = compare_cells(checks, reports["fixed_Y"], reports["fixed_N"], "fixed Y/N")
    checks.test(fixed_cell_differences == 0, "fixed Y/N all report cells equal")
    parent_delta = {
        ("ResultSummary", 0, "MSTF"): (0, 1),
        ("ResultSummary", 0, "MSUF"): (0, 1),
        ("SystemResults", 36, "NREPT"): (1, 0),
        ("SystemResults", 69, "NREPT"): (0, 1),
    }
    continuous_fixed_differences = compare_cells(
        checks, reports["continuous_Y"], reports["fixed_Y"], "continuous/fixed Y", parent_delta
    )
    checks.test(continuous_fixed_differences == 4, "continuous/fixed Y exactly four report cells differ")
    checks.test(observed["fixed_Y"] == observed["fixed_N"], "fixed Y/N extracted event timelines equal")

    verdict = {
        "schema": "simlox-g06-var04-independent-readonly/v1",
        "review_date": "2026-10-02",
        "reviewer": "independent read-only reviewer; standard library only; no author-module imports",
        "verdict": "GO" if not checks.failures else "NO-GO",
        "passed": not checks.failures,
        "checks_total": checks.total,
        "checks_passed": checks.total - len(checks.failures),
        "failures": checks.failures,
        "fingerprints": {
            "contract_sha256": sha(CASE / "contract.json"),
            "exact_diff_sha256": sha(CASE / "exact-diff.json"),
            "runs": fingerprints,
        },
        "observed_events": observed,
        "report_comparison": {
            "fixed_Y_vs_fixed_N_different_cells": fixed_cell_differences,
            "continuous_Y_vs_fixed_Y_different_cells": continuous_fixed_differences,
            "continuous_Y_vs_fixed_Y_cells": [
                {"table": table, "row": row, "column": column, "continuous_Y": values[0], "fixed_Y": values[1]}
                for (table, row, column), values in parent_delta.items()
            ],
        },
        "limits": [
            "One seed, one fixed mission, one passive B/A/C RBD and direct system CM only.",
            "Only fixed Y versus fixed N isolates ONLM. Continuous Y versus fixed Y also changes MPAT and TFOUT/TFRET.",
            "Byte-identical fixed event logs and reports support non-applicability for this model, not a universal mission-type rule.",
            "Native success and report factors retain their engine-specific definitions; no GUI visual or cross-engine behavior was tested.",
        ],
    }
    OUT.write_bytes((json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": verdict["verdict"], "checks_total": checks.total,
                      "checks_passed": verdict["checks_passed"], "report_sha256": sha(OUT)}, sort_keys=True))


if __name__ == "__main__":
    main()

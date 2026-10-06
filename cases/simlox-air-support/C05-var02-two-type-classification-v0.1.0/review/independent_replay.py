"""Standard-library, read-only replay of the accepted C05 two-type panel.

No author validator or native executable is imported or invoked. The only write is
the deterministic LF verdict in this review directory.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from pathlib import Path


REVIEW = Path(__file__).resolve().parent
PACKAGE = REVIEW.parent
CASES = PACKAGE.parent
REPO = PACKAGE.parents[2]
CONTRACT_SHA = "1028e32013b7f3b655254d10c0f2cdb40529a73517326e5b5929e32639d2a7de"
SHAPES = {
    "ProblemDescription": (1, 1),
    "ResultSummary": (1, 11),
    "SystemResults": (72, 40),
    "StockTotalResults": (72, 16),
    "ResourceResults": (72, 16),
    "ResourceResultsTotal": (1, 14),
}


class Checks:
    def __init__(self) -> None:
        self.total = 0
        self.failures: list[str] = []

    def yes(self, condition: bool, label: str) -> None:
        self.total += 1
        if not condition:
            self.failures.append(label)

    def eq(self, got: object, want: object, label: str) -> None:
        self.yes(got == want, f"{label}: got {got!r}, want {want!r}")

    def near(self, got: object, want: float, label: str) -> None:
        self.yes(isinstance(got, (float, int)) and math.isclose(got, want, abs_tol=1e-5),
                 f"{label}: got {got!r}, want {want!r}")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_file(path: Path) -> dict:
    return json.loads(path.read_bytes())


def pin(c: Checks, path: Path, expected: dict, label: str, git: bool = False) -> None:
    try:
        if git:
            data = subprocess.check_output(
                ["git", "show", "HEAD:" + path.relative_to(REPO).as_posix()],
                cwd=REPO, stderr=subprocess.DEVNULL,
            )
        else:
            data = path.read_bytes()
        c.eq(len(data), expected["bytes"], label + " bytes")
        c.eq(digest(data), expected["sha256"], label + " SHA256")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        c.yes(False, f"{label}: {exc}")


def model_tables(obj: dict) -> dict[str, dict]:
    return {table["name"]: table for table in obj["model"]["tables"]}


def report_tables(path: Path) -> dict[str, tuple[list[str], list[list]]]:
    # Preserve original report bytes; normalize native trailing commas in memory.
    text = path.read_text(encoding="utf-8-sig")
    data = json.loads(re.sub(r",\s*([}\]])", r"\1", text))["report"]
    return {
        table["name"]: (
            [column["name"] for column in table["columns"]],
            table["instances"][0]["rows"],
        )
        for table in data["tables"]
    }


def named_rows(table: tuple[list[str], list[list]]) -> list[dict]:
    columns, rows = table
    return [dict(zip(columns, row, strict=True)) for row in rows]


def report_diff(a: tuple[list[str], list[list]], b: tuple[list[str], list[list]]) -> int:
    a_columns, a_rows = a
    b_columns, b_rows = b
    if a_columns != b_columns or len(a_rows) != len(b_rows):
        return -1
    return sum(x != y for ax, bx in zip(a_rows, b_rows) for x, y in zip(ax, bx))


def check_events(c: Checks, radio_capacity: int, log: str) -> None:
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    c.eq(log.count("mission activated, systems requested: 2"), 1, f"radio{radio_capacity} one mission")
    for aircraft in (0, 1):
        marker = f"Time: 7 <TEACH-AIR-01,{aircraft}> system resource availability test"
        start = log.find(marker)
        c.yes(start >= 0, f"radio{radio_capacity} aircraft {aircraft} availability test")
        if start >= 0:
            end = log.find("\nTime:", start + len(marker))
            block = log[start:end if end >= 0 else None]
            c.yes("<MISSION-CREW at <BASE-01,0>> request for: 1 OK" in block,
                  f"radio{radio_capacity} aircraft {aircraft} crew available")
            outcome = "OK" if radio_capacity == 2 else "failed"
            c.yes(f"<MISSION-RADIO at <BASE-01,0>> request for: 1 {outcome}" in block,
                  f"radio{radio_capacity} aircraft {aircraft} radio {outcome}")
        c.eq(f"Time: 7 <TEACH-AIR-01,{aircraft}> books resources" in log, radio_capacity == 2,
             f"radio{radio_capacity} aircraft {aircraft} booking")
        c.eq(f"Time: 7 {mission} mission allocates system: <TEACH-AIR-01,{aircraft}>" in log,
             radio_capacity == 2, f"radio{radio_capacity} aircraft {aircraft} assignment")
    c.eq(log.count("books resources"), radio_capacity, f"radio{radio_capacity} bookings")
    c.eq(log.count("mission allocates system:"), radio_capacity, f"radio{radio_capacity} allocations")
    for resource in ("MISSION-CREW", "MISSION-RADIO"):
        c.eq(log.count(f"<{resource} at <BASE-01,0>> allocated to mission assigned: 1"),
             radio_capacity, f"radio{radio_capacity} {resource} allocations")
        c.eq(log.count(f"<{resource} at <BASE-01,0>> deallocated from  mission operation: 1"),
             radio_capacity, f"radio{radio_capacity} {resource} releases")
    if radio_capacity == 2:
        c.yes(f"Time: 8 {mission} mission starting, duration: 2" in log, "radio2 start h8")
        c.yes(f"Time: 10 {mission} mission completed:" in log, "radio2 completion h10")
        c.yes("mission cancelled:" not in log, "radio2 no cancellation")
        for aircraft in (0, 1):
            c.yes(f"System arrives <TEACH-AIR-01,{aircraft}>, mission success" in log,
                  f"radio2 aircraft {aircraft} successful return")
        c.yes("Time: 10 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log,
              "radio2 terminal two ready")
    else:
        c.yes(f"Time: 8.33333 {mission} mission cancelled:" in log, "radio0 cancel h8.33333")
        c.yes("mission starting, duration:" not in log and "mission completed:" not in log,
              "radio0 never starts or completes")
        c.yes("System arrives <TEACH-AIR-01" not in log, "radio0 no physical return needed")
        c.yes("Time: 0 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log,
              "radio0 two ready throughout")


def main() -> dict:
    c = Checks()
    contract_bytes = (PACKAGE / "contract.json").read_bytes()
    c.eq(digest(contract_bytes), CONTRACT_SHA, "frozen contract")
    contract = json.loads(contract_bytes)
    c.eq(contract["variant_id"], "C05.var02", "variant")
    c.eq(contract["publication_state"], "not_published", "publication state")
    c.eq(contract["catalog"]["source_bound_cross_reference_only"], True,
         "read-only source-bound scope")
    c.eq(sum(rows * cols for rows, cols in SHAPES.values()), 5210, "cells per report")
    c.eq(contract["predeclared_replay_gates"]["reports"]["total_cells_two_arms"], 10420,
         "contract pair cells")

    for name, entry in contract["prerequisites"].items():
        directory = CASES / entry["package"]
        for filename, record in entry["pins"].items():
            path = directory / record["path"]
            pin(c, path, record["local_disk"], f"{name} {filename} local")
            pin(c, path, record["published_git"], f"{name} {filename} Git", True)

    for key in ("accepted_source", "direct_parent"):
        entry = contract[key]
        directory = CASES / entry["package"]
        c.eq(len(entry["published_source_files"]), entry["published_source_file_count"],
             f"{key} source inventory")
        for record in entry["published_source_files"]:
            path = directory / record["path"]
            pin(c, path, record["local_disk"], f"{key} {record['path']} local")
            pin(c, path, record["published_git"], f"{key} {record['path']} Git", True)

    accepted = CASES / contract["accepted_source"]["package"]
    parent = CASES / contract["direct_parent"]["package"]
    parent_model = model_tables(json_file(parent / "capacity-2-input.json"))
    arm_models = {n: model_tables(json_file(accepted / f"radio-{n}-input.json")) for n in (2, 0)}
    for n in (2, 0):
        current = arm_models[n]
        c.eq(set(current), set(parent_model), f"radio{n} parent table set")
        c.eq({name for name in current if current[name] != parent_model[name]},
             set(contract["source_delta"]["direct_parent_to_each_changed_tables"]),
             f"radio{n} direct-parent changes")
        c.eq(current["ResourceAllocation"]["instances"][0]["rows"],
             [contract["source_delta"]["common_crew_allocation"],
              contract["source_delta"]["radio_allocation_by_arm"][str(n)]],
             f"radio{n} exact allocation")
        c.eq(current["MissionResource"]["instances"][0]["rows"],
             contract["source_delta"]["common_MissionResource_rows"],
             f"radio{n} both resource types required")
    c.eq({name for name in arm_models[2] if arm_models[2][name] != arm_models[0][name]},
         set(contract["source_delta"]["pairwise_changed_tables"]), "pair source delta")
    c.eq(contract["source_delta"]["common_Control"],
         {"NREPS": 1, "SIMPE": 36, "RSEED": "1"}, "source-bound run control")
    c.eq(contract["source_delta"]["common_MissionType"]["DURN"], 2.0,
         "two-hour teaching mission")

    parent_run = contract["direct_parent"]["capacity_2_run"]
    parent_dir = parent / "runs" / parent_run["run_id"]
    for label in ("closure", "invocation"):
        pin(c, parent_dir / f"{label}.json", parent_run[label], f"direct parent {label}")
    for name, record in parent_run["raw"].items():
        pin(c, parent_dir / name, record, f"direct parent raw {name}")
    parent_closure = json_file(parent_dir / "closure.json")
    c.eq(parent_closure["raw"], parent_run["raw"], "direct parent closure/raw map")
    c.eq(parent_closure["source_hashes_before"], parent_closure["source_hashes_after"],
         "direct parent source stable")

    reports: dict[int, dict] = {}
    for n in (2, 0):
        run = contract["accepted_runs"][str(n)]
        directory = accepted / "runs" / run["run_id"]
        for label in ("closure", "invocation"):
            pin(c, directory / f"{label}.json", run[label], f"radio{n} {label}")
        for name, record in run["raw"].items():
            pin(c, directory / name, record, f"radio{n} raw {name}")
        closure = json_file(directory / "closure.json")
        invocation = json_file(directory / "invocation.json")
        c.eq(closure["invocation_sha256"], run["invocation"]["sha256"],
             f"radio{n} invocation seal")
        c.eq(closure["raw"], run["raw"], f"radio{n} raw closure map")
        c.eq(closure["source_hashes_before"], closure["source_hashes_after"],
             f"radio{n} source stable")
        c.eq(closure["source_hashes_before"], run["source_hashes_before_after"],
             f"radio{n} frozen source map")
        c.eq(invocation["source_hashes_before"], closure["source_hashes_before"],
             f"radio{n} invocation source map")
        c.eq(invocation["session_id"], 0, f"radio{n} SSH session 0")
        c.yes(invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"],
              f"radio{n} sshd ancestry")
        c.eq(invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue",
             f"radio{n} queue mutex")
        c.eq(invocation["gui"],
             {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"},
             f"radio{n} original GUI identity")
        steps = json_file(directory / "steps.json")
        c.eq([step["name"] for step in steps],
             ["import", "export", "calc", "jsonreport", "check_import_export"],
             f"radio{n} ordered stages")
        for step in steps:
            c.yes(step["exit_code"] == 0 and step["status"] == "completed" and
                  step["gui_preserved"], f"radio{n} {step['name']} success/GUI")
        run_log = (directory / "run.log").read_text(encoding="utf-8-sig")
        c.yes("Errors: 0, Warnings: 2, Notes: 0" in run_log,
              f"radio{n} converter counts")
        c.eq(re.findall(r"\((?:warning|error) #(\d+)\)", run_log),
             ["108", "126"], f"radio{n} only warnings")
        check_events(c, n, (directory / "model.log").read_text(encoding="utf-8-sig"))

        exported = model_tables(json_file(directory / "roundtrip-raw.json"))
        source = arm_models[n]
        nonempty = [name for name, table in source.items() if any(i["rows"] for i in table["instances"])]
        c.eq(len(nonempty), 16, f"radio{n} authored row-containing tables")
        for name in nonempty:
            c.eq(exported[name]["columns"], source[name]["columns"],
                 f"radio{n} {name} roundtrip columns")
            c.eq(exported[name]["instances"], source[name]["instances"],
                 f"radio{n} {name} roundtrip instances/rows")

        reports[n] = report_tables(directory / "report-raw.json")
        c.eq(set(reports[n]), set(SHAPES), f"radio{n} six report tables")
        for name, (row_count, column_count) in SHAPES.items():
            columns, rows = reports[n][name]
            c.eq((len(rows), len(columns)), (row_count, column_count),
                 f"radio{n} {name} dimensions")
            for row_i, row in enumerate(rows):
                c.eq(len(row), column_count, f"radio{n} {name} row {row_i} width")
                for column_i, value in enumerate(row):
                    c.yes(value is None or isinstance(value, (str, bool, int, float)) and
                          (not isinstance(value, float) or math.isfinite(value)),
                          f"radio{n} {name} cell {row_i}/{column_i} scalar/null")
        for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
            columns, rows = reports[n][name]
            start_i, end_i = columns.index("STINT"), columns.index("ETINT")
            for i, row in enumerate(rows):
                c.near(row[start_i], i / 2, f"radio{n} {name} bin {i} start")
                c.near(row[end_i], (i + 1) / 2, f"radio{n} {name} bin {i} end")

        summary = named_rows(reports[n]["ResultSummary"])[0]
        for metric in ("MTMF", "MSTF", "MSUF", "STMF"):
            c.eq(summary[metric], 1 if n == 2 else 0, f"radio{n} summary {metric}")
        resource_total = named_rows(reports[n]["ResourceResultsTotal"])[0]
        c.eq(resource_total["NR"], n + 2, f"radio{n} crew+radio capacity total")
        sys_rows = named_rows(reports[n]["SystemResults"])
        res_rows = named_rows(reports[n]["ResourceResults"])
        stock_rows = named_rows(reports[n]["StockTotalResults"])
        for i in range(72):
            active = n == 2
            ready = 2 if not active or i < 14 or i >= 20 else 0
            assigned = 2 if active and 14 <= i < 20 else 0
            operating = 2 if active and 16 <= i < 20 else 0
            crew_assigned = 4 if active and 14 <= i < 16 else 0
            crew_operating = 4 if active and 16 <= i < 20 else 0
            c.eq(sys_rows[i]["NSYA"], 2, f"radio{n} availability denominator {i}")
            c.near(sys_rows[i]["NSYRY"], ready, f"radio{n} ready aircraft {i}")
            c.near(sys_rows[i]["NSYMA"], assigned, f"radio{n} assigned aircraft {i}")
            c.near(sys_rows[i]["NSYMO"], operating, f"radio{n} operating aircraft {i}")
            c.eq(res_rows[i]["NR"], n + 2, f"radio{n} total resource capacity {i}")
            c.near(res_rows[i]["NRMA"], crew_assigned, f"radio{n} assigned resource units {i}")
            c.near(res_rows[i]["NRMO"], crew_operating, f"radio{n} operating resource units {i}")
            c.eq(stock_rows[i]["NBO"], 0, f"radio{n} no stock backorder {i}")
            for metric in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT"):
                c.eq(stock_rows[i][metric], 0, f"radio{n} no stock movement {metric} {i}")
        c.eq(sys_rows[-1]["NSYRY"], 2, f"radio{n} terminal two ready")

    difference_counts = contract["predeclared_replay_gates"]["reports"][
        "radio_2_vs_radio_0_difference_counts"
    ]
    for name, expected in difference_counts.items():
        c.eq(report_diff(reports[2][name], reports[0][name]), expected,
             f"radio2/0 {name} changed-cell count")
    c.eq(reports[2]["StockTotalResults"], reports[0]["StockTotalResults"],
         "full stock table pair parity")

    return {
        "schema": "simlox-air-support-independent-readonly-verdict/v1",
        "case_id": "C05.var02",
        "contract_sha256": CONTRACT_SHA,
        "decision": "GO_BOUNDED" if not c.failures else "NO_GO",
        "checks": c.total,
        "failures": c.failures,
        "scope": "Read-only classification of the two accepted C05.var02 radio-capacity arms; no new native run.",
        "limits": [
            "Per-system all-required-types-before-booking is observed at radio capacity zero, not formation-wide atomic assignment.",
            "One seed, fixed two-hour mission, two resource types; no radio-one or catalog one-hour result.",
            "No general capacity law, GUI-only behavior, or cross-engine equivalence is established.",
        ],
    }


if __name__ == "__main__":
    verdict = main()
    (REVIEW / "independent-verdict.json").write_bytes(
        (json.dumps(verdict, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    print(f"{verdict['decision']} {verdict['checks']} checks, {len(verdict['failures'])} failures")
    for failure in verdict["failures"][:20]:
        print(failure)

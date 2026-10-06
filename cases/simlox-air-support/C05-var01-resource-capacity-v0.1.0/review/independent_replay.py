"""Independent, read-only replay of the accepted C05 capacity panel.

Uses only Python's standard library. It never invokes SIMLOX or an author checker.
The sole write is the deterministic verdict in this review directory.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
CASES = CASE.parent
REPO = CASE.parents[2]
CONTRACT_SHA = "096c4a6d23079c46416e06b8d79229033a13ecc23db29eb1ea6c2bf2524390ad"
TABLE_SHAPES = {
    "ProblemDescription": (1, 1),
    "ResultSummary": (1, 11),
    "SystemResults": (72, 40),
    "StockTotalResults": (72, 16),
    "ResourceResults": (72, 16),
    "ResourceResultsTotal": (1, 14),
}


class Audit:
    def __init__(self) -> None:
        self.checks = 0
        self.failures: list[str] = []

    def check(self, condition: bool, label: str) -> None:
        self.checks += 1
        if not condition:
            self.failures.append(label)

    def equal(self, got: object, expected: object, label: str) -> None:
        self.check(got == expected, f"{label}: got {got!r}; expected {expected!r}")

    def near(self, got: object, expected: float, label: str, tol: float = 1e-5) -> None:
        self.check(
            isinstance(got, (float, int)) and math.isclose(got, expected, abs_tol=tol),
            f"{label}: got {got!r}; expected {expected!r}",
        )


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> object:
    return json.loads(path.read_bytes())


def check_pin(a: Audit, label: str, path: Path, pin: dict, git: bool = False) -> None:
    try:
        if git:
            relative = path.relative_to(REPO).as_posix()
            data = subprocess.check_output(
                ["git", "show", f"HEAD:{relative}"], cwd=REPO, stderr=subprocess.DEVNULL
            )
        else:
            data = path.read_bytes()
        a.equal(len(data), pin["bytes"], label + " size")
        a.equal(sha(data), pin["sha256"], label + " SHA256")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        a.check(False, f"{label}: {exc}")


def tables(model: dict) -> dict[str, dict]:
    return {table["name"]: table for table in model["tables"]}


def report(path: Path) -> dict[str, tuple[list[str], list[list]]]:
    # Native default JSON can have trailing commas; normalization is in memory only.
    source = path.read_text(encoding="utf-8-sig")
    parsed = json.loads(re.sub(r",\s*([}\]])", r"\1", source))["report"]
    return {
        table["name"]: (
            [col["name"] for col in table["columns"]],
            table["instances"][0]["rows"],
        )
        for table in parsed["tables"]
    }


def rows_by_name(t: tuple[list[str], list[list]]) -> list[dict]:
    names, rows = t
    return [dict(zip(names, row, strict=True)) for row in rows]


def count_differences(left: tuple[list[str], list[list]], right: tuple[list[str], list[list]]) -> int:
    left_names, left_rows = left
    right_names, right_rows = right
    if left_names != right_names or len(left_rows) != len(right_rows):
        return -1
    return sum(x != y for lrow, rrow in zip(left_rows, right_rows) for x, y in zip(lrow, rrow))


def event_checks(a: Audit, arm: int, log: str) -> None:
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    a.equal(log.count("mission activated, systems requested: 2"), 1, f"{arm} one demand")
    a.equal(log.count("request for: 1 OK"), arm, f"{arm} crew availability OK")
    expected_fail = {2: 0, 1: 2, 0: 2}[arm]
    a.equal(log.count("request for: 1 failed"), expected_fail, f"{arm} crew availability failed")
    a.equal(log.count("books resources"), arm, f"{arm} bookings")
    a.equal(log.count("mission allocates system:"), arm, f"{arm} aircraft allocations")
    for aircraft in (0, 1):
        allocated = f"Time: 7 {mission} mission allocates system: <TEACH-AIR-01,{aircraft}>"
        a.equal(allocated in log, aircraft < arm, f"{arm} aircraft {aircraft} allocation")
    if arm == 2:
        a.check("Time: 8 " + mission + " mission starting, duration: 2" in log, "2 mission start h8")
        a.check("Time: 10 " + mission + " mission completed:" in log, "2 mission completion h10")
        a.equal(log.count("deallocated from  mission operation: 1"), 2, "2 crew release")
        for aircraft in (0, 1):
            a.check(
                f"System arrives <TEACH-AIR-01,{aircraft}>, mission success" in log,
                f"2 aircraft {aircraft} successful return",
            )
        a.check("mission cancelled:" not in log, "2 no cancellation")
    else:
        a.check("Time: 8.33333 " + mission + " mission cancelled:" in log, f"{arm} cancellation")
        a.check("mission starting, duration:" not in log, f"{arm} no start")
        a.check("mission completed:" not in log, f"{arm} no completion")
        a.equal(log.count("deallocated from  mission assigned: 1"), arm, f"{arm} reservation release")
        if arm == 1:
            a.check("Time: 8.33333 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>" in log,
                    "1 aircraft ID0 return")
    if arm == 2:
        a.check("Time: 10 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log,
                "2 terminal two ready")
    elif arm == 1:
        a.check("Time: 8.33333 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log,
                "1 terminal two ready")
    else:
        a.check("Time: 0 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log,
                "0 two ready throughout")


def main() -> dict:
    a = Audit()
    contract_bytes = (CASE / "contract.json").read_bytes()
    a.equal(sha(contract_bytes), CONTRACT_SHA, "frozen contract")
    c = json.loads(contract_bytes)
    a.equal(c["variant_id"], "C05.var01", "case variant")
    a.equal(c["publication_state"], "not_published", "not yet published")
    a.equal(c["catalog"]["classification_only"], True, "classification only")
    a.equal(sum(rows * cols for rows, cols in TABLE_SHAPES.values()), 5210,
            "report cells per arm")
    a.equal(c["predeclared_replay_gates"]["reports"]["total_cells_three_arms"], 15630,
            "contract three-arm cell count")

    for key, prerequisite in c["prerequisites"].items():
        base = CASES / prerequisite["package"]
        for name, pin in prerequisite["pins"].items():
            path = base / pin["path"]
            check_pin(a, f"{key} {name} disk", path, pin["local_disk"])
            check_pin(a, f"{key} {name} Git", path, pin["published_git"], git=True)

    source = c["accepted_source"]
    parent = CASES / source["package"]
    a.equal(len(source["published_source_files"]), 17, "accepted source inventory")
    for pin in source["published_source_files"]:
        path = parent / pin["path"]
        check_pin(a, f"C05 {pin['path']} disk", path, pin["local_disk"])
        check_pin(a, f"C05 {pin['path']} Git", path, pin["published_git"], git=True)

    input_data: dict[int, dict] = {}
    source_tables: dict[int, dict] = {}
    for arm in (2, 1, 0):
        input_path = parent / f"capacity-{arm}-input.json"
        input_data[arm] = read_json(input_path)
        source_tables[arm] = tables(input_data[arm]["model"])

    a03 = tables(read_json(CASES / "A03-two-aircraft-formation-v1.0.1/native-input.json")["model"])
    a.equal(set(source_tables[2]) - set(a03), {"MissionResource"}, "A03 to C05 added table")
    a.equal(set(a03) - set(source_tables[2]), set(), "A03 to C05 removed tables")
    a.equal({k for k in a03 if a03[k] != source_tables[2][k]},
            {"ProblemDescription", "Resource", "ResourceAllocation"}, "A03 to C05 changed tables")
    for left, right in ((2, 1), (2, 0), (1, 0)):
        a.equal({k for k in source_tables[left] if source_tables[left][k] != source_tables[right][k]},
                {"ProblemDescription", "ResourceAllocation"}, f"{left}/{right} source table delta")
    for arm in (2, 1, 0):
        allocation = source_tables[arm]["ResourceAllocation"]["instances"][0]["rows"]
        a.equal(allocation, [["AIR_BASIC", "MISSION-CREW", "BASE-01", arm, None]],
                f"{arm} sole capacity row")
        mission_resource = source_tables[arm]["MissionResource"]["instances"][0]["rows"]
        a.equal(mission_resource, [["BASIC-MISSION", "TEACH-AIR-01", "MISSION-CREW", 1, None]],
                f"{arm} one crew per aircraft")
    a.equal(c["source_delta"]["common_Control"], {"NREPS": 1, "SIMPE": 36, "RSEED": "1"},
            "fixed common control contract")
    a.equal(c["source_delta"]["common_MissionType"]["DURN"], 2.0,
            "two-hour teaching mission")

    reports: dict[int, dict] = {}
    for arm in (2, 1, 0):
        run = c["accepted_runs"][str(arm)]
        directory = parent / "runs" / run["run_id"]
        check_pin(a, f"{arm} closure", directory / "closure.json", run["closure"])
        check_pin(a, f"{arm} invocation", directory / "invocation.json", run["invocation"])
        for name, pin in run["raw"].items():
            check_pin(a, f"{arm} raw {name}", directory / name, pin)
        closure = read_json(directory / "closure.json")
        invocation = read_json(directory / "invocation.json")
        a.equal(closure["invocation_sha256"], run["invocation"]["sha256"], f"{arm} closure invocation")
        a.equal(closure["raw"], run["raw"], f"{arm} closure raw map")
        a.equal(closure["source_hashes_before"], closure["source_hashes_after"], f"{arm} source stable")
        a.equal(closure["source_hashes_before"], run["source_hashes_before_after"], f"{arm} source pins")
        a.equal(invocation["source_hashes_before"], closure["source_hashes_before"], f"{arm} invocation pins")
        a.equal(invocation["session_id"], 0, f"{arm} SSH session 0")
        a.check(invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"],
                f"{arm} sshd ancestry")
        a.equal(invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue", f"{arm} queue mutex")
        a.equal((invocation["gui"]["pid"], invocation["gui"]["session_id"]), (13340, 1),
                f"{arm} protected GUI identity")
        a.equal(invocation["gui"]["start_utc"], "2026-09-28T10:09:56.8261381Z",
                f"{arm} protected GUI start")
        steps = read_json(directory / "steps.json")
        a.equal([s["name"] for s in steps],
                ["import", "export", "calc", "jsonreport", "check_import_export"], f"{arm} native/check stages")
        for step in steps:
            a.check(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"],
                    f"{arm} {step['name']} completed and GUI preserved")
        run_log = (directory / "run.log").read_text(encoding="utf-8-sig")
        a.check("Errors: 0, Warnings: 2, Notes: 0" in run_log, f"{arm} converter count")
        a.equal(re.findall(r"\((?:warning|error) #(\d+)\)", run_log), ["108", "126"],
                f"{arm} sole warnings")
        log = (directory / "model.log").read_text(encoding="utf-8-sig")
        event_checks(a, arm, log)

        exported = tables(read_json(directory / "roundtrip-raw.json")["model"])
        authored = source_tables[arm]
        populated = [name for name, table in authored.items() if any(i["rows"] for i in table["instances"])]
        a.equal(len(populated), 16, f"{arm} authored row-containing tables")
        for name in populated:
            a.equal(exported[name]["columns"], authored[name]["columns"], f"{arm} {name} columns")
            a.equal(exported[name]["instances"], authored[name]["instances"], f"{arm} {name} rows")

        reports[arm] = report(directory / "report-raw.json")
        a.equal(set(reports[arm]), set(TABLE_SHAPES), f"{arm} exact six report tables")
        for name, (row_count, col_count) in TABLE_SHAPES.items():
            columns, rows = reports[arm][name]
            a.equal((len(rows), len(columns)), (row_count, col_count), f"{arm} {name} dimensions")
            for row_i, row in enumerate(rows):
                a.equal(len(row), col_count, f"{arm} {name} row {row_i} width")
                for col_i, cell in enumerate(row):
                    a.check(cell is None or isinstance(cell, (str, int, float, bool)) and
                            (not isinstance(cell, float) or math.isfinite(cell)),
                            f"{arm} {name} cell {row_i}/{col_i} finite scalar or null")
        for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
            columns, rows = reports[arm][name]
            start, end = columns.index("STINT"), columns.index("ETINT")
            for i, row in enumerate(rows):
                a.near(row[start], i / 2, f"{arm} {name} bin {i} start")
                a.near(row[end], (i + 1) / 2, f"{arm} {name} bin {i} end")

        summary = rows_by_name(reports[arm]["ResultSummary"])[0]
        for metric in ("MTMF", "MSTF", "MSUF", "STMF"):
            a.equal(summary[metric], 1 if arm == 2 else 0, f"{arm} summary {metric}")
        a.equal(summary["NREP"], 1, f"{arm} one replication")
        total = rows_by_name(reports[arm]["ResourceResultsTotal"])[0]
        a.equal(total["NR"], arm, f"{arm} resource total capacity")
        system = rows_by_name(reports[arm]["SystemResults"])
        resource = rows_by_name(reports[arm]["ResourceResults"])
        stock = rows_by_name(reports[arm]["StockTotalResults"])
        for i in range(72):
            a.equal(system[i]["NSYA"], 2, f"{arm} system availability denominator {i}")
            a.equal(resource[i]["NR"], arm, f"{arm} resource capacity bin {i}")
            a.equal(stock[i]["NBO"], 0, f"{arm} no stock backorder bin {i}")
            for metric in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT"):
                a.equal(stock[i][metric], 0, f"{arm} no stock movement {metric} bin {i}")
            if arm == 2:
                ready = 2 if i < 14 or i >= 20 else 0
                assigned = 2 if 14 <= i < 16 else 0
                operating = 2 if 16 <= i < 20 else 0
            elif arm == 0:
                ready, assigned, operating = 2, 0, 0
            else:
                ready = 1 if 14 <= i < 16 else (4 / 3 if i == 16 else 2)
                assigned = 1 if 14 <= i < 16 else (2 / 3 if i == 16 else 0)
                operating = 0
            a.near(system[i]["NSYRY"], ready, f"{arm} ready aircraft bin {i}")
            a.near(system[i]["NSYMA"], assigned + operating,
                   f"{arm} mission-allocated aircraft bin {i}")
            a.near(system[i]["NSYMO"], operating, f"{arm} operating aircraft bin {i}")
            a.near(resource[i]["NRMA"], assigned, f"{arm} crew assigned bin {i}")
            a.near(resource[i]["NRMO"], operating, f"{arm} crew operating bin {i}")
        a.equal(system[-1]["NSYRY"], 2, f"{arm} terminal ready")

    for other in (1, 0):
        expected = c["predeclared_replay_gates"]["reports"]["pairwise_difference_counts_vs_capacity_2"][f"2_vs_{other}"]
        for name, count in expected.items():
            a.equal(count_differences(reports[2][name], reports[other][name]), count,
                    f"2/{other} exact {name} changed-cell count")
        a.equal(reports[2]["StockTotalResults"], reports[other]["StockTotalResults"],
                f"2/{other} all stock cells identical")

    return {
        "schema": "simlox-air-support-independent-readonly-verdict/v1",
        "case_id": "C05.var01",
        "contract_sha256": CONTRACT_SHA,
        "decision": "GO_BOUNDED" if not a.failures else "NO_GO",
        "checks": a.checks,
        "failures": a.failures,
        "scope": "Existing accepted C05 capacity-2/1/0 CLI evidence only; no new native or GUI run.",
        "limits": [
            "Capacity 1 partially assigns aircraft ID0 before mission cancellation; no all-or-none formation claim.",
            "The teaching mission lasts two hours, differs from the one-hour catalog example, and uses one seed.",
            "No general capacity law, additional resource type, GUI behavior, or cross-engine equivalence is established.",
        ],
    }


if __name__ == "__main__":
    result = main()
    output = HERE / "independent-verdict.json"
    output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"{result['decision']} {result['checks']} checks, {len(result['failures'])} failures")
    for failure in result["failures"][:20]:
        print(failure)

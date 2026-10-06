"""Independent standard-library replay of accepted C06 primary/alternative runs.

No author validator or native executable is used. Only this review's LF verdict is written.
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
REPO = PACKAGE.parents[2]
CONTRACT_SHA = "63e5f70f9e7556d5ec3282c5c2346ffecc6b6b336f6f03cc703d18fe6a929535"
SHAPES = {
    "ProblemDescription": (1, 1),
    "ResultSummary": (1, 11),
    "SystemResults": (72, 40),
    "StockTotalResults": (72, 16),
    "ResourceResults": (72, 16),
    "ResourceResultsTotal": (1, 14),
}


class Review:
    def __init__(self) -> None:
        self.checks = 0
        self.failures: list[str] = []

    def require(self, ok: bool, label: str) -> None:
        self.checks += 1
        if not ok:
            self.failures.append(label)

    def equal(self, actual: object, expected: object, label: str) -> None:
        self.require(actual == expected, f"{label}: {actual!r} != {expected!r}")

    def close(self, actual: object, expected: float, label: str) -> None:
        self.require(isinstance(actual, (float, int)) and
                     math.isclose(actual, expected, abs_tol=1e-5),
                     f"{label}: {actual!r} != {expected!r}")


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def loaded(path: Path) -> dict:
    return json.loads(path.read_bytes())


def check_pin(checks: Review, path: Path, pin: dict, label: str, git: bool = False) -> None:
    try:
        if git:
            data = subprocess.check_output(
                ["git", "show", f"HEAD:{path.relative_to(REPO).as_posix()}"],
                cwd=REPO, stderr=subprocess.DEVNULL,
            )
        else:
            data = path.read_bytes()
        checks.equal(len(data), pin["bytes"], label + " byte count")
        checks.equal(hash_bytes(data), pin["sha256"], label + " SHA256")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        checks.require(False, f"{label}: {exc}")


def tables(data: dict) -> dict[str, dict]:
    return {t["name"]: t for t in data["model"]["tables"]}


def report(path: Path) -> dict[str, tuple[list[str], list[list]]]:
    # Native default report has occasional trailing commas. Raw bytes remain sealed.
    text = path.read_text(encoding="utf-8-sig")
    parsed = json.loads(re.sub(r",\s*([}\]])", r"\1", text))["report"]
    return {
        t["name"]: ([col["name"] for col in t["columns"]], t["instances"][0]["rows"])
        for t in parsed["tables"]
    }


def row_dicts(table: tuple[list[str], list[list]]) -> list[dict]:
    names, rows = table
    return [dict(zip(names, row, strict=True)) for row in rows]


def cell_diff(a: tuple[list[str], list[list]], b: tuple[list[str], list[list]]) -> int:
    a_names, a_rows = a
    b_names, b_rows = b
    if a_names != b_names or len(a_rows) != len(b_rows):
        return -1
    return sum(x != y for ra, rb in zip(a_rows, b_rows) for x, y in zip(ra, rb))


def overlap(start: float, end: float, left: float, right: float) -> float:
    return max(0.0, min(end, right) - max(start, left))


def event_checks(c: Review, primary: int, text: str) -> None:
    chosen = "P-CREW" if primary == 2 else "P-ALT"
    unused = "P-ALT" if primary == 2 else "P-CREW"
    duration = "0.333333" if primary == 2 else "0.666667"
    release = "7.83333" if primary == 2 else "8.16667"
    launch = "8" if primary == 2 else "8.16667"
    return_time = "9" if primary == 2 else "9.16667"
    for aircraft in (0, 1):
        prefix = f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"
        c.require(f"Time: 7.5  {prefix} started" in text,
                  f"primary{primary} ID{aircraft} subtask start")
        marker = f"Time: 7.5  {prefix} resource availability test"
        start = text.find(marker)
        c.require(start >= 0, f"primary{primary} ID{aircraft} typed test present")
        if start >= 0:
            end = text.find("\nTime:", start + len(marker))
            block = text[start:end if end >= 0 else None]
            expected_primary = "OK" if primary == 2 else "failed"
            c.require(f"<P-CREW at <BASE-01,0>> request for: 1 {expected_primary}" in block,
                      f"primary{primary} ID{aircraft} P-CREW {expected_primary}")
            c.equal("<P-ALT at <BASE-01,0>> request for: 1 OK" in block,
                    primary == 0, f"primary{primary} ID{aircraft} P-ALT test")
        c.require(f"Time: 7.5  {prefix} books resources" in text,
                  f"primary{primary} ID{aircraft} booking")
        c.require(f"Time: 7.5  {prefix} starts performing, planned to last for {duration} hours" in text,
                  f"primary{primary} ID{aircraft} work duration")
        c.require(f"Time: {release}  {prefix} completed" in text,
                  f"primary{primary} ID{aircraft} subtask completion")
        c.require(f"Time: {return_time} <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,{aircraft}>, mission success" in text,
                  f"primary{primary} ID{aircraft} mission return")
    for resource, expected in ((chosen, 2), (unused, 0)):
        c.equal(text.count(f"<{resource} at <BASE-01,0>> allocated to maintenance task: 1"),
                expected, f"primary{primary} {resource} allocations")
        c.equal(text.count(f"<{resource} at <BASE-01,0>> deallocated from  maintenance task: 1"),
                expected, f"primary{primary} {resource} releases")
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    c.require(f"Time: {launch} {mission} mission starting, duration: 1" in text,
              f"primary{primary} mission launch")
    c.require(f"Time: {return_time} {mission} mission completed:" in text,
              f"primary{primary} mission completion")
    c.require("mission cancelled:" not in text, f"primary{primary} no mission cancellation")
    c.require(f"Time: {return_time} <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in text,
              f"primary{primary} terminal two ready")


def main() -> dict:
    c = Review()
    raw_contract = (PACKAGE / "contract.json").read_bytes()
    c.equal(hash_bytes(raw_contract), CONTRACT_SHA, "frozen contract")
    contract = json.loads(raw_contract)
    c.equal(contract["variant_id"], "C06.var01", "variant")
    c.equal(contract["publication_state"], "not_published", "publication state")
    c.equal(contract["catalog"]["classification_only"], True, "classification only")
    c.equal(sum(r * n for r, n in SHAPES.values()), 5210, "report cells per arm")
    c.equal(contract["predeclared_gates"]["reports"]["total_cells"], 10420,
            "contract pair report cells")

    for key in ("accepted_C06_source", "accepted_C03_parent"):
        entry = contract[key]
        c.equal(len(entry["source_files"]), entry["source_file_count"], f"{key} source inventory")
        for name, record in entry["source_files"].items():
            path = REPO / record["path"]
            check_pin(c, path, record["local_disk"], f"{key} {name} local")
            check_pin(c, path, record["published_git"], f"{key} {name} Git", True)

    source = contract["accepted_C06_source"]
    original = contract["accepted_C03_parent"]
    pair = {}
    for primary in (2, 0):
        record = source["pair_inputs"][f"primary_{primary}_artf_2"]
        path = REPO / record["path"]
        check_pin(c, path, record["local_disk"], f"primary{primary} input local")
        check_pin(c, path, record["published_git"], f"primary{primary} input Git", True)
        pair[primary] = tables(loaded(path))
    parent_input = original["staffing_2_input"]
    parent_path = REPO / parent_input["path"]
    check_pin(c, parent_path, parent_input["local_disk"], "C03 parent input local")
    check_pin(c, parent_path, parent_input["published_git"], "C03 parent input Git", True)
    parent_tables = tables(loaded(parent_path))
    for primary in (2, 0):
        c.equal({name for name in parent_tables if parent_tables[name] != pair[primary][name]},
                set(contract["pair_source_delta"]["C03_to_C06_changed_tables"]),
                f"primary{primary} C03 source delta")
        allocation = pair[primary]["ResourceAllocation"]["instances"][0]["rows"]
        c.equal(allocation,
                [["AIR_BASIC", "P-CREW", "BASE-01", primary, None],
                 ["AIR_BASIC", "P-ALT", "BASE-01", 2, None]],
                f"primary{primary} exact resource capacities")
        row = pair[primary]["SubTaskResource"]["instances"][0]["rows"][0]
        c.equal(row[:7], ["PREP-FIXED", 1, "P-CREW", 1, 1, "P-ALT", 2.0],
                f"primary{primary} fixed alternative/ARTF")
    c.equal({name for name in pair[2] if pair[2][name] != pair[0][name]},
            {"ProblemDescription", "ResourceAllocation"}, "pair changed tables")
    for entry in contract["pair_source_delta"]["exact_changed_cells"]:
        name = entry["table"]
        columns = [x["name"] for x in pair[2][name]["columns"]]
        col = columns.index(entry["column"])
        row = entry["row_index_zero_based"]
        for primary in (2, 0):
            got = pair[primary][name]["instances"][0]["rows"][row][col]
            c.equal(got, entry[f"primary_{primary}"],
                    f"primary{primary} only {name}.{entry['column']} change")

    runs = [("C03_parent", original["staffing_2_run"])] + list(contract["accepted_C06_runs"].items())
    report_pair: dict[int, dict] = {}
    for label, run in runs:
        directory = Path(run["path"])
        for name in ("closure", "invocation"):
            check_pin(c, directory / f"{name}.json", run[name], f"{label} {name}")
        c.equal(len(run["raw"]), run["raw_count"], f"{label} raw inventory")
        for name, record in run["raw"].items():
            check_pin(c, directory / name, record, f"{label} raw {name}")
        closure = loaded(directory / "closure.json")
        invocation = loaded(directory / "invocation.json")
        c.equal(closure["invocation_sha256"], run["invocation"]["sha256"],
                f"{label} invocation closure seal")
        c.equal(closure["raw"], run["raw"], f"{label} raw closure map")
        if label == "C03_parent":
            c.equal(closure["input_sha256"], run["raw"]["input.json"]["sha256"],
                    "C03 parent closure input")
            c.equal(invocation["input_sha256"], closure["input_sha256"],
                    "C03 parent invocation input")
            continue
        c.equal(closure["source_hashes_before"], run["source_hashes_before"],
                f"{label} source before map")
        c.equal(closure["source_hashes_after"], run["source_hashes_after"],
                f"{label} source after map")
        c.equal(closure["source_hashes_before"], closure["source_hashes_after"],
                f"{label} source stable")
        c.equal(invocation["source_hashes_before"], closure["source_hashes_before"],
                f"{label} invocation source map")
        primary = 2 if label == "primary_2_artf_2" else 0
        c.equal(invocation["session_id"], 0, f"primary{primary} SSH session0")
        c.require(invocation["ssh_connection_present"] and
                  "sshd.exe" in invocation["ssh_ancestor_names"],
                  f"primary{primary} SSH ancestry")
        c.equal(invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue",
                f"primary{primary} global queue")
        c.equal(invocation["gui"],
                {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"},
                f"primary{primary} protected GUI identity")
        steps = loaded(directory / "steps.json")
        c.equal([step["name"] for step in steps],
                ["import", "export", "calc", "jsonreport", "check_import_export"],
                f"primary{primary} five guarded steps")
        for step in steps:
            c.require(step["exit_code"] == 0 and step["status"] == "completed" and
                      step["gui_preserved"], f"primary{primary} {step['name']} completion/GUI")
        runlog = (directory / "run.log").read_text(encoding="utf-8-sig")
        c.require("Errors: 0, Warnings: 2, Notes: 0" in runlog,
                  f"primary{primary} converter count")
        c.equal(re.findall(r"\((?:warning|error) #(\d+)\)", runlog), ["108", "126"],
                f"primary{primary} sole warnings")
        event_checks(c, primary, (directory / "model.log").read_text(encoding="utf-8-sig"))
        exported = tables(loaded(directory / "roundtrip-raw.json"))
        source_tables = pair[primary]
        populated = [name for name, table in source_tables.items()
                     if any(instance["rows"] for instance in table["instances"])]
        c.equal(len(populated), 20, f"primary{primary} 20 authored row tables")
        for name in populated:
            c.equal(exported[name]["columns"], source_tables[name]["columns"],
                    f"primary{primary} {name} roundtrip columns")
            c.equal(exported[name]["instances"], source_tables[name]["instances"],
                    f"primary{primary} {name} roundtrip instances/rows")

        report_pair[primary] = report(directory / "report-raw.json")
        c.equal(set(report_pair[primary]), set(SHAPES), f"primary{primary} six report tables")
        for name, (rows_expected, cols_expected) in SHAPES.items():
            names, rows = report_pair[primary][name]
            c.equal((len(rows), len(names)), (rows_expected, cols_expected),
                    f"primary{primary} {name} shape")
            for row_i, row in enumerate(rows):
                c.equal(len(row), cols_expected, f"primary{primary} {name} row {row_i} width")
                for column_i, value in enumerate(row):
                    c.require(value is None or isinstance(value, (str, bool, int, float)) and
                              (not isinstance(value, float) or math.isfinite(value)),
                              f"primary{primary} {name} cell {row_i}/{column_i} scalar/null")
        for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
            names, rows = report_pair[primary][name]
            a, b = names.index("STINT"), names.index("ETINT")
            for i, row in enumerate(rows):
                c.close(row[a], i / 2, f"primary{primary} {name} bin {i} start")
                c.close(row[b], (i + 1) / 2, f"primary{primary} {name} bin {i} end")

        summary = row_dicts(report_pair[primary]["ResultSummary"])[0]
        for field in ("MTMF", "MSTF", "MSUF", "STMF"):
            c.equal(summary[field], 1, f"primary{primary} successful summary {field}")
        c.equal(summary["NREP"], 1, f"primary{primary} one replication")
        resources = row_dicts(report_pair[primary]["ResourceResults"])
        systems = row_dicts(report_pair[primary]["SystemResults"])
        stock = row_dicts(report_pair[primary]["StockTotalResults"])
        total = row_dicts(report_pair[primary]["ResourceResultsTotal"])[0]
        c.equal(total["NR"], primary + 2, f"primary{primary} fixed total resource capacity")
        work_end = 7.5 + (1 / 3 if primary == 2 else 2 / 3)
        mission_start = 8 if primary == 2 else 8 + 1 / 6
        mission_end = mission_start + 1
        for i in range(72):
            start, end = i / 2, (i + 1) / 2
            prep_mean = 2 * overlap(start, end, 7.5, work_end) / 0.5
            mission_mean = 2 * overlap(start, end, mission_start, mission_end) / 0.5
            assigned_mean = 2 * overlap(start, end, 7.5, mission_end) / 0.5
            ready_mean = 2 - assigned_mean
            c.equal(systems[i]["NSYA"], 2, f"primary{primary} aircraft denominator {i}")
            c.close(systems[i]["NSYRY"], ready_mean, f"primary{primary} ready aircraft {i}")
            c.close(systems[i]["NSYMA"], assigned_mean, f"primary{primary} assigned aircraft {i}")
            c.close(systems[i]["NSYMO"], mission_mean, f"primary{primary} operating aircraft {i}")
            c.close(systems[i]["NSYMP"], prep_mean, f"primary{primary} preparation aircraft {i}")
            c.equal(resources[i]["NR"], primary + 2, f"primary{primary} capacity bin {i}")
            c.close(resources[i]["NRUM"], prep_mean, f"primary{primary} typed resource occupancy {i}")
            c.equal(stock[i]["NBO"], 0, f"primary{primary} no backorder {i}")
            for field in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT"):
                c.equal(stock[i][field], 0, f"primary{primary} no stock movement {field} {i}")
        c.equal(systems[-1]["NSYRY"], 2, f"primary{primary} two ready terminal")

    for name, expected in contract["predeclared_gates"]["reports"]["pair_difference_counts"].items():
        c.equal(cell_diff(report_pair[2][name], report_pair[0][name]), expected,
                f"pair {name} changed-cell count")
    c.equal(report_pair[2]["ResultSummary"], report_pair[0]["ResultSummary"],
            "summary full-cell parity")
    c.equal(report_pair[2]["StockTotalResults"], report_pair[0]["StockTotalResults"],
            "stock full-cell parity")

    return {
        "schema": "simlox-air-support-independent-readonly-verdict/v1",
        "case_id": "C06.var01",
        "contract_sha256": CONTRACT_SHA,
        "decision": "GO_BOUNDED" if not c.failures else "NO_GO",
        "checks": c.checks,
        "failures": c.failures,
        "scope": "Read-only catalog classification of two existing accepted C06 primary-resource arms; no new native run.",
        "limits": [
            "ARTF equals two in both arms, so its causal effect is not isolated.",
            "One seed, one two-aircraft mission, one primary and one alternative type; no general fallback law.",
            "No new GUI observation, additional alternatives, probabilistic requests or cross-engine parity.",
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

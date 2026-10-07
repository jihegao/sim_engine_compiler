"""Read-only byte, source-topology, and report-shape audit for E08.var04."""

import hashlib
import json
import pathlib
import subprocess
import sys


PACKAGE = pathlib.Path(__file__).resolve().parents[1]
REPO = pathlib.Path(__file__).resolve().parents[4]
CONTRACT = PACKAGE / "contract.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_bytes(path, expected):
    data = path.read_bytes()
    assert len(data) == expected["bytes"], (str(path), "bytes", len(data), expected["bytes"])
    assert digest(data) == expected["sha256"], (str(path), "sha256")
    return data


def git_bytes(base, relative):
    return subprocess.check_output(["git", "show", f"{base}:{relative}"], cwd=REPO)


def native_json(path):
    """Remove only trailing commas outside quoted strings, preserving raw file bytes."""
    source = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = False
    escaped = False
    for index, char in enumerate(source):
        if quoted:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            out.append(char)
        elif char == ",":
            later = index + 1
            while later < len(source) and source[later].isspace():
                later += 1
            if later == len(source) or source[later] not in "}]":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def table_map(input_path):
    model = native_json(input_path)["model"]
    assert list(model) == ["database_version", "tables"]
    return {table["name"]: table for table in model["tables"]}


def report_tables(path):
    return native_json(path)["report"]["tables"]


def report_shape(tables, names, dimensions):
    assert [table["name"] for table in tables] == names
    cells = 0
    for table, dimension in zip(tables, dimensions):
        observed = [len(rows(table)), len(table["columns"])]
        assert observed == dimension, (table["name"], observed, dimension)
        assert all(len(row) == dimension[1] for row in rows(table))
        cells += observed[0] * observed[1]
    return cells


def report_differences(left, right):
    assert len(left) == len(right)
    changed = {}
    for a, b in zip(left, right):
        assert a["name"] == b["name"]
        assert a["columns"] == b["columns"]
        assert len(a["instances"]) == len(b["instances"])
        ar, br = rows(a), rows(b)
        assert len(ar) == len(br)
        changed[a["name"]] = sum(x != y for u, v in zip(ar, br) for x, y in zip(u, v))
    return changed


def main():
    contract_bytes = CONTRACT.read_bytes()
    assert len(contract_bytes) == 102414
    assert digest(contract_bytes) == "83af26abcceb0199fd9264c8807304cb0fad5dfd5cee9c2cb005b6a934a50707"
    contract = json.loads(contract_bytes)
    base = contract["base_commit"]
    checks = {"local_pins": 0, "git_pins": 0, "run_files": 0, "direct_cells": 0}
    installed = {
        "simlox_exe_sha256": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual_pdf_sha256": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "dictionary_sha256": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    }
    for key, path in installed.items():
        assert digest(path.read_bytes()) == contract["installed"][key], key

    def walk(value):
        if isinstance(value, dict):
            if "path" in value and "local_disk" in value:
                relative = value["path"]
                checked_bytes(REPO / relative, value["local_disk"])
                checks["local_pins"] += 1
                published = value.get("published_git_at_base")
                if published is not None:
                    raw = git_bytes(base, relative)
                    assert len(raw) == published["bytes"]
                    assert digest(raw) == published["sha256"]
                    checks["git_pins"] += 1
            elif "path" in value and "bytes" in value and "sha256" in value:
                checked_bytes(REPO / value["path"], value)
                checks["local_pins"] += 1
            elif "path" in value and "sha256" in value and len(value) == 2:
                assert digest((REPO / value["path"]).read_bytes()) == value["sha256"]
                checks["local_pins"] += 1
            if "local_run_directory" in value and "files" in value:
                directory = REPO / value["local_run_directory"]
                for filename, pin in value["files"].items():
                    checked_bytes(directory / filename, pin)
                    checks["run_files"] += 1
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(contract)
    assert checks["run_files"] == 104
    assert checks["git_pins"] == 49, checks

    current_path = REPO / contract["source_comparison"]["current_input"]["path"]
    future_path = REPO / contract["source_comparison"]["future_input"]["path"]
    current, future = table_map(current_path), table_map(future_path)
    assert native_json(current_path)["model"]["database_version"] == native_json(future_path)["model"]["database_version"]
    assert len(current) == 34 and len(future) == 35
    assert set(future) - set(current) == {"ItemTransfer"}
    changed = []
    for name, a in current.items():
        b = future[name]
        assert a["name"] == b["name"] and a["columns"] == b["columns"]
        assert len(a["instances"]) == len(b["instances"])
        for ai, bi in zip(a["instances"], b["instances"]):
            assert ai["instance_name"] == bi["instance_name"]
            assert len(ai["rows"]) == len(bi["rows"])
            for row_number, (ar, br) in enumerate(zip(ai["rows"], bi["rows"])):
                for column, (av, bv) in enumerate(zip(ar, br)):
                    if av != bv:
                        changed.append([name, row_number, a["columns"][column]["name"], av, bv])
    assert changed == [
        ["ProblemDescription", 0, "PDESC", contract["source_comparison"]["complete_authored_model_delta"][0]["from"], contract["source_comparison"]["complete_authored_model_delta"][0]["to"]],
        ["StockAllocation", 2, "STSIZ", 1, 0],
    ], changed
    assert rows(future["ItemTransfer"]) == [contract["source_comparison"]["complete_authored_model_delta"][2]["row"]]
    assert [column["name"] for column in future["ItemTransfer"]["columns"]] == contract["source_comparison"]["complete_authored_model_delta"][2]["columns"]

    direct = []
    for parent in contract["accepted_parents"]:
        arm = parent["direct_contrast"]
        wanted = [run for run in parent["runs"] if run["contrast"] == arm]
        native = next(run for run in wanted if run["role"] == "native")
        default = report_tables(REPO / native["local_run_directory"] / "report-raw.json")
        shape = contract["report_reconstruction"]["default_per_direct_arm"]
        checks["direct_cells"] += report_shape(default, shape["table_order"], shape["dimensions"])
        stations = {}
        for run in wanted:
            if run["role"] != "station_report":
                continue
            tables = report_tables(REPO / run["local_run_directory"] / "item-report-raw.json")
            shape = contract["report_reconstruction"]["selected_station_per_arm"]
            checks["direct_cells"] += report_shape(tables, shape["table_order"], shape["dimensions"])
            station = "BASE-01" if "base01" in run["station"] or "base-01" in run["station"] else "BASE-02" if "base02" in run["station"] or "base-02" in run["station"] else "DEPOT-01"
            stations[station] = tables
        direct.append((default, stations))
    assert checks["direct_cells"] == 48684
    comparisons = contract["report_reconstruction"]["observed_difference_counts_for_crosscheck_only"]
    for station in ["default", "BASE-01", "BASE-02", "DEPOT-01"]:
        left = direct[0][0] if station == "default" else direct[0][1][station]
        right = direct[1][0] if station == "default" else direct[1][1][station]
        changed = report_differences(left, right)
        expected = comparisons[station]
        assert {name: n for name, n in changed.items() if n} == {k: v for k, v in expected.items() if k != "total"}
        assert sum(changed.values()) == expected["total"]
    print(json.dumps({"decision": "PASS", **checks}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"NO_GO: {exc!r}", file=sys.stderr)
        raise

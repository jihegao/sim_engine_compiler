"""Independent standard-library, read-only replay of sealed C04.var01 traces."""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess


HERE = pathlib.Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO = HERE.parents[3]
CASES = REPO / "cases" / "simlox-air-support"
VERDICT = HERE / "independent-verdict.json"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_report(path: pathlib.Path) -> list[dict]:
    # Normalize only a private parser copy of the historical trailing-comma export.
    content = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", content))["report"]["tables"]


def scalars(value: object, path: tuple = ()) -> dict:
    if isinstance(value, dict):
        return {key: item for name, child in value.items() for key, item in scalars(child, path + (name,)).items()}
    if isinstance(value, list):
        return {key: item for index, child in enumerate(value) for key, item in scalars(child, path + (index,)).items()}
    return {path: value}


def source_cell(source: dict, table_name: str, column: str) -> object:
    table = next(item for item in source["model"]["tables"] if item["name"] == table_name)
    names = [item["name"] for item in table["columns"]]
    return table["instances"][0]["rows"][0][names.index(column)]


def ordered(content: str, fragments: list[str]) -> bool:
    at = 0
    for fragment in fragments:
        found = content.find(fragment, at)
        if found < 0:
            return False
        at = found + len(fragment)
    return True


class Audit:
    def __init__(self) -> None:
        self.checks = 0
        self.failures: list[str] = []

    def check(self, condition: bool, label: str) -> None:
        self.checks += 1
        if not condition:
            self.failures.append(label)

    def sealed(self, path: pathlib.Path, pin: dict, label: str) -> None:
        self.checks += 1
        try:
            data = path.read_bytes()
            if len(data) != pin["bytes"] or digest(data) != pin["sha256"]:
                self.failures.append(label + " SHA/size")
        except (OSError, KeyError) as error:
            self.failures.append(label + " " + repr(error))


def expected_shortage(arm: str, table: str, row: int, column: str, baseline: object) -> object:
    if table == "ResultSummary" and column in {"MTMF", "MSTF", "MSUF", "STMF"}:
        return 0
    if arm == "aircraft-missing":
        if table == "SystemResults":
            if column == "NSYRY":
                return 0 if row == 15 else 1
            if column == "NSYA":
                return 1
            if column == "NSYMA" and row in {15, 16, 17, 18}:
                return 1 if row == 15 else 0
            if column == "NSYMP" and row in {15, 16}:
                return 1 if row == 15 else 0
            if (column, row) in {("NPSTA", 15)}:
                return 1
            if (column, row) in {("NSYMR", 16), ("NPSUC", 17)}:
                return 0
            if column in {"NSYMO", "FTMO", "STACC"} and row in {17, 18}:
                return 0
        if table == "ResourceResults":
            if column in {"NR", "NRA", "NRN"}:
                return 2
            if (column, row) in {("NRW", 15), ("NRUM", 16)}:
                return 0
        if table == "ResourceResultsTotal":
            if column in {"NR", "NRA", "NRN"}:
                return 2
            if column == "NRUM":
                return 1 / 72
            if column == "NRW":
                return 0
    if arm == "crew-zero":
        if table == "SystemResults":
            if column == "NSYRY" and row in {16, 17, 18}:
                return 2
            if column == "NSYMA" and row in {16, 17, 18}:
                return 0
            if column in {"NSYMP", "NSYMR"} and row == 16:
                return 0
            if column == "NPSUC" and row in {16, 17}:
                return 0
            if column in {"NSYMO", "FTMO", "STACC"} and row in {17, 18}:
                return 0
        if table == "ResourceResults":
            if column in {"NR", "NRA", "NRN"}:
                return 0
            if column == "NRUM" and row in {15, 16}:
                return 0
            if column == "NRW" and row == 15:
                return 2
        if table == "ResourceResultsTotal":
            if column in {"NR", "NRA", "NRN", "NRUM"}:
                return 0
            if column == "NRW":
                return 1 / 36
    return baseline


def same(actual: object, expected: object) -> bool:
    if isinstance(actual, (int, float)) and not isinstance(actual, bool) and isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return abs(actual - expected) <= 3e-5
    return actual == expected


def run() -> dict:
    audit = Audit()
    contract_bytes = (PACKAGE / "contract.json").read_bytes()
    contract = json.loads(contract_bytes)
    audit.check(digest(contract_bytes) == "eaddbcbb400107d3c8aa1f64151a04e85303448e3997efc4b22512db6b313191", "frozen corrected contract")
    audit.check(contract["variant_id"] == "C04.var01" and "0.1.1" in contract["version"], "contract identity")
    audit.sealed(pathlib.Path(contract["manual"]["installed_pdf_path"]), contract["manual"]["installed_pdf"], "installed manual")
    old = CASES / "C04-var01-shortage-v0.1.0"
    audit.check(digest((old / "contract.json").read_bytes()) == "0f9acd39449e62f205d61b4219229e5d4eb7a2992be4a098c420d66749723d3d", "old contract remains excluded")
    audit.check(digest((old / "review" / "independent-contract-no-go-2026-10-07.md").read_bytes()) == "4cf248f77eb0c9212c04b88778757d075ab85cd6890b364513a0545701ab9e15", "old NO_GO preserved")
    accepted = contract["accepted_source"]
    accepted_dir = CASES / accepted["package"]
    for key, name in (("contract", "contract.json"), ("evidence_report", "evidence-2026-09-29.md"), ("independent_review", "review/independent-readonly-2026-09-29.json")):
        audit.sealed(accepted_dir / name, accepted[key], "C04 " + key)
    audit.check(len(accepted["published_source_files"]) == 25, "25 C04 published sources")
    for record in accepted["published_source_files"]:
        file = accepted_dir / record["path"]
        audit.sealed(file, record["local_disk"], "C04 disk " + record["path"])
        rel = file.relative_to(REPO).as_posix()
        blob = subprocess.run(["git", "show", "HEAD:" + rel], cwd=REPO, capture_output=True, check=False)
        audit.check(blob.returncode == 0, "C04 Git exists " + rel)
        if blob.returncode == 0:
            pin = record["published_git"]
            audit.check(len(blob.stdout) == pin["bytes"] and digest(blob.stdout) == pin["sha256"], "C04 Git byte identity " + rel)
    c03 = contract["direct_c03_parent"]
    c03_dir = CASES / c03["package"]
    for key, name in (("contract", "contract.json"), ("evidence_report", "evidence-2026-09-29.md"), ("independent_review", "review/independent-readonly-2026-09-29.json")):
        audit.sealed(c03_dir / name, c03[key], "C03 " + key)
    for key in ("staffing_one_input", "staffing_zero_input", "staffing_two_input"):
        audit.sealed(REPO / c03[key]["path"], c03[key], "C03 " + key)
    c03_run = c03["staffing_one_run"]
    c03_run_dir = pathlib.Path(c03_run["local_run_dir"])
    audit.sealed(c03_run_dir / "closure.json", c03_run["closure"], "C03 closure")
    audit.sealed(c03_run_dir / "invocation.json", c03_run["invocation"], "C03 invocation")
    audit.check(len(c03_run["raw"]) == 11, "C03 11 raw records")
    for name, pin in c03_run["raw"].items():
        audit.sealed(c03_run_dir / name, pin, "C03 raw " + name)
    audit.check(read_json(c03_run_dir / "closure.json")["raw"] == c03_run["raw"], "C03 closure manifest")
    excluded = contract["excluded_evidence"]
    bad = excluded["horizon_wait"]
    bad_dir = accepted_dir / "runs" / bad["run_id"]
    audit.sealed(bad_dir / "run.log", bad["run_log"], "excluded horizon-wait log")
    audit.check((bad_dir / "model.sxo").stat().st_size == 4, "horizon invalid four-byte SXO")
    bad_log = (bad_dir / "run.log").read_text(encoding="utf-8-sig")
    audit.check("error #107" in bad_log and "error #204" in bad_log, "excluded #107/#204")
    audit.check(len(excluded["discovery_runs"]) == 5 and all(name.endswith("-01") for name in excluded["discovery_runs"]), "five discovery runs excluded")

    arms: dict[str, dict] = {}
    for arm in ("crew-equal", "aircraft-missing", "crew-zero"):
        pin = accepted["arms"][arm]
        directory = pathlib.Path(pin["local_run_dir"])
        audit.sealed(REPO / pin["input"]["path"], pin["input"], arm + " source")
        audit.sealed(REPO / pin["parent_diff"]["path"], pin["parent_diff"], arm + " parent diff")
        for key, filename in (("closure", "closure.json"), ("invocation", "invocation.json"), ("model_log", "model.log"), ("report_raw", "report-raw.json")):
            audit.sealed(directory / filename, pin[key], arm + " " + key)
        audit.check(len(pin["raw"]) == 11, arm + " eleven raw records")
        for filename, raw_pin in pin["raw"].items():
            audit.sealed(directory / filename, raw_pin, arm + " raw " + filename)
        closure, invocation, steps = (read_json(directory / name) for name in ("closure.json", "invocation.json", "steps.json"))
        source = read_json(REPO / pin["input"]["path"])
        exported = read_json(directory / "roundtrip-raw.json")
        audit.check(closure["raw"] == pin["raw"] and closure["input_sha256"] == pin["input"]["sha256"] and closure["invocation_sha256"] == pin["invocation"]["sha256"], arm + " closure bindings")
        audit.check((REPO / pin["input"]["path"]).read_bytes() == (directory / "input.json").read_bytes(), arm + " source copied bytes")
        audit.check(len(source["model"]["tables"]) == 31 and len(scalars(source)) == 979, arm + " source 31 tables/979 leaves")
        audit.check(sum(len(row) for table in source["model"]["tables"] for instance in table["instances"] for row in instance["rows"]) == 201, arm + " 201 authored row cells")
        audit.check(source_cell(source, "OperationProfile", "STIM") == 8 and source_cell(source, "OperationProfile", "DTIM") == .5, arm + " common h8/0.5 operation")
        audit.check(source_cell(source, "MissionType", "NOPER") == .5 and source_cell(source, "MissionType", "NOS") == 2, arm + " mission notice/quantity")
        authored = {table["name"]: table for table in source["model"]["tables"]}
        roundtripped = {table["name"]: table for table in exported["model"]["tables"]}
        audit.check(authored.keys() == roundtripped.keys(), arm + " exported table names")
        for name, table in authored.items():
            if any(instance["rows"] for instance in table["instances"]):
                audit.check(table == roundtripped[name], arm + " exact authored row-containing table " + name)
            else:
                audit.check(all(all(cell is None for cell in row) for instance in roundtripped[name]["instances"] for row in instance["rows"]), arm + " null-only placeholder " + name)
        audit.check(invocation["run_id"] == pin["run_id"] and invocation["session_id"] == 0 and invocation["execution_mode"] == "ssh_cli_v1", arm + " run/session0")
        audit.check(invocation["ssh_connection_present"] and invocation["ssh_client_present"] and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", arm + " SSH/mutex")
        gui = invocation["coexisting_gui"]
        audit.check(gui["pid"] == 13340 and gui["session_id"] == 1 and gui["responding_at_preflight"] and gui["process_start_utc"] == "2026-09-28T10:09:56.8261381Z", arm + " protected GUI identity")
        audit.check([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport"], arm + " four ordered stages")
        for step in steps:
            audit.check(step["exit_code"] == 0 and step["coexisting_gui_present_after"] is True, arm + " stage/GUI " + step["name"])
        run_log = (directory / "run.log").read_text(encoding="utf-8-sig")
        audit.check("Errors: 0, Warnings: 2, Notes: 0" in run_log and re.findall(r"warning #(\d+)", run_log) == ["108", "126"] and "error #" not in run_log, arm + " exact converter gate")
        audit.check((directory / "model.sxo").stat().st_size > 4, arm + " valid output")
        log = (directory / "model.log").read_text(encoding="utf-8-sig")
        audit.check(log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission activated, systems requested: 2") == 1, arm + " one requested mission")
        arms[arm] = {"source": source, "log": log, "tables": read_report(directory / "report-raw.json"), "dir": directory}

    equal = scalars(arms["crew-equal"]["source"])
    expected_deltas = {"aircraft-missing": {("SystemDeployment", "QTYPS"): (2, 1), ("ResourceAllocation", "RQTY"): (1, 2)}, "crew-zero": {("ResourceAllocation", "RQTY"): (1, 0)}}
    for arm, changes in expected_deltas.items():
        leaves = scalars(arms[arm]["source"])
        audit.check(equal.keys() == leaves.keys(), arm + " identical source topology")
        differences = {key: (equal[key], leaves[key]) for key in equal if equal[key] != leaves[key]}
        for table_name, column in changes:
            baseline = source_cell(arms["crew-equal"]["source"], table_name, column)
            current = source_cell(arms[arm]["source"], table_name, column)
            audit.check((baseline, current) == changes[(table_name, column)], arm + " exact " + table_name + "." + column)
        audit.check(len(differences) == len(changes), arm + " sole declared source changes")
        expected_positions = set()
        for table_name, column in changes:
            table_index = next(index for index, item in enumerate(arms[arm]["source"]["model"]["tables"]) if item["name"] == table_name)
            table = arms[arm]["source"]["model"]["tables"][table_index]
            column_index = [item["name"] for item in table["columns"]].index(column)
            expected_positions.add(("model", "tables", table_index, "instances", 0, "rows", 0, column_index))
        audit.check(set(differences) == expected_positions, arm + " exact changed scalar positions")
    parent_inputs = {name: read_json(REPO / c03[key]["path"]) for name, key in (("crew-equal", "staffing_one_input"), ("crew-zero", "staffing_zero_input"), ("aircraft-missing", "staffing_two_input"))}
    for arm, parent in parent_inputs.items():
        prior, current = scalars(parent), scalars(arms[arm]["source"])
        audit.check(prior.keys() == current.keys(), arm + " C03 parent topology")
        audit.check(len([key for key in prior if prior[key] != current[key]]) == (2 if arm == "aircraft-missing" else 1), arm + " exact C03 delta count")
        audit.check(source_cell(parent, "OperationProfile", "DTIM") == 1 and source_cell(arms[arm]["source"], "OperationProfile", "DTIM") == .5, arm + " C03 DTIM change")
        if arm == "aircraft-missing":
            audit.check(source_cell(parent, "SystemDeployment", "QTYPS") == 2 and source_cell(arms[arm]["source"], "SystemDeployment", "QTYPS") == 1, "missing C03 additional QTYPS change")

    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    positive = arms["crew-equal"]["log"]
    audit.check(ordered(positive, ["Time: 7.5 " + mission + " mission allocates system: <TEACH-AIR-01,0>", "Time: 7.5 " + mission + " mission allocates system: <TEACH-AIR-01,1>", "Time: 7.5  <P-CREW at <BASE-01,0>> allocated", "Time: 8  <P-CREW at <BASE-01,0>> deallocated", "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> resource received", "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> starts performing", "Time: 8.5  <P-CREW at <BASE-01,0>> deallocated", "Time: 8.5 " + mission + " mission starting", "Time: 9.5 " + mission + " mission success", "Time: 9.5 " + mission + " mission completed", "Time: 9.5 <TEACH-UNIT at <BASE-01,0>> systems ready: 2"]), "positive serialized crew and mission chronology")
    audit.check("mission cancelled" not in positive and positive.count("mission starting") == 1, "positive no cancellation")
    missing = arms["aircraft-missing"]["log"]
    audit.check(ordered(missing, ["Time: 7.5 " + mission + " mission allocates system: <TEACH-AIR-01,0>", "Time: 7.5 " + mission + " mission waiting:  timeout at 8", "Time: 7.5  <P-CREW at <BASE-01,0>> allocated", "Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing", "Time: 8  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed", "Time: 8  <P-CREW at <BASE-01,0>> deallocated", "Time: 8 " + mission + " mission cancelled", "Time: 8 <TEACH-AIR-01,0> turnround started", "Time: 8 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>", "Time: 8 <TEACH-UNIT at <BASE-01,0>> systems ready: 1"]), "missing physical timeline")
    audit.check("mission allocates system: <TEACH-AIR-01,1>" not in missing and "System arrives <TEACH-AIR-01,1>" not in missing and "mission starting" not in missing and "mission success" not in missing, "missing no second aircraft/launch")
    audit.check("reduction factor: 1" in missing and missing.count("mission cancelled") == 1, "missing factor/cancellation count")
    zero = arms["crew-zero"]["log"]
    audit.check(ordered(zero, ["Time: 7.5 " + mission + " mission allocates system: <TEACH-AIR-01,0>", "Time: 7.5 " + mission + " mission allocates system: <TEACH-AIR-01,1>", "Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> resource availability test", "Time: 7.5  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> resource availability test", "Time: 8 " + mission + " mission cancelled", "Time: 8  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> ordered to stop", "Time: 8  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> resource waiting stopped", "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> ordered to stop", "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> resource waiting stopped", "Time: 8 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>", "Time: 8 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,1>", "Time: 8 <TEACH-UNIT at <BASE-01,0>> systems ready: 2"]), "zero crew physical timeline")
    audit.check(zero.count("request for: 1 failed") == 2 and "books resources" not in zero and "starts performing" not in zero and "mission starting" not in zero and "mission success" not in zero, "zero crew no physical work/launch")
    audit.check(zero.count("reduction factor: 0") == 2 and zero.count("mission cancelled") == 1, "zero crew factor/cancellation count")

    names = contract["report_gate"]["table_order"]
    shapes = contract["report_gate"]["shape_rows_columns"]
    for arm, data in arms.items():
        tables = data["tables"]
        audit.check([table["name"] for table in tables] == names, arm + " exact six report tables")
        cells = 0
        for table in tables:
            row_count, col_count = shapes[table["name"]]
            rows = table["instances"][0]["rows"]
            audit.check(len(table["columns"]) == col_count and len(table["instances"]) == 1 and len(rows) == row_count and all(len(row) == col_count for row in rows), arm + " report shape " + table["name"])
            cells += row_count * col_count
            if table["name"] in {"SystemResults", "StockTotalResults", "ResourceResults"}:
                columns = [column["name"] for column in table["columns"]]
                start, end = columns.index("STINT"), columns.index("ETINT")
                for index, row in enumerate(rows):
                    audit.check(row[start] == index / 2 and row[end] == (index + 1) / 2, arm + " interval " + table["name"] + ":" + str(index))
        audit.check(cells == 5210, arm + " 5210 parsed cells")
        summary = next(table for table in tables if table["name"] == "ResultSummary")
        values = summary["instances"][0]["rows"][0]
        audit.check(all(same(actual, expected) for actual, expected in zip(values, contract["report_gate"]["summary_expected"][arm])), arm + " full 11-field summary")

    equal_tables = arms["crew-equal"]["tables"]
    parent_tables = read_report(c03_run_dir / "report-raw.json")
    audit.check((arms["crew-equal"]["dir"] / "report-raw.json").read_bytes() == (c03_run_dir / "report-raw.json").read_bytes(), "equal report byte-identical C03 staffing1")
    diff_counts: dict[str, list[int]] = {}
    for arm in ("aircraft-missing", "crew-zero"):
        changes = []
        for baseline, observed in zip(equal_tables, arms[arm]["tables"]):
            name = baseline["name"]
            audit.check(baseline["columns"] == observed["columns"] and baseline["name"] == observed["name"], arm + " report schema " + name)
            columns = [item["name"] for item in baseline["columns"]]
            prior_rows, current_rows = baseline["instances"][0]["rows"], observed["instances"][0]["rows"]
            changed = 0
            for row_index, (prior, current) in enumerate(zip(prior_rows, current_rows)):
                for index, (before, actual) in enumerate(zip(prior, current)):
                    expected = expected_shortage(arm, name, row_index, columns[index], before)
                    audit.check(same(actual, expected), arm + " complete report cell " + name + "/" + str(row_index) + "/" + columns[index])
                    changed += actual != before
            changes.append(changed)
        diff_counts[arm] = changes
        audit.check(changes == contract["report_gate"]["changed_cells_vs_crew_equal"][arm], arm + " declared six-table diff counts")
    for baseline, parent in zip(equal_tables, parent_tables):
        audit.check(baseline["columns"] == parent["columns"] and baseline["name"] == parent["name"], "C03 baseline schema " + baseline["name"])
        for row_index, (row1, row2) in enumerate(zip(baseline["instances"][0]["rows"], parent["instances"][0]["rows"])):
            for col_index, (value1, value2) in enumerate(zip(row1, row2)):
                audit.check(value1 == value2, "C03 equal complete report cell " + baseline["name"] + "/" + str(row_index) + "/" + str(col_index))
    result = {"schema": "simlox-c04-var01-independent-replay/v1", "decision": "GO_BOUNDED" if not audit.failures else "NO_GO", "checks": audit.checks, "failures": audit.failures, "contract_sha256": digest(contract_bytes), "raw_seals": {"c04": 33, "c03": 11}, "report_cells_per_arm": 5210, "diff_counts_vs_equal": diff_counts, "limits": ["Read-only reuse of three accepted fixed-source CLI traces; no native rerun", "Aircraft-missing jointly changes QTYPS and RQTY", "Generic cancellation text carries no structured reason code", "No general cutoff/resource-allocation or GUI-only behavior rule"]}
    VERDICT.write_bytes((json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    return result


if __name__ == "__main__":
    result = run()
    print(result["decision"], result["checks"], len(result["failures"]))
    for failure in result["failures"][:30]:
        print("FAIL:", failure)

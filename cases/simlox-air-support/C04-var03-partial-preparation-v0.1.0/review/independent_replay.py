"""Independent stdlib-only read of accepted C04.var03 source and sealed raw evidence."""

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


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parsed(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: pathlib.Path) -> list[dict]:
    source = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", source))["report"]["tables"]


def leaves(value: object, prefix: tuple = ()) -> dict:
    if isinstance(value, dict):
        return {p: v for k, child in value.items() for p, v in leaves(child, prefix + (k,)).items()}
    if isinstance(value, list):
        return {p: v for k, child in enumerate(value) for p, v in leaves(child, prefix + (k,)).items()}
    return {prefix: value}


def col(source: dict, table_name: str, column_name: str) -> object:
    table = next(t for t in source["model"]["tables"] if t["name"] == table_name)
    names = [c["name"] for c in table["columns"]]
    return table["instances"][0]["rows"][0][names.index(column_name)]


def in_order(content: str, pieces: list[str]) -> bool:
    pos = 0
    for piece in pieces:
        at = content.find(piece, pos)
        if at < 0:
            return False
        pos = at + len(piece)
    return True


def equal(actual: object, expected: object) -> bool:
    if isinstance(actual, (int, float)) and not isinstance(actual, bool) and isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return abs(actual - expected) <= 3e-5
    return actual == expected


class Audit:
    def __init__(self) -> None:
        self.checks = 0
        self.failures: list[str] = []

    def check(self, okay: bool, label: str) -> None:
        self.checks += 1
        if not okay:
            self.failures.append(label)

    def sealed(self, path: pathlib.Path, pin: dict, label: str) -> None:
        self.checks += 1
        try:
            data = path.read_bytes()
            if (len(data), sha(data)) != (pin["bytes"], pin["sha256"]):
                self.failures.append(label + " SHA/size")
        except (OSError, KeyError) as exc:
            self.failures.append(label + " " + str(exc))


def run() -> dict:
    a = Audit()
    contract_bytes = (PACKAGE / "contract.json").read_bytes()
    c = json.loads(contract_bytes)
    a.check(sha(contract_bytes) == "8430c74254baae1401edb92df41f1dee0ae7a30c9628e5f21b2d56197bd34d3d", "frozen contract")
    a.check(c["variant_id"] == "C04.var03" and "0.1.0" in c["version"] and not c["ownership"]["native_child_planned"], "read-only identity")
    a.sealed(pathlib.Path(c["manual"]["installed_pdf_path"]), c["manual"]["installed_pdf"], "installed manual")
    accepted = c["accepted_source"]
    accepted_dir = CASES / accepted["package"]
    for field, filename in (("contract", "contract.json"), ("evidence_report", "evidence-2026-09-29.md"), ("independent_review", "review/independent-readonly-2026-09-29.json")):
        a.sealed(accepted_dir / filename, accepted[field], "C04 " + field)
    a.check(len(accepted["published_source_files"]) == 25, "25 published C04 sources")
    for record in accepted["published_source_files"]:
        file = accepted_dir / record["path"]
        a.sealed(file, record["local_disk"], "C04 disk " + record["path"])
        rel = file.relative_to(REPO).as_posix()
        p = subprocess.run(["git", "show", "HEAD:" + rel], cwd=REPO, capture_output=True, check=False)
        a.check(p.returncode == 0, "C04 Git exists " + rel)
        if p.returncode == 0:
            pin = record["published_git"]
            a.check((len(p.stdout), sha(p.stdout)) == (pin["bytes"], pin["sha256"]), "C04 Git " + rel)
    overlap = c["accepted_published_overlap"]["source_pins"]
    a.check(len(overlap) == 4, "four C04.var02 overlap pins")
    for name, pin in overlap.items():
        file = REPO / pin["path"]
        a.sealed(file, pin["local_disk"], "overlap disk " + name)
        p = subprocess.run(["git", "show", "HEAD:" + pin["path"]], cwd=REPO, capture_output=True, check=False)
        a.check(p.returncode == 0, "overlap Git exists " + name)
        if p.returncode == 0:
            ref = pin["published_git"]
            a.check((len(p.stdout), sha(p.stdout)) == (ref["bytes"], ref["sha256"]), "overlap Git " + name)
    parent = c["direct_c03_parent"]
    parent_dir = CASES / parent["package"]
    for field, filename in (("contract", "contract.json"), ("evidence_report", "evidence-2026-09-29.md"), ("independent_review", "review/independent-readonly-2026-09-29.json")):
        a.sealed(parent_dir / filename, parent[field], "C03 " + field)
        rel = (parent_dir / filename).relative_to(REPO).as_posix()
        blob = subprocess.run(["git", "show", "HEAD:" + rel], cwd=REPO, capture_output=True, check=False)
        a.check(blob.returncode == 0 and (len(blob.stdout), sha(blob.stdout)) == (parent[field]["bytes"], parent[field]["sha256"]), "C03 Git " + field)
    a.sealed(REPO / parent["staffing_one_input"]["path"], parent["staffing_one_input"], "C03 staffing1 source")
    blob = subprocess.run(["git", "show", "HEAD:" + parent["staffing_one_input"]["path"]], cwd=REPO, capture_output=True, check=False)
    a.check(blob.returncode == 0 and (len(blob.stdout), sha(blob.stdout)) == (parent["staffing_one_input"]["bytes"], parent["staffing_one_input"]["sha256"]), "C03 Git staffing1 input")
    parent_run = parent["staffing_one_run"]
    pr = pathlib.Path(parent_run["local_run_dir"])
    a.sealed(pr / "closure.json", parent_run["closure"], "C03 closure")
    a.sealed(pr / "invocation.json", parent_run["invocation"], "C03 invocation")
    a.check(len(parent_run["raw"]) == 11, "C03 11 raw seals")
    for name, pin in parent_run["raw"].items():
        a.sealed(pr / name, pin, "C03 raw " + name)
    a.check(parsed(pr / "closure.json")["raw"] == parent_run["raw"], "C03 manifest")
    bad = c["excluded_evidence"]["horizon_wait"]
    bad_run = accepted_dir / "runs" / bad["run_id"]
    a.sealed(bad_run / "run.log", bad["run_log"], "excluded horizon log")
    a.check((bad_run / "model.sxo").stat().st_size == 4, "horizon invalid SXO")
    a.check("error #107" in (bad_run / "run.log").read_text(encoding="utf-8-sig") and "error #204" in (bad_run / "run.log").read_text(encoding="utf-8-sig"), "excluded errors")
    a.check(len(c["excluded_evidence"]["discovery_runs"]) == 5, "five discovery runs excluded")

    arms: dict[str, dict] = {}
    for arm, dtim in (("crew-equal", 0.5), ("crew-after", 0.49)):
        pin = accepted["arms"][arm]
        d = pathlib.Path(pin["local_run_dir"])
        a.sealed(REPO / pin["input"]["path"], pin["input"], arm + " input")
        a.sealed(REPO / pin["parent_diff"]["path"], pin["parent_diff"], arm + " parent diff")
        for field, filename in (("closure", "closure.json"), ("invocation", "invocation.json"), ("model_log", "model.log"), ("report_raw", "report-raw.json")):
            a.sealed(d / filename, pin[field], arm + " " + field)
        a.check(len(pin["raw"]) == 11, arm + " 11 raw seals")
        for name, raw_pin in pin["raw"].items():
            a.sealed(d / name, raw_pin, arm + " raw " + name)
        closure, invocation, steps = (parsed(d / name) for name in ("closure.json", "invocation.json", "steps.json"))
        a.check(closure["raw"] == pin["raw"] and closure["input_sha256"] == pin["input"]["sha256"] and closure["invocation_sha256"] == pin["invocation"]["sha256"], arm + " closure binding")
        source = parsed(REPO / pin["input"]["path"])
        a.check((REPO / pin["input"]["path"]).read_bytes() == (d / "input.json").read_bytes(), arm + " copied source bytes")
        a.check(len(source["model"]["tables"]) == 31 and len(leaves(source)) == 979, arm + " source structure")
        a.check(sum(len(row) for table in source["model"]["tables"] for instance in table["instances"] for row in instance["rows"]) == 201, arm + " 201 authored cells")
        a.check(col(source, "OperationProfile", "STIM") == 8 and col(source, "OperationProfile", "DTIM") == dtim and col(source, "MissionType", "NOPER") == 0.5, arm + " schedule")
        exported = parsed(d / "roundtrip-raw.json")
        authored_tables = {t["name"]: t for t in source["model"]["tables"]}
        exported_tables = {t["name"]: t for t in exported["model"]["tables"]}
        a.check(authored_tables.keys() == exported_tables.keys(), arm + " roundtrip topology")
        for name, table in authored_tables.items():
            if any(instance["rows"] for instance in table["instances"]):
                a.check(table == exported_tables[name], arm + " exact row-containing roundtrip " + name)
            else:
                a.check(all(all(cell is None for cell in row) for instance in exported_tables[name]["instances"] for row in instance["rows"]), arm + " null placeholder " + name)
        a.check(invocation["run_id"] == pin["run_id"] and invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0, arm + " SSH0 identity")
        a.check(invocation["ssh_connection_present"] and invocation["ssh_client_present"] and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", arm + " SSH/mutex")
        gui = invocation["coexisting_gui"]
        a.check(gui["pid"] == 13340 and gui["session_id"] == 1 and gui["responding_at_preflight"] and gui["process_start_utc"] == "2026-09-28T10:09:56.8261381Z", arm + " GUI preflight identity")
        a.check([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport"], arm + " four ordered stages")
        for step in steps:
            a.check(step["exit_code"] == 0 and step["coexisting_gui_present_after"] is True, arm + " step GUI/exit " + step["name"])
        run_log = (d / "run.log").read_text(encoding="utf-8-sig")
        a.check("Errors: 0, Warnings: 2, Notes: 0" in run_log and re.findall(r"warning #(\d+)", run_log) == ["108", "126"] and "error #" not in run_log, arm + " converter diagnostics")
        a.check((d / "model.sxo").stat().st_size > 4, arm + " valid output")
        arms[arm] = {"source": source, "log": (d / "model.log").read_text(encoding="utf-8-sig"), "tables": report(d / "report-raw.json"), "dir": d}

    equal_leaves = leaves(arms["crew-equal"]["source"])
    after_leaves = leaves(arms["crew-after"]["source"])
    differences = {key: (equal_leaves[key], after_leaves[key]) for key in equal_leaves if equal_leaves[key] != after_leaves[key]}
    table_index = next(i for i, t in enumerate(arms["crew-equal"]["source"]["model"]["tables"]) if t["name"] == "OperationProfile")
    t = arms["crew-equal"]["source"]["model"]["tables"][table_index]
    dtim_index = [x["name"] for x in t["columns"]].index("DTIM")
    expected_path = ("model", "tables", table_index, "instances", 0, "rows", 0, dtim_index)
    a.check(equal_leaves.keys() == after_leaves.keys() and differences == {expected_path: (0.5, 0.49)}, "sole DTIM scalar difference")
    parent_source = parsed(REPO / parent["staffing_one_input"]["path"])
    prior = leaves(parent_source)
    for arm, expected in (("crew-equal", 0.5), ("crew-after", 0.49)):
        current = leaves(arms[arm]["source"])
        a.check(current.keys() == prior.keys(), arm + " C03 topology")
        a.check({k: (prior[k], current[k]) for k in prior if prior[k] != current[k]} == {expected_path: (1, expected)}, arm + " sole C03 DTIM delta")

    m = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    common = ["Time: 7.5 " + m + " mission allocates system: <TEACH-AIR-01,0>", "Time: 7.5 " + m + " mission allocates system: <TEACH-AIR-01,1>", "Time: 7.5  <P-CREW at <BASE-01,0>> allocated", "Time: 8  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed", "Time: 8  <P-CREW at <BASE-01,0>> deallocated", "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> resource received", "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> books resources", "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> starts performing"]
    for arm in arms:
        a.check(in_order(arms[arm]["log"], common), arm + " shared owner/crew chronology")
    control = arms["crew-equal"]["log"]
    a.check(in_order(control, ["Time: 8.5  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> completed", "Time: 8.5  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> frees resources", "Time: 8.5  <P-CREW at <BASE-01,0>> deallocated", "Time: 8.5 " + m + " mission starting", "Time: 9.5 " + m + " mission success", "Time: 9.5 " + m + " mission completed", "Time: 9.5 <TEACH-UNIT at <BASE-01,0>> systems ready: 2"]), "control completion/release/launch")
    a.check("mission cancelled" not in control, "control no cancellation")
    partial = arms["crew-after"]["log"]
    cleanup = ["Time: 8.49 " + m + " mission cancelled", "Time: 8.49  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> ordered to stop", "Time: 8.49  system preparation task 1 on <TEACH-AIR-01,1> stopped", "Time: 8.49 <TEACH-AIR-01,1> preparation ended", "Time: 8.49 <TEACH-AIR-01,1> turnround started, mission: " + m + " reduction factor: 0.98", "Time: 8.49 <TEACH-AIR-01,0> turnround started, mission: " + m + " reduction factor: 1", "Time: 8.49  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> frees resources", "Time: 8.49  <P-CREW at <BASE-01,0>> deallocated", "Time: 8.49  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> stopped", "Time: 8.49  subtask 1 seqno 1 check return remote resources", "Time: 8.49 <TEACH-AIR-01,1> turnround ended", "Time: 8.49 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,1>", "Time: 8.49 <TEACH-AIR-01,0> turnround ended", "Time: 8.49 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>", "Time: 8.49 <TEACH-UNIT at <BASE-01,0>> systems ready: 2"]
    a.check(in_order(partial, cleanup), "partial ID1 stop/factor/lease/arrival and ID0 ready chronology")
    a.check(partial.count("subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> completed") == 0, "ID1 subtask never completed")
    a.check(partial.count("Time: 8.49  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> frees resources") == 1 and partial.count("Time: 8.49  <P-CREW at <BASE-01,0>> deallocated") == 1, "ID1 crew released exactly once")
    a.check(partial.count("mission cancelled") == 1 and "mission starting" not in partial and "mission success" not in partial, "partial cancellation without launch")
    a.check(partial.count("reduction factor: 0.98") == 1 and partial.count("reduction factor: 1") == 1, "distinct owner factors")
    a.check(abs((0.49 / 0.5) - .98) < 1e-12, "source-bound fraction comparison")
    a.check("Time: 8.49 <BASE-01,0> trig missions and tasks waiting for resources" in partial and "Tasks waiting for resources at: <BASE-01,0> 0" in partial.split("Time: 8.49 <BASE-01,0> trig missions and tasks waiting for resources", 1)[1], "h8.49 zero remaining resource waiters")

    names = c["report_gate"]["table_order"]
    shapes = c["report_gate"]["shape_rows_columns"]
    for arm, data in arms.items():
        tables = data["tables"]
        a.check([t["name"] for t in tables] == names, arm + " exact six report tables")
        total = 0
        for table in tables:
            nrows, ncols = shapes[table["name"]]
            rows = table["instances"][0]["rows"]
            a.check(len(table["columns"]) == ncols and len(table["instances"]) == 1 and len(rows) == nrows and all(len(row) == ncols for row in rows), arm + " table shape " + table["name"])
            total += nrows * ncols
            if table["name"] in {"SystemResults", "StockTotalResults", "ResourceResults"}:
                cols = [x["name"] for x in table["columns"]]
                st, en = cols.index("STINT"), cols.index("ETINT")
                for i, row in enumerate(rows):
                    a.check(row[st] == i / 2 and row[en] == (i + 1) / 2, arm + " interval " + table["name"] + "/" + str(i))
        a.check(total == 5210, arm + " 5210 parsed cells")
        summary = next(t for t in tables if t["name"] == "ResultSummary")["instances"][0]["rows"][0]
        a.check(len(summary) == 11 and all(equal(x, y) for x, y in zip(summary, c["report_gate"]["summary_expected"][arm])), arm + " full summary")
    a.check((arms["crew-equal"]["dir"] / "report-raw.json").read_bytes() == (pr / "report-raw.json").read_bytes(), "control report byte-identical C03 staffing1")

    # Reconstruct all changed cells from the partial owner timeline. Every other
    # field, including nulls and descriptions, must equal the accepted control.
    modifications = {
        ("ResultSummary", 0, "MTMF"): 0, ("ResultSummary", 0, "MSTF"): 0,
        ("ResultSummary", 0, "MSUF"): 0, ("ResultSummary", 0, "STMF"): 0,
        ("SystemResults", 16, "NSYRY"): .04, ("SystemResults", 16, "NSYMA"): 1.96,
        ("SystemResults", 16, "NSYMP"): .98, ("SystemResults", 16, "NSYMR"): .98,
        ("ResourceResults", 16, "NRUM"): .98,
        ("ResourceResultsTotal", 0, "NRUM"): .99 / 36,
    }
    for i in (17, 18):
        modifications.update({("SystemResults", i, "NSYRY"): 2, ("SystemResults", i, "NSYMA"): 0,
                              ("SystemResults", i, "NSYMO"): 0, ("SystemResults", i, "FTMO"): 0,
                              ("SystemResults", i, "STACC"): 0})
    modifications[("SystemResults", 17, "NPSUC")] = 0
    counts = []
    for baseline, changed in zip(arms["crew-equal"]["tables"], arms["crew-after"]["tables"]):
        name = baseline["name"]
        a.check(name == changed["name"] and baseline["columns"] == changed["columns"], "report schema parity " + name)
        columns = [x["name"] for x in baseline["columns"]]
        old_rows = baseline["instances"][0]["rows"]
        new_rows = changed["instances"][0]["rows"]
        count = 0
        for row_index, (old_row, new_row) in enumerate(zip(old_rows, new_rows)):
            for index, (before, actual) in enumerate(zip(old_row, new_row)):
                expected = modifications.get((name, row_index, columns[index]), before)
                a.check(equal(actual, expected), "complete report cell " + name + "/" + str(row_index) + "/" + columns[index])
                count += actual != before
        counts.append(count)
    a.check(counts == c["report_gate"]["equal_vs_partial_changed_cells"] == [0, 4, 15, 0, 1, 1], "declared report differences")
    a.check(sum(counts) == len(modifications) == 21, "all 21 deviations explicitly reconstructed")
    baseline = report(pr / "report-raw.json")
    for parent_table, control_table in zip(baseline, arms["crew-equal"]["tables"]):
        a.check(parent_table["columns"] == control_table["columns"] and parent_table["name"] == control_table["name"], "C03 control report schema " + parent_table["name"])
        for row_index, (row1, row2) in enumerate(zip(parent_table["instances"][0]["rows"], control_table["instances"][0]["rows"])):
            for index, (x, y) in enumerate(zip(row1, row2)):
                a.check(x == y, "C03 control report cell " + parent_table["name"] + "/" + str(row_index) + "/" + str(index))

    result = {"schema": "simlox-c04-var03-independent-replay/v1", "decision": "GO_BOUNDED" if not a.failures else "NO_GO", "checks": a.checks, "failures": a.failures, "contract_sha256": sha(contract_bytes), "raw_seals": {"c04": 22, "c03": 11}, "report_cells_per_arm": 5210, "equal_partial_difference_counts": counts, "scope": "Read-only owner-level reclassification of accepted C04 equal/after final CLI runs; no new native result", "limits": ["Previously published C04.var02 already used these runs and verified the cutoff contrast", "No general partial-work factor or same-time ordering law", "No structured cancellation reason or fresh GUI capture"]}
    VERDICT.write_bytes((json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    return result


if __name__ == "__main__":
    result = run()
    print(result["decision"], result["checks"], len(result["failures"]))
    for failure in result["failures"][:20]:
        print("FAIL:", failure)

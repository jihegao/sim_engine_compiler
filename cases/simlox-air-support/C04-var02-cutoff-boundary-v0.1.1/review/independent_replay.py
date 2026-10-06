"""Independent, read-only replay of sealed C04.var02 evidence (stdlib only)."""

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
CONTRACT_PATH = PACKAGE / "contract.json"
VERDICT_PATH = HERE / "independent-verdict.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parsed(path: pathlib.Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: pathlib.Path) -> dict:
    # The historical CLI exporter leaves a trailing comma. Only this parser copy
    # is normalized; the sealed raw file stays byte-for-byte untouched.
    source = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", source))["report"]


def leaves(value: object, path: tuple = ()) -> dict:
    if isinstance(value, dict):
        out = {}
        for key, sub in value.items():
            out.update(leaves(sub, path + (key,)))
        return out
    if isinstance(value, list):
        out = {}
        for idx, sub in enumerate(value):
            out.update(leaves(sub, path + (idx,)))
        return out
    return {path: value}


def table(model: dict, name: str) -> dict:
    matches = [t for t in model["model"]["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"expected one {name} table, got {len(matches)}")
    return matches[0]


def exact_lines_in_order(content: str, fragments: list[str]) -> bool:
    position = 0
    for fragment in fragments:
        found = content.find(fragment, position)
        if found < 0:
            return False
        position = found + len(fragment)
    return True


class Audit:
    def __init__(self) -> None:
        self.count = 0
        self.failures: list[str] = []

    def check(self, condition: bool, label: str) -> None:
        self.count += 1
        if not condition:
            self.failures.append(label)

    def sealed(self, path: pathlib.Path, pin: dict, label: str) -> None:
        self.count += 1
        try:
            data = path.read_bytes()
            if (len(data), sha(data)) != (pin["bytes"], pin["sha256"]):
                self.failures.append(label + ": SHA/size")
        except (OSError, KeyError) as exc:
            self.failures.append(label + f": {exc}")


def run() -> dict:
    audit = Audit()
    contract_data = CONTRACT_PATH.read_bytes()
    contract = json.loads(contract_data.decode("utf-8"))
    audit.check(
        sha(contract_data) == "0d71443048ec3499d0610e73e702409574c6e52df80047102b18cb12bd5069ee",
        "frozen corrected contract SHA",
    )
    audit.check(contract["variant_id"] == "C04.var02" and "0.1.1" in contract["version"], "case/version")
    old = CASES / "C04-var02-cutoff-boundary-v0.1.0"
    audit.check(
        sha((old / "contract.json").read_bytes())
        == "9f30694d4046b0d15cdfd72f89563e9f159980130d8055825bd3ce6893b3c555",
        "excluded original contract preserved",
    )
    audit.check(
        sha((old / "review" / "independent-contract-no-go-2026-10-07.md").read_bytes())
        == "ea388c2092743ccfa46030c40ffe8360b52e4eb3aed1a68c25af0c39f16d2a2d",
        "excluded original NO_GO preserved",
    )
    audit.sealed(pathlib.Path(contract["manual"]["installed_pdf_path"]), contract["manual"]["installed_pdf"], "installed manual")

    accepted = contract["accepted_source"]
    accepted_dir = CASES / accepted["package"]
    for field, name in (
        ("contract", "contract.json"),
        ("evidence_report", "evidence-2026-09-29.md"),
        ("independent_review", "review/independent-readonly-2026-09-29.json"),
    ):
        audit.sealed(accepted_dir / name, accepted[field], "C04 " + field)
    audit.check(len(accepted["published_source_files"]) == 25, "25 published C04 source records")
    for record in accepted["published_source_files"]:
        file = accepted_dir / record["path"]
        audit.sealed(file, record["local_disk"], "C04 disk " + record["path"])
        rel = file.relative_to(REPO).as_posix()
        blob = subprocess.run(["git", "show", "HEAD:" + rel], cwd=REPO, capture_output=True, check=False)
        audit.check(blob.returncode == 0, "C04 Git blob exists " + rel)
        if blob.returncode == 0:
            pin = record["published_git"]
            audit.check((len(blob.stdout), sha(blob.stdout)) == (pin["bytes"], pin["sha256"]), "C04 Git blob " + rel)

    c03 = contract["direct_c03_parent"]
    c03_dir = CASES / c03["package"]
    for field, name in (
        ("contract", "contract.json"),
        ("evidence_report", "evidence-2026-09-29.md"),
        ("independent_review", "review/independent-readonly-2026-09-29.json"),
    ):
        audit.sealed(c03_dir / name, c03[field], "C03 " + field)
    audit.sealed(REPO / c03["staffing_one_input"]["path"], c03["staffing_one_input"], "C03 staffing-1 input")
    parent_run = c03["staffing_one_run"]
    parent_dir = pathlib.Path(parent_run["local_run_dir"])
    audit.sealed(parent_dir / "closure.json", parent_run["closure"], "C03 closure")
    audit.sealed(parent_dir / "invocation.json", parent_run["invocation"], "C03 invocation")
    audit.check(len(parent_run["raw"]) == 11, "C03 11 raw records")
    for name, pin in parent_run["raw"].items():
        audit.sealed(parent_dir / name, pin, "C03 raw " + name)
    parent_closure = parsed(parent_dir / "closure.json")
    audit.check(parent_closure["raw"] == parent_run["raw"], "C03 closure/raw manifest")
    parent_input = parsed(REPO / c03["staffing_one_input"]["path"])
    parent_report_bytes = (parent_dir / "report-raw.json").read_bytes()

    excluded = contract["excluded_evidence"]["horizon_wait"]
    excluded_dir = accepted_dir / "runs" / excluded["run_id"]
    audit.sealed(excluded_dir / "run.log", excluded["run_log"], "excluded horizon-wait log")
    audit.check((excluded_dir / "model.sxo").stat().st_size == 4, "excluded horizon-wait invalid SXO")
    horizon_log = (excluded_dir / "run.log").read_text(encoding="utf-8-sig")
    audit.check("error #107" in horizon_log and "error #204" in horizon_log, "excluded converter errors #107/#204")

    arms: dict[str, dict] = {}
    expected_dtims = {"crew-before": 0.51, "crew-equal": 0.5, "crew-after": 0.49}
    expected_clocks = {"crew-before": "08:30:36", "crew-equal": "08:30:00", "crew-after": "08:29:24"}
    for arm, dtim in expected_dtims.items():
        pin = accepted["arms"][arm]
        path = pathlib.Path(pin["local_run_dir"])
        audit.sealed(REPO / pin["input"]["path"], pin["input"], arm + " authored input")
        audit.sealed(REPO / pin["parent_diff"]["path"], pin["parent_diff"], arm + " parent diff")
        for field, name in (("closure", "closure.json"), ("invocation", "invocation.json"), ("model_log", "model.log"), ("report_raw", "report-raw.json")):
            audit.sealed(path / name, pin[field], arm + " " + field)
        audit.check(len(pin["raw"]) == 11, arm + " 11 raw records")
        for name, raw_pin in pin["raw"].items():
            audit.sealed(path / name, raw_pin, arm + " raw " + name)
        closure = parsed(path / "closure.json")
        invocation = parsed(path / "invocation.json")
        steps = parsed(path / "steps.json")
        source = parsed(REPO / pin["input"]["path"])
        copied = parsed(path / "input.json")
        roundtrip = parsed(path / "roundtrip-raw.json")
        audit.check(closure["raw"] == pin["raw"], arm + " closure/raw manifest")
        audit.check(closure["input_sha256"] == pin["input"]["sha256"], arm + " closure input pin")
        audit.check(closure["invocation_sha256"] == pin["invocation"]["sha256"], arm + " closure invocation pin")
        audit.check((REPO / pin["input"]["path"]).read_bytes() == (path / "input.json").read_bytes(), arm + " copied input bytes")
        audit.check(source == copied, arm + " copied input structure")
        audit.check(len(source["model"]["tables"]) == 31, arm + " 31 authored tables")
        audit.check(len(leaves(source)) == 979, arm + " 979 scalar leaves")
        audit.check(sum(len(row) for t in source["model"]["tables"] for inst in t["instances"] for row in inst["rows"]) == 201, arm + " 201 authored cells")
        operation = table(source, "OperationProfile")
        names = [c["name"] for c in operation["columns"]]
        audit.check(operation["instances"][0]["rows"][0][names.index("DTIM")] == dtim, arm + " DTIM")
        audit.check(operation["instances"][0]["rows"][0][names.index("STIM")] == 8, arm + " STIM")
        audit.check(abs(contract["source_panel"]["latest_launch_hours"][arm] - (8 + dtim)) < 1e-12, arm + " latest launch hour")
        audit.check(contract["source_panel"]["latest_launch_clocks"][arm] == expected_clocks[arm], arm + " latest launch clock")
        mission = table(source, "MissionType")
        mission_names = [c["name"] for c in mission["columns"]]
        audit.check(mission["instances"][0]["rows"][0][mission_names.index("NOPER")] == 0.5, arm + " NOPER")
        original_tables = {t["name"]: t for t in source["model"]["tables"]}
        exported_tables = {t["name"]: t for t in roundtrip["model"]["tables"]}
        audit.check(original_tables.keys() == exported_tables.keys(), arm + " roundtrip table names")
        for name, authored_table in original_tables.items():
            if any(instance["rows"] for instance in authored_table["instances"]):
                audit.check(authored_table == exported_tables[name], arm + " exact row-containing roundtrip " + name)
            else:
                audit.check(all(all(value is None for value in row) for instance in exported_tables[name]["instances"] for row in instance["rows"]), arm + " null-only exported placeholder " + name)
        audit.check(invocation["run_id"] == pin["run_id"] and invocation["session_id"] == 0, arm + " invocation identity/session0")
        audit.check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["ssh_connection_present"] and invocation["ssh_client_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], arm + " SSH ancestry")
        audit.check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", arm + " mutex")
        gui = invocation["coexisting_gui"]
        audit.check(gui["pid"] == 13340 and gui["session_id"] == 1 and gui["responding_at_preflight"] and gui["process_start_utc"] == "2026-09-28T10:09:56.8261381Z", arm + " GUI preflight")
        audit.check([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport"], arm + " four stages")
        for step in steps:
            audit.check(step["exit_code"] == 0 and step["coexisting_gui_present_after"] is True, arm + " stage " + step["name"] + " exit/GUI identity")
        run_log = (path / "run.log").read_text(encoding="utf-8-sig")
        audit.check("Errors: 0, Warnings: 2, Notes: 0" in run_log, arm + " converter counts")
        audit.check(re.findall(r"warning #(\d+)", run_log) == ["108", "126"] and "error #" not in run_log, arm + " exact converter warnings")
        audit.check((path / "model.sxo").stat().st_size > 4, arm + " valid SXO size")
        log = (path / "model.log").read_text(encoding="utf-8-sig")
        common = [
            "Time: 7.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission activated, systems requested: 2",
            "Time: 7.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>",
            "Time: 7.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,1>",
            "Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing",
            "request for: 1 failed",
            "Time: 8  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed",
            "Time: 8  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
            "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> resource availability test",
            "request for: 1 OK",
            "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> resource received",
            "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> books resources",
            "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> starts performing, planned to last for 0.5 hours",
        ]
        audit.check(exact_lines_in_order(log, common), arm + " common physical event order")
        arms[arm] = {"path": path, "source": source, "log": log, "tables": report(path / "report-raw.json")["tables"]}

    original = leaves(parent_input)
    before = leaves(arms["crew-before"]["source"])
    candidates = [k for k in original if k[-1] == 8 and original[k] == 1.0 and before.get(k) == 0.51]
    audit.check(len(candidates) == 1, "one unique changed OperationProfile DTIM scalar")
    expected_path = candidates[0]
    audit.check(expected_path == ("model", "tables", 14, "instances", 0, "rows", 0, 8), "changed scalar located in OperationProfile.DTIM")
    for arm, dtim in expected_dtims.items():
        current = leaves(arms[arm]["source"])
        audit.check(current.keys() == original.keys(), arm + " source topology vs C03")
        for key, value in original.items():
            audit.check(current[key] == (dtim if key == expected_path else value), arm + " C03 parent leaf " + str(key))
    for first, second in (("crew-before", "crew-equal"), ("crew-before", "crew-after"), ("crew-equal", "crew-after")):
        left, right = leaves(arms[first]["source"]), leaves(arms[second]["source"])
        for key, value in left.items():
            audit.check(right[key] == (expected_dtims[second] if key == expected_path else value), first + "/" + second + " leaf " + str(key))
    audit.check((arms["crew-before"]["path"] / "model.log").read_bytes() == (arms["crew-equal"]["path"] / "model.log").read_bytes(), "before/equal byte-identical model.log")
    audit.check((arms["crew-before"]["path"] / "report-raw.json").read_bytes() == (arms["crew-equal"]["path"] / "report-raw.json").read_bytes(), "before/equal byte-identical report")
    audit.check((arms["crew-before"]["path"] / "report-raw.json").read_bytes() == parent_report_bytes, "before report byte-identical C03 staffing-1")

    shared_success = [
        "Time: 8.5  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> completed",
        "Time: 8.5  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> frees resources",
        "Time: 8.5  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
        "Time: 8.5 <TEACH-AIR-01,1> preparation ended",
        "Time: 8.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>",
        "Time: 9.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success",
        "Time: 9.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>",
        "Time: 9.5 <TEACH-UNIT at <BASE-01,0>> systems ready: 2",
    ]
    for arm in ("crew-before", "crew-equal"):
        log = arms[arm]["log"]
        audit.check(exact_lines_in_order(log, shared_success), arm + " success chronology")
        audit.check("mission cancelled" not in log, arm + " no cancellation")
    after_log = arms["crew-after"]["log"]
    cleanup = [
        "Time: 8.49 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled",
        "Time: 8.49  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> ordered to stop",
        "Time: 8.49  system preparation task 1 on <TEACH-AIR-01,1> stopped",
        "Time: 8.49 <TEACH-AIR-01,1> preparation ended",
        "Time: 8.49 <TEACH-AIR-01,1> turnround started, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0> reduction factor: 0.98",
        "Time: 8.49  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> frees resources",
        "Time: 8.49  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
        "Time: 8.49  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> stopped",
        "Time: 8.49 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,1>",
        "Time: 8.49 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>",
        "Time: 8.49 <TEACH-UNIT at <BASE-01,0>> systems ready: 2",
    ]
    audit.check(exact_lines_in_order(after_log, cleanup), "after cancellation/cleanup chronology")
    audit.check("mission starting" not in after_log and "mission success" not in after_log, "after no launch or success")

    table_names = ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"]
    expected_shapes = [(1, 1), (1, 11), (72, 40), (72, 16), (72, 16), (1, 14)]
    for arm in expected_dtims:
        tables = arms[arm]["tables"]
        audit.check([t["name"] for t in tables] == table_names, arm + " six report tables")
        count = 0
        for t, (rows, cols) in zip(tables, expected_shapes):
            audit.check(len(t["columns"]) == cols and len(t["instances"]) == 1 and len(t["instances"][0]["rows"]) == rows, arm + " shape " + t["name"])
            count += rows * cols
            if t["name"] in ("SystemResults", "StockTotalResults", "ResourceResults"):
                st = [c["name"] for c in t["columns"]].index("STINT")
                et = [c["name"] for c in t["columns"]].index("ETINT")
                for idx, row in enumerate(t["instances"][0]["rows"]):
                    audit.check(row[st] == idx / 2 and row[et] == (idx + 1) / 2, arm + " interval " + t["name"] + ":" + str(idx))
        audit.check(count == 5210, arm + " 5210 report cells")

    # Reconstruct every after-arm cell from the independently sealed C03/before
    # report and the event-derived fractional/mission changes. All remaining
    # cells must retain their exact baseline values.
    deviations = {
        ("ResultSummary", 0, "MTMF"): 0,
        ("ResultSummary", 0, "MSTF"): 0,
        ("ResultSummary", 0, "MSUF"): 0,
        ("ResultSummary", 0, "STMF"): 0,
        ("SystemResults", 16, "NSYRY"): 0.03999999910593033,
        ("SystemResults", 16, "NSYMA"): 1.9600000381469727,
        ("SystemResults", 16, "NSYMP"): 0.9800000190734863,
        ("SystemResults", 16, "NSYMR"): 0.9800000190734863,
        ("SystemResults", 17, "NSYRY"): 2,
        ("SystemResults", 17, "NSYMA"): 0,
        ("SystemResults", 17, "NSYMO"): 0,
        ("SystemResults", 17, "FTMO"): 0,
        ("SystemResults", 17, "STACC"): 0,
        ("SystemResults", 17, "NPSUC"): 0,
        ("SystemResults", 18, "NSYRY"): 2,
        ("SystemResults", 18, "NSYMA"): 0,
        ("SystemResults", 18, "NSYMO"): 0,
        ("SystemResults", 18, "FTMO"): 0,
        ("SystemResults", 18, "STACC"): 0,
        ("ResourceResults", 16, "NRUM"): 0.9800000190734863,
        ("ResourceResultsTotal", 0, "NRUM"): 0.027499999850988388,
    }
    actual_diff_counts = []
    for base_table, equal_table, after_table in zip(
        arms["crew-before"]["tables"], arms["crew-equal"]["tables"], arms["crew-after"]["tables"]
    ):
        name = base_table["name"]
        audit.check(base_table["columns"] == equal_table["columns"] == after_table["columns"], "report columns " + name)
        names = [col["name"] for col in base_table["columns"]]
        before_rows = base_table["instances"][0]["rows"]
        equal_rows = equal_table["instances"][0]["rows"]
        after_rows = after_table["instances"][0]["rows"]
        changed = 0
        for row_index, (baseline, equal, after) in enumerate(zip(before_rows, equal_rows, after_rows)):
            for col_index, (old_value, equal_value, after_value) in enumerate(zip(baseline, equal, after)):
                key = (name, row_index, names[col_index])
                audit.check(equal_value == old_value, "equal report cell " + str(key))
                audit.check(after_value == deviations.get(key, old_value), "after report cell " + str(key))
                changed += after_value != old_value
        actual_diff_counts.append(changed)
    audit.check(actual_diff_counts == [0, 4, 15, 0, 1, 1], "exact report difference counts")
    audit.check(len(deviations) == sum(actual_diff_counts) == 21, "all 21 changes accounted")
    for arm in expected_dtims:
        total = arms[arm]["tables"][-1]
        names = [col["name"] for col in total["columns"]]
        row = total["instances"][0]["rows"][0]
        audit.check(row[names.index("NR")] == 1, arm + " terminal crew count")
    result = {
        "schema": "simlox-c04-var02-independent-replay/v1",
        "decision": "GO_BOUNDED" if not audit.failures else "NO_GO",
        "checks": audit.count,
        "failures": audit.failures,
        "contract_sha256": sha(contract_data),
        "raw_seals": {"c04": 33, "c03": 11},
        "report_cells_per_arm": 5210,
        "before_after_diff_counts": actual_diff_counts,
        "scope": "Read-only, three accepted final -02 fixed-seed CLI runs; no general deadline or tie-order rule",
    }
    VERDICT_PATH.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return result


if __name__ == "__main__":
    result = run()
    print(result["decision"], result["checks"], len(result["failures"]))
    for failure in result["failures"][:20]:
        print("FAIL:", failure)

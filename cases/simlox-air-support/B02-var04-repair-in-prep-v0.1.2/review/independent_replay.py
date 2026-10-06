"""Independent, read-only replay of the sealed B02.var04 converter-negative run."""

import hashlib
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parent
RUN_ID = "b02-var04-repair-prep-v012-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
PARENT = ROOT / "B02-serial-preparation-v1.0.2"
PARENT_RUN = Path(r"C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support\B02-serial-preparation-v1.0.2\runs\b02-v102-ssh-20260929-01")
B01 = ROOT / "B01-fixed-preparation-v1.0.1"
B01_RUN = Path(r"C:\Users\user\dev\sim_engine_compiler-b01-v101\cases\simlox-air-support\B01-fixed-preparation-v1.0.1\runs\b01-v101-ssh-20260929-06")
V010 = ROOT / "B02-var04-repair-in-prep-v0.1.0"
V011 = ROOT / "B02-var04-repair-in-prep-v0.1.1"
INPUT_SHA = "e408ff21a8dc9cb7c12ae5acd50d14089846299a4382e40303c9d68edc472d7e"
PARENT_SHA = "fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34"
CONTRACT_SHA = "e8a25202909d7d435f4781e7f7353760ab0ba8f223bd32e65c0e0b8c49bba2fb"
RUNNER_SHA = "f6f4a33c650ce740ebd276de85fe6b247e782740fd263c1f01c66a26ed82a767"
VALIDATOR_SHA = "218171ead143e56bafca88db43ac602ca0fdfa370cb476bb734da17c48f4837e"
APPROVAL_SHA = "eb614ba54f84369c123fbfee3d353621f548f8b027619da2ee2bc9b280c61028"
PARENT_CLOSURE_SHA = "3bbaffe3460da2195a4084cb3b92e1fc9c605a5d01380619abf92e3cd107f570"
B01_CLOSURE_SHA = "046a7724f053f63e6967e3c3e803f726fd5f4b6322015239cb25a380c6446516"
CHILD_CLOSURE_SHA = "aa402a3cd17e387b9bcb1a5e7ca60906b3a39a2acf86e1d247fe079de37efba6"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_json(path):
    """Parse exporter JSON using a copy with trailing commas removed outside strings."""
    text = path.read_bytes().decode("utf-8-sig")
    out = []
    quoted = escaped = False
    for index, char in enumerate(text):
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
        elif char == "," and text[index + 1 :].lstrip().startswith(("]", "}")):
            continue
        else:
            out.append(char)
    return json.loads("".join(out))


def cells(doc):
    result = {}
    for table in doc["model"]["tables"]:
        columns = [column["name"] for column in table["columns"]]
        for instance_index, instance in enumerate(table["instances"]):
            for row_index, row in enumerate(instance["rows"]):
                if len(row) != len(columns):
                    raise ValueError("nonrectangular authored row")
                for field, value in zip(columns, row):
                    key = (table["name"], instance_index, row_index, field)
                    if key in result:
                        raise ValueError("duplicate authored cell")
                    result[key] = value
    return result


def row_tables(doc):
    result = {}
    for table in doc["model"]["tables"]:
        if any(instance["rows"] for instance in table["instances"]):
            result[table["name"]] = {"columns": table["columns"], "instances": table["instances"]}
    return result


class Replay:
    def __init__(self):
        self.checks = 0
        self.failures = []

    def check(self, condition, label):
        self.checks += 1
        if not condition:
            self.failures.append(label)

    def seal(self, folder, closure, expected_count, label):
        raw = closure["raw"]
        self.check(len(raw) == expected_count, f"{label}: raw file count")
        for name, record in sorted(raw.items()):
            path = folder / name
            self.check(path.is_file(), f"{label}: missing {name}")
            if path.is_file():
                self.check(path.stat().st_size == record["bytes"], f"{label}: byte count {name}")
                self.check(sha(path) == record["sha256"], f"{label}: SHA {name}")


def source_paths():
    exe = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
    python = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
    return {
        "child_input": CASE / "native-input.json", "child_contract": CASE / "contract.json",
        "contract_review": HERE / "independent-contract-go-2026-10-06.md",
        "builder": CASE / "build.py", "parent_diff_checker": CASE / "check_parent_diff.py",
        "roundtrip_checker": CASE / "check_roundtrip.py", "shared_parser": ROOT / "tools" / "validate_native.py",
        "behavior_validator": CASE / "validate_negative.py", "runner_script": CASE / "run_native_ssh.ps1",
        "accepted_input": PARENT / "native-input.json", "accepted_contract": PARENT / "contract.json",
        "accepted_diff": PARENT / "parent-diff.json", "accepted_evidence": PARENT / "evidence-2026-09-29.md",
        "accepted_verdict": PARENT / "review" / "independent-readonly-2026-09-29.json",
        "accepted_closure": PARENT_RUN / "closure.json", "prereq_input": B01 / "native-input.json",
        "prereq_contract": B01 / "contract.json", "prereq_evidence": B01 / "evidence-2026-09-29.md",
        "prereq_closure": B01_RUN / "closure.json",
        "positive_input": ROOT / "B05-var05-direct-repair-subtask-v1.0.0" / "native-input.json",
        "excluded_contract": V010 / "contract.json", "excluded_validator": V010 / "validate_negative.py",
        "excluded_review": V010 / "review" / "independent-prelaunch-no-go-2026-10-06.md",
        "excluded_v011_contract": V011 / "contract.json",
        "excluded_v011_validator": V011 / "validate_negative.py",
        "excluded_v011_review": V011 / "review" / "independent-prelaunch-no-go-2026-10-06.md",
        "installed_exe": exe, "installed_manual": manual, "installed_dictionary": dictionary,
        "python": python, "prelaunch_approval": HERE / "independent-prelaunch-go.json",
    }


def replay():
    t = Replay()
    t.check(RUN.is_dir() and RUN.name == RUN_ID, "child run identity")
    t.check(sha(RUN / "closure.json") == CHILD_CLOSURE_SHA, "child closure SHA")
    t.check(sha(PARENT_RUN / "closure.json") == PARENT_CLOSURE_SHA, "B02 closure SHA")
    t.check(sha(B01_RUN / "closure.json") == B01_CLOSURE_SHA, "B01 closure SHA")
    closure = parse_json(RUN / "closure.json")
    invocation = parse_json(RUN / "invocation.json")
    t.check(closure.get("run_id") == RUN_ID and closure.get("error") is None, "child closure status")
    t.check(invocation.get("run_id") == RUN_ID, "invocation run identity")
    t.check(sha(RUN / "invocation.json") == closure.get("invocation_sha256"), "invocation seal")
    t.seal(RUN, closure, 10, "child")
    actual_raw = {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"}
    t.check(actual_raw == set(closure["raw"]), "all child raw files sealed, no extras")
    for label, folder, expected_id in (("B02", PARENT_RUN, "b02-v102-ssh-20260929-01"),
                                       ("B01", B01_RUN, "b01-v101-ssh-20260929-06")):
        control = parse_json(folder / "closure.json")
        t.check(control.get("run_id") == expected_id, f"{label}: closure run identity")
        t.seal(folder, control, 11, label)
    t.check(not (V010 / "runs" / "b02-var04-repair-prep-v010-ssh-20261006-01").exists(), "v010 excluded without run")
    t.check(not (V011 / "runs" / "b02-var04-repair-prep-v011-ssh-20261006-01").exists(), "v011 excluded without run")
    paths = source_paths()
    before = closure["source_hashes_before"]
    after = closure["source_hashes_after"]
    t.check(before == after == invocation["source_hashes_before"], "source fingerprints before/after/invocation")
    t.check(set(before) == set(paths), "source fingerprint label set")
    for label, path in sorted(paths.items()):
        t.check(path.is_file(), f"source absent: {label}")
        if path.is_file():
            t.check(sha(path) == before.get(label), f"source SHA: {label}")
    for label, value in {"child_input": INPUT_SHA, "child_contract": CONTRACT_SHA,
                         "runner_script": RUNNER_SHA, "behavior_validator": VALIDATOR_SHA,
                         "prelaunch_approval": APPROVAL_SHA, "accepted_input": PARENT_SHA,
                         "accepted_closure": PARENT_CLOSURE_SHA,
                         "prereq_closure": B01_CLOSURE_SHA}.items():
        t.check(before.get(label) == value, f"fixed source pin: {label}")
    t.check(invocation.get("input_sha256") == INPUT_SHA and invocation.get("contract_sha256") == CONTRACT_SHA
            and invocation.get("runner_script_sha256") == RUNNER_SHA, "invocation source pins")
    t.check(invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") is True
            and "sshd.exe" in invocation.get("ssh_ancestor_names", []), "SSH0 sshd provenance")
    gui = invocation.get("gui", {})
    t.check(gui.get("pid") == 13340 and gui.get("session_id") == 1
            and gui.get("start_unix_ms") == 1790590196826, "protected GUI identity")
    t.check(invocation.get("queue_mutex") == r"Global\SimloxIssue18NativeQueue", "global mutex identity")
    t.check(sha(RUN / "input.json") == INPUT_SHA == sha(CASE / "native-input.json"), "copied input byte identity")
    parent_cells = cells(parse_json(PARENT / "native-input.json"))
    child_cells = cells(parse_json(CASE / "native-input.json"))
    t.check(len(parent_cells) == len(child_cells) == 185 and parent_cells.keys() == child_cells.keys(), "185-cell source topology")
    changes = {key: (parent_cells[key], child_cells[key]) for key in parent_cells if parent_cells[key] != child_cells[key]}
    t.check(changes == {("TaskBreakDown", 0, 0, "SUTID"): ("INSPECT", "<REPAIR>")}, "sole source cell")
    authored = row_tables(parse_json(RUN / "input.json"))
    exported = row_tables(parse_json(RUN / "roundtrip-raw.json"))
    t.check(len(authored) == 17, "17 authored row-containing tables")
    for table, content in sorted(authored.items()):
        t.check(exported.get(table) == content, f"exact import/export: {table}")
    t.check("Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig"), "import complete")
    t.check("Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig"), "export complete")
    steps = parse_json(RUN / "steps.json")
    t.check([step.get("name") for step in steps] == ["import", "export", "check_import_export", "calc", "check_negative"], "five ordered stages")
    for index, step in enumerate(steps):
        t.check(step.get("status") == "completed" and step.get("exit_code") == 0
                and step.get("gui_preserved") is True, f"stage {index}: completion/exit/GUI")
    planned = invocation.get("planned_commands", [])
    t.check([item.get("name") for item in planned] == ["import", "export", "calc"], "three native calls, no report")
    t.check(all("-report" not in item.get("arguments", "") for item in planned), "no report command")
    log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    t.check(re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
            == [("1", "2", "0")], "converter exact 1/2/0")
    forms = re.findall(r"^Form:\s*(.+)$", log, re.M)
    errors = re.findall(r"^rec\s+(\d+):\s+\(error #(\d+)\)\s+(.+)$", log, re.M)
    warnings = re.findall(r"^rec\s+(\d+):\s+\(warning #(\d+)\)\s+(.+)$", log, re.M)
    t.check(forms == ["Control", "MissionPreparation", "System"], "converter form order")
    t.check(errors == [("1", "165", "Invalid subtask breakdown of mission preparation task: PREP-FIXED")], "sole targeted error #165")
    t.check([(record, code) for record, code, _ in warnings] == [("1", "108"), ("1", "126")], "sole classified warnings")
    t.check((RUN / "model.sxo").stat().st_size == 4
            and sha(RUN / "model.sxo") == "2a2d5e177502c5a794270deadd8dd755859f202a96d9d27568826ab0b69f984b",
            "invalid four-byte SXO")
    t.check(not (RUN / "model.log").exists() and not (RUN / "report-raw.json").exists(), "no model log or report")
    for path in sorted(RUN.glob("*.log")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        t.check(not re.search(r"(?im)^\s*Time:\s*\d|\b(?:mission|subtask|task)\s+(?:starts|completed)\b", text),
                f"no physical events in {path.name}")
    result = {
        "schema": "simlox-b02-var04-independent-replay/v1",
        "decision": "GO_BOUNDED" if not t.failures else "NO_GO",
        "checks": t.checks,
        "failures": t.failures,
        "run_id": RUN_ID,
        "closure_sha256": CHILD_CLOSURE_SHA,
        "source_changed_cells": 1,
        "authored_row_containing_tables": len(authored),
        "converter": {"errors": 1, "warnings": [108, 126], "notes": 0,
                      "target_form": "MissionPreparation", "target_record": 1, "target_code": 165},
        "scope": "one converter-negative <REPAIR> mission-preparation child; no physical simulation",
        "limits": ["single fixed input and installed SIMLOX 2017 CLI", "no GUI validation or general predefined-subtask rule"],
    }
    return result


if __name__ == "__main__":
    output = HERE / "independent-verdict.json"
    try:
        verdict = replay()
    except Exception as exc:
        verdict = {"schema": "simlox-b02-var04-independent-replay/v1", "decision": "NO_GO",
                   "checks": 0, "failures": [f"exception: {type(exc).__name__}: {exc}"], "run_id": RUN_ID}
    output.write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    raise SystemExit(0 if verdict["decision"] == "GO_BOUNDED" else 1)

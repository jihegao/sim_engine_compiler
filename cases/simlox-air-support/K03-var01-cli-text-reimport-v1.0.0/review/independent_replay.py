"""Independent read-only replay of one native delimited-text reimport."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CASES = HERE.parent
RUN = HERE / "runs/k03-var01-reimport-v100-ssh-20261004-01"
EXPORT = CASES / "K03-var01-cli-text-export-v1.0.1"
EXPORT_RUN = EXPORT / "runs/k03-var01-text-v101-ssh-20261004-01"
K02 = CASES / "K02-var01-json-structure-v1.0.1"
K02_RUN = K02 / "runs/k02-var01-named-v101-ssh-20261004-01"
OLD_EXPORT = CASES / "K03-var01-cli-text-export-v1.0.0/runs/k03-var01-text-v100-ssh-20261004-01"
K04_DIAGNOSTIC = CASES / "K04-var01-one-level-include-v1.0.0/runs/k04-var01-include-v100-ssh-20261004-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        out = []
        quoted = escaped = False
        for i, char in enumerate(raw):
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
                j = i + 1
                while j < len(raw) and raw[j].isspace():
                    j += 1
                if j == len(raw) or raw[j] not in "]}":
                    out.append(char)
            else:
                out.append(char)
        return json.loads("".join(out))


checks = 0
failures = []


def check(condition, label):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def source_paths():
    return {
        "contract": HERE / "contract.json",
        "parent_text": EXPORT_RUN / "model.txt",
        "parent_json": EXPORT_RUN / "model-raw.json",
        "parent_closure": EXPORT_RUN / "closure.json",
        "parent_signoff": EXPORT / "cli-scope-signoff-2026-10-04.md",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "run_native_ssh.ps1": HERE / "run_native_ssh.ps1",
    }


def main():
    contract = load(HERE / "contract.json")
    closure = load(RUN / "closure.json")
    invocation = load(RUN / "invocation.json")
    check(contract["case_id"] == "K03" and contract["variant_id"] == "K03.var01", "contract identity")
    check(closure["run_id"] == invocation["run_id"] == contract["run_id"] == RUN.name, "run identity")
    for key, path in sorted(source_paths().items()):
        check(path.is_file() and sha(path) == closure["source_hashes_before"][key], key + " source SHA")
    for key, path in {"text": EXPORT_RUN / "model.txt", "json": EXPORT_RUN / "model-raw.json", "closure": EXPORT_RUN / "closure.json", "signoff": EXPORT / "cli-scope-signoff-2026-10-04.md"}.items():
        check(sha(path) == contract["accepted_parent"][key + "_sha256"], key + " contract parent pin")
    check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source hashes stable")
    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    check(closure["error"] is None, "closure success")
    check(len(closure["raw"]) == 11, "11 sealed raw files")
    for name, seal in sorted(closure["raw"].items()):
        path = RUN / name
        check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], name + " raw seal")
    check(sha(RUN / "input.txt") == sha(EXPORT_RUN / "model.txt"), "exact accepted text input bytes")
    check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0, "SSH session0")
    check("sshd.exe" in invocation["ssh_ancestor_names"], "sshd ancestor")
    check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0, "protected GUI identity")
    commands = invocation["planned_commands"]
    check([command["name"] for command in commands] == ["timport", "jexport", "calc", "jsonreport"], "four CLI commands")
    check("-timport" in commands[0]["arguments"] and "-twidth 4096" in commands[0]["arguments"] and "-tsep !" in commands[0]["arguments"], "matching reimport delimiter and width")
    steps = load(RUN / "steps.json")
    check([step["name"] for step in steps] == ["timport", "jexport", "calc", "jsonreport"], "four recorded steps")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], step["name"] + " exit/GUI")
    check((RUN / "text-import.log").stat().st_size == 0, "optional import log empty")
    check((RUN / "model.sxi").stat().st_size > 4 and (RUN / "model.sxo").stat().st_size > 4, "usable SXI/SXO")
    log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log, "converter totals")
    check(re.findall(r"\(warning #(\d+)\)", log) == ["108", "126"], "converter warnings")
    check(not re.search(r"\((?:error|notice) #", log), "no converter errors/notices")

    previous = load(EXPORT_RUN / "model-raw.json")["model"]["tables"]
    current = load(RUN / "roundtrip-raw.json")["model"]["tables"]
    check(len(previous) == len(current) == 31, "31 tables")
    check([table["name"] for table in previous] == [table["name"] for table in current], "table order/name parity")
    changes = []
    n_instances = n_cells = 0
    for old, new in zip(previous, current):
        name = old["name"]
        check(old["columns"] == new["columns"], name + " columns and declared types")
        check(len(old["instances"]) == len(new["instances"]), name + " instance count")
        n_instances += len(old["instances"])
        for i, (old_instance, new_instance) in enumerate(zip(old["instances"], new["instances"])):
            check(old_instance["instance_name"] == new_instance["instance_name"], name + f" instance {i} name")
            check(len(old_instance["rows"]) == len(new_instance["rows"]), name + f" instance {i} row count")
            for row_no, (old_row, new_row) in enumerate(zip(old_instance["rows"], new_instance["rows"])):
                check(len(old_row) == len(new_row) == len(old["columns"]), name + f" instance {i} row {row_no} width")
                for col_no, (left, right) in enumerate(zip(old_row, new_row)):
                    n_cells += 1
                    column = old["columns"][col_no]["name"]
                    if left != right:
                        changes.append({"table": name, "instance": old_instance["instance_name"], "row": row_no, "column": column, "before": left, "after": right})
                    check(left == right or (name == "OperationProfile" and old_instance["instance_name"] == "" and row_no == 0 and column == "DTIM" and left == 0.3333333333333333 and right == 0.3), name + f" instance {i} row {row_no} {column} allowed value")
    check(n_instances == 33 and n_cells == 381, "33 instances/381 exported cells")
    expected_change = [{"table": "OperationProfile", "instance": "", "row": 0, "column": "DTIM", "before": 0.3333333333333333, "after": 0.3}]
    check(changes == expected_change, "exactly one DTIM precision loss")
    authored = load(K02 / "named-input.json")["model"]["tables"]
    authored_map = {table["name"]: table for table in authored}
    current_map = {table["name"]: table for table in current}
    check(len(authored_map) == 31, "K02 authored source 31 tables")
    check(sum(any(instance["rows"] for instance in table["instances"]) for table in authored) == 13, "K02 authored 13 row-containing tables")
    for name, table in sorted(authored_map.items()):
        check(table["columns"] == current_map[name]["columns"], name + " authored column preservation")
        if any(instance["rows"] for instance in table["instances"]):
            for source_instance in table["instances"]:
                match = [instance for instance in current_map[name]["instances"] if instance["instance_name"] == source_instance["instance_name"]]
                check(len(match) == 1, name + " authored instance retained")
                if match:
                    if name == "OperationProfile":
                        col = [c["name"] for c in table["columns"]].index("DTIM")
                        changed = [row[:] for row in source_instance["rows"]]
                        changed[0][col] = 0.3
                        check(match[0]["rows"] == changed, "authored OperationProfile with sole DTIM loss")
                    else:
                        check(match[0]["rows"] == source_instance["rows"], name + " authored rows")
    stations = current_map["Station"]["instances"]
    check([instance["instance_name"] for instance in stations] == ["", "K02-BASE", "K02-AUX"], "default plus two named Station instances")
    check(stations[0]["rows"] == [[None] * 21], "sole empty native Station default")

    check(sha(RUN / "model.log") == sha(K02_RUN / "model.log"), "byte-identical accepted K02 event log")
    events = (RUN / "model.log").read_text(encoding="utf-8-sig")
    for marker in ("Time: 7 <TEACH-UNIT> mission ordered", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 3", "Time: 11 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success", "Time: 11 <TEACH-AIR-01,BASE-01,0> System ready"):
        check(marker in events, marker)
    check(sha(RUN / "report-raw.json") == sha(K02_RUN / "report-raw.json"), "byte-identical K02 native report")
    report = {table["name"]: table for table in load(RUN / "report-raw.json")["report"]["tables"]}
    check([table["name"] for table in load(RUN / "report-raw.json")["report"]["tables"]] == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"], "report table set")
    check(report["ResultSummary"]["instances"][0]["rows"][0][0] == 1, "one replication")
    for name in ("SystemResults", "StockTotalResults"):
        rows = report[name]["instances"][0]["rows"]
        check(len(rows) == 72, name + " 72 bins")
        offset = 2 if name == "SystemResults" else 0
        for index, row in enumerate(rows):
            check(row[offset] == index * 0.5 and row[offset + 1] == (index + 1) * 0.5, name + f" interval {index}")
    system = report["SystemResults"]
    columns = [col["name"] for col in system["columns"]]
    rows = system["instances"][0]["rows"]
    check(rows[-1][columns.index("NSYRY")] == rows[-1][columns.index("NSYA")] == 1, "terminal one ready aircraft")
    check(sum(row[columns.index("NSYMO")] for row in rows) * 0.5 == 3, "three aircraft flight hours")
    check(sha(OLD_EXPORT / "closure.json") == "a36ff4174fc64341cdbbbbf7930fe32a37792905b25b1c05dc729aa783af29a9", "excluded K03 export-runner diagnostic pin")
    check(sha(K04_DIAGNOSTIC / "closure.json") == "660911c81d9d33d0d18230f4ce8bcdf35c09c0ad557620412b795b4d32a89f6f", "distinct K04 include diagnostic pin")

    verdict = {
        "schema": "independent-k03-var01-text-reimport/v1",
        "passed": not failures,
        "verdict": "GO: bounded native text reimport with one numeric precision loss" if not failures else "NO-GO: reviewer discrepancies",
        "checks_passed": checks - len(failures),
        "checks_total": checks,
        "failures": failures,
        "closure_sha256": sha(RUN / "closure.json"),
        "reimport_export_sha256": sha(RUN / "roundtrip-raw.json"),
        "input_text_sha256": sha(RUN / "input.txt"),
        "native_report_sha256": sha(RUN / "report-raw.json"),
        "observed_cell_changes": changes,
        "limits": ["This is one `!` delimiter, 4096 width, one fixed model and installed SIMLOX 2017 CLI.", "OperationProfile.DTIM was rounded from 0.3333333333333333 to 0.3; the native calculation happened to preserve this fixed mission's log/report, not numeric input fidelity.", "Other text widths, delimiters, precision cases, clipboard, Excel XML, and GUI pathways remain unverified.", "The excluded K03 v1.0.0 export runner stopped on an optional empty log; the separate K04 failure involved an auxiliary default Control table, not this import."],
    }
    target = HERE / "review/independent-verdict.json"
    target.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict["verdict"], "checks": [verdict["checks_passed"], checks], "failures": failures}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

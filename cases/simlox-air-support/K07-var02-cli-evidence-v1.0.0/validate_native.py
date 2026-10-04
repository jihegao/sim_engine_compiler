"""Author's read-only replay of the sealed K07 CLI workflow."""
import hashlib
import json
import re
from pathlib import Path

case = Path(__file__).resolve().parent
run = case / "runs/k07-var02-cli-evidence-v100-ssh-20261004-01"
parent = case.parent / "K02-var01-json-structure-v1.0.1"
parent_run = parent / "runs/k02-var01-named-v101-ssh-20261004-01"
checks = 0
failures = []


def check(ok, label):
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_native_json(path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # This SIMLOX report exporter emits trailing commas. Parse a copy only.
        out = []
        quoted = escape = False
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
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


contract = load(case / "contract.json")
closure = load(run / "closure.json")
invocation = load(run / "invocation.json")
outcome = load(run / "outcome.json")
steps = load(run / "steps.json")
check(contract["case_id"] == "K07" and contract["variant_ids"] == ["K07.var02", "K07.var03", "K07.var05"], "contract identity")
check(contract["run_id"] == closure["run_id"] == invocation["run_id"] == run.name, "run identity")
check(sha(parent / "named-input.json") == contract["dependency"]["input_sha256"], "parent input pin")
check(sha(parent_run / "model.sxi") == contract["dependency"]["native_sxi_sha256"], "parent native SXI pin")
check(sha(parent_run / "closure.json") == contract["dependency"]["closure_sha256"], "parent closure pin")
check(sha(parent / "cli-scope-signoff-2026-10-04.md") == contract["dependency"]["signoff_sha256"], "parent signoff pin")
check(sha(case / "normal-input.json") == contract["inputs_sha256"]["normal"] == sha(parent / "named-input.json"), "normal source pin")
check(sha(case / "inactive-base-input.json") == contract["inputs_sha256"]["inactive_base"], "negative source pin")
normal_source = load(case / "normal-input.json")
negative_source = load(case / "inactive-base-input.json")
expected_negative = json.loads(json.dumps(normal_source))
station = next(t for t in expected_negative["model"]["tables"] if t["name"] == "Station")
station["instances"][0]["inactive_rows"] = [1]
check(negative_source == expected_negative, "negative source sole inactive-row delta")
check(sha(run / "normal-input.json") == sha(case / "normal-input.json"), "normal run source copy")
check(sha(run / "inactive-base-input.json") == sha(case / "inactive-base-input.json"), "negative run source copy")
check(closure["error"] is None and outcome["error"] is None, "sealed successful workflow")
check(closure["invocation_sha256"] == sha(run / "invocation.json"), "invocation seal")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source hashes stable")
source_paths = {
    "contract": case / "contract.json",
    "normal": case / "normal-input.json",
    "inactive_base": case / "inactive-base-input.json",
    "parent_input": parent / "named-input.json",
    "parent_sxi": parent_run / "model.sxi",
    "parent_closure": parent_run / "closure.json",
    "parent_signoff": parent / "cli-scope-signoff-2026-10-04.md",
    "parent_log": parent_run / "model.log",
    "parent_report": parent_run / "report-raw.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "build.py": case / "build.py",
    "run_native_ssh.ps1": case / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check(set(source_paths) == set(closure["source_hashes_before"]), "source-hash key set")
for key, path in sorted(source_paths.items()):
    check(path.is_file() and sha(path) == closure["source_hashes_before"][key], f"source seal {key}")
check(len(closure["raw"]) == 23, "23 raw files")
for name, seal in sorted(closure["raw"].items()):
    path = run / name
    check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw seal {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-0 SSH ancestry")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "GUI identity")
expected_steps = ["normal_import", "normal_export", "normal_calc", "normal_report", "copy_convert", "copy_export", "inactive_base_import", "inactive_base_export", "inactive_base_calc"]
check([s["name"] for s in steps] == expected_steps, "nine ordered steps")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"step {step['name']}")
check(outcome["normal"] == "completed" and outcome["copy_convert"] == "completed" and outcome["inactive_base"] == "completed_rejection", "three outcomes")
normal_export = load_native_json(run / "normal-roundtrip-raw.json")
converted_export = load_native_json(run / "convert-roundtrip-raw.json")
parent_export = load_native_json(parent_run / "roundtrip-raw.json")
check(normal_export == parent_export, "fresh positive full JSON roundtrip equals accepted K02")
check(converted_export == normal_export, "converted-copy full JSON roundtrip equals positive")
check(sha(run / "normal.sxi") == sha(run / "convert-copy.sxi") == sha(parent_run / "model.sxi"), "same-version convert copy and original SXI bytes equal parent")
check((run / "normal.sxo").stat().st_size > 4, "positive usable SXO")
normal_run_log = (run / "normal-run.log").read_text(encoding="utf-8-sig")
check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in normal_run_log, "normal converter summary")
check(re.findall(r"\(warning #(\d+)\)", normal_run_log) == ["108", "126"], "normal warning codes")
check(not re.findall(r"\((?:error|notice) #", normal_run_log), "normal no error/notice")
check(sha(run / "normal.log") == sha(parent_run / "model.log"), "normal event log byte parity")
check(sha(run / "normal-report-raw.json") == sha(parent_run / "report-raw.json"), "normal report byte parity")
log = (run / "normal.log").read_text(encoding="utf-8-sig")
for event in ("Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting", "Time: 11 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success", "Time: 11 <TEACH-UNIT at <BASE-01,0>> systems ready: 1"):
    check(event in log, "normal event " + event[:32])
report = load_native_json(run / "normal-report-raw.json")["report"]["tables"]
report_by_name = {t["name"]: t for t in report}
check(len(report_by_name) == len(report), "report table names unique")
for name in ("SystemResults", "StockTotalResults"):
    check(sum(len(i["rows"]) for i in report_by_name[name]["instances"]) == 72, f"{name} 72 half-hour bins")
negative_export = load_native_json(run / "inactive-base-roundtrip-raw.json")
negative_station = next(t for t in negative_export["model"]["tables"] if t["name"] == "Station")
check(negative_station["instances"][1]["rows"][0] == [None] * 21, "inactive BASE-01 exported as null row")
check(negative_station["instances"][2]["rows"][0][0] == "K02-NAMED", "auxiliary Station retained")
negative_run_log = (run / "inactive-base-run.log").read_text(encoding="utf-8-sig")
check(outcome["negative_converter_summary"] == [4, 2, 1], "negative summary recorded")
check("Input conversion completed. Errors: 4, Warnings: 2, Notes: 1" in negative_run_log, "negative native summary")
check(re.findall(r"\(error #(\d+)\)", negative_run_log) == ["2024", "492", "114", "492"], "negative exact error codes")
check(re.findall(r"\(warning #(\d+)\)", negative_run_log) == ["108", "126"], "negative warning codes")
check(re.findall(r"\(notice #(\d+)\)", negative_run_log) == ["115"], "negative notice code")
check(outcome["negative_sxo_bytes"] == (run / "inactive-base.sxo").stat().st_size == 4, "negative four-byte SXO")
check(not (run / "inactive-base.log").exists() and not (run / "inactive-base-report-raw.json").exists(), "negative no event/report")

verdict = {
    "schema": "simlox-k07-author-readonly-validation/v1",
    "case": "K07 var02/03/05 v1.0.0",
    "run_id": run.name,
    "closure_sha256": sha(run / "closure.json"),
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "passed": not failures,
    "failures": failures,
    "outcome": "GO: one normal source-bound CLI lifecycle and copied same-version conversion; diagnostic-only invalid inactive BASE-01 yields four converter errors and a four-byte SXO" if not failures else "NO-GO",
    "limits": ["No GUI Test, old-version migration, threading equivalence, generic error-classification or full K07 claim."],
}
path = case / "author-native-validation-2026-10-04.json"
path.write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'}: {verdict['checks_passed']}/{checks}")
if failures:
    print("\n".join(failures))
    raise SystemExit(1)

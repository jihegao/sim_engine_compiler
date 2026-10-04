"""Independent read-only replay of the sealed K06.var01 direct-OPI CLI run."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CASES = HERE.parent
DONOR = CASES / "K02-var01-json-structure-v1.0.1"
DONOR_RUN = DONOR / "runs/k02-var01-named-v101-ssh-20261004-01"
RUN = HERE / "runs/k06-var01-opi-open-v100-ssh-20261005-01"
VERDICT = Path(__file__).with_name("independent-verdict.json")
checks = 0
failures = []


def check(condition, label):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


contract = read(HERE / "contract.json")
closure = read(RUN / "closure.json")
invocation = read(RUN / "invocation.json")
outcome = read(RUN / "outcome.json")
steps = read(RUN / "steps.json")
donor_closure = read(DONOR_RUN / "closure.json")
dep = contract["dependency"]
expected = {
    "contract": HERE / "contract.json",
    "parent_input": DONOR / "named-input.json",
    "parent_signoff": DONOR / "cli-scope-signoff-2026-10-04.md",
    "parent_closure": DONOR_RUN / "closure.json",
    "parent_sxi": DONOR_RUN / "model.sxi",
    "parent_event": DONOR_RUN / "model.log",
    "parent_report": DONOR_RUN / "report-raw.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": HERE / "run_native_ssh.ps1",
}
check(contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name, "run IDs")
check(closure["error"] is None and closure["publication_state"] == "not_published", "closure state")
check(closure["invocation_sha256"] == digest(RUN / "invocation.json"), "invocation seal")
check(invocation["source_hashes_before"] == closure["source_hashes_before"], "invocation source map")
check(closure["source_hashes_before"] == closure["source_hashes_after"], "source immutability")
for name, path in expected.items():
    check(path.exists(), f"source exists: {name}")
    if path.exists():
        check(digest(path) == closure["source_hashes_before"].get(name), f"source seal: {name}")
check(dep["input_sha256"] == digest(expected["parent_input"]), "contract donor input")
check(dep["signoff_sha256"] == digest(expected["parent_signoff"]), "contract donor signoff")
check(dep["closure_sha256"] == digest(expected["parent_closure"]), "contract donor closure")
check(dep["native_sxi_sha256"] == digest(expected["parent_sxi"]), "contract donor SXI")
check(dep["event_log_sha256"] == digest(expected["parent_event"]), "contract donor event")
check(dep["report_sha256"] == digest(expected["parent_report"]), "contract donor report")
check(contract["manual"]["sha256"] == digest(expected["manual"]), "contract manual")
check(donor_closure["error"] is None, "accepted donor closure")
for raw_name, key in [("model.sxi", "native_sxi_sha256"), ("model.log", "event_log_sha256"), ("report-raw.json", "report_sha256")]:
    check(donor_closure["raw"][raw_name]["sha256"] == dep[key], f"donor raw closure {raw_name}")
check(len(closure["raw"]) == 10, "ten raw seals")
for raw_name, record in closure["raw"].items():
    path = RUN / raw_name
    check(path.exists(), f"raw exists: {raw_name}")
    if path.exists():
        check(path.stat().st_size == record["bytes"], f"raw bytes: {raw_name}")
        check(digest(path) == record["sha256"], f"raw SHA: {raw_name}")
check((RUN / "model.opi").read_bytes() == expected["parent_sxi"].read_bytes(), "OPI exact donor SXI copy")
check((RUN / "model.opi").stat().st_size == dep["native_sxi_bytes"], "OPI donor byte count")
check(invocation["copied_opi_sha256"] == dep["native_sxi_sha256"], "invocation OPI seal")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH session zero")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI identity")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
check([s["name"] for s in steps] == ["opi_json_export", "opi_calc", "opi_report"], "three steps and order")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True and step["error"] is None, f"guarded step {step['name']}")
    check(str(RUN / "model.opi").lower() in step["arguments"].lower() if step["name"] != "opi_report" else str(RUN / "model.sxo").lower() in step["arguments"].lower(), f"step input {step['name']}")
check(outcome["steps"] == "completed" and outcome["error"] is None, "outcome completed")
check(outcome["converter_summary"] == [0, 2, 0] and outcome["warning_codes"] == ["108", "126"], "outcome converter")
run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")
check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in run_log, "converter exact summary")
check(re.findall(r"\(warning #(\d+)\)", run_log) == ["108", "126"], "converter exact warnings")
check((RUN / "model.sxo").stat().st_size > 100000, "nonempty native result")
export = read(RUN / "roundtrip-raw.json")
donor_export = read(DONOR_RUN / "roundtrip-raw.json")
source = read(DONOR / "named-input.json")
check(export == donor_export, "export exact donor JSON object")
tables = {t["name"]: t for t in export["model"]["tables"]}
source_tables = {t["name"]: t for t in source["model"]["tables"]}
check(len(tables) == len(source_tables) == 31 and tables.keys() == source_tables.keys(), "31 authored tables")
for name, authored in source_tables.items():
    actual = tables[name]
    check(actual["columns"] == authored["columns"], f"table columns {name}")
    source_instances = [(i["instance_name"], r) for i in authored["instances"] for r in i["rows"] if any(v is not None for v in r)]
    actual_instances = [(i["instance_name"], r) for i in actual["instances"] for r in i["rows"] if any(v is not None for v in r)]
    check(actual_instances == source_instances, f"populated instance rows {name}")
station_instances = tables["Station"]["instances"]
check([i["instance_name"] for i in station_instances] == ["", "K02-BASE", "K02-AUX"], "Station default/name ordering")
check(len(station_instances[0]["rows"]) == 1 and all(v is None for v in station_instances[0]["rows"][0]), "Station empty default canonicalization")
check((RUN / "model.log").read_bytes() == expected["parent_event"].read_bytes(), "event log donor byte parity")
check((RUN / "report-raw.json").read_bytes() == expected["parent_report"].read_bytes(), "report donor byte parity")
event = (RUN / "model.log").read_text(encoding="utf-8-sig")
check(len(re.findall(r"Time: 8 .*mission starting, duration: 3", event)) == 1, "single h8 mission launch")
check(len(re.findall(r"Time: 11 .*mission success:", event)) == 1, "single h11 mission success")
check("Time: 11 <TEACH-AIR-01,BASE-01,0> System ready" in event, "h11 system ready")
check("OPUS10-generated" in contract["limits"][0] and "merge" in contract["gate"] and "OPO" in contract["gate"] and "phase" in contract["gate"], "scope exclusions")

result = {
    "schema": "simlox-k06-opi-direct-open-independent-verdict/v1",
    "run_id": RUN.name,
    "verdict": "GO_BOUNDED" if not failures else "NO_GO",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "observations": {
        "opi_exact_donor_sxi": (RUN / "model.opi").read_bytes() == expected["parent_sxi"].read_bytes(),
        "export_exact_donor_object": export == donor_export,
        "event_log_byte_identical": (RUN / "model.log").read_bytes() == expected["parent_event"].read_bytes(),
        "report_byte_identical": (RUN / "report-raw.json").read_bytes() == expected["parent_report"].read_bytes(),
        "station_default_canonicalized": [i["instance_name"] for i in station_instances] == ["", "K02-BASE", "K02-AUX"],
        "native_result_sha256": digest(RUN / "model.sxo"),
    },
    "limits": ["Copied accepted self-built SXI bytes under an .opi extension only; no OPUS10-generated input.", "No OPI/SXI merge, OPO, phase-scenario, or GUI workflow tested.", "Native report is byte identical to donor; its legacy JSON contains invalid trailing-comma syntax, so report equivalence is a byte comparison rather than a strict JSON parse."],
}
VERDICT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"verdict": result["verdict"], "checks": f"{result['checks_passed']}/{checks}", "failures": failures, "script_sha256": digest(Path(__file__)), "verdict_sha256": digest(VERDICT)}, indent=2))

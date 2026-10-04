"""Independent, read-only K06 merge replay. Never launches SIMLOX."""
import copy
import hashlib
import json
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
CASES = PACKAGE.parent
RUN = PACKAGE / "runs/k06-var01-opi-sxi-merge-v020-ssh-20261005-01"
PRIOR = CASES / "K06-var01-opi-sxi-merge-v0.1.0/runs/k06-var01-opi-sxi-merge-v010-ssh-20261005-01"
K01 = CASES / "K01-var04-parent-child-model-diff-v1.0.0"
K01_RUN = K01 / "runs/k01-var04-duration-v100-ssh-20261004-01"
K02 = CASES / "K02-var01-json-structure-v1.0.1"
K02_RUN = K02 / "runs/k02-var01-named-v101-ssh-20261004-01"
VERDICT_PATH = Path(__file__).with_name("independent-verdict.json")
checks = 0
failures = []


def check(value, name):
    global checks
    checks += 1
    if not value:
        failures.append(name)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seal_raw(directory, closure, label):
    for name, record in sorted(closure["raw"].items()):
        path = directory / name
        check(path.is_file(), f"{label} raw exists: {name}")
        if path.is_file():
            check(path.stat().st_size == record["bytes"], f"{label} raw size: {name}")
            check(sha(path) == record["sha256"], f"{label} raw SHA: {name}")


contract = load(PACKAGE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
prior_closure = load(PRIOR / "closure.json")
prior_outcome = load(PRIOR / "outcome.json")
source_closure = load(K02_RUN / "closure.json")
target_closure = load(K01_RUN / "closure.json")
source_paths = {
    "contract": PACKAGE / "contract.json",
    "builder": PACKAGE / "build.py",
    "derived_input": PACKAGE / "source-input.json",
    "prior_closure": PRIOR / "closure.json",
    "source_input": K02 / "named-input.json",
    "source_signoff": K02 / "cli-scope-signoff-2026-10-04.md",
    "source_closure": K02_RUN / "closure.json",
    "source_sxi": K02_RUN / "model.sxi",
    "target_closure": K01_RUN / "closure.json",
    "target_sxi": K01_RUN / "model.sxi",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": PACKAGE / "run_native_ssh.ps1",
}
check(contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name, "run IDs")
check(closure["error"] is None and closure["publication_state"] == "not_published", "closure state")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
check(invocation["source_hashes_before"] == closure["source_hashes_before"], "invocation source map")
check(closure["source_hashes_before"] == closure["source_hashes_after"], "source immutability")
check(set(closure["source_hashes_before"]) == set(source_paths), "complete source map")
for name, path in source_paths.items():
    check(path.is_file(), f"source exists: {name}")
    if path.is_file():
        check(sha(path) == closure["source_hashes_before"].get(name), f"source SHA: {name}")
check(contract["derived_source"]["json_sha256"] == sha(PACKAGE / "source-input.json"), "contract derived JSON")
check(contract["prior_diagnostic"]["closure_sha256"] == sha(PRIOR / "closure.json"), "contract prior closure")
for key, path in [("native_sxi_sha256", K01_RUN / "model.sxi"), ("closure_sha256", K01_RUN / "closure.json")]:
    check(contract["target"][key] == sha(path), f"target contract {key}")
for key, path in [("native_sxi_sha256", K02_RUN / "model.sxi"), ("closure_sha256", K02_RUN / "closure.json"), ("input_sha256", K02 / "named-input.json"), ("signoff_sha256", K02 / "cli-scope-signoff-2026-10-04.md")]:
    check(contract["source"][key] == sha(path), f"source contract {key}")
check(source_closure["error"] is None and target_closure["error"] is None, "accepted parent closures")
check(source_closure["raw"]["model.sxi"]["sha256"] == contract["source"]["native_sxi_sha256"], "source closure SXI")
check(target_closure["raw"]["model.sxi"]["sha256"] == contract["target"]["native_sxi_sha256"], "target closure SXI")
check(contract["manual"]["sha256"] == sha(source_paths["manual"]), "manual pin")

check(prior_closure["run_id"] == contract["prior_diagnostic"]["run_id"], "prior run ID")
check(len(prior_closure["raw"]) == 11, "prior eleven raw files")
seal_raw(PRIOR, prior_closure, "prior")
check(prior_closure["source_hashes_before"] == prior_closure["source_hashes_after"], "prior source immutability")
prior_export = load(PRIOR / "roundtrip-raw.json")
prior_station = next(t for t in prior_export["model"]["tables"] if t["name"] == "Station")
prior_keys = [row[0] for instance in prior_station["instances"] for row in instance["rows"] if row[0] is not None]
check(prior_keys.count("BASE-01") == 2, "prior duplicate BASE-01")
check(prior_outcome["error"] == "merged.sxo missing or too small", "prior rejected result")
prior_log = (PRIOR / "run.log").read_text(encoding="utf-8-sig")
check(re.search(r"\(error #2013\) Double definition of data for: BASE-01", prior_log) is not None, "prior exact #2013")
check("Input conversion completed. Errors: 1, Warnings: 2, Notes: 0" in prior_log, "prior converter summary")
check((PRIOR / "merged.sxo").stat().st_size == 4, "prior four-byte SXO")

donor_json = load(K02 / "named-input.json")
derived_json = load(PACKAGE / "source-input.json")
expected_json = copy.deepcopy(donor_json)
station = next(t for t in expected_json["model"]["tables"] if t["name"] == "Station")
removed = [instance for instance in station["instances"] if instance["instance_name"] == "K02-BASE"]
check(len(removed) == 1 and removed[0]["rows"][0][0] == "BASE-01", "removed named Station instance")
station["instances"] = [instance for instance in station["instances"] if instance["instance_name"] != "K02-BASE"]
check(derived_json == expected_json, "exact donor JSON minus K02-BASE instance")
check((RUN / "source-input.json").read_bytes() == (PACKAGE / "source-input.json").read_bytes(), "copied derived JSON bytes")
check((RUN / "source.sxi").read_bytes() == (RUN / "source.opi").read_bytes(), "source SXI/OPI exact bytes")
check((RUN / "target.sxi").read_bytes() == (K01_RUN / "model.sxi").read_bytes(), "target SXI exact bytes")
check(invocation["copied_source_input_sha256"] == sha(RUN / "source-input.json"), "invocation copied source JSON")
check(invocation["copied_target_sha256"] == sha(RUN / "target.sxi"), "invocation copied target")

check(len(closure["raw"]) == 17, "seventeen raw files")
seal_raw(RUN, closure, "current")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH session zero")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI identity")
check([s["name"] for s in steps] == ["derived_json_import", "opi_sxi_import", "merged_json_export", "merged_calc", "merged_report"], "five ordered steps")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True and step["error"] is None, f"guarded step: {step['name']}")
check(outcome["steps"] == "completed" and outcome["converter_summary"] == [0, 2, 0] and outcome["warning_codes"] == ["108", "126"] and outcome["error"] is None, "completed outcome")
source_import = (RUN / "source-import.log").read_text(encoding="utf-8-sig")
merge_import = (RUN / "import.log").read_text(encoding="utf-8-sig")
check("Import completed!" in source_import and "Number of forms inserted: 31" in source_import, "derived JSON imported")
check("Number of forms inserted: 32" in merge_import and "inserting form Station, K02-AUX" in merge_import, "OPI merge imported")
check((RUN / "merged.sxi").stat().st_size > 100000 and (RUN / "merged.sxo").stat().st_size > 100000, "nonempty merged native files")
run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")
check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in run_log, "converter zero errors")
check(re.findall(r"\(warning #(\d+)\)", run_log) == ["108", "126"], "converter warnings exact")
merged = load(RUN / "roundtrip-raw.json")
target_export = load(K01_RUN / "roundtrip-raw.json")
source_tables = {t["name"]: t for t in derived_json["model"]["tables"]}
merged_tables = {t["name"]: t for t in merged["model"]["tables"]}
target_tables = {t["name"]: t for t in target_export["model"]["tables"]}
check(len(merged_tables) == len(source_tables) == len(target_tables) == 31, "31 model tables")
check(merged_tables.keys() == source_tables.keys() == target_tables.keys(), "table names preserved")


def populated(table):
    return [(instance["instance_name"], tuple(row)) for instance in table["instances"] for row in instance["rows"] if any(value is not None for value in row)]


for name in source_tables:
    actual = populated(merged_tables[name])
    for origin, tables in [("source", source_tables), ("target", target_tables)]:
        for row in populated(tables[name]):
            check(row in actual, f"{origin} populated row retained: {name}")
    if name not in {"Station", "ProblemDescription"}:
        check(actual == populated(target_tables[name]) == populated(source_tables[name]), f"unchanged business rows: {name}")
station_instances = merged_tables["Station"]["instances"]
check([instance["instance_name"] for instance in station_instances] == ["", "K02-AUX"], "merged Station instances")
station_keys = [row[0] for instance in station_instances for row in instance["rows"] if row[0] is not None]
check(station_keys.count("BASE-01") == 1 and station_keys.count("K02-NAMED") == 1 and len(station_keys) == 2, "two unique Station keys")
descriptions = [row[0] for _, row in populated(merged_tables["ProblemDescription"])]
check(descriptions == ["K01.var04 v1.0.0 A01-derived three-hour model comparison", "K02.var01 v1.0.1 JSON named probe"], "both ProblemDescription rows ordered")

merged_log = (RUN / "merged.log").read_bytes()
check(merged_log == (K01_RUN / "model.log").read_bytes(), "event log byte parity K01")
check(merged_log == (K02_RUN / "model.log").read_bytes(), "event log byte parity K02")
check(len(re.findall(rb"Time: 8 .*mission starting, duration: 3", merged_log)) == 1, "one mission launch h8")
check(len(re.findall(rb"Time: 11 .*mission success:", merged_log)) == 1, "one mission success h11")
merged_report = (RUN / "report-raw.json").read_bytes()
k02_report = (K02_RUN / "report-raw.json").read_bytes()
report_lines = merged_report.splitlines(keepends=True)
extra_description = [line for line in report_lines if b"K01.var04 v1.0.0 A01-derived three-hour model comparison" in line]
check(len(extra_description) == 1, "one added K01 report description")
check(b"".join(line for line in report_lines if line not in extra_description) == k02_report, "report otherwise byte-identical to K02")
check(merged_report != k02_report and merged_report != (K01_RUN / "report-raw.json").read_bytes(), "full report differs by descriptions")
check("OPUS10-generated" in contract["limits"][0] and ".opo" in contract["gate"] and "phase" in contract["gate"], "bounded claim")

verdict = {
    "schema": "simlox-k06-opi-sxi-merge-independent-verdict/v1",
    "run_id": RUN.name,
    "verdict": "GO_BOUNDED" if not failures else "NO_GO",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "observations": {
        "prior_v010": "sealed diagnostic: duplicate BASE-01, converter error #2013, four-byte SXO",
        "current": "five guarded steps; 17 raw seals; Station BASE-01 and K02-NAMED once each; both descriptions; converter 0/2/0",
        "event_log": "byte-identical to accepted K01 and K02; one mission h8-h11",
        "report": "only added K01 ProblemDescription line relative to accepted K02 report",
    },
    "limits": ["One self-built derived JSON imported to SXI and copied as OPI for a CLI merge; no OPUS10-generated input.", "No OPO result point, phase-scenario, GUI, cross-engine, or general merge conclusion.", "Legacy native report is compared bytewise because its trailing-comma syntax is not strict JSON."],
}
VERDICT_PATH.write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"verdict": verdict["verdict"], "checks": f"{verdict['checks_passed']}/{checks}", "failures": failures, "script_sha256": sha(Path(__file__)), "verdict_sha256": sha(VERDICT_PATH)}, indent=2))

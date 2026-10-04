"""Read-only author replay of the bounded K06 .opi-to-.sxi merge."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/k06-var01-opi-sxi-merge-v020-ssh-20261005-01"
K01 = ROOT / "K01-var04-parent-child-model-diff-v1.0.0"
K01_RUN = K01 / "runs/k01-var04-duration-v100-ssh-20261004-01"
K02 = ROOT / "K02-var01-json-structure-v1.0.1"
K02_RUN = K02 / "runs/k02-var01-named-v101-ssh-20261004-01"
PRIOR = ROOT / "K06-var01-opi-sxi-merge-v0.1.0"
PRIOR_RUN = PRIOR / "runs/k06-var01-opi-sxi-merge-v010-ssh-20261005-01"
failed: list[str] = []
checks = 0


def check(condition: bool, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failed.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(document: dict, root: str) -> dict:
    return {table["name"]: table for table in document[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


contract = load(HERE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
steps = load(RUN / "steps.json")
outcome = load(RUN / "outcome.json")
check((contract["case_id"], contract["variant_id"], contract["version"]) == ("K06", "K06.var01", "0.2.0-candidate"), "contract identity")
check(contract["run_id"] == RUN.name == closure["run_id"] == invocation["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None and outcome["steps"] == "completed", "successful closure")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stability")

source_paths = {
    "contract": HERE / "contract.json",
    "builder": HERE / "build.py",
    "derived_input": HERE / "source-input.json",
    "prior_closure": PRIOR_RUN / "closure.json",
    "source_input": K02 / "named-input.json",
    "source_signoff": K02 / "cli-scope-signoff-2026-10-04.md",
    "source_closure": K02_RUN / "closure.json",
    "source_sxi": K02_RUN / "model.sxi",
    "target_closure": K01_RUN / "closure.json",
    "target_sxi": K01_RUN / "model.sxi",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": HERE / "run_native_ssh.ps1",
}
check(set(source_paths) == set(closure["source_hashes_before"]), "source inventory")
for name, path in source_paths.items():
    check(path.is_file() and sha(path) == closure["source_hashes_before"].get(name), f"source seal {name}")
check(sha(source_paths["derived_input"]) == contract["derived_source"]["json_sha256"], "derived JSON pin")
check(sha(source_paths["prior_closure"]) == contract["prior_diagnostic"]["closure_sha256"], "prior diagnostic pin")
check(sha(source_paths["source_closure"]) == contract["source"]["closure_sha256"], "K02 closure pin")
check(sha(source_paths["target_closure"]) == contract["target"]["closure_sha256"], "K01 closure pin")
check(sha(source_paths["source_sxi"]) == contract["source"]["native_sxi_sha256"], "K02 SXI pin")
check(sha(source_paths["target_sxi"]) == contract["target"]["native_sxi_sha256"], "K01 SXI pin")
check(len(closure["raw"]) == 17, "17 raw seals")
for name, seal in closure["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw seal {name}")

check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0 ancestry")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "native queue")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI")
check([step["name"] for step in steps] == ["derived_json_import", "opi_sxi_import", "merged_json_export", "merged_calc", "merged_report"], "five ordered steps")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"native step {step['name']}")
check(outcome["converter_summary"] == [0, 2, 0] and outcome["warning_codes"] == ["108", "126"], "reviewed converter diagnostics")
check((RUN / "source-input.json").read_bytes() == source_paths["derived_input"].read_bytes(), "copied source JSON")
check((RUN / "target.sxi").read_bytes() == source_paths["target_sxi"].read_bytes(), "unchanged target SXI")
check((RUN / "source.sxi").stat().st_size > 1000 and (RUN / "source.sxi").read_bytes() == (RUN / "source.opi").read_bytes(), "generated OPI copy")
check((RUN / "merged.sxi").stat().st_size > 1000 and (RUN / "merged.sxo").stat().st_size > 1000, "native merged input and output")
check("Import completed!" in (RUN / "source-import.log").read_text(encoding="utf-8-sig"), "source native import")
check("Number of forms inserted: 32" in (RUN / "import.log").read_text(encoding="utf-8-sig"), "OPI merge import")
check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in (RUN / "run.log").read_text(encoding="utf-8-sig"), "native calculation")

export = tables(load(RUN / "roundtrip-raw.json"), "model")
target = tables(load(K01_RUN / "roundtrip-raw.json"), "model")
source = tables(load(K02_RUN / "roundtrip-raw.json"), "model")
check(set(export) == set(target) == set(source), "model table inventory")
check({name for name in export if export[name] != target[name]} == {"ProblemDescription", "Station"}, "only expected tables differ from target")
check(all(export[name] == target[name] == source[name] for name in export if name not in {"ProblemDescription", "Station"}), "other authored tables unchanged")
station_instances = export["Station"]["instances"]
station_keys = [row[0] for row in rows(export["Station"]) if row and row[0] is not None]
check(station_keys.count("BASE-01") == 1 and station_keys.count("K02-NAMED") == 1, "unique base and named Station keys")
check(any(instance["instance_name"] == "K02-AUX" and any(row[0] == "K02-NAMED" for row in instance["rows"]) for instance in station_instances), "named Station instance")
descriptions = [row[0] for row in rows(export["ProblemDescription"])]
check(descriptions == [rows(target["ProblemDescription"])[0][0], rows(source["ProblemDescription"])[0][0]], "two traceable descriptions")
check((RUN / "merged.log").read_bytes() == (K01_RUN / "model.log").read_bytes(), "accepted event timeline exact parity")
event = (RUN / "merged.log").read_text(encoding="utf-8-sig")
check("Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in event and "Time: 11 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in event, "h8 launch and h11 success")

def report(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    check(len(re.findall(r",\s*]", raw)) == 1, f"one native report trailing comma {path.parent.name}")
    return tables(json.loads(re.sub(r",\s*]", "]", raw)), "report")


merged_report = report(RUN / "report-raw.json")
parent_report = report(K01_RUN / "report-raw.json")
check(set(merged_report) == set(parent_report), "report table inventory")
check({name for name in merged_report if merged_report[name] != parent_report[name]} == {"ProblemDescription"}, "only report description differs")
for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
    check(merged_report[name] == parent_report[name], f"{name} exact numeric parity")
for name in ("SystemResults", "StockTotalResults"):
    check(len(rows(merged_report[name])) == 72, f"{name} 72 half-hour bins")

verdict = {
    "schema": "simlox-k06-opi-sxi-merge-author-replay/v1",
    "run_id": RUN.name,
    "closure_sha256": sha(RUN / "closure.json"),
    "passed": not failed,
    "checks": checks,
    "checks_passed": checks - len(failed),
    "failures": failed,
    "observed": {
        "native_steps": len(steps),
        "raw_seals": len(closure["raw"]),
        "merged_station_keys": station_keys,
        "problem_description_rows": descriptions,
        "event_log_equal_K01": (RUN / "merged.log").read_bytes() == (K01_RUN / "model.log").read_bytes(),
    },
    "limits": "One derived self-built .opi donor and K01 target under CLI; no OPUS10-generated input, .opo result points, LORA, phase scenario, GUI or general K06 acceptance.",
}
destination = HERE / "review/author-validation-2026-10-05.json"
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'} {verdict['checks_passed']}/{checks}")
for failure in failed:
    print(failure)
raise SystemExit(0 if verdict["passed"] else 1)

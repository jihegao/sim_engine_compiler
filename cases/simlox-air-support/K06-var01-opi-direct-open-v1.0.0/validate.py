"""Read-only author replay for one common-format .opi direct-open run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/k06-var01-opi-open-v100-ssh-20261005-01"
PARENT = ROOT / "K02-var01-json-structure-v1.0.1"
PARENT_RUN = PARENT / "runs/k02-var01-named-v101-ssh-20261004-01"
FAIL: list[str] = []
CHECKS = 0


def check(ok: bool, name: str) -> None:
    global CHECKS
    CHECKS += 1
    if not ok:
        FAIL.append(name)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


contract = load(HERE / "contract.json")
closure = load(RUN / "closure.json")
parent_closure = load(PARENT_RUN / "closure.json")
invocation = load(RUN / "invocation.json")
steps = load(RUN / "steps.json")
outcome = load(RUN / "outcome.json")
check((contract["case_id"], contract["variant_id"], contract["version"]) == ("K06", "K06.var01", "1.0.0-candidate"), "contract identity")
check(contract["run_id"] == RUN.name == closure["run_id"] == invocation["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None and outcome["steps"] == "completed", "closure success")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stable")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
paths = {
    "contract": HERE / "contract.json",
    "parent_input": PARENT / "named-input.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-04.md",
    "parent_closure": PARENT_RUN / "closure.json",
    "parent_sxi": PARENT_RUN / "model.sxi",
    "parent_event": PARENT_RUN / "model.log",
    "parent_report": PARENT_RUN / "report-raw.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": HERE / "run_native_ssh.ps1",
}
check(set(paths) == set(closure["source_hashes_before"]), "source inventory")
for key, path in paths.items():
    check(path.is_file() and sha(path) == closure["source_hashes_before"][key], f"source seal {key}")
check(sha(paths["parent_input"]) == contract["dependency"]["input_sha256"], "parent input pin")
check(sha(paths["parent_signoff"]) == contract["dependency"]["signoff_sha256"], "parent signoff pin")
check(sha(paths["parent_closure"]) == contract["dependency"]["closure_sha256"], "parent closure pin")
check(parent_closure["error"] is None and parent_closure["raw"]["model.sxi"]["sha256"] == contract["dependency"]["native_sxi_sha256"], "parent SXI closure")
check(sha(paths["parent_event"]) == contract["dependency"]["event_log_sha256"], "parent event pin")
check(sha(paths["parent_report"]) == contract["dependency"]["report_sha256"], "parent report pin")
check(len(closure["raw"]) == 10, "10 raw seals")
for name, seal in closure["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-0 SSH")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI")
check([s["name"] for s in steps] == ["opi_json_export", "opi_calc", "opi_report"], "three serial steps")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"step {step['name']}")
check(outcome["converter_summary"] == [0, 2, 0] and outcome["warning_codes"] == ["108", "126"], "reviewed converter diagnostics")
check((RUN / "model.opi").stat().st_size == contract["dependency"]["native_sxi_bytes"] and (RUN / "model.opi").read_bytes() == paths["parent_sxi"].read_bytes(), "byte-identical SXI to OPI")
check((RUN / "model.sxo").stat().st_size > 1000, "nonempty SXO")
for candidate, parent, label in (
    (RUN / "roundtrip-raw.json", PARENT_RUN / "roundtrip-raw.json", "JSON export"),
    (RUN / "model.log", PARENT_RUN / "model.log", "event log"),
    (RUN / "report-raw.json", PARENT_RUN / "report-raw.json", "raw report"),
):
    check(candidate.read_bytes() == parent.read_bytes(), f"{label} exact parity")
export = load(RUN / "roundtrip-raw.json")
check(len(export["model"]["tables"]) > 10 and any(t["name"] == "Station" for t in export["model"]["tables"]), "native JSON export parsed")
raw_report = (RUN / "report-raw.json").read_text(encoding="utf-8-sig")
marker = ",\n      ]"
check(raw_report.count(marker) == 1, "one native trailing comma")
report = json.loads(raw_report.replace(marker, "\n      ]"))
tables = {t["name"]: t for t in report["report"]["tables"]}
check(all(name in tables for name in ("ResultSummary", "SystemResults", "StockTotalResults")), "report tables")
for name in ("SystemResults", "StockTotalResults"):
    rows = [r for inst in tables[name]["instances"] for r in inst["rows"]]
    check(len(rows) == 72, f"{name} 72 bins")
log = (RUN / "model.log").read_text(encoding="utf-8-sig")
check("Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log, "h8 launch")
check("Time: 11 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log, "h11 success")
verdict = {"schema": "simlox-k06-var01-author-replay/v1", "run_id": RUN.name,
           "closure_sha256": sha(RUN / "closure.json"), "passed": not FAIL,
           "checks": CHECKS, "checks_passed": CHECKS - len(FAIL), "failures": FAIL,
           "observed": {"opi_copied_from_sxi": True, "three_native_steps": True,
                        "json_export_equal_parent": True, "event_log_equal_parent": True,
                        "report_equal_parent": True},
           "limits": "Self-built copied OPI direct-open only; no OPUS10-generated content, OPI/SXI merge, OPO, LORA, phase scenario, GUI or general K06."}
dest = HERE / "review/author-validation-2026-10-05.json"
dest.parent.mkdir(exist_ok=True)
dest.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'} {verdict['checks_passed']}/{CHECKS}")
for failure in FAIL:
    print(failure)
raise SystemExit(0 if verdict["passed"] else 1)

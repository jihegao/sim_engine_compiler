"""Read-only independent replay of the excluded K09 v1.0.0 report-settings run."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "k09-var01-report-settings-v100-ssh-20261004-01"
PARENT = CASES / "J05-collection-window-v1.0.1"
PARENT_RUN = PARENT / "runs" / "j05-baseline-v101-20261001-01"
CHECKS: list[tuple[str, bool]] = []


def check(label: str, result: bool) -> None:
    CHECKS.append((label, bool(result)))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path: Path) -> dict:
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(doc: dict) -> dict[str, dict]:
    return {table["name"]: table for table in doc["report"]["tables"]}


def records(table: dict) -> list[dict]:
    fields = [column["name"] for column in table["columns"]]
    return [dict(zip(fields, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


contract = load(CASE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
steps = load(RUN / "steps.json")
outcome = load(RUN / "outcome.json")
check("run and parent IDs", contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name and invocation["parent_run_id"] == contract["parent"]["run_id"])
check("parent closure bound", closure["parent_closure_sha256"] == contract["parent"]["closure_sha256"])
check("invocation SHA bound", closure["invocation_sha256"] == digest(RUN / "invocation.json"))
check("clean diagnostic closure", closure["error"] is None and outcome == {"status": "completed", "error": None})
check("SSH session 0", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"])
check("global native mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("protected GUI", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]))
check("three serial report-only steps", [step["name"] for step in steps] == ["default-a", "mission-enabled", "default-b"])
for step in steps:
    check(f"step success {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None and step["gui_preserved"] is True)
    check(f"report-only command {step['name']}", " -report -rpts " in step["arguments"] and " -rjexport " in step["arguments"] and " -calc " not in step["arguments"] and " -close" in step["arguments"])
    check(f"same source SXO {step['name']}", str(PARENT_RUN / "model.sxo") in step["arguments"])

source_paths = {
    "contract": CASE / "contract.json",
    "parent_closure": PARENT_RUN / "closure.json",
    "parent_input": PARENT / "baseline-input.json",
    "parent_sxo": PARENT_RUN / "model.sxo",
    "parent_report": PARENT_RUN / "report-raw.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-01.md",
    "settings_builder": CASE / "make_report_settings.py",
    "mission_settings": CASE / "runs" / "settings" / "mission-enabled.sxs",
    "default_settings": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "report_runner": CASE / "run_reports_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check("complete source fingerprint set", set(source_paths) == set(closure["source_hashes_before"]))
for key, before in closure["source_hashes_before"].items():
    check(f"source before/after {key}", before == closure["source_hashes_after"][key] == invocation["source_hashes_before"][key])
    check(f"source exists/SHA {key}", source_paths[key].is_file() and digest(source_paths[key]) == before)
for key, source in (("input_sha256", "parent_input"), ("sxo_sha256", "parent_sxo"), ("closure_sha256", "parent_closure"), ("signoff_sha256", "parent_signoff"), ("default_report_sha256", "parent_report")):
    check(f"contract parent {key}", contract["parent"][key] == closure["source_hashes_before"][source])
for key, source in (("installed_default_sha256", "default_settings"), ("mission_enabled_sha256", "mission_settings"), ("builder_sha256", "settings_builder")):
    check(f"contract settings {key}", contract["settings"][key] == closure["source_hashes_before"][source])
check("contract manual pin", contract["manual"]["sha256"] == closure["source_hashes_before"]["manual"])
check("eight raw seals", len(closure["raw"]) == 8)
for name, seal in closure["raw"].items():
    path = RUN / name
    check(f"raw exists {name}", path.is_file())
    if path.is_file():
        check(f"raw bytes {name}", path.stat().st_size == seal["bytes"])
        check(f"raw SHA {name}", digest(path) == seal["sha256"])

source_settings = source_paths["default_settings"].read_bytes()
derived_settings = source_paths["mission_settings"].read_bytes()
changed = [index for index, (a, b) in enumerate(zip(source_settings, derived_settings)) if a != b]
check("settings same size", len(source_settings) == len(derived_settings))
check("eight N-to-Y settings bytes", len(changed) == 8 and all(source_settings[i] == ord("N") and derived_settings[i] == ord("Y") for i in changed))

parent_bytes = (PARENT_RUN / "report-raw.json").read_bytes()
default_a_bytes = (RUN / "default-a-report-raw.json").read_bytes()
default_b_bytes = (RUN / "default-b-report-raw.json").read_bytes()
check("default A/B byte equality", default_a_bytes == default_b_bytes)
parent_doc = native_report(PARENT_RUN / "report-raw.json")
default_a_doc = native_report(RUN / "default-a-report-raw.json")
default_b_doc = native_report(RUN / "default-b-report-raw.json")
mission_doc = native_report(RUN / "mission-enabled-report-raw.json")
check("default A/B parsed equality", default_a_doc == default_b_doc)
check("parent has no database_version", "database_version" not in parent_doc["report"])
check("explicit report database_version zero", default_a_doc["report"].get("database_version") == mission_doc["report"].get("database_version") == 0)
parent_tables = tables(parent_doc)
default_tables = tables(default_a_doc)
mission_tables = tables(mission_doc)
check("four default tables", set(default_tables) == set(parent_tables) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
check("mission adds four specific tables", set(mission_tables) - set(default_tables) == {"MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal"})
for name in default_tables:
    check(f"common table equality selected settings {name}", default_tables[name] == mission_tables[name])
    check(f"parent/explicit columns {name}", parent_tables[name]["columns"] == default_tables[name]["columns"])
    parent_rows = records(parent_tables[name])
    explicit_rows = records(default_tables[name])
    check(f"parent/explicit row count {name}", len(parent_rows) == len(explicit_rows))
    for index, (parent_row, explicit_row) in enumerate(zip(parent_rows, explicit_rows)):
        check(f"parent/explicit row {name}/{index}", parent_row == explicit_row)
for name in ("ProblemDescription", "ResultSummary"):
    check(f"unchanged instance name {name}", parent_tables[name]["instances"][0]["instance_name"] == default_tables[name]["instances"][0]["instance_name"])
for name in ("SystemResults", "StockTotalResults"):
    check(f"parent nonblank instance {name}", bool(parent_tables[name]["instances"][0]["instance_name"]))
    check(f"explicit blank instance {name}", default_tables[name]["instances"][0]["instance_name"] == "")
    rows = records(default_tables[name])
    check(f"72 half-hour bins {name}", len(rows) == 72 and all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(rows)))

mission_rows = records(mission_tables["MissionResults"])
fixed_rows = records(mission_tables["FixedMissionResults"])
fixed_total = records(mission_tables["FixedMissionResultsTotal"])
check("72 mission half-hour bins", len(mission_rows) == 72 and all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(mission_rows)))
check("mission h8-to-h10 two-hour occupancy", [row["STINT"] for row in mission_rows if row["MTREQ"] == row["MTACC"] == row["STREQ"] == row["STACC"] == 1] == [8, 8.5, 9, 9.5] and all(row["MTREQ"] == row["MTACC"] == row["STREQ"] == row["STACC"] == 0 for row in mission_rows if row["STINT"] not in (8, 8.5, 9, 9.5)))
check("one h8 fixed mission", len(fixed_rows) == 1 and fixed_rows[0]["STIM"] == 8 and fixed_rows[0]["NMSTA"] == fixed_rows[0]["NMSUC"] == 1 and fixed_rows[0]["NSYOT"] == 1 and fixed_rows[0]["MTOT"] == 1)
check("fixed mission summary", len(fixed_total) == 1 and fixed_total[0]["NMSTA"] == fixed_total[0]["NMSUC"] == 1 and fixed_total[0]["NSYOT"] == 1)
model_log = (PARENT_RUN / "model.log").read_text(encoding="latin-1")
check("parent event mission start h8", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2" in model_log)
check("parent event mission success h10", "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in model_log)

failed = [label for label, passed in CHECKS if not passed]
expected_failed_gate = "default report byte-equal to accepted parent"
check(expected_failed_gate, default_a_bytes == parent_bytes)
failed = [label for label, passed in CHECKS if not passed]
unexpected = [label for label in failed if label != expected_failed_gate]
verdict = {
    "schema": "simlox-k09-var01-independent-diagnostic-replay/v1",
    "run_id": RUN.name,
    "verdict": "NO_GO_FULL_CONTRACT" if not unexpected and expected_failed_gate in failed else "NO_GO_REPLAY",
    "diagnostic_replay": "GO" if not unexpected else "NO_GO",
    "checks": len(CHECKS),
    "passed": len(CHECKS) - len(failed),
    "failed": failed,
    "unexpected_failures": unexpected,
    "parent_report_sha256": digest(PARENT_RUN / "report-raw.json"),
    "default_a_sha256": digest(RUN / "default-a-report-raw.json"),
    "default_b_sha256": digest(RUN / "default-b-report-raw.json"),
    "mission_enabled_sha256": digest(RUN / "mission-enabled-report-raw.json"),
    "difference": "Explicit -rpts adds report.database_version=0 and blanks SystemResults and StockTotalResults instance_name. Common table columns and all 72 row values match the accepted J05 parent, and explicit default A/B are byte-identical. The frozen parent byte-identity gate fails.",
    "limits": "One accepted J05 SXO and three report-only exports. Retain this version as an excluded diagnostic; a narrower prospective contract is required for publication.",
}
(CASE / "review" / "independent-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(json.dumps(verdict, indent=2))
if unexpected:
    raise SystemExit(1)

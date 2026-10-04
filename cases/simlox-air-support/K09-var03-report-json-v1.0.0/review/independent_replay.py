"""Independent, read-only replay for the K09.var03 report-JSON cross-reference."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CASES = HERE.parent
REPO = HERE.parents[2]
ACCEPTED = CASES / "K09-var01-report-settings-v1.0.1"
DIAGNOSTIC = CASES / "K09-var01-report-settings-v1.0.0"
RUN = ACCEPTED / "runs/k09-var01-report-settings-v101-ssh-20261004-01"
OLD_RUN = DIAGNOSTIC / "runs/k09-var01-report-settings-v100-ssh-20261004-01"
J05 = CASES / "J05-collection-window-v1.0.1"
J05_RUN = J05 / "runs/j05-baseline-v101-20261001-01"
VERDICT_PATH = Path(__file__).with_name("independent-verdict.json")
checks = 0
failures = []


def check(ok, label):
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return sha_bytes(path.read_bytes())


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def git_bytes(path):
    relative = path.relative_to(REPO).as_posix()
    result = subprocess.run(["git", "show", "HEAD:" + relative], cwd=REPO, capture_output=True, check=False)
    check(result.returncode == 0, "published Git blob: " + relative)
    return result.stdout if result.returncode == 0 else b""


contract = load(HERE / "contract.json")
index = load(ACCEPTED / "evidence-index.json")
parent_contract = load(ACCEPTED / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
steps = load(RUN / "steps.json")
outcome = load(RUN / "outcome.json")
old_closure = load(OLD_RUN / "closure.json")
parent = contract["parent"]
check(contract["evidence_mode"] == "source-bound reuse of accepted K09.var01 report-only native exports; no new native call", "cross-reference mode")
check(parent["package"] == ACCEPTED.name and parent["run_id"] == RUN.name, "accepted K09 parent")
check(sha(ACCEPTED / "evidence-index.json") == parent["evidence_index_sha256"], "parent index pin")
check(sha_bytes(git_bytes(ACCEPTED / "evidence-index.json")) == parent["evidence_index_sha256"], "parent index Git bytes")
for name, path, wanted in [
    ("parent contract", ACCEPTED / "contract.json", parent["contract_sha256"]),
    ("parent independent verdict", ACCEPTED / "review/independent-verdict.json", parent["independent_verdict_sha256"]),
    ("parent signoff", ACCEPTED / "cli-scope-signoff-2026-10-05.md", parent["signoff_sha256"]),
]:
    check(sha(path) == wanted, name + " disk SHA")
    check(sha_bytes(git_bytes(path)) == wanted, name + " Git SHA")
check(load(ACCEPTED / "review/independent-verdict.json")["verdict"] == "GO_BOUNDED", "parent independent acceptance")
for version, package in [("v1.0.0", DIAGNOSTIC), ("v1.0.1", ACCEPTED)]:
    for relative, record in sorted(index["source"][version].items()):
        path = package / relative
        check(path.is_file() and path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], f"source disk {version}/{relative}")
        check(sha_bytes(git_bytes(path)) == record["sha256"], f"source Git {version}/{relative}")
check(index["runs"]["bounded_candidate"]["run_id"] == RUN.name, "indexed accepted run")
check(index["runs"]["excluded_diagnostic"]["run_id"] == OLD_RUN.name, "indexed excluded run")
check(index["runs"]["excluded_diagnostic"]["classification"] == "excluded_diagnostic", "older diagnostic excluded")
check(sha(OLD_RUN / "closure.json") == parent_contract["excluded_diagnostic"]["closure_sha256"], "excluded closure pin")
check(sha(OLD_RUN / "closure.json") == index["runs"]["excluded_diagnostic"]["closure"]["sha256"], "excluded index closure")
check(parent_contract["excluded_diagnostic"]["reason"].startswith("The predeclared byte-for-byte equality"), "older diagnostic reason")

check(closure["run_id"] == invocation["run_id"] == RUN.name, "accepted run IDs")
check(closure["error"] is None and closure["publication_state"] == "not_published", "accepted closure state")
check(sha(RUN / "closure.json") == parent["closure_sha256"] == index["runs"]["bounded_candidate"]["closure"]["sha256"], "accepted closure pin")
check(sha(RUN / "invocation.json") == closure["invocation_sha256"] == index["runs"]["bounded_candidate"]["invocation"]["sha256"], "invocation pin")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source immutability")
source_paths = {
    "contract": ACCEPTED / "contract.json",
    "excluded_diagnostic_closure": OLD_RUN / "closure.json",
    "parent_closure": J05_RUN / "closure.json",
    "parent_input": J05 / "baseline-input.json",
    "parent_sxo": J05_RUN / "model.sxo",
    "parent_report": J05_RUN / "report-raw.json",
    "parent_signoff": J05 / "cli-scope-signoff-2026-10-01.md",
    "settings_builder": ACCEPTED / "make_report_settings.py",
    "mission_settings": ACCEPTED / "runs/settings/mission-enabled.sxs",
    "default_settings": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "report_runner": ACCEPTED / "run_reports_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check(set(source_paths) == set(closure["source_hashes_before"]), "complete source map")
for name, path in source_paths.items():
    check(path.is_file() and sha(path) == closure["source_hashes_before"].get(name), "accepted source seal: " + name)
check(sha(J05_RUN / "model.sxo") == parent["source_sxo_sha256"], "J05 source SXO pin")
check(sha(J05_RUN / "closure.json") == parent_contract["parent"]["closure_sha256"], "J05 closure parent pin")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH session zero")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
check(len(closure["raw"]) == index["raw_files_total"] // 2 == 8, "eight accepted raw seals")
check(closure["raw"] == index["runs"]["bounded_candidate"]["raw"], "indexed raw map")
for name, record in sorted(closure["raw"].items()):
    path = RUN / name
    check(path.is_file(), "raw exists: " + name)
    if path.is_file():
        check(path.stat().st_size == record["bytes"], "raw bytes: " + name)
        check(sha(path) == record["sha256"], "raw SHA: " + name)
check([step["name"] for step in steps] == ["default-a", "mission-enabled", "default-b"], "three report-only steps")
for step in steps:
    name = step["name"]
    args = step["arguments"]
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] and step["error"] is None, "guarded report step: " + name)
    check(re.search(r"-report\s+-rpts\s+.*\s+-rjexport\s+", args) is not None and "-calc" not in args, "report-only command: " + name)
    check(str(J05_RUN / "model.sxo").lower() in args.lower(), "sealed source SXO command: " + name)
    settings = source_paths["mission_settings"] if name == "mission-enabled" else source_paths["default_settings"]
    check(str(settings).lower() in args.lower(), "settings selector command: " + name)
    check(str(RUN / (name + "-report-raw.json")).lower() in args.lower(), "report destination: " + name)
check(outcome.get("error") is None, "completed report outcome")

reports = {}
for name, contract_key in [("default-a", "default_a"), ("mission-enabled", "mission_enabled"), ("default-b", "default_b")]:
    path = RUN / (name + "-report-raw.json")
    raw = path.read_bytes()
    check(sha_bytes(raw) == contract["raw_report_sha256"][contract_key], "contract report SHA: " + name)
    try:
        reports[name] = json.loads(raw.decode("utf-8"))
        check(True, "strict UTF-8 JSON: " + name)
    except (UnicodeDecodeError, json.JSONDecodeError):
        reports[name] = {"report": {"tables": []}}
        check(False, "strict UTF-8 JSON: " + name)
check((RUN / "default-a-report-raw.json").read_bytes() == (RUN / "default-b-report-raw.json").read_bytes(), "fresh defaults byte-identical")
default = {table["name"]: table for table in reports["default-a"]["report"]["tables"]}
mission = {table["name"]: table for table in reports["mission-enabled"]["report"]["tables"]}
check(set(default) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "exact four default tables")
added = {"MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal"}
check(set(mission) == set(default) | added, "exact eight mission-enabled tables")
check(len(mission) == 8 and len(default) == 4, "4-versus-8 counts")
for name in default:
    left, right = default[name], mission[name]
    check(left["columns"] == right["columns"], "common columns: " + name)
    check([(i["instance_name"], i["rows"]) for i in left["instances"]] == [(i["instance_name"], i["rows"]) for i in right["instances"]], "common instances/rows: " + name)
    check(left == next(table for table in reports["default-b"]["report"]["tables"] if table["name"] == name), "second default table: " + name)
mission_rows = [row for instance in mission["MissionResults"]["instances"] for row in instance["rows"]]
check(len(mission_rows) == 72, "72 half-hour MissionResults bins")
columns = [column["name"] for column in mission["MissionResults"]["columns"]]
start, end = columns.index("STINT"), columns.index("ETINT")
check(all(row[start] == index * 0.5 and row[end] == (index + 1) * 0.5 for index, row in enumerate(mission_rows)), "contiguous 0-36 half-hour bins")
fixed = mission["FixedMissionResults"]
fixed_rows = [row for instance in fixed["instances"] for row in instance["rows"]]
fixed_fields = {column["name"]: value for column, value in zip(fixed["columns"], fixed_rows[0])} if len(fixed_rows) == 1 else {}
check(len(fixed_rows) == 1 and fixed_fields.get("STIM") == 8 and fixed_fields.get("NMSUC") == 1 and fixed_fields.get("MTOT") == 1 and fixed_fields.get("MTREQ") == 2, "h8 mission, success and two operating hours")
for name in ["MissionResultsTotal", "FixedMissionResultsTotal", "SystemResults", "StockTotalResults"]:
    expected = 72 if name in {"SystemResults", "StockTotalResults"} else 1
    table = mission[name]
    check(sum(len(i["rows"]) for i in table["instances"]) == expected, f"{name} row count")

# The older J05 export has one legacy trailing comma and is intentionally not
# counted as strictly parseable JSON. Remove only such commas to compare its
# four table schemas and data rows with the accepted fresh reports.
older_text = (J05_RUN / "report-raw.json").read_bytes().decode("utf-8")
check(sha(J05_RUN / "report-raw.json") == parent_contract["parent"]["default_report_sha256"], "older J05 report seal")
try:
    json.loads(older_text)
    old_strict = True
except json.JSONDecodeError:
    old_strict = False
check(not old_strict, "older J05 raw report legacy syntax disclosed")
older_clean = re.sub(r",(?=\s*[}\]])", "", older_text)
check(len(older_text) - len(older_clean) == 1, "only one legacy trailing comma normalized")
older = {table["name"]: table for table in json.loads(older_clean)["report"]["tables"]}
check(set(older) == set(default), "older J05 four common tables")
for name in default:
    check(older[name]["columns"] == default[name]["columns"], "older J05 common columns: " + name)
    check([i["rows"] for i in older[name]["instances"]] == [i["rows"] for i in default[name]["instances"]], "older J05 common rows: " + name)
check((J05_RUN / "report-raw.json").read_bytes() != (RUN / "default-a-report-raw.json").read_bytes(), "older J05 report not byte-identical")
check("No generic JSON serialization guarantee" in contract["limits"][1], "bounded serializer claim")

verdict = {
    "schema": "simlox-k09-var03-independent-report-json-verdict/v1",
    "case_id": "K09.var03",
    "verdict": "GO_BOUNDED" if not failures else "NO_GO",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "accepted_run_id": RUN.name,
    "accepted_raw_seals": len(closure["raw"]),
    "finding": "Three guarded report-only exports from one accepted J05 SXO parse as UTF-8 JSON; default A/B are byte-identical, mission settings add exactly four tables, and all four common tables retain equal columns and rows.",
    "limits": ["Source-bound reuse only: no new K09 calculation or report export.", "One SXO and two settings on one installed SIMLOX 2017 executable; no general serializer guarantee.", "The older J05 raw report has legacy trailing-comma syntax and differs in metadata/instance labels; only common columns and data rows are compared.", "No GUI formatting, alternate model, database export, anonymization, or cross-engine claim."],
}
VERDICT_PATH.write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"verdict": verdict["verdict"], "checks": f"{verdict['checks_passed']}/{checks}", "failures": failures, "script_sha256": sha(Path(__file__)), "verdict_sha256": sha(VERDICT_PATH)}, indent=2))

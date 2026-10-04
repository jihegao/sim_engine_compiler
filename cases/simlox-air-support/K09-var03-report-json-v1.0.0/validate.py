"""Read-only, source-bound K09.var03 replay. Never invokes SIMLOX."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "K09-var01-report-settings-v1.0.1"
CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
PINS = CONTRACT["parent"]
INDEX = json.loads((PARENT / "evidence-index.json").read_text(encoding="utf-8"))
RUN_INDEX = INDEX["runs"]["bounded_candidate"]
RUN = PARENT / "runs" / RUN_INDEX["run_id"]
passed = 0


def require(condition, label):
    global passed
    if not condition:
        raise AssertionError(label)
    passed += 1


def seal(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def git_bytes(path):
    relative = path.relative_to(ROOT.parent.parent).as_posix()
    return subprocess.check_output(["git", "show", "origin/simlox/main:" + relative], cwd=ROOT.parent.parent)


for name, key in (("evidence-index.json", "evidence_index_sha256"),
                  ("contract.json", "contract_sha256"),
                  ("review/independent-verdict.json", "independent_verdict_sha256"),
                  ("cli-scope-signoff-2026-10-05.md", "signoff_sha256")):
    path = PARENT / name
    require(seal(path.read_bytes())["sha256"] == PINS[key], "linked disk " + name)
    require(seal(git_bytes(path))["sha256"] == PINS[key], "linked Git " + name)

for version, entries in INDEX["source"].items():
    package = ROOT / ("K09-var01-report-settings-" + version)
    for name, expected in entries.items():
        path = package / name
        require(seal(path.read_bytes()) == expected, "indexed disk " + version + "/" + name)
        require(seal(git_bytes(path)) == expected, "indexed Git " + version + "/" + name)

require(PINS["run_id"] == RUN_INDEX["run_id"], "accepted run identity")
require(RUN_INDEX["classification"] == "bounded_candidate", "accepted classification")
require(seal((RUN / "closure.json").read_bytes()) == RUN_INDEX["closure"], "accepted closure")
require(seal((RUN / "invocation.json").read_bytes()) == RUN_INDEX["invocation"], "accepted invocation")
for name, expected in RUN_INDEX["raw"].items():
    require(seal((RUN / name).read_bytes()) == expected, "accepted raw " + name)
require(len(RUN_INDEX["raw"]) == 8, "eight sealed raw artifacts")
require(INDEX["runs"]["excluded_diagnostic"]["classification"] == "excluded_diagnostic", "older diagnostic excluded")

invocation = read_json(RUN / "invocation.json")
closure = read_json(RUN / "closure.json")
steps = read_json(RUN / "steps.json")
verdict = read_json(PARENT / "review/independent-verdict.json")
require(invocation["run_id"] == PINS["run_id"], "invocation run identity")
require(invocation["session_id"] == 0, "session zero")
require("sshd.exe" in invocation["ssh_ancestor_names"], "SSH ancestor")
require(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "host mutex")
require(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "GUI coexistence")
require(invocation["source_hashes_before"]["parent_sxo"] == PINS["source_sxo_sha256"], "source SXO pin")
require(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source hashes unchanged")
require(closure["raw"] == RUN_INDEX["raw"], "closure raw map")
require(verdict["verdict"] == "GO_BOUNDED" and verdict["passed"] == verdict["checks"] == 263 and not verdict["failed"], "parent independent verdict")
require([step["name"] for step in steps] == ["default-a", "mission-enabled", "default-b"], "three report step order")
for step in steps:
    args = step["arguments"]
    require(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True, "completed guarded " + step["name"])
    require(all(flag in args for flag in ("-report", "-rpts", "-rjexport")), "report export flags " + step["name"])
    require("-calc" not in args and "-jimport" not in args, "no recalculation " + step["name"])

report_names = ["default-a-report-raw.json", "mission-enabled-report-raw.json", "default-b-report-raw.json"]
raw = [(RUN / name).read_bytes() for name in report_names]
for name, data, key in zip(report_names, raw, ("default_a", "mission_enabled", "default_b")):
    require(seal(data)["sha256"] == CONTRACT["raw_report_sha256"][key], "contract report pin " + name)
reports = [json.loads(data.decode("utf-8"))["report"] for data in raw]
require(raw[0] == raw[2], "fresh default byte identity")
require(all(set(report) == {"database_version", "tables"} for report in reports), "strict report object shape")
require(all(report["database_version"] == 0 for report in reports), "database version")
common = ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"]
mission = ["MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal"]
names = [[table["name"] for table in report["tables"]] for report in reports]
require(names[0] == common and names[2] == common, "default table names")
require(names[1] == common[:2] + mission + common[2:], "mission table names")
by_name = [{table["name"]: table for table in report["tables"]} for report in reports]
for name in common:
    base = by_name[0][name]
    for other in (by_name[1][name], by_name[2][name]):
        require(base["columns"] == other["columns"], "common columns " + name)
        require([i["rows"] for i in base["instances"]] == [i["rows"] for i in other["instances"]], "common data " + name)
for table in reports[1]["tables"]:
    require(len(table["instances"]) == 1, "one instance " + table["name"])
    require(all(len(row) == len(table["columns"]) for row in table["instances"][0]["rows"]), "row width " + table["name"])
require(len(by_name[1]["MissionResults"]["instances"][0]["rows"]) == 72, "72 mission bins")
require(len(by_name[1]["FixedMissionResults"]["instances"][0]["rows"]) == 1, "one fixed mission row")
require(all(len(by_name[1][name]["instances"][0]["rows"]) == 72 for name in ("SystemResults", "StockTotalResults")), "72 common bins")

result = {"schema": "simlox-k09-var03-author-validation/v1", "case_id": "K09.var03",
          "verdict": "GO_BOUNDED", "checks_passed": passed, "checks_total": passed,
          "reused_raw_seals": 8, "native_invocations_added": 0,
          "finding": "Three accepted source-bound report-only exports are strict UTF-8 JSON; default reports are byte-identical and mission settings add four mission tables.",
          "limits": CONTRACT["limits"]}
destination = HERE / "review" / "author-validation-2026-10-05.json"
destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"verdict": result["verdict"], "checks": passed, "raw_seals": 8}))

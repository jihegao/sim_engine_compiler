"""Independent read-only replay for A02.var01 insufficient-gap v0.1.1."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REVIEW = Path(__file__).resolve().parent
PKG = REVIEW.parent
CASES = PKG.parent
RUN = PKG / "runs/a02-var01-insufficient-gap-v011-ssh-20261006-01"
count = 0
errors: list[str] = []


def ck(condition: bool, label: str) -> None:
    global count
    count += 1
    if not condition:
        errors.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def obj(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def raw_seals(base: Path, artifacts: dict, label: str) -> None:
    for name, rec in artifacts.items():
        path = base / name
        ck(path.is_file(), f"{label} missing {name}")
        if path.is_file():
            ck(path.stat().st_size == rec["bytes"], f"{label} size {name}")
            ck(sha(path) == rec["sha256"], f"{label} sha {name}")


contract = obj(PKG / "contract.json")
ck(sha(PKG / "contract.json") == "f674de2448d4c97e909da95c1c0a3c9ffbea743da19bb0042d16ba6d5137a6d5", "contract sha")
for field, folder in (("prerequisite_a01", "A01-single-aircraft-single-mission"),
                      ("accepted_parent", "A02-single-aircraft-repeated-missions")):
    package = CASES / folder
    pins = contract[field]
    for key, name in (("input_sha256", "native-input.json"), ("contract_sha256", "contract.json"),
                      ("signoff_sha256", "cli-scope-signoff-2026-09-29.md"),
                      ("evidence_index_sha256", "evidence-index.json")):
        ck(sha(package / name) == pins[key], f"{field} {key}")
    runs = obj(package / "evidence-index.json")["runs"]
    ck([r["run_id"] for r in runs] == [pins["final_run_id"], pins["replay_run_id"]], f"{field} run IDs")
    for indexed, closure_key in zip(runs, ("final_closure_sha256", "replay_closure_sha256")):
        ck(len(indexed["artifacts"]) == 17, f"{field} indexed count")
        closure_path = Path(indexed["artifacts"]["closure.json"]["path"])
        ck(sha(closure_path) == pins[closure_key], f"{field} closure")
        for name, rec in indexed["artifacts"].items():
            path = Path(rec["path"])
            ck(path.is_file(), f"{field} missing {name}")
            if path.is_file():
                ck(path.stat().st_size == rec["bytes"], f"{field} size {name}")
                ck(sha(path) == rec["sha256"], f"{field} sha {name}")

sibling_pin = contract["published_at_return_sibling"]
sibling = CASES / sibling_pin["package"]
sibling_run = sibling / "runs" / sibling_pin["run_id"]
for key, path in (("input_sha256", sibling / "native-input.json"),
                  ("evidence_index_sha256", sibling / "evidence-index.json"),
                  ("closure_sha256", sibling_run / "closure.json"),
                  ("independent_verdict_sha256", sibling / "review/independent-verdict.json")):
    ck(sha(path) == sibling_pin[key], f"sibling {key}")
raw_seals(sibling_run, obj(sibling_run / "closure.json")["raw"], "sibling")

old_pin = contract["excluded_prelaunch"]
old = CASES / old_pin["package"]
for key, name in (("contract_sha256", "contract.json"), ("validator_sha256", "validate_native_cli.py"),
                  ("runner_sha256", "run_native_ssh.ps1"),
                  ("no_go_sha256", "review/independent-prelaunch-no-go-2026-10-06.md")):
    ck(sha(old / name) == old_pin[key], f"old {key}")
ck(not (old / "runs/a02-var01-insufficient-gap-v010-ssh-20261006-01").exists(), "v010 no run")

analogue = contract["accepted_a12_cancellation_analogue"]
a12 = CASES / analogue["package"]
a12_run = a12 / "runs" / analogue["run_id"]
for key, path in (("input_sha256", a12 / analogue["input_file"]),
                  ("contract_sha256", a12 / "contract.json"),
                  ("signoff_sha256", a12 / "cli-scope-signoff-2026-09-30.md"),
                  ("independent_verdict_sha256", a12 / "review/independent-priority-2026-09-30.json"),
                  ("closure_sha256", a12_run / "closure.json"),
                  ("model_log_sha256", a12_run / "model.log"),
                  ("report_raw_sha256", a12_run / "report-raw.json")):
    ck(sha(path) == analogue[key], f"A12 {key}")
a12_text = (a12_run / "report-raw.json").read_text(encoding="utf-8-sig")
a12_data = json.loads(re.sub(r",\s*([}\]])", r"\1", a12_text))
a12_summary = next(t for t in a12_data["report"]["tables"] if t["name"] == "ResultSummary")
a12_values = dict(zip((x["name"] for x in a12_summary["columns"]), a12_summary["instances"][0]["rows"][0]))
for field in ("MTMF", "MSTF", "MSUF", "STMF"):
    ck(a12_values[field] == .5, f"A12 summary {field}")

closure = obj(RUN / "closure.json")
invocation = obj(RUN / "invocation.json")
ck(sha(RUN / "closure.json") == "fff531321e18b8c8074ca172da5b83c729d7aa356484cbd2c00e3d05305546b1", "child closure sha")
ck(closure["run_id"] == contract["ownership"]["native_run_id_reserved"] and closure["error"] is None, "child closure success")
ck(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
ck(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source before/after")
parent_package = CASES / "A02-single-aircraft-repeated-missions"
prereq_package = CASES / "A01-single-aircraft-single-mission"
parent_runs = obj(parent_package / "evidence-index.json")["runs"]
prereq_runs = obj(prereq_package / "evidence-index.json")["runs"]
source_paths = {
    "child_input": PKG / "native-input.json", "child_contract": PKG / "contract.json",
    "contract_review": REVIEW / "independent-contract-go-2026-10-06.md",
    "excluded_contract": old / "contract.json", "excluded_validator": old / "validate_native_cli.py",
    "excluded_runner": old / "run_native_ssh.ps1",
    "excluded_no_go": old / "review/independent-prelaunch-no-go-2026-10-06.md",
    "analogue_input": a12 / analogue["input_file"], "analogue_contract": a12 / "contract.json",
    "analogue_signoff": a12 / "cli-scope-signoff-2026-09-30.md",
    "analogue_verdict": a12 / "review/independent-priority-2026-09-30.json",
    "analogue_closure": a12_run / "closure.json", "analogue_log": a12_run / "model.log",
    "analogue_report": a12_run / "report-raw.json",
    "sibling_input": sibling / "native-input.json", "sibling_index": sibling / "evidence-index.json",
    "sibling_closure": sibling_run / "closure.json",
    "sibling_verdict": sibling / "review/independent-verdict.json",
    "negative_checker": PKG / "check_negative_control.py",
    "negative_control": REVIEW / "negative-control-parent-and-sibling.json",
    "builder": PKG / "build.py", "parent_diff": PKG / "check_parent_diff.py",
    "roundtrip_checker": PKG / "check_roundtrip.py",
    "behavior_validator": PKG / "validate_native_cli.py",
    "runner_script": PKG / "run_native_ssh.ps1",
    "accepted_input": parent_package / "native-input.json",
    "accepted_contract": parent_package / "contract.json",
    "accepted_signoff": parent_package / "cli-scope-signoff-2026-09-29.md",
    "accepted_index": parent_package / "evidence-index.json",
    "accepted_final_closure": Path(parent_runs[0]["artifacts"]["closure.json"]["path"]),
    "accepted_replay_closure": Path(parent_runs[1]["artifacts"]["closure.json"]["path"]),
    "prereq_input": prereq_package / "native-input.json",
    "prereq_contract": prereq_package / "contract.json",
    "prereq_signoff": prereq_package / "cli-scope-signoff-2026-09-29.md",
    "prereq_index": prereq_package / "evidence-index.json",
    "prereq_final_closure": Path(prereq_runs[0]["artifacts"]["closure.json"]["path"]),
    "prereq_replay_closure": Path(prereq_runs[1]["artifacts"]["closure.json"]["path"]),
    "installed_manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "installed_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "prelaunch_approval": REVIEW / "independent-prelaunch-go.json",
}
ck(set(source_paths) == set(closure["source_hashes_before"]), "complete 41-source map")
for name, path in source_paths.items():
    ck(path.is_file(), f"source missing {name}")
    if path.is_file():
        ck(sha(path) == closure["source_hashes_before"][name], f"source sha {name}")
ck(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0")
ck(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "mutex")
gui = invocation["gui"]
ck((gui["pid"], gui["session_id"], gui["start_unix_ms"]) == (13340, 1, 1790590196826), "GUI identity")
ck(sha(PKG / "native-input.json") == sha(RUN / "input.json") == contract["source_delta"].get("child_input_sha256", "df7d693e7364c50d489723c2d4c336c1225959e1e03cfb6535f82d9cf32a2109"), "child input sha")
ck(sha(PKG / "run_native_ssh.ps1") == invocation["runner_script_sha256"], "runner pin")
ck(sha(PKG / "validate_native_cli.py") == closure["source_hashes_before"]["behavior_validator"], "validator pin")
ck(sha(REVIEW / "independent-prelaunch-go.json") == closure["source_hashes_before"]["prelaunch_approval"], "prelaunch approval pin")
raw_seals(RUN, closure["raw"], "child")
ck(len(closure["raw"]) == 12, "12 child raw")
steps = obj(RUN / "steps.json")
ck([s["name"] for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport"], "five ordered steps")
for k, step in enumerate(steps):
    ck((step["status"], step["exit_code"], step["gui_preserved"]) == ("completed", 0, True), f"step {k}")
ck([x["name"] for x in invocation["planned_commands"]] == ["import", "export", "calc", "jsonreport"], "four native calls")

parent = obj(CASES / "A02-single-aircraft-repeated-missions/native-input.json")["model"]["tables"]
child = obj(PKG / "native-input.json")["model"]["tables"]
ck([x["name"] for x in parent] == [x["name"] for x in child], "source table geometry")
deltas = []
for before, after in zip(parent, child):
    ck(before["columns"] == after["columns"], f"source columns {before['name']}")
    for pi, ai in zip(before["instances"], after["instances"]):
        for pr, ar in zip(pi["rows"], ai["rows"]):
            for col, pv, av in zip(before["columns"], pr, ar):
                if pv != av:
                    deltas.append((before["name"], col["name"], pv, av))
ck(deltas == [("OperationProfile", "STIM", 20.0, 9.5)], "sole authored cell")
ck(sum(len(r) for t in child for i in t["instances"] for r in i["rows"]) == 179, "179 authored cells")
authored = {t["name"]: t for t in child if any(i["rows"] for i in t["instances"])}
exported = {t["name"]: t for t in obj(RUN / "roundtrip-raw.json")["model"]["tables"]}
ck(len(authored) == 13, "13 authored tables")
for name, table in authored.items():
    ck(exported.get(name) == table, f"roundtrip {name}")
ck(obj(RUN / "roundtrip-validation.json")["passed"] is True, "roundtrip gate")
calc_log = (RUN / "run.log").read_text(encoding="utf-8-sig")
ck("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc_log, "converter summary")
ck(re.findall(r"\(warning #(\d+)\)", calc_log) == ["108", "126"], "warnings 108/126 only")
ck(not re.findall(r"\((?:error|note) #\d+\)", calc_log), "no converter errors/notes")

events = (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
parent_index = obj(CASES / "A02-single-aircraft-repeated-missions/evidence-index.json")["runs"][0]
parent_events = Path(parent_index["artifacts"]["model.log"]["path"]).read_text(encoding="utf-8-sig").splitlines()

def hits(time: str, fragment: str) -> list[int]:
    return [k for k, line in enumerate(events) if line.startswith(f"Time: {time} ") and fragment in line]

for mission, start, finish in ((0, "8", "10"), (2, "32", "34")):
    tag = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mission}>"
    for time, phrase in ((start, " mission starting, duration: 2 : <TEACH-AIR-01,0>"),
                         (finish, " mission success:"), (finish, " mission completed: <TEACH-AIR-01,0>")):
        ck(len(hits(time, tag + phrase)) == 1, f"mission {mission} {phrase}")
    ck([x for x in events if tag in x] == [x for x in parent_events if tag in x], f"mission {mission} parent parity")
tag = "<BASIC-MISSION,TEACH-UNIT,0,0,1>"
ck(len(hits("8.5", tag + " mission created:")) == 1, "mission1 created")
ck(len(hits("8.5", tag + " mission activated, systems requested: 1")) == 1, "mission1 requests one")
waiting = [x for x in events if tag + " mission waiting:" in x]
ck(len(waiting) == 1 and waiting[0].startswith("Time: 8.5 ") and "timeout at 9.83333" in waiting[0], "mission1 h8.5 wait/deadline")
cancel = hits("9.83333", tag + " mission cancelled:")
ck(len(cancel) == 1, "mission1 h9.83333 cancellation")
first_arrival = hits("10", "System arrives <TEACH-AIR-01,0>, mission success")
ck(len(first_arrival) == 1 and cancel[0] < first_arrival[0], "cancel before first return")
ck(not any(tag in x and any(p in x for p in (" mission starting", " task starting", " task completed", " mission success:", " mission completed:")) for x in events), "mission1 never launches/tasks/succeeds")
ck([x for x in events if "mission cancelled:" in x] == [events[cancel[0]]], "only mission1 cancelled")
ck(sum(" mission starting, duration:" in x for x in events) == 2, "two starts")
ck(sum(" mission success:" in x for x in events) == 2, "two successes")
ck(sum(" mission completed:" in x for x in events) == 2, "two completions")
ck(set(re.findall(r"<TEACH-AIR-01,(\d+)>", "\n".join(events))) == {"0"}, "sole physical aircraft")

report_text = (RUN / "report-raw.json").read_text(encoding="utf-8-sig")
normalized, fixes = re.subn(r",\s*\]", "]", report_text)
ck(fixes == 1, "one trailing-comma parser-copy repair")
tables = {t["name"]: t for t in json.loads(normalized)["report"]["tables"]}
ck(set(tables) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report tables")
system = tables["SystemResults"]
stock = tables["StockTotalResults"]
sfields = [x["name"] for x in system["columns"]]
tfields = [x["name"] for x in stock["columns"]]
srows = system["instances"][0]["rows"]
trows = stock["instances"][0]["rows"]
ck((len(sfields), len(srows), len(tfields), len(trows)) == (40, 72, 16, 72), "full report shape")
for index, row in enumerate(srows):
    start = index / 2
    state = "flight" if 8 <= start < 10 or 32 <= start < 34 else "reserved" if 7 <= start < 8 or 31 <= start < 32 else "ready"
    expected = dict.fromkeys(sfields, 0)
    expected.update(UNID="Total over all Units", SID="Total over all Systems", STINT=start, ETINT=start+.5,
                    NSYRY=int(state == "ready"), NSYMA=int(state != "ready"),
                    NSYMO=int(state == "flight"), NSYMR=int(state == "reserved"),
                    NSYA=1, FTMO=int(state == "flight"), STACC=int(state == "flight"), SYDT=None)
    for field, actual in zip(sfields, row):
        ck(actual == expected[field], f"system row {index} {field}")
for index, row in enumerate(trows):
    start = index / 2
    expected = dict.fromkeys(tfields, 0)
    expected.update(STINT=start, ETINT=start+.5, NBOU=None, ROS=None, ROST=None, WT=None,
                    WTT=None, WTS=None, PNB=1)
    for field, actual in zip(tfields, row):
        ck(actual == expected[field], f"stock row {index} {field}")
summary = tables["ResultSummary"]
fields = [x["name"] for x in summary["columns"]]
values = summary["instances"][0]["rows"][0]
ck(len(fields) == len(values) == 11, "11 summary fields")
expected_summary = {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": 2/3, "RSMTMF": 0,
                    "MSTF": 2/3, "RSMSTF": 0, "MSUF": 2/3, "RSMSUF": 0,
                    "STMF": 2/3, "RSSTMF": 0}
for field, value in zip(fields, values):
    ck(abs(value - expected_summary[field]) < 1e-6, f"summary {field}")
ck(sum(r[sfields.index("FTMO")] * .5 for r in srows) == 4, "four flight hours")
ck(sum(r[sfields.index("NSYRY")] * .5 for r in srows) == 30, "30 ready hours")
ck(srows[-1][sfields.index("NSYRY")] == 1 and trows[-1][tfields.index("NBO")] == 0, "ready/no-backorder terminal")

result = {
    "schema": "independent-a02-var01-insufficient-gap-v011-replay/v1",
    "decision": "GO_BOUNDED" if not errors else "NO_GO",
    "checks": count,
    "failures": errors,
    "run_id": RUN.name,
    "closure_sha256": sha(RUN / "closure.json"),
    "raw_log_sha256": sha(RUN / "model.log"),
    "raw_report_sha256": sha(RUN / "report-raw.json"),
    "scope": "one fixed-seed single-aircraft h9.5 scheduled mission cancellation before h10 return",
}
print(json.dumps(result, indent=2))
raise SystemExit(0 if not errors else 1)

"""Independent, read-only A02.var01 v0.1.1 replay. No author validator import."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
CASES = PKG.parent
RUN = PKG / "runs" / "a02-var01-at-return-v011-ssh-20261006-01"
OLD = CASES / "A02-var01-at-return-v0.1.0" / "runs" / "a02-var01-at-return-v010-ssh-20261006-01"
checks = 0
failures: list[str] = []


def ck(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def j(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seal(run: Path, records: dict, label: str) -> None:
    for name, rec in records.items():
        path = run / name
        ck(path.is_file(), f"{label} missing {name}")
        if path.is_file():
            ck(path.stat().st_size == rec["bytes"], f"{label} size {name}")
            ck(sha(path) == rec["sha256"], f"{label} sha {name}")


def accepted(package: str, pins: dict, prefix: str) -> None:
    base = CASES / package
    for key, filename in {
        "input_sha256": "native-input.json",
        "contract_sha256": "contract.json",
        "signoff_sha256": "cli-scope-signoff-2026-09-29.md",
        "evidence_index_sha256": "evidence-index.json",
    }.items():
        ck(sha(base / filename) == pins[key], f"{prefix} {key}")
    index = j(base / "evidence-index.json")
    ck(len(index["runs"]) == 2, f"{prefix} two runs")
    for run, closure_field, id_field in zip(
        index["runs"],
        ("final_closure_sha256", "replay_closure_sha256"),
        ("final_run_id", "replay_run_id"),
    ):
        ck(run["run_id"] == pins[id_field], f"{prefix} run id")
        ck(sha(Path(run["artifacts"]["closure.json"]["path"])) == pins[closure_field], f"{prefix} closure")
        for name, rec in run["artifacts"].items():
            path = Path(rec["path"])
            ck(path.is_file(), f"{prefix} missing {name}")
            if path.is_file():
                ck(path.stat().st_size == rec["bytes"], f"{prefix} size {name}")
                ck(sha(path) == rec["sha256"], f"{prefix} sha {name}")


contract = j(PKG / "contract.json")
ck(sha(PKG / "contract.json") == "ca816a596a8fd697ba1b23bc6a84a2344516f06a6ae855e2244dc7914c57e932", "contract sha")
accepted("A01-single-aircraft-single-mission", contract["prerequisite_a01"], "A01")
accepted("A02-single-aircraft-repeated-missions", contract["accepted_parent"], "A02")
old_closure = j(OLD / "closure.json")
old_failure = j(OLD / "failure-seal.json")
ck(sha(OLD / "closure.json") == contract["excluded_predecessor"]["closure_sha256"], "old closure")
ck(sha(OLD / "failure-seal.json") == contract["excluded_predecessor"]["failure_seal_sha256"], "old failure seal")
seal(OLD, old_failure["files"], "old raw")
old_steps = j(OLD / "steps.json")
ck([x["name"] for x in old_steps] == ["import", "export", "check_import_export"], "old stopped before calc")
ck(old_steps[-1]["exit_code"] == 1, "old checker failed")
old_validation = j(OLD / "roundtrip-validation.json")
ck(old_validation["differences"] == ["expected 10 row-containing authored tables; found 13"], "old sole count defect")
ck(not (OLD / "model.log").exists() and not (OLD / "report-raw.json").exists(), "old no simulation/report")

closure = j(RUN / "closure.json")
inv = j(RUN / "invocation.json")
ck(closure["run_id"] == contract["ownership"]["native_run_id_reserved"], "child run id")
ck(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
ck(closure["source_hashes_before"] == closure["source_hashes_after"], "source before/after stable")
ck(inv["source_hashes_before"] == closure["source_hashes_before"], "invocation source set")
source_paths = {
    "child_input": PKG / "native-input.json", "child_contract": PKG / "contract.json",
    "contract_review": HERE / "independent-contract-repair-go-2026-10-06.md",
    "repair_verdict": HERE / "repair-readonly-old-run.json",
    "excluded_closure": OLD / "closure.json", "excluded_failure_seal": OLD / "failure-seal.json",
    "excluded_checker": OLD.parent.parent / "check_roundtrip.py",
    "negative_checker": PKG / "check_negative_control.py",
    "negative_control": HERE / "negative-control-accepted-parent.json",
    "builder": PKG / "build.py", "parent_diff": PKG / "check_parent_diff.py",
    "roundtrip_checker": PKG / "check_roundtrip.py",
    "behavior_validator": PKG / "validate_native_cli.py",
    "runner_script": PKG / "run_native_ssh.ps1",
    "accepted_input": CASES / "A02-single-aircraft-repeated-missions/native-input.json",
    "accepted_contract": CASES / "A02-single-aircraft-repeated-missions/contract.json",
    "accepted_signoff": CASES / "A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md",
    "accepted_index": CASES / "A02-single-aircraft-repeated-missions/evidence-index.json",
    "accepted_final_closure": Path(j(CASES / "A02-single-aircraft-repeated-missions/evidence-index.json")["runs"][0]["artifacts"]["closure.json"]["path"]),
    "accepted_replay_closure": Path(j(CASES / "A02-single-aircraft-repeated-missions/evidence-index.json")["runs"][1]["artifacts"]["closure.json"]["path"]),
    "prereq_input": CASES / "A01-single-aircraft-single-mission/native-input.json",
    "prereq_contract": CASES / "A01-single-aircraft-single-mission/contract.json",
    "prereq_signoff": CASES / "A01-single-aircraft-single-mission/cli-scope-signoff-2026-09-29.md",
    "prereq_index": CASES / "A01-single-aircraft-single-mission/evidence-index.json",
    "prereq_final_closure": Path(j(CASES / "A01-single-aircraft-single-mission/evidence-index.json")["runs"][0]["artifacts"]["closure.json"]["path"]),
    "prereq_replay_closure": Path(j(CASES / "A01-single-aircraft-single-mission/evidence-index.json")["runs"][1]["artifacts"]["closure.json"]["path"]),
    "installed_manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "installed_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "prelaunch_approval": HERE / "independent-prelaunch-go.json",
}
for field, path in source_paths.items():
    ck(path.is_file(), f"source missing {field}")
    if path.is_file():
        ck(sha(path) == closure["source_hashes_before"][field], f"source sha {field}")
ck(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "SSH0 ancestry")
ck(inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "mutex")
ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1 and inv["gui"]["start_unix_ms"] == 1790590196826, "GUI identity")
ck(inv["input_sha256"] == sha(PKG / "native-input.json") == sha(RUN / "input.json"), "child source seal")
ck(inv["contract_sha256"] == sha(PKG / "contract.json"), "contract pin")
ck(inv["runner_script_sha256"] == sha(PKG / "run_native_ssh.ps1"), "runner pin")
seal(RUN, closure["raw"], "child raw")
steps = j(RUN / "steps.json")
ck([x["name"] for x in steps] == ["import", "export", "check_import_export", "calc", "jsonreport"], "step order")
for k, step in enumerate(steps):
    ck(step["exit_code"] == 0 and step["gui_preserved"] and step["status"] == "completed", f"step {k}")
ck([x["name"] for x in inv["planned_commands"]] == ["import", "export", "calc", "jsonreport"], "four native commands")

source = j(PKG / "native-input.json")["model"]["tables"]
parent = j(CASES / "A02-single-aircraft-repeated-missions" / "native-input.json")["model"]["tables"]
cells = []
for pt, ct in zip(parent, source):
    ck(pt["name"] == ct["name"] and pt["columns"] == ct["columns"], f"source schema {pt['name']}")
    for pi, ci in zip(pt["instances"], ct["instances"]):
        for pr, cr in zip(pi["rows"], ci["rows"]):
            for col, pv, cv in zip(pt["columns"], pr, cr):
                if pv != cv:
                    cells.append((pt["name"], col["name"], pv, cv))
ck(cells == [("OperationProfile", "STIM", 20.0, 10.0)], "sole source cell")
ck(sum(len(r) for t in source for i in t["instances"] for r in i["rows"]) == 179, "179 cells")
roundtrip = j(RUN / "roundtrip-raw.json")["model"]["tables"]
rt = {t["name"]: t for t in roundtrip}
authored = {t["name"]: t for t in source if any(i["rows"] for i in t["instances"])}
ck(len(authored) == 13, "13 authored tables")
for name, table in authored.items():
    ck(rt.get(name) == table, f"roundtrip {name}")
ck(j(RUN / "roundtrip-validation.json")["passed"] is True, "roundtrip gate")
runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
ck("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog, "converter summary")
ck(len(re.findall(r"\(warning #\d+\)", runlog)) == 2 and "(warning #108)" in runlog and "(warning #126)" in runlog, "classified warnings")
ck("(error #" not in runlog and "(note #" not in runlog, "no error/note")

log = (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
def event(time: str, fragment: str) -> int:
    hits = [i for i, line in enumerate(log) if line.startswith("Time: " + time + " ") and fragment in line]
    ck(len(hits) == 1, f"event h{time} {fragment}")
    return hits[0] if hits else -1

mission_times = [(0, "8", "10"), (1, "10", "12"), (2, "32", "34")]
for ident, start, end in mission_times:
    tag = f"<BASIC-MISSION,TEACH-UNIT,0,0,{ident}>"
    event(start, tag + " mission starting, duration: 2 : <TEACH-AIR-01,0>")
    event(end, tag + " mission success:")
    event(end, tag + " mission completed: <TEACH-AIR-01,0>")
    event(end, "System arrives <TEACH-AIR-01,0>, mission success")
event("9", "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission waiting:")
first_done = event("10", "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:")
preassigned = event("10", "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission preassigns a system:")
first_arrival = event("10", "System arrives <TEACH-AIR-01,0>, mission success")
second_alloc = event("10", "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission allocates system:")
second_start = event("10", "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting, duration: 2")
ck(0 <= first_done < preassigned < first_arrival < second_alloc < second_start, "observed h10 order")
ck(sum("mission starting, duration:" in x for x in log) == 3, "three starts")
ck(sum("mission success:" in x for x in log) == 3, "three successes")
ck(sum("mission completed:" in x for x in log) == 3, "three completions")
ck(not any("mission cancelled:" in x or "mission aborted:" in x for x in log), "no cancel/abort")
ck(not any("failure occurs" in x.lower() or "backorder" in x.lower() for x in log), "no failure/backorder")

raw_text = (RUN / "report-raw.json").read_text(encoding="utf-8-sig")
fixed_text, fixes = re.subn(r",\s*\]", "]", raw_text)
ck(fixes == 1, "one trailing comma parser-copy normalization")
report = json.loads(fixed_text)["report"]["tables"]
tables = {t["name"]: t for t in report}
ck(set(tables) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table set")
system = tables["SystemResults"]
stock = tables["StockTotalResults"]
scols = [c["name"] for c in system["columns"]]
tcols = [c["name"] for c in stock["columns"]]
srows = system["instances"][0]["rows"]
trows = stock["instances"][0]["rows"]
ck(len(srows) == len(trows) == 72, "72 report bins each")
for k, row in enumerate(srows):
    start = k / 2
    finish = start + .5
    state = "flight" if (8 <= start < 12 or 32 <= start < 34) else "reserved" if (7 <= start < 8 or 31 <= start < 32) else "ready"
    expected = {name: 0 for name in scols}
    expected.update(UNID="Total over all Units", SID="Total over all Systems", STINT=start, ETINT=finish,
                    NSYRY=int(state == "ready"), NSYMA=int(state != "ready"),
                    NSYMO=int(state == "flight"), NSYMR=int(state == "reserved"),
                    NSYA=1, FTMO=int(state == "flight"), STACC=int(state == "flight"), SYDT=None)
    for name, value in zip(scols, row):
        ck(value == expected[name], f"system bin {k} {name}")
for k, row in enumerate(trows):
    start = k / 2
    expected = {name: 0 for name in tcols}
    expected.update(STINT=start, ETINT=start+.5, NBOU=None, ROS=None, ROST=None,
                    WT=None, WTT=None, WTS=None, PNB=1)
    for name, value in zip(tcols, row):
        ck(value == expected[name], f"stock bin {k} {name}")
summary = tables["ResultSummary"]
ck([c["name"] for c in summary["columns"]] == ["NREP","RTILW","RTIUP","MTMF","RSMTMF","MSTF","RSMSTF","MSUF","RSMSUF","STMF","RSSTMF"], "summary columns")
expected_summary = [1, 0, 36, 1, 0, 1, 0, 1, 0, 1, 0]
for k, (actual, expected) in enumerate(zip(summary["instances"][0]["rows"][0], expected_summary)):
    ck(actual == expected, f"summary {k}")
ck(sum(r[scols.index("FTMO")] * .5 for r in srows) == 6, "six flight hours")
ck(sum(r[scols.index("NSYRY")] * .5 for r in srows) == 28, "28 ready hours")
ck(srows[-1][scols.index("NSYRY")] == 1 and trows[-1][tcols.index("NBO")] == 0, "terminal ready/no BO")

verdict = {
    "schema": "independent-a02-var01-v011-readonly-replay/v1",
    "decision": "GO_BOUNDED" if not failures else "NO_GO",
    "checks": checks,
    "failures": failures,
    "run_id": RUN.name,
    "closure_sha256": sha(RUN / "closure.json"),
    "raw_report_sha256": sha(RUN / "report-raw.json"),
    "raw_log_sha256": sha(RUN / "model.log"),
    "h10_order": ["first mission complete", "second mission preassign", "first system arrival", "second mission allocate", "second mission start"],
    "scope": "one fixed-seed at-return arm; no general tie-order or other A02.var01 arm",
    "author_cli_serializer": "not used; its set serialization failure is separate from raw replay",
}
print(json.dumps(verdict, indent=2))
raise SystemExit(0 if not failures else 1)

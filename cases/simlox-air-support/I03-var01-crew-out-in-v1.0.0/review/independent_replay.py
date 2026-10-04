"""Independent read-only replay of the sealed I03 crew OUT/IN panel."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "i03-var01-crew-transfer-v100-ssh-20261005-01"
ARMS = ("control", "out", "out_in")
CHECKS: list[tuple[str, bool]] = []


def check(label: str, ok: bool) -> None:
    CHECKS.append((label, bool(ok)))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path: Path) -> dict:
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(doc: dict, root: str) -> dict:
    return {table["name"]: table for table in doc[root]["tables"]}


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


contract = load(CASE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check("run identities", contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name)
check("closure clean", closure["error"] is None and outcome["error"] is None)
check("invocation SHA", closure["invocation_sha256"] == sha(RUN / "invocation.json"))
check("SSH session zero", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"])
check("global native mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("protected GUI identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]))
check("twelve ordered steps", [step["name"] for step in steps] == [f"{arm}_{stage}" for arm in ARMS for stage in ("import", "export", "calc", "report")])
for step in steps:
    check(f"step successful and GUI preserved {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True and step["error"] is None)

parent = CASES / "C03-shared-crew-formation-v1.0.2"
c08 = CASES / "C08-shift-maxut-v1.0.0"
source_paths = {
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "parent_input": parent / "inputs" / "staffing-2.json",
    "parent_evidence": parent / "evidence-2026-09-29.md",
    "c08_input": c08 / "maxut-one-input.json",
    "c08_signoff": c08 / "cli-scope-signoff-2026-09-30.md",
    "control": CASE / "control-input.json",
    "out": CASE / "out-input.json",
    "out_in": CASE / "out_in-input.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "runner": CASE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check("source key set", set(source_paths) == set(closure["source_hashes_before"]))
for name, before in closure["source_hashes_before"].items():
    check(f"source stable {name}", before == closure["source_hashes_after"][name] == invocation["source_hashes_before"][name])
    check(f"source SHA {name}", source_paths[name].is_file() and sha(source_paths[name]) == before)
for name, expected in (("parent_input", contract["dependency"]["input_sha256"]), ("parent_evidence", contract["dependency"]["evidence_sha256"]), ("c08_input", contract["prerequisite"]["input_sha256"]), ("c08_signoff", contract["prerequisite"]["signoff_sha256"]), ("builder", contract["builder_sha256"]), ("manual", contract["manual"]["sha256"]), ("dictionary", contract["manual"]["dictionary_sha256"])):
    check(f"contract source pin {name}", expected == closure["source_hashes_before"][name])
check("32 raw seals", len(closure["raw"]) == 32)
for name, seal in closure["raw"].items():
    path = RUN / name
    check(f"raw exists {name}", path.is_file())
    if path.is_file():
        check(f"raw size {name}", path.stat().st_size == seal["bytes"])
        check(f"raw SHA {name}", sha(path) == seal["sha256"])

models = {arm: tables(load(CASE / f"{arm}-input.json"), "model") for arm in ARMS}
parent_model = tables(load(source_paths["parent_input"]), "model")
check("32 tables and 21 populated per arm", all(len(model) == 32 and sum(bool(rows(t)) for t in model.values()) == 21 for model in models.values()))
for arm in ARMS:
    model = models[arm]
    check(f"parent-derived fixed tables {arm}", {name for name in parent_model if parent_model[name] != model[name]} == {"ProblemDescription", "OperationProfile"} and set(model) - set(parent_model) == {"ResourceTransfer"})
    check(f"two formation schedule rows {arm}", [r["STIM"] for r in rows(model["OperationProfile"])] == [8, 20])
    check(f"input contract pin {arm}", sha(CASE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == closure["source_hashes_before"][arm])
    check(f"run-local input copy {arm}", sha(RUN / f"{arm}-input.json") == contract["inputs_sha256"][arm])
check("paired source changes only description and transfer", all({name for name in models["control"] if models["control"][name] != models[arm][name]} == {"ProblemDescription", "ResourceTransfer"} for arm in ("out", "out_in")))
rt = {arm: rows(models[arm]["ResourceTransfer"]) for arm in ARMS}
check("control null placeholder", len(rt["control"]) == 1 and all(value is None for value in rt["control"][0].values()))
check("OUT row", rt["out"] == [{"STFID": "BASE-01", "STTID": "<OUTSIDE>", "RID": "P-CREW", "TFTIME": 7.75, "TFQTY": 1, "TFDT": 0.0, "NOTE": None}])
check("OUT+IN rows", rt["out_in"] == rt["out"] + [{"STFID": "<OUTSIDE>", "STTID": "BASE-01", "RID": "P-CREW", "TFTIME": 10.0, "TFQTY": 1, "TFDT": 0.5, "NOTE": None}])

observed = {}
for arm in ARMS:
    model = models[arm]
    exported = tables(load(RUN / f"{arm}-roundtrip-raw.json"), "model")
    for name, table in model.items():
        original = rows(table)
        if not original:
            continue
        check(f"roundtrip table exists {arm}/{name}", name in exported)
        if name not in exported:
            continue
        native = exported[name]
        check(f"roundtrip exact authored columns {arm}/{name}", [(c["name"], c["datatype"]) for c in table["columns"]] == [(c["name"], c["datatype"]) for c in native["columns"]])
        returned = rows(native)
        check(f"roundtrip row count {arm}/{name}", len(original) == len(returned))
        for i, (a, b) in enumerate(zip(original, returned)):
            for field, value in a.items():
                if value is not None:
                    check(f"roundtrip cell {arm}/{name}/{i}/{field}", b.get(field) == value)
    check(f"null placeholder survives export {arm}", arm != "control" or rows(exported["ResourceTransfer"]) == rt["control"])
    converter = (RUN / f"{arm}-run.log").read_text(encoding="latin-1")
    check(f"converter zero error {arm}", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter)
    check(f"only warning 108/126 {arm}", re.findall(r"\(warning #(\d+)\)", converter) == ["108", "126"])
    check(f"outcome complete {arm}", outcome["arms"][arm] == "completed" and outcome["converter_summaries"][arm] == [0, 2, 0] and outcome["warning_codes"][arm] == ["108", "126"])
    check(f"usable SXO {arm}", (RUN / f"{arm}.sxo").stat().st_size > 100000)
    log = (RUN / f"{arm}.log").read_text(encoding="latin-1")
    mission_starts = [float(t) for t in re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission starting", log)]
    mission_successes = [float(t) for t in re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission success:", log)]
    check(f"first formation starts and succeeds {arm}", mission_starts[0] == 8 and mission_successes[0] == 9)
    check(f"second formation timing {arm}", mission_starts[1] == (20.5 if arm == "out" else 20) and mission_successes[1] == (21.5 if arm == "out" else 21))
    check(f"two formation missions no abort {arm}", len(mission_starts) == len(mission_successes) == 2 and "mission aborted:" not in log and "mission cancelled:" not in log)
    prep_starts = [(float(t), int(id)) for t, id in re.findall(r"Time: ([\d.]+)  system preparation task (\d+) on <TEACH-AIR-01,\d+> started", log)]
    prep_done = [(float(t), int(id)) for t, id in re.findall(r"Time: ([\d.]+)  system preparation task (\d+) on <TEACH-AIR-01,\d+> completed", log)]
    check(f"four preparation tasks {arm}", len(prep_starts) == len(prep_done) == 4)
    check(f"first prep parallel {arm}", prep_starts[:2] == [(7.5, 0), (7.5, 1)] and prep_done[:2] == [(8, 0), (8, 1)])
    check(f"second prep concurrency {arm}", prep_starts[2:] == [(19.5, 2), (19.5, 3)] and prep_done[2:] == ([(20, 2), (20.5, 3)] if arm == "out" else [(20, 2), (20, 3)]))
    if arm != "control":
        check(f"busy crew transfer backorder {arm}", "Time: 7.75  <P-CREW at <BASE-01,0>> Resource transfer backorder added" in log and "Time: 8  <P-CREW at <BASE-01,0>> Resource transfer backorder removed" in log)
        check(f"OUT zero then one crew {arm}", "Time: 7.75  resource transfer task 0 (OUT)  starts with 0 resources" in log and "Time: 8  resource transfer task 1 (OUT)  arrives with 1 resources" in log)
    else:
        check("control no transfer events", "resource transfer task" not in log)
    if arm == "out_in":
        check("IN h10 departure h10.5 arrival", "Time: 10  resource transfer task 2 (IN)  starts with 1 resources, transfer time: 0.5" in log and "Time: 10.5  resource transfer task 2 (IN)  arrives with 1 resources" in log and "Time: 10.5  <P-CREW at <BASE-01,0>> transfer arrives: 1" in log)
    else:
        check(f"no IN transfer {arm}", "(IN)" not in log)
    rtables = tables(native_report(RUN / f"{arm}-report-raw.json"), "report")
    check(f"six report tables {arm}", set(rtables) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"})
    system, stock, resource = (rows(rtables[name]) for name in ("SystemResults", "StockTotalResults", "ResourceResults"))
    check(f"72 half-hour report bins {arm}", all(len(group) == 72 and all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(group)) for group in (system, stock, resource)))
    by_time = {row["STINT"]: row for row in resource}
    expected_crew = {7.5: 2, 8: 2 if arm == "control" else 1, 10: 2 if arm == "control" else 1, 10.5: 1 if arm == "out" else 2, 19.5: 1 if arm == "out" else 2, 20: 1 if arm == "out" else 2, 35.5: 1 if arm == "out" else 2}
    check(f"resource roster bins {arm}", all(by_time[t]["NR"] == n for t, n in expected_crew.items()))
    check(f"first prep utilization two crews {arm}", by_time[7.5]["NRUM"] == 2)
    check(f"second prep utilization and wait {arm}", by_time[19.5]["NRUM"] == (1 if arm == "out" else 2) and by_time[19.5]["NRW"] == (1 if arm == "out" else 0) and by_time[20]["NRUM"] == (1 if arm == "out" else 0))
    check(f"resource total work two crew-hours {arm}", abs(sum((row["NRUM"] or 0) * 0.5 for row in resource) - 2) < 1e-6)
    check(f"resource conservation bounds {arm}", all(0 <= (row["NRUM"] or 0) <= row["NR"] <= 2 for row in resource))
    resource_total = rows(rtables["ResourceResultsTotal"])
    check(f"resource total report one row {arm}", len(resource_total) == 1)
    if len(resource_total) == 1:
        for field in ("NR", "NRUM", "NRW"):
            check(f"resource total {field} reconciles bins {arm}", abs(resource_total[0][field] - sum((row[field] or 0) for row in resource) / len(resource)) < 1e-6)
    check(f"no stock demand or backorder {arm}", all(all((row[field] or 0) == 0 for field in ("NBO", "NBOU", "NDF", "NDD", "NDR")) for row in stock))
    check(f"mission summary and terminal two ready {arm}", len(rows(rtables["ResultSummary"])) == 1 and rows(rtables["ResultSummary"])[0]["MSUF"] == 1 and system[-1]["NSYRY"] == 2)
    check(f"zero system failures {arm}", sum(row["NFAIL"] or 0 for row in system) == 0)
    observed[arm] = {"mission_starts": mission_starts, "mission_successes": mission_successes, "preparation_completions": prep_done, "resource_roster_19_5": by_time[19.5]["NR"], "resource_use_19_5": by_time[19.5]["NRUM"], "resource_wait_19_5": by_time[19.5]["NRW"], "resource_work_hours": sum((row["NRUM"] or 0) * 0.5 for row in resource), "terminal_ready": system[-1]["NSYRY"]}

failed = [label for label, passed in CHECKS if not passed]
verdict = {"schema": "simlox-i03-var01-independent-replay/v1", "run_id": RUN.name, "verdict": "GO_BOUNDED" if not failed else "NO_GO", "checks": len(CHECKS), "passed": len(CHECKS) - len(failed), "failed": failed, "observed": observed, "limits": "One fixed seed, one base, two aircraft, and P-CREW only. Transfer is an OUT backorder until first preparation releases a busy crew, followed by a scheduled IN in one arm; no equipment or BETWEEN transfer and no general policy claim."}
(CASE / "review" / "independent-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in verdict.items() if k != "observed"}, indent=2))
if failed:
    raise SystemExit(1)

"""Independent read-only replay of the sealed I05.var06 preparation change pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "i05-var06-prep-change-v100-ssh-20261005-01"
ARMS = ("control", "change")
CHECKS: list[tuple[str, bool]] = []


def check(label: str, result: bool) -> None:
    CHECKS.append((label, bool(result)))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: Path) -> dict:
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(doc: dict, root: str) -> dict:
    return {t["name"]: t for t in doc[root]["tables"]}


def rows(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


contract = load(CASE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check("run identity", contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name)
check("clean closure", closure["error"] is None and outcome["error"] is None)
check("invocation SHA", closure["invocation_sha256"] == sha(RUN / "invocation.json"))
check("SSH session zero", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"])
check("global host mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("protected GUI identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]))
check("eight ordered native steps", [s["name"] for s in steps] == [f"{a}_{stage}" for a in ARMS for stage in ("import", "export", "calc", "report")])
for step in steps:
    check(f"step success and GUI preserved {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True and step["error"] is None)

parent = CASES / "B01-fixed-preparation-v1.0.1"
sources = {
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "parent_input": parent / "native-input.json",
    "parent_evidence": parent / "evidence-2026-09-29.md",
    "control": CASE / "control-input.json",
    "change": CASE / "change-input.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "runner": CASE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check("source set complete", set(sources) == set(closure["source_hashes_before"]))
for name, before in closure["source_hashes_before"].items():
    check(f"source stable {name}", before == closure["source_hashes_after"][name] == invocation["source_hashes_before"][name])
    check(f"source SHA {name}", sources[name].is_file() and sha(sources[name]) == before)
for name, expected in (("parent_input", contract["dependency"]["input_sha256"]), ("parent_evidence", contract["dependency"]["evidence_sha256"]), ("builder", contract["builder_sha256"]), ("manual", contract["manual"]["sha256"]), ("dictionary", contract["manual"]["dictionary_sha256"])):
    check(f"contract source pin {name}", expected == closure["source_hashes_before"][name])
check("22 raw seals", len(closure["raw"]) == 22)
for name, seal in closure["raw"].items():
    path = RUN / name
    check(f"raw exists {name}", path.is_file())
    if path.is_file():
        check(f"raw bytes {name}", path.stat().st_size == seal["bytes"])
        check(f"raw SHA {name}", sha(path) == seal["sha256"])

models = {a: tables(load(CASE / f"{a}-input.json"), "model") for a in ARMS}
parent_model = tables(load(sources["parent_input"]), "model")
check("32 tables and 16 populated per arm", all(len(t) == 32 and sum(bool(rows(x)) for x in t.values()) == 16 for t in models.values()))
for arm, model in models.items():
    check(f"B01 derivation {arm}", {name for name in parent_model if parent_model[name] != model[name]} == {"ProblemDescription", "MissionType", "OperationProfile", "MissionPreparation", "Tasks"} and set(model) - set(parent_model) == {"ChangesMissionPreparation"})
    check(f"mission schedule h13/h24 {arm}", [r["STIM"] for r in rows(model["OperationProfile"])] == [13, 24])
    check(f"initial four-hour prep and notice {arm}", rows(model["MissionPreparation"])[0]["DURN"] == 4 and rows(model["MissionType"])[0]["NOPER"] == 4)
    check(f"input source pin {arm}", sha(CASE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == closure["source_hashes_before"][arm])
    check(f"run-local input copy {arm}", sha(RUN / f"{arm}-input.json") == contract["inputs_sha256"][arm])
check("pair differs only change row and description", {name for name in models["control"] if models["control"][name] != models["change"][name]} == {"ChangesMissionPreparation", "ProblemDescription"})
control_change = rows(models["control"]["ChangesMissionPreparation"])
active_change = rows(models["change"]["ChangesMissionPreparation"])
check("control null placeholder", len(control_change) == 1 and all(value is None for value in control_change[0].values()))
check("source-frozen TIMEC10 DURN1 and null DURND", active_change == [{"MTID": "BASIC-MISSION", "SID": "TEACH-AIR-01", "STID": "BASE-01", "TIMEC": 10, "DURN": 1, "DURND": None, "NOTE": None}])

observed = {}
for arm, model in models.items():
    exported = tables(load(RUN / f"{arm}-roundtrip-raw.json"), "model")
    for name, authored in model.items():
        original = rows(authored)
        if not original:
            continue
        check(f"roundtrip table {arm}/{name}", name in exported)
        if name not in exported:
            continue
        native = exported[name]
        check(f"roundtrip exact columns {arm}/{name}", [(c["name"], c["datatype"]) for c in authored["columns"]] == [(c["name"], c["datatype"]) for c in native["columns"]])
        returned = rows(native)
        check(f"roundtrip row count {arm}/{name}", len(original) == len(returned))
        for i, (a, b) in enumerate(zip(original, returned)):
            for field, value in a.items():
                if value is not None:
                    check(f"roundtrip cell {arm}/{name}/{i}/{field}", b.get(field) == value)
    check(f"change table null fields and placeholder {arm}", rows(exported["ChangesMissionPreparation"]) == (control_change if arm == "control" else active_change))
    converter = (RUN / f"{arm}-run.log").read_text(encoding="latin-1")
    check(f"converter zero error {arm}", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter)
    check(f"only warnings 108/126 {arm}", re.findall(r"\(warning #(\d+)\)", converter) == ["108", "126"])
    check(f"outcome complete {arm}", outcome["arms"][arm] == "completed" and outcome["converter_summaries"][arm] == [0, 2, 0] and outcome["warning_codes"][arm] == ["108", "126"])
    check(f"usable SXO {arm}", (RUN / f"{arm}.sxo").stat().st_size > 100000)
    log = (RUN / f"{arm}.log").read_text(encoding="latin-1")
    prep_start = [float(t) for t in re.findall(r"Time: ([\d.]+) <TEACH-AIR-01,0> preparation started, mission:", log)]
    prep_end = [float(t) for t in re.findall(r"Time: ([\d.]+) <TEACH-AIR-01,0> preparation ended, mission:", log)]
    planned = [float(t) for t in re.findall(r"system preparation task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for ([\d.]+) hours", log)]
    check(f"first in-progress preparation retains 4h {arm}", prep_start[0] == 9 and prep_end[0] == 13 and planned[0] == 4 and "Time: 10  subtask 0 seqno 0 within system preparation task 0 on <TEACH-AIR-01,0> completed" not in log)
    check(f"second preparation duration {arm}", prep_start[1] == 20 and prep_end[1] == (24 if arm == "control" else 21) and planned[1] == (4 if arm == "control" else 1))
    launches = [float(t) for t in re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission starting", log)]
    successes = [float(t) for t in re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission success:", log)]
    check(f"two launch/completion times {arm}", launches == [13, 24] and successes == [15, 26])
    check(f"no abort/cancellation {arm}", "mission aborted:" not in log and "mission cancelled:" not in log)
    rt = tables(report(RUN / f"{arm}-report-raw.json"), "report")
    check(f"four report tables {arm}", set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    system, stock = rows(rt["SystemResults"]), rows(rt["StockTotalResults"])
    check(f"72 half-hour system/stock bins {arm}", all(len(group) == 72 and all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(group)) for group in (system, stock)))
    by_time = {r["STINT"]: r for r in system}
    prep_intervals = [(9, 13), (20, 24 if arm == "control" else 21)]
    check(f"NSYMP exact prep intervals {arm}", all(by_time[i / 2]["NSYMP"] == (1 if any(start <= i / 2 < end for start, end in prep_intervals) else 0) for i in range(72)))
    check(f"prep occupied hours {arm}", sum((r["NSYMP"] or 0) * 0.5 for r in system) == (8 if arm == "control" else 5))
    check(f"mission summary success {arm}", len(rows(rt["ResultSummary"])) == 1 and rows(rt["ResultSummary"])[0]["MSUF"] == 1)
    check(f"terminal ready and no failure {arm}", system[-1]["NSYRY"] == 1 and sum(r["NFAIL"] or 0 for r in system) == 0)
    check(f"no stock demand/backorder {arm}", all(all((r[field] or 0) == 0 for field in ("NBO", "NBOU", "NDF", "NDD", "NDR")) for r in stock))
    observed[arm] = {"prep_start": prep_start, "prep_end": prep_end, "planned_hours": planned, "mission_start": launches, "mission_success": successes, "reported_prep_hours": sum((r["NSYMP"] or 0) * 0.5 for r in system), "terminal_ready": system[-1]["NSYRY"]}

failed = [label for label, result in CHECKS if not result]
verdict = {"schema": "simlox-i05-var06-independent-replay/v1", "run_id": RUN.name, "verdict": "GO_BOUNDED" if not failed else "NO_GO", "checks": len(CHECKS), "passed": len(CHECKS) - len(failed), "failed": failed, "observed": observed, "limits": "One fixed seed, one existing preparation record, DURN only. TIMEC10 is established by frozen source; the native log records task durations but does not print a distinct change-application message. No DURND, same-time tie, queued task, GUI or general I05 claim."}
(CASE / "review" / "independent-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in verdict.items() if k != "observed"}, indent=2))
if failed:
    raise SystemExit(1)

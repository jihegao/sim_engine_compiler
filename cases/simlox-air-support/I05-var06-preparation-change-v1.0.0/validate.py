"""Read-only author replay of the frozen I05 preparation-change evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/i05-var06-prep-change-v100-ssh-20261005-01"
ARMS = ("control", "change")
FAILED: list[str] = []
CHECKS = 0


def check(ok: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILED.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    marker = ",\n      ]"
    check(raw.count(marker) == 1, f"{path.name} one native trailing comma")
    return json.loads(raw.replace(marker, "\n      ]"))


def populated(doc: dict) -> dict:
    return {
        t["name"]: {"columns": [(c["name"], c["datatype"]) for c in t["columns"]],
                    "rows": [r for i in t["instances"] for r in i["rows"]]}
        for t in doc["model"]["tables"] if any(i["rows"] for i in t["instances"])
    }


def rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for i in table["instances"] for row in i["rows"]]


contract = load(HERE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check((contract["case_id"], contract["variant_id"], contract["version"]) == ("I05", "I05.var06", "1.0.0-candidate"), "contract identity")
check(contract["run_id"] == RUN.name == closure["run_id"] == invocation["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stability")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
paths = {
    "contract": HERE / "contract.json", "builder": HERE / "build.py",
    "parent_input": ROOT / "B01-fixed-preparation-v1.0.1/native-input.json",
    "parent_evidence": ROOT / "B01-fixed-preparation-v1.0.1/evidence-2026-09-29.md",
    **{arm: HERE / f"{arm}-input.json" for arm in ARMS},
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "runner": HERE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check(set(paths) == set(closure["source_hashes_before"]), "source inventory")
for key, path in paths.items():
    check(path.is_file() and sha(path) == closure["source_hashes_before"][key], f"source seal {key}")
check(sha(paths["parent_input"]) == contract["dependency"]["input_sha256"], "B01 input pin")
check(sha(paths["parent_evidence"]) == contract["dependency"]["evidence_sha256"], "B01 evidence pin")
check(sha(paths["builder"]) == contract["builder_sha256"], "builder contract pin")
check(len(closure["raw"]) == 22, "22 raw seals")
for name, seal in closure["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw seal {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-0 SSH")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI")
check([s["name"] for s in steps] == [f"{arm}_{part}" for arm in ARMS for part in ("import", "export", "calc", "report")], "eight serial steps")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"step {step['name']}")

observed = {}
for arm in ARMS:
    check(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == sha(RUN / f"{arm}-input.json"), f"{arm} frozen input")
    authored = populated(load(HERE / f"{arm}-input.json"))
    exported = populated(load(RUN / f"{arm}-roundtrip-raw.json"))
    check(len(authored) == 16 and all(exported.get(k) == v for k, v in authored.items()), f"{arm} 16 row-containing table roundtrip")
    check(outcome["arms"][arm] == "completed" and outcome["converter_summaries"][arm] == [0, 2, 0] and outcome["warning_codes"][arm] == ["108", "126"], f"{arm} converter")
    check((RUN / f"{arm}.sxo").stat().st_size > 1000, f"{arm} SXO")
    log = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig")
    rep = report(RUN / f"{arm}-report-raw.json")
    system = rows(rep, "SystemResults")
    stock = rows(rep, "StockTotalResults")
    for name, series in (("SystemResults", system), ("StockTotalResults", stock)):
        check(len(series) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(series)), f"{arm} {name} bins")
    check(rows(rep, "ResultSummary")[0]["NREP"] == 1, f"{arm} one repetition")
    check(all(r["NFAIL"] == r["NDAM"] == 0 for r in system), f"{arm} no failure/damage")
    check(all(abs(r["NSYA"] - 1) < 1e-6 for r in system[-4:]), f"{arm} terminal one ready system")
    for seq, start, prep_end, launch, finish, duration in (
        (0, 9, 13, 13, 15, 4),
        (1, 20, 24 if arm == "control" else 21, 24, 26, 4 if arm == "control" else 1),
    ):
        token = f"<BASIC-MISSION,TEACH-UNIT,0,0,{seq}>"
        check(f"Time: {start} <TEACH-AIR-01,0> preparation started, mission: {token}" in log, f"{arm} prep {seq} starts")
        check(f"Time: {start}  subtask {seq} seqno 0 within system preparation task {seq} on <TEACH-AIR-01,0> starts performing, planned to last for {duration} hours" in log, f"{arm} prep {seq} duration")
        check(f"Time: {prep_end} <TEACH-AIR-01,0> preparation ended, mission: {token}" in log, f"{arm} prep {seq} ends")
        check(f"Time: {launch} {token} mission starting, duration: 2 : <TEACH-AIR-01,0>" in log, f"{arm} mission {seq} launch")
        check(f"Time: {finish} {token} mission completed: <TEACH-AIR-01,0>" in log and f"Time: {finish} {token} mission success" in log, f"{arm} mission {seq} success")
    prep_bins = [r["STINT"] for r in system if r["NSYMP"] > 0]
    expected_bins = [x / 2 for x in range(18, 26)] + [x / 2 for x in range(40, 48 if arm == "control" else 42)]
    check(prep_bins == expected_bins, f"{arm} preparation half-hour bins")
    check(abs(sum(r["NSYMP"] * 0.5 for r in system) - (8 if arm == "control" else 5)) < 1e-6, f"{arm} preparation aircraft-hours")
    check(abs(sum(r["NSYMO"] * 0.5 for r in system) - 4) < 1e-6, f"{arm} four mission aircraft-hours")
    check(sum(r["STACC"] for r in system) == 8, f"{arm} eight aircraft half-hour accepted intervals")
    observed[arm] = {"first_preparation": [9, 13],
                     "second_preparation": [20, 24 if arm == "control" else 21],
                     "mission_launches": [13, 24],
                     "preparation_aircraft_hours": 8 if arm == "control" else 5}

check(observed["control"]["first_preparation"] == observed["change"]["first_preparation"], "running task retained initial duration")
check(observed["control"]["second_preparation"][1] - observed["change"]["second_preparation"][1] == 3, "later task saves three hours")
verdict = {"schema": "simlox-i05-var06-author-replay/v1", "run_id": RUN.name,
           "closure_sha256": sha(RUN / "closure.json"), "passed": not FAILED,
           "checks": CHECKS, "checks_passed": CHECKS - len(FAILED), "failures": FAILED,
           "observed": observed,
           "limits": "One fixed seed, DURN change on one existing MissionPreparation record, two separated notices. No distributions, subtasks, tie-time change, other Changes tables, GUI or general I05 claim."}
dest = HERE / "review/author-validation-2026-10-05.json"
dest.parent.mkdir(exist_ok=True)
dest.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'} {verdict['checks_passed']}/{CHECKS}")
for failure in FAILED:
    print(failure)
raise SystemExit(0 if verdict["passed"] else 1)

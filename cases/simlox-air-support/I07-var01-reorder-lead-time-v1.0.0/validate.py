"""Read-only author replay of the frozen I07 lead-time evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/i07-var01-reorder-leadt-v100-ssh-20261005-01"
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


def populated(doc: dict) -> dict:
    return {
        t["name"]: {"columns": [(c["name"], c["datatype"]) for c in t["columns"]],
                    "rows": [row for inst in t["instances"] for row in inst["rows"]]}
        for t in doc["model"]["tables"] if any(inst["rows"] for inst in t["instances"])
    }


def rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


contract = load(HERE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check((contract["case_id"], contract["variant_id"], contract["version"]) == ("I07", "I07.var01", "1.0.0-candidate"), "contract identity")
check(contract["run_id"] == RUN.name == closure["run_id"] == invocation["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "stable source")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
parent = ROOT / "E15-var07-explicit-istoh-v1.0.1"
paths = {
    "contract": HERE / "contract.json", "builder": HERE / "build.py",
    "parent_input": parent / "native-input-explicit-three.json",
    "parent_signoff": parent / "cli-scope-signoff-2026-10-02.md",
    "settings_builder": parent / "make_report_settings.py",
    "default_settings": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
    "selector": parent / "runs/report-settings/item-position-results.sxs",
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
check(sha(paths["parent_input"]) == contract["dependency"]["input_sha256"], "E15 input pin")
check(sha(paths["parent_signoff"]) == contract["dependency"]["signoff_sha256"], "E15 signoff pin")
check(sha(paths["builder"]) == contract["builder_sha256"], "builder contract pin")
check(sha(paths["selector"]) == contract["report_selector"]["selector_sha256"], "selected report pin")
check(len(closure["raw"]) == 22, "22 raw seals")
for name, seal in closure["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw seal {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-0 SSH")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI")
check([step["name"] for step in steps] == [f"{arm}_{part}" for arm in ARMS for part in ("import", "export", "calc", "report")], "eight serial steps")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"step {step['name']}")

observed = {}
for arm in ARMS:
    check(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == sha(RUN / f"{arm}-input.json"), f"{arm} input pin")
    authored = populated(load(HERE / f"{arm}-input.json"))
    exported = populated(load(RUN / f"{arm}-roundtrip-raw.json"))
    check(len(authored) == 22 and all(exported.get(name) == table for name, table in authored.items()), f"{arm} 22 populated tables exactly roundtrip")
    check(outcome["arms"][arm] == "completed" and outcome["converter_summaries"][arm] == [0, 1, 0] and outcome["warning_codes"][arm] == ["108"], f"{arm} converter")
    check((RUN / f"{arm}.sxo").stat().st_size > 1000, f"{arm} SXO")
    log = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig")
    report = load(RUN / f"{arm}-report-raw.json")
    item = rows(report, "ItemResults")
    check(len(item) == 72 and all((r["IID"], r["STID"], r["STINT"], r["ETINT"]) == ("TEACH-DU-01", "DEPOT-01", i / 2, (i + 1) / 2) for i, r in enumerate(item)), f"{arm} selected half-hour bins")
    summary = rows(report, "ResultSummary")
    check(len(summary) == 1 and summary[0]["NREP"] == 1 and abs(summary[0]["MSUF"] - 2 / 3) < 1e-6, f"{arm} mission summary")
    duration, arrival = (1, 11) if arm == "control" else (3, 13)
    check(f"Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: {duration}" in log, f"{arm} h10 reorder duration")
    check(f"Time: {arrival} <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was {duration}" in log, f"{arm} reorder completion")
    check(f"Time: {arrival} <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives" in log, f"{arm} two-unit delivery")
    check(log.count("reorder task 0 started") == log.count("Delivery with 2 item(s) arrives") == 1, f"{arm} sole order")
    check(len([r for r in item if r["NRO"] == 1]) == 1 and item[20]["NRO"] == 1, f"{arm} report sole reorder")
    check([r["STOHA"] for r in item[:20]] == [3] * 20, f"{arm} initial on hand")
    check([r["STOHA"] for r in item[20:2 * arrival]] == [2] * (2 * arrival - 20), f"{arm} pending on hand")
    check([r["STOHA"] for r in item[2 * arrival:]] == [4] * (72 - 2 * arrival), f"{arm} after delivery on hand")
    check("Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted" in log, f"{arm} first mission abort")
    for seq, start, end in ((1, 20, 22), (2, 32, 34)):
        token = f"<BASIC-MISSION,TEACH-UNIT,0,0,{seq}>"
        check(f"Time: {start} {token} mission starting" in log and f"Time: {end} {token} mission success" in log, f"{arm} later mission {seq} success")
    observed[arm] = {"order_started_hour": 10, "order_duration_hours": duration,
                     "delivery_hour": arrival, "delivered_quantity": 2,
                     "depot_on_hand_two_hours": arrival - 10,
                     "later_successful_missions": [20, 32]}

check(observed["change"]["delivery_hour"] - observed["control"]["delivery_hour"] == 2, "two-hour delivery contrast")
verdict = {"schema": "simlox-i07-var01-author-replay/v1", "run_id": RUN.name,
           "closure_sha256": sha(RUN / "closure.json"), "passed": not FAILED,
           "checks": CHECKS, "checks_passed": CHECKS - len(FAILED), "failures": FAILED,
           "observed": observed,
           "limits": "One seed, one existing ItemReorder, LEADT only, h5 change before h10 stock-based reorder. No outstanding-order, interval, tie-time, other Changes tables, GUI or general I07 claim."}
dest = HERE / "review/author-validation-2026-10-05.json"
dest.parent.mkdir(exist_ok=True)
dest.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'} {verdict['checks_passed']}/{CHECKS}")
for failure in FAILED:
    print(failure)
raise SystemExit(0 if verdict["passed"] else 1)

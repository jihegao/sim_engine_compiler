"""Read-only author replay of the frozen I04 system BETWEEN evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/i04-var01-system-between-v100-ssh-20261005-01"
ARMS = ("control", "between")
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
check((contract["case_id"], contract["variant_id"], contract["version"]) == ("I04", "I04.var01", "1.0.0-candidate"), "contract identity")
check(contract["run_id"] == RUN.name == closure["run_id"] == invocation["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stability")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
paths = {
    "contract": HERE / "contract.json", "builder": HERE / "build.py",
    "parent_input": ROOT / "A17-multi-unit-group-v1.0.0/native-input.json",
    "parent_signoff": ROOT / "A17-multi-unit-group-v1.0.0/cli-scope-signoff-2026-09-29.md",
    "a02_input": ROOT / "A02-single-aircraft-repeated-missions/native-input.json",
    "a02_signoff": ROOT / "A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md",
    "d03_input": ROOT / "D03-calendar-pm-v1.0.0/native-input.json",
    "d03_signoff": ROOT / "D03-calendar-pm-v1.0.0/cli-scope-signoff-2026-09-30.md",
    "d09_input": ROOT / "D09-var01-calendar-vs-operational-v1.0.0/native-input-calendar.json",
    "d09_signoff": ROOT / "D09-var01-calendar-vs-operational-v1.0.0/cli-scope-signoff-2026-10-02.md",
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
check(sha(paths["parent_input"]) == contract["dependency"]["input_sha256"], "A17 input pin")
check(sha(paths["parent_signoff"]) == contract["dependency"]["signoff_sha256"], "A17 signoff pin")
for key in ("a02_input", "a02_signoff", "d03_input", "d03_signoff", "d09_input", "d09_signoff"):
    field = key[:3].upper() + key[3:] + "_sha256"
    check(sha(paths[key]) == contract["instructional_prerequisites"][field], f"{key} prerequisite pin")
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
    check(all(abs(r["NSYA"] - 2) < 1e-6 for r in system[-4:]), f"{arm} terminal two systems")
    for seq, start, end in ((0, 8, 10), (1, 20, 22)):
        pattern = rf"Time: {start} <BASIC-MISSION,TEACH-GROUP,0,0,{seq}> mission starting, duration: 2 : (.*)"
        launch = re.findall(pattern, log)
        finish = re.findall(rf"Time: {end} <BASIC-MISSION,TEACH-GROUP,0,0,{seq}> mission completed: (.*)", log)
        for label, match in (("start", launch), ("finish", finish)):
            check(len(match) == 1 and sorted(re.findall(r"<TEACH-AIR-01,[01]>", match[0])) == ["<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>"], f"{arm} wave {seq} {label} identities")
        check(f"Time: {end} <BASIC-MISSION,TEACH-GROUP,0,0,{seq}> mission success" in log, f"{arm} wave {seq} success")
    if arm == "control":
        check("system transfered out" not in log and "system transfered in" not in log, "control no physical transfer")
        check(system[20]["NSYA"] == system[21]["NSYA"] == 2, "control two systems h10-11")
    else:
        departure = "Time: 10 <TEACH-UNIT at <BASE-01,0>> system transfered out: <TEACH-AIR-01,0>."
        arrival = "Time: 10.5 <TEACH-UNIT-2 at <BASE-02,0>> system transfered in: <TEACH-AIR-01,0>."
        check(log.count(departure) == 1 and log.count(arrival) == 1, "one stable identity BETWEEN h10 to h10.5")
        check("Time: 10 <TEACH-AIR-01,0> nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>" in log, "source roster decrements")
        check("Time: 10.5 <TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT-2 at <BASE-02,0>>" in log, "target roster increments")
        check("Time: 10.5 <TEACH-UNIT-2 at <BASE-02,0>> systems ready: 2 :<TEACH-AIR-01,1>,<TEACH-AIR-01,0>" in log, "target two distinct ready IDs")
        check(system[20]["NSYA"] == 1 and system[21]["NSYA"] == 2, "one system absent during half-hour transit")
        check("mission allocates system: <TEACH-AIR-01,0>" in log, "transferred system assigned after arrival")
    check(sum(r["STACC"] for r in system) == 16, f"{arm} sixteen aircraft half-hour accepted intervals")
    observed[arm] = {"first_launch_hour": 8, "second_launch_hour": 20,
                     "systems_in_report_h10_to_10_5": system[20]["NSYA"]}

verdict = {"schema": "simlox-i04-var01-author-replay/v1", "run_id": RUN.name,
           "closure_sha256": sha(RUN / "closure.json"), "passed": not FAILED,
           "checks": CHECKS, "checks_passed": CHECKS - len(FAILED), "failures": FAILED,
           "observed": observed,
           "limits": "One fixed-seed BETWEEN transfer of one system type between two explicit units. No IN/OUT, PM identity state, resource priority, GUI or general I04 claim."}
dest = HERE / "review/author-validation-2026-10-05.json"
dest.parent.mkdir(exist_ok=True)
dest.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'} {verdict['checks_passed']}/{CHECKS}")
for failure in FAILED:
    print(failure)
raise SystemExit(0 if verdict["passed"] else 1)

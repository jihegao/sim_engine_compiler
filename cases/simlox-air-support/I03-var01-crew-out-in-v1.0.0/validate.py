"""Read-only author replay of the frozen I03 crew transfer evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/i03-var01-crew-transfer-v100-ssh-20261005-01"
ARMS = ("control", "out", "out_in")
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
    result = {}
    for table in doc["model"]["tables"]:
        rs = [row for instance in table["instances"] for row in instance["rows"]]
        if rs:
            result[table["name"]] = {
                "columns": [(col["name"], col["datatype"]) for col in table["columns"]],
                "rows": rs,
            }
    return result


def rows(doc: dict, name: str) -> list[dict]:
    table = next(table for table in doc["report"]["tables"] if table["name"] == name)
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


contract = load(HERE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check((contract["case_id"], contract["variant_id"], contract["version"]) == ("I03", "I03.var01", "1.0.0-candidate"), "contract identity")
check(contract["run_id"] == RUN.name == closure["run_id"] == invocation["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stability")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
source_paths = {
    "contract": HERE / "contract.json", "builder": HERE / "build.py",
    "parent_input": ROOT / "C03-shared-crew-formation-v1.0.2/inputs/staffing-2.json",
    "parent_evidence": ROOT / "C03-shared-crew-formation-v1.0.2/evidence-2026-09-29.md",
    "c08_input": ROOT / "C08-shift-maxut-v1.0.0/maxut-one-input.json",
    "c08_signoff": ROOT / "C08-shift-maxut-v1.0.0/cli-scope-signoff-2026-09-30.md",
    **{arm: HERE / f"{arm}-input.json" for arm in ARMS},
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "runner": HERE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check(set(source_paths) == set(closure["source_hashes_before"]), "source inventory")
for key, path in source_paths.items():
    check(path.is_file() and sha(path) == closure["source_hashes_before"][key], f"source seal {key}")
check(sha(source_paths["parent_input"]) == contract["dependency"]["input_sha256"], "C03 parent input pin")
check(sha(source_paths["parent_evidence"]) == contract["dependency"]["evidence_sha256"], "C03 parent evidence pin")
check(sha(source_paths["c08_input"]) == contract["prerequisite"]["input_sha256"], "C08 input pin")
check(sha(source_paths["c08_signoff"]) == contract["prerequisite"]["signoff_sha256"], "C08 signoff pin")
check(sha(source_paths["builder"]) == contract["builder_sha256"], "builder contract pin")
check(len(closure["raw"]) == 32, "32 raw seals")
for name, seal in closure["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw seal {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-0 SSH")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI")
check([step["name"] for step in steps] == [f"{arm}_{part}" for arm in ARMS for part in ("import", "export", "calc", "report")], "12 serial steps")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"step {step['name']}")

observed = {}
for arm in ARMS:
    authored = load(HERE / f"{arm}-input.json")
    check(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == sha(RUN / f"{arm}-input.json"), f"{arm} frozen input")
    expected = populated(authored)
    actual = populated(load(RUN / f"{arm}-roundtrip-raw.json"))
    check(len(expected) == 21 and all(actual.get(name) == table for name, table in expected.items()), f"{arm} 21 row-containing table roundtrip")
    check(outcome["arms"][arm] == "completed" and outcome["converter_summaries"][arm] == [0, 2, 0] and outcome["warning_codes"][arm] == ["108", "126"], f"{arm} converter")
    check((RUN / f"{arm}.sxo").stat().st_size > 1000, f"{arm} SXO")
    log = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig")
    rep = report(RUN / f"{arm}-report-raw.json")
    series = {name: rows(rep, name) for name in ("SystemResults", "StockTotalResults", "ResourceResults")}
    for name, rs in series.items():
        check(len(rs) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(rs)), f"{arm} {name} 72 bins")
    system, resource = series["SystemResults"], series["ResourceResults"]
    check(all(abs(r["NSYA"] + r["NSYUA"] - 2) < 1e-6 for r in system), f"{arm} aircraft conservation")
    check(all(r["NFAIL"] == r["NDAM"] == 0 for r in system), f"{arm} no failure or damage")
    check(all(abs(r["NSYA"] - 2) < 1e-6 for r in system[-4:]), f"{arm} terminal ready")
    check(all(abs(r["NR"] - r["NRA"]) < 1e-6 for r in resource), f"{arm} crew availability conservation")
    check(rows(rep, "ResultSummary")[0]["NREP"] == 1, f"{arm} one repetition")
    first_start = re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", log)
    first_end = re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", log)
    second_start = re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting, duration: 1 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", log)
    second_end = re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,1> mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", log)
    check(first_start == ["8"] and first_end == ["9"], f"{arm} first formation on time")
    expected_second = ("20.5", "21.5") if arm == "out" else ("20", "21")
    check(second_start == [expected_second[0]] and second_end == [expected_second[1]], f"{arm} second formation timing")
    crew_at = {r["STINT"]: r for r in resource}
    check(crew_at[19.5]["NR"] == (1 if arm == "out" else 2), f"{arm} second preparation crew roster")
    check(crew_at[19.5]["NRUM"] == (1 if arm == "out" else 2), f"{arm} second preparation crew usage")
    check(system[39]["NSYMP"] == 2, f"{arm} two systems entering second preparation")
    check(system[40]["NSYMO"] == (0 if arm == "out" else 2), f"{arm} second wave first half-hour")
    if arm == "control":
        check("resource transfer task" not in log, "control no transfer")
    else:
        check("Time: 7.75  <P-CREW at <BASE-01,0>> Resource transfer backorder added" in log, f"{arm} busy crew backorder")
        check("Time: 8  <P-CREW at <BASE-01,0>> Resource transfer backorder removed" in log, f"{arm} backorder filled at h8")
        check("Time: 7.75  resource transfer task 0 (OUT)  arrives with 0 resources" in log, f"{arm} no busy crew leaves at h7.75")
        check("Time: 8  resource transfer task 1 (OUT)  arrives with 1 resources" in log, f"{arm} one crew leaves at h8")
    if arm == "out_in":
        check("Time: 10  resource transfer task 2 (IN)  starts with 1 resources, transfer time: 0.5" in log, "IN starts h10 with half-hour delay")
        check("Time: 10.5  resource transfer task 2 (IN)  arrives with 1 resources" in log, "IN arrival h10.5")
        check("Time: 10.5  <P-CREW at <BASE-01,0>> transfer arrives: 1" in log, "IN roster addition")
    else:
        check("(IN)" not in log, f"{arm} no IN")
    observed[arm] = {"first_launch_hour": float(first_start[0]) if first_start else None,
                     "second_launch_hour": float(second_start[0]) if second_start else None,
                     "crew_at_second_prep": crew_at[19.5]["NR"]}

check(observed["control"]["second_launch_hour"] == observed["out_in"]["second_launch_hour"] == 20.0, "IN restores control timing")
check(observed["out"]["second_launch_hour"] - observed["control"]["second_launch_hour"] == 0.5, "OUT delays second wave half-hour")
verdict = {
    "schema": "simlox-i03-var01-author-replay/v1", "run_id": RUN.name,
    "closure_sha256": sha(RUN / "closure.json"), "passed": not FAILED,
    "checks": CHECKS, "checks_passed": CHECKS - len(FAILED), "failures": FAILED,
    "observed": observed,
    "limits": "One fixed seed, personnel P-CREW at one station, one OUT and one IN schedule; no BETWEEN, equipment, alternate transfer priority or general I03 claim.",
}
destination = HERE / "review/author-validation-2026-10-05.json"
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'} {verdict['checks_passed']}/{CHECKS}")
for failure in FAILED:
    print(failure)
raise SystemExit(0 if verdict["passed"] else 1)

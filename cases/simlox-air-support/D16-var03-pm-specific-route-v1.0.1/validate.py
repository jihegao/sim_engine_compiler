"""Read-only author replay of the frozen D16.var03 PM-specific route run."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/d16-var03-pm-route-v101-ssh-20261005-01"
PARENT = ROOT / "D12-var04-remote-critical-v1.0.1"
PARENT_RUN = PARENT / "runs/d12-var04-remote-critical-v101-ssh-20261004-01"
DIAG = ROOT / "D16-var03-pm-specific-route-v1.0.0"
DIAG_RUN = DIAG / "runs/d16-var03-pm-route-v100-ssh-20261005-01"
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
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def transports(log: str) -> list[tuple[str, str, float, float, float]]:
    created = {number: (origin, destination) for number, origin, destination in re.findall(
        r"transport task (\d+) created from <(BASE-\d+),0> to <(BASE-\d+),0>", log
    )}
    starts = {number: (float(when), float(duration)) for when, number, duration in re.findall(
        r"Time: ([\d.]+)  transport task (\d+) starts with 1 items/systems, transport time: ([\d.]+)", log
    )}
    arrivals = {number: float(when) for when, number in re.findall(
        r"Time: ([\d.]+)  transport task (\d+) arrives with 1 items/systems", log
    )}
    check(set(starts) == set(arrivals) and set(starts) <= set(created), "transport task joins")
    return sorted((created[n][0], created[n][1], starts[n][0], arrivals[n], starts[n][1]) for n in starts)


contract = load(HERE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check((contract["case_id"], contract["variant_id"], contract["version"]) == ("D16", "D16.var03", "1.0.1-candidate"), "contract identity")
check(contract["run_id"] == RUN.name == closure["run_id"] == invocation["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stability")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
source_paths = {
    "contract": HERE / "contract.json", "builder": HERE / "build.py",
    "parent_input": PARENT / "remote-input.json", "parent_closure": PARENT_RUN / "closure.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-04.md", "diagnostic_closure": DIAG_RUN / "closure.json",
    "default": HERE / "default-input.json", "pm_specific": HERE / "pm_specific-input.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "runner": HERE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check(set(source_paths) == set(closure["source_hashes_before"]), "source inventory")
for key, path in source_paths.items():
    check(path.is_file() and sha(path) == closure["source_hashes_before"][key], f"source seal {key}")
check(sha(PARENT / "remote-input.json") == contract["dependency"]["input_sha256"], "parent input pin")
check(sha(PARENT_RUN / "closure.json") == contract["dependency"]["closure_sha256"], "parent closure pin")
check(sha(PARENT / "cli-scope-signoff-2026-10-04.md") == contract["dependency"]["signoff_sha256"], "parent signoff pin")
check(sha(DIAG_RUN / "closure.json") == contract["excluded_diagnostic_closure_sha256"], "excluded diagnostic pin")
check(len(closure["raw"]) == 22, "22 raw seals")
for name, seal in closure["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw seal {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-0 SSH")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI")
check([s["name"] for s in steps] == [f"{arm}_{part}" for arm in ("default", "pm_specific") for part in ("import", "export", "calc", "report")], "eight serial steps")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"step {step['name']}")

authored = {arm: load(HERE / f"{arm}-input.json") for arm in ("default", "pm_specific")}
native_logs = {}
reports = {}
for arm in ("default", "pm_specific"):
    check(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == sha(RUN / f"{arm}-input.json"), f"{arm} frozen input")
    expected = populated(authored[arm])
    actual = populated(load(RUN / f"{arm}-roundtrip-raw.json"))
    check(len(expected) == 24 and all(actual.get(name) == table for name, table in expected.items()), f"{arm} 24 populated-table roundtrip")
    check(outcome["arms"][arm] == "completed" and outcome["converter_summaries"][arm] == [0, 2, 0] and outcome["warning_codes"][arm] == ["108", "126"], f"{arm} converter")
    check((RUN / f"{arm}.sxo").stat().st_size > 1000, f"{arm} SXO")
    native_logs[arm] = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig")
    reports[arm] = report(RUN / f"{arm}-report-raw.json")
    for table_name in ("SystemResults", "StockTotalResults", "ResourceResults"):
        series = rows(reports[arm], table_name)
        check(len(series) == 60 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(series)), f"{arm} {table_name} bins")
    system = rows(reports[arm], "SystemResults")
    resource = rows(reports[arm], "ResourceResults")
    check(all(abs(r["NSYA"] + r["NSYUA"] - 2) < 0.0001 for r in system), f"{arm} aircraft conservation")
    check(sum(r["NPMS"] for r in system) == sum(r["NPMT"] for r in system) == 4, f"{arm} four PM tasks completed")
    check(abs(sum(r["NSYPM"] * 0.5 for r in system) - 4) < 0.0001, f"{arm} four PM aircraft-hours")
    check(abs(sum(r["NRUM"] * 0.5 for r in resource) - 4) < 0.0001, f"{arm} four worker-hours")
    check(all(abs(r["NSYA"] - 2) < 0.0001 for r in system[-4:]), f"{arm} terminal ready")
    check("critical random failure added" not in native_logs[arm], f"{arm} no failure confound")

check(sha(RUN / "default.log") == sha(PARENT_RUN / "remote.log"), "default/accepted-parent event identity")
check(rows(reports["default"], "ResultSummary") == rows(reports["pm_specific"], "ResultSummary"), "mission summary equality")
check(rows(reports["default"], "StockTotalResults") == rows(reports["pm_specific"], "StockTotalResults"), "stock bins equality")

observed_routes = {}
for arm, duration, arrival, return_home, big_start, transport_hours in (
    ("default", 0.25, 24.25, 25.5, 25.5, 1),
    ("pm_specific", 1.0, 25.0, 27.0, 27.0, 4),
):
    routes = transports(native_logs[arm])
    observed_routes[arm] = routes
    check(len(routes) == 4, f"{arm} four physical route legs")
    check(sum(origin == "BASE-01" and destination == "BASE-02" for origin, destination, *_ in routes) == 2, f"{arm} two outbound legs")
    check(sum(origin == "BASE-02" and destination == "BASE-01" for origin, destination, *_ in routes) == 2, f"{arm} two return legs")
    check(all(abs(finish - start - duration) < 1e-8 and abs(logged - duration) < 1e-8 for _, _, start, finish, logged in routes), f"{arm} physical travel duration")
    check(sorted(finish for origin, destination, _, finish, _ in routes if origin == "BASE-01") == [arrival] * 2, f"{arm} BASE-02 arrival")
    check(sorted(finish for origin, destination, _, finish, _ in routes if origin == "BASE-02") == [return_home] * 2, f"{arm} BASE-01 return")
    check(native_logs[arm].count("PMID: CAL24") == 2 and native_logs[arm].count("PMID: BIG24P75") == 2, f"{arm} PM identities")
    check(f"Time: {big_start:g}  system PM task 2 on" in native_logs[arm], f"{arm} larger PM after return")
    system = rows(reports[arm], "SystemResults")
    check(abs(sum(r["NSYTP"] * 0.5 for r in system) - transport_hours) < 0.0001, f"{arm} transport aircraft-hours")

verdict = {
    "schema": "simlox-d16-var03-author-replay/v1",
    "run_id": RUN.name,
    "closure_sha256": sha(RUN / "closure.json"),
    "passed": not FAILED,
    "checks": CHECKS,
    "checks_passed": CHECKS - len(FAILED),
    "failures": FAILED,
    "observed_routes": observed_routes,
    "limits": "One fixed seed, two aircraft, one CAL24 system PM and one symmetric support link; no CM-specific route or general routing law.",
}
destination = HERE / "review/author-validation-2026-10-05.json"
destination.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'} {verdict['checks_passed']}/{CHECKS}")
for failure in FAILED:
    print(failure)
raise SystemExit(0 if verdict["passed"] else 1)

"""Independent, read-only replay of the H03 position-FM native pair.

Uses only Python's standard library and raw source/run artifacts.  It does not
import the case builder, roundtrip checker, or author validator.  The native
event log displays rounded times; report-bin comparisons use a 0.0002 hour
tolerance for those timestamps.
"""

import hashlib
import json
import pathlib
import re
import sys


P = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path(__file__).with_name("independent-readonly-2026-10-02.json")
total = 0
fail = []
run_hashes = {}


def J(path):
    source = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", source))


def H(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def T(obj):
    return {item["name"]: item for item in obj.get("report", obj.get("model", obj))["tables"]}


def R(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def C(value, label):
    global total
    total += 1
    if not value:
        fail.append(label)


def A(value, expected):
    return abs(value - expected) < 0.0002


def O(a, b, c, d):
    return max(0, min(b, d) - max(a, c))


contract = J(P / "contract.json")
diff = J(P / "exact-diff.json")
src = {v: T(J(P / (v + "-input.json"))) for v in ("control", "mode")}
parent = T(J(P / contract["direct_parent"]["source"]))
C(H(P / contract["direct_parent"]["source"]) == contract["direct_parent"]["sha256"], "parent hash")
C(H(P / contract["damage_reference"]["source"]) == contract["damage_reference"]["sha256"], "damage donor hash")
C(H(P / "exact-diff.json") == contract["sources_sha256"]["exact_diff"], "diff hash")
C(set(src["control"]) - set(parent) == {"DamageType", "MissionDamage", "DamageFailureMode"}, "add tables")
for name in parent:
    if name not in ("FailureMode", "ProblemDescription"):
        C(src["control"][name] == parent[name], "parent diff " + name)
for name in src["control"]:
    if name not in ("DamageFailureMode", "ProblemDescription"):
        C(src["control"][name] == src["mode"][name], "pair diff " + name)
C(R(src["control"]["DamageFailureMode"])[0][3] == 0 and R(src["mode"]["DamageFailureMode"])[0][3] == 1, "prob pair")

arms = (
    ("control", [7, 19, 31], [8, 20, 32], [10, 22, 34], [], [8.13665, 20.828, 32.373]),
    ("mode", [7, 19, 31], [8, 20, 32], [8.27329, 21.1501, 33.6102], [8.77329, 21.6501, 34.1102], [8.13665, 20.6501, 33.1102]),
)
for v, alloc, launch, ret, end, dam in arms:
    run = P / "runs" / ("h03-var01-posfm-" + v + "-v100-ssh-20261002-01")
    invocation = J(run / "invocation.json")
    closure = J(run / "closure.json")
    source = src[v]
    C(H(P / (v + "-input.json")) == contract["sources_sha256"][v] == H(run / "input.json"), "source " + v)
    C(H(run / "invocation.json") == closure["invocation_sha256"], "inv seal " + v)
    C(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH " + v)
    C(invocation["gui"]["pid"] == 13340 and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "GUI mutex " + v)
    C(closure["source_hashes_before"] == closure["source_hashes_after"], "stable " + v)
    source_files = (
        ("input", P / (v + "-input.json")),
        ("parent", P / contract["direct_parent"]["source"]),
        ("damage_reference", P / contract["damage_reference"]["source"]),
        ("contract", P / "contract.json"),
        ("builder", P / "build.py"),
        ("checker", P / "check_roundtrip.py"),
        ("runner_script", P / "run_native_ssh.ps1"),
        ("exact_diff", P / "exact-diff.json"),
    )
    for name, path in source_files:
        C(closure["source_hashes_before"][name] == H(path), "source seal " + v + name)
    for name, meta in closure["raw"].items():
        C(H(run / name) == meta["sha256"] and (run / name).stat().st_size == meta["bytes"], "raw " + v + name)
    steps = J(run / "steps.json")
    C(len(steps) == 5 and all(step["exit_code"] == 0 and step["gui_preserved"] for step in steps), "steps " + v)
    roundtrip = T(J(run / "roundtrip-raw.json"))
    authored = {name: table for name, table in source.items() if R(table)}
    C(len(authored) == 21, "21 tables " + v)
    for name, table in authored.items():
        C(name in roundtrip and table["columns"] == roundtrip[name]["columns"] and table["instances"] == roundtrip[name]["instances"], "roundtrip " + v + name)
    C("Errors: 0" in (run / "run.log").read_text() and (run / "model.sxo").stat().st_size > 4, "converter " + v)
    log = (run / "model.log").read_text()
    C(log.count("Damage BATTLE-HIT occured") == 3, "damage count " + v)
    C(log.count("Failure Mode: FM-POS-A on materiel: <POS-A,0>") == (0 if v == "control" else 3), "FM count " + v)
    C(log.count("Next random failure will occur 1e+010") > 0 and not re.search("ordinary failure occured", log, re.I), "ordinary no failure " + v)
    for i in range(3):
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{i}>"
        C(f"Time: {launch[i]} {mission} mission starting" in log, "launch " + v + str(i))
        C(f"Time: {dam[i]} <TEACH-AIR-01,0>Damage BATTLE-HIT occured" in log, "damage " + v + str(i))
        if v == "control":
            C(f"Time: {ret[i]} {mission} mission success" in log, "success " + v + str(i))
        else:
            C(f"Time: {dam[i]} {mission} mission aborted" in log, "abort " + str(i))
            C(f"Time: {ret[i]}  system CM task {i} on <TEACH-AIR-01,0> started" in log, "CM start " + str(i))
            C(f"Time: {end[i]}  system CM task {i} on <TEACH-AIR-01,0> completed" in log, "CM end " + str(i))
            C(f"Time: {end[i]} <TEACH-AIR-01,BASE-01,0> System ready" in log, "ready " + str(i))
    report = T(J(run / "report-raw.json"))
    system = report["SystemResults"]
    stock = report["StockTotalResults"]
    sys_rows = R(system)
    stock_rows = R(stock)
    sc = {column["name"]: i for i, column in enumerate(system["columns"])}
    ic = {column["name"]: i for i, column in enumerate(stock["columns"])}
    C(len(sys_rows) == len(stock_rows) == 72, "72 bins " + v)
    for ix, (row, stock_row) in enumerate(zip(sys_rows, stock_rows)):
        a = ix / 2
        b = a + .5
        ma = sum(O(a, b, alloc[k], ret[k]) * 2 for k in range(3))
        mo = sum(O(a, b, launch[k], ret[k]) * 2 for k in range(3))
        rp = sum(O(a, b, ret[k], end[k]) * 2 for k in range(len(end)))
        mr = sum(O(a, b, alloc[k], launch[k]) * 2 for k in range(3))
        expectations = (
            ("NSYMA", ma), ("NSYMO", mo), ("FTMO", mo), ("STACC", mo),
            ("NSYRP", rp), ("NSYUA", rp), ("NSYRY", 1 - ma - rp),
            ("NSYA", 1 - rp), ("NSYMR", mr),
            ("NDAM", sum(a <= time < b for time in dam)),
            ("NREPT", sum(a <= time < b for time in end)),
        )
        for name, expected in expectations:
            C(A(row[sc[name]], expected), v + name + str(ix))
        C(A(row[sc["STINT"]], a) and A(row[sc["ETINT"]], b), "time " + v + str(ix))
        C(stock_row[ic["PNB"]] == 1 and stock_row[ic["NBO"]] == 0, "stock " + v + str(ix))
    flight_hours = sum(row[sc["NSYMO"]] * .5 for row in sys_rows)
    repair_hours = sum(row[sc["NSYRP"]] * .5 for row in sys_rows)
    C(A(flight_hours, sum(ret[k] - launch[k] for k in range(3))), "flight integral " + v)
    C(A(repair_hours, len(end) * .5), "CM integral " + v)
    C(sys_rows[-1][sc["NSYRY"]] == 1 and sys_rows[-1][sc["NSYRP"]] == 0, "terminal " + v)
    summary = report["ResultSummary"]
    summary_row = R(summary)[0]
    uc = {column["name"]: i for i, column in enumerate(summary["columns"])}
    C(summary_row[uc["NREP"]] == 1 and summary_row[uc["MSTF"]] == 1 and summary_row[uc["MSUF"]] == (1 if v == "control" else 0), "summary " + v)
    run_hashes[v] = {
        "closure_sha256": H(run / "closure.json"),
        "report_sha256": H(run / "report-raw.json"),
        "model_log_sha256": H(run / "model.log"),
        "flight_aircraft_hours": flight_hours,
        "cm_repair_aircraft_hours": repair_hours,
    }

result = {
    "schema": "h03-position-fm-independent-readonly/v1",
    "passed": not fail and total == 2087,
    "verdict": "GO: bounded position-FM damage-to-CM path" if not fail and total == 2087 else "NO-GO",
    "checks_passed": total - len(fail),
    "checks_total": total,
    "failures": fail,
    "runs": run_hashes,
    "scope": "One seed, one BATTLE-HIT damage type, FM-POS-A on child position POS-A, three observed damage-to-CM cycles; control has PROB0 and mode PROB1.",
    "limits": [
        "No simultaneous DamageItem and DamageFailureMode consequence is modeled; the earlier directly system-owned mixed diagnostic remains unresolved.",
        "Positive ordinary FRQ=1e-9 is not a mathematical zero-rate guarantee; no ordinary random failure occurred in these runs.",
        "No general probability law, other position or station, GUI visual behavior, or cross-engine parity is established.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "failures": fail, "output": str(OUT)}))
sys.exit(0 if result["passed"] else 1)

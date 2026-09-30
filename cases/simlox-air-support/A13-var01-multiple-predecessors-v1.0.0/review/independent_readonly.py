"""Independent standard-library read-only replay of A13.var01 three native runs."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parents[1]
AIR = HERE.parent
PARENT = AIR / "A13-start-dependence-v1.0.0" / "dependent-input.json"
RUNS = {v: f"a13-var01-{v}-v100-20261001-01" for v in ("control", "single", "multiple")}
FROZEN = {
    "parent": "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246",
    "contract": "84b82ff8e6172a63f488909d88d048c419a14daaad6d50b9409119334deebc88",
    "builder": "6d5cc8ee0f3cb2723e5b6ca01e57adb9677436c38868d5449973cfbf6d61b05b",
    "exact_diff": "9aa2e04fc202a95b3e5fa61bf59fca9249e2c26796abd80afc8b8c94c917a38a",
    "diff_checker": "a8a96e3b2c765af0d2b14261d4957fbb0d009b7dd358a1de77eaf023fca93402",
    "checker": "46720c5a238110e7e3715771ac04f10e9776dcef2254ee66ed043fa13b9bbb45",
    "runner_script": "ef1c586f85da518b5b88f2969d7da34b7c20029d9f00f680e25a68db4453da75",
    "python": "372c2eae555b344520bf147be0096e009069aeca4e7f78d6aecea6d53158056a",
    "simlox_exe": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
    "manual": "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3",
    "dictionary": "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0",
    "control": "dad6d27f7b565235e9fcfedde9862c84596c8360fd32bb191959e0d6d32ab82a",
    "single": "d816f5de462263c746a7094603417c7fdc618c03374685b8ead484f545bae030",
    "multiple": "1d2226850d07d7caf5f58e825bb2d3fdf498f7626fb58e4a6ed4bcfa469d18ae",
}
FILES = {
    "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py",
    "exact_diff": HERE / "exact-diff.json", "diff_checker": HERE / "describe_diff.py",
    "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    **{v: HERE / f"{v}-input.json" for v in RUNS},
}
OUT = HERE / "review" / "independent-readonly-2026-10-01.json"
checks = 0
failures: list[str] = []


def check(label: str, good: bool) -> None:
    global checks
    checks += 1
    if not good:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        out: list[str] = []
        quoted = escaped = False
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def tabmap(doc: dict, root: str) -> dict[str, dict]:
    items = doc[root]["tables"]
    result = {t["name"]: t for t in items}
    check(f"{root} unique tables", len(result) == len(items))
    return result


def pop(doc: dict) -> dict[str, dict]:
    result = {}
    for name, t in tabmap(doc, "model").items():
        rows = [r for i in t["instances"] for r in i["rows"]]
        for row in rows:
            check(f"{name} rectangular", len(row) == len(t["columns"]))
        if rows:
            result[name] = {"columns": t["columns"], "rows": rows}
    return result


def field(t: dict, row: list, name: str):
    return row[[c["name"] for c in t["columns"]].index(name)]


def near(a, b, tol=3e-5) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(float(a), float(b), rel_tol=0, abs_tol=tol)


def occ(start: float, end: float, lo: float, hi: float) -> float:
    return max(0, min(end, hi) - max(start, lo)) / (hi - lo)


def source_checks() -> None:
    contract, diff = read(FILES["contract"]), read(FILES["exact_diff"])
    for key, expected in FROZEN.items():
        check(f"frozen SHA {key}", FILES[key].is_file() and sha(FILES[key]) == expected)
    check("accepted A13 parent signoff", (AIR / "A13-start-dependence-v1.0.0" /
          "cli-scope-signoff-2026-09-30.md").is_file())
    check("catalog A13.var01 planned", '"variant_id": "A13.var01"' in
          (AIR / "catalog-v2.json").read_text(encoding="utf-8"))
    check("contract identity/source", contract["case_id"] == "A13" and
          contract["variant_id"] == "A13.var01" and contract["version"] == "1.0.0-candidate" and
          contract["parent_input_sha256"] == FROZEN["parent"] and
          contract["source"]["manual_sha256"] == FROZEN["manual"] and
          contract["configuration"]["aircraft"] == 3 and contract["configuration"]["simulation_hours"] == 24)
    check("exact diff parent", diff["parent_sha256"] == FROZEN["parent"])
    parent = tabmap(read(PARENT), "model")
    child = {}
    for v in RUNS:
        t = tabmap(read(FILES[v]), "model")
        child[v] = t
        expected_tables = 31 if v == "control" else 32
        check(f"{v} table inventory", len(t) == expected_tables and
              set(t) == (set(parent) - ({"MissionDependence"} if v == "control" else set())))
        changes = {name: {"before": parent[name]["instances"] if name in parent else None,
                          "after": t[name]["instances"] if name in t else None}
                   for name in sorted(set(parent) | set(t)) if parent.get(name) != t.get(name)}
        check(f"{v} exact changed tables", set(changes) == {"MissionDependence", "MissionType",
              "OperationProfile", "ProblemDescription", "SystemDeployment", "Unit"} and
              changes == diff["variants"][v]["changed_tables"] and
              sorted((set(parent) & set(t)) - set(changes)) == diff["variants"][v]["unchanged_tables"] and
              diff["variants"][v]["input_sha256"] == FROZEN[v])
        check(f"{v} populated table count", len(pop(read(FILES[v]))) == (13 if v == "control" else 14))
        deployment = t["SystemDeployment"]
        check(f"{v} three aircraft source", field(deployment, deployment["instances"][0]["rows"][0], "QTYPS") == 3)
        system = t["System"]
        check(f"{v} zero system failure", field(system, system["instances"][0]["rows"][0], "FRT") == 0)
        mission = t["MissionType"]
        mrows = {field(mission, r, "MTID"): r for r in mission["instances"][0]["rows"]}
        check(f"{v} three fixed mission types", set(mrows) == {"EARLY", "LATE", "FOLLOW"} and
              all(field(mission, r, "MPAT") is None and field(mission, r, "MNOS") == 1 and
                  field(mission, r, "MSUCPT") == 1 for r in mrows.values()) and
              [field(mission, mrows[n], "DURN") for n in ("EARLY", "LATE", "FOLLOW")] == [1, 4, 2])
        profile = t["OperationProfile"]
        prows = {field(profile, r, "SPRID"): r for r in profile["instances"][0]["rows"]}
        check(f"{v} scheduled identities/deferral", set(prows) == set(mrows) and
              [field(profile, prows[n], "STIM") for n in ("EARLY", "LATE", "FOLLOW")] == [8, 8, 10] and
              all(field(profile, r, "DTIM") == 4 and field(profile, r, "IQTY") == 1 for r in prows.values()))
        dep_rows = t["MissionDependence"]["instances"][0]["rows"] if "MissionDependence" in t else []
        check(f"{v} dependency row identities", len(dep_rows) == {"control": 0, "single": 1, "multiple": 2}[v] and
              {field(t["MissionDependence"], r, "PMTID") for r in dep_rows} ==
              {"control": set(), "single": {"EARLY"}, "multiple": {"EARLY", "LATE"}}[v] and
              all(field(t["MissionDependence"], r, "DMTID") == "FOLLOW" and
                  field(t["MissionDependence"], r, "DSTIM") == 10 and
                  field(t["MissionDependence"], r, "PSTIM") == 8 and
                  field(t["MissionDependence"], r, "DTYPE") == "START" for r in dep_rows))
    for a, b in (("control", "single"), ("single", "multiple")):
        check(f"{a}->{b} pair only dependence and label",
              {n for n in set(child[a]) | set(child[b]) if child[a].get(n) != child[b].get(n)} ==
              {"MissionDependence", "ProblemDescription"})


def run_checks(v: str) -> tuple[dict, str]:
    run = HERE / "runs" / RUNS[v]
    inv, closure, steps = (read(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
    check(f"{v} invocation identity", inv["schema"].startswith("simlox-a13-var01-multiple-predecessors-v100-") and
          inv["case_id"] == "A13" and inv["variant_id"] == "A13.var01" and
          inv["case_version"] == "1.0.0-candidate" and inv["variant"] == v and
          inv["run_id"] == RUNS[v] and inv["input_sha256"] == FROZEN[v] and
          inv["parent_sha256"] == FROZEN["parent"] and
          inv["scope"] == "start_dependency_multiple_predecessors")
    check(f"{v} original run path", Path(inv["original_run_dir"]).resolve() == run.resolve())
    check(f"{v} session0 SSH/mutex/GUI", inv["execution_mode"] == "ssh_cli_v1" and
          inv["session_id"] == 0 and inv["ssh_connection_present"] is True and
          "sshd.exe" in inv["ssh_ancestor_names"] and
          inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
          inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1 and
          bool(inv["gui"]["start_utc"]))
    check(f"{v} closure identity", closure["schema"].startswith("simlox-a13-var01-multiple-predecessors-v100-") and
          closure["run_id"] == RUNS[v] and closure["invocation_sha256"] == sha(run / "invocation.json") and
          closure["error"] is None and closure["scope"] == "start_dependency_multiple_predecessors")
    expected = {key: FROZEN[key] for key in ("parent", "contract", "builder", "exact_diff",
                "diff_checker", "checker", "runner_script", "python", "simlox_exe")}
    expected["input"] = FROZEN[v]
    for key, value in expected.items():
        check(f"{v} frozen before/after {key}", inv["source_hashes_before"].get(key) == value and
              closure["source_hashes_before"].get(key) == value and
              closure["source_hashes_after"].get(key) == value)
    check(f"{v} top-level hash fields", inv["contract_sha256"] == expected["contract"] and
          inv["builder_sha256"] == expected["builder"] and
          inv["checker_sha256"] == expected["checker"] and
          inv["python_sha256"] == expected["python"] and
          inv["runner_script_sha256"] == expected["runner_script"] and
          inv["simlox_exe_sha256"] == expected["simlox_exe"])
    files = {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}
    check(f"{v} complete sealed raw inventory", files == set(closure["raw"]) and len(files) == 12)
    for name, meta in closure["raw"].items():
        f = run / name
        check(f"{v} raw {name}", f.stat().st_size == meta["bytes"] and sha(f) == meta["sha256"])
    check(f"{v} five guarded steps", [s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          [s["status"] for s in steps] ==
          ["completed", "completed", "calc_observed", "completed", "completed"] and
          all(s["exit_code"] == 0 and s["gui_preserved"] and s["error"] is None for s in steps))
    for i, step in enumerate(steps):
        start = datetime.fromisoformat(step["started_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(step["completed_utc"].replace("Z", "+00:00"))
        check(f"{v} step {i} times", start <= end and
              (i == 0 or datetime.fromisoformat(steps[i-1]["completed_utc"].replace("Z", "+00:00")) <= start))
    check(f"{v} planned commands", all(steps[i]["arguments"] ==
          inv["planned_commands"][i]["arguments"] for i in range(3)) and
          steps[3]["arguments"] == inv["planned_report"]["arguments"] and
          steps[4]["arguments"] == inv["planned_check"]["arguments"])
    check(f"{v} copied source hash", sha(run / "input.json") == FROZEN[v])
    before, after = pop(native(run / "input.json")), pop(native(run / "roundtrip-raw.json"))
    check(f"{v} populated count", len(before) == (13 if v == "control" else 14))
    for name, table in before.items():
        check(f"{v} exact source roundtrip {name}", after.get(name) == table)
    check(f"{v} import/export markers", "Import completed!" in
          (run / "import.log").read_text(encoding="utf-8-sig", errors="replace") and
          "Export completed!" in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"))
    check(f"{v} author's source checker corroboration", read(run / "roundtrip-validation.json")["passed"] is True)
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check(f"{v} converter zero errors/warnings 108,126", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc and
          len(re.findall(r"\(warning #108\)", calc)) == 1 and
          len(re.findall(r"\(warning #126\)", calc)) == 1 and
          len(re.findall(r"\(warning #", calc)) == 2 and "(error #" not in calc and
          "Saving results" in calc)
    check(f"{v} valid SXO/report", (run / "model.sxo").stat().st_size > 4 and
          (run / "report-raw.json").stat().st_size > 4 and
          "Generating Json-report" in (run / "report-export.log").read_text(encoding="utf-8-sig", errors="replace"))
    return native(run / "report-raw.json"), (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")


def event_checks(v: str, log: str) -> None:
    ids = {"EARLY": "<EARLY,TEACH-UNIT,0,0,0>", "LATE": "<LATE,TEACH-UNIT,0,0,1>",
           "FOLLOW": "<FOLLOW,TEACH-UNIT,0,0,2>"}
    def one(label: str, fragment: str) -> int:
        check(f"{v} {label}", log.count(fragment) == 1)
        return log.find(fragment)
    one("initial ready3", "Time: 0 <TEACH-UNIT at <BASE-01,0>> systems ready: 3")
    for name, aircraft, assign, launch, done, dur in (
        ("EARLY", 0, 7, 8, 9, 1), ("LATE", 1, 7, 8, 12, 4),
        ("FOLLOW", 2, 9, 12 if v == "multiple" else 10, 14 if v == "multiple" else 12, 2)):
        mid = ids[name]
        p = one(f"{name} assigned aircraft{aircraft}",
                f"Time: {assign} {mid} mission allocates system: <TEACH-AIR-01,{aircraft}>")
        q = one(f"{name} launched", f"Time: {launch} {mid} mission starting, duration: {dur} : <TEACH-AIR-01,{aircraft}>")
        r = one(f"{name} success", f"Time: {done} {mid} mission success:")
        s = one(f"{name} completion", f"Time: {done} {mid} mission completed: <TEACH-AIR-01,{aircraft}>")
        check(f"{v} {name} ordered lifecycle", 0 <= p < q < r < s)
        task_start = {"EARLY": 8.25, "LATE": 9, "FOLLOW": 12.5 if v == "multiple" else 10.5}[name]
        task_end = {"EARLY": 8.75, "LATE": 11, "FOLLOW": 13.5 if v == "multiple" else 11.5}[name]
        one(f"{name} positive task starts", f"Time: {task_start} {mid} task starting: <TEACH-AIR-01,{aircraft}>")
        one(f"{name} positive task ends", f"Time: {task_end} {mid} task completed: <TEACH-AIR-01,{aircraft}>")
    check(f"{v} no failures/cancellations", "critical random failure added" not in log and
          "mission cancelled:" not in log and "mission aborted:" not in log)
    one("terminal ready3", f"Time: {14 if v == 'multiple' else 12} <TEACH-UNIT at <BASE-01,0>> systems ready: 3")
    check(f"{v} horizon event", "Time: 24  Start of day no 1" in log)
    if v == "multiple":
        a = log.find("Time: 12 <LATE,TEACH-UNIT,0,0,1> mission success:")
        b = log.find("Time: 12 <FOLLOW,TEACH-UNIT,0,0,2> mission starting")
        c = log.find("Time: 12 <LATE,TEACH-UNIT,0,0,1> mission completed:")
        check("multiple exact same-time log order", 0 <= a < b < c)


def report_table(doc: dict, name: str) -> tuple[list[str], list[list]]:
    t = tabmap(doc, "report")[name]
    check(f"{name} single instance", len(t["instances"]) == 1)
    return [c["name"] for c in t["columns"]], t["instances"][0]["rows"]


def ledger_checks(v: str, doc: dict) -> dict:
    names, system = report_table(doc, "SystemResults")
    snames, stock = report_table(doc, "StockTotalResults")
    rnames, summaries = report_table(doc, "ResultSummary")
    check(f"{v} report population", set(tabmap(doc, "report")) ==
          {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"} and
          len(system) == len(stock) == 48 and len(summaries) == 1)
    check(f"{v} system columns", names == ["UNID", "SID", "STINT", "ETINT", "NSYRY", "NSYMA",
          "NSYMO", "NSYMC", "NSYMP", "NSYMT", "NSYMS", "NSYMR", "NSYUA", "NSYA", "NSYAL",
          "FTMO", "NSYRP", "NSYPM", "NSYTP", "NSYWR", "NSYWI", "NSYLA", "NSYUH", "NREPT",
          "NPMT", "NFAIL", "NDAM", "NPMS", "NROBT", "NRCFG", "STREQ", "STACC", "STF", "STLOW",
          "SYDT", "SYDTU", "NSYDT", "NSYSW", "NPSTA", "NPSUC"])
    check(f"{v} stock columns", snames == ["STINT", "ETINT", "NBO", "NBOU", "ROS", "ROST",
          "WT", "WTT", "WTS", "PNB", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT"])
    follow_launch = 12 if v == "multiple" else 10
    follow_end = 14 if v == "multiple" else 12
    for i, row in enumerate(system):
        lo, hi = i / 2, (i + 1) / 2
        assigned = occ(7, 9, lo, hi) + occ(7, 12, lo, hi) + occ(9, follow_end, lo, hi)
        operating = occ(8, 9, lo, hi) + occ(8, 12, lo, hi) + occ(follow_launch, follow_end, lo, hi)
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                    "STINT": lo, "ETINT": hi, "NSYRY": 3 - assigned, "NSYMA": assigned,
                    "NSYMO": operating, "NSYMR": assigned - operating, "NSYA": 3,
                    "FTMO": operating / 3, "STACC": operating, "SYDT": None}
        for j, name in enumerate(names):
            value = expected.get(name, 0)
            check(f"{v} System bin{i} {name}", near(row[j], value) if
                  isinstance(value, (int, float)) or value is None else row[j] == value)
    for i, row in enumerate(stock):
        expected = {"STINT": i / 2, "ETINT": (i + 1) / 2, "PNB": 1,
                    **{k: None for k in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS")}}
        for j, name in enumerate(snames):
            check(f"{v} Stock bin{i} {name}", near(row[j], expected.get(name, 0)))
    summary = dict(zip(rnames, summaries[0]))
    for name, value in summary.items():
        check(f"{v} summary {name}", near(value, {"NREP": 1, "RTIUP": 24,
              "MTMF": 1, "MSTF": 1, "MSUF": 1, "STMF": 1}.get(name, 0)))
    check(f"{v} terminal three ready", near(system[-1][names.index("NSYRY")], 3) and
          near(system[-1][names.index("NSYMA")], 0) and
          near(system[-1][names.index("NSYMO")], 0))
    integral = lambda name: sum(row[names.index(name)] or 0 for row in system) / 2
    return {"summary": summary, "system_bins": len(system), "stock_bins": len(stock),
            "integrals": {name: integral(name) for name in
                          ("NSYRY", "NSYMA", "NSYMO", "NSYMR", "NSYA", "STACC")},
            "terminal_ready": system[-1][names.index("NSYRY")]}


def main() -> int:
    source_checks()
    results: dict[str, dict] = {}
    reports: dict[str, dict] = {}
    logs: dict[str, str] = {}
    for v in RUNS:
        reports[v], logs[v] = run_checks(v)
        event_checks(v, logs[v])
        results[v] = ledger_checks(v, reports[v])
    check("control/single byte-identical native log", logs["control"] == logs["single"])
    ta, tb = tabmap(reports["control"], "report"), tabmap(reports["single"], "report")
    check("control/single reports differ only description", {k for k in ta if ta[k] != tb[k]} ==
          {"ProblemDescription"})
    ta, tb = tabmap(reports["single"], "report"), tabmap(reports["multiple"], "report")
    check("single/multiple report difference", {k for k in ta if ta[k] != tb[k]} ==
          {"ProblemDescription", "SystemResults"})
    output = {"schema": "simlox-a13-var01-independent-readonly/v1",
              "passed": not failures, "check_count": checks, "passed_count": checks - len(failures),
              "failures": failures,
              "decision": "GO_bounded_two_fixed_START_precedents" if not failures else "NO_GO",
              "scope": "one seed, one unit, three aircraft, two simultaneous fixed precedents and one dependent",
              "same_time_caveat": "At hour 12 the multiple-run text orders LATE success, FOLLOW launch, then LATE completion/arrival; identical timestamps do not establish the engine's internal return-versus-launch ordering.",
              "limitations": ["No absent, failed, cross-unit, continuous, repeated-identity or post-horizon predecessor claim",
                              "No GUI visual-content or cross-engine claim"],
              "frozen_sha256": FROZEN,
              "runs": {v: {"run_id": RUNS[v], "closure_sha256": sha(HERE / "runs" / RUNS[v] / "closure.json"),
                            **results[v]} for v in RUNS}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes((json.dumps(output, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({k: output[k] for k in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

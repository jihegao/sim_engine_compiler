"""Independent, read-only A13.var04 v1.0.2 native evidence replay.

Uses only Python's standard library and never imports case builder/checker code.
Reads frozen sources and sealed raw runs; writes only its review JSON.
"""
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
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
REPORT = HERE / "review" / "independent-readonly-2026-10-01.json"
RUNS = {
    "failure-control": "a13-var04-failure-control-v102-20261001-01",
    "failure-dependency": "a13-var04-failure-dependency-v102-20261001-01",
}
FROZEN = {
    "parent": "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246",
    "contract": "c40536f52028b94b1639f300d723be15de25948fd7da4b08281f76b11e159012",
    "builder": "2e7b12bd07c0c812ba4a9f5761e8b7213e70eeca094331635d42fd89bc8f7fd5",
    "exact_diff": "1ef7ccd2227c82046e01747d07ca3fa11bdc3970ac695b2e6ce62d991bb170bb",
    "diff_checker": "b2e5d10987f9c5ae532815972ba60687c24dd72f3e555a64bf0e021219789192",
    "checker": "4966ce1a0e2342515c2d1b6a60720c1f85424f10db8d48edf525d024dfffe674",
    "runner_script": "c6650344a890a2fe8c02c5b488447b37f7cb35ad1207abe6b1e11606fc8efc82",
    "python": "372c2eae555b344520bf147be0096e009069aeca4e7f78d6aecea6d53158056a",
    "simlox_exe": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
    "manual": "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3",
    "dictionary": "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0",
    "failure-control": "9890dac653a5a77938875e25335dd0103ed1e539f45971394f18933c6a3e2514",
    "failure-dependency": "ee41efc4ecfa6446c835f2249941dabdeacd4b7a506941f6f5d68e30414e3d75",
}
FILES = {
    "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py",
    "exact_diff": HERE / "exact-diff.json", "diff_checker": HERE / "describe_diff.py",
    "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1",
    "python": PYTHON, "simlox_exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY,
    **{v: HERE / f"{v}-input.json" for v in RUNS},
}
failures: list[str] = []
checks = 0


def check(label: str, condition: bool) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    """Remove only commas followed by a closing delimiter, outside strings."""
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


def tables(doc: dict, root: str) -> dict[str, dict]:
    items = doc[root]["tables"]
    result = {t["name"]: t for t in items}
    check(f"{root} unique table names", len(result) == len(items))
    return result


def populated(doc: dict) -> dict[str, dict]:
    result = {}
    for name, t in tables(doc, "model").items():
        rows = [r for i in t["instances"] for r in i["rows"]]
        for r in rows:
            check(f"source {name} rectangular", len(r) == len(t["columns"]))
        if rows:
            result[name] = {"columns": t["columns"], "rows": rows}
    return result


def report_table(doc: dict, name: str) -> tuple[list[str], list[list]]:
    t = tables(doc, "report")[name]
    check(f"{name} one instance", len(t["instances"]) == 1)
    return [c["name"] for c in t["columns"]], t["instances"][0]["rows"]


def close(a: float | int | None, b: float | int | None, tol: float = 3e-5) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(float(a), float(b), rel_tol=0, abs_tol=tol)


def occ(a: float, b: float, lo: float, hi: float) -> float:
    return max(0.0, min(b, hi) - max(a, lo)) / (hi - lo)


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def source_checks() -> None:
    contract = read(FILES["contract"])
    diff = read(FILES["exact_diff"])
    for key, expected in FROZEN.items():
        check(f"frozen SHA {key}", FILES[key].is_file() and sha(FILES[key]) == expected)
    check("accepted parent signoff", (AIR / "A13-start-dependence-v1.0.0" /
          "cli-scope-signoff-2026-09-30.md").is_file())
    check("contract identity/version", contract["case_id"] == "A13" and
          contract["variant_id"] == "A13.var04" and contract["case_version"] == "1.0.2-candidate" and
          contract["publication_state"] == "not_published")
    check("contract source fingerprints", contract["parent"]["input_sha256"] == FROZEN["parent"] and
          contract["inputs_sha256"] == {v: FROZEN[v] for v in RUNS} and
          contract["exact_diff_sha256"] == FROZEN["exact_diff"] and
          contract["source"]["manual_sha256"] == FROZEN["manual"] and
          contract["source"]["dictionary_sha256"] == FROZEN["dictionary"])
    check("excluded earlier diagnostic", {x["package"] for x in contract["excluded_diagnostics"]} ==
          {"../A13-var04-failed-precedent-v1.0.0", "../A13-var04-failed-precedent-v1.0.1"})
    parent = tables(read(PARENT), "model")
    check("diff parent SHA", diff["parent_sha256"] == FROZEN["parent"])
    children = {}
    for v in RUNS:
        f = FILES[v]
        child = tables(read(f), "model")
        children[v] = child
        check(f"{v} exact parent table inventory", parent.keys() == child.keys() and len(child) == 32)
        delta = {name: {"before": parent[name]["instances"], "after": child[name]["instances"]}
                 for name in parent if parent[name] != child[name]}
        expected_names = ({"ProblemDescription", "System", "SystemRepair", "MissionType"} |
                          ({"MissionDependence"} if v == "failure-control" else set()))
        check(f"{v} exact changed table names", set(delta) == expected_names)
        check(f"{v} exact declared parent delta", delta == diff["variants"][v]["changed_tables"] and
              sorted(set(parent) - set(delta)) == diff["variants"][v]["unchanged_tables"] and
              diff["variants"][v]["input_sha256"] == FROZEN[v])
        mt = child["MissionType"]
        cols = [c["name"] for c in mt["columns"]]
        rows = {r[cols.index("MTID")]: r for r in mt["instances"][0]["rows"]}
        check(f"{v} fixed mission success/failure fields",
              rows["RECON"][cols.index("MSUCPT")] == 1.0 and
              rows["FOLLOW"][cols.index("MFF")] == 1e-6 and
              all(r[cols.index("MPAT")] is None for r in rows.values()))
        sys = child["System"]
        cols = [c["name"] for c in sys["columns"]]
        row = sys["instances"][0]["rows"][0]
        check(f"{v} operating-hour system failure", row[cols.index("FRT")] == 300000 and
              row[cols.index("OPID")] == "OPHOURS")
        repair = child["SystemRepair"]
        cols = [c["name"] for c in repair["columns"]]
        row = repair["instances"][0]["rows"][0]
        check(f"{v} direct repair source", row[cols.index("SID")] == "TEACH-AIR-01" and
              row[cols.index("STID")] == "BASE-01" and row[cols.index("DIRPT")] == 0.5 and
              row[cols.index("DIRPF")] == 1.0)
    check("pair differs only description and START row", [n for n in parent if
          children["failure-control"][n] != children["failure-dependency"][n]] ==
          ["ProblemDescription", "MissionDependence"])


def run_checks(v: str) -> tuple[dict, str]:
    run = HERE / "runs" / RUNS[v]
    inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    check(f"{v} invocation identity", inv["schema"].startswith("simlox-a13-var04-failed-precedent-v102-") and
          inv["case_id"] == "A13" and inv["variant_id"] == "A13.var04" and
          inv["case_version"] == "1.0.2-candidate" and inv["variant"] == v and
          inv["run_id"] == RUNS[v] and inv["input_sha256"] == FROZEN[v] and
          inv["parent_sha256"] == FROZEN["parent"] and inv["publication_state"] == "not_published")
    check(f"{v} invocation absolute run path", Path(inv["original_run_dir"]).resolve() == run.resolve())
    check(f"{v} SSH/session/mutex/GUI", inv["execution_mode"] == "ssh_cli_v1" and
          inv["session_id"] == 0 and inv["ssh_connection_present"] is True and
          "sshd.exe" in inv["ssh_ancestor_names"] and
          inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
          inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1 and
          bool(inv["gui"]["start_utc"]))
    check(f"{v} closure identity", closure["schema"].startswith("simlox-a13-var04-failed-precedent-v102-") and
          closure["run_id"] == RUNS[v] and closure["error"] is None and
          closure["publication_state"] == "not_published" and
          closure["invocation_sha256"] == sha(run / "invocation.json"))
    hashes = {key: FROZEN[key] for key in
              ("parent", "contract", "builder", "exact_diff", "diff_checker", "checker",
               "runner_script", "python", "simlox_exe")}
    hashes["input"] = FROZEN[v]
    for key, val in hashes.items():
        check(f"{v} before/after frozen {key}",
              inv["source_hashes_before"].get(key) == val and
              closure["source_hashes_before"].get(key) == val and
              closure["source_hashes_after"].get(key) == val)
    check(f"{v} invocation top-level source hashes",
          inv["contract_sha256"] == hashes["contract"] and
          inv["builder_sha256"] == hashes["builder"] and
          inv["checker_sha256"] == hashes["checker"] and
          inv["python_sha256"] == hashes["python"] and
          inv["runner_script_sha256"] == hashes["runner_script"] and
          inv["simlox_exe_sha256"] == hashes["simlox_exe"])
    actual = {p.name for p in run.iterdir() if p.is_file()} - {"closure.json", "invocation.json"}
    check(f"{v} complete raw inventory", actual == set(closure["raw"]) and len(actual) == 12)
    for name, meta in closure["raw"].items():
        f = run / name
        check(f"{v} sealed {name}", f.stat().st_size == meta["bytes"] and sha(f) == meta["sha256"])
    check(f"{v} five guarded steps", [s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(s["exit_code"] == 0 and s["gui_preserved"] and s["error"] is None for s in steps) and
          [s["status"] for s in steps] ==
          ["completed", "completed", "calc_observed", "completed", "completed"])
    for i, step in enumerate(steps):
        check(f"{v} step {i} ordered times", timestamp(step["started_utc"]) <=
              timestamp(step["completed_utc"]) and
              (i == 0 or timestamp(steps[i - 1]["completed_utc"]) <= timestamp(step["started_utc"])))
    check(f"{v} command arguments sealed", all(steps[i]["arguments"] ==
          inv["planned_commands"][i]["arguments"] for i in range(3)) and
          steps[3]["arguments"] == inv["planned_report"]["arguments"] and
          steps[4]["arguments"] == inv["planned_check"]["arguments"])
    check(f"{v} copied source SHA", sha(run / "input.json") == FROZEN[v])
    source, exported = native(run / "input.json"), native(run / "roundtrip-raw.json")
    src, exp = populated(source), populated(exported)
    check(f"{v} source populated count", len(src) == (14 if v == "failure-control" else 15))
    for name, table in src.items():
        check(f"{v} exact native source roundtrip {name}", exp.get(name) == table)
    check(f"{v} import/export markers", "Import completed!" in
          (run / "import.log").read_text(encoding="utf-8-sig", errors="replace") and
          "Export completed!" in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"))
    check(f"{v} author roundtrip result corroboration", read(run / "roundtrip-validation.json")["passed"] is True)
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check(f"{v} converter counts", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log and
          len(re.findall(r"\(warning #108\)", log)) == 1 and
          len(re.findall(r"\(warning #126\)", log)) == 1 and "(error #" not in log and
          "Saving results" in log)
    check(f"{v} valid native SXO/report", (run / "model.sxo").stat().st_size > 4 and
          (run / "report-raw.json").stat().st_size > 4 and
          "Generating Json-report" in (run / "report-export.log").read_text(encoding="utf-8-sig", errors="replace"))
    return native(run / "report-raw.json"), (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")


def event_checks(v: str, log: str) -> None:
    def one(label: str, fragment: str) -> int:
        check(f"{v} event {label}", log.count(fragment) == 1)
        return log.find(fragment)

    recon = "<RECON,TEACH-UNIT,0,0,0>"
    follow = "<FOLLOW,TEACH-UNIT,0,0,1>"
    ordered = [
        ("initial two ready", "Time: 0 <TEACH-UNIT at <BASE-01,0>> systems ready: 2"),
        ("RECON assigned aircraft 0", f"Time: 7 {recon} mission allocates system: <TEACH-AIR-01,0>"),
        ("RECON launches", f"Time: 8 {recon} mission starting, duration: 4 : <TEACH-AIR-01,0>"),
        ("FOLLOW assigned aircraft 1", f"Time: 9 {follow} mission allocates system: <TEACH-AIR-01,1>"),
        ("critical failure aircraft 0", "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added"),
        ("RECON abort", f"Time: 9.8829 {recon} mission aborted:"),
        ("aborted RECON completes", f"Time: 10.8829 {recon} aborted mission completed:"),
        ("repair begins", "Time: 10.8829  system DIRP task 0 on <TEACH-AIR-01,0> started"),
        ("repair ends", "Time: 11.3829  system DIRP task 0 on <TEACH-AIR-01,0> completed"),
    ]
    positions = {label: one(label, frag) for label, frag in ordered}
    check(f"{v} causal common event order", all(positions[label] >= 0 for label, _ in ordered) and
          positions["initial two ready"] < positions["RECON assigned aircraft 0"] <
          positions["RECON launches"] < positions["FOLLOW assigned aircraft 1"] <
          positions["critical failure aircraft 0"] < positions["RECON abort"] <
          positions["aborted RECON completes"] < positions["repair begins"] <
          positions["repair ends"])
    check(f"{v} no RECON success", f"{recon} mission success:" not in log)
    one("RECON failure aircraft abort identity", f"<TEACH-AIR-01,0> aborts its mission {recon}")
    one("repair positive half hour", "starts performing, planned to last for 0.5 hours")
    one("repaired aircraft ready", "Time: 11.3829 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>")
    if v == "failure-control":
        one("FOLLOW launch", f"Time: 10 {follow} mission starting, duration: 2 : <TEACH-AIR-01,1>")
        one("FOLLOW success", f"Time: 12 {follow} mission success:")
        one("FOLLOW completion", f"Time: 12 {follow} mission completed: <TEACH-AIR-01,1>")
        check("control no FOLLOW cancellation", f"{follow} mission cancelled:" not in log)
        one("control terminal two ready", "Time: 12 <TEACH-UNIT at <BASE-01,0>> systems ready: 2")
    else:
        one("FOLLOW cancellation on failed return", f"Time: 10.8829 {follow} mission cancelled:")
        check("dependency FOLLOW never launches/succeeds", f"{follow} mission starting" not in log and
              f"{follow} mission success:" not in log and f"{follow} task starting:" not in log)
        check("dependency unfailed aircraft returns",
              log.count("Time: 10.8829 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,1>") == 2)
        one("dependency terminal two ready", "Time: 11.3829 <TEACH-UNIT at <BASE-01,0>> systems ready: 2")
    check(f"{v} horizon marker", "Time: 24  Start of day no 1" in log)


def ledger_checks(v: str, doc: dict) -> dict:
    names, system = report_table(doc, "SystemResults")
    snames, stock = report_table(doc, "StockTotalResults")
    rnames, summary_rows = report_table(doc, "ResultSummary")
    check(f"{v} report table population", set(tables(doc, "report")) ==
          {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"} and
          len(system) == len(stock) == 48 and len(summary_rows) == 1)
    check(f"{v} system report columns", names == ["UNID", "SID", "STINT", "ETINT", "NSYRY", "NSYMA",
          "NSYMO", "NSYMC", "NSYMP", "NSYMT", "NSYMS", "NSYMR", "NSYUA", "NSYA", "NSYAL", "FTMO",
          "NSYRP", "NSYPM", "NSYTP", "NSYWR", "NSYWI", "NSYLA", "NSYUH", "NREPT", "NPMT", "NFAIL",
          "NDAM", "NPMS", "NROBT", "NRCFG", "STREQ", "STACC", "STF", "STLOW", "SYDT", "SYDTU",
          "NSYDT", "NSYSW", "NPSTA", "NPSUC"])
    check(f"{v} stock report columns", snames == ["STINT", "ETINT", "NBO", "NBOU", "ROS", "ROST",
          "WT", "WTT", "WTS", "PNB", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT"])
    follow_end = 12.0 if v == "failure-control" else 10.8829
    for i, row in enumerate(system):
        lo, hi = i / 2, (i + 1) / 2
        recon_assign = occ(7, 10.8829, lo, hi)
        follow_assign = occ(9, follow_end, lo, hi)
        assigned = recon_assign + follow_assign
        operating = occ(8, 10.8829, lo, hi) + (occ(10, 12, lo, hi) if v == "failure-control" else 0)
        reserved = occ(7, 8, lo, hi) + occ(9, 10 if v == "failure-control" else 10.8829, lo, hi)
        repair = occ(10.8829, 11.3829, lo, hi)
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems", "STINT": lo,
                    "ETINT": hi, "NSYRY": 2 - assigned - repair, "NSYMA": assigned,
                    "NSYMO": operating, "NSYMR": reserved, "NSYUA": repair,
                    "NSYA": 2 - repair, "FTMO": operating / 2, "NSYRP": repair,
                    "NREPT": 1 if lo == 11 else 0, "NFAIL": 1 if lo == 9.5 else 0,
                    "STACC": operating, "SYDT": .5 if lo == 10.5 else None,
                    "NSYDT": 1 if lo == 10.5 else 0}
        for j, name in enumerate(names):
            value = expected.get(name, 0)
            check(f"{v} SystemResults bin {i} {name}", close(row[j], value) if
                  isinstance(value, (int, float)) or value is None else row[j] == value)
    for i, row in enumerate(stock):
        lo, hi = i / 2, (i + 1) / 2
        expected = {"STINT": lo, "ETINT": hi, "PNB": 1,
                    **{k: None for k in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS")}}
        for j, name in enumerate(snames):
            value = expected.get(name, 0)
            check(f"{v} StockTotalResults bin {i} {name}", close(row[j], value))
    summary = dict(zip(rnames, summary_rows[0]))
    expected_summary = {"NREP": 1, "RTILW": 0, "RTIUP": 24,
                        "MTMF": (4.8829 if v == "failure-control" else 2.8829) / 6,
                        "MSTF": 1 if v == "failure-control" else .5,
                        "MSUF": .5 if v == "failure-control" else 0,
                        "STMF": (4.8829 if v == "failure-control" else 2.8829) / 6}
    for name, val in summary.items():
        check(f"{v} ResultSummary {name}", close(val, expected_summary.get(name, 0)))
    integral = lambda name: sum(row[names.index(name)] or 0 for row in system) / 2
    check(f"{v} terminal ready two", close(system[-1][names.index("NSYRY")], 2) and
          close(system[-1][names.index("NSYA")], 2) and
          close(system[-1][names.index("NSYMA")], 0) and
          close(system[-1][names.index("NSYUA")], 0))
    return {"summary": summary,
            "integrals": {name: integral(name) for name in
                          ("NSYRY", "NSYMA", "NSYMO", "NSYMR", "NSYUA", "NSYA", "NSYRP", "STACC")},
            "terminal_ready": system[-1][names.index("NSYRY")], "system_bins": len(system),
            "stock_bins": len(stock)}


def main() -> int:
    source_checks()
    details = {}
    for v in RUNS:
        report, log = run_checks(v)
        event_checks(v, log)
        details[v] = ledger_checks(v, report)
    control_log = (HERE / "runs" / RUNS["failure-control"] / "model.log").read_bytes()
    dep_log = (HERE / "runs" / RUNS["failure-dependency"] / "model.log").read_bytes()
    common = b"Time: 9.8829 <RECON,TEACH-UNIT,0,0,0> task completed: (aborted):"
    check("matched common failure prefix", common in control_log and common in dep_log and
          control_log.split(common)[0] == dep_log.split(common)[0])
    result = {"schema": "simlox-a13-var04-v102-independent-readonly/v1",
              "passed": not failures, "check_count": checks, "passed_count": checks - len(failures),
              "failures": failures, "decision": "GO_bounded_failed_fixed_precedent_START_pair" if not failures else "NO_GO",
              "scope": "one fixed seed, two fixed missions, one aircraft each, one matched direct critical system failure",
              "limitations": ["No multiple/absent/unfinished predecessor, cross-unit, other seed or failure mode claim",
                              "No GUI visual-content or cross-engine claim; same-time internal event order unresolved",
                              "Native evidence shows this pair only; manual's MSUCPT result-only wording is not resolved generically"],
              "frozen_sha256": FROZEN, "runs": {v: {"run_id": RUNS[v],
                  "closure_sha256": sha(HERE / "runs" / RUNS[v] / "closure.json"), **details[v]} for v in RUNS}}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({k: result[k] for k in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

"""Independent standard-library replay of sealed A12.var04 CLI evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RESULT = Path(__file__).with_name("independent-confiscation-2026-09-30.json")
PARENT_SHA = "300f3129b1f5d78018ad00875b545ffc1d7619dde5c3086c7a8bf0abb145094a"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
DIFF_SHA = "a805c7f1a99f482016f9194a6867e174821404271305677526d4fbee2e2b995c"
RUNS = {
    "early-high": ("a12-var04-early-high-20260930-01", "de69780b98779f8cf76f61f391bd4ecae97fe0f660fd6b8f26a5e61384174551"),
    "late-high": ("a12-var04-late-high-20260930-01", "499e2b056b72cda8d4ada7918e65c692e06a3d2b5b8c852e2cba9a8177e6c88e"),
}
checks: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name: str, ok: bool, actual: object = None) -> None:
    checks.append({"name": name, "passed": bool(ok), "actual_if_failed": actual if not ok else None})


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


def tables(doc: dict, root: str = "model") -> dict:
    return {t["name"]: t for t in doc[root]["tables"]}


def rows(table: dict) -> list[dict]:
    keys = [c["name"] for c in table["columns"]]
    return [dict(zip(keys, row)) for instance in table["instances"] for row in instance["rows"]]


def near(a: float, b: float, tol: float = 2e-5) -> bool:
    return abs(a - b) <= tol


def overlap(a: float, b: float, lo: float, hi: float) -> float:
    return max(0.0, min(b, hi) - max(a, lo))


def events(raw: str) -> list[tuple[float, str, int]]:
    return [(float(m.group(1)), m.group(2), i) for i, line in enumerate(raw.splitlines())
            if (m := re.match(r"^Time: ([0-9.]+) (.*)$", line))]


def found(ev: list, pattern: str) -> list:
    rx = re.compile(pattern)
    return [(t, body, index) for t, body, index in ev if rx.search(body)]


def at(ev: list, name: str, pattern: str, hour: float, count: int = 1) -> list:
    got = found(ev, pattern)
    check(name, len(got) == count and all(near(t, hour) for t, _, _ in got), got)
    return got


def ready_twice(ev: list, name: str, aircraft: str, later: float) -> None:
    got = found(ev, rf"{re.escape(aircraft)} nbr ready increased at unit:")
    check(name, len(got) == 2 and near(got[0][0], 0) and near(got[1][0], later), got)


def main() -> None:
    parent = ROOT / "A12-mission-priority-contention-v1.0.0" / "basic-high-input.json"
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    check("published A12 parent SHA", sha(parent) == PARENT_SHA)
    check("installed manual SHA", sha(manual) == MANUAL_SHA)
    check("frozen exact diff SHA", sha(CASE / "exact-diff.json") == DIFF_SHA)
    parent_t = tables(load(parent))
    docs = {v: load(CASE / f"{v}-input.json") for v in RUNS}
    source = {v: tables(d) for v, d in docs.items()}
    for variant, (_, expected_sha) in RUNS.items():
        prefix = variant + ": "
        check(prefix + "input SHA", sha(CASE / f"{variant}-input.json") == expected_sha)
        delta = {n for n in parent_t if parent_t[n] != source[variant][n]}
        expected_delta = {"ProblemDescription", "OperationProfile"} | ({"MissionType"} if variant == "late-high" else set())
        check(prefix + "parent changed tables", delta == expected_delta, sorted(delta))
        check(prefix + "all parent table schemas and names preserved", len(source[variant]) == len(parent_t) == 32 and all(source[variant][n]["columns"] == parent_t[n]["columns"] for n in parent_t))
        ms = rows(source[variant]["MissionSystem"])
        check(prefix + "each mission needs one A and one B", len(ms) == 4 and all({r["SID"]: (r["NOS"], r["MNOS"]) for r in ms if r["MTID"] == m} == {"TEACH-AIR-01": (1, 1), "TEACH-AIR-02": (1, 1)} for m in ("BASIC-MISSION", "SECOND-MISSION")))
        mt = {r["MTID"]: r for r in rows(source[variant]["MissionType"])}
        want = (1, 2) if variant == "early-high" else (2, 1)
        check(prefix + "priority and one-hour notice", (mt["BASIC-MISSION"]["PRI"], mt["SECOND-MISSION"]["PRI"]) == want and all(r["NOPER"] == 1 and r["NOS"] == r["MNOS"] == 2 and r["DURN"] == 2 for r in mt.values()))
        op = {r["SPRID"]: r for r in rows(source[variant]["OperationProfile"])}
        check(prefix + "7/7.25 call and distinct scheduled rows", len(op) == 2 and op["BASIC-MISSION"]["STIM"] == 8 and op["SECOND-MISSION"]["STIM"] == 8.25 and all(r["PRID"] == "BASIC-SCHEDULE" and r["ITYPE"] == "SCHEDULED" and r["IQTY"] == 1 and r["IPER"] == 0 and near(r["DTIM"], 1/3) for r in op.values()))
        mp = rows(source[variant]["MissionPreparation"])
        check(prefix + "four half-hour preparation recipes", len(mp) == 4 and {(r["MTID"], r["SID"]) for r in mp} == {(m, s) for m in mt for s in ("TEACH-AIR-01", "TEACH-AIR-02")} and all(r["DURN"] == .5 and r["TID"] == "PREP-FIXED" for r in mp))
        check(prefix + "A+A+B deployment", {(r["SID"], r["QTYPS"]) for r in rows(source[variant]["SystemDeployment"])} == {("TEACH-AIR-01", 2), ("TEACH-AIR-02", 1)})
    changed_pair = {n for n in source["early-high"] if source["early-high"][n] != source["late-high"][n]}
    check("pair changes only MissionType and descriptive label", changed_pair == {"MissionType", "ProblemDescription"}, sorted(changed_pair))
    e = {r["MTID"]: r for r in rows(source["early-high"]["MissionType"])}
    l = {r["MTID"]: r for r in rows(source["late-high"]["MissionType"])}
    check("priority-only pairwise business delta", all({k: v for k, v in e[mid].items() if k != "PRI"} == {k: v for k, v in l[mid].items() if k != "PRI"} for mid in e))

    evidence: dict[str, dict] = {}
    for variant, (run_id, input_sha) in RUNS.items():
        prefix = variant + ": "
        run = CASE / "runs" / run_id
        inv, closure, steps = (load(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
        check(prefix + "invocation/closure lineage", inv["variant"] == variant and inv["case_id"] == "A12.var04" and inv["run_id"] == closure["run_id"] == run_id and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None)
        actual_raw = {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}
        check(prefix + "12 raw files byte and SHA sealed", len(actual_raw) == 12 and set(closure["raw"]) == actual_raw and all(closure["raw"][name]["sha256"] == sha(run / name) and closure["raw"][name]["bytes"] == (run / name).stat().st_size for name in actual_raw), sorted(actual_raw))
        sh = inv["source_hashes_before"]
        paths = {"input": CASE / f"{variant}-input.json", "parent": parent, "contract": CASE / "contract.json", "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(inv["planned_check"]["executable"]), "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")}
        check(prefix + "source/tool hashes before=after=current", sh == closure["source_hashes_before"] == closure["source_hashes_after"] and all(sh[k] == sha(path) for k, path in paths.items()), sh)
        check(prefix + "selected input and parent SHA", inv["input_sha256"] == input_sha == sha(run / "input.json") and inv["parent_sha256"] == PARENT_SHA)
        gui = inv["gui"]
        check(prefix + "session-0 SSH queue and GUI identity", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and gui["pid"] == 13340 and gui["session_id"] == 1 and bool(gui["start_utc"]))
        names = ["import", "export", "calc", "jsonreport", "check_import_export"]
        check(prefix + "five serial GUI-preserving successful steps", [x["name"] for x in steps] == names and all(x["status"] == "completed" and x["exit_code"] == 0 and x["gui_preserved"] and x["started_utc"] <= x["completed_utc"] for x in steps) and all(steps[j]["completed_utc"] <= steps[j+1]["started_utc"] for j in range(4)))
        check(prefix + "planned command arguments match steps", all(inv["planned_commands"][j]["name"] == steps[j]["name"] and inv["planned_commands"][j]["arguments"] == steps[j]["arguments"] for j in range(4)))
        inp, exp = tables(native(run / "input.json")), tables(native(run / "roundtrip-raw.json"))
        populated = {name for name, t in inp.items() if rows(t)}
        check(prefix + "16 exact row-containing source tables roundtrip", len(populated) == 16 and all(name in exp and inp[name]["columns"] == exp[name]["columns"] and inp[name]["instances"] == exp[name]["instances"] for name in populated))
        check(prefix + "import/export markers", "Import completed!" in (run / "import.log").read_text(encoding="utf-8-sig") and "Export completed!" in (run / "export.log").read_text(encoding="utf-8-sig"))
        conversion = (run / "run.log").read_text(encoding="utf-8-sig")
        warns = re.findall(r"warning #(\d+)", conversion)
        check(prefix + "zero conversion errors and classified warnings", "Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in conversion and sorted(warns) == ["108", "126", "126"] and "Saving results" in conversion, warns)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        ev = events(log)
        basic, second = "<BASIC-MISSION,TEACH-UNIT,0,0,0>", "<SECOND-MISSION,TEACH-UNIT,0,0,1>"
        a0, a1, b2 = "<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>", "<TEACH-AIR-02,2>"
        for mission, tag, hour in (("BASIC-MISSION", basic, 7), ("SECOND-MISSION", second, 7.25)):
            at(ev, prefix + mission + " ordered", rf"<TEACH-UNIT> mission ordered: {mission}$", hour)
            at(ev, prefix + mission + " created", rf"{re.escape(tag)} mission created:", hour)
            at(ev, prefix + mission + " activated", rf"{re.escape(tag)} mission activated, systems requested: 2", hour)
        for tag, aircraft, hour in ((basic, a0, 7), (basic, b2, 7), (second, a1, 7.25)):
            at(ev, prefix + tag + " allocates " + aircraft, rf"{re.escape(tag)} mission allocates system: {re.escape(aircraft)}$", hour)
            at(ev, prefix + aircraft + " preparation starts for " + tag, rf"{re.escape(aircraft)} preparation started, mission: {re.escape(tag)}$", hour)
        at(ev, prefix + "A0 BASIC prep ends", rf"{re.escape(a0)} preparation ended, mission: {re.escape(basic)}$", 7.5)
        at(ev, prefix + "A1 SECOND prep ends", rf"{re.escape(a1)} preparation ended, mission: {re.escape(second)}$", 7.75)
        if variant == "early-high":
            at(ev, prefix + "B2 BASIC prep ends", rf"{re.escape(b2)} preparation ended, mission: {re.escape(basic)}$", 7.5)
            at(ev, prefix + "SECOND waits to 8.08333", rf"{re.escape(second)} mission waiting:  timeout at 8\.08333", 7.25)
            at(ev, prefix + "SECOND cancels", rf"{re.escape(second)} mission cancelled:", 8.08333)
            at(ev, prefix + "BASIC launches A0+B2", rf"{re.escape(basic)} mission starting, duration: 2 : {re.escape(a0)},{re.escape(b2)}$", 8)
            at(ev, prefix + "BASIC on station", rf"{re.escape(basic)} task starting: {re.escape(a0)},{re.escape(b2)}$", 8.5)
            at(ev, prefix + "BASIC back from station", rf"{re.escape(basic)} task completed: {re.escape(a0)},{re.escape(b2)}$", 9.5)
            at(ev, prefix + "BASIC succeeds", rf"{re.escape(basic)} mission success:", 10)
            at(ev, prefix + "BASIC completes", rf"{re.escape(basic)} mission completed: {re.escape(a0)},{re.escape(b2)}$", 10)
            ready_twice(ev, prefix + "A1 returns ready", a1, 8.08333)
            ready_twice(ev, prefix + "A0 returns ready", a0, 10)
            ready_twice(ev, prefix + "B2 returns ready", b2, 10)
            check(prefix + "no B2 confiscation/stop", not found(ev, r"mission gives away system:|ordered to stop|system preparation task .* stopped"))
            flight_start, flight_end, cancel = 8, 10, 8.083333333333334
            assigns = [(7, 10), (7, 10), (7.25, cancel)]
            preps = [(7, 7.5), (7, 7.5), (7.25, 7.75)]
            prepared = [(7.5, 8), (7.5, 8), (7.75, cancel)]
            prep_started, prep_completed = 3, 3
        else:
            at(ev, prefix + "BASIC gives B2 away", rf"{re.escape(basic)} mission gives away system: {re.escape(b2)}$", 7.25)
            at(ev, prefix + "SECOND preassigns B2", rf"{re.escape(second)} mission preassigns a system: {re.escape(b2)}$", 7.25)
            stop_order = at(ev, prefix + "B2 original subtask ordered to stop", rf"subtask 1 seqno 0 within system preparation task 1 on {re.escape(b2)} ordered to stop$", 7.25)
            at(ev, prefix + "B2 original task stopped", rf"^\s*system preparation task 1 on {re.escape(b2)} stopped$", 7.25)
            at(ev, prefix + "B2 BASIC prep ends early", rf"{re.escape(b2)} preparation ended, mission: {re.escape(basic)}$", 7.25)
            turn_start = at(ev, prefix + "B2 proportional turnround starts at factor .5", rf"{re.escape(b2)} turnround started, mission: {re.escape(basic)} reduction factor: 0\.5$", 7.25)
            turn_end = at(ev, prefix + "B2 zero-duration turnround ends", rf"{re.escape(b2)} turnround ended, mission: {re.escape(basic)}$", 7.25)
            b2alloc = at(ev, prefix + "SECOND allocates B2", rf"{re.escape(second)} mission allocates system: {re.escape(b2)}$", 7.25)
            at(ev, prefix + "B2 SECOND prep starts", rf"{re.escape(b2)} preparation started, mission: {re.escape(second)}$", 7.25)
            at(ev, prefix + "B2 SECOND prep ends", rf"{re.escape(b2)} preparation ended, mission: {re.escape(second)}$", 7.75)
            at(ev, prefix + "B2 new task completes", rf"^\s*system preparation task 3 on {re.escape(b2)} completed$", 7.75)
            give = found(ev, rf"{re.escape(basic)} mission gives away system: {re.escape(b2)}$")
            preassign = found(ev, rf"{re.escape(second)} mission preassigns a system: {re.escape(b2)}$")
            check(prefix + "ordered transfer lifecycle at same timestamp", all(len(x) == 1 for x in (give, preassign, stop_order, turn_start, turn_end, b2alloc)) and give[0][2] < preassign[0][2] < stop_order[0][2] < turn_start[0][2] < turn_end[0][2] < b2alloc[0][2])
            at(ev, prefix + "BASIC cancels", rf"{re.escape(basic)} mission cancelled:", 7.83333)
            at(ev, prefix + "SECOND launches A1+B2", rf"{re.escape(second)} mission starting, duration: 2 : {re.escape(a1)},{re.escape(b2)}$", 8.25)
            at(ev, prefix + "SECOND on station", rf"{re.escape(second)} task starting: {re.escape(a1)},{re.escape(b2)}$", 8.75)
            at(ev, prefix + "SECOND back from station", rf"{re.escape(second)} task completed: {re.escape(a1)},{re.escape(b2)}$", 9.75)
            at(ev, prefix + "SECOND succeeds", rf"{re.escape(second)} mission success:", 10.25)
            at(ev, prefix + "SECOND completes", rf"{re.escape(second)} mission completed: {re.escape(a1)},{re.escape(b2)}$", 10.25)
            ready_twice(ev, prefix + "A0 returns ready", a0, 7.83333)
            ready_twice(ev, prefix + "A1 returns ready", a1, 10.25)
            # B2 also temporarily becomes ready at 7.25 between the zero-time
            # turnround and immediate new allocation, then ready after flight.
            b2ready = found(ev, rf"{re.escape(b2)} nbr ready increased at unit:")
            check(prefix + "B2 conservation through transient ready and final return", len(b2ready) == 3 and all(near(b2ready[j][0], h) for j, h in enumerate((0, 7.25, 10.25))), b2ready)
            flight_start, flight_end, cancel = 8.25, 10.25, 7.833333333333334
            assigns = [(7, cancel), (7, 10.25), (7.25, 10.25)]
            preps = [(7, 7.5), (7, 7.25), (7.25, 7.75), (7.25, 7.75)]
            prepared = [(7.5, cancel), (7.75, 8.25), (7.75, 8.25)]
            prep_started, prep_completed = 4, 3
        check(prefix + "exact one launch, success, cancellation and no failure", len(found(ev, r"mission starting, duration:")) == 1 and len(found(ev, r"mission success:")) == 1 and len(found(ev, r"mission cancelled:")) == 1 and not found(ev, r"(?i)(failure occurs|mission aborted|repair task .* started)"))
        check(prefix + "preparation event counts", len(found(ev, r"preparation started, mission:")) == prep_started and len(found(ev, r"^\s*system preparation task \d+ on .* completed$")) == prep_completed)
        check(prefix + "last ready roster has all three aircraft", "systems ready: 3 :<TEACH-AIR-01,1>,<TEACH-AIR-01,0>,<TEACH-AIR-02,2>" in log if variant == "early-high" else "systems ready: 3 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>,<TEACH-AIR-02,2>" in log)

        report = tables(native(run / "report-raw.json"), "report")
        summary = rows(report["ResultSummary"])
        check(prefix + "one of two mission summary", len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 36 and all(near(summary[0][k], .5) for k in ("MTMF", "MSTF", "MSUF", "STMF")))
        sy, st = rows(report["SystemResults"]), rows(report["StockTotalResults"])
        check(prefix + "72 contiguous half-hour system/stock bins", len(sy) == len(st) == 72 and all(near(sy[j]["STINT"], j/2) and near(sy[j]["ETINT"], (j+1)/2) and near(st[j]["STINT"], j/2) and near(st[j]["ETINT"], (j+1)/2) for j in range(72)))
        occupancy_ok = counters_ok = stock_ok = demand_profile_ok = True
        for r, stock in zip(sy, st):
            lo, hi = r["STINT"], r["ETINT"]
            av = lambda intervals: sum(overlap(a, b, lo, hi) for a, b in intervals) / .5
            assigned = av(assigns)
            operating = av([(flight_start, flight_end)] * 2)
            expected = {"NSYRY": 3-assigned, "NSYMA": assigned, "NSYMP": av(preps), "NSYMR": av(prepared), "NSYMO": operating, "NSYA": 3, "FTMO": operating/3, "STACC": operating}
            if not all(near(r[k], val) for k, val in expected.items()): occupancy_ok = False
            if r["NPSTA"] != (prep_started if lo == 7 else 0) or r["NPSUC"] != (prep_completed if lo == 7.5 else 0) or any(r[k] != 0 for k in ("NFAIL", "NREPT", "NPMT", "NSYRP", "NSYPM", "NSYMT", "NSYMS", "NSYWR", "NSYWI")): counters_ok = False
            if stock["PNB"] != 1 or any(stock[k] != 0 for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")): stock_ok = False
            # STREQ is an observed requirement series, not flight occupancy.
            # Numerically it decomposes into one 8-10 and one 8.25-10.25
            # interval in both variants; we do not assign mission identity.
            if not near(r["STREQ"], av([(8, 10), (8.25, 10.25)])): demand_profile_ok = False
        check(prefix + "all event-derived occupancy fields reconcile every bin", occupancy_ok)
        check(prefix + "preparation starts/completions and zero maintenance/failure bins", counters_ok)
        check(prefix + "72 stock bins have zero demand/backorder/wait", stock_ok)
        check(prefix + "separate STREQ numerical profile across 72 bins", demand_profile_ok)
        prep_hours = 1.5 if variant == "early-high" else 1.75
        check(prefix + "integrals and terminal ready", near(sum(r["NSYMP"]*.5 for r in sy), prep_hours) and near(sum(r["NSYMO"]*.5 for r in sy), 4) and near(sum(r["STACC"]*.5 for r in sy), 4) and near(sy[-1]["NSYRY"], 3) and near(sy[-1]["NSYMA"], 0))
        evidence[variant] = {"run_id": run_id, "input_sha256": input_sha, "invocation_sha256": sha(run / "invocation.json"), "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"), "report_raw_sha256": sha(run / "report-raw.json"), "winner": "BASIC-MISSION" if variant == "early-high" else "SECOND-MISSION", "cancellation_hour": 8.08333 if variant == "early-high" else 7.83333, "prep_start_count": prep_started, "prep_complete_count": prep_completed, "prep_aircraft_hours": prep_hours, "operation_aircraft_hours": 4, "STREQ_aircraft_hours": sum(r["STREQ"]*.5 for r in sy), "terminal_ready": 3}

    result = {"schema": "simlox-a12-var04-independent-native-review/v1", "author": "separate independent read-only reviewer", "decision": "bounded_native_behavior_accepted" if all(c["passed"] for c in checks) else "review_failed", "check_count": len(checks), "pass_count": sum(c["passed"] for c in checks), "fail_count": sum(not c["passed"] for c in checks), "checks": checks, "runs": evidence, "limits": ["The late-high raw trace proves interruption and transfer of B2 after 0.25h of BASIC preparation, with a logged proportional-turnround factor 0.5 but no positive turnround duration in this model.", "A1 comes from the ready pool, so only B2 is shown confiscated from active preparation.", "STREQ is identical in both variants and numerically equals one unit over 8-10 plus one over 8.25-10.25. Its precise semantics are unresolved here; it must not be presented as actual per-bin flight occupancy. NSYMO and STACC match actual flight intervals.", "The system report is fleet-aggregate; aircraft and mission identities derive from the native event log.", "This pair does not establish equal-priority ties, positive unpreparation duration, resources, failures, GUI behavior or cross-engine parity."]}
    RESULT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"decision": result["decision"], "checks": result["check_count"], "passed": result["pass_count"], "failed": result["fail_count"], "script_sha256": sha(Path(__file__)), "report_sha256": sha(RESULT), "failures": [c for c in checks if not c["passed"]]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

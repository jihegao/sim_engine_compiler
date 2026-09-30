"""Independent, read-only A12 native pair replay. Standard library only."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
REVIEW = Path(__file__).with_name("independent-priority-2026-09-30.json")
PARENT_SHA = "4e1387b15457485de42ae20b1f0ed6382c013603c0bfc6de75d753339c2a7213"
PREP_SHA = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
VARIANTS = {
    "basic-high": ("a12-basic-high-20260930-01", "300f3129b1f5d78018ad00875b545ffc1d7619dde5c3086c7a8bf0abb145094a", "BASIC-MISSION", "SECOND-MISSION"),
    "second-high": ("a12-second-high-20260930-01", "84e6a73b74502d259588e38ef43415d4e9c2d2f29307622a0fdd5e4c5d2c5135", "SECOND-MISSION", "BASIC-MISSION"),
}
checks: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(label: str, condition: bool, detail: object = None) -> None:
    checks.append({"check": label, "passed": bool(condition), "detail": detail if not condition else None})


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    # Native SIMLOX JSON may have trailing commas. Normalize only a parser copy.
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


def tabs(doc: dict, root: str = "model") -> dict:
    return {t["name"]: t for t in doc[root]["tables"]}


def rows(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def close(a: float, b: float, tol: float = 2e-5) -> bool:
    return abs(a - b) <= tol


def overlap(start: float, end: float, left: float, right: float) -> float:
    return max(0.0, min(end, right) - max(start, left))


def events(text: str) -> list[tuple[float, str]]:
    return [(float(m.group(1)), m.group(2)) for line in text.splitlines()
            if (m := re.match(r"^Time: ([0-9.]+) (.*)$", line))]


def matches(ev: list[tuple[float, str]], pattern: str) -> list[tuple[float, str]]:
    rx = re.compile(pattern)
    return [(t, body) for t, body in ev if rx.search(body)]


def timed(ev: list[tuple[float, str]], label: str, pattern: str, expected: float, count: int = 1) -> None:
    got = matches(ev, pattern)
    require(label, len(got) == count and all(close(t, expected) for t, _ in got), got)


def timed_pair(ev: list[tuple[float, str]], label: str, pattern: str, later: float) -> None:
    got = matches(ev, pattern)
    require(label, len(got) == 2 and close(got[0][0], 0) and close(got[1][0], later), got)


def main() -> None:
    parent_path = ROOT / "A11-mixed-type-minimum-v1.0.0" / "required-input.json"
    prep_path = ROOT / "B01-fixed-preparation-v1.0.1" / "native-input.json"
    manual_path = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    require("accepted A11 parent SHA", sha(parent_path) == PARENT_SHA)
    require("accepted B01 preparation SHA", sha(prep_path) == PREP_SHA)
    require("installed manual SHA", sha(manual_path) == MANUAL_SHA)
    parent = tabs(load(parent_path))
    documents = {v: load(CASE / f"{v}-input.json") for v in VARIANTS}
    source = {v: tabs(doc) for v, doc in documents.items()}
    for variant, (_, expected_sha, winner, loser) in VARIANTS.items():
        require(f"{variant} frozen source SHA", sha(CASE / f"{variant}-input.json") == expected_sha)
        changed = {n for n in parent if parent[n] != source[variant][n]}
        require(f"{variant} parent changed-table set", changed == {"ProblemDescription", "MissionType", "OperationProfile", "MissionSystem", "MissionPreparation", "Tasks"}, sorted(changed))
        mt = {r["MTID"]: r for r in rows(source[variant]["MissionType"])}
        require(f"{variant} priority and mission types", set(mt) == {"BASIC-MISSION", "SECOND-MISSION"} and mt[winner]["PRI"] == 1 and mt[loser]["PRI"] == 2)
        op = rows(source[variant]["OperationProfile"])
        require(f"{variant} distinct simultaneous profile keys", len(op) == 2 and {r["SPRID"] for r in op} == set(mt) and all(r["PRID"] == "BASIC-SCHEDULE" and r["STIM"] == 8 and r["ITYPE"] == "SCHEDULED" and r["IQTY"] == 1 and r["IPER"] == 0 and close(r["DTIM"], 1/3) for r in op))
        ms = rows(source[variant]["MissionSystem"])
        require(f"{variant} each mission requires A+B", len(ms) == 4 and all({r["SID"]: (r["NOS"], r["MNOS"]) for r in ms if r["MTID"] == mission} == {"TEACH-AIR-01": (1, 1), "TEACH-AIR-02": (1, 1)} for mission in mt))
        mp = rows(source[variant]["MissionPreparation"])
        require(f"{variant} four half-hour preparation rows", len(mp) == 4 and {(r["MTID"], r["SID"]) for r in mp} == {(m, s) for m in mt for s in ("TEACH-AIR-01", "TEACH-AIR-02")} and all(r["DURN"] == .5 and r["TID"] == "PREP-FIXED" for r in mp))
        require(f"{variant} three deployed aircraft", {(r["SID"], r["QTYPS"]) for r in rows(source[variant]["SystemDeployment"])} == {("TEACH-AIR-01", 2), ("TEACH-AIR-02", 1)})
    pair_changed = {n for n in source["basic-high"] if source["basic-high"][n] != source["second-high"][n]}
    require("pair changed-table set", pair_changed == {"ProblemDescription", "MissionType"}, sorted(pair_changed))
    pmt = {v: {r["MTID"]: r for r in rows(source[v]["MissionType"])} for v in VARIANTS}
    require("pair has only PRI business-field changes", all({k: x for k, x in pmt["basic-high"][m].items() if k != "PRI"} == {k: x for k, x in pmt["second-high"][m].items() if k != "PRI"} for m in pmt["basic-high"]))

    run_evidence = {}
    for variant, (run_id, expected_sha, winner, loser) in VARIANTS.items():
        run = CASE / "runs" / run_id
        invocation, closure, steps = (load(run / f) for f in ("invocation.json", "closure.json", "steps.json"))
        prefix = variant + ": "
        require(prefix + "invocation and closure binding", invocation["run_id"] == closure["run_id"] == run_id and invocation["variant"] == variant and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None)
        raw_files = {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}
        require(prefix + "12 sealed raw artifacts", len(raw_files) == 12 and set(closure["raw"]) == raw_files and all(closure["raw"][name]["sha256"] == sha(run / name) and closure["raw"][name]["bytes"] == (run / name).stat().st_size for name in raw_files), sorted(raw_files))
        sh = invocation["source_hashes_before"]
        paths = {"input": CASE / f"{variant}-input.json", "parent": parent_path, "contract": CASE / "contract.json", "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(invocation["planned_check"]["executable"]), "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")}
        require(prefix + "source and executable sealed before/after", sh == closure["source_hashes_before"] == closure["source_hashes_after"] and all(sh[k] == sha(path) for k, path in paths.items()), sh)
        require(prefix + "selected input and parent fingerprints", invocation["input_sha256"] == expected_sha == sha(run / "input.json") and invocation["parent_sha256"] == PARENT_SHA)
        gui = invocation["gui"]
        require(prefix + "session-0 SSH mutex GUI guard", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and gui["pid"] == 13340 and gui["session_id"] == 1 and bool(gui["start_utc"]))
        names = ["import", "export", "calc", "jsonreport", "check_import_export"]
        require(prefix + "five serial guarded successful steps", [s["name"] for s in steps] == names and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] and s["started_utc"] <= s["completed_utc"] for s in steps) and all(steps[j]["completed_utc"] <= steps[j + 1]["started_utc"] for j in range(4)))
        require(prefix + "planned native commands match recorded steps", all(invocation["planned_commands"][j]["name"] == steps[j]["name"] and invocation["planned_commands"][j]["arguments"] == steps[j]["arguments"] for j in range(4)))
        imported = tabs(native(run / "input.json")); exported = tabs(native(run / "roundtrip-raw.json"))
        populated = {name for name, table in imported.items() if rows(table)}
        require(prefix + "16 populated source-table exact roundtrip", len(populated) == 16 and all(name in exported and imported[name]["columns"] == exported[name]["columns"] and imported[name]["instances"] == exported[name]["instances"] for name in populated))
        require(prefix + "import/export completed", "Import completed!" in (run / "import.log").read_text(encoding="utf-8-sig") and "Export completed!" in (run / "export.log").read_text(encoding="utf-8-sig"))
        log = (run / "run.log").read_text(encoding="utf-8-sig")
        warnings = re.findall(r"warning #(\d+)", log)
        require(prefix + "conversion zero errors and classified warnings", "Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in log and sorted(warnings) == ["108", "126", "126"] and "Saving results" in log, warnings)
        model = (run / "model.log").read_text(encoding="utf-8-sig")
        ev = events(model)
        hi = f"<{winner},TEACH-UNIT,0,0,0>"
        lo = f"<{loser},TEACH-UNIT,0,0,1>"
        a0, a1, b2 = "<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>", "<TEACH-AIR-02,2>"
        for mission, tag in ((winner, hi), (loser, lo)):
            timed(ev, prefix + mission + " order", rf"<TEACH-UNIT> mission ordered: {mission}$", 7)
            timed(ev, prefix + mission + " created", rf"{re.escape(tag)} mission created:", 7)
            timed(ev, prefix + mission + " activated", rf"{re.escape(tag)} mission activated, systems requested: 2", 7)
        for tag, aircraft in ((hi, a0), (hi, b2), (lo, a1)):
            timed(ev, prefix + tag + " allocates " + aircraft, rf"{re.escape(tag)} mission allocates system: {re.escape(aircraft)}$", 7)
            timed(ev, prefix + aircraft + " prep start", rf"{re.escape(aircraft)} preparation started, mission: {re.escape(tag)}$", 7)
            timed(ev, prefix + aircraft + " prep end", rf"{re.escape(aircraft)} preparation ended, mission: {re.escape(tag)}$", 7.5)
        require(prefix + "exact allocation/preparation counts", len(matches(ev, r"mission allocates system:")) == 3 and len(matches(ev, r"preparation started, mission:")) == 3 and len(matches(ev, r"preparation ended, mission:")) == 3)
        timed(ev, prefix + "loser waits to 7.83333", rf"{re.escape(lo)} mission waiting:  timeout at 7\.83333", 7)
        timed(ev, prefix + "loser cancels at 7.83333", rf"{re.escape(lo)} mission cancelled:", 7.83333)
        timed_pair(ev, prefix + "loser A1 returns ready", rf"{re.escape(a1)} nbr ready increased at unit:", 7.83333)
        timed(ev, prefix + "winner launches A0+B2", rf"{re.escape(hi)} mission starting, duration: 2 : {re.escape(a0)},{re.escape(b2)}$", 8)
        timed(ev, prefix + "winner out on station", rf"{re.escape(hi)} task starting: {re.escape(a0)},{re.escape(b2)}$", 8.5)
        timed(ev, prefix + "winner back from station", rf"{re.escape(hi)} task completed: {re.escape(a0)},{re.escape(b2)}$", 9.5)
        timed(ev, prefix + "winner success", rf"{re.escape(hi)} mission success:", 10)
        timed(ev, prefix + "winner completes A0+B2", rf"{re.escape(hi)} mission completed: {re.escape(a0)},{re.escape(b2)}$", 10)
        for aircraft in (a0, b2):
            timed_pair(ev, prefix + aircraft + " ready after return", rf"{re.escape(aircraft)} nbr ready increased at unit:", 10)
        require(prefix + "no extra mission launches/success/cancellations/failures", len(matches(ev, r"mission starting, duration:")) == 1 and len(matches(ev, r"mission success:")) == 1 and len(matches(ev, r"mission cancelled:")) == 1 and not matches(ev, r"(?i)(failure occurs|mission aborted|repair task .* started)"))
        require(prefix + "last ready roster has three exact instances", "systems ready: 3 :<TEACH-AIR-01,1>,<TEACH-AIR-01,0>,<TEACH-AIR-02,2>" in model)

        report = tabs(native(run / "report-raw.json"), "report")
        summary = rows(report["ResultSummary"])
        require(prefix + "summary one of two succeeds", len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 36 and all(close(summary[0][key], .5) for key in ("MTMF", "MSTF", "MSUF", "STMF")))
        system = rows(report["SystemResults"]); stock = rows(report["StockTotalResults"])
        require(prefix + "72 contiguous half-hour system and stock intervals", len(system) == len(stock) == 72 and all(close(system[j]["STINT"], j/2) and close(system[j]["ETINT"], (j+1)/2) and close(stock[j]["STINT"], j/2) and close(stock[j]["ETINT"], (j+1)/2) for j in range(72)))
        occupancy_ok = True
        counters_ok = True
        stock_ok = True
        for r, st in zip(system, stock):
            left, right = r["STINT"], r["ETINT"]
            assigned = (2*overlap(7, 10, left, right) + overlap(7, 7.833333333333333, left, right))/.5
            prep = 3*overlap(7, 7.5, left, right)/.5
            ready_prepared = (2*overlap(7.5, 8, left, right) + overlap(7.5, 7.833333333333333, left, right))/.5
            operating = 2*overlap(8, 10, left, right)/.5
            expected = {"NSYRY": 3-assigned, "NSYMA": assigned, "NSYMP": prep, "NSYMR": ready_prepared, "NSYMO": operating, "NSYA": 3, "STREQ": operating, "STACC": operating, "FTMO": operating/3}
            if not all(close(r[k], val) for k, val in expected.items()): occupancy_ok = False
            if r["NPSTA"] != (3 if left == 7 else 0) or r["NPSUC"] != (3 if left == 7.5 else 0) or any(r[k] != 0 for k in ("NFAIL", "NREPT", "NPMT", "NSYRP", "NSYPM", "NSYMT", "NSYMS", "NSYWR", "NSYWI")): counters_ok = False
            if st["PNB"] != 1 or any(st[k] != 0 for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")): stock_ok = False
        require(prefix + "event-derived occupancy reconciles all 72 bins", occupancy_ok)
        require(prefix + "preparation counts and no failure/maintenance across bins", counters_ok)
        require(prefix + "stock ledger 72 bins has no demand/backorder/wait", stock_ok)
        require(prefix + "report integrals and terminal ready", close(sum(r["NSYMP"]*.5 for r in system), 1.5) and close(sum(r["NSYMO"]*.5 for r in system), 4) and close(sum(r["STACC"]*.5 for r in system), 4) and close(system[-1]["NSYRY"], 3) and close(system[-1]["NSYMA"], 0))
        run_evidence[variant] = {"run_id": run_id, "input_sha256": expected_sha, "invocation_sha256": sha(run / "invocation.json"), "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"), "report_raw_sha256": sha(run / "report-raw.json"), "winner": winner, "loser": loser, "loser_cancel_h": 7.83333, "preparation_aircraft_hours": 1.5, "operation_aircraft_hours": 4, "terminal_ready": 3}

    result = {"schema": "simlox-a12-independent-native-review/v1", "authorship": "independent reviewer; no author implementation imports or native calls", "case_id": "A12", "version": "1.0.0", "decision": "bounded_native_behavior_accepted" if all(c["passed"] for c in checks) else "review_failed", "check_count": len(checks), "pass_count": sum(c["passed"] for c in checks), "fail_count": sum(not c["passed"] for c in checks), "checks": checks, "runs": run_evidence, "limits": ["Only these two deterministic, one-unit, three-aircraft CLI runs are evidenced.", "The lower-priority mission does allocate and fully prepare the spare A aircraft before cancellation; the raw log timestamps cancellation at latest preparation-start 7.83333, before scheduled 8.33333 delay bound.", "The log and aggregate system report support event identities and fleet occupancy; report rows do not independently expose per-mission prepared-aircraft state.", "No equal-priority tie, later readiness, resource contention, active-preparation confiscation, GUI behavior, or cross-engine parity is established."]}
    REVIEW.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"decision": result["decision"], "checks": result["check_count"], "passed": result["pass_count"], "failed": result["fail_count"], "review_sha256": sha(REVIEW), "script_sha256": sha(Path(__file__)), "failures": [c for c in checks if not c["passed"]]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

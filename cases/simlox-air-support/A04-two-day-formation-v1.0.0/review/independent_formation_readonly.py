"""Independent, standard-library replay of the sealed A04 CLI evidence.

This program reads frozen inputs and raw run files. It never imports the case
builder, checker, or author validator, and it never starts SIMLOX.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN_ID = "a04-two-day-form-v100-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
OUT = CASE / "review" / "independent-formation-2026-09-30.json"
PARENT = CASES / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"
PROFILE = CASES / "A09-hierarchical-operation-profile-v1.0.1" / "native-nested.json"
INPUT_SHA = "9e2eac17e0408903e099e6ce054ebf4b91db1ca79036afe29638ee8a41d40711"
PARENT_SHA = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"
PROFILE_SHA = "e795c5fcf563f8e42ab9e9cb161a925bec3b06157cbbecde7901e99bfec91d85"
STARTS = (8, 20, 32, 44)
ENDS = (10, 22, 34, 46)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native: bool = False) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    if native:
        # SIMLOX emits a comma after the final table in a JSON array. Remove
        # only commas outside string literals immediately before ] or }.
        out = []
        quote = escape = False
        for pos, char in enumerate(raw):
            if quote:
                out.append(char)
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    quote = False
            elif char == '"':
                quote = True
                out.append(char)
            elif char == "," and re.match(r"\s*[}\]]", raw[pos + 1 :]):
                continue
            else:
                out.append(char)
        raw = "".join(out)
    return json.loads(raw)


def table(doc: dict, root: str, name: str) -> dict:
    found = [x for x in doc[root]["tables"] if x["name"] == name]
    if len(found) != 1:
        raise ValueError(f"expected one {name}, found {len(found)}")
    return found[0]


def records(doc: dict, root: str, name: str) -> list[dict]:
    t = table(doc, root, name)
    columns = [x["name"] for x in t["columns"]]
    return [dict(zip(columns, row)) for inst in t["instances"] for row in inst["rows"]]


def main() -> None:
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        ok = actual == expected
        checks.append({"name": name, "passed": ok, **({} if ok else {
            "actual": repr(actual)[:600], "expected": repr(expected)[:600]})})

    child_path = CASE / "native-input.json"
    contract = load(CASE / "contract.json")
    diff = load(CASE / "parent-diff.json")
    child, parent, profile = load(child_path), load(PARENT), load(PROFILE)
    check("accepted A03 source SHA", sha(PARENT), PARENT_SHA)
    check("accepted A09 source SHA", sha(PROFILE), PROFILE_SHA)
    check("frozen child SHA", sha(child_path), INPUT_SHA)
    check("contract binds all three inputs", (
        contract["native_input_sha256"], contract["parent"]["input_sha256"],
        contract["instructional_prerequisite"]["input_sha256"]),
        (INPUT_SHA, PARENT_SHA, PROFILE_SHA))
    check("both accepted prerequisite signoffs exist", (
        (CASE / contract["parent"]["signoff"]).is_file(),
        (CASE / contract["instructional_prerequisite"]["signoff"]).is_file()), (True, True))
    a03_signoff = (CASE / contract["parent"]["signoff"]).read_text(encoding="utf-8")
    a09_signoff = (CASE / contract["instructional_prerequisite"]["signoff"]).read_text(encoding="utf-8")
    check("A03 accepted control states two-aircraft one-wave outcome", all(
        s in a03_signoff for s in (PARENT_SHA, "two sorties and four aircraft-hours",
                                "native_behavior_accepted_cli_scope")), True)
    check("A09 accepted control states four-wave one-aircraft outcome", all(
        s in a09_signoff for s in (PROFILE_SHA, "8/20/32/44", "10/22/34/46",
                                "eight aircraft-hours of operation",
                                "native_behavior_accepted_cli_scope")), True)
    check("diff binds all three inputs", (
        diff["child_input_sha256"], diff["parent_input_sha256"], diff["profile_source_sha256"]),
        (INPUT_SHA, PARENT_SHA, PROFILE_SHA))

    ptab = {t["name"]: t for t in parent["model"]["tables"]}
    ctab = {t["name"]: t for t in child["model"]["tables"]}
    changed = {name for name in ptab if ptab[name] != ctab[name]}
    expected_changed = {"ProblemDescription", "Control", "OperationProfile", "Unit", "ResultCollection"}
    check("same parent/child table set", set(ptab), set(ctab))
    check("exact five changed tables", changed, expected_changed)
    check("26 unchanged tables", len(set(ptab) - changed), 26)
    check("diff changed table list", set(diff["changed_tables_only"]), expected_changed)
    check("diff no added tables", diff["added_tables_only"], [])
    check("diff reproduces every changed table", all(
        diff["changed_tables"][name]["parent"] == ptab[name]
        and diff["changed_tables"][name]["child"] == ctab[name]
        for name in changed), True)
    check("nested profile rows copied exactly", records(child, "model", "OperationProfile"),
          records(profile, "model", "OperationProfile"))
    check("A03 formation counts retained", (
        records(child, "model", "MissionType")[0]["MNOS"],
        records(child, "model", "MissionType")[0]["NOS"],
        records(child, "model", "SystemDeployment")[0]["QTYPS"]), (2, 2, 2))
    check("profile root and two child rows", [
        (r["PRID"], r["SPRID"], r["STIM"], r["IQTY"], r["IPER"])
        for r in records(child, "model", "OperationProfile")], [
        ("BASIC-SCHEDULE", "A09-DAILY-TWO-WAVE", 0, 2, 48),
        ("A09-DAILY-TWO-WAVE", "BASIC-MISSION", 8, 1, 0),
        ("A09-DAILY-TWO-WAVE", "BASIC-MISSION", 20, 1, 0)])
    control = records(child, "model", "Control")[0]
    check("one fixed-seed 48h run", (control["NREPS"], control["RSEED"],
                                      control["SIMPE"], control["RCINT"], control["RCEND"]),
          (1, "1", 48, 0.5, 48))
    check("both result windows end at 48h", [
        (r["RTYPE"], r["RCINT"], r["RCSTA"], r["RCEND"])
        for r in records(child, "model", "ResultCollection")],
        [("MISSION", 0.5, 0, 48), ("SYSTEM", 0.5, 0, 48)])
    check("no failure/PM enabling", (control["ENPM"], records(child, "model", "System")[0]["FRT"]),
          ("N", 0))

    invocation, closure, steps = [load(RUN / n) for n in
                                  ("invocation.json", "closure.json", "steps.json")]
    check("copied run input SHA and bytes", (sha(RUN / "input.json"),
          (RUN / "input.json").read_bytes() == child_path.read_bytes()), (INPUT_SHA, True))
    check("invocation run/source identities", (invocation["case_id"], invocation["run_id"],
        invocation["input_sha256"], invocation["parent_sha256"], invocation["profile_source_sha256"]),
        ("A04", RUN_ID, INPUT_SHA, PARENT_SHA, PROFILE_SHA))
    check("session-0 SSH with sshd ancestor", (
        invocation["execution_mode"], invocation["session_id"], invocation["ssh_connection_present"],
        "sshd.exe" in [s.lower() for s in invocation["ssh_ancestor_names"]]),
        ("ssh_cli_v1", 0, True, True))
    check("host queue and preserved GUI identity", (
        invocation["queue_mutex"], invocation["gui"]["pid"], invocation["gui"]["session_id"],
        bool(invocation["gui"]["start_utc"])),
        ("Global\\SimloxIssue18NativeQueue", 13340, 1, True))
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    check("runner preflight and GUI assertions present", all(s in runner for s in (
        "SSH_CONNECTION", "sshd.exe", "WaitOne(0)", "Global\\SimloxIssue18NativeQueue",
        "13340", "Assert-Gui", "session-0 SSH required")), True)
    check("invocation seal", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    check("closure identity and no error", (closure["run_id"], closure["error"]), (RUN_ID, None))
    check("source hashes unchanged in run", closure["source_hashes_before"],
          closure["source_hashes_after"])
    check("invocation and closure source hashes agree", invocation["source_hashes_before"],
          closure["source_hashes_before"])
    source_files = {"input": child_path, "parent": PARENT, "profile_source": PROFILE,
                    "contract": CASE / "contract.json", "builder": CASE / "build.py",
                    "checker": CASE / "check_roundtrip.py",
                    "runner_script": CASE / "run_native_ssh.ps1"}
    for name, path in source_files.items():
        check(f"source seal {name}", closure["source_hashes_before"][name], sha(path))
    check("raw closure file set", set(closure["raw"]),
          {p.name for p in RUN.iterdir() if p.is_file()} - {"invocation.json", "closure.json"})
    for name, stamp in closure["raw"].items():
        path = RUN / name
        check(f"raw seal {name}", (stamp["bytes"], stamp["sha256"]),
              (path.stat().st_size, sha(path)))
    check("five successful steps, GUI preserved", [
        (x["name"], x["status"], x["exit_code"], x["gui_preserved"])
        for x in steps], [(n, "completed", 0, True) for n in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    check("CLI arguments bound to run", [x["arguments"] == y["arguments"] for x, y in
          zip(steps[:4], invocation["planned_commands"])], [True] * 4)

    native = load(RUN / "roundtrip-raw.json", native=True)
    source_populated = [t for t in child["model"]["tables"]
                        if any(inst["rows"] for inst in t["instances"])]
    check("13 row-containing source tables", len(source_populated), 13)
    check("native export retains every source business table", all(
        table(native, "model", t["name"])["columns"] == t["columns"]
        and table(native, "model", t["name"])["instances"] == t["instances"]
        for t in source_populated), True)
    roundcheck = load(RUN / "roundtrip-validation.json")
    check("native checker agrees on roundtrip", (roundcheck["passed"],
          roundcheck["differences"], roundcheck["source_sha256"],
          roundcheck["roundtrip_sha256"]), (True, [], INPUT_SHA,
          sha(RUN / "roundtrip-raw.json")))
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check("conversion totals", re.findall(
        r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
        runlog), [("0", "2", "0")])
    check("conversion warning codes", sorted(re.findall(r"warning #(\d+)", runlog)),
          ["108", "126"])

    lines = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    check("four mission orders, creations, launches, successes, completions", tuple(
        sum(token in line for line in lines) for token in
        ("mission ordered:", "mission created:", "mission starting, duration:",
         "mission success:", "mission completed:")), (4, 4, 4, 4, 4))
    check("no abort/cancel/delay/failure/service events", any(re.search(
        r"mission (?:abort|cancel|delay)|critical random failure added|repair task started|PM task started",
        line, re.I) for line in lines), False)
    for j, (start, end) in enumerate(zip(STARTS, ENDS)):
        mid = f"<BASIC-MISSION,TEACH-UNIT,0,0,{j}>"
        check(f"wave{j} ordered/prepared on time", (
            sum(f"Time: {start-1} <TEACH-UNIT> mission ordered:" in x for x in lines),
            sum(f"Time: {start-1} {mid} mission created:" in x for x in lines)), (1, 1))
        check(f"wave{j} requests and allocates both aircraft", (
            sum(f"{mid} mission activated, systems requested: 2" in x for x in lines),
            sorted(re.findall(r"mission allocates system: <TEACH-AIR-01,([01])>",
                "\n".join(x for x in lines if mid in x)))), (1, ["0", "1"]))
        check(f"wave{j} joint start and success", (
            sum(f"Time: {start} {mid} mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in x for x in lines),
            sum(f"Time: {end} {mid} mission success:" in x for x in lines),
            sum(f"Time: {end} {mid} mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in x for x in lines)),
            (1, 1, 1))
        for aircraft in (0, 1):
            check(f"wave{j} aircraft{aircraft} ready on return", sum(
                f"Time: {end} <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,{aircraft}>" in x
                for x in lines), 2)
    check("eight individual return events", sum(
        "System arrives <TEACH-AIR-01," in x and "mission success" in x for x in lines), 8)
    check("terminal two ready", any(
        x.startswith("Time: 46 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
        for x in lines), True)

    report = load(RUN / "report-raw.json", native=True)
    check("report business tables", [x["name"] for x in report["report"]["tables"]],
          ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"])
    sysrows = records(report, "report", "SystemResults")
    stock = records(report, "report", "StockTotalResults")
    check("96 aligned half-hour system/stock bins", (
        len(sysrows), len(stock), all(r["STINT"] == i / 2 and r["ETINT"] == (i+1)/2
        for i, r in enumerate(sysrows)), all(r["STINT"] == i / 2 and r["ETINT"] == (i+1)/2
        for i, r in enumerate(stock))), (96, 96, True, True))
    for j, (start, end) in enumerate(zip(STARTS, ENDS)):
        before = [r for r in sysrows if start-1 <= r["STINT"] < start]
        during = [r for r in sysrows if start <= r["STINT"] < end]
        check(f"wave{j} preparation then two-aircraft mission bins", (
            [(r["NSYRY"], r["NSYMA"], r["NSYMO"], r["NSYMR"]) for r in before],
            [(r["NSYRY"], r["NSYMA"], r["NSYMO"], r["STACC"]) for r in during]),
            ([(0, 2, 0, 2)] * 2, [(0, 2, 2, 2)] * 4))
    check("all other bins two aircraft ready", all(
        (r["NSYRY"], r["NSYMA"], r["NSYMO"]) == (2, 0, 0)
        for r in sysrows if not any(start-1 <= r["STINT"] < end
                                     for start, end in zip(STARTS, ENDS))), True)
    check("aircraft-hour and availability ledgers", (
        sum(r["NSYMO"] * 0.5 for r in sysrows),
        sum(r["NSYMA"] * 0.5 for r in sysrows),
        sum(r["NSYA"] * 0.5 for r in sysrows),
        sysrows[-1]["NSYRY"]), (16, 24, 96, 2))
    check("no failure/repair/PM/wait in system ledger", all(
        (r[k] or 0) == 0 for r in sysrows for k in
        ("NFAIL", "NREPT", "NSYRP", "NSYPM", "NSYWI", "NSYWR", "NDAM")), True)
    check("stock ledger has no demand or backorder", all(
        (r[k] or 0) == 0 for r in stock for k in
        ("NBO", "NDF", "NDD", "NDR", "NDP", "NWT")), True)
    check("report summary single replication 0-48", (
        records(report, "report", "ResultSummary")[0]["NREP"],
        records(report, "report", "ResultSummary")[0]["RTILW"],
        records(report, "report", "ResultSummary")[0]["RTIUP"]), (1, 0, 48))

    result = {
        "schema": "simlox-a04-independent-formation-readonly/v1",
        "reviewer": "Independent standard-library replay; no author imports or native invocation",
        "case_id": "A04", "run_id": RUN_ID,
        "passed": all(c["passed"] for c in checks),
        "passed_count": sum(c["passed"] for c in checks),
        "failed_count": sum(not c["passed"] for c in checks),
        "failed": [c for c in checks if not c["passed"]],
        "checks": checks,
        "hashes": {"child_input": sha(child_path), "parent_input": sha(PARENT),
                   "profile_input": sha(PROFILE), "invocation": sha(RUN / "invocation.json"),
                   "closure": sha(RUN / "closure.json"), "raw_model_log": sha(RUN / "model.log"),
                   "raw_report": sha(RUN / "report-raw.json")},
        "observed": {"waves": list(zip(STARTS, ENDS)), "mission_successes": 4,
                     "aircraft_sorties": 8, "aircraft_mission_hours": 16,
                     "report_bins": 96, "terminal_ready_aircraft": 2,
                     "conversion_errors": 0, "conversion_warnings": [108, 126]},
        "comparison_controls": {
            "A03_accepted_one_wave": "two aircraft, two sorties, four mission aircraft-hours at 8-10",
            "A09_accepted_four_wave": "one aircraft, four starts 8/20/32/44, eight mission aircraft-hours",
            "A04_observed_combination": "same A09 wave times with both A03 aircraft in each wave; eight sorties and 16 mission aircraft-hours"
        },
        "decision": "bounded_cli_formation_accepted" if all(c["passed"] for c in checks)
                    else "review_rejected_pending_resolution",
        "limits": [
            "One fixed seed, two aircraft, four fixed waves, no failures, PM or resource contention.",
            "A03 and A09 accepted signoffs and source hashes were checked; their original raw runs are not present in this checkout and were not re-executed.",
            "Native report is JSON-like with a trailing comma, so the parser removes only out-of-string trailing commas before parsing.",
            "No GUI visual inspection or cross-engine equivalence is established by this CLI replay."
        ],
        "publication_state": "independent_review_only"
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed": result["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()

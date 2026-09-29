"""Independent standard-library replay of A05 v1.0.1's three sealed runs.

Read-only: no imports from author code, native executable, or GUI interaction.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
OUT = CASE / "review" / "independent-continuous-2026-09-30.json"
PARENT = CASES / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"
OLD = CASES / "A05-continuous-baseline-v1.0.0"
PARENT_SHA = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"
VARIANTS = {
    "fixed": ("native-fixed-control.json", "a05-fixed-four-hour-v101-ssh-20260930-01",
              "577f95bc8716b7191a783f3ec06ed24c50d61362df1dbf434e9fba846be58b0d"),
    "continuous": ("native-continuous.json", "a05-continuous-four-hour-v101-ssh-20260930-01",
                   "997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea"),
    "shortage": ("native-initial-shortage.json", "a05-initial-shortage-v101-ssh-20260930-01",
                 "95d2c855f0e7a99f9892053a89fdff99501dfab78b50bac0265b9d4512a67cca"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native: bool = False) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    if native:
        out = []
        quoted = escaped = False
        for i, ch in enumerate(raw):
            if quoted:
                out.append(ch)
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    quoted = False
            elif ch == '"':
                quoted = True
                out.append(ch)
            elif ch == "," and re.match(r"\s*[}\]]", raw[i + 1 :]):
                continue
            else:
                out.append(ch)
        raw = "".join(out)
    return json.loads(raw)


def tables(doc: dict, root: str) -> dict:
    entries = doc[root]["tables"]
    found = {x["name"]: x for x in entries}
    if len(found) != len(entries):
        raise ValueError("duplicate table names")
    return found


def rows(doc: dict, root: str, name: str) -> list[dict]:
    tab = tables(doc, root)[name]
    cols = [x["name"] for x in tab["columns"]]
    return [dict(zip(cols, row)) for inst in tab["instances"] for row in inst["rows"]]


def cells_delta(a: dict, b: dict) -> list[tuple]:
    before, after = tables(a, "model"), tables(b, "model")
    if set(before) != set(after):
        raise ValueError("table set differs")
    changes = []
    for name in sorted(before):
        x, y = before[name], after[name]
        if x["columns"] != y["columns"]:
            raise ValueError(f"{name} schema differs")
        xr, yr = rows(a, "model", name), rows(b, "model", name)
        if len(xr) != len(yr):
            raise ValueError(f"{name} row count differs")
        for i, (one, two) in enumerate(zip(xr, yr)):
            for field in one:
                if one[field] != two[field]:
                    changes.append((name, i, field, one[field], two[field]))
    return changes


def main() -> None:
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        ok = actual == expected
        checks.append({"name": name, "passed": ok, **({} if ok else {
            "actual": repr(actual)[:650], "expected": repr(expected)[:650]})})

    contract = load(CASE / "contract.json")
    exact = load(CASE / "exact-diffs.json")
    parent = load(PARENT)
    docs = {k: load(CASE / VARIANTS[k][0]) for k in VARIANTS}
    check("accepted A03 parent SHA", sha(PARENT), PARENT_SHA)
    check("accepted A03 signoff exists", (CASE / contract["parent"]["signoff"]).is_file(), True)
    check("contract parent binding", contract["parent"]["input_sha256"], PARENT_SHA)
    for variant, (filename, _, digest) in VARIANTS.items():
        check(f"{variant} frozen source SHA", sha(CASE / filename), digest)
    check("contract binds three frozen inputs", contract["inputs"], {
        "fixed_control": VARIANTS["fixed"][2],
        "continuous_control": VARIANTS["continuous"][2],
        "continuous_initial_shortage": VARIANTS["shortage"][2]})

    pairs = [
        ("A03_to_fixed", parent, docs["fixed"], PARENT_SHA, VARIANTS["fixed"][2],
         [("Control", 0, "RCEND", 36, 16), ("Control", 0, "SIMPE", 36, 16),
          ("MissionType", 0, "DESCR", "Two-hour generic mission", "Four-hour teaching mission"),
          ("MissionType", 0, "DURN", 2, 4),
          ("ProblemDescription", 0, "PDESC", "A03 two-aircraft, one-wave teaching case; no J35/F35 equivalence",
           "A05 fixed four-hour two-aircraft control"),
          ("ResultCollection", 0, "RCEND", 36, 16),
          ("ResultCollection", 1, "RCEND", 36, 16),
          ("Unit", 0, "DESCR", "One-aircraft teaching unit", "Two-aircraft teaching unit")]),
        ("fixed_to_continuous", docs["fixed"], docs["continuous"],
         VARIANTS["fixed"][2], VARIANTS["continuous"][2],
         [("MissionType", 0, "MPAT", None, "CONTINUOUS"),
          ("MissionType", 0, "TFOUT", 0.25, None),
          ("MissionType", 0, "TFRET", 0.25, None),
          ("ProblemDescription", 0, "PDESC", "A05 fixed four-hour two-aircraft control",
           "A05 continuous four-hour two-aircraft control")]),
        ("continuous_to_shortage", docs["continuous"], docs["shortage"],
         VARIANTS["continuous"][2], VARIANTS["shortage"][2],
         [("ProblemDescription", 0, "PDESC", "A05 continuous four-hour two-aircraft control",
           "A05 continuous four-hour initial one-aircraft shortage"),
          ("SystemDeployment", 0, "QTYPS", 2, 1),
          ("Unit", 0, "DESCR", "Two-aircraft teaching unit", "One-aircraft teaching unit")]),
    ]
    for name, before, after, before_sha, after_sha, wanted in pairs:
        recorded = exact["deltas"][name]
        actual = cells_delta(before, after)
        check(f"{name} exact cell delta", sorted(actual), sorted(wanted))
        check(f"{name} manifest hashes", (recorded["before_sha256"], recorded["after_sha256"]),
              (before_sha, after_sha))
        check(f"{name} manifest table delta", (
            set(recorded["changed_tables_only"]), recorded["unchanged_table_count"]),
            ({x[0] for x in wanted}, 31-len({x[0] for x in wanted})))
        a, b = tables(before, "model"), tables(after, "model")
        check(f"{name} manifest row images", all(
            recorded["changed_tables"][t]["before"] == a[t]
            and recorded["changed_tables"][t]["after"] == b[t]
            for t in recorded["changed_tables_only"]), True)
    for variant, doc in docs.items():
        control = rows(doc, "model", "Control")[0]
        mission = rows(doc, "model", "MissionType")[0]
        deployment = rows(doc, "model", "SystemDeployment")[0]
        check(f"{variant} core mission configuration", (
            control["NREPS"], control["RSEED"], control["SIMPE"], control["RCINT"],
            mission["DURN"], mission["NOS"], mission["MNOS"], deployment["QTYPS"]),
            (1, "1", 16, 0.5, 4, 2, 2, 1 if variant == "shortage" else 2))
        check(f"{variant} profile launch hour", rows(doc, "model", "OperationProfile")[0]["STIM"], 8)
        check(f"{variant} no failure or PM", (
            control["ENPM"], rows(doc, "model", "System")[0]["FRT"]), ("N", 0))

    guard = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    check("runner has SSH, queue and GUI guards", all(s in guard for s in (
        "SSH_CONNECTION", "sshd.exe", "WaitOne(0)", "Global\\SimloxIssue18NativeQueue",
        "13340", "Assert-Gui", "session-0 SSH required")), True)
    observed = {}
    for variant, (filename, run_id, digest) in VARIANTS.items():
        run = CASE / "runs" / run_id
        inv, closure, steps = [load(run / x) for x in
                               ("invocation.json", "closure.json", "steps.json")]
        check(f"{variant} copied input exact bytes", (
            sha(run / "input.json"),
            (run / "input.json").read_bytes() == (CASE / filename).read_bytes()), (digest, True))
        check(f"{variant} invocation identity", (
            inv["case_id"], inv["case_version"], inv["variant"], inv["run_id"],
            inv["input_sha256"], inv["parent_sha256"]),
            ("A05", "1.0.1-candidate", variant, run_id, digest, PARENT_SHA))
        check(f"{variant} session-0 SSH and GUI guard", (
            inv["execution_mode"], inv["session_id"], inv["ssh_connection_present"],
            "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]],
            inv["queue_mutex"], inv["gui"]["pid"], inv["gui"]["session_id"],
            bool(inv["gui"]["start_utc"])),
            ("ssh_cli_v1", 0, True, True, "Global\\SimloxIssue18NativeQueue", 13340, 1, True))
        check(f"{variant} invocation SHA in closure", closure["invocation_sha256"],
              sha(run / "invocation.json"))
        check(f"{variant} clean closure and stable source", (
            closure["run_id"], closure["error"],
            closure["source_hashes_before"] == closure["source_hashes_after"]),
            (run_id, None, True))
        check(f"{variant} invocation/closure source agreement", inv["source_hashes_before"],
              closure["source_hashes_before"])
        src = {"parent": PARENT, "fixed": CASE / VARIANTS["fixed"][0],
               "continuous": CASE / VARIANTS["continuous"][0],
               "shortage": CASE / VARIANTS["shortage"][0],
               "contract": CASE / "contract.json", "builder": CASE / "build.py",
               "checker": CASE / "check_roundtrip.py",
               "runner_script": CASE / "run_native_ssh.ps1"}
        for key, path in src.items():
            check(f"{variant} source seal {key}", closure["source_hashes_before"][key], sha(path))
        check(f"{variant} selected input seal", closure["source_hashes_before"]["input"], digest)
        check(f"{variant} raw closure file set", set(closure["raw"]),
              {p.name for p in run.iterdir() if p.is_file()} - {"closure.json", "invocation.json"})
        for name, stamp in closure["raw"].items():
            path = run / name
            check(f"{variant} raw seal {name}", (stamp["bytes"], stamp["sha256"]),
                  (path.stat().st_size, sha(path)))
        check(f"{variant} five successful steps, GUI preserved", [
            (x["name"], x["status"], x["exit_code"], x["gui_preserved"])
            for x in steps], [(n, "completed", 0, True) for n in
            ("import", "export", "calc", "jsonreport", "check_import_export")])
        check(f"{variant} CLI commands bound to invocation", [
            x["arguments"] == y["arguments"] for x, y in zip(steps[:4], inv["planned_commands"])],
            [True] * 4)
        export = load(run / "roundtrip-raw.json", native=True)
        populated = [x for x in docs[variant]["model"]["tables"]
                     if any(inst["rows"] for inst in x["instances"])]
        check(f"{variant} 13 source row-containing tables", len(populated), 13)
        check(f"{variant} exact source business rows in export", all(
            tables(export, "model")[x["name"]]["columns"] == x["columns"]
            and tables(export, "model")[x["name"]]["instances"] == x["instances"]
            for x in populated), True)
        rt = load(run / "roundtrip-validation.json")
        check(f"{variant} checker roundtrip agreement", (
            rt["passed"], rt["differences"], rt["source_sha256"], rt["roundtrip_sha256"]),
            (True, [], digest, sha(run / "roundtrip-raw.json")))
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check(f"{variant} conversion totals", re.findall(
            r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
            runlog), [("0", "2", "0")])
        check(f"{variant} warning codes", sorted(re.findall(r"warning #(\d+)", runlog)),
              ["108", "126"])
        events = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
        mid = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
        check(f"{variant} order/create/request 2 at hour 7", (
            sum("Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION" in x for x in events),
            sum(f"Time: 7 {mid} mission created:" in x for x in events),
            sum(f"Time: 7 {mid} mission activated, systems requested: 2" in x for x in events)),
            (1, 1, 1))
        expected_aircraft = "<TEACH-AIR-01,0>" if variant == "shortage" else \
                            "<TEACH-AIR-01,0>,<TEACH-AIR-01,1>"
        check(f"{variant} on-time four-hour launch", sum(
            f"Time: 8 {mid} mission starting, duration: 4 : {expected_aircraft}" in x
            for x in events), 1)
        check(f"{variant} hour-12 success/completion markers", (
            sum(f"Time: 12 {mid} mission success:" in x for x in events),
            sum(f"Time: 12 {mid} mission completed: {expected_aircraft}" in x for x in events)),
            (1, 1))
        check(f"{variant} no abort/cancel/random failure/repair", any(re.search(
            r"mission (?:abort|cancel)|critical random failure added|repair task started|PM task started",
            x, re.I) for x in events), False)
        check(f"{variant} allocation identities", sorted(re.findall(
            r"mission allocates system: <TEACH-AIR-01,([01])>", "\n".join(events))),
            ["0"] if variant == "shortage" else ["0", "1"])
        check(f"{variant} return and terminal readiness", (
            sum("System arrives <TEACH-AIR-01," in x and "mission success" in x for x in events),
            any(x.startswith(f"Time: 12 <TEACH-UNIT at <BASE-01,0>> systems ready: "
                             f"{1 if variant == 'shortage' else 2} :") for x in events)),
            (1 if variant == "shortage" else 2, True))
        report = load(run / "report-raw.json", native=True)
        check(f"{variant} report table names", list(tables(report, "report")),
              ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"])
        summary = rows(report, "report", "ResultSummary")[0]
        sysrows = rows(report, "report", "SystemResults")
        stock = rows(report, "report", "StockTotalResults")
        check(f"{variant} 32 aligned half-hour bins", (
            len(sysrows), len(stock),
            all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(sysrows)),
            all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(stock))),
            (32, 32, True, True))
        strength = 1 if variant == "shortage" else 2
        check(f"{variant} preparation allocation 7-8", [
            (r["NSYRY"], r["NSYMA"], r["NSYMO"], r["NSYMR"])
            for r in sysrows if 7 <= r["STINT"] < 8], [(0, strength, 0, strength)] * 2)
        check(f"{variant} operating/holding bins 8-12", [
            (r["NSYRY"], r["NSYMA"], r["NSYMO"], r["STACC"])
            for r in sysrows if 8 <= r["STINT"] < 12],
            [(0, strength, 0 if variant == "shortage" else 2,
              0 if variant == "shortage" else 2)] * 8)
        check(f"{variant} ready outside 7-12", all(
            (r["NSYRY"], r["NSYMA"], r["NSYMO"]) == (strength, 0, 0)
            for r in sysrows if not 7 <= r["STINT"] < 12), True)
        check(f"{variant} terminal ready and operation hours", (
            sysrows[-1]["NSYRY"], sum(r["NSYMO"] * 0.5 for r in sysrows)),
            (strength, 0 if variant == "shortage" else 8))
        check(f"{variant} report summary mission-status fields", (
            summary["NREP"], summary["RTILW"], summary["RTIUP"],
            summary["MTMF"], summary["MSTF"], summary["MSUF"], summary["STMF"]),
            (1, 0, 16, 0 if variant == "shortage" else 1,
             1 if variant == "fixed" else 0, 1 if variant == "fixed" else 0,
             0 if variant == "shortage" else 1))
        check(f"{variant} no system failure/maintenance/wait", all(
            (r[k] or 0) == 0 for r in sysrows for k in
            ("NFAIL", "NREPT", "NSYRP", "NSYPM", "NSYWI", "NSYWR", "NDAM")), True)
        check(f"{variant} no stock demand/backorder/wait", all(
            (r[k] or 0) == 0 for r in stock for k in
            ("NBO", "NDF", "NDD", "NDR", "NDP", "NWT")), True)
        observed[variant] = {
            "run_id": run_id, "input_sha256": digest,
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "model_log_sha256": sha(run / "model.log"),
            "report_raw_sha256": sha(run / "report-raw.json"),
            "event_success_marker_hour": 12,
            "summary_MTMF": summary["MTMF"],
            "summary_MSTF": summary["MSTF"], "summary_MSUF": summary["MSUF"],
            "summary_STMF": summary["STMF"],
            "aircraft_operation_hours": sum(r["NSYMO"] * 0.5 for r in sysrows),
            "terminal_ready_aircraft": sysrows[-1]["NSYRY"]}
        if variant == "shortage":
            check("shortage suspended at start", sum(
                f"Time: 8 {mid} mission suspended: <TEACH-AIR-01,0>" in x
                for x in events), 1)
            check("shortage only resume marker at terminal hour", [
                x for x in events if "mission resumed:" in x],
                [f"Time: 12 {mid} mission resumed: <TEACH-AIR-01,0>(Susp)"])
            check("shortage zero mission operation and task duration", (
                sum(r["NSYMO"] for r in sysrows),
                sum("task starting:" in x and x.startswith("Time: 12 ") for x in events),
                sum("task completed:" in x and x.startswith("Time: 12 ") for x in events)),
                (0, 1, 1))
        else:
            check(f"{variant} has no suspended/resumed mission event", any(
                "mission suspended:" in x or "mission resumed:" in x for x in events), False)
    check("fixed and full continuous system/stock rows coincide", (
        rows(load(CASE / "runs" / VARIANTS["fixed"][1] / "report-raw.json", native=True),
             "report", "SystemResults") ==
        rows(load(CASE / "runs" / VARIANTS["continuous"][1] / "report-raw.json", native=True),
             "report", "SystemResults"),
        rows(load(CASE / "runs" / VARIANTS["fixed"][1] / "report-raw.json", native=True),
             "report", "StockTotalResults") ==
        rows(load(CASE / "runs" / VARIANTS["continuous"][1] / "report-raw.json", native=True),
             "report", "StockTotalResults")), (True, True))

    old_run = OLD / "runs" / contract["excluded_probe"]["run_id"]
    old_input = OLD / "native-continuous.json"
    old_log = (old_run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check("excluded v1.0.0 input SHA", (
        sha(old_input), sha(old_run / "input.json"),
        contract["excluded_probe"]["input_sha256"]),
        ("260c9508c5c39ce0d31441510b73084c563e4000f3870c105eb769e83d88fef8",) * 3)
    check("excluded v1.0.0 has invalid continuous out/back fractions", (
        rows(load(old_input), "model", "MissionType")[0]["MPAT"],
        rows(load(old_input), "model", "MissionType")[0]["TFOUT"],
        rows(load(old_input), "model", "MissionType")[0]["TFRET"]),
        ("CONTINUOUS", 0.25, 0.25))
    check("excluded converter #335 and 1 error", (
        "(error #335)" in old_log,
        re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+)", old_log)),
        (True, [("1", "2")]))
    old_closure = load(old_run / "closure.json")
    check("excluded run has no completed result", (
        old_closure["error"], (old_run / "model.sxo").stat().st_size,
        (old_run / "report-raw.json").exists()),
        ("calc output model.sxo absent/empty", 4, False))
    check("excluded closure raw seals", all(
        (old_run / name).stat().st_size == stamp["bytes"]
        and sha(old_run / name) == stamp["sha256"]
        for name, stamp in old_closure["raw"].items()), True)

    passed = all(x["passed"] for x in checks)
    result = {
        "schema": "simlox-a05-v101-independent-continuous-readonly/v1",
        "reviewer": "Independent standard-library raw replay; no author imports or native invocation",
        "passed": passed, "passed_count": sum(x["passed"] for x in checks),
        "failed_count": sum(not x["passed"] for x in checks),
        "failed": [x for x in checks if not x["passed"]], "checks": checks,
        "parent_input_sha256": sha(PARENT), "runs": observed,
        "excluded_v100": {"converter_error": 335, "input_sha256": sha(old_input),
                           "run_log_sha256": sha(old_run / "run.log"),
                           "closure_sha256": sha(old_run / "closure.json")},
        "decision": "bounded_initial_shortage_and_control_cli_evidence_accepted_with_metric_discordance"
                    if passed else "review_rejected_pending_resolution",
        "full_A05_method_status": "unaccepted",
        "interpretation": [
            "Fixed and full-strength continuous runs have identical two-aircraft operation and stock ledgers. Fixed ResultSummary MSTF/MSUF=1/1, continuous MSTF/MSUF=0/0 despite the latter's hour-12 log success marker; the metric disagreement remains unresolved.",
            "Initial shortage starts and suspends at hour 8 with one aircraft allocated. The only resume marker is at terminal hour 12, immediately before zero-duration task and success markers; all 8-12 operation bins and STACC are zero. This does not establish effective resumption or a successful operating mission.",
            "The v1.0.0 #335 probe is excluded; its model.sxo is a four-byte stub and no report exists. Clearing TFOUT/TFRET is part of the corrected continuous inputs."
        ],
        "limits": [
            "One seed, one initial-shortage pattern, no mid-mission loss, replacement or sustained resumption.",
            "No failures, repair, PM, external-resource contention, GUI visual verification or cross-engine equivalence.",
            "Native JSON report requires read-only removal of out-of-string trailing commas for parsing."
        ],
        "publication_state": "independent_review_only"
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "passed_count": result["passed_count"],
                      "failed": result["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()

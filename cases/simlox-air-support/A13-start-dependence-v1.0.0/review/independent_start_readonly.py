"""Independent, read-only replay of the sealed A13 START-dependence pair.

Only this reviewer JSON is written. No author code or native executable is loaded.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
PARENT = ROOT / "A02-single-aircraft-repeated-missions" / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
OUT = Path(__file__).with_name("independent-start-2026-09-30.json")
RUN_NAMES = {v: f"a13-{v}-20260930-03" for v in ("control", "dependent")}
PARENT_SHA = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
GUI = {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"}
checks: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def obj(path: Path, native: bool = False):
    raw = path.read_text(encoding="utf-8-sig")
    # SIMLOX report export emits a trailing comma after the final table.
    if native:
        raw = re.sub(r",\s*([}\]])", r"\1", raw)
    return json.loads(raw)


def ck(name: str, condition: bool, detail=None) -> None:
    entry = {"name": name, "passed": bool(condition)}
    if not condition and detail is not None:
        entry["detail"] = detail
    checks.append(entry)


def tables(doc, root="model"):
    return {t["name"]: t for t in doc[root]["tables"]}


def rows(table):
    return [row for instance in table.get("instances", []) for row in instance.get("rows", [])]


def fields(table, row):
    return dict(zip((c["name"] for c in table["columns"]), row))


def by_field(table, key):
    return {fields(table, r)[key]: fields(table, r) for r in rows(table)}


def event(log: str, mission: str, phrase: str):
    found = re.findall(rf"^Time: ([0-9.]+) <({mission},TEACH-UNIT,0,0,[0-9]+)> {re.escape(phrase)}", log, re.M)
    return [(float(t), ident) for t, ident in found]


def report_table(report, name):
    return tables(report, "report")[name]


def series(table, field):
    idx = [c["name"] for c in table["columns"]].index(field)
    return [r[idx] for r in rows(table)]


def main() -> None:
    contract = obj(CASE / "contract.json")
    parent = obj(PARENT)
    inputs = {v: obj(CASE / f"{v}-input.json") for v in RUN_NAMES}
    pt = tables(parent)
    ct, dt = (tables(inputs[v]) for v in ("control", "dependent"))
    ck("accepted A02 parent fingerprint", sha(PARENT) == PARENT_SHA)
    ck("installed manual fingerprint and cited pages", sha(MANUAL) == MANUAL_SHA and contract["source"]["pages"] == [188, 287, 288, 289] and contract["source"]["manual_sha256"] == MANUAL_SHA)
    ck("contract describes only explicit START pair", contract["case_id"] == "A13" and contract["configuration"]["aircraft"] == 2 and contract["configuration"]["control"] == "same model without MissionDependence row")

    allowed = {"ProblemDescription", "Control", "SystemDeployment", "Unit", "MissionType", "OperationProfile", "ResultCollection"}
    ck("control contains original A02 table set", set(ct) == set(pt))
    ck("control modifies only seven planned tables", {n for n in pt if pt[n] != ct[n]} == allowed)
    ck("dependent adds only MissionDependence table", set(dt) == set(ct) | {"MissionDependence"} and {n for n in ct if ct[n] != dt[n]} == {"ProblemDescription"})
    ck("unchanged parent tables byte-equivalent as JSON", all(ct[n] == pt[n] for n in set(pt) - allowed))
    ck("two aircraft with matching explicit unit", fields(dt["SystemDeployment"], rows(dt["SystemDeployment"])[0])["QTYPS"] == 2 and fields(dt["Unit"], rows(dt["Unit"])[0])["UNID"] == "TEACH-UNIT")
    mts = by_field(dt["MissionType"], "MTID")
    ops = by_field(dt["OperationProfile"], "SPRID")
    ck("two default-FIXED mission definitions and durations", set(mts) == {"RECON", "FOLLOW"} and mts["RECON"]["DURN"] == 4 and mts["FOLLOW"]["DURN"] == 2 and mts["RECON"]["MPAT"] is None and mts["FOLLOW"]["MPAT"] is None)
    ck("scheduled hours and four-hour delay limit", ops["RECON"]["STIM"] == 8 and ops["FOLLOW"]["STIM"] == 10 and ops["FOLLOW"]["DTIM"] == 4)
    dep = fields(dt["MissionDependence"], rows(dt["MissionDependence"])[0])
    ck("one exact START dependency identity", len(rows(dt["MissionDependence"])) == 1 and tuple(dep[k] for k in ("DUNID", "DMTID", "DSTIM", "PUNID", "PMTID", "PSTIM", "DTYPE")) == ("TEACH-UNIT", "FOLLOW", 10, "TEACH-UNIT", "RECON", 8, "START"))
    ck("both result windows end at 24", all(fields(dt["ResultCollection"], r)["RCEND"] == 24 for r in rows(dt["ResultCollection"])) and fields(dt["Control"], rows(dt["Control"])[0])["SIMPE"] == 24)

    observed = {}
    report_hashes = {}
    for variant, run_name in RUN_NAMES.items():
        run = CASE / "runs" / run_name
        source = CASE / f"{variant}-input.json"
        prefix = f"{variant}: "
        inv, clo, step = (obj(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
        raw = clo["raw"]
        expected_source = {
            "input": sha(source), "parent": sha(PARENT), "contract": sha(CASE / "contract.json"),
            "builder": sha(CASE / "build.py"), "checker": sha(CASE / "check_roundtrip.py"),
            "runner_script": sha(CASE / "run_native_ssh.ps1"),
        }
        ck(prefix + "run copy matches frozen source", sha(run / "input.json") == expected_source["input"])
        ck(prefix + "invocation/closure identity", inv["run_id"] == clo["run_id"] == run_name and inv["variant"] == variant and clo["invocation_sha256"] == sha(run / "invocation.json"))
        ck(prefix + "session-0 SSH queue and preserved GUI", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"] == GUI)
        ck(prefix + "source fingerprints before and after", all(inv["source_hashes_before"].get(k) == v and clo["source_hashes_before"].get(k) == v and clo["source_hashes_after"].get(k) == v for k, v in expected_source.items()))
        ck(prefix + "all 12 raw hashes and sizes", len(raw) == 12 and all((run / n).is_file() and len((run / n).read_bytes()) == data["bytes"] and sha(run / n) == data["sha256"] for n, data in raw.items()))
        ck(prefix + "five native/check steps and GUI guard", [s["name"] for s in step] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] is True for s in step) and [c["name"] for c in inv["planned_commands"]] == ["import", "export", "calc", "jsonreport"])
        ck(prefix + "planned versus actual CLI arguments", all(step[i]["arguments"] == inv["planned_commands"][i]["arguments"] for i in range(4)))
        exported = tables(obj(run / "roundtrip-raw.json"))
        ck(prefix + "source table business-row roundtrip", all(t["columns"] == exported[n]["columns"] and (not rows(t) or rows(t) == rows(exported[n])) for n, t in tables(inputs[variant]).items()))
        nrows = sum(bool(rows(t)) for t in tables(inputs[variant]).values())
        ck(prefix + "source row-containing table count", nrows == (13 if variant == "control" else 14))
        ck(prefix + "roundtrip checker corroboration", obj(run / "roundtrip-validation.json")["passed"] is True)
        runlog = (run / "run.log").read_text(errors="replace")
        ck(prefix + "zero conversion errors, two classified warnings", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog and sorted(map(int, re.findall(r"warning #(\d+)", runlog))) == [108, 126] and not re.search(r"error #\d+", runlog))
        log = (run / "model.log").read_text(errors="replace")
        rep = obj(run / "report-raw.json", native=True)
        report_hashes[variant] = sha(run / "report-raw.json")
        rt = report_table(rep, "ResultSummary")
        summary = fields(rt, rows(rt)[0])
        sy = report_table(rep, "SystemResults")
        stock = report_table(rep, "StockTotalResults")
        sr = rows(sy)
        ck(prefix + "48 contiguous half-hour system and stock bins", len(sr) == len(rows(stock)) == 48 and all(abs(r[2] - i * .5) < 1e-8 and abs(r[3] - (i + 1) * .5) < 1e-8 for i, r in enumerate(sr)) and all(abs(r[0] - i * .5) < 1e-8 and abs(r[1] - (i + 1) * .5) < 1e-8 for i, r in enumerate(rows(stock))))
        ck(prefix + "mission summary and no failures", summary["NREP"] == 1 and summary["RTIUP"] == 24 and all(summary[k] == 1 for k in ("MTMF", "MSTF", "MSUF", "STMF")) and max(series(sy, "NFAIL")) == 0 and max(series(stock, "NBO")) == 0)
        start = {m: event(log, m, "mission starting,") for m in ("RECON", "FOLLOW")}
        completed = {m: event(log, m, "mission completed:") for m in ("RECON", "FOLLOW")}
        success = {m: event(log, m, "mission success:") for m in ("RECON", "FOLLOW")}
        allocated = re.findall(r"^Time: ([0-9.]+) <(FOLLOW,TEACH-UNIT,0,0,[0-9]+)> mission allocates system: <(TEACH-AIR-01,[0-9]+)>", log, re.M)
        ck(prefix + "one distinct ID per mission and no extra starts", all(len(start[m]) == len(completed[m]) == len(success[m]) == 1 and start[m][0][1] == completed[m][0][1] == success[m][0][1] for m in start) and len(re.findall(r"mission starting,", log)) == 2 and start["RECON"][0][1] != start["FOLLOW"][0][1])
        ck(prefix + "RECON launch, success and return", start["RECON"][0][0] == 8 and success["RECON"][0][0] == completed["RECON"][0][0] == 12 and "Time: 12 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>" in log)
        ck(prefix + "FOLLOW allocated before start to other aircraft", len(allocated) == 1 and float(allocated[0][0]) == 9 and allocated[0][2] == "TEACH-AIR-01,1" and start["FOLLOW"][0][1] == allocated[0][1])
        expected_start, expected_end = (10, 12) if variant == "control" else (12, 14)
        ck(prefix + "FOLLOW launch, success and return", start["FOLLOW"][0][0] == expected_start and success["FOLLOW"][0][0] == completed["FOLLOW"][0][0] == expected_end and f"Time: {expected_end} <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,1>" in log)
        idx = {c["name"]: i for i, c in enumerate(sy["columns"])}
        occupancy = [int((8 <= i*.5 < 12) + (expected_start <= i*.5 < expected_end)) for i in range(48)]
        ck(prefix + "event-derived operating occupancy equals all system bins", all(abs(r[idx["NSYMO"]] - count) < 1e-8 for r, count in zip(sr, occupancy)))
        operating_hours = sum((r[3] - r[2]) * r[idx["NSYMO"]] for r in sr)
        allocated_hours = sum((r[3] - r[2]) * r[idx["NSYMA"]] for r in sr)
        ck(prefix + "six operating aircraft-hours and expected allocated hours", operating_hours == 6 and allocated_hours == (8 if variant == "control" else 10))
        ck(prefix + "terminal two ready and zero active", sr[-1][idx["NSYRY"]] == 2 and sr[-1][idx["NSYMO"]] == 0 and sr[-1][idx["NSYMA"]] == 0)
        observed[variant] = {"recon_start": start["RECON"][0][0], "recon_success_return": success["RECON"][0][0], "follow_allocated": float(allocated[0][0]), "follow_start": start["FOLLOW"][0][0], "follow_success_return": success["FOLLOW"][0][0], "operating_aircraft_hours": operating_hours, "allocated_aircraft_hours": allocated_hours, "report_sha256": report_hashes[variant]}

    ck("paired start dependency adds two hours of launch delay", observed["dependent"]["follow_start"] - observed["control"]["follow_start"] == 2 and observed["dependent"]["follow_start"] == observed["dependent"]["recon_success_return"])
    ck("paired contrast preserves aircraft operating hours", observed["dependent"]["operating_aircraft_hours"] == observed["control"]["operating_aircraft_hours"] == 6)
    pd = fields(dt["ProblemDescription"], rows(dt["ProblemDescription"])[0])
    ck("dependent description does not falsely assign hour-9 success", "succeeds at 9" not in str(pd))
    result = {
        "schema": "simlox-a13-independent-start-readonly/v1",
        "reviewer": "Standalone standard-library raw replay; no author imports or native invocation",
        "passed": all(c["passed"] for c in checks),
        "passed_count": sum(c["passed"] for c in checks),
        "failed_count": sum(not c["passed"] for c in checks),
        "failed": [c for c in checks if not c["passed"]],
        "checks": checks,
        "hashes": {"parent_input": sha(PARENT), "manual_pdf": sha(MANUAL), "contract": sha(CASE / "contract.json"), "control_input": sha(CASE / "control-input.json"), "dependent_input": sha(CASE / "dependent-input.json"), "control_report": report_hashes["control"], "dependent_report": report_hashes["dependent"]},
        "observed": observed,
        "manual_read": "Installed PDF pp188,287-289 describes START waiting for precedent success and return; pp188/289 require FIXED precedent, p287 says FIXED dependent. Both case missions are FIXED, so this contradiction is unresolved.",
        "decision": "bounded_pair_accepted" if all(c["passed"] for c in checks) else "review_failed",
        "limits": ["One explicit unit, one predecessor and one dependent FIXED mission in this installed native CLI run only.", "The native log places RECON mission success at hour 12, the same timestamp as return; an earlier success point is not directly observed.", "Failure, multiple precedents, cross-unit references, repetition, CONTINUOUS dependence and GUI visual behavior were not tested.", "This pair does not resolve the manual's conflicting FIXED-side language."],
    }
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"], "failed": result["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()

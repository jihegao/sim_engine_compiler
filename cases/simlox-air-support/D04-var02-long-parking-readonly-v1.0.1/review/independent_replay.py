"""Independent read-only replay of the accepted D04 long-parking evidence."""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parent
PARENT = ROOT / "D04-flight-hour-pm-v1.0.0"
RUN = PARENT / "runs" / "d04-flight-v100-ssh-20260930-01"
OLD = ROOT / "D04-var02-long-parking-readonly-v1.0.0"
checks: list[dict] = []


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name: str, condition: bool, detail: object = None) -> None:
    checks.append({"name": name, "passed": bool(condition), "detail": detail})


def read(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: pathlib.Path) -> dict:
    # Native default JSON has a trailing comma; normalize only the parser copy.
    src = path.read_text(encoding="utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for i, c in enumerate(src):
        if quoted:
            out.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
            out.append(c)
        elif c == "," and re.match(r"\s*[}\]]", src[i + 1:]):
            continue
        else:
            out.append(c)
    return json.loads("".join(out))


def table_rows(doc: dict, name: str) -> tuple[list[dict], list[str]]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    columns = [col["name"] for col in table["columns"]]
    result = []
    for instance in table["instances"]:
        for row in instance["rows"]:
            check(f"{name} rectangular row {len(result)}", len(row) == len(columns))
            result.append(dict(zip(columns, row)))
    return result, columns


def times(log: str, fragment: str) -> list[float]:
    return [float(m.group(1)) for line in log.splitlines()
            if (m := re.match(r"^Time: ([0-9.]+) (.*)$", line)) and fragment in m.group(2)]


def pm_task_times(log: str, action: str) -> list[float]:
    pattern = rf"^Time: ([0-9.]+)  system PM task 0 on <TEACH-AIR-01,0> {action}$"
    return [float(value) for value in re.findall(pattern, log, re.M)]


def main() -> int:
    try:
        contract = read(CASE / "contract.json")
        check("contract SHA", sha(CASE / "contract.json") == "5248f06f0d7500e449000e85d1ec59761fe6a404b63ee4e19fb48106814b9f59")
        check("contract GO memo", sha(HERE / "independent-contract-go-or-no-go-2026-10-06.md") ==
              "93a30e7ad1c32a016a14d65b842da5733875e880f542fd3a686a6172f9c56c42")
        check("old contract NO_GO", sha(OLD / "contract.json") == contract["preserved_contract_failure"]["contract_sha256"] and
              sha(OLD / "review" / "independent-contract-no-go-2026-10-06.md") ==
              contract["preserved_contract_failure"]["independent_no_go_sha256"])
        for name, path, pin in (
            ("D04 input", PARENT / "native-input.json", contract["accepted_parent"]["input_sha256"]),
            ("D04 signoff", PARENT / "cli-scope-signoff-2026-09-30.md", contract["accepted_parent"]["signoff_sha256"]),
            ("D04 closure", RUN / "closure.json", contract["accepted_parent"]["closure_sha256"]),
            ("D03 input", ROOT / "D03-calendar-pm-v1.0.0" / "native-input.json", contract["instructional_prerequisite"]["input_sha256"]),
            ("D03 signoff", ROOT / "D03-calendar-pm-v1.0.0" / "cli-scope-signoff-2026-09-30.md", contract["instructional_prerequisite"]["signoff_sha256"]),
            ("manual", pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"), contract["source"]["manual_pdf_sha256"]),
            ("executable", pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"), contract["source"]["native_executable_sha256"]),
        ):
            check(f"source {name}", sha(path) == pin)
        closure, invocation = read(RUN / "closure.json"), read(RUN / "invocation.json")
        check("complete accepted closure", closure["error"] is None and closure["run_id"] == RUN.name)
        check("invocation SHA", sha(RUN / "invocation.json") == closure["invocation_sha256"])
        check("12 raw seals", len(closure["raw"]) == 12)
        for name, seal in sorted(closure["raw"].items()):
            p = RUN / name
            check(f"raw {name}", p.is_file() and p.stat().st_size == seal["bytes"] and sha(p) == seal["sha256"])
        check("stable source hashes", closure["source_hashes_before"] == closure["source_hashes_after"])
        check("source input/executable", closure["source_hashes_before"]["input"] == contract["accepted_parent"]["input_sha256"] and
              closure["source_hashes_before"]["simlox_exe"] == contract["source"]["native_executable_sha256"])
        for name, path in (
            ("input", PARENT / "native-input.json"),
            ("parent", ROOT / "D03-calendar-pm-v1.0.0" / "native-input.json"),
            ("contract", PARENT / "contract.json"),
            ("builder", PARENT / "build.py"),
            ("checker", PARENT / "check_roundtrip.py"),
            ("runner_script", PARENT / "run_native_ssh.ps1"),
            ("simlox_exe", pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")),
        ):
            check(f"recorded source {name}", sha(path) == closure["source_hashes_before"][name])
        check("recorded historical Python SHA", len(closure["source_hashes_before"]["python"]) == 64)
        check("SSH0 and sshd", invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
              "sshd.exe" in invocation["ssh_ancestor_names"])
        check("GUI record", invocation["gui"] == {"pid": 13340, "session_id": 1,
              "start_utc": "2026-09-28T10:09:56.8261381Z"})
        check("global queue", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
        steps = read(RUN / "steps.json")
        check("accepted native/check order", [s["name"] for s in steps] ==
              ["import", "export", "calc", "jsonreport", "check_import_export"])
        for step in steps:
            check(f"step {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"])
        converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("converter zero errors", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter and
              not re.search(r"\(error #\d+\)", converter))
        check("reviewed warning codes", sorted(re.findall(r"\(warning #(\d+)\)", converter)) == ["108", "126"])

        log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        all_times = [float(m.group(1)) for line in log.splitlines() if (m := re.match(r"^Time: ([0-9.]+) ", line))]
        check("complete chronological event times", all_times == sorted(all_times) and all_times[0] == 0 and all_times[-1] <= 60)
        for name, fragment, expected in (
            ("first mission start", "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting", [8]),
            ("first mission success", "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:", [10]),
            ("first mission completion", "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed: <TEACH-AIR-01,0>", [10]),
            ("first return", "System arrives <TEACH-AIR-01,0>, mission success", [10, 41]),
            ("second mission order", "mission ordered: SHORT-MISSION", [39]),
            ("second mission allocation", "<SHORT-MISSION,TEACH-UNIT,0,0,1> mission allocates system: <TEACH-AIR-01,0>", [39]),
            ("second mission start", "<SHORT-MISSION,TEACH-UNIT,0,0,1> mission starting", [40]),
            ("second mission success", "<SHORT-MISSION,TEACH-UNIT,0,0,1> mission success:", [41]),
            ("second mission completion", "<SHORT-MISSION,TEACH-UNIT,0,0,1> mission completed: <TEACH-AIR-01,0>", [41]),
            ("PM physical return", "Maintained system arrives <TEACH-AIR-01,0>", [42]),
        ):
            check(name, times(log, fragment) == expected, {"actual": times(log, fragment), "expected": expected})
        check("PM starts", pm_task_times(log, "started") == [41])
        check("PM completes", pm_task_times(log, "completed") == [42])
        check("no flight or PM event inside h10-40", not any(10 < t < 40 for t in
              times(log, "mission starting") + pm_task_times(log, "started")))
        check("no failure/mission cancellation", not re.search(r"mission (?:cancelled|aborted):|failure occurred", log))

        raw = report(RUN / "report-raw.json")
        system, scols = table_rows(raw, "SystemResults")
        stock, kcols = table_rows(raw, "StockTotalResults")
        summary, qcols = table_rows(raw, "ResultSummary")
        check("120×40 System", len(system) == 120 and len(scols) == 40)
        check("120×16 Stock", len(stock) == 120 and len(kcols) == 16)
        check("one 11-field summary", len(summary) == 1 and len(qcols) == 11)
        system_zero = {name: 0 for name in scols if name not in ("UNID", "SID", "STINT", "ETINT", "SYDT")}
        system_zero.update({"UNID": "Total over all Units", "SID": "Total over all Systems", "SYDT": None})
        stock_zero = {name: 0 for name in kcols if name not in ("STINT", "ETINT", "NBOU", "ROS", "ROST", "WT", "WTT", "WTS")}
        stock_zero.update({name: None for name in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS")})
        stock_zero["PNB"] = 1  # Aggregate stock-total field, not physical on-hand identity.
        for i, row in enumerate(system):
            h = i * .5
            expected = dict(system_zero, STINT=h, ETINT=h + .5)
            if 7 <= h < 8 or 39 <= h < 40:
                expected.update(NSYMA=1, NSYMR=1, NSYA=1)
            elif 8 <= h < 10 or 40 <= h < 41:
                expected.update(NSYMA=1, NSYMO=1, NSYA=1, FTMO=1, STACC=1)
            elif h == 41:
                expected.update(NSYUA=1, NSYPM=1, NPMS=1, SYDT=1, NSYDT=1)
            elif h == 41.5:
                expected.update(NSYUA=1, NSYPM=1)
            elif h == 42:
                expected.update(NSYRY=1, NSYA=1, NPMT=1)
            else:
                expected.update(NSYRY=1, NSYA=1)
            check(f"System row {i} fields", row.keys() == expected.keys())
            for field in scols:
                check(f"System row {i} {field}", row[field] == expected[field], {"actual": row[field], "expected": expected[field]})
        for i, row in enumerate(stock):
            expected = dict(stock_zero, STINT=i * .5, ETINT=(i + 1) * .5)
            check(f"Stock row {i} fields", row.keys() == expected.keys())
            for field in kcols:
                check(f"Stock row {i} {field}", row[field] == expected[field], {"actual": row[field], "expected": expected[field]})
        expected_summary = {"NREP": 1, "RTILW": 0, "RTIUP": 60, "MTMF": 1, "RSMTMF": 0,
                            "MSTF": 1, "RSMSTF": 0, "MSUF": 1, "RSMSUF": 0, "STMF": 1, "RSSTMF": 0}
        for field in qcols:
            check(f"summary {field}", summary[0][field] == expected_summary[field])
        parked = [r for r in system if 10 <= r["STINT"] < 39]
        reserved = [r for r in system if 39 <= r["STINT"] < 40]
        check("58 ready-parking bins", len(parked) == 58 and all(r["NSYRY"] == r["NSYA"] == 1 and
              r["NSYMA"] == r["NSYMO"] == r["NSYPM"] == 0 for r in parked))
        check("two reserved-not-flying bins", len(reserved) == 2 and all(r["NSYRY"] == 0 and
              r["NSYA"] == r["NSYMA"] == 1 and r["NSYMO"] == r["NSYPM"] == 0 for r in reserved))
        check("PM markers once", sum(r["NPMS"] for r in system) == sum(r["NPMT"] for r in system) == 1)
        check("terminal ready", system[-1]["NSYRY"] == system[-1]["NSYA"] == 1 and system[-1]["NSYPM"] == 0)
        for field, expected in (("NSYRY", 54), ("NSYA", 59), ("NSYMO", 3), ("NSYPM", 1), ("NSYMA", 5)):
            check(f"integral {field}", sum(row[field] * .5 for row in system) == expected)
        for name, expected_bad in (("failed-author-validation-2026-10-06.json", "replay exception"),
                                   ("failed-author-validation-v2-2026-10-06.json", "PM starts/completes")):
            prior = read(HERE / name)
            check(f"preserved {name}", prior["passed"] is False and any(
                  c["name"] == expected_bad and c["passed"] is False for c in prior["checks"]))
    except Exception as exc:
        check("replay exception", False, f"{type(exc).__name__}: {exc}")

    failures = [c["name"] for c in checks if not c["passed"]]
    verdict = {"schema": "simlox-d04-var02-v101-independent-replay/v1",
               "verdict": "GO_BOUNDED" if not failures else "NO_GO", "checks_count": len(checks),
               "failures": failures, "accepted_run": RUN.name,
               "accepted_closure_sha256": "3cae72c375ef7a7c8dc63d785a33e97e9bd6103655fc28971abf5a0ccb24df45",
               "scope": "one sealed 30-hour no-flight gap, of which 29 hours are ready and one hour is mission-reserved",
               "limits": ["no new native run or direct PM counter trace", "no general inactivity-accrual law",
                          "raw report trailing comma normalized only in memory", "aggregate PNB is not physical stock identity"]}
    (HERE / "independent-verdict.json").write_bytes((json.dumps(verdict, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": verdict["verdict"], "checks": len(checks), "failures": failures}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

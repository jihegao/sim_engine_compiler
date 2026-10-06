"""Independent, read-only replay of sealed D04.var01 OPHOURS=4 evidence."""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parent
PARENT = ROOT / "D04-flight-hour-pm-v1.0.0"
PRUN = PARENT / "runs" / "d04-flight-v100-ssh-20260930-01"
PRIOR = ROOT / "D04-var01-threshold-not-reached-v0.1.0"
RUN = CASE / "runs" / "d04-var01-op4-v011-ssh-20261006-01"
EXPECTED_CLOSURE = "98d30d678431fb8ce6661b2cac2b5a3681b226bca32a8076c7eac8899e18dea0"
PARENT_CLOSURE = "3cae72c375ef7a7c8dc63d785a33e97e9bd6103655fc28971abf5a0ccb24df45"
INPUT_SHA = "cb8d6045df3b395583e3df2290b61376afa4fa9e8bc82a1c6f53fcfb44e2bddd"
checks: list[dict] = []


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name: str, passed: bool, detail: object = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def obj(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: pathlib.Path) -> dict:
    # SIMLOX's default report has a trailing comma. Normalize an in-memory copy only.
    src = path.read_text(encoding="utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for index, char in enumerate(src):
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
        elif char == "," and re.match(r"\s*[}\]]", src[index + 1:]):
            continue
        else:
            out.append(char)
    return json.loads("".join(out))


def tables(doc: dict, root: str) -> dict:
    return {table["name"]: table for table in doc[root]["tables"]}


def cells(doc: dict) -> dict:
    out = {}
    for table in doc["model"]["tables"]:
        for instance_number, instance in enumerate(table["instances"]):
            cols = [c["name"] for c in table["columns"]]
            for row_number, row in enumerate(instance["rows"]):
                check(f"source rectangular {table['name']} {instance_number}/{row_number}", len(row) == len(cols))
                for name, value in zip(cols, row):
                    key = (table["name"], instance_number, row_number, name)
                    check(f"source unique {key}", key not in out)
                    out[key] = value
    return out


def rows(table: dict) -> list[dict]:
    columns = [c["name"] for c in table["columns"]]
    result = []
    for instance in table["instances"]:
        for row in instance["rows"]:
            check(f"report rectangular {table['name']} row {len(result)}", len(row) == len(columns))
            result.append(dict(zip(columns, row)))
    return result


def seal(role: str, run: pathlib.Path, closure: dict) -> None:
    check(f"{role} closure status", closure["error"] is None)
    check(f"{role} 12 raw seals", len(closure["raw"]) == 12)
    for name, expected in sorted(closure["raw"].items()):
        path = run / name
        check(f"{role} raw {name}", path.is_file() and path.stat().st_size == expected["bytes"]
              and sha(path) == expected["sha256"])


def near(got: object, expected: object, tol: float = 5e-5) -> bool:
    if isinstance(got, (int, float)) and not isinstance(got, bool) and isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return math.isfinite(float(got)) and abs(float(got) - float(expected)) <= tol
    return got == expected


def at(log: str, time: float, fragment: str) -> bool:
    return any(float(m.group(1)) == time and fragment in m.group(2)
               for line in log.splitlines()
               if (m := re.match(r"^Time: ([0-9.]+) (.*)$", line)))


def main() -> int:
    try:
        contract = obj(CASE / "contract.json")
        check("contract SHA", sha(CASE / "contract.json") == "a49bd85018977531f8219f2f5fc5e1ebdfa8b5054eb2dc28d54f903ee950b8bd")
        check("child closure SHA", sha(RUN / "closure.json") == EXPECTED_CLOSURE)
        check("parent closure SHA", sha(PRUN / "closure.json") == PARENT_CLOSURE)
        check("prior no-go SHA", sha(PRIOR / "review" / "independent-prelaunch-no-go-2026-10-06.md") ==
              contract["preserved_prelaunch_failure"]["independent_prelaunch_no_go_sha256"])
        check("prior run absent", not (PRIOR / "runs" / "d04-var01-op4-v010-ssh-20261006-01").exists())
        check("child input SHA", sha(CASE / "native-input.json") == INPUT_SHA)
        check("prior input byte identity", (CASE / "native-input.json").read_bytes() == (PRIOR / "native-input.json").read_bytes())
        pclosure, closure = obj(PRUN / "closure.json"), obj(RUN / "closure.json")
        seal("parent", PRUN, pclosure)
        seal("child", RUN, closure)
        check("child run ID", closure["run_id"] == RUN.name)
        check("invocation seal", closure["invocation_sha256"] == sha(RUN / "invocation.json"))
        check("source before/after stable", closure["source_hashes_before"] == closure["source_hashes_after"])
        paths = {
            "input": CASE / "native-input.json",
            "parent": PARENT / "native-input.json",
            "parent_signoff": PARENT / "cli-scope-signoff-2026-09-30.md",
            "parent_closure": PRUN / "closure.json",
            "d03_input": ROOT / "D03-calendar-pm-v1.0.0" / "native-input.json",
            "d03_signoff": ROOT / "D03-calendar-pm-v1.0.0" / "cli-scope-signoff-2026-09-30.md",
            "contract_review": HERE / "independent-contract-go-2026-10-06.md",
            "negative_control": HERE / "negative-control-accepted-parent.json",
            "manual_pdf": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
            "contract": CASE / "contract.json",
            "builder": CASE / "build.py",
            "checker": CASE / "check_roundtrip.py",
            "diff_checker": CASE / "check_parent_diff.py",
            "validator": CASE / "validate_native_cli.py",
            "python": pathlib.Path(sys.executable),
            "runner_script": CASE / "run_native_ssh.ps1",
            "simlox_exe": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        }
        for name, path in paths.items():
            check(f"source seal {name}", sha(path) == closure["source_hashes_before"][name])
        check("contract parent pin", sha(paths["parent"]) == contract["accepted_parent"]["input_sha256"])
        check("contract D03 pin", sha(paths["d03_input"]) == contract["instructional_prerequisites"][0]["input_sha256"])
        check("contract manual/exe pins", sha(paths["manual_pdf"]) == contract["source"]["manual_pdf_sha256"] and
              sha(paths["simlox_exe"]) == contract["source"]["native_executable_sha256"])

        invocation, steps = obj(RUN / "invocation.json"), obj(RUN / "steps.json")
        check("SSH0 and sshd", invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
              "sshd.exe" in invocation["ssh_ancestor_names"])
        check("GUI identity", invocation["gui"] == {"pid": 13340, "session_id": 1,
              "start_utc": "2026-09-28T10:09:56.8261381Z"})
        check("global mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
        check("five ordered steps", [s["name"] for s in steps] ==
              ["import", "export", "check_import_export", "calc", "jsonreport"])
        for step in steps:
            check(f"step {step['name']} completed/GUI", step["status"] == "completed" and
                  step["exit_code"] == 0 and step["gui_preserved"])
        check("roundtrip checker result", obj(RUN / "roundtrip-validation.json")["passed"] is True)
        runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("converter 0/2/0", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog)
        check("warnings exactly 108/126", sorted(re.findall(r"\(warning #(\d+)\)", runlog)) == ["108", "126"])
        check("no converter error", not re.search(r"\(error #\d+\)", runlog))
        check("valid outputs", all((RUN / n).stat().st_size > 4 for n in ("model.sxi", "model.sxo", "model.log", "report-raw.json")))

        before = native_json(PARENT / "native-input.json")
        after = native_json(CASE / "native-input.json")
        old, new = cells(before), cells(after)
        check("221 source cells", len(old) == len(new) == 221)
        check("source keys", old.keys() == new.keys())
        check("one PMINT delta", {key: (old[key], new[key]) for key in old if old[key] != new[key]} ==
              {("MaterielPM", 0, 0, "PMINT"): (3.0, 4.0)})
        check("copied input SHA", sha(RUN / "input.json") == INPUT_SHA)
        exported = tables(native_json(RUN / "roundtrip-raw.json"), "model")
        populated = [t for t in after["model"]["tables"] if any(i["rows"] for i in t["instances"])]
        check("18 authored row-containing tables", len(populated) == 18)
        for table in populated:
            name = table["name"]
            check(f"roundtrip {name} columns", exported[name]["columns"] == table["columns"])
            check(f"roundtrip {name} instances/rows", exported[name]["instances"] == table["instances"])

        plog = (PRUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        def prefix(source: str) -> list[str]:
            return [line for line in source.splitlines()
                    if (m := re.match(r"^Time: ([0-9.]+) ", line)) and float(m.group(1)) < 41]
        check("pre-h41 event prefix", prefix(log) == prefix(plog))
        for hour, phrase in ((8, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting"),
                             (10, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:"),
                             (10, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:"),
                             (40, "<SHORT-MISSION,TEACH-UNIT,0,0,1> mission starting"),
                             (41, "<SHORT-MISSION,TEACH-UNIT,0,0,1> mission success:"),
                             (41, "<SHORT-MISSION,TEACH-UNIT,0,0,1> mission completed:"),
                             (41, "System arrives <TEACH-AIR-01,0>, mission success"),
                             (41, "System ready <TEACH-AIR-01,0>")):
            check(f"event {hour} {phrase}", at(log, hour, phrase))
        check("exact two starts/completions/successes", all(len(re.findall(r"^Time: .* " + fragment, log, re.M)) == 2
              for fragment in (r"<[^>]+> mission starting", r"<[^>]+> mission completed", r"<[^>]+> mission success:")))
        check("no cancel/abort", not re.search(r"mission (?:cancelled|aborted):", log))
        check("no PM action or claim", not re.search(r"system PM task|within system PM task|System to PM|Maintained system arrives|\d+ PM tasks:|OP3 Critical", log))

        report = tables(native_json(RUN / "report-raw.json"), "report")
        parent_report = tables(native_json(PRUN / "report-raw.json"), "report")
        sysrows, psys = rows(report["SystemResults"]), rows(parent_report["SystemResults"])
        stock, pstock = rows(report["StockTotalResults"]), rows(parent_report["StockTotalResults"])
        summary, psummary = rows(report["ResultSummary"]), rows(parent_report["ResultSummary"])
        check("120+120 System rows", len(sysrows) == len(psys) == 120)
        check("120+120 Stock rows", len(stock) == len(pstock) == 120)
        check("40 System and 16 Stock columns", len(sysrows[0]) == 40 and len(stock[0]) == 16)
        ready_template = next(r for r in psys if r["STINT"] == 42.5)
        for i, row in enumerate(sysrows):
            start = i * .5
            expected = psys[i] if start < 41 else dict(ready_template, STINT=start, ETINT=start + .5)
            check(f"System row {i} field set", row.keys() == expected.keys())
            for field, value in expected.items():
                check(f"System row {i} {field}", near(row[field], value), {"actual": row[field], "expected": value})
            check(f"System interval {i}", near(row["STINT"], start) and near(row["ETINT"], start + .5))
        for i, row in enumerate(stock):
            expected = pstock[i]
            check(f"Stock row {i} field set", row.keys() == expected.keys())
            for field, value in expected.items():
                check(f"Stock row {i} {field}", near(row[field], value), {"actual": row[field], "expected": value})
        check("one summary row", len(summary) == len(psummary) == 1)
        check("11 summary fields", len(summary[0]) == len(psummary[0]) == 11)
        for field, value in psummary[0].items():
            check(f"ResultSummary {field}", near(summary[0][field], value, 3e-8))
        for field, value in (("NSYMO", 3), ("NSYRY", 55), ("NSYA", 60), ("NSYPM", 0), ("NSYMA", 5)):
            integral = sum((r[field] or 0) * .5 for r in sysrows)
            check(f"integrated {field}", near(integral, value), {"actual": integral, "expected": value})
        check("no PM markers", sum((r["NPMS"] or 0) + (r["NPMT"] or 0) for r in sysrows) == 0)
        check("no failures or repairs", all((r["NFAIL"] or 0) == (r["NREPT"] or 0) == 0 for r in sysrows))
        check("terminal ready", all(near(sysrows[-1][k], v) for k, v in (("NSYRY", 1), ("NSYPM", 0), ("NSYMO", 0))))
    except Exception as exc:
        check("replay exception", False, f"{type(exc).__name__}: {exc}")

    failures = [c["name"] for c in checks if not c["passed"]]
    result = {"schema": "simlox-d04-var01-v011-independent-replay/v1", "verdict": "GO_BOUNDED" if not failures else "NO_GO",
              "passed": not failures, "checks_count": len(checks), "failures": failures,
              "run_id": RUN.name, "closure_sha256": EXPECTED_CLOSURE,
              "scope": "one fixed-seed OPHOURS 3 versus 4 below-threshold native CLI contrast; no full threshold panel",
              "limits": ["stale OP3/DESCR labels are historical; child PMINT=4 is authoritative",
                         "default report raw bytes have trailing comma; only in-memory parse copy normalized",
                         "stock total PNB is aggregate, not physical installed-ID evidence",
                         "no cross-engine, GUI-visual, or general threshold claim"]}
    (HERE / "independent-verdict.json").write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": len(checks), "failures": failures}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

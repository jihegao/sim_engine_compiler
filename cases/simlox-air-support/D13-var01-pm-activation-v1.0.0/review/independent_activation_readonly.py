"""Independent read-only replay of D13.var01 local PM activation.

Uses only the Python standard library and frozen source/sealed raw files.
It never imports the builder, author validator, roundtrip checker, or SIMLOX.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
PARENT = CASE.parent / "D03-calendar-pm-v1.0.0"
RUN = CASE / "runs" / "d13-var01-activation-v100-ssh-20260930-01"
PARENT_RUN = PARENT / "runs" / "d03-calendar-v100-ssh-20261001-02"
MANUAL = Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf")
DICTIONARY = Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt")
INPUT_SHA = "f4fce5c8f362be817264544f22f271c1ee47b6e635e871619525fa1c8545ca70"
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
PARENT_LOG_SHA = "edd41c34046fb92e53a3f5eb8569cec3a932aa00aed8e878ecc40ef45826a4a5"
PARENT_REPORT_SHA = "a9cc414e9b40da06be620e5fb64c52e0db41ec6fe959ac0874497d358232a84e"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
DICTIONARY_SHA = "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    """Strip trailing commas in native JSON outside quoted strings."""
    raw = path.read_text(encoding="utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for index, char in enumerate(raw):
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
        elif char == "," and re.match(r"\s*[}\]]", raw[index + 1 :]):
            continue
        else:
            out.append(char)
    return json.loads("".join(out))


def tables(doc: dict, root: str) -> dict:
    return {table["name"]: table for table in doc[root]["tables"]}


def rows(doc: dict, root: str, name: str) -> list[dict]:
    table = tables(doc, root)[name]
    fields = [column["name"] for column in table["columns"]]
    return [
        dict(zip(fields, row))
        for instance in table["instances"]
        for row in instance["rows"]
    ]


def row_tables(doc: dict) -> dict:
    return {
        table["name"]: (
            table["columns"],
            [row for instance in table["instances"] for row in instance["rows"]],
        )
        for table in doc["model"]["tables"]
        if any(instance["rows"] for instance in table["instances"])
    }


def dictionary_fields(raw: str, table: str) -> list[str]:
    return [line.split(";")[2] for line in raw.splitlines() if line.startswith(table + ";")]


def events(log: str) -> dict:
    find = lambda pattern: re.findall(pattern, log, flags=re.MULTILINE)
    return {
        "mission_starts": [
            (float(time), int(wave), int(aircraft))
            for time, wave, aircraft in find(
                r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission starting, duration: 2 : <TEACH-AIR-01,(\d+)>$"
            )
        ],
        "mission_successes": [
            (float(time), int(wave))
            for time, wave in find(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission success: ?$")
        ],
        "mission_cancelled": bool(re.search(r"mission cancelle?d", log, flags=re.IGNORECASE)),
        "failure": bool(re.search(r"critical random failure|non-critical random failure", log, flags=re.IGNORECASE)),
        "pm_objects": [
            (float(time), int(task), int(aircraft))
            for time, task, aircraft in find(
                r"^Time: ([\d.]+)  system PM task (\d+) on <TEACH-AIR-01,(\d+)> started$"
            )
        ],
        "pm_work": [
            (float(time), int(task), int(aircraft))
            for time, task, aircraft in find(
                r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task (\d+) on <TEACH-AIR-01,(\d+)> starts performing, planned to last for 1 hours$"
            )
        ],
        "pm_done": [
            (float(time), int(task), int(aircraft))
            for time, task, aircraft in find(
                r"^Time: ([\d.]+)  system PM task (\d+) on <TEACH-AIR-01,(\d+)> completed$"
            )
        ],
    }


def replay() -> dict:
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected, "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float, tolerance: float = 3e-5) -> None:
        checks.append({
            "name": name,
            "passed": abs(actual - expected) <= tolerance,
            "actual": actual,
            "expected": expected,
            "tolerance": tolerance,
        })

    hashes: dict = {}
    observed: dict = {}
    try:
        contract = read_json(CASE / "contract.json")
        diff = read_json(CASE / "parent-diff.json")
        invocation = read_json(RUN / "invocation.json")
        closure = read_json(RUN / "closure.json")
        parent_closure = read_json(PARENT_RUN / "closure.json")
        steps = read_json(RUN / "steps.json")
        checker = read_json(RUN / "roundtrip-validation.json")
        source = native_json(CASE / "native-input.json")
        parent = native_json(PARENT / "native-input.json")
        copied = native_json(RUN / "input.json")
        exported = native_json(RUN / "roundtrip-raw.json")
        report = native_json(RUN / "report-raw.json")
        log = (RUN / "model.log").read_text(encoding="utf-8-sig")
        parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
        run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")
        runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
        dictionary = DICTIONARY.read_text(encoding="utf-8-sig", errors="replace")

        source_paths = {
            "input": CASE / "native-input.json",
            "parent": PARENT / "native-input.json",
            "contract": CASE / "contract.json",
            "builder": CASE / "build.py",
            "checker": CASE / "check_roundtrip.py",
            "python": Path(invocation["planned_check"]["executable"]),
            "runner_script": CASE / "run_native_ssh.ps1",
            "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
        }
        source_hashes = {name: sha(path) for name, path in source_paths.items()}
        raw_hashes = {
            name: {"sha256": sha(RUN / name), "bytes": (RUN / name).stat().st_size}
            for name in closure["raw"]
        }
        check("accepted D03 parent input SHA", source_hashes["parent"], PARENT_SHA)
        check("frozen activation input SHA", source_hashes["input"], INPUT_SHA)
        check("copied input SHA", sha(RUN / "input.json"), INPUT_SHA)
        check("contract, diff and invocation source binding", (
            contract["input_sha256"], contract["parent_input_sha256"],
            diff["child_input_sha256"], diff["parent_input_sha256"],
            invocation["input_sha256"], invocation["parent_sha256"],
        ), (INPUT_SHA, PARENT_SHA, INPUT_SHA, PARENT_SHA, INPUT_SHA, PARENT_SHA))
        check("source hashes before and after", (closure["source_hashes_before"], closure["source_hashes_after"]), (source_hashes, source_hashes))
        check("invocation source hashes", invocation["source_hashes_before"], source_hashes)
        check("invocation byte seal", closure["invocation_sha256"], sha(RUN / "invocation.json"))
        check("12 sealed raw hashes and byte counts", (len(raw_hashes), raw_hashes), (12, closure["raw"]))
        check("raw file inventory", sorted(raw_hashes), sorted([
            "input.json", "import.log", "model.sxi", "roundtrip-raw.json",
            "export.log", "model.sxo", "model.log", "run.log",
            "report-raw.json", "report-export.log", "roundtrip-validation.json", "steps.json",
        ]))
        check("closure error", closure["error"], None)
        check("run and case identity", (
            closure["run_id"], invocation["run_id"], invocation["case_id"],
        ), (RUN.name, RUN.name, "D13.var01"))
        check("accepted parent sealed log", (
            parent_closure["source_hashes_before"]["input"], sha(PARENT_RUN / "model.log"),
            sha(PARENT_RUN / "report-raw.json"),
        ), (PARENT_SHA, PARENT_LOG_SHA, PARENT_REPORT_SHA))
        check("session-0 SSH and GUI identity", (
            invocation["session_id"], invocation["ssh_connection_present"],
            "sshd.exe" in invocation["ssh_ancestor_names"],
            invocation["gui"]["pid"], invocation["gui"]["session_id"],
        ), (0, True, True, 13340, 1))
        check("host mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("runner implements SSH, queue, GUI and immutable-run guards", all(token in runner for token in [
            "session-0 SSH required", "host-wide Issue 18 native queue busy",
            "expected existing GUI PID 13340 only", "GUI session not active",
            "GUI process changed", "immutable native run already exists",
        ]), True)
        check("five recorded steps", [x["name"] for x in steps], [
            "import", "export", "calc", "jsonreport", "check_import_export",
        ])
        check("steps exit zero and preserve GUI", all(
            x["status"] == "completed" and x["exit_code"] == 0 and x["gui_preserved"]
            for x in steps
        ), True)

        check("installed manual and dictionary fingerprints", (sha(MANUAL), sha(DICTIONARY)), (MANUAL_SHA, DICTIONARY_SHA))
        check("contract records installed manual fingerprint and pages", (
            MANUAL_SHA in contract["manual_source"],
            "379-385" in contract["manual_source"],
        ), (True, True))
        check("PMActivation field schema matches installed dictionary", dictionary_fields(dictionary, "PMActivation"), [
            "USTID", "PMID", "ENPM", "CRIT", "PRID", "NOTE",
        ])
        check("PMActivationProfile field schema matches installed dictionary", dictionary_fields(dictionary, "PMActivationProfile"), [
            "PRID", "SPRID", "STIM", "ETIM", "IQTY", "IINT", "ENPM", "CRIT", "NOTE",
        ])

        check("source equals copied native input", copied, source)
        ptab, ctab = tables(parent, "model"), tables(source, "model")
        check("parent 31 tables; child adds two", (
            len(ptab), len(ctab), sorted(set(ctab) - set(ptab)), sorted(set(ptab) - set(ctab)),
        ), (31, 33, ["PMActivation", "PMActivationProfile"], []))
        changed = sorted(name for name in ptab if ptab[name] != ctab[name])
        check("only parent table change is description label", changed, ["ProblemDescription"])
        check("exact parent diff document", (
            diff["changed_tables_only"], diff["added_tables_only"], diff["unchanged_table_count"],
            diff["changed_tables"]["ProblemDescription"]["parent"] == ptab["ProblemDescription"],
            diff["changed_tables"]["ProblemDescription"]["child"] == ctab["ProblemDescription"],
            all(diff["added_tables"][name] == ctab[name] for name in ["PMActivation", "PMActivationProfile"]),
        ), (["ProblemDescription"], ["PMActivation", "PMActivationProfile"], 30, True, True, True))
        check("global Control.ENPM remains enabled", (
            rows(parent, "model", "Control")[0]["ENPM"],
            rows(source, "model", "Control")[0]["ENPM"],
        ), ("Y", "Y"))
        check("local PM activation links TEACH-UNIT/CAL24 to PM-SWITCH", rows(source, "model", "PMActivation"), [{
            "USTID": "TEACH-UNIT", "PMID": "CAL24", "ENPM": "Y", "CRIT": "Y", "PRID": "PM-SWITCH", "NOTE": None,
        }])
        check("nonoverlapping N 0-30 then Y 30-60 periods", rows(source, "model", "PMActivationProfile"), [
            {"PRID": "PM-SWITCH", "SPRID": "<LIMIT>", "STIM": 0.0, "ETIM": 30.0, "IQTY": 1, "IINT": 0.0, "ENPM": "N", "CRIT": "Y", "NOTE": None},
            {"PRID": "PM-SWITCH", "SPRID": "<LIMIT>", "STIM": 30.0, "ETIM": 60.0, "IQTY": 1, "IINT": 0.0, "ENPM": "Y", "CRIT": "Y", "NOTE": None},
        ])
        check("CALHOURS interval and 60-hour horizon unchanged", (
            rows(parent, "model", "MaterielPM"), rows(source, "model", "MaterielPM"),
            rows(parent, "model", "Control")[0]["SIMPE"], rows(source, "model", "Control")[0]["SIMPE"],
        ), (rows(parent, "model", "MaterielPM"), rows(parent, "model", "MaterielPM"), 60, 60))
        before, after = row_tables(copied), row_tables(exported)
        check("20 source row-containing tables roundtrip unchanged", (
            len(before), len(after), all(after.get(name) == value for name, value in before.items()),
        ), (20, 33, True))
        extras = sorted(name for name in after if name not in before)
        check("native-added tables are all-null placeholders", (len(extras), all(
            all(value is None for row in after[name][1] for value in row) for name in extras
        )), (13, True))
        check("recorded roundtrip checker", (
            checker["passed"], len(checker["populated_tables"]), checker["source_sha256"],
        ), (True, 20, INPUT_SHA))
        conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
        check("conversion zero errors, two documented warnings", conversion.groups() if conversion else None, ("0", "2", "0"))
        check("conversion warning codes", ("(warning #108)" in run_log, "(warning #126)" in run_log), (True, True))

        child_events, parent_events = events(log), events(parent_log)
        check("three mission starts match D03", child_events["mission_starts"], parent_events["mission_starts"])
        check("three mission successes match D03", child_events["mission_successes"], parent_events["mission_successes"])
        check("mission times and identity", child_events["mission_starts"], [
            (8.0, 0, 0), (20.0, 1, 0), (32.0, 2, 0),
        ])
        check("three success hours, no cancellation or failure", (
            child_events["mission_successes"], child_events["mission_cancelled"], child_events["failure"],
        ), ([(10.0, 0), (22.0, 1), (34.0, 2)], False, False))
        check("no PM object or work at hour 24", (
            any(time == 24 for time, _, _ in child_events["pm_objects"]),
            any(time == 24 for time, _, _ in child_events["pm_work"]),
        ), (False, False))
        check("PM object starts 30 and 55", child_events["pm_objects"], [(30.0, 0, 0), (55.0, 1, 0)])
        check("physical PM work 30 and 55", child_events["pm_work"], [(30.0, 0, 0), (55.0, 1, 0)])
        check("PM completion 31 and 56", child_events["pm_done"], [(31.0, 0, 0), (56.0, 1, 0)])
        check("accepted D03 parent PM objects instead start 24 and 49", parent_events["pm_objects"], [(24.0, 0, 0), (49.0, 1, 0)])

        system = rows(report, "report", "SystemResults")
        stock = rows(report, "report", "StockTotalResults")
        summary = rows(report, "report", "ResultSummary")
        check("120 aligned half-hour report bins to hour 60", (
            len(summary), summary[0]["RTIUP"], len(system), len(stock),
            all(x["STINT"] == i / 2 and x["ETINT"] == (i + 1) / 2 for group in (system, stock) for i, x in enumerate(group)),
        ), (1, 60, 120, 120, True))
        check("PM report markers", (
            [(x["STINT"], x["NPMS"]) for x in system if x["NPMS"]],
            [(x["STINT"], x["NPMT"]) for x in system if x["NPMT"]],
        ), ([(30, 1), (55, 1)], [(31, 1), (56, 1)]))
        near("no PM occupancy before hour 30", sum(x["NSYPM"] * 0.5 for x in system if x["STINT"] < 30), 0)
        near("two PM aircraft-hours", sum(x["NSYPM"] * 0.5 for x in system), 2)
        check("peak one aircraft in PM", max(x["NSYPM"] for x in system), 1)
        check("no report failures or direct repairs", (
            sum(x["NFAIL"] for x in system), sum(x["NREPT"] for x in system),
        ), (0, 0))
        near("mission success fraction one", summary[0]["MSUF"], 1)
        check("terminal one ready, no PM or repair", (
            system[-1]["NSYRY"], system[-1]["NSYPM"], system[-1]["NSYRP"],
        ), (1, 0, 0))

        hashes = {
            "source": source_hashes,
            "parent_diff_sha256": sha(CASE / "parent-diff.json"),
            "manual_pdf_sha256": sha(MANUAL),
            "dictionary_sha256": sha(DICTIONARY),
            "invocation_sha256": sha(RUN / "invocation.json"),
            "closure_sha256": sha(RUN / "closure.json"),
            "raw": raw_hashes,
            "parent_model_log_sha256": sha(PARENT_RUN / "model.log"),
            "parent_report_sha256": sha(PARENT_RUN / "report-raw.json"),
        }
        observed = {
            "child_events": child_events,
            "parent_pm_objects": parent_events["pm_objects"],
            "report_bins": len(system),
            "report_pm_start_markers": [(x["STINT"], x["NPMS"]) for x in system if x["NPMS"]],
            "report_pm_completion_markers": [(x["STINT"], x["NPMT"]) for x in system if x["NPMT"]],
            "pm_aircraft_hours": sum(x["NSYPM"] * 0.5 for x in system),
            "terminal_ready_aircraft": system[-1]["NSYRY"],
            "conversion_errors": int(conversion.group(1)),
            "conversion_warnings": int(conversion.group(2)),
        }
    except (OSError, KeyError, ValueError, TypeError, IndexError, StopIteration, json.JSONDecodeError) as exc:
        checks.append({"name": "independent replay exception", "passed": False, "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    passed = all(item["passed"] for item in checks)
    return {
        "schema": "simlox-d13-var01-activation-independent-review/v1",
        "reviewer": "independent standard-library read-only raw replay; author code not imported",
        "case_id": "D13.var01",
        "run_id": RUN.name,
        "parent_run_id": PARENT_RUN.name,
        "passed": passed,
        "decision": "bounded_local_pm_activation_cli_evidence_pass" if passed else "independent_review_failed",
        "checks_count": len(checks),
        "checks": checks,
        "hashes": hashes,
        "observed": observed,
        "manual_grounding": [
            "Installed SIMLOX 2017 manual pp380-385 describes PMActivation and PMActivationProfile ENPM/CRIT overrides, nonoverlapping <LIMIT> periods, and the distinction between local ENPM and Control.ENPM.",
            "The manual says PM counters continue while local PM is disabled. The native run has no per-counter telemetry; this review infers accumulated eligibility only from later PM timing.",
            "Installed database dictionary columns are checked against both source tables.",
        ],
        "limits": [
            "This is one fixed-seed local activation profile N during 0-30 and Y during 30-60 with global Control.ENPM=Y.",
            "No PM event occurs at 24, and work begins at 30, but the run does not directly expose a per-aircraft PM counter or prove exactly when it first became due.",
            "PM start exactly at the 30-hour profile change is observed here, not a generic same-time boundary rule across models.",
            "The later PM at 55-56 is observed; its relation to the 24-hour CALHOURS interval is inferred from timing and frozen input rather than direct counter telemetry.",
            "Conversion has zero errors and two warnings (#108 event logging, #126 itemless teaching system); the run is not warning-free.",
            "Session-0 SSH, queue use, and GUI PID preservation are runner records. GUI visual content was not inspected.",
            "This does not establish D13.var02 CRIT=Y/N, MAXPM capacity limits, alternate PM profiles, other seeds, or cross-engine equivalence.",
        ],
        "publication_state": "candidate_review_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write review JSON here; stdout otherwise")
    args = parser.parse_args()
    result = replay()
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.output:
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.write_bytes(raw)
    else:
        sys.stdout.buffer.write(raw)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

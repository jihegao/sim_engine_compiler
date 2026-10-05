"""Independent, read-only replay of the sealed D03.var02 cancellation diagnostic.

This script does not import the case's behavior validator or ledger helper.
It never runs SIMLOX and writes only its own verdict JSON under review/.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
SUPPORT = CASE.parent
RUN = CASE / "runs" / "d03-var02-mission245-v012-ssh-20261006-01"
PARENT = SUPPORT / "D03-calendar-pm-v1.0.0"
PARENT_RUN = PARENT / "runs" / "d03-calendar-v100-ssh-20261001-02"
VERDICT = HERE / "independent-verdict.json"
EXPECTED_CHILD_CLOSURE = "0ddcb125d5350b913501445ceebcd2a8f2ceb30c0cb4f5dc36aa4bbe83f5718e"
EXPECTED_PARENT_CLOSURE = "9cd845f957105eb8659809ec09cf380ae5df68a63babb264d70631c164f7d2d8"
EXPECTED_CHILD_INPUT = "393f80c1c271d3687862c639bfc5e7aa1c534e7a375d9c773a2afb18066c1427"
EXPECTED_PARENT_INPUT = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
EXPECTED_AUTHOR_FAILURE = "0e83052ee12b8c99fe33a231652fd9a59a77b5702aa7da84b99505e57bdfcb87"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_with_native_trailing_comma(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = escaped = False
    for pos, char in enumerate(raw):
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
        elif char == "," and raw[pos + 1 :].lstrip().startswith(("]", "}")):
            continue
        else:
            out.append(char)
    return json.loads("".join(out))


def rows(document: dict, name: str, root: str) -> list[dict]:
    matches = [table for table in document[root]["tables"] if table["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"expected one {root}.{name}, got {len(matches)}")
    table = matches[0]
    fields = [column["name"] for column in table["columns"]]
    return [dict(zip(fields, row, strict=True))
            for instance in table["instances"] for row in instance["rows"]]


def event_map(log: str, suffix: str) -> dict[int, float]:
    pattern = (r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> "
               + re.escape(suffix) + r"$")
    pairs = [(int(identity), float(time)) for time, identity in re.findall(pattern, log, re.M)]
    if len({identity for identity, _ in pairs}) != len(pairs):
        raise ValueError(f"duplicate mission event {suffix}")
    return dict(pairs)


def event_times(log: str, text: str) -> list[float]:
    return [float(time) for time in re.findall(r"^Time: ([\d.]+) " + text + r"$", log, re.M)]


def same(got, want, tolerance=5e-5) -> bool:
    if isinstance(got, (int, float)) and not isinstance(got, bool) and isinstance(want, (int, float)) and not isinstance(want, bool):
        return math.isfinite(float(got)) and abs(float(got) - float(want)) <= tolerance
    return got == want


def main() -> int:
    tested = 0
    failures: list[str] = []

    def check(condition: bool, label: str) -> None:
        nonlocal tested
        tested += 1
        if not condition:
            failures.append(label)

    details = {}
    try:
        child_closure = json_with_native_trailing_comma(RUN / "closure.json")
        parent_closure = json_with_native_trailing_comma(PARENT_RUN / "closure.json")
        invocation = json_with_native_trailing_comma(RUN / "invocation.json")
        steps = json_with_native_trailing_comma(RUN / "steps.json")
        roundtrip = json_with_native_trailing_comma(RUN / "roundtrip-validation.json")
        author = json_with_native_trailing_comma(HERE / "author-native-validation-2026-10-06.json")
        child_input = json_with_native_trailing_comma(CASE / "native-input.json")
        parent_input = json_with_native_trailing_comma(PARENT / "native-input.json")
        exported = json_with_native_trailing_comma(RUN / "roundtrip-raw.json")
        child_report = json_with_native_trailing_comma(RUN / "report-raw.json")
        parent_report = json_with_native_trailing_comma(PARENT_RUN / "report-raw.json")
        log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")

        check(sha(RUN / "closure.json") == EXPECTED_CHILD_CLOSURE, "child closure literal SHA")
        check(sha(PARENT_RUN / "closure.json") == EXPECTED_PARENT_CLOSURE, "parent closure literal SHA")
        check(sha(CASE / "native-input.json") == EXPECTED_CHILD_INPUT, "child input literal SHA")
        check(sha(PARENT / "native-input.json") == EXPECTED_PARENT_INPUT, "parent input literal SHA")
        check(sha(HERE / "author-native-validation-2026-10-06.json") == EXPECTED_AUTHOR_FAILURE,
              "preserved original failed author verdict SHA")
        check(author["passed"] is False, "original author mission-first verdict remains FAIL")
        check(child_closure["error"] is None and parent_closure["error"] is None, "both closures complete")
        check(child_closure["invocation_sha256"] == sha(RUN / "invocation.json"), "child invocation seal")
        check(child_closure["source_hashes_before"] == child_closure["source_hashes_after"], "source stability")
        check(len(child_closure["raw"]) == 12 and len(parent_closure["raw"]) == 12, "12+12 raw files")
        for label, folder, closure in (("child", RUN, child_closure), ("parent", PARENT_RUN, parent_closure)):
            for name, seal in sorted(closure["raw"].items()):
                path = folder / name
                check(path.is_file(), f"{label} raw exists {name}")
                check(path.stat().st_size == seal["bytes"], f"{label} raw length {name}")
                check(sha(path) == seal["sha256"], f"{label} raw SHA {name}")

        source_paths = {
            "input": CASE / "native-input.json",
            "parent": PARENT / "native-input.json",
            "parent_signoff": PARENT / "cli-scope-signoff-2026-09-30.md",
            "parent_closure": PARENT_RUN / "closure.json",
            "a02_signoff": SUPPORT / "A02-single-aircraft-repeated-missions" / "cli-scope-signoff-2026-09-29.md",
            "b02_evidence": SUPPORT / "B02-serial-preparation-v1.0.2" / "evidence-2026-09-29.md",
            "contract_review": HERE / "independent-contract-go-2026-10-06.md",
            "contract": CASE / "contract.json",
            "builder": CASE / "build.py",
            "checker": CASE / "check_roundtrip.py",
            "diff_checker": CASE / "check_parent_diff.py",
            "validator": CASE / "validate_native_cli.py",
            "ledger": CASE / "reconstruct_system_ledger.py",
            "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
            "runner_script": CASE / "run_native_ssh.ps1",
            "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        }
        check(set(source_paths) == set(child_closure["source_hashes_before"]), "all source seal keys")
        for label, path in sorted(source_paths.items()):
            check(sha(path) == child_closure["source_hashes_before"][label], f"source SHA {label}")

        before = {table["name"]: table for table in child_input["model"]["tables"]}
        after = {table["name"]: table for table in exported["model"]["tables"]}
        populated = 0
        for name, table in before.items():
            authored_rows = [row for instance in table["instances"] for row in instance["rows"]]
            if not authored_rows:
                continue
            populated += 1
            native = after.get(name)
            check(native is not None, f"roundtrip table {name}")
            check(native is not None and table["columns"] == native["columns"], f"roundtrip columns {name}")
            native_rows = [row for instance in native["instances"] for row in instance["rows"]] if native else []
            check(authored_rows == native_rows, f"roundtrip rows {name}")
        check(populated == 18 and roundtrip["passed"] and len(roundtrip["populated_tables"]) == 18,
              "18 authored roundtrip tables and recorded checker pass")
        check(sha(RUN / "input.json") == EXPECTED_CHILD_INPUT, "copied child input")
        alternate = copy.deepcopy(child_input)
        mission_table = [table for table in alternate["model"]["tables"] if table["name"] == "OperationProfile"]
        check(len(mission_table) == 1, "one OperationProfile table")
        fields = [column["name"] for column in mission_table[0]["columns"]]
        mission_rows = mission_table[0]["instances"][0]["rows"]
        check(mission_rows[1][fields.index("STIM")] == 24.5, "child second STIM 24.5")
        mission_rows[1][fields.index("STIM")] = 20.0
        check(alternate == parent_input, "sole authored source delta is second STIM 20 to 24.5")

        check(invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True
              and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH session zero lineage")
        check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "global native mutex")
        check(invocation["gui"] == {"pid": 13340, "session_id": 1,
              "start_utc": "2026-09-28T10:09:56.8261381Z"}, "protected GUI identity")
        check([step["name"] for step in steps] == ["import", "export", "check_import_export", "calc", "jsonreport"],
              "five ordered guarded steps")
        for step in steps:
            check(step["status"] == "completed" and step["exit_code"] == 0
                  and step["gui_preserved"] is True, f"step complete and GUI retained {step['name']}")
        check("Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig"), "import marker")
        check("Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig"), "export marker")
        converter = (RUN / "run.log").read_text(encoding="utf-8-sig")
        check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter,
              "converter 0/2/0")
        check(sorted(re.findall(r"\(warning #(\d+)\)", converter)) == ["108", "126"]
              and not re.findall(r"\(error #\d+\)", converter), "only warnings 108 and 126")

        def prefix(text: str) -> list[str]:
            return [line for line in text.splitlines()
                    if (m := re.match(r"^Time: ([\d.]+) ", line)) and float(m[1]) < 19]
        check(prefix(log) == prefix(parent_log) and len(prefix(log)) == 30,
              "30 time-stamped event lines before h19 equal parent")
        allocation = event_map(log, "mission allocates system: <TEACH-AIR-01,0>")
        start = event_map(log, "mission starting, duration: 2 : <TEACH-AIR-01,0>")
        success = event_map(log, "mission success: ")
        completion = event_map(log, "mission completed: <TEACH-AIR-01,0>")
        cancellation = event_map(log, "mission cancelled: ")
        check(allocation == {0: 7.0, 1: 23.5, 2: 31.0}, "three allocations including booked identity 1")
        check(start == {0: 8.0, 2: 32.0}, "only identities 0 and 2 start")
        check(success == completion == {0: 10.0, 2: 34.0}, "two successes and completions")
        check(cancellation == {1: 24.8333}, "identity 1 cancels during first PM")
        pm_start = event_times(log, r" system PM task \d+ on <TEACH-AIR-01,0> started")
        pm_done = event_times(log, r" system PM task \d+ on <TEACH-AIR-01,0> completed")
        sub_start = event_times(log, r" subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours")
        sub_done = event_times(log, r" subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> completed")
        check(pm_start == sub_start == [24.0, 49.0], "two PM starts and one-hour subtasks")
        check(pm_done == sub_done == [25.0, 50.0], "two PM completions")
        check("Time: 24 <TEACH-AIR-01,BASE-01,0> System to PM <TEACH-AIR-01,0>" in log,
              "booked aircraft enters PM at h24")
        check("Time: 25 <TEACH-AIR-01,BASE-01,0> Maintained system arrives <TEACH-AIR-01,0>" in log,
              "aircraft exits PM at h25")
        details["events"] = {"allocated": allocation, "started": start, "succeeded": success,
                             "completed": completion, "cancelled": cancellation,
                             "pm_start": pm_start, "pm_complete": pm_done}

        system = rows(child_report, "SystemResults", "report")
        parent_system = rows(parent_report, "SystemResults", "report")
        stock = rows(child_report, "StockTotalResults", "report")
        parent_stock = rows(parent_report, "StockTotalResults", "report")
        summary = rows(child_report, "ResultSummary", "report")
        check(len(system) == len(stock) == len(parent_system) == len(parent_stock) == 120,
              "120 child and parent System/Stock bins")
        check(len(system[0]) == 40 and len(stock[0]) == 16, "40 System and 16 Stock fields")
        for label, series in (("system", system), ("stock", stock)):
            for i, row in enumerate(series):
                check(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2,
                      f"{label} grid row {i}")
        check([row for row in system if row["ETINT"] <= 19] ==
              [row for row in parent_system if row["ETINT"] <= 19], "System prefix through h19")

        forms = {state: next(row for row in parent_system if row["STINT"] == when)
                 for state, when in (("ready", 18.5), ("reserved", 19.5),
                                     ("mission", 20.5), ("pm", 24.5))}
        state_bins = {state: 0 for state in forms}
        for row in system:
            time = row["STINT"]
            states = []
            if any(a <= time < b for a, b in zip(pm_start, pm_done)):
                states.append("pm")
            if any(start[i] <= time < completion[i] for i in start):
                states.append("mission")
            reservation_ends = {0: start[0], 1: pm_start[0], 2: start[2]}
            if any(allocation[i] <= time < reservation_ends[i] for i in allocation):
                states.append("reserved")
            check(len(states) <= 1, f"no lifecycle overlap at h{time}")
            state = states[0] if states else "ready"
            state_bins[state] += 1
            expected = dict(forms[state])
            expected.update(STINT=time, ETINT=row["ETINT"], NPMS=int(time in pm_start),
                            NPMT=int(time in pm_done), NSYDT=int(time in pm_start),
                            SYDT=1 if time in pm_start else None)
            check(set(row) == set(expected), f"System schema at h{time}")
            for field, want in expected.items():
                check(same(row[field], want), f"System h{time} {field}")
        check(state_bins == {"ready": 103, "reserved": 5, "mission": 8, "pm": 4},
              "event-derived full-horizon state bins")
        for i, (actual, control) in enumerate(zip(stock, parent_stock)):
            check(set(actual) == set(control), f"Stock schema row {i}")
            for field, want in control.items():
                check(actual[field] == want, f"Stock row {i} {field}")
        check(len(summary) == 1 and len(summary[0]) == 11, "one 11-field summary")
        expected_summary = {"NREP": 1, "RTILW": 0, "RTIUP": 60,
                            "MTMF": 2 / 3, "RSMTMF": 0, "MSTF": 2 / 3,
                            "RSMSTF": 0, "MSUF": 2 / 3, "RSMSUF": 0,
                            "STMF": 2 / 3, "RSSTMF": 0}
        check(set(summary[0]) == set(expected_summary), "summary schema")
        for field, want in expected_summary.items():
            check(same(summary[0][field], want, 3e-8), f"summary {field}")
        integrals = {field: sum(float(row[field]) * .5 for row in system)
                     for field in ("NSYRY", "NSYA", "NSYMA", "NSYMO", "NSYPM")}
        expected_integrals = {"NSYRY": 51.5, "NSYA": 58, "NSYMA": 6.5,
                              "NSYMO": 4, "NSYPM": 2}
        for field, want in expected_integrals.items():
            check(same(integrals[field], want, 5e-5), f"integral {field}")
        check(sum(row["NPMS"] for row in system) == sum(row["NPMT"] for row in system) == 2,
              "two System PM starts/completions")
        check(all(row["NFAIL"] == 0 and row["NREPT"] == 0 for row in system),
              "no failure or repair markers")
        check(system[-1]["NSYRY"] == 1 and system[-1]["NSYMO"] == 0
              and system[-1]["NSYPM"] == 0, "terminal aircraft ready")
        check(all(row["NBO"] == 0 and row["NDF"] == 0 for row in stock),
              "item-free stock no backorder or demand")
        details.update(state_bins=state_bins, integrals=integrals,
                       report_summary=summary[0], system_field_comparisons=4800,
                       stock_field_comparisons=1920, summary_field_comparisons=11)
    except Exception as exc:  # A diagnostic exception is always a failed replay.
        failures.append(f"replay exception: {type(exc).__name__}: {exc}")

    observed_contract_failure = details.get("events", {}).get("cancelled") == {1: 24.8333}
    result = {
        "schema": "simlox-d03-var02-v012-independent-diagnostic/v1",
        "run_id": RUN.name,
        "diagnostic_evidence_passed": not failures,
        "v012_mission_first_contract_passed": False,
        "verdict": "NO_GO_FULL_CONTRACT" if observed_contract_failure and not failures else "NO_GO_EVIDENCE",
        "checks_count": tested,
        "failures": failures,
        "details": details,
        "limits": ["One fixed-seed aircraft and one shifted mission; no general PM priority rule.",
                   "The frozen v0.1.2 mission-first branch failed and remains excluded.",
                   "A new versioned, separately reviewed read-only checker may apply the previously approved v0.1.1 broader cancellation branch without native rerun."],
    }
    VERDICT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "diagnostic_evidence_passed": result["diagnostic_evidence_passed"],
                      "checks_count": tested, "failures": failures}, ensure_ascii=False))
    return 0 if result["diagnostic_evidence_passed"] and observed_contract_failure else 1


if __name__ == "__main__":
    raise SystemExit(main())

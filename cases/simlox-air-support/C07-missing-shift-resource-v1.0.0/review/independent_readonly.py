"""Independent standard-library, read-only replay of C07 ShiftResource variants."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "C07-cross-shift-gap-v1.0.0" / "draos-y-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
RUNS = {"qty-zero": "c07-shift-qty-zero-20260930-02", "row-absent": "c07-shift-row-absent-20260930-02"}
CHECKS: list[dict] = []


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_report(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    output = []
    quoted = escaped = False
    removed = 0
    for pos, char in enumerate(raw):
        if quoted:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            output.append(char)
        elif char == "," and raw[pos + 1 :].lstrip().startswith(("}", "]")):
            removed += 1
        else:
            output.append(char)
    return json.loads("".join(output)), removed


def check(name, passed, detail=None):
    item = {"name": name, "passed": bool(passed)}
    if detail is not None:
        item["detail"] = detail
    CHECKS.append(item)


def tables(document, root="model"):
    items = document[root]["tables"]
    keys = [table["name"] for table in items]
    return {table["name"]: table for table in items}, len(keys) == len(set(keys))


def rows(table):
    return [entry for instance in table["instances"] for entry in instance["rows"]]


def fields(table):
    return [column["name"] for column in table["columns"]]


def row(table):
    return dict(zip(fields(table), rows(table)[0]))


def bins(table):
    return {item["STINT"]: item for item in (dict(zip(fields(table), entry)) for entry in rows(table))}


def series(ranges):
    expected = {}
    for start, end, value in ranges:
        for half in range(int(start * 2), int(end * 2) + 1):
            expected[half / 2] = value
    return expected


def subtask(aircraft):
    return f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    index = load(CASE / "evidence-index.json")
    parent, unique_parent = tables(load(PARENT))
    check("accepted C07 cross-shift Y parent fingerprint", unique_parent and len(parent) == 35 and sha(PARENT) == contract["parent_input_sha256"] == diff["parent_sha256"] == "cab26bedc1c5bbadadc82476c34e6e4bd6e71624bebeebe46e4ca342a616674d")
    check("contract identity and candidate state", contract["schema"] == "simlox-c07-missing-shift-resource-contract/v1" and contract["case_id"] == "C07" and contract["variant_id"] == "C07.var02" and contract["version"] == "1.0.0-candidate" and contract["publication_state"] == "not_published")
    check("manual fingerprint and cited pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_pages"] == [227, 418, 419, 421, 422])
    check("declared source change scope", set(contract["changed_tables_from_parent"]) == set(diff["pair_changed_tables"]) == {"ProblemDescription", "ShiftResource"})
    index_runs = {entry["variant"]: entry for entry in index["runs"]}
    check("index identity and exactly accepted pair", index["schema"] == "simlox-c07-missing-shift-resource-evidence-index/v1" and index["relative_raw_root"] == "runs/" and index["raw_publication"] == "local_sealed_not_committed" and len(index["runs"]) == len(index_runs) == 2 and set(index_runs) == set(RUNS))
    check("index manual/native hashes and dictionary declaration", index["source_manual_sha256"] == sha(MANUAL) and index["source_dictionary_sha256"] == load(CASE.parent / "C07-offshift-boundary-v1.0.0" / "contract.json")["source_dictionary_sha256"] and index["simlox_exe_sha256"] == sha(EXE))
    excluded = index["excluded_diagnostic_runs"]
    check("earlier diagnostic runs explicitly excluded", len(excluded) == 2 and any(line.startswith("c07-shift-qty-zero-20260930-01:") for line in excluded) and any(line.startswith("c07-shift-row-absent-20260930-01:") for line in excluded) and all(entry["run_id"] not in ("c07-shift-qty-zero-20260930-01", "c07-shift-row-absent-20260930-01") for entry in index["runs"]))
    sources = {}
    reports = {}
    logs = {}

    for variant, run_id in RUNS.items():
        tag = variant + ": "
        source_path = CASE / f"{variant}-input.json"
        run = CASE / "runs" / run_id
        source, unique = tables(load(source_path))
        sources[variant] = source
        check(tag + "unique 35-table source", unique and len(source) == 35)
        check(tag + "source/run/contract/diff byte identity", sha(source_path) == sha(run / "input.json") == contract["input_sha256"][variant] == diff["children"][variant]["sha256"])
        changed = {name for name in parent | source if parent.get(name) != source.get(name)}
        check(tag + "exact parent table delta", changed == {"ProblemDescription", "ShiftResource"} == set(diff["children"][variant]["changed_tables"]), sorted(changed))
        check(tag + "all other parent tables identical", all(parent.get(name) == source.get(name) for name in parent | source if name not in changed))
        description = "C07 shift resource explicit zero; DRAOS=Y" if variant == "qty-zero" else "C07 shift resource row absent; DRAOS=Y"
        check(tag + "source description and DRAOS Y", rows(source["ProblemDescription"]) == [[description]] and row(source["Control"])["DRAOS"] == "Y")
        expected_shift_row = [["DAY-OPEN", "BASE-01", "P-CREW", 0, None, None]] if variant == "qty-zero" else []
        check(tag + "exact ShiftResource source row semantics", fields(source["ShiftResource"]) == ["SHID", "STID", "RID", "QTY", "MAXUT", "NOTE"] and rows(source["ShiftResource"]) == expected_shift_row and len(source["ShiftResource"]["instances"]) == 1)
        check(tag + "two nominal crew and two active shifts retained", rows(source["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]] and rows(source["ShiftProfile"]) == [["CREW-DAY", "DAY-OPEN", 8, 9, 1, None, None], ["CREW-DAY", "DAY-OPEN", 10, 11, 1, None, None]] and rows(source["TaskBreakDown"]) == [["PREP-FIXED", 1, "INSPECT", 2, None, None]])

        invocation = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        check(tag + "invocation run identity and source", invocation["case_id"] == "C07" and invocation["variant"] == variant and invocation["run_id"] == closure["run_id"] == run_id and Path(invocation["original_run_dir"]).resolve() == run.resolve() and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == sha(PARENT))
        check(tag + "session-zero SSH/mutex guard", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        check(tag + "GUI preserved across five steps", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and all(step["gui_preserved"] is True for step in steps))
        paths = {"input": run / "input.json", "parent": PARENT, "contract": CASE / "contract.json", "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(invocation["planned_check"]["executable"]), "simlox_exe": EXE}
        seals = invocation["source_hashes_before"]
        check(tag + "current frozen source/runtime byte hashes", all(path.exists() and sha(path) == seals[key] for key, path in paths.items()))
        check(tag + "before/after seals and invocation hash", closure["source_hashes_before"] == closure["source_hashes_after"] == seals and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None and all(invocation[key + "_sha256"] == seals[key] for key in ("contract", "builder", "checker", "runner_script", "simlox_exe")) and invocation["python_sha256"] == seals["python"])
        raw_files = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
        check(tag + "complete raw inventory", raw_files == set(closure["raw"]))
        for filename, meta in closure["raw"].items():
            path = run / filename
            check(tag + "raw byte seal " + filename, path.exists() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"])
        check(tag + "five successful ordered steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None for step in steps))
        check(tag + "planned commands and chronology", all(steps[i]["arguments"] == invocation["planned_commands"][i]["arguments"] for i in range(4)) and steps[4]["arguments"] == invocation["planned_check"]["arguments"] and all(stamp(step["started_utc"]) <= stamp(step["completed_utc"]) for step in steps) and all(stamp(steps[i]["completed_utc"]) <= stamp(steps[i + 1]["started_utc"]) for i in range(4)))
        indexed = index_runs[variant]
        check(tag + "index identity/path/raw fingerprints", indexed["run_id"] == run_id and Path(indexed["original_run_dir"]).resolve() == run.resolve() and indexed["input_sha256"] == sha(run / "input.json") and indexed["closure_sha256"] == sha(run / "closure.json") and indexed["model_log_sha256"] == sha(run / "model.log") and indexed["report_raw_sha256"] == sha(run / "report-raw.json"))
        check(tag + "index complete raw inventory equals closure", indexed["raw"] == closure["raw"])

        original, original_unique = tables(load(run / "input.json"))
        roundtrip, roundtrip_unique = tables(load(run / "roundtrip-raw.json"))
        populated = {name for name, table in original.items() if rows(table)}
        expected_count = 24 if variant == "qty-zero" else 23
        check(tag + "variant-specific populated source count", original_unique and roundtrip_unique and len(populated) == expected_count)
        for name in sorted(populated):
            check(tag + "exact populated native roundtrip " + name, original[name] == roundtrip.get(name))
        if variant == "row-absent":
            check(tag + "empty source row/native all-null placeholder", rows(original["ShiftResource"]) == [] and roundtrip["ShiftResource"]["columns"] == original["ShiftResource"]["columns"] and rows(roundtrip["ShiftResource"]) == [[None] * 6] and len(roundtrip["ShiftResource"]["instances"]) == 1)
        else:
            check(tag + "explicit zero row exact roundtrip", roundtrip["ShiftResource"] == original["ShiftResource"])
        imported = (run / "import.log").read_text(errors="replace")
        exported = (run / "export.log").read_text(errors="replace")
        converted = (run / "run.log").read_text(errors="replace")
        check(tag + "35-form import/export", "Number of forms inserted: 35" in imported and "Import completed!" in imported and "Export completed!" in exported)
        check(tag + "zero conversion errors and two known warnings", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == 1 and converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted)
        check(tag + "JSON report export complete", "Generating Json-report" in (run / "report-export.log").read_text(errors="replace"))

        log_bytes = (run / "model.log").read_bytes()
        logs[variant] = log_bytes
        log = log_bytes.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
        check(tag + "mission requests two systems", log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission activated, systems requested: 2") == 1 and log.count("mission allocates system:") == 2)
        for time, shift, crew in ((0, 0, 2), (8, 1, 0), (9, 2, 2), (10, 3, 0), (11, 4, 2)):
            check(tag + f"shift {shift} capacity at {time}", f"Time: {time}  resource shift {shift} starting at <P-CREW at <BASE-01,0>>, overlap time from previous = 0\n  Free resources at: <BASE-01,0> P-CREW {crew}" in log)
        for aircraft in (0, 1):
            sub = subtask(aircraft)
            check(tag + f"aircraft {aircraft} positive initial work", f"Time: 7.5  {sub} starts performing, planned to last for 2 hours" in log and f"Time: 8  {sub} is stopped due to shift change, time left= 1.5" in log)
            check(tag + f"aircraft {aircraft} gap work and second stop", f"Time: 9  {sub} resource received" in log and f"Time: 9  {sub} starts performing, planned to last for 1.5 hours" in log and f"Time: 10  {sub} is stopped due to shift change, time left= 0.5" in log)
            check(tag + f"aircraft {aircraft} final resume and completion", f"Time: 11  {sub} resource received" in log and f"Time: 11  {sub} starts performing, planned to last for 0.5 hours" in log and f"Time: 11.5  {sub} completed" in log and f"Time: 11.5 <TEACH-AIR-01,{aircraft}> preparation ended" in log)
        check(tag + "typed crew allocations and returns", log.count("<P-CREW at <BASE-01,0>> allocated to maintenance task: 1") == 6 and log.count("<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1") == 2)
        check(tag + "mission 12-13 success and terminal ready", "Time: 12 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1" in log and "Time: 13 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and "Time: 13 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:" in log and "mission cancelled" not in log and "Time: 13 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :" in log)

        report, removed = load_report(run / "report-raw.json")
        rt, report_unique = tables(report, "report")
        reports[variant] = rt
        check(tag + "six report tables and structural parse", report_unique and set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"} and removed > 0)
        summary = row(rt["ResultSummary"])
        check(tag + "one successful mission summary", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == 1)
        total = row(rt["ResourceResultsTotal"])
        check(tag + "resource total four work/four wait hours", total["NR"] == total["NRN"] == 2 and abs(total["NRUM"] * 36 - 4) < 1e-5 and abs(total["NRW"] * 36 - 4) < 1e-5 and total["NRMA"] == total["NRMO"] == 0)
        resource = bins(rt["ResourceResults"])
        system = bins(rt["SystemResults"])
        stock = bins(rt["StockTotalResults"])
        check(tag + "72 complete half-hour bins", all(len(ledger) == 72 and all(ledger[i / 2]["ETINT"] == (i + 1) / 2 for i in range(72)) for ledger in (resource, system, stock)))
        expected = {
            "NRUM": (resource, series([(7.5, 7.5, 2), (9, 9.5, 2), (11, 11, 2)])),
            "NRW": (resource, series([(8, 8.5, 2), (10, 10.5, 2)])),
            "NRA": (resource, series([(0, 7.5, 2), (9, 9.5, 2), (11, 35.5, 2)])),
            "NSYRY": (system, series([(0, 7, 2), (13, 35.5, 2)])),
            "NSYMA": (system, series([(7.5, 12.5, 2)])),
            "NSYMP": (system, series([(7.5, 11, 2)])),
            "NSYMO": (system, series([(12, 12.5, 2)])),
        }
        for field, (ledger, wanted) in expected.items():
            check(tag + "exact 72-bin " + field + " ledger", all(abs(ledger[i / 2][field] - wanted.get(i / 2, 0)) < 1e-6 for i in range(72)))
        check(tag + "nominal crew count and zero mission booking", all(resource[i / 2]["NR"] == resource[i / 2]["NRN"] == 2 and resource[i / 2]["NRMA"] == resource[i / 2]["NRMO"] == 0 for i in range(72)))
        check(tag + "zero stock events and terminal resource state", all(all(stock[i / 2][field] == 0 for field in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")) for i in range(72)) and resource[35.5]["NRUM"] == resource[35.5]["NRW"] == 0 and system[35.5]["NSYRY"] == 2)

    changed_pair = {name for name in sources["qty-zero"] | sources["row-absent"] if sources["qty-zero"].get(name) != sources["row-absent"].get(name)}
    check("pair differs exactly in description and ShiftResource", changed_pair == {"ProblemDescription", "ShiftResource"})
    check("accepted model logs byte-identical", logs["qty-zero"] == logs["row-absent"])
    check("parsed reports equal except description", all(reports["qty-zero"].get(name) == reports["row-absent"].get(name) for name in reports["qty-zero"] | reports["row-absent"] if name != "ProblemDescription") and reports["qty-zero"]["ProblemDescription"] != reports["row-absent"]["ProblemDescription"])
    failures = [item for item in CHECKS if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1", "case_id": "C07.var02.missing_shift_resource", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures), "failures": failures,
        "decision": "GO_bounded_explicit_zero_equals_missing_row" if not failures else "NO_GO",
        "accepted_scope": "In one DRAOS=Y two-shift, one-resource, one-seed model, an explicit ShiftResource.QTY=0 row and an absent row both expose zero crew during 8-9 and 10-11 shifts, two off shift, identical byte-level native event logs, and identical parsed reports except description. Each aircraft performs 7.5-8, pauses until 9, performs 9-10, pauses until 11, finishes 11.5; the 12-13 mission succeeds.",
        "roundtrip_interpretation": "The explicit-zero source has 24 row-containing tables and exactly roundtrips. The absent-row source has 23 row-containing tables and all 23 exactly roundtrip. Native export creates one all-null ShiftResource placeholder row for the absent source table; it is not a source row and is not treated as exact table equality.",
        "metric_interpretation": "ResourceResults.NRW is waiting demand, not booked work. Each accepted run records four crew-hours of positive work and four resource-hours of waiting across the two zero-capacity shifts; exact 72-bin resource/system/stock ledgers pass.",
        "limits": ["Earlier qty-zero -01 and row-absent -01 are excluded diagnostics; the latter's old checker rejected the native all-null placeholder. Only both immutable -02 runs are accepted.", "One station, one resource type, one seed, two first-day shifts and DRAOS=Y. This does not establish behavior for multiple resource types, recurring/overlapping shifts, DRAOS=N, or MAXUT.", "The index's dictionary fingerprint is consistent with the prior C07 contract declaration; its original file is unavailable for independent hashing. The installed manual PDF is hashed.", "SSH/GUI/queue evidence is replayed from sealed metadata; this reviewer did not rerun native SIMLOX."],
        "checks": CHECKS,
    }
    output = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

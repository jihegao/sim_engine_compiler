"""Independent stdlib read-only replay of the C08 partial-pool pair."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENTS = {
    "stagger-unlimited": CASE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json",
    "stagger-maxut": CASE.parent / "C08-shift-maxut-v1.0.0" / "maxut-one-input.json",
}
RUNS = {"stagger-unlimited": "c08-partial-unlimited-20260930-01", "stagger-maxut": "c08-partial-maxut-20260930-01"}
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
CHECKS: list[dict] = []


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path):
    raw = path.read_text(encoding="utf-8-sig")
    output = []
    quoted = escaped = False
    repairs = 0
    for index, char in enumerate(raw):
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
        elif char == "," and raw[index + 1 :].lstrip().startswith(("}", "]")):
            repairs += 1
        else:
            output.append(char)
    return json.loads("".join(output)), repairs


def check(name, condition, detail=None):
    item = {"name": name, "passed": bool(condition)}
    if detail is not None:
        item["detail"] = detail
    CHECKS.append(item)


def tables(document, key="model"):
    source = document[key]["tables"]
    names = [table["name"] for table in source]
    return {table["name"]: table for table in source}, len(names) == len(set(names))


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def columns(table):
    return [column["name"] for column in table["columns"]]


def row(table):
    return dict(zip(columns(table), rows(table)[0]))


def bins(table):
    return {record["STINT"]: record for record in (dict(zip(columns(table), values)) for values in rows(table))}


def grid(*ranges):
    expected = {}
    for start, end, value in ranges:
        for half in range(int(start * 2), int(end * 2) + 1):
            expected[half / 2] = value
    return expected


def ledger(label, actual, expected):
    check(label + " contiguous half-hour bins", len(actual) == 72 and all(actual[index / 2]["ETINT"] == (index + 1) / 2 for index in range(72)))
    fields = set(actual[0]) - {"RID", "STID", "UNID", "SID", "STINT", "ETINT"}
    check(label + " expected fields present", set(expected) <= fields)
    for field in sorted(fields):
        values = expected.get(field, {})
        if values is None:
            valid = all(actual[index / 2][field] is None for index in range(72))
        else:
            valid = all(isinstance(actual[index / 2][field], (int, float)) and abs(actual[index / 2][field] - values.get(index / 2, 0)) < 1e-6 for index in range(72))
        check(label + " exact 72-bin " + field, valid)


def subtask(aircraft):
    return f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    expected_parent_shas = ("e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e", "00e660275ace4d71d41cdafa725da2b552baeea9604756d94ad6b07de846e9d5")
    expected_child_shas = {"stagger-unlimited": "f69be976c2afa0515670f76737397b3fc1258b0fcc16a1243086ded579f34ee4", "stagger-maxut": "415c1a918dd643f3db869e28c02ceebbde68c887847df222ec3780ae9c4deb75"}
    check("contract/diff identity and accepted parent list", contract["schema"] == "simlox-c08-partial-pool-contract/v1" and contract["case_id"] == "C08" and contract["variant_id"] == "C08.var03" and contract["version"] == "1.0.0-candidate" and contract["publication_state"] == "not_published" and tuple(contract["accepted_parent_input_sha256"]) == expected_parent_shas and diff["schema"] == "simlox-c08-partial-pool-diff/v1")
    check("manual fingerprint/pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_physical_pages"] == [296, 402, 403, 404, 422, 423])
    sources = {}
    reports = {}
    logs = {}
    for variant in RUNS:
        tag = variant + ": "
        run_id = RUNS[variant]
        run = CASE / "runs" / run_id
        source_path = CASE / (variant + "-input.json")
        parent_path = PARENTS[variant]
        parent, unique_parent = tables(read(parent_path))
        child, unique_child = tables(read(source_path))
        sources[variant] = child
        check(tag + "parent and child hashes", unique_parent and unique_child and len(parent) == len(child) == 35 and sha(parent_path) == diff["accepted_parent_input_sha256"][variant] == contract["accepted_parent_input_sha256"][0 if variant == "stagger-unlimited" else 1] and sha(source_path) == sha(run / "input.json") == diff["child_input_sha256"][variant] == contract["input_sha256"][variant] == expected_child_shas[variant])
        changed = {name for name in parent | child if parent.get(name) != child.get(name)}
        check(tag + "exact three-table parent delta", changed == {"ProblemDescription", "MissionType", "OperationProfile"} and all(parent[name] == child[name] for name in parent if name not in changed), sorted(changed))
        old_mt, new_mt = row(parent["MissionType"]), row(child["MissionType"])
        check(tag + "NOS/MNOS 2→1 plus description", {field for field in old_mt | new_mt if old_mt.get(field) != new_mt.get(field)} == {"NOS", "MNOS", "DESCR"} and old_mt["NOS"] == old_mt["MNOS"] == 2 and new_mt["NOS"] == new_mt["MNOS"] == 1 and new_mt["DESCR"] == "One-hour single-aircraft mission, staggered pair")
        old_profile, new_profile = rows(parent["OperationProfile"]), rows(child["OperationProfile"])
        check(tag + "only second 28.5 scheduled mission added", len(old_profile) == 1 and len(new_profile) == 2 and old_profile == new_profile[:1] and new_profile[1][:5] == ["BASIC-SCHEDULE", "BASIC-MISSION", 28.5, "SCHEDULED", 1])
        check(tag + "common two-crew two-window source", row(child["ShiftResource"])["QTY"] == 2 and row(child["ShiftResource"])["MAXUT"] == (None if variant == "stagger-unlimited" else 1) and rows(child["ShiftProfile"]) == [["CREW-DAY", "DAY-OPEN", 23, 25, 1, None, None], ["CREW-DAY", "DAY-OPEN", 26, 28, 1, None, None]] and row(child["ResourceStationData"])["SHPID"] == "CREW-DAY" and row(child["Control"])["DRAOS"] == "N" and row(child["Control"])["RSEED"] == "1")

        invocation = read(run / "invocation.json")
        closure = read(run / "closure.json")
        steps = read(run / "steps.json")
        check(tag + "run source/parent identity", invocation["case_id"] == "C08" and invocation["variant"] == variant and invocation["run_id"] == closure["run_id"] == run_id and Path(invocation["original_run_dir"]).resolve() == run.resolve() and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == sha(parent_path))
        check(tag + "SSH session0/mutex/GUI", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and all(step["gui_preserved"] is True for step in steps))
        sealed = {"input": run / "input.json", "parent": parent_path, "contract": CASE / "contract.json", "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(invocation["planned_check"]["executable"]), "simlox_exe": EXE}
        before = invocation["source_hashes_before"]
        check(tag + "frozen source/runtime bytes", all(path.exists() and sha(path) == before[name] for name, path in sealed.items()))
        check(tag + "closure and invocation seals", closure["source_hashes_before"] == closure["source_hashes_after"] == before and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None and all(invocation[key + "_sha256"] == before[key] for key in ("contract", "builder", "checker", "runner_script", "simlox_exe")) and invocation["python_sha256"] == before["python"])
        raw_names = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
        check(tag + "complete raw inventory", raw_names == set(closure["raw"]))
        for filename, metadata in closure["raw"].items():
            path = run / filename
            check(tag + "raw seal " + filename, path.exists() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"])
        check(tag + "five ordered successful steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None and timestamp(step["started_utc"]) <= timestamp(step["completed_utc"]) for step in steps) and all(timestamp(steps[index]["completed_utc"]) <= timestamp(steps[index + 1]["started_utc"]) for index in range(4)))
        check(tag + "planned commands executed", all(steps[index]["arguments"] == invocation["planned_commands"][index]["arguments"] for index in range(4)) and steps[4]["arguments"] == invocation["planned_check"]["arguments"])

        original, original_unique = tables(read(run / "input.json"))
        roundtrip, roundtrip_unique = tables(read(run / "roundtrip-raw.json"))
        populated = {name for name in original if rows(original[name])}
        all_null = {name for name in populated if all(all(value is None for value in record) for record in rows(original[name]))}
        check(tag + "24 populated tables and null placeholders", original_unique and roundtrip_unique and len(populated) == 24 and all_null == {"ControlParameters", "GlobalParameters", "OperationParameter"})
        for name in sorted(populated):
            check(tag + "exact native roundtrip " + name, original[name] == roundtrip.get(name))
        imported = (run / "import.log").read_text(errors="replace")
        converted = (run / "run.log").read_text(errors="replace")
        check(tag + "zero conversion errors, warnings108/126", "Number of forms inserted: 35" in imported and "Import completed!" in imported and "Export completed!" in (run / "export.log").read_text(errors="replace") and "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted and "Generating Json-report" in (run / "report-export.log").read_text(errors="replace") and (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        logs[variant] = log
        check(tag + "two staggered mission orders and distinct aircraft", log.count("mission ordered: BASIC-MISSION") == 2 and "Time: 23.5 <TEACH-UNIT> mission ordered: BASIC-MISSION" in log and "Time: 24 <TEACH-UNIT> mission ordered: BASIC-MISSION" in log and log.count("mission allocates system:") == 2)
        check(tag + "two shift windows", all(f"Time: {hour}  resource shift {number} starting at <P-CREW at <BASE-01,0>>" in log for hour, number in ((23, 1), (25, 2), (26, 3), (28, 4))))
        check(tag + "first crew at 23.5, second at 24", f"Time: 23.5  {subtask(0)} starts performing, planned to last for 2 hours" in log and f"Time: 24  {subtask(1)} starts performing, planned to last for 2 hours" in log and log.count("allocated to maintenance task: 1") == 4)
        if variant == "stagger-unlimited":
            check(tag + "shift stop and next shift completion", f"Time: 25  {subtask(0)} is stopped due to shift change, time left= 0.5" in log and f"Time: 25  {subtask(1)} is stopped due to shift change, time left= 1" in log and f"Time: 26  {subtask(0)} starts performing, planned to last for 0.5 hours" in log and f"Time: 26  {subtask(1)} starts performing, planned to last for 1 hours" in log and f"Time: 26.5  {subtask(0)} completed" in log and f"Time: 27  {subtask(1)} completed" in log and "out of utilisation time" not in log)
        else:
            check(tag + "pooled MAXUT at 24.75", "Time: 23.5  <P-CREW at <BASE-01,0>> set time to max utilisation: 2" in log and "Time: 24  <P-CREW at <BASE-01,0>> set time to max utilisation: 0.75" in log and "Time: 24.75  <P-CREW at <BASE-01,0>> out of utilisation time" in log and f"Time: 24.75  {subtask(0)} is stopped due to resource time-out, time left= 0.75" in log and f"Time: 24.75  {subtask(1)} is stopped due to resource time-out, time left= 1.25" in log)
            check(tag + "reset26 and completions26.75/27.25", f"Time: 26  {subtask(0)} resource received" in log and f"Time: 26  {subtask(1)} resource received" in log and f"Time: 26  {subtask(0)} starts performing, planned to last for 0.75 hours" in log and f"Time: 26  {subtask(1)} starts performing, planned to last for 1.25 hours" in log and f"Time: 26.75  {subtask(0)} completed" in log and f"Time: 27.25  {subtask(1)} completed" in log)
        check(tag + "two successful staggered missions and ready2", all(f"Time: {start} <BASIC-MISSION,TEACH-UNIT,0,0,{index}> mission starting, duration: 1" in log and f"Time: {end} <BASIC-MISSION,TEACH-UNIT,0,0,{index}> mission success:" in log and f"Time: {end} <BASIC-MISSION,TEACH-UNIT,0,0,{index}> mission completed:" in log for index, start, end in ((0, 28, 29), (1, 28.5, 29.5))) and "mission cancelled" not in log and "Time: 29.5 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log)

        report_doc, repairs = native_report(run / "report-raw.json")
        report, report_unique = tables(report_doc, "report")
        reports[variant] = report
        check(tag + "six parseable native report tables", repairs > 0 and report_unique and set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"})
        summary, total = row(report["ResultSummary"]), row(report["ResourceResultsTotal"])
        wait = 2 if variant == "stagger-unlimited" else 2.5
        check(tag + "mission summary and four work/two or 2.5 wait hours", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == 1 and total["NR"] == total["NRN"] == 2 and abs(total["NRUM"] * 36 - 4) < 1e-5 and abs(total["NRW"] * 36 - wait) < 1e-5 and total["NRMO"] == total["NRMA"] == 0)
        resource = bins(report["ResourceResults"])
        system = bins(report["SystemResults"])
        stock = bins(report["StockTotalResults"])
        common_resource = {"NR": grid((0, 35.5, 2)), "NRN": grid((0, 35.5, 2))}
        common_system = {"NSYRY": grid((0, 23, 2), (23.5, 23.5, 1), (29, 29, 1), (29.5, 35.5, 2)), "NSYMA": grid((23.5, 23.5, 1), (24, 28.5, 2), (29, 29, 1)), "NSYMO": grid((28, 28, 1), (28.5, 28.5, 2), (29, 29, 1)), "NSYA": grid((0, 35.5, 2)), "FTMO": grid((28, 28, 0.5), (28.5, 28.5, 1), (29, 29, 0.5)), "STACC": grid((28, 28, 1), (28.5, 28.5, 2), (29, 29, 1)), "SYDT": None, "NPSTA": grid((23.5, 24, 1)), "NPSUC": grid((26.5, 27, 1))}
        if variant == "stagger-unlimited":
            resource_expected = common_resource | {"NRUM": grid((23.5, 23.5, 1), (24, 24.5, 2), (26, 26, 2), (26.5, 26.5, 1)), "NRW": grid((25, 25.5, 2)), "NRA": grid((23, 24.5, 2), (26, 27.5, 2))}
            system_expected = common_system | {"NSYMP": grid((23.5, 23.5, 1), (24, 26, 2), (26.5, 26.5, 1)), "NSYMR": grid((26.5, 26.5, 1), (27, 27.5, 2), (28, 28, 1))}
        else:
            resource_expected = common_resource | {"NRUM": grid((23.5, 23.5, 1), (24, 24, 2), (24.5, 24.5, 1), (26, 26, 2), (26.5, 26.5, 1.5), (27, 27, 0.5)), "NRW": grid((24.5, 24.5, 1), (25, 25.5, 2)), "NRA": grid((23, 24, 2), (24.5, 24.5, 1), (26, 27.5, 2))}
            system_expected = common_system | {"NSYMP": grid((23.5, 23.5, 1), (24, 26, 2), (26.5, 26.5, 1.5), (27, 27, 0.5)), "NSYMR": grid((26.5, 26.5, 0.5), (27, 27, 1.5), (27.5, 27.5, 2), (28, 28, 1))}
        ledger(tag + "ResourceResults", resource, resource_expected)
        ledger(tag + "SystemResults", system, system_expected)
        ledger(tag + "StockTotalResults", stock, {"PNB": grid((0, 35.5, 1)), "NBOU": None, "ROS": None, "ROST": None, "WT": None, "WTT": None, "WTS": None})
        check(tag + "terminal ready2, no work/wait", system[35.5]["NSYRY"] == 2 and resource[35.5]["NRUM"] == resource[35.5]["NRW"] == 0)

    unlimited, maxut = sources["stagger-unlimited"], sources["stagger-maxut"]
    pair_changed = {name for name in unlimited | maxut if unlimited.get(name) != maxut.get(name)}
    left, right = row(unlimited["ShiftResource"]), row(maxut["ShiftResource"])
    check("pair differs only MAXUT plus description", pair_changed == {"ProblemDescription", "ShiftResource"} and {field for field in left | right if left.get(field) != right.get(field)} == {"MAXUT"} and left["MAXUT"] is None and right["MAXUT"] == 1)
    check("pair event logs differ as expected", logs["stagger-unlimited"] != logs["stagger-maxut"] and "resource time-out" not in logs["stagger-unlimited"] and "resource time-out" in logs["stagger-maxut"])
    report_left, report_right = reports["stagger-unlimited"], reports["stagger-maxut"]
    check("pair report delta limited to resource/system/description", {name for name in report_left | report_right if report_left.get(name) != report_right.get(name)} == {"ProblemDescription", "ResourceResults", "ResourceResultsTotal", "SystemResults"} and report_left["ResultSummary"] == report_right["ResultSummary"] and report_left["StockTotalResults"] == report_right["StockTotalResults"])

    if (CASE / "evidence-index.json").exists():
        evidence = read(CASE / "evidence-index.json")
        entries = {entry["variant"]: entry for entry in evidence["runs"]}
        check("evidence index pinned pair inventory", sha(CASE / "evidence-index.json") == "f0c1e3da56681bbc7f50742cf42792177795497706d1049004e50e7a3a2d28b2" and evidence["schema"] == "simlox-c08-partial-pool-evidence-index/v1" and evidence["relative_raw_root"] == "runs/" and evidence["raw_publication"] == "local_sealed_not_committed" and evidence["excluded_diagnostic_run"] is None and len(evidence["runs"]) == 2 and set(entries) == set(RUNS) and evidence["source_manual_sha256"] == sha(MANUAL) and evidence["simlox_exe_sha256"] == sha(EXE))
        for variant, run_id in RUNS.items():
            run = CASE / "runs" / run_id
            entry = entries[variant]
            closure = read(run / "closure.json")
            check(variant + ": evidence index path and top-level hashes", entry["run_id"] == run_id and Path(entry["original_run_dir"]).resolve() == run.resolve() and entry["input_sha256"] == sha(run / "input.json") and entry["closure_sha256"] == sha(run / "closure.json") and entry["run_log_sha256"] == sha(run / "run.log") and entry["model_log_sha256"] == sha(run / "model.log") and entry["report_raw_sha256"] == sha(run / "report-raw.json"))
            check(variant + ": evidence index raw hashes", entry["raw"] == closure["raw"] == {name: {"bytes": (run / name).stat().st_size, "sha256": sha(run / name)} for name in closure["raw"]})

    failures = [item for item in CHECKS if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1", "case_id": "C08.var03.partial_pool", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures), "failures": failures,
        "decision": "GO_bounded_two_crew_staggered_partial_pool" if not failures else "NO_GO",
        "accepted_scope": "For this fixed-seed staggered two-crew pair, the unlimited control works one crew from 23.5-24 and two through 25, pauses at shift end, then finishes at 26.5/27. MAXUT=1 reaches the two-crew-hour first-shift pool limit at 24.75, stops with 0.75/1.25 hours remaining, resets at 26 and finishes at 26.75/27.25. Both runs succeed in separate missions 28-29 and 28.5-29.5.",
        "metric_interpretation": "Both have four resource-hours of positive work; NRW records 2 versus 2.5 resource-hours of waiting. Every numeric/null field in the 72 half-hour resource, system and stock ledgers is checked, including partial bins, and terminal ready2.",
        "limits": ["One fixed-seed stagger interval, two-crew pool, single station and two-window schedule on this executable. Other intervals, pool sizes, daily MUTILF interaction, GUI visuals and cross-engine equivalence remain unverified.", "Session/GUI/mutex continuity is replayed from sealed metadata; no native SIMLOX rerun was performed."],
        "checks": CHECKS,
    }
    output = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

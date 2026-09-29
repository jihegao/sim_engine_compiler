"""Independent, read-only replay of B03 source and sealed native evidence.

This module deliberately does not import the builder, validator, or shared
validation helpers. Its expected source delta and event timeline are written
from the B03 contract and published B02 parent.
"""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B02-serial-preparation-v1.0.2" / "native-input.json"
A02_SCOPE = HERE.parent / "A02-single-aircraft-repeated-missions" / "cli-scope-signoff-2026-09-29.md"
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
       "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}
CHANGED = ["MissionType", "OperationProfile", "MissionPreparation", "Tasks", "SubTaskType", "TaskBreakDown"]
OWNER = "<TEACH-AIR-01,0>"
WAVES = (("COLD-FIRST", 7.0, 8.0, 10.0, (10, 20)),
         ("HOT-SORTIE", 11.0, 12.0, 14.0, (10,)),
         ("HOT-SORTIE", 15.0, 16.0, 18.0, (10,)))
TIME = re.compile(r"^Time:\s*([\d.eE+\-]+)\s+([^\r\n]+)")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    # The 2017 report exporter emits trailing commas.
    return json.loads(re.sub(r",(?=\s*[}\]])", "", raw))


def tables(document: dict, envelope: str) -> dict[str, list[dict]]:
    result = {}
    for table in document[envelope]["tables"]:
        name = table["name"]
        if name in result or len(table["instances"]) != 1:
            raise ValueError(f"duplicate or multi-instance table: {name}")
        columns = [column["name"] for column in table["columns"]]
        if len(columns) != len(set(columns)):
            raise ValueError(f"duplicate columns: {name}")
        result[name] = [dict(zip(columns, row, strict=True)) for row in table["instances"][0]["rows"]]
    return result


def check_source() -> list[str]:
    errors = []
    contract = read(HERE / "contract.json")
    if any(contract.get(key) != value for key, value in {
        "schema": "simlox-b03-observable-contract/v1", "case_id": "B03", "version": "1.0.2",
        "business_profile": "explicit-mission-type-v1", "parent_case": "B02@1.0.2",
        "source_method_id": "M-B03",
        "source_manual_sha256": "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3",
        "aircraft_instance": OWNER, "unit_id": "TEACH-UNIT", "site_id": "BASE-01",
        "horizon_hours": 36, "report_interval_hours": .5,
    }.items()):
        errors.append("contract identity, manual binding, or observation scope differs")
    if contract.get("requires") != ["B02@1.0.2", "A02@1.0.0-cli-scope"] or contract.get("conversion") != {
        "errors": 0, "allowed_warning_counts": {"108": 1, "126": 1}
    }:
        errors.append("contract prerequisites or conversion allowlist differ")
    for path, field in ((PARENT, "parent_input_sha256"), (HERE / "native-input.json", "input_sha256"),
                        (HERE / "parent-diff.json", "parent_diff_sha256")):
        if sha(path) != contract.get(field):
            errors.append(f"source hash mismatch: {field}")
    parent, child = read(PARENT), read(HERE / "native-input.json")
    old, new = tables(parent, "model"), tables(child, "model")
    if list(old) != list(new):
        errors.append("model table set or order changed")
    changed = [name for name in old if old[name] != new.get(name)]
    if changed != CHANGED:
        errors.append(f"unexpected changed tables: {changed}")
    # Check the full document, including schema and metadata, after replacing
    # only the six authorized row collections with their B02 values.
    restored = copy.deepcopy(child)
    old_by_name = {table["name"]: table for table in parent["model"]["tables"]}
    for table in restored["model"]["tables"]:
        if table["name"] in CHANGED:
            table["instances"][0]["rows"] = copy.deepcopy(old_by_name[table["name"]]["instances"][0]["rows"])
    if restored != parent:
        errors.append("non-row source fields, schemas, or unchanged tables differ from B02")

    mission = old["MissionType"][0]
    profile = old["OperationProfile"][0]
    prep = old["MissionPreparation"][0]
    task = old["Tasks"][0]
    expect = {
        "MissionType": [dict(mission, MTID="COLD-FIRST", DESCR="Cold-first two-hour sortie"),
                        dict(mission, MTID="HOT-SORTIE", DESCR="Hot two-hour repeat sortie")],
        "OperationProfile": [dict(profile, SPRID="COLD-FIRST"), dict(profile, SPRID="HOT-SORTIE", STIM=12.0),
                             dict(profile, SPRID="HOT-SORTIE", STIM=16.0)],
        "MissionPreparation": [dict(prep, MTID="COLD-FIRST"),
                               dict(prep, MTID="HOT-SORTIE", TID="HOT-PREP")],
        "Tasks": [dict(task, DESCR="Cold-first serial 10+20-minute preparation"),
                  dict(task, TID="HOT-PREP", DESCR="Hot-sortie 10-minute preparation")],
        "SubTaskType": old["SubTaskType"] + [{"SUTID": "HOT-SERVICE", "DESCR": "HOT-SERVICE", "NOTE": None}],
        "TaskBreakDown": old["TaskBreakDown"] + [{"TID": "HOT-PREP", "SEQ": 1, "SUTID": "HOT-SERVICE",
                                                  "DURN": 10 / 60, "DURND": None, "NOTE": None}],
    }
    for name in CHANGED:
        if new.get(name) != expect[name]:
            errors.append(f"{name} does not match exact B02-derived delta")
    if [(m["mtid"], m["notice_hour"], m["launch_hour"], m["duration_hours"],
         m["task_id"], [(s["seq"], s["step_id"], s["minutes"]) for s in m["steps"]])
        for m in contract["missions"]] != [
            ("COLD-FIRST", 7, 8, 2, "PREP-FIXED", [(1, "INSPECT", 10), (2, "SERVICE", 20)]),
            ("HOT-SORTIE", 11, 12, 2, "HOT-PREP", [(1, "HOT-SERVICE", 10)]),
            ("HOT-SORTIE", 15, 16, 2, "HOT-PREP", [(1, "HOT-SERVICE", 10)])]:
        errors.append("contract mission schedule or recipe differs")
    if [(r["MTID"], r["NOPER"], r["DURN"]) for r in new["MissionType"]] != [
        ("COLD-FIRST", 1, 2), ("HOT-SORTIE", 1, 2)]:
        errors.append("mission notice/duration fields differ")
    declared = read(HERE / "parent-diff.json")
    expected_diff = {"schema": "simlox-b03-exact-parent-diff/v1", "parent_case": "B02@1.0.2",
                     "case_id": "B03", "version": "1.0.2", "parent_input_sha256": sha(PARENT),
                     "child_input_sha256": sha(HERE / "native-input.json"),
                     "unchanged_table_count": len(old) - len(CHANGED), "changed_tables_only": CHANGED,
                     "tables": {name: {"parent_rows": old[name], "child_rows": new[name]} for name in CHANGED}}
    if declared != expected_diff:
        errors.append("declared parent diff does not match independently computed delta")
    return errors


def event_rows(raw: str) -> list[tuple[int, float, str]]:
    return [(line, float(m[1]), m[2].strip()) for line, text in enumerate(raw.splitlines(), 1)
            if (m := TIME.match(text))]


def assert_events(events: list[tuple[int, float, str]]) -> list[str]:
    errors = []
    if not events or any(a[1] > b[1] + 1e-9 for a, b in zip(events, events[1:])):
        errors.append("native event timestamps missing or decreasing")

    def exact(label: str, marker: str, expected: list[tuple[float, str]]) -> None:
        observed = [(hour, body) for _, hour, body in events if marker in body]
        if len(observed) != len(expected) or any(
            abs(a[0] - w[0]) > 1e-4 or a[1] != w[1] for a, w in zip(observed, expected)
        ):
            errors.append(f"{label} events differ: {observed!r}")

    created = [(hour, body) for _, hour, body in events if " mission created:" in body]
    tags = [body.removesuffix(" mission created:") for _, body in created]
    if len(tags) != 3 or len(set(tags)) != 3 or any(
        not re.fullmatch(rf"<{re.escape(wave[0])},TEACH-UNIT,0,0,\d+>", candidate)
        for wave, candidate in zip(WAVES, tags)
    ):
        errors.append(f"mission instance identity or MTID differs: {created!r}")
        return errors
    expected = {
        "notice": (" mission ordered:", [(n, f"<TEACH-UNIT> mission ordered: {mtid}") for mtid, n, _, _, _ in WAVES]),
        "created": (" mission created:", [(n, f"{t} mission created:") for (_, n, _, _, _), t in zip(WAVES, tags)]),
        "allocated": (" mission allocates system:", [(n, f"{t} mission allocates system: {OWNER}") for (_, n, _, _, _), t in zip(WAVES, tags)]),
        "prep_start": (" preparation started,", [(n, f"{OWNER} preparation started, mission: {t}") for (_, n, _, _, _), t in zip(WAVES, tags)]),
        "prep_end": (" preparation ended,", [(n + sum(steps) / 60, f"{OWNER} preparation ended, mission: {t}") for (_, n, _, _, steps), t in zip(WAVES, tags)]),
        "launch": (" mission starting, duration:", [(start, f"{t} mission starting, duration: 2 : {OWNER}") for (_, _, start, _, _), t in zip(WAVES, tags)]),
        "success": (" mission success:", [(end, f"{t} mission success:") for (_, _, _, end, _), t in zip(WAVES, tags)]),
        "completed": (" mission completed:", [(end, f"{t} mission completed: {OWNER}") for (_, _, _, end, _), t in zip(WAVES, tags)]),
        "cancelled": (" mission cancelled:", []), "aborted": (" mission aborted:", []),
    }
    for label, (marker, wanted) in expected.items():
        exact(label, marker, wanted)

    tasks = [(line, hour, body) for line, hour, body in events if body.startswith("system preparation task ")]
    substeps = [(line, hour, body) for line, hour, body in events if body.startswith("subtask ")]
    if len(tasks) != 6:
        errors.append(f"expected six task lifecycle events; found {len(tasks)}")
    if len(substeps) != 20:
        errors.append(f"expected 20 subtask lifecycle events; found {len(substeps)}")
    for wave, (mtid, notice, launch, end, minutes) in enumerate(WAVES):
        start = notice
        finish = notice + sum(minutes) / 60
        matching_tasks = [(line, hour, body) for line, hour, body in tasks if abs(hour - start) < 1e-4 or abs(hour - finish) < 1e-4]
        task_nums = []
        for line, hour, body in matching_tasks:
            m = re.fullmatch(rf"system preparation task (\d+) on {re.escape(OWNER)} (started|completed)", body)
            if m:
                task_nums.append(m[1])
        if len(matching_tasks) != 2 or len(task_nums) != 2 or task_nums != [str(wave)] * 2 or (
            abs(matching_tasks[0][1] - start) > 1e-4 or not matching_tasks[0][2].endswith(" started") or
            abs(matching_tasks[1][1] - finish) > 1e-4 or not matching_tasks[1][2].endswith(" completed")
        ):
            errors.append(f"wave {wave} preparation task lifecycle differs: {matching_tasks!r}")
            continue
        task_no = task_nums[0]
        wanted = []
        clock = start
        previous_steps = sum(len(prior[4]) for prior in WAVES[:wave])
        for ordinal, duration in enumerate(minutes):
            base = f"subtask {previous_steps + ordinal} seqno {ordinal + 1} within system preparation task {task_no} on {OWNER}"
            wanted.extend([(clock, base + " started"), (clock, base + " requests resources: no resources needed"),
                           (clock, base + " resource availability test"),
                           (clock, base + f" starts performing, planned to last for {duration / 60:.6f} hours")])
            clock += duration / 60
            wanted.append((clock, base + " completed"))
        actual = [(hour, body) for _, hour, body in substeps if start - 1e-4 <= hour <= finish + 1e-4]
        if len(actual) != len(wanted) or any(abs(a[0] - w[0]) > 1e-4 or a[1] != w[1]
                                              for a, w in zip(actual, wanted)):
            errors.append(f"wave {wave} subtask order, recipe, or duration differs: {actual!r}")
        relevant = [(line, body) for line, hour, body in events if start - 1e-4 <= hour <= end + 1e-4]
        indices = {}
        for label, predicate in {
            "notice": lambda b: b == f"<TEACH-UNIT> mission ordered: {mtid}",
            "created": lambda b: b == f"{tags[wave]} mission created:",
            "allocated": lambda b: b == f"{tags[wave]} mission allocates system: {OWNER}",
            "prep_start": lambda b: b == f"{OWNER} preparation started, mission: {tags[wave]}",
            "prep_end": lambda b: b == f"{OWNER} preparation ended, mission: {tags[wave]}",
            "launch": lambda b: b == f"{tags[wave]} mission starting, duration: 2 : {OWNER}",
            "success": lambda b: b == f"{tags[wave]} mission success:",
            "completed": lambda b: b == f"{tags[wave]} mission completed: {OWNER}",
        }.items():
            found = [line for line, body in relevant if predicate(body)]
            if len(found) == 1:
                indices[label] = found[0]
        order = [indices.get(k, -1) for k in ("notice", "created", "allocated", "prep_start", "prep_end", "launch", "success", "completed")]
        if -1 in order or order != sorted(order) or len(set(order)) != len(order):
            errors.append(f"wave {wave} mission event order differs: {order}")
        elif not (indices["prep_start"] < matching_tasks[0][0] < matching_tasks[1][0] < indices["prep_end"]):
            errors.append(f"wave {wave} task did not execute inside preparation lifecycle")
    if any("resources needed" in body and "no resources needed" not in body for _, _, body in events):
        errors.append("native events contain resource requests")
    return errors


def check_report(report: dict) -> tuple[list[str], dict]:
    errors = []
    result = tables(report, "report")
    if list(result) != ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"]:
        errors.append(f"unexpected report table set or order: {list(result)}")
    summary = result.get("ResultSummary", [])
    if len(summary) != 1 or any(summary[0].get(k) != v for k, v in
                                {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": 1, "MSUF": 1}.items()):
        errors.append(f"ResultSummary differs: {summary!r}")
    intervals = result.get("SystemResults", [])
    if len(intervals) != 72:
        errors.append(f"expected 72 SystemResults intervals; found {len(intervals)}")
    totals = Counter()
    for index, row in enumerate(intervals):
        hour = index / 2
        expected = {"STINT": hour, "ETINT": hour + .5, "UNID": "Total over all Units",
                    "SID": "Total over all Systems", "NSYA": 1,
                    "NPSTA": int(hour in (7, 11, 15)), "NPSUC": int(hour in (7.5, 11, 15)),
                    "NSYMP": sum(max(0, min(hour + .5, e) - max(hour, s)) / .5
                                 for s, e in ((7, 7.5), (11, 11 + 1/6), (15, 15 + 1/6))),
                    "FTMO": int(any(s <= hour < s + 2 for s in (8, 12, 16))),
                    "NSYMO": int(any(s <= hour < s + 2 for s in (8, 12, 16)))}
        for key, wanted in expected.items():
            actual = row.get(key)
            if (not isinstance(actual, (int, float)) or abs(actual - wanted) > 1e-4) if key in (
                "NSYMP", "FTMO", "NSYMO") else actual != wanted:
                errors.append(f"SystemResults interval {index} {key}: expected {wanted}, got {row.get(key)}")
        for key in ("NPSTA", "NPSUC", "NSYMP", "FTMO", "NSYMO"):
            value = row.get(key)
            if isinstance(value, (int, float)):
                totals[key] += value if key in ("NPSTA", "NPSUC") else value * .5
    if any(abs(totals[key] - wanted) > 1e-8 for key, wanted in
           {"NPSTA": 3, "NPSUC": 3, "NSYMP": 5/6, "FTMO": 6, "NSYMO": 6}.items()):
        errors.append(f"SystemResults totals differ: {dict(totals)}")
    stock = result.get("StockTotalResults", [])
    if len(stock) != 72:
        errors.append(f"expected 72 StockTotalResults intervals; found {len(stock)}")
    for index, row in enumerate(stock):
        if row.get("STINT") != index / 2 or row.get("ETINT") != (index + 1) / 2 or any(
            row.get(field) != 0 for field in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")
        ):
            errors.append(f"StockTotalResults inventory or shortage ledger differs at {index}")
    unexpected = {name: len(rows) for name, rows in result.items()
                  if name != "StockTotalResults" and
                  re.search(r"resource|inventory|stock|personnel|equipment", name, re.I) and rows}
    if unexpected:
        errors.append(f"unexpected resource/inventory report rows: {unexpected}")
    return errors, {"system_result_intervals": len(intervals), "metric_totals": dict(totals)}


def check_evidence(run: Path) -> tuple[list[str], dict]:
    errors = []
    necessary = RAW | {"invocation.json", "closure.json", "validation.json", "run-manifest.json"}
    missing = [name for name in necessary if not (run / name).is_file() or (run / name).stat().st_size <= 4]
    if missing:
        return [f"missing or empty evidence: {missing}"], {}
    invocation, closure, manifest, validation = (read(run / name) for name in
                                                 ("invocation.json", "closure.json", "run-manifest.json", "validation.json"))
    contract = read(HERE / "contract.json")
    if set(closure.get("raw", {})) != RAW:
        errors.append("raw closure file set differs")
    for name, item in closure.get("raw", {}).items():
        path = run / name
        if not path.is_file() or path.stat().st_size != item.get("bytes") or sha(path) != item.get("sha256"):
            errors.append(f"raw closure mismatch: {name}")
    if sha(run / "input.json") != contract["input_sha256"]:
        errors.append("run input differs from checked candidate")
    expected_hashes = {"input_sha256": HERE / "native-input.json", "contract_sha256": HERE / "contract.json",
                       "builder_sha256": HERE / "build.py", "parent_diff_sha256": HERE / "parent-diff.json",
                       "validator_sha256": HERE / "validate.py", "runner_sha256": HERE / "run_native_ssh.ps1",
                       "launcher_sha256": HERE / "invoke_loopback.ps1", "parent_input_sha256": PARENT,
                       "a02_scope_sha256": A02_SCOPE}
    for field, path in expected_hashes.items():
        if not path.is_file() or invocation.get(field) != sha(path):
            errors.append(f"invocation source hash mismatch: {field}")
    if any(invocation.get(k) != v for k, v in {"schema": "simlox-b03-invocation/ssh-cli-v1",
                                               "case_id": "B03", "case_version": "1.0.2",
                                               "execution_mode": "ssh_cli_v1", "session_id": 0,
                                               "ssh_connection_present": True,
                                               "simlox_exe_sha256": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
                                               "queue_mutex": "Global\\SimloxIssue18NativeQueue"}.items()):
        errors.append("native invocation identity or SSH provenance differs")
    if invocation.get("host_name", "").lower() != "4700-3" or invocation.get("session_name") or invocation.get("ssh_client_present") is not True:
        errors.append("native host or SSH session fields differ")
    if invocation.get("original_run_dir", "").lower() != str(run.resolve()).lower() or invocation.get("run_id") != run.name:
        errors.append("invocation run directory or ID differs")
    if "sshd.exe" not in invocation.get("ssh_ancestor_names", []):
        errors.append("native invocation lacks sshd ancestry")
    gui = invocation.get("coexisting_gui") or {}
    if not invocation.get("allow_existing_gui") or any(gui.get(k) != v for k, v in
        {"pid": 13340, "session_id": 1, "process_start_utc": "2026-09-28T10:09:56.8261381Z",
         "responding_at_preflight": True}.items()) or not gui.get("session_query_line"):
        errors.append("preserved GUI process identity differs")
    if closure.get("schema") != "simlox-b03-closure/v1" or closure.get("case_id") != "B03" or closure.get("case_version") != "1.0.2" or closure.get("run_id") != invocation.get("run_id") or closure.get("input_sha256") != contract["input_sha256"] or closure.get("invocation_sha256") != sha(run / "invocation.json"):
        errors.append("raw closure identity or invocation binding differs")
    if any(manifest.get(k) != v for k, v in
           {"schema": "simlox-b03-run-manifest/v1", "case_id": "B03", "case_version": "1.0.2",
            "run_id": invocation.get("run_id"), "input_sha256": contract["input_sha256"],
            "invocation_sha256": sha(run / "invocation.json"), "closure_sha256": sha(run / "closure.json"),
            "validation_sha256": sha(run / "validation.json"), "execution_mode": "ssh_cli_v1"}.items()):
        errors.append("run manifest chain or identity differs")
    if not validation.get("passed") or validation.get("differences"):
        errors.append("source-bound validation did not pass")
    steps = read(run / "steps.json")
    if [s.get("name") for s in steps] != ["import", "export", "calc", "jsonreport"] or any(
        s.get("exit_code") != 0 or s.get("coexisting_gui_present_after") is not True or
        not s.get("started_utc") or not s.get("completed_utc") for s in steps):
        errors.append("native step sequence, exit code, or GUI coexistence differs")
    source = tables(read(run / "input.json"), "model")
    exported = tables(read(run / "roundtrip-raw.json"), "model")
    if list(source) != list(exported):
        errors.append("roundtrip table set or order differs")
    def business(rows: list[dict]) -> list[dict]:
        return [row for row in rows if any(value not in (None, "") for value in row.values())]

    for name, original in source.items():
        if business(original) != business(exported.get(name, [])):
            errors.append(f"roundtrip business rows differ: {name}")
    for name, rows in source.items():
        if re.search(r"resource|inventory|stock|personnel|equipment", name, re.I) and rows:
            errors.append(f"unexpected source resource/inventory rows: {name}")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", run_log))
    if not conversion or conversion.group(1, 2) != ("0", "2") or warnings != Counter({"108": 1, "126": 1}):
        errors.append(f"conversion errors or warning allowlist differs: {dict(warnings)}")
    errors.extend(assert_events(event_rows((run / "model.log").read_text(encoding="utf-8-sig", errors="replace"))))
    report_errors, report_details = check_report(read(run / "report-raw.json"))
    errors.extend(report_errors)
    details = {"run_id": invocation.get("run_id"), "raw_closure_count": len(closure.get("raw", {})),
               "roundtrip_business_tables": sum(any(any(value not in (None, "") for value in row.values())
                                                for row in rows) for rows in source.values()), **report_details,
               "hashes": {name: sha(run / name) for name in ("invocation.json", "closure.json",
                           "run-manifest.json", "validation.json", "model.sxi", "model.sxo",
                           "model.log", "report-raw.json")}}
    return errors, details


def review(run: Path) -> dict:
    errors = check_source()
    evidence_errors, details = check_evidence(run)
    errors.extend(evidence_errors)
    return {"schema": "simlox-b03-independent-readonly-review/v1", "case_id": "B03", "version": "1.0.2",
            "passed": not errors, "differences": errors, "reviewer_sha256": sha(HERE / "review_readonly.py"),
            **details}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: review_readonly.py RUN_DIRECTORY")
    result = review(Path(sys.argv[1]))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

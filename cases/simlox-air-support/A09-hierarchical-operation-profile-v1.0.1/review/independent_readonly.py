"""Independent, read-only replay of sealed A09 v1.0.1 native CLI evidence.

This script uses only Python's standard library and does not import project code.
It never runs SIMLOX or the author's builder, runner, or validator.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CASE = REPO / "cases/simlox-air-support/A09-hierarchical-operation-profile-v1.0.1"
OLD = REPO / "cases/simlox-air-support/A09-hierarchical-operation-profile"
A02 = REPO / "cases/simlox-air-support/A02-single-aircraft-repeated-missions"
RUN = Path(r"C:\Users\user\Documents\Codex\2026-09-29\simlox-a09-v101-ed46e1c02e64\repo\cases\simlox-air-support\A09-hierarchical-operation-profile-v1.0.1\runs\a09-v101-20260929-01")
FLAT = Path(r"C:\Users\user\Documents\Codex\2026-09-29\simlox-a09-1c7a7bda5088\repo\cases\simlox-air-support\A09-hierarchical-operation-profile\runs\a09-flat-nested-20260929-02-flat")
SNAP = Path(r"C:\Users\user\Documents\Codex\2026-09-29\simlox-a09-v101-ed46e1c02e64\repo")
OUT = CASE / "review/independent-readonly-2026-09-29.json"

failures: list[str] = []
checks: dict[str, object] = {}


def ck(name: str, actual, expected) -> None:
    ok = actual == expected
    entry = {"passed": ok}
    if not ok or (isinstance(actual, (str, int, float, bool, type(None), list, tuple)) and len(str(actual)) <= 200):
        entry.update({"actual": actual, "expected": expected})
    checks[name] = entry
    if not ok:
        failures.append(name)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # SIMLOX's raw JSON report ends its tables array with a trailing comma.
        # Strip commas before a closing bracket only while outside JSON strings.
        cleaned = []
        in_string = escaped = False
        for i, c in enumerate(raw):
            if in_string:
                cleaned.append(c)
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == '"':
                    in_string = False
            elif c == '"':
                in_string = True
                cleaned.append(c)
            elif c == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
                continue
            else:
                cleaned.append(c)
        return json.loads("".join(cleaned))


def table(doc, name: str, root="model"):
    found = [t for t in doc[root]["tables"] if t["name"] == name]
    assert len(found) == 1, (name, len(found))
    t = found[0]
    cols = [c["name"] for c in t["columns"]]
    assert len(cols) == len(set(cols))
    rows = [dict(zip(cols, r)) for instance in t["instances"] for r in instance["rows"]]
    return rows


def business(doc):
    return {t["name"]: table(doc, t["name"]) for t in doc["model"]["tables"] if any(i["rows"] for i in t["instances"])}


def event_rows(log: str, phrase: str):
    rows = []
    for line in log.splitlines():
        if phrase in line:
            m = re.match(r"Time: ([0-9.]+) (.*)", line)
            assert m, line
            rows.append((float(m.group(1)), m.group(2)))
    return rows


def tags(rows):
    return [re.search(r"<BASIC-MISSION,TEACH-UNIT,0,0,\d+>", text).group(0) for _, text in rows]


def main():
    contract = data(CASE / "contract.json")
    invocation = data(RUN / "invocation.json")
    closure = data(RUN / "closure.json")
    manifest = data(RUN / "run-manifest.json")
    steps = data(RUN / "steps.json")
    candidate = data(CASE / "native-nested.json")
    previous = data(OLD / "native-nested.json")
    parent = data(A02 / "native-input.json")
    flat_source = data(OLD / "native-flat.json")
    input_doc = data(RUN / "input.json")
    roundtrip = data(RUN / "roundtrip-raw.json")
    report = data(RUN / "report-raw.json")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")

    for label, path, expected in [
        ("A02 source", A02 / "native-input.json", contract["parent_input_sha256"]),
        ("previous source", OLD / "native-nested.json", contract["previous_input_sha256"]),
        ("flat source", OLD / "native-flat.json", contract["flat_control_sha256"]),
        ("candidate source", CASE / "native-nested.json", contract["candidate_input_sha256"]),
        ("run input", RUN / "input.json", contract["candidate_input_sha256"]),
        ("frozen contract", CASE / "contract.json", invocation["contract_sha256"]),
        ("invocation", RUN / "invocation.json", closure["invocation_sha256"]),
        ("closure", RUN / "closure.json", manifest["closure_sha256"]),
        ("validation identity", RUN / "validation.json", manifest["validation_sha256"]),
        ("snapshot builder", SNAP / "cases/simlox-air-support/A09-hierarchical-operation-profile-v1.0.1/build.py", invocation["builder_sha256"]),
        ("snapshot runner", SNAP / "cases/simlox-air-support/A09-hierarchical-operation-profile-v1.0.1/run_native_ssh.ps1", invocation["runner_sha256"]),
        ("snapshot validator", SNAP / "cases/simlox-air-support/A09-hierarchical-operation-profile-v1.0.1/validate_native_cli.py", invocation["native_validator_sha256"]),
        ("snapshot parser", SNAP / "cases/simlox-air-support/tools/validate_native.py", invocation["shared_parser_sha256"]),
        ("snapshot binding", SNAP / "cases/simlox-air-support/tools/native_binding.py", invocation["shared_binding_sha256"]),
        ("pinned native executable", Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"), invocation["simlox_exe_sha256"]),
        ("pinned Python executable", Path(invocation["python_path"]), invocation["python_exe_sha256"]),
    ]:
        ck("sha256 " + label, sha(path), expected)
    ck("run input equals candidate source", input_doc, candidate)
    ck("invocation source", invocation["input_sha256"], contract["candidate_input_sha256"])
    ck("invocation parent", invocation["parent_input_sha256"], contract["parent_input_sha256"])
    ck("invocation previous", invocation["previous_input_sha256"], contract["previous_input_sha256"])
    ck("invocation flat", invocation["flat_control_sha256"], contract["flat_control_sha256"])
    ck("invocation run path", invocation["original_run_dir"].lower(), str(RUN).lower())
    ck("snapshot contract", sha(SNAP / "cases/simlox-air-support/A09-hierarchical-operation-profile-v1.0.1/contract.json"), invocation["contract_sha256"])
    ck("snapshot candidate", sha(SNAP / "cases/simlox-air-support/A09-hierarchical-operation-profile-v1.0.1/native-nested.json"), invocation["input_sha256"])
    ck("invocation CLI session", (invocation["execution_mode"], invocation["session_id"], invocation["ssh_connection_present"], invocation["ssh_client_present"]), ("ssh_cli_v1", 0, True, True))
    ck("coexisting GUI identity", (invocation["coexisting_gui"]["pid"], invocation["coexisting_gui"]["session_id"]), (13340, 1))
    ck("manifest run ID", manifest["run_id"], invocation["run_id"])
    ck("manifest input", manifest["input_sha256"], sha(RUN / "input.json"))
    ck("manifest invocation", manifest["invocation_sha256"], sha(RUN / "invocation.json"))
    for name, sealed in closure["raw"].items():
        path = RUN / name
        ck("closure " + name, (path.stat().st_size, sha(path)), (sealed["bytes"], sealed["sha256"]))
    ck("closure raw count", len(closure["raw"]), 11)
    ck("step names", [s["name"] for s in steps], ["import", "export", "calc", "jsonreport"])
    ck("step exits", [s["exit_code"] for s in steps], [0, 0, 0, 0])
    ck("step GUI continuity", [(s["gui_state_check_passed"], s["coexisting_gui_present_after"], s["launch_error"]) for s in steps], [(True, True, None)] * 4)
    ck("step order", all(steps[i]["completed_utc"] <= steps[i+1]["started_utc"] for i in range(3)), True)
    ck("step run path", all(str(RUN).lower() in s["arguments"].lower() for s in steps), True)
    ck("import completion", "Import completed!" in (RUN / "import.log").read_text(), True)
    runlog = (RUN / "run.log").read_text()
    ck("conversion", re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog).groups(), ("0", "2", "0"))
    ck("warning IDs", re.findall(r"warning #(\d+)", runlog), ["108", "126"])
    ck("native result saved", "Saving results" in runlog and "Total execution time" in runlog, True)
    ck("roundtrip business", business(input_doc), {k: table(roundtrip, k) for k in business(input_doc)})
    ck("all nonempty tables count", len(business(input_doc)), 13)
    ck("10 operating business tables count", len(set(business(input_doc)) - {"ProblemDescription", "ControlParameters", "GlobalParameters"}), 10)

    # A09 v1.0.1 differs from v1.0.0 in one cell only.
    expected = copy.deepcopy(previous)
    root = [t for t in expected["model"]["tables"] if t["name"] == "OperationProfile"][0]
    names = [c["name"] for c in root["columns"]]
    idx = names.index("IPER")
    rows = root["instances"][0]["rows"]
    roots = [r for r in rows if r[names.index("PRID")] == "BASIC-SCHEDULE" and r[names.index("SPRID")] == "A09-DAILY-TWO-WAVE" and r[names.index("STIM")] == 0]
    ck("one target root", len(roots), 1)
    ck("previous IPER", roots[0][idx], 24)
    roots[0][idx] = 48
    ck("one-cell revision", candidate, expected)
    ck("revised root", [r for r in table(candidate, "OperationProfile") if r["PRID"] == "BASIC-SCHEDULE"], [dict(zip(names, roots[0]))])
    ck("parent source identity", sha(A02 / "native-input.json"), contract["parent_input_sha256"])
    ck("parent signoff exists", (A02 / "cli-scope-signoff-2026-09-29.md").exists(), True)
    parent_diff = data(OLD / "parent-diff-nested.json")["changed_tables"]
    calculated = {}
    for name in set(business(parent)) | set(business(previous)):
        before, after = table(parent, name), table(previous, name)
        if before != after:
            calculated[name] = {"before_rows": before, "after_rows": after}
    ck("parent diff", calculated, parent_diff)
    ck("flat source identity", sha(OLD / "native-flat.json"), contract["flat_control_sha256"])

    expected_times = contract["v101_prediction_if_candidate_rule_holds"]
    phrases = {"ordered": "mission ordered:", "created": "mission created:", "activated": "mission activated,", "allocated": "mission allocates system:", "started": "mission starting,", "succeeded": "mission success:", "completed": "mission completed:"}
    events = {key: event_rows(log, phrase) for key, phrase in phrases.items()}
    ck("ordered hours", [t for t, _ in events["ordered"]], expected_times["notification_hours"])
    ck("created hours", [t for t, _ in events["created"]], expected_times["notification_hours"])
    ck("started hours", [t for t, _ in events["started"]], expected_times["launch_hours"])
    ck("completed hours", [t for t, _ in events["completed"]], expected_times["completion_hours"])
    ck("four unique tags", tags(events["created"]), [f"<BASIC-MISSION,TEACH-UNIT,0,0,{i}>" for i in range(4)])
    for key in ("activated", "allocated", "started", "succeeded", "completed"):
        ck("tag order " + key, tags(events[key]), tags(events["created"]))
    ck("allocated aircraft", all("<TEACH-AIR-01,0>" in text for _, text in events["allocated"]), True)
    ck("start aircraft", all("<TEACH-AIR-01,0>" in text for _, text in events["started"]), True)
    ck("complete aircraft", all("<TEACH-AIR-01,0>" in text for _, text in events["completed"]), True)
    ck("no cancellation or abort", not re.search(r"mission (cancel|abort)", log, re.I), True)
    ck("ready increase hours", [t for t, _ in event_rows(log, "nbr ready increased at unit:")], [0, 10, 22, 34, 46])
    ck("ready decrease hours", [t for t, _ in event_rows(log, "nbr ready decreased at unit:")], [7, 19, 31, 43])
    ck("eight System ready events", [t for t, _ in event_rows(log, "System ready <")], [10, 10, 22, 22, 34, 34, 46, 46])
    ck("systems ready hours", [t for t, _ in event_rows(log, "systems ready:")], [0, 10, 22, 34, 46])
    ck("soon ready hours", [t for t, _ in event_rows(log, "System soon ready")], [10, 22, 34, 46])

    summary = table(report, "ResultSummary", "report")
    ck("result summary", summary, [{"NREP": 1, "RTILW": 0, "RTIUP": 48, "MTMF": 1, "RSMTMF": 0, "MSTF": 1, "RSMSTF": 0, "MSUF": 1, "RSMSUF": 0, "STMF": 1, "RSSTMF": 0}])
    sysrows = table(report, "SystemResults", "report")
    ck("96 system intervals", len(sysrows), 96)
    ck("contiguous half-hour intervals", [(r["STINT"], r["ETINT"]) for r in sysrows], [(i / 2, (i + 1) / 2) for i in range(96)])
    ck("system identity", {(r["UNID"], r["SID"]) for r in sysrows}, {("Total over all Units", "Total over all Systems")})
    flight = [(8, 10), (20, 22), (32, 34), (44, 46)]
    notice = [7, 19, 31, 43]
    ck("STACC flight profile", [r["STACC"] for r in sysrows], [int(any(a <= i/2 < b for a,b in flight)) for i in range(96)])
    ck("NSYMO flight profile", [r["NSYMO"] for r in sysrows], [int(any(a <= i/2 < b for a,b in flight)) for i in range(96)])
    ck("NPSTA all zero", {r["NPSTA"] for r in sysrows}, {0})
    ck("result intervals match flat", sysrows, table(data(FLAT / "report-raw.json"), "SystemResults", "report"))
    ck("all report tables match flat", report, data(FLAT / "report-raw.json"))
    ck("model log byte match flat", sha(RUN / "model.log"), sha(FLAT / "model.log"))
    ck("report byte match flat", sha(RUN / "report-raw.json"), sha(FLAT / "report-raw.json"))
    ck("pinned flat log", sha(FLAT / "model.log"), contract["v100_native_flat_control"]["model_log_sha256"])
    ck("pinned flat report", sha(FLAT / "report-raw.json"), contract["v100_native_flat_control"]["report_raw_sha256"])

    # In-memory negative controls: each independent predicate must reject a
    # single altered field without touching any retained run file.
    altered = copy.deepcopy(input_doc)
    altered["model"]["tables"][0]["instances"][0]["rows"][0][0] = "tampered"
    ck("negative control source identity rejects change", altered != candidate, True)
    altered_created = copy.deepcopy(events["created"])
    altered_created[0] = (7.5, altered_created[0][1])
    ck("negative control event time rejects change", [t for t, _ in altered_created] != expected_times["notification_hours"], True)
    altered_created = copy.deepcopy(events["created"])
    altered_created[0] = (altered_created[0][0], altered_created[0][1].replace(",0,0,0>", ",0,0,9>"))
    ck("negative control mission identity rejects change", tags(altered_created) != tags(events["created"]), True)
    altered_rows = copy.deepcopy(sysrows)
    altered_rows[16]["STACC"] = 0
    ck("negative control interval rejects change", altered_rows != table(data(FLAT / "report-raw.json"), "SystemResults", "report"), True)
    ck("negative control hash rejects change", hashlib.sha256((RUN / "model.log").read_bytes() + b"x").hexdigest() != closure["raw"]["model.log"]["sha256"], True)

    result = {"schema": "simlox-a09-v101-independent-readonly-review/v1", "reviewer_script_sha256": sha(Path(__file__)), "run_id": invocation["run_id"], "source_run_dir": str(RUN), "review_scope": "raw native CLI evidence only; no native or GUI execution", "passed": not failures, "failures": failures, "checks": checks, "evidence_note": "Native report-raw.json has a trailing comma before the tables closing bracket; its byte hash was checked before a string-aware trailing-comma normalization for independent parsing.", "limits": ["One candidate run supports only the tested IPER=48, IQTY=2 schedule; it does not prove a general expansion formula.", "The recorded GUI review is partial and outside this read-only replay.", "This review does not publish A09 or establish cross-engine equivalence."]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False, default=list) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "failures": failures, "check_count": len(checks), "report": str(OUT)}, indent=2))
    return result["passed"]


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

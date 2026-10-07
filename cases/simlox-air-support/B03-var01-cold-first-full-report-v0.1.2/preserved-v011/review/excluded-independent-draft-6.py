"""Independent read-only B03.var01 retrospective source/event/report replay.

Uses only the standard library. The default command prints a verdict and writes
nothing. It does not import the historical or current author checkers.
"""

import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = next(p for p in HERE.parents if (p / ".git").exists())
CASES = REPO / "cases" / "simlox-air-support"
CONTRACT_SHA = "3c487385f4a160b7994b9533deaacba8c4a91de6cdf032812316bb6a2ca287c8"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def seal(path, pin):
    raw = path.read_bytes()
    assert len(raw) == pin["bytes"] and sha(raw) == pin["sha256"], str(path)
    return raw


def native_json_bytes(raw):
    """Remove structural native trailing commas without changing quoted text."""
    source = raw.decode("utf-8-sig")
    result = []
    quoted = escaped = False
    for pos, char in enumerate(source):
        if quoted:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
            result.append(char)
        elif char == ",":
            next_pos = pos + 1
            while next_pos < len(source) and source[next_pos].isspace():
                next_pos += 1
            if next_pos >= len(source) or source[next_pos] not in "]}":
                result.append(char)
        else:
            result.append(char)
    assert not quoted
    return json.loads("".join(result))


def tables(doc, root):
    return {table["name"]: table for table in doc[root]["tables"]}


def rows(table):
    assert len(table["instances"]) == 1
    return table["instances"][0]["rows"]


def source_and_provenance(contract):
    old = CASES / "B03-var01-cold-first-full-report-v0.1.0"
    for pin in contract["excluded_v010"]["files"]:
        seal(REPO / pin["original_path"], pin)
        seal(HERE / pin["inert_copy_path"], pin)
    assert len(contract["accepted_source_files"]) == 38
    for pin in contract["accepted_source_files"]:
        seal(REPO / pin["path"], pin["local_disk"])
        blob = subprocess.run(["git", "show", contract["base_commit"] + ":" + pin["path"]],
                              cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=True).stdout
        assert len(blob) == pin["published_git_at_base"]["bytes"]
        assert sha(blob) == pin["published_git_at_base"]["sha256"]
    for pin in contract["installed"].values():
        seal(Path(pin["path"]), pin)
    catalog = contract["published_parent_scope"]
    historical = seal(HERE / "review" / "preserved-root-catalog-at-contract.json",
                      catalog["catalog_snapshot_at_base"]["local_disk"])
    base_blob = subprocess.run(["git", "show", contract["base_commit"] + ":" + catalog["catalog_path"]],
                               cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               check=True).stdout
    assert len(base_blob) == catalog["catalog_snapshot_at_base"]["published_git_at_base"]["bytes"]
    assert sha(base_blob) == catalog["catalog_snapshot_at_base"]["published_git_at_base"]["sha256"]
    baseline = json.loads(historical)
    assert baseline == json.loads(base_blob)
    current = json.loads((REPO / catalog["catalog_path"]).read_bytes())
    assert {k: v for k, v in current.items() if k != "entries"} == {k: v for k, v in baseline.items() if k != "entries"}
    assert current["entries"][:len(baseline["entries"])] == baseline["entries"]
    parent = json.loads((CASES / "B02-serial-preparation-v1.0.2" / "native-input.json").read_bytes())
    child = json.loads((CASES / "B03-explicit-cold-hot-v1.0.2" / "native-input.json").read_bytes())
    before, after = tables(parent, "model"), tables(child, "model")
    assert list(before) == list(after) and len(after) == 31
    changed = {name for name in after if before[name] != after[name]}
    assert changed == set(contract["source_and_roundtrip_gates"]["B02_to_B03_changed_tables_exact"])
    assert len(after) - len(changed) == 25
    assert sha((CASES / "B02-serial-preparation-v1.0.2" / "native-input.json").read_bytes()) == contract["prerequisites"]["parent_input_sha256"]
    assert sha((CASES / "B03-explicit-cold-hot-v1.0.2" / "native-input.json").read_bytes()) == contract["prerequisites"]["accepted_B03_input_sha256"]
    assert sha((CASES / "B03-explicit-cold-hot-v1.0.2" / "parent-diff.json").read_bytes()) == contract["prerequisites"]["B02_to_B03_exact_diff_sha256"]
    return after


def run_evidence(contract):
    outputs = []
    for run in contract["parent_runs"]:
        directory = Path(run["original_directory"])
        invocation_raw = seal(directory / "invocation.json", run["invocation"])
        closure_raw = seal(directory / "closure.json", run["closure"])
        invocation = json.loads(invocation_raw.decode("utf-8-sig"))
        closure = json.loads(closure_raw.decode("utf-8-sig"))
        assert invocation["run_id"] == closure["run_id"] == run["run_id"]
        assert invocation["input_sha256"] == closure["input_sha256"] == run["input"]["sha256"]
        assert invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True
        assert invocation["ssh_client_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"]
        assert invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
        assert closure["invocation_sha256"] == run["invocation"]["sha256"]
        assert closure["raw"] == run["raw"]
        assert len(run["raw"]) == 11
        for name, pin in run["raw"].items():
            seal(directory / name, pin)
        for name, pin in run["other_local_files"].items():
            seal(directory / name, pin)
        steps = json.loads((directory / "steps.json").read_text(encoding="utf-8-sig"))
        assert [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport"]
        assert all(type(s["exit_code"]) is int and s["exit_code"] == 0 and
                   s["coexisting_gui_present_after"] is True for s in steps)
        outputs.append(directory)
    assert (outputs[0] / "model.log").read_bytes() == (outputs[1] / "model.log").read_bytes()
    assert (outputs[0] / "report-raw.json").read_bytes() == (outputs[1] / "report-raw.json").read_bytes()
    assert json.loads((outputs[0] / "validation.json").read_text(encoding="utf-8-sig"))["passed"] is False
    assert json.loads((outputs[1] / "validation.json").read_text(encoding="utf-8-sig"))["passed"] is True
    return outputs[1]


def roundtrip(source, directory):
    exported = tables(native_json_bytes((directory / "roundtrip-raw.json").read_bytes()), "model")
    assert list(exported) == list(source)
    populated = 0
    for name, table in source.items():
        candidate = exported[name]
        assert candidate["columns"] == table["columns"]
        src = rows(table)
        dst = rows(candidate)
        if src:
            assert dst == src, name
            populated += int(any(any(value not in (None, "") for value in row) for row in src))
        else:
            assert dst == [[None] * len(table["columns"])], name
    assert populated == 14
    conversion = (directory / "run.log").read_text(encoding="utf-8-sig")
    assert "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in conversion
    assert re.findall(r"\(warning #(\d+)\)", conversion) == ["108", "126"]
    return populated


def timestamp(line):
    match = re.match(r"Time:\s*([0-9]+(?:\.[0-9]+)?)\s+(.*)", line)
    assert match, line
    token = match.group(1)
    uncertainty = 0.5 * 10 ** (-len(token.partition(".")[2])) if "." in token else 0
    return float(token), uncertainty, match.group(2)


def expected_plan(source):
    mt = {r[0]: r for r in rows(source["MissionType"])}
    mtcols = [x["name"] for x in source["MissionType"]["columns"]]
    profiles = rows(source["OperationProfile"])
    pcols = [x["name"] for x in source["OperationProfile"]["columns"]]
    prep = {r[0]: r[4] for r in rows(source["MissionPreparation"])}
    tasks = {}
    for task, seq, kind, duration, *_ in rows(source["TaskBreakDown"]):
        tasks.setdefault(task, []).append((seq, kind, duration))
    assert tasks == {"PREP-FIXED": [(1, "INSPECT", 1/6), (2, "SERVICE", 1/3)],
                     "HOT-PREP": [(1, "HOT-SERVICE", 1/6)]}
    plan = []
    for ordinal, p in enumerate(profiles):
        mission = p[pcols.index("SPRID")]
        launch = p[pcols.index("STIM")]
        notice = launch - 1
        duration = mt[mission][mtcols.index("DURN")]
        assert p[pcols.index("ITYPE")] == "SCHEDULED" and p[pcols.index("IQTY")] == 1
        assert mt[mission][mtcols.index("NOS")] == 1 and mt[mission][mtcols.index("MNOS")] == 1
        assert duration == 2
        step_list = sorted(tasks[prep[mission]])
        completion = notice + sum(step[2] for step in step_list)
        assert (mission, launch, completion) == [("COLD-FIRST", 8, 7.5),
                                                  ("HOT-SORTIE", 12, 11 + 1/6),
                                                  ("HOT-SORTIE", 16, 15 + 1/6)][ordinal]
        plan.append({"mission": mission, "ordinal": ordinal, "id": f"<{mission},TEACH-UNIT,0,0,{ordinal}>",
                     "notice": notice, "prep_end": completion, "launch": launch,
                     "return": launch + duration, "steps": step_list, "task": ordinal})
    return plan


def physical(log_bytes, plan):
    lines = log_bytes.decode("utf-8-sig").splitlines()
    timed = [(number, *timestamp(line)) for number, line in enumerate(lines, 1) if line.startswith("Time:")]
    aircraft = "<TEACH-AIR-01,0>"
    assert set(re.findall(r"<TEACH-AIR-[^>]+>", "\n".join(lines))) == {aircraft}
    assert sum("mission ordered:" in text for _, _, _, text in timed) == 3
    assert sum("mission starting, duration:" in text for _, _, _, text in timed) == 3
    assert sum("mission success:" in text for _, _, _, text in timed) == 3
    assert sum("preparation started, mission:" in text for _, _, _, text in timed) == 3
    assert sum("preparation ended, mission:" in text for _, _, _, text in timed) == 3
    assert sum(re.search(r"subtask \d+ seqno \d+ .* starts performing", text) is not None
               for _, _, _, text in timed) == 4
    assert not any(re.search(r"\b(cancelled|canceled|aborted|waiting for|books? resource|resource booked|item demand)\b", text, re.I)
                   for _, _, _, text in timed)
    assert all(aircraft in text for _, _, _, text in timed if "allocates system:" in text)
    cursor = 0

    def edge(fragment, expected_time, exact=False):
        nonlocal cursor
        matches = [i for i in range(cursor, len(timed)) if fragment in timed[i][3]]
        assert matches, fragment
        i = matches[0]
        number, value, uncertainty, text = timed[i]
        if exact:
            assert value == expected_time, (fragment, number, value, expected_time)
        else:
            assert abs(value - expected_time) <= uncertainty + 1e-9, (fragment, number, value, expected_time)
        cursor = i + 1
        return number, value, uncertainty

    for task in plan:
        mid = task["id"]
        edge(f"mission ordered: {task['mission']}", task["notice"], True)
        edge(f"{mid} mission created:", task["notice"], True)
        edge(f"{mid} mission activated, systems requested: 1", task["notice"], True)
        edge(f"{mid} mission allocates system: {aircraft}", task["notice"], True)
        edge(f"{aircraft} preparation started, mission: {mid}", task["notice"], True)
        edge(f"system preparation task {task['task']} on {aircraft} started", task["notice"], True)
        sub_start = task["notice"]
        for step_index, (seq, kind, duration) in enumerate(task["steps"]):
            sid = (0 if task["ordinal"] == 0 else task["ordinal"] + 1) + step_index
            label = f"subtask {sid} seqno {seq} within system preparation task {task['task']} on {aircraft}"
            edge(label + " started", sub_start)
            edge(label + " requests resources: no resources needed", sub_start)
            edge(label + " resource availability test", sub_start)
            edge(label + " starts performing", sub_start)
            sub_start += duration
            edge(label + " completed", sub_start)
        edge(f"system preparation task {task['task']} on {aircraft} completed", task["prep_end"])
        edge(f"{aircraft} preparation ended, mission: {mid}", task["prep_end"])
        edge(f"{mid} mission starting, duration: 2 : {aircraft}", task["launch"], True)
        edge(f"{mid} task starting: {aircraft}", task["launch"] + 0.5, True)
        edge(f"{mid} task completed: {aircraft}", task["return"] - 0.5, True)
        edge(f"{mid} mission success:", task["return"], True)
        edge(f"{mid} mission completed: {aircraft}", task["return"], True)
        edge(f"{aircraft} turnround started, mission: {mid}", task["return"], True)
        edge(f"{aircraft} turnround ended, mission: {mid}", task["return"], True)
        edge(f"{aircraft} nbr ready increased at unit:", task["return"], True)
    assert all(value <= 36 for _, value, _, _ in timed)
    assert any(value == 18 and "System ready" in text for _, value, _, text in timed)
    return len(timed)


def overlap(a, b, c, d):
    return max(0.0, min(b, d) - max(a, c))


def expected_report(source, plan, gate):
    columns = gate["column_order_exact"]
    result = {}
    result["ProblemDescription"] = rows(source["ProblemDescription"])
    summary = gate["summary_expected"]
    result["ResultSummary"] = [[summary[name] for name in columns["ResultSummary"]]]
    system = []
    stock = []
    for i in range(72):
        a, b = i / 2, (i + 1) / 2
        prep_fraction = sum(overlap(a, b, p["notice"], p["prep_end"]) for p in plan) / 0.5
        prepared_fraction = sum(overlap(a, b, p["prep_end"], p["launch"]) for p in plan) / 0.5
        flight_fraction = sum(overlap(a, b, p["launch"], p["return"]) for p in plan) / 0.5
        assigned = sum(overlap(a, b, p["notice"], p["return"]) for p in plan) / 0.5
        ready = 1 - assigned
        starts = sum(a <= p["notice"] < b for p in plan)
        finishes = sum(a <= p["prep_end"] < b for p in plan)
        fields = {name: 0 for name in columns["SystemResults"]}
        fields.update(UNID="Total over all Units", SID="Total over all Systems", STINT=a, ETINT=b,
                      NSYRY=ready, NSYMA=assigned, NSYMO=flight_fraction,
                      NSYMP=prep_fraction, NSYMR=prepared_fraction, NSYA=1,
                      FTMO=flight_fraction, STACC=flight_fraction,
                      SYDT=None, NPSTA=starts, NPSUC=finishes)
        system.append([fields[name] for name in columns["SystemResults"]])
        item = {name: 0 for name in columns["StockTotalResults"]}
        item.update(STINT=a, ETINT=b, PNB=1)
        for name in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
            item[name] = None
        stock.append([item[name] for name in columns["StockTotalResults"]])
    result["SystemResults"] = system
    result["StockTotalResults"] = stock
    return result


def compare_report(report, expected, gate):
    tables_here = report["report"]["tables"]
    declared = gate["native_tables_in_order"]
    assert [t["name"] for t in tables_here] == [d["name"] for d in declared]
    cells = 0
    for table, shape in zip(tables_here, declared):
        name = table["name"]
        names = gate["column_order_exact"][name]
        assert [c["name"] for c in table["columns"]] == names
        assert len(table["instances"]) == 1
        instance = table["instances"][0]
        assert instance["instance_name"] == gate["instance_names_exact"][name]
        assert len(instance["rows"]) == shape["rows"] and len(names) == shape["columns"]
        for n, column in zip(names, table["columns"]):
            want_type = "string" if (name == "ProblemDescription" or n in ("UNID", "SID")) else (
                "integer" if n == "NREP" else "double")
            assert column["datatype"] == want_type
            assert column.get("key", False) is (name in ("SystemResults", "StockTotalResults") and
                                                n in ("UNID", "SID", "STINT", "ETINT"))
        for i, (observed, want) in enumerate(zip(instance["rows"], expected[name])):
            assert len(observed) == len(want) == len(names)
            for field, actual, calculated in zip(names, observed, want):
                assert type(actual) is not bool
                if calculated is None or isinstance(calculated, str):
                    assert actual == calculated and type(actual) is type(calculated), (name, i, field)
                elif field in ("STINT", "ETINT") or calculated == 0 or calculated == 1 or float(calculated).is_integer():
                    assert actual == calculated, (name, i, field, actual, calculated)
                else:
                    assert name == "SystemResults" and field in ("NSYMP", "NSYMR"), (name, i, field, actual, calculated)
                    # Hot preparation completion is printed at 11.1667/15.1667;
                    # half a last decimal unit per contributing endpoint / 0.5h.
                    bound = 0.0001005
                    assert abs(actual - calculated) <= bound, (name, i, field, actual, calculated)
                cells += 1
    assert cells == gate["total_cells"] == 4044
    return cells


def self_check(expected, gate, original):
    # Mutate parsed report after the original byte seals and physical replay.
    probes = [
        ("whole_bin", "SystemResults", 0, "NSYRY", 0),
        ("zero_residue", "SystemResults", 0, "NSYMP", 1e-9),
        ("fraction_bound", "SystemResults", 22, "NSYMP", 0.334),
        ("preparation_count", "SystemResults", 14, "NPSTA", 2),
        ("stock_null", "StockTotalResults", 0, "ROS", 0),
        ("stock_baseline", "StockTotalResults", 0, "PNB", 0),
        ("summary_ratio", "ResultSummary", 0, "MTMF", 0.5),
    ]
    rejected = 0
    for _, name, row, field, replacement in probes:
        test = json.loads(json.dumps(original))
        table = next(t for t in test["report"]["tables"] if t["name"] == name)
        index = [x["name"] for x in table["columns"]].index(field)
        table["instances"][0]["rows"][row][index] = replacement
        try:
            compare_report(test, expected, gate)
        except AssertionError:
            rejected += 1
    assert rejected == len(probes)
    return rejected


def physical_self_check(plan, original):
    # Each mutation is in memory after the unmodified log has passed its SHA seal.
    text = original.decode("utf-8-sig")
    changes = [
        ("mission ordered: COLD-FIRST", "mission ordered: HOT-SORTIE"),
        ("requests resources: no resources needed", "requests resources: P-CREW"),
        ("mission allocates system: <TEACH-AIR-01,0>", "mission allocates system: <TEACH-AIR-02,0>"),
        ("subtask 0 seqno 1", "subtask 0 seqno 2"),
        ("Time: 7.16667  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed",
         "Time: 7.2  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed"),
    ]
    rejected = 0
    for before, after in changes:
        assert before in text
        changed = text.replace(before, after, 1).encode("utf-8")
        try:
            physical(changed, plan)
        except AssertionError:
            rejected += 1
    assert rejected == len(changes)
    return rejected


def main():
    raw = seal(HERE / "contract.json", {"bytes": 38324, "sha256": CONTRACT_SHA})
    contract = json.loads(raw)
    source = source_and_provenance(contract)
    accepted = run_evidence(contract)
    populated = roundtrip(source, accepted)
    plan = expected_plan(source)
    log_bytes = (accepted / "model.log").read_bytes()
    log_events = physical(log_bytes, plan)
    gate = contract["full_report_gate"]
    expected = expected_report(source, plan, gate)
    report = native_json_bytes((accepted / "report-raw.json").read_bytes())
    cells = compare_report(report, expected, gate)
    probes = self_check(expected, gate, report) + physical_self_check(plan, log_bytes)
    verdict = {"schema": "b03-var01-independent-readonly-replay/v1",
               "decision": "GO_BOUNDED", "contract_sha256": CONTRACT_SHA,
               "accepted_run_id": contract["parent_runs"][1]["run_id"],
               "new_native_runs": 0, "source_local_git_pairs": 38,
               "parent_runs_sealed": 2, "raw_files_sealed": 22,
               "populated_roundtrip_tables": populated, "physical_timed_lines": log_events,
               "full_expected_report_cells": cells, "semantic_mutation_rejections": probes,
               "limits": ["Retrospective explicit-MTID cold-first classification; hot sorties remain required context.",
                          "Historical invocation records SSH session zero and integer step exits, not native child PID/session.",
                          "No same-MTID thermal/history switching, cold-only causal effect or new native behavior claim."]}
    print(json.dumps(verdict, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

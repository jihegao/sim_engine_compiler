"""Independent standard-library read-only replay of E10.var06 mixed-IID batching."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
OUT = Path(__file__).with_name("independent-verdict.json")
RUN_IDS = {arm: f"e10-var06-mixed-{arm}-v103-ssh-20261003-01" for arm in ("minbs1", "minbs2")}
checks = []


def check(name, good):
    checks.append({"name": name, "passed": bool(good)})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path, native=False):
    content = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",(?=\s*[}\]])", "", content) if native else content)


def tables(document, root="model"):
    return {table["name"]: table for table in document[root]["tables"]}


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def field(table, row, name):
    return row[[col["name"] for col in table["columns"]].index(name)]


def at(log, time, phrase):
    return any(line.startswith(f"Time: {time} ") and phrase in line for line in log.splitlines())


def near(actual, expected, tol=0.001):
    return math.isclose(float(actual), float(expected), abs_tol=tol, rel_tol=0)


def average(start, end, segments):
    return sum(max(0.0, min(end, stop) - max(start, begin)) * qty for begin, stop, qty in segments) / (end - start)


def changed(parent, child):
    return {name for name in parent.keys() | child.keys() if parent.get(name) != child.get(name)}


def changed_fields(left, right):
    return {column["name"] for lr, rr in zip(rows(left), rows(right))
            for i, column in enumerate(left["columns"]) if lr[i] != rr[i]}


def main():
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    parent_pkg = ROOT / contract["accepted_parent"]["package"]
    parent_inputs = {arm: parent_pkg / f"native-input-{arm}.json" for arm in RUN_IDS}
    parent_closures = {arm: parent_pkg / "runs" / contract["accepted_parent"]["run_ids"][arm] / "closure.json"
                       for arm in RUN_IDS}
    parent_index = parent_pkg / "evidence-index.json"
    child_inputs = {arm: CASE / f"native-input-{arm}.json" for arm in RUN_IDS}
    for arm in RUN_IDS:
        check(f"accepted {arm} parent input SHA", sha(parent_inputs[arm]) ==
              contract["accepted_parent"]["input_sha256"][arm] == diff["parent_inputs_sha256"][arm])
        check(f"accepted {arm} parent closure SHA", sha(parent_closures[arm]) ==
              contract["accepted_parent"]["native_closure_sha256"][arm])
        check(f"frozen {arm} child input SHA", sha(child_inputs[arm]) ==
              contract["native_inputs_sha256"][arm] == diff[f"arm{1 if arm == 'minbs1' else 2}_sha256"])
    check("accepted parent evidence-index SHA", sha(parent_index) == contract["accepted_parent"]["evidence_index_sha256"])
    check("exact diff SHA", sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
    diagnostics = {}
    for key, version in (("prior_diagnostic_no_go", "1.0.0"),
                         ("second_diagnostic_no_go", "1.0.1"),
                         ("third_diagnostic_no_go", "1.0.2")):
        pkg = ROOT / contract[key]["package"]
        diagnostics[key] = {}
        for arm in RUN_IDS:
            source = pkg / f"native-input-{arm}.json"
            run_dirs = sorted((pkg / "runs").glob(f"*{arm}*"))
            closure = run_dirs[0] / "closure.json" if len(run_dirs) == 1 else None
            check(f"excluded {version} {arm} source SHA", sha(source) == contract[key]["input_sha256"][arm])
            check(f"excluded {version} {arm} closure SHA", closure is not None and
                  sha(closure) == contract[key]["native_closure_sha256"][arm])
            diagnostics[key][arm] = closure
    check("v1.0.3 discloses exact v1.0.1 source reuse", all(sha(child_inputs[arm]) ==
          contract["second_diagnostic_no_go"]["input_sha256"][arm] for arm in RUN_IDS))
    parent = {arm: tables(read(path)) for arm, path in parent_inputs.items()}
    child = {arm: tables(read(path)) for arm, path in child_inputs.items()}
    for arm in RUN_IDS:
        old, new = parent[arm], child[arm]
        delta = changed(old, new)
        check(f"{arm} exact parent table delta", delta == set(diff["changed_tables_each_parent_to_child"]) and
              diff["unchanged_tables_parent_to_child"] == len(old) - len(delta))
        for name in sorted(old.keys() - delta):
            check(f"{arm} unchanged parent table {name}", old[name] == new[name])
        check(f"{arm} RSEED-only Control edit", changed_fields(old["Control"], new["Control"]) == {"RSEED"} and
              field(new["Control"], rows(new["Control"])[0], "RSEED") == "2")
        check(f"{arm} System FRT6M only", changed_fields(old["System"], new["System"]) == {"FRT"} and
              field(new["System"], rows(new["System"])[0], "FRT") == 6000000)
        check(f"{arm} cloned second LRU type and repair/structure", all(
              len(rows(new[name])) == 2 * len(rows(old[name])) for name in ("Item", "ItemRepair", "ItemStructure", "StockAllocation")))
        for name in ("Item", "ItemRepair", "ItemStructure", "StockAllocation"):
            old_rows = rows(old[name])
            new_rows = rows(new[name])
            check(f"{arm} original {name} rows retained", new_rows[:len(old_rows)] == old_rows)
            expected_clones = [[value.replace("TEACH-LRU-01", "TEACH-LRU-02") if isinstance(value, str)
                                else value for value in row] for row in old_rows]
            if name == "Item":
                expected_clones[0][1] = "Second replaceable teaching component"
            check(f"{arm} exact {name} second-IID clone", new_rows[len(old_rows):] == expected_clones)
        check(f"{arm} both IID source rows and depot stock2 per type", {field(new["Item"], r, "IID") for r in rows(new["Item"])} ==
              {"TEACH-LRU-01", "TEACH-LRU-02"} and
              sorted((field(new["StockAllocation"], r, "IID"), field(new["StockAllocation"], r, "STID"),
                      field(new["StockAllocation"], r, "STSIZ")) for r in rows(new["StockAllocation"])) ==
              [("TEACH-LRU-01", "BASE-01", 0), ("TEACH-LRU-01", "DEPOT-01", 2),
               ("TEACH-LRU-02", "BASE-01", 0), ("TEACH-LRU-02", "DEPOT-01", 2)])
    a, b = child["minbs1"], child["minbs2"]
    check("arm pair differs only description/MINBS profile", changed(a, b) ==
          set(diff["changed_tables_between_child_arms"]) and
          diff["unchanged_tables_between_child_arms"] == len(a) - 2)
    for name in sorted(a.keys() - changed(a, b)):
        check(f"child arm common table {name}", a[name] == b[name])
    check("policy rows MINBS1 and MINBS2 exact", rows(a["TransportPolicyProfile"]) ==
          [diff["arm1_policy_row"]] and rows(b["TransportPolicyProfile"]) == [diff["arm2_policy_row"]] and
          changed_fields(a["TransportPolicyProfile"], b["TransportPolicyProfile"]) == {"MINBS"})
    check("no resource rows or item-specific transport", all(name not in a or not rows(a[name]) for name in
          ("Resource", "ResourceAllocation", "TaskResource", "ItemStationStructure")))

    reports, logs, run_hashes = {}, {}, {}
    for arm in RUN_IDS:
        run = CASE / "runs" / RUN_IDS[arm]
        invocation = read(run / "invocation.json")
        closure = read(run / "closure.json")
        check(f"{arm} invocation/closure identity and SHA", invocation["run_id"] == closure["run_id"] == RUN_IDS[arm] and
              closure["invocation_sha256"] == sha(run / "invocation.json"))
        check(f"{arm} native input SHA bind", invocation["input_sha256"] == sha(run / "input.json") == sha(child_inputs[arm]))
        pins = closure["source_hashes_before"]
        check(f"{arm} source stable before/after", pins == closure["source_hashes_after"] ==
              invocation["source_hashes_before"])
        paths = {
            "input": child_inputs[arm], "parent_minbs1": parent_inputs["minbs1"],
            "parent_minbs2": parent_inputs["minbs2"],
            "parent_closure_minbs1": parent_closures["minbs1"],
            "parent_closure_minbs2": parent_closures["minbs2"],
            "parent_index": parent_index, "contract": CASE / "contract.json",
            "exact_diff": CASE / "exact-diff.json", "builder": CASE / "build.py",
            "diff_builder": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
            "runner_script": CASE / "run_native_ssh.ps1",
        }
        for diagnostic in diagnostics:
            for prior_arm in RUN_IDS:
                paths[f"{diagnostic.removesuffix('_no_go')}_closure_{prior_arm}"] = diagnostics[diagnostic][prior_arm]
        for name, path in sorted(paths.items()):
            check(f"{arm} sealed source {name}", name in pins and pins[name] == sha(path))
        check(f"{arm} installed exe/manual/dictionary pins", all(
              pins[name] == contract["source"][key] for name, key in
              (("simlox_exe", "simlox_exe_sha256"), ("manual", "manual_pdf_sha256"),
               ("dictionary", "dictionary_sha256"))))
        check(f"{arm} SSH0/queue and GUI identity", invocation["execution_mode"] == "ssh_cli_v1" and
              invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
              "sshd.exe" in invocation["ssh_ancestor_names"] and
              invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
              invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        steps = read(run / "steps.json")
        check(f"{arm} five guarded steps", [s["name"] for s in steps] ==
              ["import", "export", "calc", "jsonreport", "check_import_export"] and
              all(s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
        check(f"{arm} twelve raw files", len(closure["raw"]) == 12)
        for name, seal in sorted(closure["raw"].items()):
            path = run / name
            check(f"{arm} raw seal {name}", path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        exported = tables(read(run / "roundtrip-raw.json", native=True))
        count = 0
        for name, authored in sorted(child[arm].items()):
            if not rows(authored):
                continue
            count += 1
            target = exported.get(name)
            same = target is not None
            if same:
                width = len(authored["columns"])
                same = ([c["name"] for c in authored["columns"]] ==
                        [c["name"] for c in target["columns"][:width]] and
                        [i["rows"] for i in authored["instances"]] ==
                        [[r[:width] for r in i["rows"]] for i in target["instances"]])
            check(f"{arm} exact native table {name}", same)
        check(f"{arm} 22 authored row-containing tables", count == 22)
        converter = (run / "run.log").read_text(encoding="utf-8-sig")
        check(f"{arm} converter errors0/warning108", bool(re.search(
              r"Errors:\s*0, Warnings:\s*1, Notes:\s*0", converter)) and
              re.findall(r"warning #(\d+)", converter) == ["108"])
        check(f"{arm} valid native outputs", all((run / name).stat().st_size > 1000 for name in
              ("model.sxo", "model.log", "report-raw.json")))
        logs[arm] = (run / "model.log").read_text(encoding="utf-8-sig")
        reports[arm] = tables(read(run / "report-raw.json", native=True), "report")
        run_hashes[arm] = {"closure": sha(run / "closure.json"), "model_log": sha(run / "model.log"),
                           "report": sha(run / "report-raw.json")}

    demands = [("8.0822", "TEACH-LRU-01", 0, 4), ("8.0822", "TEACH-LRU-02", 2, 5),
               ("8.66291", "TEACH-LRU-02", 3, 6), ("8.66291", "TEACH-LRU-01", 1, 7)]
    repairs = [("10.2489", "11.2489", "TEACH-LRU-01", 4),
               ("10.2489", "11.2489", "TEACH-LRU-02", 5),
               ("10.8296", "11.8296", "TEACH-LRU-02", 6),
               ("10.8296", "11.8296", "TEACH-LRU-01", 7)]
    for arm, log in logs.items():
        check(f"{arm} four local and four depot demands", sum("Item demand arrives" in line for line in log.splitlines()) == 8 and
              sum("Item demand arrives from pos <TEACH-AIR-01" in line for line in log.splitlines()) == 4)
        check(f"{arm} four source-identified on-mission failures", all(at(log, time,
              f"<TEACH-AIR-01,{aircraft}> critical random failure added") for time, aircraft in
              (("8.0411", 1), ("8.07256", 1), ("8.33146", 0), ("8.43916", 0))) and
              all(f"subitem failed: <{iid},0,{physical}>" in log for _, iid, _, physical in demands))
        for time, iid, spare, failed in demands:
            check(f"{arm} {time} local {iid} failed physical {failed}", at(log, time,
                  f"<{iid},0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01") and
                  at(log, time, f"item requiring maintenance is <{iid},0,{failed}>"))
            check(f"{arm} {time} depot {iid} demand/spare {spare}", at(log, time,
                  f"<{iid},0,DEPOT-01,0> Item demand arrives") and
                  at(log, time, f"Take replacement item <{iid},0,{spare}> from stock"))
            check(f"{arm} {time} {iid} local backorder", at(log, time, f"<{iid},0,BASE-01,0> Backorder added"))
        check(f"{arm} no other depot demand times or item types", sorted((line.split()[1],
              re.search(r"<(TEACH-LRU-\d+),0,DEPOT-01,0>", line).group(1))
              for line in log.splitlines() if "Item demand arrives" in line and "DEPOT-01" in line) ==
              sorted((t, iid) for t, iid, _, _ in demands))
        for start, finish, iid, physical in repairs:
            check(f"{arm} {iid} physical {physical} repair {start}-{finish}",
                  at(log, start, f"Start repair of item <{iid},0,{physical}>") and
                  at(log, finish, f"Finished repair of item <{iid},0,{physical}>") and
                  at(log, finish, f"Put back replacement item <{iid},0,{physical}> to stock"))
        check(f"{arm} two starts and two aborts, no success", all(at(log, "8",
              f"BASIC-MISSION,TEACH-UNIT,0,0,{n}> mission starting") for n in (0, 1)) and
              at(log, "8.0411", "BASIC-MISSION,TEACH-UNIT,0,0,1> mission aborted") and
              at(log, "8.33146", "BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted") and
              "mission success:" not in log)
        check(f"{arm} terminal ready two; repaired items depot stock", "systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log and
              all(f"Put back replacement item <{iid},0,{physical}> to stock" in log for _, _, iid, physical in repairs))
        check(f"{arm} depot terminal IID01 physical stock IDs4/7", "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-LRU-01,0,4>,<TEACH-LRU-01,0,7>," in log)
        check(f"{arm} depot terminal IID02 physical stock IDs5/6", "Stock at: <TEACH-LRU-02,0,DEPOT-01,0> Level: 2 Items:<TEACH-LRU-02,0,5>,<TEACH-LRU-02,0,6>," in log)
        check(f"{arm} no resource booking", "books resources" not in log)
        check(f"{arm} all physical transport tasks arrive", sum(" starts with " in line and "items/systems" in line for line in log.splitlines()) ==
              sum(" arrives with " in line and "items/systems" in line for line in log.splitlines()))

    one, two = logs["minbs1"], logs["minbs2"]
    starts_one = re.findall(r"Time: ([\d.]+)  transport task (\d+) starts with (\d+) items/systems", one)
    starts_two = re.findall(r"Time: ([\d.]+)  transport task (\d+) starts with (\d+) items/systems", two)
    check("MINBS1 four one-item downward tasks", all((t, task, "1") in starts_one for t, task in
          (("8.0822", "1"), ("8.0822", "2"), ("8.66291", "6"), ("8.66291", "7"))) and
          not any(q == "2" for _, _, q in starts_one))
    check("MINBS2 two mixed two-item downward tasks", all((t, task, "2") in starts_two for t, task in
          (("8.0822", "2"), ("8.66291", "7"))) and
          sum(q == "2" for _, _, q in starts_two) == 2)
    check("MINBS2 provisional single-item tasks cancelled", at(two, "8.0822", "transport task 1 cancelled with 1 items/systems") and
          at(two, "8.66291", "transport task 6 cancelled with 1 items/systems") and
          not any(t == "8.0822" and task == "1" for t, task, _ in starts_two) and
          not any(t == "8.66291" and task == "6" for t, task, _ in starts_two))
    for time, task, pair in (("8.0822", "2", (("TEACH-LRU-01", 0), ("TEACH-LRU-02", 2))),
                             ("8.66291", "7", (("TEACH-LRU-01", 1), ("TEACH-LRU-02", 3)))):
        check(f"MINBS2 {time} same-task mixed physical request IDs", all(at(two, time,
              f"transport request <<{iid},0,{physical}>,<{iid},0,DEPOT-01,0>,<{iid},0,BASE-01,0>> attached to  transport task {task}") and
              at(two, time, f"transport request <<{iid},0,{physical}>,<{iid},0,DEPOT-01,0>,<{iid},0,BASE-01,0>> started")
              for iid, physical in pair))
        arrival = "10.0822" if time == "8.0822" else "10.6629"
        check(f"MINBS2 {arrival} two-item arrival", at(two, arrival,
              f"transport task {task} arrives with 2 items/systems"))
    check("MINBS1 four separate downward arrivals", all(at(one, t,
          f"transport task {task} arrives with 1 items/systems") for t, task in
          (("10.0822", "1"), ("10.0822", "2"), ("10.6629", "6"), ("10.6629", "7"))))
    check("four two-hour local backorder clearances each arm", all(sum(
          line.startswith(f"Time: {t} ") and "Backorder removed, waiting time was 2" in line
          for line in log.splitlines()) == 2 for log in (one, two) for t in ("10.0822", "10.6629")))

    for arm in RUN_IDS:
        report = reports[arm]
        system, stock, summary = (report[name] for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
        sy, st = rows(system), rows(stock)
        check(f"{arm} only four selected report tables", set(report) ==
              {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        check(f"{arm} 72 System/Stock bins", len(sy) == len(st) == 72)
        backorders = [(8.0822, 10.0822, 2), (8.66291, 10.66291, 2)]
        ready = [(0, 7, 2), (10.4155, 36, 1), (10.9962, 36, 1)]
        operating = [(8, 8.0822, 1), (8, 8.66291, 1)]
        for index, (sr, tr) in enumerate(zip(sy, st)):
            start, end = index / 2, (index + 1) / 2
            check(f"{arm} System interval {index}", near(field(system, sr, "STINT"), start, 1e-6) and
                  near(field(system, sr, "ETINT"), end, 1e-6))
            check(f"{arm} Stock interval {index}", near(field(stock, tr, "STINT"), start, 1e-6) and
                  near(field(stock, tr, "ETINT"), end, 1e-6))
            check(f"{arm} event-derived NBO {index}", near(field(stock, tr, "NBO") or 0,
                  average(start, end, backorders), 0.001))
            check(f"{arm} event-derived NSYRY {index}", near(field(system, sr, "NSYRY") or 0,
                  average(start, end, ready), 0.001))
            check(f"{arm} event-derived NSYMO {index}", near(field(system, sr, "NSYMO") or 0,
                  average(start, end, operating), 0.001))
            check(f"{arm} event-derived NDF {index}", (field(stock, tr, "NDF") or 0) ==
                  (2 if start in (8, 8.5) else 0))
            check(f"{arm} first-bin four faults {index}", (field(system, sr, "NFAIL") or 0) ==
                  (4 if start == 8 else 0))
            check(f"{arm} repair completion bins {index}", (field(system, sr, "NREPT") or 0) ==
                  (2 if start in (10, 10.5) else 0))
            check(f"{arm} exact whole System bin pair equality {index}", sr == rows(reports["minbs1"]["SystemResults"])[index])
            check(f"{arm} exact whole Stock bin pair equality {index}", tr == rows(reports["minbs1"]["StockTotalResults"])[index])
        check(f"{arm} WT two per demand time bin", near(sum((field(stock, r, "WT") or 0) for r in st), 4) and
              sum("Backorder removed, waiting time was 2" in line for line in logs[arm].splitlines()) == 4)
        result = rows(summary)[0]
        check(f"{arm} one 36h repetition; no mission success", field(summary, result, "NREP") == 1 and
              field(summary, result, "RTIUP") == 36 and field(summary, result, "MSUF") == 0)
        check(f"{arm} terminal ready2/no aggregate backorder", near(field(system, sy[-1], "NSYRY"), 2) and
              (field(stock, st[-1], "NBO") or 0) == 0)
    check("entire selected aggregate business reports equal across arms", all(
          reports["minbs1"][name] == reports["minbs2"][name] for name in
          ("ResultSummary", "SystemResults", "StockTotalResults")))
    failed = [entry["name"] for entry in checks if not entry["passed"]]
    result = {
        "schema": "simlox-e10-var06-mixed-independent-readonly/v1", "passed": not failed,
        "verdict": "GO_bounded_two_mixed_IID_batches" if not failed else "NO_GO",
        "checks_passed": len(checks) - len(failed), "checks_total": len(checks),
        "failures": failed, "checks": checks,
        "hashes": {"contract": sha(CASE / "contract.json"), "exact_diff": sha(CASE / "exact-diff.json"),
                   "parent_inputs": {arm: sha(path) for arm, path in parent_inputs.items()},
                   "inputs": {arm: sha(path) for arm, path in child_inputs.items()}, "runs": run_hashes},
        "scope": "At fixed seed2, both arms have two same-time mixed-IID demand pairs, h8.0822 and h8.66291, four total depot demands and four distinct physical spares. MINBS1 starts four one-item downward tasks. MINBS2 cancels each provisional one-item task and starts two mixed-IID two-item tasks, one per demand time. Both item types arrive after two hours, four local backorders clear, four failed items return upward for repair, and both aircraft are ready at horizon. Aggregate business report tables are identical across arms and do not reveal transport grouping.",
        "limits": ["The three earlier frozen diagnostic versions remain excluded. v1.0.3 reuses v1.0.1 source bytes under a new four-demand contract and fresh guarded runs.",
                   "One seed, two aircraft, two IID types and a shared general depot-to-base link; no item-specific transport, cross-link pooling, larger threshold, partial batch, GUI-only or cross-engine claim.",
                   "No resource rows or ResourceResults are authored; resource capacity is outside scope."],
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                      "checks_total": result["checks_total"], "failures": failed}))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

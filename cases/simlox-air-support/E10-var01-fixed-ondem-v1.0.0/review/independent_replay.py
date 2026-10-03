"""Independent read-only replay of E10.var01 native FIXED and ONDEM evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
OUTPUT = Path(__file__).with_name("independent-verdict.json")
IDS = {a: f"e10-var01-{a}-v100-ssh-20261003-01" for a in ("fixed", "ondem")}
checks = []


def check(name, ok, gate="evidence"):
    checks.append({"name": name, "passed": bool(ok), "gate": gate})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, native=False):
    text = path.read_text(encoding="utf-8-sig")
    if native:
        text = re.sub(r",(?=\s*[}\]])", "", text)
    return json.loads(text)


def tables(doc, key="model"):
    return {t["name"]: t for t in doc[key]["tables"]}


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def get(table, row, column):
    return row[[c["name"] for c in table["columns"]].index(column)]


def near(a, b, tol=0.0003):
    return math.isclose(float(a), float(b), rel_tol=0, abs_tol=tol)


def event(log, hour, text):
    return any(line.startswith(f"Time: {hour} ") and text in line for line in log.splitlines())


def check_roundtrip(arm, authored, exported):
    count = 0
    for name, source in authored.items():
        if not rows(source):
            continue
        count += 1
        target = exported.get(name)
        same = target is not None
        if same:
            width = len(source["columns"])
            same = ([c["name"] for c in source["columns"]] ==
                    [c["name"] for c in target["columns"][:width]])
            same &= ([i["rows"] for i in source["instances"]] ==
                     [[r[:width] for r in i["rows"]] for i in target["instances"]])
        check(f"{arm}: exact source roundtrip {name}", same)
    check(f"{arm}: 22 row-containing source tables", count == 22)


def check_bins(arm, table):
    series = rows(table)
    check(f"{arm}: {table['name']} has 72 bins", len(series) == 72)
    for i, row in enumerate(series):
        check(f"{arm}: {table['name']} interval {i}", near(get(table, row, "STINT"), i / 2, 1e-6) and
              near(get(table, row, "ETINT"), (i + 1) / 2, 1e-6))
    return series


def main():
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    parent_pkg = ROOT / "E04-upstream-transport-fast-v1.0.0"
    parent_input = parent_pkg / "native-input.json"
    parent_closure = parent_pkg / "runs" / "e04-fast-v100-ssh-20260929-01" / "closure.json"
    prerequisite = ROOT / "E02-zero-stock-local-backorder-v1.0.0"
    prereq_input = prerequisite / "native-input.json"
    prereq_closure = prerequisite / "runs" / "e02-v100-ssh-20260929-01" / "closure.json"
    check("accepted E04 parent input seal", sha(parent_input) == contract["accepted_parent"]["input_sha256"])
    check("accepted E04 parent closure seal", sha(parent_closure) == contract["accepted_parent"]["native_closure_sha256"])
    check("E02 prerequisite input seal", sha(prereq_input) == contract["supporting_prerequisite"]["input_sha256"])
    check("E02 prerequisite closure seal", sha(prereq_closure) == contract["supporting_prerequisite"]["native_closure_sha256"])
    check("contract exact-diff SHA", sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
    check("diff parent identity", diff["parent_sha256"] == sha(parent_input))
    parent = tables(load(parent_input))
    source = {arm: tables(load(CASE / f"native-input-{arm}.json")) for arm in IDS}
    for arm, child in source.items():
        check(f"{arm}: source SHA", sha(CASE / f"native-input-{arm}.json") ==
              contract["arms"][arm]["input_sha256"] == diff["source_sha256"][arm])
        changes = {name for name in parent.keys() | child.keys() if parent.get(name) != child.get(name)}
        check(f"{arm}: exact parent table delta", changes == {"ProblemDescription", "StationStructure", "TransportPolicyProfile"})
        for name in sorted(parent.keys() - changes):
            check(f"{arm}: unchanged parent table {name}", parent[name] == child[name])
        old = rows(parent["StationStructure"])[0]
        now = rows(child["StationStructure"])[0]
        structure = child["StationStructure"]
        check(f"{arm}: only downward PFRMS binding", [c["name"] for c in parent["StationStructure"]["columns"]] ==
              [c["name"] for c in structure["columns"]] and
              [(column["name"], x, y) for column, x, y in zip(structure["columns"], old, now) if x != y] ==
              [("PFRMS", None, "DOWN-POLICY")])
        profile = child["TransportPolicyProfile"]
        profile_rows = rows(profile)
        check(f"{arm}: one matched policy row", len(profile_rows) == 1 and
              [get(profile, profile_rows[0], k) for k in ("TPRID", "STPRID", "STIM", "DURN", "TPTIM")] ==
              ["DOWN-POLICY", contract["arms"][arm]["policy"], contract["arms"][arm]["start_hour"],
               contract["arms"][arm]["duration_hours"], 2.0])
        check(f"{arm}: no personnel resource rows", not rows(child["Resource"]) and
              not rows(child["ResourceAllocation"]) and not rows(child["TaskResource"]))
    check("pair differs in description and profile only", {name for name in source["fixed"].keys() | source["ondem"].keys()
          if source["fixed"].get(name) != source["ondem"].get(name)} ==
          {"ProblemDescription", "TransportPolicyProfile"})

    observed = {}
    for arm, run_id in IDS.items():
        folder = CASE / "runs" / run_id
        invocation = load(folder / "invocation.json")
        closure = load(folder / "closure.json")
        check(f"{arm}: run identity", invocation["run_id"] == closure["run_id"] == run_id)
        check(f"{arm}: invocation input binding", invocation["input_sha256"] ==
              sha(CASE / f"native-input-{arm}.json") == sha(folder / "input.json"))
        check(f"{arm}: closure invocation binding", closure["invocation_sha256"] == sha(folder / "invocation.json"))
        check(f"{arm}: source stable before/after", closure["source_hashes_before"] ==
              closure["source_hashes_after"] == invocation["source_hashes_before"])
        sealed = {
            "input": CASE / f"native-input-{arm}.json", "parent": parent_input,
            "parent_closure": parent_closure, "catalog_parent": prereq_input,
            "catalog_parent_closure": prereq_closure, "contract": CASE / "contract.json",
            "exact_diff": CASE / "exact-diff.json", "builder": CASE / "build.py",
            "diff_builder": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
            "runner_script": CASE / "run_native_ssh.ps1",
        }
        for name, path in sealed.items():
            check(f"{arm}: source seal {name}", closure["source_hashes_before"][name] == sha(path))
        pins = closure["source_hashes_before"]
        check(f"{arm}: manual/dictionary/exe pins", pins["manual"] == contract["source"]["manual_pdf_sha256"] and
              pins["dictionary"] == contract["source"]["dictionary_sha256"] and
              pins["simlox_exe"] == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0")
        check(f"{arm}: SSH0/mutex/GUI", invocation["execution_mode"] == "ssh_cli_v1" and
              invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
              invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
              invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        steps = load(folder / "steps.json")
        check(f"{arm}: five successful guarded steps", [s["name"] for s in steps] ==
              ["import", "export", "calc", "jsonreport", "check_import_export"] and
              all(s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
        check(f"{arm}: twelve raw seals", len(closure["raw"]) == 12)
        for name, metadata in sorted(closure["raw"].items()):
            path = folder / name
            check(f"{arm}: raw seal {name}", path.stat().st_size == metadata["bytes"] and
                  sha(path) == metadata["sha256"])
        check_roundtrip(arm, source[arm], tables(load(folder / "roundtrip-raw.json", True)))
        converter = (folder / "run.log").read_text(encoding="utf-8-sig")
        check(f"{arm}: converter errors0/warning108/notes0", bool(re.search(r"Errors:\s*0, Warnings:\s*1, Notes:\s*0", converter)) and
              re.findall(r"warning #(\d+)", converter) == ["108"])
        check(f"{arm}: valid native output", all((folder / name).stat().st_size > 1000 for name in
              ("model.sxo", "model.log", "report-raw.json")))
        log = (folder / "model.log").read_text(encoding="utf-8-sig")
        report = tables(load(folder / "report-raw.json", True), "report")
        check(f"{arm}: matched first failure h9.8829", event(log, "9.8829", "<TEACH-AIR-01,0> critical random failure added") and
              event(log, "9.8829", "BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted"))
        check(f"{arm}: one local and one depot demand at h10", sum("Item demand arrives" in line for line in log.splitlines()) == 2 and
              event(log, "10", "<TEACH-LRU-01,0,BASE-01,0> Item demand arrives") and
              event(log, "10", "<TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives"))
        check(f"{arm}: no later item demands", all(line.startswith("Time: 10 ") for line in log.splitlines()
              if "Item demand arrives" in line))
        check(f"{arm}: physical IDs and unchanged upward path", all(event(log, time, fragment) for time, fragment in (
              ("10", "Take replacement item <TEACH-LRU-01,0,0> from stock"),
              ("10.1667", "transport task"),
              ("12.1667", "<TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>"),
              ("12.1667", "Start repair of item <TEACH-LRU-01,0,1>"),
              ("13.1667", "Finished repair of item <TEACH-LRU-01,0,1>"),
              ("13.1667", "Put back replacement item <TEACH-LRU-01,0,1> to stock"))))
        check(f"{arm}: later missions 20-22 and 32-34 succeed", all(event(log, time, fragment) for time, fragment in (
              ("20", "BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting"),
              ("22", "BASIC-MISSION,TEACH-UNIT,0,0,1> mission success"),
              ("32", "BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting"),
              ("34", "BASIC-MISSION,TEACH-UNIT,0,0,2> mission success"))))
        sys, stock, summary = (report[n] for n in ("SystemResults", "StockTotalResults", "ResultSummary"))
        sy, st = check_bins(arm, sys), check_bins(arm, stock)
        clearance = 13 if arm == "fixed" else 12
        ready = clearance + 1 / 3
        for i, row in enumerate(st):
            left = i / 2
            check(f"{arm}: backorder bin {i}", (get(stock, row, "NBO") or 0) ==
                  (1 if 10 <= left < clearance else 0))
            check(f"{arm}: demand bin {i}", (get(stock, row, "NDF") or 0) ==
                  (1 if left == 10 else 0))
        check(f"{arm}: stock waiting time", near(sum((get(stock, row, "WT") or 0) for row in st), clearance - 10, 1e-6))
        check(f"{arm}: failure and maintenance bins", [get(sys, row, "STINT") for row in sy if (get(sys, row, "NFAIL") or 0) > 0] == [9.5] and
              [get(sys, row, "STINT") for row in sy if (get(sys, row, "NREPT") or 0) > 0] == [clearance])
        check(f"{arm}: readiness fractional bin", near(get(sys, sy[clearance * 2], "NSYRY"), 1 / 3, 0.0001) and
              event(log, f"{ready:.4f}", "System ready <TEACH-AIR-01,0>"))
        check(f"{arm}: terminal ready, backorder cleared", get(sys, sy[-1], "NSYRY") == 1 and
              (get(stock, st[-1], "NBO") or 0) == 0)
        result_row = rows(summary)[0]
        check(f"{arm}: summary one repetition, 36h, two of three successes", get(summary, result_row, "NREP") == 1 and
              get(summary, result_row, "RTIUP") == 36 and near(get(summary, result_row, "MSUF"), 2 / 3, 1e-5))
        observed[arm] = {"run_id": run_id, "closure_sha256": sha(folder / "closure.json"),
                         "report_sha256": sha(folder / "report-raw.json"), "log": log, "report": report}

    fixed, ondem = observed["fixed"], observed["ondem"]
    check("FIXED queued transport departs 11 arrives 13", all(event(fixed["log"], h, p) for h, p in (
          ("10", "attached to  scheduled transport task 0"),
          ("11", "scheduled transport task 0 starts with 1 items/systems"),
          ("13", "scheduled transport task 0 arrives with 1 items/systems"),
          ("13", "Replacement item arrives <TEACH-LRU-01,0,0>"),
          ("13", "Backorder removed, waiting time was 3"),
          ("13.3333", "System ready <TEACH-AIR-01,0>"))))
    check("ONDEM transport departs 10 arrives 12", all(event(ondem["log"], h, p) for h, p in (
          ("10", "transport task 1 starts with 1 items/systems"),
          ("12", "transport task 1 arrives with 1 items/systems"),
          ("12", "Replacement item arrives <TEACH-LRU-01,0,0>"),
          ("12", "Backorder removed, waiting time was 2"),
          ("12.3333", "System ready <TEACH-AIR-01,0>"))))
    check("one-hour report difference in backorder and readiness", sum(get(fixed["report"]["StockTotalResults"], r, "NBO") or 0
          for r in rows(fixed["report"]["StockTotalResults"])) == 6 and
          sum(get(ondem["report"]["StockTotalResults"], r, "NBO") or 0
              for r in rows(ondem["report"]["StockTotalResults"])) == 4)
    check("native report lacks ResourceResults", all("ResourceResults" not in data["report"] for data in observed.values()))
    check("frozen contract requires ResourceResults bins but none exist", all("ResourceResults" in data["report"] and
          len(rows(data["report"]["ResourceResults"])) == 72 for data in observed.values()), gate="frozen_contract")
    failures = [c["name"] for c in checks if not c["passed"]]
    evidence_failures = [c["name"] for c in checks if not c["passed"] and c["gate"] == "evidence"]
    report = {
        "schema": "simlox-e10-var01-independent-replay/v1",
        "passed": not failures, "verdict": "NO_GO_frozen_contract_resource_bins_unavailable" if failures else "GO",
        "behavioral_contrast_passed": not evidence_failures,
        "checks_passed": len(checks) - len(failures), "checks_total": len(checks), "failures": failures,
        "checks": checks,
        "hashes": {"fixed_input": sha(CASE / "native-input-fixed.json"), "ondem_input": sha(CASE / "native-input-ondem.json"),
                   "contract": sha(CASE / "contract.json"), "exact_diff": sha(CASE / "exact-diff.json")},
        "runs": {arm: {k: v for k, v in data.items() if k in ("run_id", "closure_sha256", "report_sha256")}
                 for arm, data in observed.items()},
        "observed": "Both arms have the same h9.8829 fault and sole h10 local/depot demand. ONDEM ships spare ID0 h10-12, clears BO at h12 and restores readiness h12.3333. FIXED queues h10, ships h11-13, clears BO at h13 and restores readiness h13.3333. Failed ID1 follows the same upward h10.1667-12.1667 path and h12.1667-13.1667 depot repair. Later h20 and h32 missions succeed; no later Item demand exists in either log.",
        "contract_mismatch": "The predeclared gate asks to reconcile 72 ResourceResults bins, but both authored models have no Resource/ResourceAllocation/TaskResource rows and neither selected report contains ResourceResults. Strict acceptance of the frozen contract is therefore not met; resource reporting is structurally inapplicable to this model.",
        "limits": ["Behavioral observations are one fixed seed, one demand and one general downward support link.",
                   "No later demand occurs, so this run does not establish repeated FIXED departure or ONDEM multi-demand behavior.",
                   "No batch-size, nested profile, distribution, item-specific override, GUI visual or cross-engine claim."],
    }
    OUTPUT.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": report["passed"], "behavioral_contrast_passed": report["behavioral_contrast_passed"],
                      "checks_passed": report["checks_passed"], "checks_total": report["checks_total"],
                      "failures": failures, "output": str(OUTPUT)}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Independent read-only replay of the predeclared D03.var02 cancellation branch.

Uses only the earlier independently authored JSON/event helpers, never the
author's validate_readonly.py or the native executable. Writes review only.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parent
V010 = ROOT / "D03-var02-mission-pm-conflict-v0.1.0"
V011 = ROOT / "D03-var02-mission-pm-conflict-v0.1.1"
V012 = ROOT / "D03-var02-mission-pm-conflict-v0.1.2"
RUN = V012 / "runs" / "d03-var02-mission245-v012-ssh-20261006-01"
PARENT = ROOT / "D03-calendar-pm-v1.0.0"
PARENT_RUN = PARENT / "runs" / "d03-calendar-v100-ssh-20261001-02"
VERDICT = HERE / "independent-readonly-verdict.json"
CONTRACT_SHA = "ce3498e9170eaf22579add9fe4adcca599ae8b05ed75fe0c7146403adcd8d929"
AUTHOR_SCRIPT_SHA = "eea431b53fb6520f638e40a265e1067229729d74754e94436b043f80ddf85c6b"
AUTHOR_RESULT_SHA = "332e919afca61dc81310f7e7383d38b78a9cfa82fa92ea9b2fc3a9d342a33bfa"
CONTRACT_REVIEW_SHA = "21e5cf9f43ba1492a0c01e896603255812a74f765df6a452fb22990db2f6a499"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    count = 0
    failures: list[str] = []

    def check(ok: bool, label: str) -> None:
        nonlocal count
        count += 1
        if not ok:
            failures.append(label)

    detail = {}
    try:
        contract = json.loads((CASE / "contract.json").read_text(encoding="utf-8-sig"))
        check(sha(CASE / "contract.json") == CONTRACT_SHA, "frozen v013 contract SHA")
        check(contract["mode"].startswith("read_only_reanalysis_") and
              contract["publication_state"] == "not_published", "read-only unpublished scope")
        check(sha(HERE / "independent-contract-go-2026-10-06.md") == CONTRACT_REVIEW_SHA,
              "independent contract-only review SHA")
        check(sha(CASE / "validate_readonly.py") == AUTHOR_SCRIPT_SHA, "author checker SHA")
        check(sha(HERE / "author-readonly-validation-2026-10-06.json") == AUTHOR_RESULT_SHA,
              "author result SHA")
        author = json.loads((HERE / "author-readonly-validation-2026-10-06.json").read_text(encoding="utf-8-sig"))
        check(author["passed"] is True and author["checks_count"] == 7623,
              "reported author 7623/7623 pass")

        historical = [
            (V010 / "contract.json", contract["prior_no_go_contract"]["contract_sha256"]),
            (V010 / "review" / "independent-contract-no-go-2026-10-06.md",
             contract["prior_no_go_contract"]["independent_no_go_sha256"]),
            (V011 / "contract.json", contract["predeclared_basis"]["contract_sha256"]),
            (V011 / "review" / "independent-contract-go-2026-10-06.md",
             contract["predeclared_basis"]["independent_contract_go_sha256"]),
            (V011 / "review" / "independent-prelaunch-no-go-2026-10-06.md",
             contract["predeclared_basis"]["prelaunch_no_go_sha256"]),
            (V012 / "contract.json", contract["preserved_failed_branch"]["contract_sha256"]),
            (V012 / "review" / "independent-prelaunch-go-2026-10-06.md",
             contract["preserved_failed_branch"]["prelaunch_go_sha256"]),
            (V012 / "review" / "author-native-validation-2026-10-06.json",
             contract["preserved_failed_branch"]["author_failed_verdict_sha256"]),
            (V012 / "review" / "independent-verdict.json",
             contract["preserved_failed_branch"]["independent_no_go_verdict_sha256"]),
            (V012 / "review" / "independent-diagnostic-postrun-2026-10-06.md",
             contract["preserved_failed_branch"]["independent_no_go_memo_sha256"]),
            (V012 / "review" / "independent_replay.py",
             contract["sealed_run"]["independent_diagnostic_script_sha256"]),
            (RUN / "closure.json", contract["sealed_run"]["closure_sha256"]),
            (RUN / "model.log", contract["sealed_run"]["model_log_sha256"]),
            (RUN / "report-raw.json", contract["sealed_run"]["report_sha256"]),
            (PARENT / "native-input.json", contract["accepted_parent"]["input_sha256"]),
            (PARENT / "cli-scope-signoff-2026-09-30.md", contract["accepted_parent"]["signoff_sha256"]),
            (PARENT_RUN / "closure.json", contract["accepted_parent"]["closure_sha256"]),
            (Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
             contract["source"]["manual_pdf_sha256"]),
            (Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
             contract["source"]["native_executable_sha256"]),
        ]
        for path, expected in historical:
            check(sha(path) == expected, f"historical source SHA {path.name} in {path.parent.name}")
        input_pin = contract["predeclared_basis"]["frozen_child_input_sha256"]
        for path in (V011 / "native-input.json", V012 / "native-input.json", RUN / "input.json"):
            check(sha(path) == input_pin, f"same frozen child input {path.parent.name}")
        original_author = json.loads((V012 / "review" / "author-native-validation-2026-10-06.json").read_text(encoding="utf-8-sig"))
        original_independent = json.loads((V012 / "review" / "independent-verdict.json").read_text(encoding="utf-8-sig"))
        check(original_author["passed"] is False and
              original_independent["verdict"] == "NO_GO_FULL_CONTRACT" and
              original_independent["diagnostic_evidence_passed"] is True,
              "v012 mission-first failure remains excluded")

        # Import only this reviewer's earlier utility functions, whose exact
        # script SHA is pinned above. Its main() is never called or written.
        spec = importlib.util.spec_from_file_location("independent_v012", V012 / "review" / "independent_replay.py")
        independent = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(independent)
        load = independent.json_with_native_trailing_comma
        rows = independent.rows
        event_map = independent.event_map
        event_times = independent.event_times
        same = independent.same

        closure, parent_closure = load(RUN / "closure.json"), load(PARENT_RUN / "closure.json")
        invocation, steps = load(RUN / "invocation.json"), load(RUN / "steps.json")
        check(closure["error"] is None and parent_closure["error"] is None, "complete parent and child closures")
        check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "sealed invocation")
        check(closure["source_hashes_before"] == closure["source_hashes_after"], "source before/after identity")
        check(len(closure["raw"]) == len(parent_closure["raw"]) == 12, "twelve raw files in each closure")
        for role, folder, sealset in (("child", RUN, closure), ("parent", PARENT_RUN, parent_closure)):
            for name, pin in sorted(sealset["raw"].items()):
                path = folder / name
                check(path.is_file(), f"{role} raw file {name}")
                check(path.stat().st_size == pin["bytes"], f"{role} raw size {name}")
                check(sha(path) == pin["sha256"], f"{role} raw SHA {name}")
        source_paths = {
            "input": V012 / "native-input.json",
            "parent": PARENT / "native-input.json",
            "parent_signoff": PARENT / "cli-scope-signoff-2026-09-30.md",
            "parent_closure": PARENT_RUN / "closure.json",
            "a02_signoff": ROOT / "A02-single-aircraft-repeated-missions" / "cli-scope-signoff-2026-09-29.md",
            "b02_evidence": ROOT / "B02-serial-preparation-v1.0.2" / "evidence-2026-09-29.md",
            "contract_review": V012 / "review" / "independent-contract-go-2026-10-06.md",
            "contract": V012 / "contract.json",
            "builder": V012 / "build.py",
            "checker": V012 / "check_roundtrip.py",
            "diff_checker": V012 / "check_parent_diff.py",
            "validator": V012 / "validate_native_cli.py",
            "ledger": V012 / "reconstruct_system_ledger.py",
            "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
            "runner_script": V012 / "run_native_ssh.ps1",
            "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        }
        check(set(source_paths) == set(closure["source_hashes_before"]), "all 16 original source pin keys")
        for key, path in source_paths.items():
            check(sha(path) == closure["source_hashes_before"][key], f"original source SHA {key}")
        check(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
              "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0 and sshd ancestor")
        check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "global native mutex")
        check(invocation["gui"] == {"pid": 13340, "session_id": 1,
              "start_utc": "2026-09-28T10:09:56.8261381Z"}, "protected GUI identity")
        check([step["name"] for step in steps] ==
              ["import", "export", "check_import_export", "calc", "jsonreport"], "ordered guarded steps")
        for step in steps:
            check(step["status"] == "completed" and step["exit_code"] == 0
                  and step["gui_preserved"] is True, f"completed step {step['name']}")
        check("Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig"), "native import marker")
        check("Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig"), "native export marker")
        calc = (RUN / "run.log").read_text(encoding="utf-8-sig")
        check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc
              and sorted(__import__("re").findall(r"\(warning #(\d+)\)", calc)) == ["108", "126"],
              "converter 0/2/0 only warnings 108 and 126")
        source, parent_source, native = load(V012 / "native-input.json"), load(PARENT / "native-input.json"), load(RUN / "roundtrip-raw.json")
        reset = copy.deepcopy(source)
        changed = [table for table in reset["model"]["tables"] if table["name"] == "OperationProfile"]
        check(len(changed) == 1, "single OperationProfile table")
        names = [column["name"] for column in changed[0]["columns"]]
        check(changed[0]["instances"][0]["rows"][1][names.index("STIM")] == 24.5,
              "second mission moved to h24.5")
        changed[0]["instances"][0]["rows"][1][names.index("STIM")] = 20.0
        check(reset == parent_source, "sole source difference is STIM 20 to 24.5")
        authored_cells = sum(len(row) for table in source["model"]["tables"]
                             for instance in table["instances"] for row in instance["rows"])
        check(authored_cells == 216, "216 positional authored source cells")
        authored_count = 0
        by_name = {table["name"]: table for table in native["model"]["tables"]}
        for table in source["model"]["tables"]:
            authored_rows = [row for inst in table["instances"] for row in inst["rows"]]
            if not authored_rows:
                continue
            authored_count += 1
            exported = by_name.get(table["name"])
            check(exported is not None, f"exported authored table {table['name']}")
            check(exported is not None and exported["columns"] == table["columns"],
                  f"authored columns {table['name']}")
            check(exported is not None and
                  [row for inst in exported["instances"] for row in inst["rows"]] == authored_rows,
                  f"authored rows {table['name']}")
        check(authored_count == 18, "18 authored row-containing tables")

        log = (RUN / "model.log").read_text(encoding="utf-8-sig")
        parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
        def prefix(text: str) -> list[str]:
            import re
            return [line for line in text.splitlines()
                    if (match := re.match(r"^Time: ([\d.]+) ", line)) and float(match[1]) < 19]
        check(prefix(log) == prefix(parent_log) and len(prefix(log)) == 30, "30 equal pre-h19 event lines")
        allocated = event_map(log, "mission allocates system: <TEACH-AIR-01,0>")
        started = event_map(log, "mission starting, duration: 2 : <TEACH-AIR-01,0>")
        succeeded = event_map(log, "mission success: ")
        completed = event_map(log, "mission completed: <TEACH-AIR-01,0>")
        cancelled = event_map(log, "mission cancelled: ")
        check(allocated == {0: 7.0, 1: 23.5, 2: 31.0}, "all three mission allocations")
        check(started == {0: 8.0, 2: 32.0} and succeeded == completed == {0: 10.0, 2: 34.0},
              "two starts and successful completions")
        check(cancelled == {1: 24.8333}, "PM-time cancellation of booked identity 1")
        pm_start = event_times(log, r" system PM task \d+ on <TEACH-AIR-01,0> started")
        pm_done = event_times(log, r" system PM task \d+ on <TEACH-AIR-01,0> completed")
        sub_start = event_times(log, r" subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours")
        sub_done = event_times(log, r" subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> completed")
        check(pm_start == sub_start == [24, 49] and pm_done == sub_done == [25, 50],
              "two complete one-hour CAL24 PMs")
        check("Time: 24 <TEACH-AIR-01,BASE-01,0> System to PM <TEACH-AIR-01,0>" in log
              and "Time: 25 <TEACH-AIR-01,BASE-01,0> Maintained system arrives <TEACH-AIR-01,0>" in log,
              "physical aircraft entered and left PM")
        check(allocated[1] < pm_start[0] < cancelled[1] < pm_done[0],
              "booked mission cancels during active PM")

        report, parent_report = load(RUN / "report-raw.json"), load(PARENT_RUN / "report-raw.json")
        system, parent_system = rows(report, "SystemResults", "report"), rows(parent_report, "SystemResults", "report")
        stock, parent_stock = rows(report, "StockTotalResults", "report"), rows(parent_report, "StockTotalResults", "report")
        summary = rows(report, "ResultSummary", "report")
        check(len(system) == len(stock) == len(parent_system) == len(parent_stock) == 120,
              "120 child/parent System and Stock bins")
        check(len(system[0]) == 40 and len(stock[0]) == 16 and len(summary) == 1 and len(summary[0]) == 11,
              "40/16/11 report geometry")
        check([r for r in system if r["ETINT"] <= 19] ==
              [r for r in parent_system if r["ETINT"] <= 19], "System prefix through h19")
        forms = {state: next(row for row in parent_system if row["STINT"] == time)
                 for state, time in (("ready", 18.5), ("reserved", 19.5),
                                     ("mission", 20.5), ("pm", 24.5))}
        state_bins = {state: 0 for state in forms}
        field_count = 0
        for i, actual in enumerate(system):
            time = i / 2
            check(actual["STINT"] == time and actual["ETINT"] == (i + 1) / 2,
                  f"System interval {i}")
            active = []
            if any(a <= time < b for a, b in zip(pm_start, pm_done)):
                active.append("pm")
            if any(started[j] <= time < completed[j] for j in started):
                active.append("mission")
            reservation_end = {0: started[0], 1: pm_start[0], 2: started[2]}
            if any(allocated[j] <= time < reservation_end[j] for j in allocated):
                active.append("reserved")
            check(len(active) <= 1, f"single physical aircraft state h{time}")
            state = active[0] if active else "ready"
            state_bins[state] += 1
            expected = dict(forms[state])
            expected.update(STINT=time, ETINT=(i + 1) / 2,
                            NPMS=int(time in pm_start), NPMT=int(time in pm_done),
                            NSYDT=int(time in pm_start), SYDT=1 if time in pm_start else None)
            check(set(actual) == set(expected), f"System field names h{time}")
            for field, want in expected.items():
                field_count += 1
                check(same(actual[field], want, 5e-5), f"System h{time} {field}")
        check(field_count == 4800 and state_bins == {"ready": 103, "reserved": 5, "mission": 8, "pm": 4},
              "4,800 event-derived System fields and state bins")
        stock_fields = 0
        for i, (actual, control) in enumerate(zip(stock, parent_stock)):
            check(actual["STINT"] == i / 2 and actual["ETINT"] == (i + 1) / 2,
                  f"Stock interval {i}")
            check(set(actual) == set(control), f"Stock field names {i}")
            for field, want in control.items():
                stock_fields += 1
                check(actual[field] == want, f"Stock row {i} {field}")
        check(stock_fields == 1920, "1,920 Stock fields equal item-free parent")
        expected_summary = {"NREP": 1, "RTILW": 0, "RTIUP": 60,
                            "MTMF": 2 / 3, "RSMTMF": 0, "MSTF": 2 / 3,
                            "RSMSTF": 0, "MSUF": 2 / 3, "RSMSUF": 0,
                            "STMF": 2 / 3, "RSSTMF": 0}
        check(set(summary[0]) == set(expected_summary), "11 summary field names")
        for field, want in expected_summary.items():
            check(same(summary[0][field], want, 3e-8), f"summary {field}")
        integrals = {field: sum(float(row[field]) * .5 for row in system)
                     for field in ("NSYRY", "NSYA", "NSYMA", "NSYMO", "NSYPM")}
        for field, want in {"NSYRY": 51.5, "NSYA": 58, "NSYMA": 6.5,
                            "NSYMO": 4, "NSYPM": 2}.items():
            check(same(integrals[field], want, 5e-5), f"event-derived integral {field}")
        check(sum(row["NPMS"] for row in system) == sum(row["NPMT"] for row in system) == 2,
              "two report PM starts and completions")
        check(all(row["NFAIL"] == 0 and row["NREPT"] == 0 for row in system),
              "zero failure/repair markers")
        check(system[-1]["NSYRY"] == 1 and system[-1]["NSYMO"] == 0
              and system[-1]["NSYPM"] == 0, "terminal aircraft ready")
        check(all(row["NBO"] == 0 and row["NDF"] == 0 for row in stock),
              "no item demand or backorder")
        detail = {"mission": {"allocated": allocated, "started": started, "succeeded": succeeded,
                              "completed": completed, "cancelled": cancelled},
                  "pm_start": pm_start, "pm_complete": pm_done,
                  "state_bins": state_bins, "integrals": integrals,
                  "system_field_comparisons": field_count,
                  "stock_field_comparisons": stock_fields,
                  "summary_field_comparisons": 11}
    except Exception as exc:
        failures.append(f"replay exception: {type(exc).__name__}: {exc}")

    verdict = {
        "schema": "simlox-d03-var02-v013-independent-readonly/v1",
        "run_id": RUN.name,
        "passed": not failures,
        "verdict": "GO_BOUNDED_READONLY_REANALYSIS" if not failures else "NO_GO",
        "checks_count": count,
        "failures": failures,
        "details": detail,
        "preserved_v012_status": "NO_GO_FULL_CONTRACT",
        "scope": "Previously reviewed v0.1.1 broad PM-attributed cancellation branch applied to sealed v0.1.2 evidence only",
        "limitations": ["No new native or GUI run.", "One fixed-seed aircraft and one shifted mission.",
                        "No general PM priority, resource or recurrence rule.",
                        "Original v0.1.2 mission-first contract remains failed."],
    }
    VERDICT.write_bytes((json.dumps(verdict, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": verdict["verdict"], "checks_count": count,
                      "failures": failures}, ensure_ascii=False))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

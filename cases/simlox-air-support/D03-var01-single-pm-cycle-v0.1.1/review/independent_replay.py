"""Independent, read-only replay of the sealed D03.var01 native evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / "runs" / "d03-var01-onecycle-v011-ssh-20261006-01"
PARENT = ROOT / "D03-calendar-pm-v1.0.0"
PARENT_RUN = PARENT / "runs" / "d03-calendar-v100-ssh-20261001-02"
VERDICT = CASE / "review" / "independent-verdict.json"

EXPECTED = {
    "input": "760cb41baca99d7fe3b8558a58c7330acb81944bb3d3ceba4e4241c06b9b9a00",
    "parent": "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32",
    "parent_signoff": "8c609dc19b1a4b7f027da9538096c5171244609b80cab9026e1ad360cd9006d1",
    "parent_closure": "9cd845f957105eb8659809ec09cf380ae5df68a63babb264d70631c164f7d2d8",
    "a02_signoff": "608eef828a65ef7a8c738a3ec227b890421c29248ee8addd9e992a4c7e7e919e",
    "b02_evidence": "bceddd5983e9187bf8be19464b04ad5b2136bf665f6d4d9d676928b8c2354c61",
    "contract_review": "a07a9daa41ec5eb30b91fe4e14813db928c382ec5cd04847810bc50a51d5ae9d",
    "excluded_prelaunch_no_go": "a19f508c055ac943d497d54651e18ec0950edeb5cdadcac1bfafcaa5cc44eb42",
    "contract": "ec40614d1b6c916a7108e3c07b35ac7d0ea035f6d24a5d2ae32f6f4ec231c107",
    "builder": "c6b02d60e01c348334e74906f51834c0eed8848dfa7e47f4ca72cedfe341db12",
    "checker": "dc0d1788d8c259d49e6c38294ef2c64c9adaa0d99397d6c04b4e6f3e986bb3cf",
    "diff_checker": "149dbfd98a30981db1e9365a4a05d55816c8135220984449e401789f035fc500",
    "validator": "ce1199870ccc1706841f23088e29e022cff3702bcbe52f45daab2f1281caace1",
    "python": "372c2eae555b344520bf147be0096e009069aeca4e7f78d6aecea6d53158056a",
    "runner_script": "50419a7bbde4a67ef10f6e5a0853211034b59dc2361fe14e72ee767af30b25cd",
    "simlox_exe": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
}

PATHS = {
    "input": CASE / "native-input.json",
    "parent": PARENT / "native-input.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-09-30.md",
    "parent_closure": PARENT_RUN / "closure.json",
    "a02_signoff": ROOT / "A02-single-aircraft-repeated-missions" / "cli-scope-signoff-2026-09-29.md",
    "b02_evidence": ROOT / "B02-serial-preparation-v1.0.2" / "evidence-2026-09-29.md",
    "contract_review": CASE / "review" / "independent-contract-go-2026-10-06.md",
    "excluded_prelaunch_no_go": ROOT / "D03-var01-single-pm-cycle-v0.1.0" / "review" / "independent-prelaunch-no-go-2026-10-06.md",
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "checker": CASE / "check_roundtrip.py",
    "diff_checker": CASE / "check_parent_diff.py",
    "validator": CASE / "validate_native_cli.py",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "runner_script": CASE / "run_native_ssh.ps1",
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        out = []
        quoted = escaped = False
        for i, char in enumerate(text):
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
            elif char == "," and text[i + 1 :].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def tables(doc: dict, root: str) -> dict:
    return {t["name"]: t for t in doc[root]["tables"]}


def rows(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


def flat_cells(doc: dict) -> dict[tuple, object]:
    cells = {}
    for table in doc["model"]["tables"]:
        for inst_i, instance in enumerate(table["instances"]):
            for row_i, row in enumerate(instance["rows"]):
                for col, value in zip(table["columns"], row, strict=True):
                    key = (table["name"], inst_i, row_i, col["name"])
                    if key in cells:
                        raise ValueError(f"duplicate authored cell {key}")
                    cells[key] = value
    return cells


def main() -> int:
    count = 0
    failures: list[str] = []

    def check(label: str, actual: object, expected: object) -> None:
        nonlocal count
        count += 1
        if actual != expected:
            failures.append(f"{label}: actual={actual!r}, expected={expected!r}")

    def near(label: str, actual: float, expected: float, tol: float = 3e-5) -> None:
        check(label, abs(actual - expected) <= tol, True)

    observations = {}
    try:
        for key, expected in EXPECTED.items():
            check(f"frozen source {key}", sha(PATHS[key]), expected)
        invocation = native_json(RUN / "invocation.json")
        closure = native_json(RUN / "closure.json")
        steps = native_json(RUN / "steps.json")
        roundtrip_verdict = native_json(RUN / "roundtrip-validation.json")
        parent_closure = native_json(PARENT_RUN / "closure.json")
        contract = native_json(CASE / "contract.json")
        check("contract variant/version", (contract["variant_id"], contract["version"]),
              ("D03.var01", "0.1.1-contract-candidate"))
        check("contract links excluded prelaunch", contract["prelaunch_revision"]["excluded_prelaunch_no_go_sha256"],
              EXPECTED["excluded_prelaunch_no_go"])
        check("contract reserved run", contract["ownership"]["native_run_id_reserved"], RUN.name)
        check("parent closure clean", parent_closure["error"], None)
        check("parent raw seal count", len(parent_closure["raw"]), 12)
        for name, seal in sorted(parent_closure["raw"].items()):
            p = PARENT_RUN / name
            check(f"parent raw bytes {name}", p.stat().st_size, seal["bytes"])
            check(f"parent raw SHA {name}", sha(p), seal["sha256"])
        check("closure clean", closure["error"], None)
        check("closure run/schema", (closure["run_id"], closure["schema"]),
              (RUN.name, "simlox-d03-var01-v011-native-closure/v1"))
        check("invocation SHA", closure["invocation_sha256"], sha(RUN / "invocation.json"))
        check("child raw seal count", len(closure["raw"]), 12)
        check("child raw file set", set(closure["raw"]),
              {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"})
        for name, seal in sorted(closure["raw"].items()):
            p = RUN / name
            check(f"child raw bytes {name}", p.stat().st_size, seal["bytes"])
            check(f"child raw SHA {name}", sha(p), seal["sha256"])
        for key, expected in EXPECTED.items():
            check(f"closure before {key}", closure["source_hashes_before"][key], expected)
            check(f"closure after {key}", closure["source_hashes_after"][key], expected)
        check("before/after source map", closure["source_hashes_before"], closure["source_hashes_after"])
        check("run input copied exactly", sha(RUN / "input.json"), EXPECTED["input"])
        check("invocation source pins", (invocation["input_sha256"], invocation["parent_sha256"],
                                         invocation["contract_sha256"], invocation["runner_script_sha256"]),
              (EXPECTED["input"], EXPECTED["parent"], EXPECTED["contract"], EXPECTED["runner_script"]))
        check("SSH0 evidence", (invocation["session_id"], invocation["ssh_connection_present"],
                                 "sshd.exe" in invocation["ssh_ancestor_names"]), (0, True, True))
        check("protected GUI", invocation["gui"],
              {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
        check("mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("planned native steps", [x["name"] for x in invocation["planned_commands"]],
              ["import", "export", "calc", "jsonreport"])
        check("actual guarded order", [x["name"] for x in steps],
              ["import", "export", "check_import_export", "calc", "jsonreport"])
        for i, step in enumerate(steps):
            check(f"step {i} completed/GUI/exit", (step["status"], step["gui_preserved"], step["exit_code"]),
                  ("completed", True, 0))
            check(f"step {i} time order", step["started_utc"] <= step["completed_utc"], True)
        for i in range(len(steps) - 1):
            check(f"step boundary {i}", steps[i]["completed_utc"] <= steps[i + 1]["started_utc"], True)
        check("roundtrip checker passed", roundtrip_verdict["passed"], True)
        check("roundtrip schema", roundtrip_verdict["schema"], "simlox-d03-var01-v011-import-export/v1")
        check("roundtrip input/export SHA", (roundtrip_verdict["source_sha256"],
                                               roundtrip_verdict["roundtrip_sha256"]),
              (EXPECTED["input"], sha(RUN / "roundtrip-raw.json")))

        parent_input = native_json(PARENT / "native-input.json")
        child_input = native_json(CASE / "native-input.json")
        exported = native_json(RUN / "roundtrip-raw.json")
        parent_cells = flat_cells(parent_input)
        child_cells = flat_cells(child_input)
        check("parent/child cell keys", set(child_cells), set(parent_cells))
        check("authored cell count", len(child_cells), 216)
        changes = {
            ("ProblemDescription", 0, 0, "PDESC"),
            ("Control", 0, 0, "SIMPE"),
            ("Control", 0, 0, "RCEND"),
            ("ResultCollection", 0, 0, "RCEND"),
            ("ResultCollection", 0, 1, "RCEND"),
        }
        check("exact changed cell keys", {k for k in child_cells if child_cells[k] != parent_cells[k]}, changes)
        for key, value in child_cells.items():
            if key not in changes:
                check(f"retained authored cell {key}", value, parent_cells[key])
        source_tables = tables(child_input, "model")
        exported_tables = tables(exported, "model")
        authored = {k for k, t in source_tables.items() if rows(t)}
        check("authored row-containing table count", len(authored), 18)
        for name in sorted(authored):
            check(f"roundtrip column/row {name}",
                  (source_tables[name]["columns"], rows(source_tables[name])),
                  (exported_tables[name]["columns"], rows(exported_tables[name])))

        calc = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("converter marker", re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", calc),
              [("0", "2", "0")])
        check("converter warning codes", re.findall(r"\(warning #(\d+)\)", calc), ["108", "126"])
        check("converter error codes", re.findall(r"\(error #(\d+)\)", calc), [])
        check("warning 126 target", "This system contains no items: TEACH-AIR-01" in calc, True)
        for name in ("model.sxi", "model.sxo", "model.log", "report-raw.json"):
            check(f"nonplaceholder native output {name}", (RUN / name).stat().st_size > 4, True)

        log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        parent_lines = parent_log.splitlines()
        prefix_end = next(i for i, line in enumerate(parent_lines) if line.startswith("Time: 48 "))
        check("event prefix parent equality", log.splitlines()[2:], parent_lines[2:prefix_end])
        def event_times(pattern: str) -> list[float]:
            return [float(x) for x in re.findall(pattern, log, re.MULTILINE)]
        check("PM started", event_times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started$"), [24.0])
        check("PM completed", event_times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed$"), [25.0])
        check("CAL24 task identity", len(re.findall(r"^Time: [\d.]+  system PM task \d+ on <TEACH-AIR-01,0> PMID: CAL24$", log, re.MULTILINE)), 1)
        check("PM physical work start", event_times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours$"), [24.0])
        check("PM physical work completion", event_times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> completed$"), [25.0])
        check("mission start", event_times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission starting, duration: 2 : <TEACH-AIR-01,0>$"), [8.0, 20.0, 32.0])
        check("mission success", event_times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success: $"), [10.0, 22.0, 34.0])
        check("mission completion", event_times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission completed: <TEACH-AIR-01,0>$"), [10.0, 22.0, 34.0])
        check("no failure/abort/cancel", bool(re.search(r"(?:failure occurs|mission (?:aborted|cancelled|canceled))", log, re.I)), False)
        check("no second PM in child", "Time: 49  system PM task" in log, False)

        report = native_json(RUN / "report-raw.json")
        parent_report = native_json(PARENT_RUN / "report-raw.json")
        child_report_tables = tables(report, "report")
        parent_report_tables = tables(parent_report, "report")
        summary = rows(child_report_tables["ResultSummary"])
        check("summary single/horizon", (len(summary), summary[0]["RTIUP"]), (1, 36))
        observed_bins = {}
        for table_name in ("SystemResults", "StockTotalResults"):
            actual_rows = rows(child_report_tables[table_name])
            expected_rows = rows(parent_report_tables[table_name])[:72]
            check(f"{table_name} 72 bins", len(actual_rows), 72)
            check(f"{table_name} parent prefix row count", len(expected_rows), 72)
            for i, (actual, expected) in enumerate(zip(actual_rows, expected_rows, strict=True)):
                check(f"{table_name} interval {i}", (actual["STINT"], actual["ETINT"]),
                      (i / 2, (i + 1) / 2))
                check(f"{table_name} same columns {i}", set(actual), set(expected))
                for column, value in expected.items():
                    check(f"{table_name} parent prefix {i}/{column}", actual[column], value)
            observed_bins[table_name] = actual_rows
        system_rows = observed_bins["SystemResults"]
        stock_rows = observed_bins["StockTotalResults"]
        check("zero failure and repair bins", all(x["NFAIL"] == 0 and x["NREPT"] == 0 for x in system_rows), True)
        for i, row in enumerate(stock_rows):
            for field in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT"):
                check(f"zero stock event bin {i}/{field}", row[field], 0)
        check("one PM start/completion in bins", (sum(x["NPMS"] for x in system_rows),
                                                   sum(x["NPMT"] for x in system_rows)), (1, 1))
        check("PM start/completion bin locations", ([x["STINT"] for x in system_rows if x["NPMS"] == 1],
                                                     [x["STINT"] for x in system_rows if x["NPMT"] == 1]),
              ([24.0], [25.0]))
        metrics = {k: sum((x[k] or 0) * .5 for x in system_rows)
                   for k in ("NSYRY", "NSYA", "NSYMO", "NSYPM")}
        for key, expected in (("NSYRY", 26), ("NSYA", 35), ("NSYMO", 6), ("NSYPM", 1)):
            near(f"{key} aircraft-hour integral", metrics[key], expected)
        check("terminal ready/no PM", (system_rows[-1]["NSYRY"], system_rows[-1]["NSYPM"]), (1, 0))
        observations = {"system_bins": len(system_rows), "stock_total_bins": len(observed_bins["StockTotalResults"]),
                        "pm_started_h": [24.0], "pm_completed_h": [25.0],
                        "mission_starts_h": [8.0, 20.0, 32.0],
                        "mission_completions_h": [10.0, 22.0, 34.0],
                        "aircraft_hours": metrics,
                        "child_closure_sha256": sha(RUN / "closure.json"),
                        "parent_closure_sha256": sha(PARENT_RUN / "closure.json")}
    except Exception as exc:
        failures.append(f"replay exception: {type(exc).__name__}: {exc}")
    result = {
        "schema": "simlox-d03-var01-v011-independent-replay/v1",
        "verdict": "GO_BOUNDED" if not failures else "NO_GO",
        "checks_passed": count - len(failures),
        "checks_total": count,
        "failures": failures,
        "observations": observations,
        "limits": [
            "One fixed-seed aircraft and one 36-hour child run; no general PM recurrence inference.",
            "StockTotalResults is aggregate, not physical item-ID on-hand evidence.",
            "Only command-recorded GUI identity/preservation is evidenced; no visual GUI state claim.",
            "v0.1.0 was excluded at prelaunch and had no native child run.",
        ],
    }
    VERDICT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("verdict", "checks_passed", "checks_total", "failures")}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

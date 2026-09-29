"""Independent read-only replay of five sealed D02.var06 native CLI probes.

Standard library only. Never imports builder/checker/author validator or starts
SIMLOX. Expected negative outcomes are judged from native field diagnostics,
not from the runner's noncompletion alone.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
PARENT = CASE.parent / "D01-installed-lru-direct-repair-v1.0.0/native-input.json"
OUTPUT = CASE / "review/independent-matrix-2026-09-30.json"
PARENT_SHA = "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"
RUN_SUFFIX = "-v100-ssh-20260930-01"
VARIANTS = {
    "item-calhours": ("Item", "CALHOURS", False),
    "item-missions": ("Item", "MISSIONS", False),
    "rate-ophours": ("ItemFailureRate", "OPHOURS", True),
    "rate-calhours": ("ItemFailureRate", "CALHOURS", False),
    "rate-missions": ("ItemFailureRate", "MISSIONS", False),
}
EXPECTED_SHA = {
    "item-calhours": "e6287abc8e3292aeef8ac2b2ff30daecddcb998eb2659c4741690e70b9879239",
    "item-missions": "99b3daaa36febae511e195c71f739dd34b23182f7c8e49f6db47b433b35c5dbc",
    "rate-ophours": "b76dd77056378ca06c0134ddd363816d9c9ac211e4f36181fb597eca0e9b4797",
    "rate-calhours": "70ba834f4fb2c6bd2ba4558e1c499024652b533f297951e53445585925b9e713",
    "rate-missions": "0fb2b7dd2761fe051d5ebc3c2c2cfdd957142c4f60db7c027efaa10a7c289262",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path, native: bool = False):
    text = path.read_text(encoding="utf-8-sig")
    if native:
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def tables(document, key="model"):
    return {table["name"]: table for table in document[key]["tables"]}


def rows(table):
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for part in table["instances"] for row in part["rows"]]


def main():
    checks = []

    def check(name, actual, expected):
        checks.append({"name": name, "passed": actual == expected, "actual": actual, "expected": expected})

    contract = load(CASE / "contract.json")
    parent = load(PARENT)
    parent_tables = tables(parent)
    check("accepted D01 parent SHA", sha(PARENT), PARENT_SHA)
    check("contract parent binding", contract["parent"]["input_sha256"], PARENT_SHA)
    check("five contract variants", sorted(contract["variants"]), sorted(VARIANTS))
    check("five frozen input paths", sorted(p.name for p in CASE.glob("native-input-*.json")),
          sorted(f"native-input-{key}.json" for key in VARIANTS))
    observations = {}
    models = {}
    run_hashes = {}

    for variant, (field_table, clock, positive) in VARIANTS.items():
        run_id = f"d02-var06-{variant}{RUN_SUFFIX}"
        run = CASE / "runs" / run_id
        source_path = CASE / f"native-input-{variant}.json"
        source = load(source_path)
        model = tables(source)
        models[variant] = model
        invocation = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        exported = tables(load(run / "roundtrip-raw.json", native=True))
        run_log = (run / "run.log").read_text(encoding="utf-8-sig")
        import_log = (run / "import.log").read_text(encoding="utf-8-sig")
        export_log = (run / "export.log").read_text(encoding="utf-8-sig")
        prefix = variant + ": "

        check(prefix + "frozen source SHA", sha(source_path), EXPECTED_SHA[variant])
        check(prefix + "contract source binding", contract["native_input_sha256"][variant], EXPECTED_SHA[variant])
        check(prefix + "copied native input SHA", sha(run / "input.json"), EXPECTED_SHA[variant])
        check(prefix + "invocation input/parent binding", [invocation["input_sha256"], invocation["parent_sha256"]], [EXPECTED_SHA[variant], PARENT_SHA])
        check(prefix + "run id binding", [invocation["run_id"], closure["run_id"]], [run_id, run_id])
        check(prefix + "invocation sealed in closure", closure["invocation_sha256"], sha(run / "invocation.json"))
        check(prefix + "source hashes stable", closure["source_hashes_before"], closure["source_hashes_after"])
        check(prefix + "invocation/closure source agreement", invocation["source_hashes_before"], closure["source_hashes_before"])
        for key, path in {"input": source_path, "parent": PARENT, "contract": CASE / "contract.json",
                          "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py",
                          "runner_script": CASE / "run_native_ssh.ps1"}.items():
            check(prefix + f"sealed local {key} bytes", sha(path), closure["source_hashes_before"][key])
        check(prefix + "session-0 SSH/GUI/queue guard",
              [invocation["execution_mode"], invocation["session_id"], invocation["ssh_connection_present"],
               invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["queue_mutex"]],
              ["ssh_cli_v1", 0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"])
        check(prefix + "raw artifact count", len(closure["raw"]), 12 if positive else 8)
        for name, claim in sorted(closure["raw"].items()):
            path = run / name
            check(prefix + f"raw sealed {name}", [path.stat().st_size, sha(path)], [claim["bytes"], claim["sha256"]])
        check(prefix + "import/export markers", ["Import completed!" in import_log, "Export completed!" in export_log], [True, True])
        check(prefix + "table names exported", sorted(exported), sorted(model))
        source_rows = [name for name, table in model.items() if any(part["rows"] for part in table["instances"])]
        check(prefix + "row-containing table count", len(source_rows), 19 if variant.startswith("rate-") else 18)
        check(prefix + "business source tables roundtrip", all(model[name] == exported.get(name) for name in source_rows), True)

        changed = sorted(name for name in parent_tables if parent_tables[name] != model.get(name))
        added = sorted(model.keys() - parent_tables.keys())
        check(prefix + "exact changed parent tables", changed,
              ["Item", "ProblemDescription"] if variant.startswith("item-") else ["ProblemDescription"])
        check(prefix + "exact added tables", added, [] if variant.startswith("item-") else ["ItemFailureRate"])
        if variant.startswith("item-"):
            before = rows(parent_tables["Item"])[0]
            after = rows(model["Item"])[0]
            check(prefix + "only Item.OPID differs", [key for key in before if before[key] != after[key]], ["OPID"])
            check(prefix + "Item.OPID value", [before["OPID"], after["OPID"]], ["OPHOURS", clock])
            check(prefix + "traditional FRT retained", after["FRT"], 300000)
        else:
            rate = rows(model["ItemFailureRate"])
            check(prefix + "rate row identity/value", rate, [{"IID": "TEACH-LRU-01", "OPID": clock, "FRT": 300000.0, "NOTE": None}])
            check(prefix + "base Item OPID/FRT retained", [rows(model["Item"])[0]["OPID"], rows(model["Item"])[0]["FRT"]], ["OPHOURS", 300000])
        check(prefix + "contract proposed table/value", [contract["variants"][variant]["table"], contract["variants"][variant]["value"]], [field_table, clock])

        match = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
        check(prefix + "conversion summary present", match is not None, True)
        if positive:
            check(prefix + "all five steps completed", [s["name"] for s in steps],
                  ["import", "export", "calc", "jsonreport", "check_import_export"])
            check(prefix + "all steps exit zero and preserve GUI", all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] for s in steps), True)
            check(prefix + "closure success", closure["error"], None)
            check(prefix + "positive conversion counts", match.groups() if match else None, ("0", "2", "0"))
            check(prefix + "positive warning codes", re.findall(r"warning #(\d+)", run_log), ["108", "2058"])
            check(prefix + "rate overrides base OPHOURS", "Data overrides previous data: TEACH-LRU-01/OPHOURS" in run_log, True)
            check(prefix + "simulation and report produced", ["Starting simulation..." in run_log,
                                                           "Saving results ..." in run_log,
                                                           (run / "model.sxo").stat().st_size > 4,
                                                           (run / "report-raw.json").stat().st_size > 4], [True] * 4)
            report = tables(load(run / "report-raw.json", native=True), "report")
            system_rows = rows(report["SystemResults"])
            stock_rows = rows(report["StockTotalResults"])
            check(prefix + "72 aligned system and stock report bins", [len(system_rows), len(stock_rows)], [72, 72])
            check(prefix + "report horizon", [(r["STINT"], r["ETINT"]) for r in system_rows],
                  [(i / 2, (i + 1) / 2) for i in range(72)])
            check(prefix + "one observed failure and repair", [sum(r["NFAIL"] for r in system_rows), sum(r["NREPT"] for r in system_rows)], [1, 1])
            check(prefix + "terminal ready", system_rows[-1]["NSYRY"], 1)
        else:
            check(prefix + "import/export pass and calc rejected by runner", [(s["name"], s["exit_code"], s["status"]) for s in steps],
                  [("import", 0, "completed"), ("export", 0, "completed"), ("calc", 0, "failed")])
            check(prefix + "GUI guard persisted on all attempted steps", all(s["gui_preserved"] for s in steps), True)
            check(prefix + "exact runner failure", closure["error"], "calc output model.sxo absent/empty")
            check(prefix + "native conversion counts", match.groups() if match else None, ("1", "1", "0"))
            check(prefix + "native field-specific diagnostic", re.search(
                rf"Form: {field_table}\s+rec 1: \(error #2057\) Predefined operation parameter not allowed:\s+{clock}\b", run_log) is not None, True)
            check(prefix + "no simulation/result saved", ["Starting simulation..." in run_log,
                                                        "Saving results ..." in run_log,
                                                        (run / "model.sxo").stat().st_size,
                                                        (run / "report-raw.json").exists()], [False, False, 4, False])
            check(prefix + "only expected logging warning", re.findall(r"warning #(\d+)", run_log), ["108"])
        observations[variant] = {
            "source_sha256": sha(source_path), "run_id": run_id,
            "conversion_errors": int(match.group(1)) if match else None,
            "conversion_warnings": int(match.group(2)) if match else None,
            "native_diagnostic": re.findall(r"rec 1: \((?:error|warning) #[^\n]+", run_log),
            "native_calc_exit_code": next(s["exit_code"] for s in steps if s["name"] == "calc"),
            "runner_error": closure["error"], "model_sxo_bytes": (run / "model.sxo").stat().st_size,
            "raw_report_sha256": sha(run / "report-raw.json") if positive else None,
        }
        run_hashes[variant] = {"invocation": sha(run / "invocation.json"), "closure": sha(run / "closure.json"),
                               "run_log": sha(run / "run.log")}

    # The three rate probes share the same structural base; the only behavior
    # change among them is ItemFailureRate.OPID, plus the description label.
    baseline = models["rate-ophours"]
    for variant in ("rate-calhours", "rate-missions"):
        candidate = models[variant]
        check(variant + ": only rate OPID/description differ from positive control",
              sorted(name for name in baseline if baseline[name] != candidate[name]),
              ["ItemFailureRate", "ProblemDescription"])
        before, after = rows(baseline["ItemFailureRate"])[0], rows(candidate["ItemFailureRate"])[0]
        check(variant + ": same rate row except OPID",
              {key: value for key, value in before.items() if key != "OPID"},
              {key: value for key, value in after.items() if key != "OPID"})

    result = {
        "schema": "simlox-d02-var06-independent-clock-matrix-readonly/v1",
        "reviewer": "independent standard-library read-only replay; no author imports or native calls",
        "case_id": "D02", "variant_id": "D02.var06",
        "passed": all(c["passed"] for c in checks),
        "passed_count": sum(c["passed"] for c in checks),
        "failed_count": sum(not c["passed"] for c in checks),
        "checks": checks, "runs": observations,
        "hashes": {"parent_input": sha(PARENT), "contract": sha(CASE / "contract.json"),
                   "run_seals": run_hashes},
        "decision": "four_native_clock_values_rejected_one_ophours_control_accepted" if all(c["passed"] for c in checks) else "review_failed",
        "limits": [
            "Negative inputs imported/exported; native conversion, not JSON parsing, emitted field-specific #2057 for CALHOURS or MISSIONS in Item and ItemFailureRate.",
            "The SIMLOX calc process returned exit code 0 for negative probes despite conversion error; runner correctly marked them failed because model.sxo was only four bytes. No negative simulation/report evidence exists.",
            "The positive ItemFailureRate.OPHOURS control had warning #2058 that the rate row overrides base Item.FRT, plus logging warning #108; zero conversion errors and complete simulation are the acceptance facts.",
            "This is installed-executable/version-specific evidence for these predefined clock values. Custom OperationParameter identifiers, other clock values, GUI visuals and cross-engine behavior remain untested.",
        ],
        "publication_state": "independent_review_only",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": [c for c in checks if not c["passed"]],
                      "output": str(OUTPUT)}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

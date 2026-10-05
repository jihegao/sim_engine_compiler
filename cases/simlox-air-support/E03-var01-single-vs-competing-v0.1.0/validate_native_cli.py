"""Read-only, source-bound replay of the E03.var01 single-demand candidate."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import validate_native as native  # noqa: E402

INPUT_SHA = "0fd7210b04aa8383a7288d3af0374fc96265c19f8d315612bee23a85c4d63879"
PARENT_SHA = "657c0d52116c09ef2dbd009209f461f6fb4ed3570327c4305e0e4608f208cbf0"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}
RUN_ID = "e03-var01-single-v010-ssh-20261006-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def validate(run: Path) -> dict:
    errors: list[str] = []
    checks = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            errors.append(label)

    contract = load(HERE / "contract.json")
    ck("contract and variant", contract.get("variant_id") == "E03.var01" and contract.get("native_input_sha256") == INPUT_SHA and contract["parent"]["input_sha256"] == PARENT_SHA)
    ck("frozen input", sha(HERE / "native-input.json") == INPUT_SHA and sha(run / "input.json") == INPUT_SHA)
    ck("accepted parent input", sha(HERE.parent / "E03-two-aircraft-shared-spare-v1.0.0/native-input.json") == PARENT_SHA)
    for label, relative, expected in (
        ("E03 signoff", "E03-two-aircraft-shared-spare-v1.0.0/cli-scope-signoff-2026-09-29.md", "dedf59901c805c7bbfd6c7421f02d0b051d0fbbc38c97819970988203e47c4e1"),
        ("E03 closure", "E03-two-aircraft-shared-spare-v1.0.0/runs/e03-v100-ssh-20260929-01/closure.json", "b200b18fbbed80dcc7ff9e9f4e2e1d7952734449b49a400a509d054090a9b7d6"),
        ("E02 signoff", "E02-zero-stock-local-backorder-v1.0.0/cli-scope-signoff-2026-09-29.md", "c28abcac8c3b8a55d0f58adf87ec3038555102d6b7bc2b35dc84ab9793e42ad6"),
        ("A03 signoff", "A03-two-aircraft-formation-v1.0.1/cli-scope-signoff-2026-09-29.md", "6c8d3998f20e216d0403b807866fcbe306f68ebc6f376693334435e808747b2b"),
    ):
        ck(label, sha(HERE.parent / relative) == expected)
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    ck("unique run identity", run.name == RUN_ID and invocation.get("run_id") == RUN_ID and closure.get("run_id") == RUN_ID and invocation.get("variant_id") == "E03.var01")
    ck("evidence schemas", invocation.get("schema") == "simlox-e03-var01-v010-native-candidate/ssh-cli-v1" and closure.get("schema") == "simlox-e03-var01-v010-native-closure/v1")
    ck("invocation source", invocation.get("input_sha256") == INPUT_SHA and invocation.get("parent_sha256") == PARENT_SHA)
    for key, filename in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"), ("runner_script_sha256", "run_native_ssh.ps1"), ("checker_sha256", "check_roundtrip.py"), ("diff_checker_sha256", "check_parent_diff.py"), ("validator_sha256", "validate_native_cli.py")):
        ck(f"source bound {filename}", invocation.get(key) == sha(HERE / filename))
    ck("pinned executable", invocation.get("simlox_exe_sha256") == EXE_SHA)
    ck("session zero SSH", invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") and "sshd.exe" in invocation.get("ssh_ancestor_names", []))
    gui = invocation.get("gui", {})
    ck("protected GUI", gui.get("pid") == 13340 and gui.get("session_id") == 1 and isinstance(gui.get("start_utc"), str) and bool(gui["start_utc"]))
    ck("native mutex", invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue")
    ck("closure invocation", closure.get("invocation_sha256") == sha(run / "invocation.json"))
    ck("closure successful", closure.get("error") is None)
    ck("source stable", closure.get("source_hashes_before") == closure.get("source_hashes_after") == invocation.get("source_hashes_before"))
    ck("raw inventory", set(closure.get("raw", {})) == RAW)
    for name, item in closure.get("raw", {}).items():
        path = run / name
        ck(f"raw seal {name}", path.is_file() and path.stat().st_size == item.get("bytes") and sha(path) == item.get("sha256"))
    steps = load(run / "steps.json")
    ck("step order", [s.get("name") for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport"])
    planned = invocation.get("planned_commands", [])
    native_steps = [s for s in steps if s.get("name") != "check_import_export"]
    ck("planned commands", len(planned) == len(native_steps) == 4 and all(planned[i].get("name") == native_steps[i].get("name") and planned[i].get("arguments") == native_steps[i].get("arguments") for i in range(4)))
    for step in steps:
        ck(f"step {step.get('name')}", step.get("status") == "completed" and step.get("exit_code") == 0 and step.get("gui_preserved") is True)
    roundtrip = load(run / "roundtrip-validation.json")
    ck("roundtrip checker", roundtrip.get("passed") is True and roundtrip.get("differences") == [] and len(roundtrip.get("populated_tables", [])) == 20)
    ck("business rows preserved", native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"])
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", calc)
    ck("conversion clean", conversion is not None and int(conversion[1]) == 0 and int(conversion[2]) == 1 and Counter(re.findall(r"\(warning #(\d+)\)", calc)) == Counter({"108": 1}))

    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    lines = log.splitlines()
    def matching(pattern: str) -> list[re.Match[str]]:
        return list(re.finditer(pattern, log, re.M))
    starts = matching(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission starting, duration: 2 : <TEACH-AIR-01,(\d+)>$")
    allocations = matching(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission allocates system: <TEACH-AIR-01,(\d+)>$")
    ck("one mission allocation and launch", len(starts) == len(allocations) == 1 and starts[0][2] == allocations[0][2] if starts and allocations else False)
    ck("two aircraft initially ready", len([line for line in lines if "systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in line]) >= 1)
    critical = matching(r"^Time: ([\d.]+) <TEACH-AIR-01,(\d+)> critical random failure added")
    failed_items = matching(r"^  subitem failed: <TEACH-LRU-01,0,(\d+)> connection path:")
    demands = matching(r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item demand arrives .*item requiring maintenance is <TEACH-LRU-01,0,(\d+)>$")
    issues = matching(r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock")
    if not critical or not failed_items or not demands:
        errors.append("INCONCLUSIVE: no qualifying critical installed LRU failure and replacement demand")
    ck("exactly one physical failure and demand", len(critical) == 1 and len(demands) == 1 and len(failed_items) == 2 and len({m[1] for m in failed_items}) == 1 and critical[0][2] == starts[0][2] if critical and starts else False)
    failed_id = demands[0][2] if demands else None
    ck("demand physical identity", failed_id is not None and all(m[1] == failed_id for m in failed_items))
    ck("opening spare uniquely issued", len(issues) == 1 and issues[0][2] == "0" and len([line for line in lines if "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>," in line]) == 1)
    arrivals = matching(r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,(\d+)>")
    ck("one local repaired-item arrival, no alternate supply", len(arrivals) == 1 and arrivals[0][2] == failed_id and not matching(r"Backorder added|Backorder removed|Transport") and len(issues) == 1)
    ck("one repair work chain", len(matching(r"^Time: [\d.]+  system SURP task \d+ on <TEACH-AIR-01,\d+> started$")) == 1 and len(matching(r"^Time: [\d.]+  item DIRP task \d+ on <TEACH-LRU-01,0,\d+> started$")) == 1)
    ck("one remove and fit", len(matching(r"^Time: [\d.]+  remove subitem subtask .* started$")) == 1 and len(matching(r"^Time: [\d.]+  remove subitem subtask .* completed$")) == 1 and len(matching(r"^Time: [\d.]+  fit subitem subtask .* starts performing, planned to last for 0\.333333 hours$")) == 1 and len(matching(r"^Time: [\d.]+  fit subitem subtask .* completed$")) == 1)
    ck("failed item four-hour repair", failed_id is not None and len(matching(rf"^Time: [\d.]+  direct repair subtask .* on <TEACH-LRU-01,0,{failed_id}> starts performing, planned to last for 4 hours$")) == 1 and len(matching(rf"^Time: [\d.]+  item DIRP task \d+ on <TEACH-LRU-01,0,{failed_id}> completed$")) == 1)
    ck("failed item restocked", failed_id is not None and len(matching(rf"^Time: [\d.]+ <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,{failed_id}> to stock")) == 1)
    ck("stock physical ledger", failed_id is not None and len([line for line in lines if "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:" in line]) == 1 and len([line for line in lines if f"Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,{failed_id}>," in line]) == 1)
    ck("one aborted mission outcome", len(matching(r"^Time: [\d.]+ <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission aborted:")) == 1 and len(matching(r"^Time: [\d.]+ <BASIC-MISSION,TEACH-UNIT,0,0,\d+> aborted mission completed:")) == 1 and not matching(r"mission success:"))
    ck("terminal aircraft ready", any("systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in line for line in lines[-30:]))

    result = report(run / "report-raw.json")
    summary = native.table_rows(result, "ResultSummary")
    system = native.table_rows(result, "SystemResults")
    stock = native.table_rows(result, "StockTotalResults")
    ck("one repetition and mission result", len(summary) == 1 and summary[0].get("NREP") == 1 and summary[0].get("MSUF") == 0)
    for title, rows in (("system", system), ("stock", stock)):
        ck(f"{title} 72 half-hour rows", len(rows) == 72 and all(row["STINT"] == i * .5 and row["ETINT"] == (i + 1) * .5 for i, row in enumerate(rows)))
    ck("one system failure and repair", sum(row.get("NFAIL", 0) for row in system) == 1 and sum(row.get("NREPT", 0) for row in system) == 1 and system[-1]["NSYRY"] == system[-1]["NSYA"] == 2)
    ck("one stock demand, no backorder", sum(row.get("NDF", 0) for row in stock) == 1 and all(row.get("NBO", 0) == 0 for row in stock))
    return {"schema": "simlox-e03-var01-v010-author-native-validation/v1", "variant_id": "E03.var01", "run_id": run.name, "passed": not errors, "checks": checks, "differences": errors, "observed_aircraft": critical[0][2] if critical else None, "observed_failed_physical_id": failed_id, "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "scope": "single_mission_one_observed_physical_demand_cli_candidate", "publication_state": "not_published"}


if __name__ == "__main__":
    answer = validate(Path(sys.argv[1]))
    print(json.dumps(answer, indent=2))
    sys.exit(0 if answer["passed"] else 1)

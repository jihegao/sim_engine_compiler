"""Read-only v0.1.2 replay correcting the v0.1.1 validator filename lookup."""
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

INPUT_SHA = "f9b1d2120de85307458dfddd92f69d7fa4bec9dd7bc5ee88c06c99b9cc338786"
PARENT_SHA = "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
       "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
       "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate(run: Path) -> dict:
    errors: list[str] = []
    checks = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            errors.append(label)

    ck("child input pin", sha(HERE / "native-input.json") == sha(run / "input.json") == INPUT_SHA)
    ck("accepted parent pin", sha(HERE.parent / "D01-installed-lru-direct-repair-v1.0.0/native-input.json") == PARENT_SHA)
    inv, closure = load(run / "invocation.json"), load(run / "closure.json")
    ck("run identity", inv.get("case_id") == "D01" and inv.get("variant_id") == "D01.var01" and
       inv.get("run_id") == run.name == "d01-var01-zero-v010-ssh-20261006-01")
    ck("pinned sources", inv.get("input_sha256") == INPUT_SHA and inv.get("parent_sha256") == PARENT_SHA and
       inv.get("simlox_exe_sha256") == EXE_SHA)
    for key, filename in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"),
                          ("checker_sha256", "check_roundtrip.py"), ("diff_checker_sha256", "check_parent_diff.py"),
                          ("validator_sha256", "validate_native_cli_v011.py"), ("runner_script_sha256", "run_native_ssh.ps1")):
        ck(f"bound {filename}", inv.get(key) == sha(HERE / filename))
    ck("SSH session and queue", inv.get("session_id") == 0 and inv.get("ssh_connection_present") and
       "sshd.exe" in inv.get("ssh_ancestor_names", []) and inv.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue")
    gui = inv.get("gui", {})
    ck("GUI identity", gui.get("pid") == 13340 and gui.get("session_id") == 1 and gui.get("start_utc"))
    ck("closure and stable sources", closure.get("invocation_sha256") == sha(run / "invocation.json") and
       closure.get("error") is None and closure.get("source_hashes_before") == closure.get("source_hashes_after") == inv.get("source_hashes_before"))
    ck("raw inventory", set(closure.get("raw", {})) == RAW)
    for name, seal in closure.get("raw", {}).items():
        path = run / name
        ck(f"raw {name}", path.is_file() and path.stat().st_size == seal.get("bytes") and sha(path) == seal.get("sha256"))
    steps = load(run / "steps.json")
    ck("step order", [s.get("name") for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport"])
    for step in steps:
        ck(f"step {step.get('name')}", step.get("status") == "completed" and step.get("exit_code") == 0 and step.get("gui_preserved") is True)
    rt = load(run / "roundtrip-validation.json")
    ck("roundtrip", rt.get("passed") is True and rt.get("differences") == [] and len(rt.get("populated_tables", [])) == 18 and
       native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"])
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    counts = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", calc)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", calc))
    ck("zero-error classified conversion", counts is not None and tuple(map(int, counts.groups())) == (0, 2, 0) and
       warnings == Counter({"108": 1, "2053": 1}) and "FRT is zero for: TEACH-LRU-01" in calc and
       not re.search(r"\(error #\d+\)", calc))
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    lines = log.splitlines()
    for index, start in enumerate((8, 20, 32)):
        ck(f"mission {index} starts", sum(line.startswith(f"Time: {start} ") and
           f"<BASIC-MISSION,TEACH-UNIT,0,0,{index}> mission starting, duration: 2" in line for line in lines) == 1)
        ck(f"mission {index} succeeds", sum(line.startswith(f"Time: {start+2} ") and
           f"<BASIC-MISSION,TEACH-UNIT,0,0,{index}> mission success:" in line for line in lines) == 1)
    lifecycle = Counter(re.findall(
        r"^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> "
        r"(mission created|mission starting|mission success|mission cancelled|mission aborted)",
        log, re.M))
    expected_lifecycle = Counter()
    for index, start in enumerate((8, 20, 32)):
        expected_lifecycle[(str(start-1), str(index), "mission created")] = 1
        expected_lifecycle[(str(start), str(index), "mission starting")] = 1
        expected_lifecycle[(str(start+2), str(index), "mission success")] = 1
    ck("exact three mission lifecycles", lifecycle == expected_lifecycle)
    ck("no abort, cancellation or extra ordered mission", not re.search(r"\b(?:abort\w*|cancel\w*|mission failed)\b", log, re.I) and
       len(re.findall(r"^Time: [0-9.]+ <TEACH-UNIT> mission ordered: BASIC-MISSION$", log, re.M)) == 3)
    ck("no failures or maintenance", not any(token in log.lower() for token in
       ("failure added", "mission aborted", "item demand arrives", "take replacement item", "item dirp task", "system surp task", "backorder")))
    ck("opening and terminal physical spare", log.count("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>,") >= 1 and
       "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0" not in log and
       "Put back replacement item" not in log)
    report = json.loads(native.remove_trailing_commas((run / "report-raw.json").read_bytes()))
    summary = native.table_rows(report, "ResultSummary")
    system = native.table_rows(report, "SystemResults")
    stock = native.table_rows(report, "StockTotalResults")
    ck("mission summary", len(summary) == 1 and summary[0].get("NREP") == 1 and abs(summary[0].get("MSUF", -1) - 1) < 1e-6)
    ck("aligned system bins", len(system) == 72 and all(row["STINT"] == i*.5 and row["ETINT"] == (i+1)*.5 for i,row in enumerate(system)))
    ck("aligned stock bins", len(stock) == 72 and all(row["STINT"] == i*.5 and row["ETINT"] == (i+1)*.5 for i,row in enumerate(stock)))
    ck("zero fault/repair counters", all(row.get(k, 0) == 0 for row in system for k in ("NFAIL", "NREPT", "NSYRP", "NDAM", "NPMT", "NSYPM")))
    ck("zero demand/backorder counters", all(row.get(k, 0) == 0 for row in stock for k in ("NDF", "NDD", "NDR", "NDP", "NBO")))
    ck("available aircraft all bins and terminal ready", bool(system) and all(row.get("NSYA") == 1 for row in system) and
       system[-1].get("NSYRY") == 1)
    flight_windows = ((8, 10), (20, 22), (32, 34))
    allocated_windows = ((7, 10), (19, 22), (31, 34))
    ck("every flight bin matches event timeline", len(system) == 72 and all(
        row.get("FTMO") == int(any(lo <= row["STINT"] < hi for lo, hi in flight_windows))
        for row in system))
    ck("every ready bin matches allocation timeline", len(system) == 72 and all(
        row.get("NSYRY") == int(not any(lo <= row["STINT"] < hi for lo, hi in allocated_windows))
        for row in system))
    ck("six flight hours", abs(sum(row.get("FTMO", 0) * (row["ETINT"] - row["STINT"]) for row in system) - 6) < 1e-6)
    ck("27 ready aircraft hours", abs(sum(row.get("NSYRY", 0) * (row["ETINT"] - row["STINT"]) for row in system) - 27) < 1e-6)
    return {"schema": "simlox-d01-var01-v012-author-native-validation/v1", "run_id": run.name,
            "passed": not errors, "checks": checks, "differences": errors, "scope": "matched_zero_frt_cli_candidate",
            "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "publication_state": "not_published"}


if __name__ == "__main__":
    answer = validate(Path(sys.argv[1]))
    print(json.dumps(answer, indent=2))
    sys.exit(0 if answer["passed"] else 1)

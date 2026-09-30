"""Author replay of twelve sealed RPROB=0.5 single-replication native runs."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
PARENT = HERE.parent / "C06-rprob-endpoints-v1.0.0" / "rprob-1-input.json"
OBSERVED = {1: "ND", 2: "DN", 3: "ND", 4: "DN", 5: "NN", 6: "DD", 7: "NN", 8: "ND", 9: "DN", 10: "NN", 11: "DD", 12: "NN"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(report: dict, name: str) -> tuple[list[str], list[list]]:
    t = next(t for t in report["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in t["columns"]], [r for instance in t["instances"] for r in instance["rows"]]


def check(seed: int) -> dict:
    variant = f"seed-{seed:02d}"
    run_id = f"c06-rprob-half-{variant}-20260930-01"
    run = HERE / "runs" / run_id
    problems: list[str] = []

    def demand(ok: bool, label: str) -> None:
        if not ok:
            problems.append(label)

    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    demand(sha(PARENT) == CONTRACT["parent_input_sha256"], "accepted parent source differs")
    demand(sha(HERE / f"{variant}-input.json") == sha(run / "input.json") == CONTRACT["input_sha256"][variant], "frozen input differs")
    demand(invocation["run_id"] == closure["run_id"] == run_id and invocation["variant"] == variant, "run identity differs")
    demand(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], "session-0 SSH provenance differs")
    demand(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "queue/GUI provenance differs")
    demand(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], "source drift/native closure error")
    for key, path in {"input": HERE / f"{variant}-input.json", "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
        demand(closure["source_hashes_before"][key] == sha(path), f"run-time source seal differs: {key}")
    demand(sha(run / "invocation.json") == closure["invocation_sha256"], "invocation seal differs")
    demand([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps), "native steps/GUI guard differ")
    for name, item in closure["raw"].items():
        path = run / name
        demand(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"raw seal differs: {name}")
    demand(json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"], "roundtrip checker failed")
    source, exported = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
    demand(len(source) == 20 and all(exported.get(name) == rows for name, rows in source.items()), "20 populated table roundtrip differs")
    warnings: set[str] = set()
    for name in ("import.log", "export.log", "run.log", "report-export.log"):
        text = (run / name).read_text(encoding="utf-8-sig", errors="replace")
        demand(not re.search(r"\(error\s+#\d+\)", text, re.I), f"conversion error: {name}")
        warnings.update(re.findall(r"warning\s+#(\d+)", text, re.I))
    demand(warnings == {"108", "126"}, "warning set differs")

    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    observed = []
    for aid in (0, 1):
        sid = f"TEACH-AIR-01,{aid}"
        pattern = rf"Time: 7\.5  subtask \d+ seqno 1 within system preparation task \d+ on <{sid}> resource availability test\n(.*?)(?=Time:)"
        match = re.search(pattern, log, re.S)
        demand(match is not None, f"resource availability test absent: {sid}")
        section = match.group(1) if match else ""
        failed_primary = "Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed" in section
        failed_alternate = "Availability test on  <P-ALT at <BASE-01,0>> request for: 1 failed" in section
        demand(failed_primary == failed_alternate, f"partial typed resource test: {sid}")
        needs = failed_primary and failed_alternate
        observed.append("D" if needs else "N")
        if needs:
            demand(not re.search(rf"subtask \d+ seqno 1 within system preparation task \d+ on <{sid}> starts performing", log), f"demanding aircraft performed work: {sid}")
            stop = "9" if OBSERVED[seed] in ("DN", "ND") else "8.66667"
            demand(re.search(rf"Time: {stop}  subtask \d+ seqno 1 within system preparation task \d+ on <{sid}> resource waiting stopped", log) is not None, f"demand wait cleanup differs: {sid}")
        else:
            demand(re.search(rf"Time: 7\.5  subtask \d+ seqno 1 within system preparation task \d+ on <{sid}> starts performing, planned to last for 0\.333333 hours", log) is not None, f"resource-free work absent: {sid}")
            demand(re.search(rf"Time: 7\.83333  subtask \d+ seqno 1 within system preparation task \d+ on <{sid}> completed", log) is not None, f"resource-free completion absent: {sid}")
    pattern = "".join(observed)
    demand(pattern == OBSERVED[seed], "observed per-aircraft demand pattern differs")
    demand(not re.search(r"<P-(?:CREW|ALT) at <BASE-01,0>> allocated to maintenance task: 1", log), "typed resource allocated despite zero capacity")
    expected_cancel = None if pattern == "NN" else (8.66667 if pattern == "DD" else 9)
    if pattern == "NN":
        demand("Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and "Time: 9 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log and "mission cancelled" not in log, "successful mission timeline differs")
    else:
        demand(f"Time: {expected_cancel} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled" in log and "mission starting" not in log, "cancelled mission timeline differs")
    demand("systems ready: 2 :" in log, "terminal two-ready event absent")

    report = parse_native(run / "report-raw.json")
    cols, rows = table(report, "ResultSummary")
    demand(len(rows) == 1 and rows[0][cols.index("NREP")] == 1 and rows[0][cols.index("MTMF")] == int(pattern == "NN"), "mission summary differs")
    cols, rows = table(report, "ResourceResultsTotal")
    demand(len(rows) == 1 and all(rows[0][cols.index(name)] == 0 for name in ("NR", "NRMO", "NRMA", "NRUM", "NRLA")), "resource total stock/use differs")
    expected_wait_total = {"NN": 0, "ND": 1.5 / 36, "DN": 1.5 / 36, "DD": (7 / 3) / 36}[pattern]
    demand(math.isclose(rows[0][cols.index("NRW")], expected_wait_total, abs_tol=1e-6), "resource total waiting differs")
    cols, rows = table(report, "ResourceResults")
    demand(len(rows) == 72 and all(row[cols.index(name)] == 0 for row in rows for name in ("NR", "NRMO", "NRMA", "NRUM")), "resource series stock/use differs")
    expected_bins = {"NN": [0, 0, 0], "ND": [1, 1, 1], "DN": [1, 1, 1], "DD": [2, 2, 2 / 3]}[pattern]
    demand(all(math.isclose(rows[i][cols.index("NRW")], value, abs_tol=1e-6) for i, value in zip((15, 16, 17), expected_bins)) and all(rows[i][cols.index("NRW")] == 0 for i in list(range(15)) + list(range(18, 72))), "resource waiting bins differ")
    cols, rows = table(report, "SystemResults")
    demand(len(rows) == 72 and rows[-1][cols.index("NSYRY")] == 2 and all(row[cols.index(name)] == 0 for row in rows for name in ("NFAIL", "NREPT")), "system/terminal ledger differs")
    demand(rows[16][cols.index("NSYMO")] == rows[17][cols.index("NSYMO")] == (2 if pattern == "NN" else 0), "mission operation bins differ")
    expected_prep = {"NN": [4 / 3, 0, 0], "ND": [5 / 3, 1, 1], "DN": [5 / 3, 1, 1], "DD": [2, 2, 2 / 3]}[pattern]
    demand(all(math.isclose(rows[i][cols.index("NSYMP")], value, abs_tol=1e-6) for i, value in zip((15, 16, 17), expected_prep)), "system preparation bins differ")
    cols, rows = table(report, "StockTotalResults")
    demand(len(rows) == 72 and all(row[cols.index(name)] == 0 for row in rows for name in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), "inventory ledger differs")
    return {"variant": variant, "seed": seed, "observed_pattern": pattern, "mission_outcome": "success" if pattern == "NN" else "cancelled", "cancellation_hour": expected_cancel, "passed": not problems, "issues": problems, "input_sha256": CONTRACT["input_sha256"][variant], "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "warning_numbers": sorted(warnings)}


if __name__ == "__main__":
    observations = [check(seed) for seed in OBSERVED]
    result = {"schema": "simlox-c06-rprob-half-matrix-author-validation/v1", "passed": all(item["passed"] for item in observations), "runs": observations, "pattern_counts": {pattern: sum(item["observed_pattern"] == pattern for item in observations) for pattern in ("NN", "ND", "DN", "DD")}, "scope": "twelve fixed-seed observed demand patterns at RPROB 0.5; no probability-law or independence claim"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)

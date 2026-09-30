"""Author replay of the frozen C06 primary/alternative zero-capacity run."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUN_ID = "c06-both-zero-20260930-01"
RUN = HERE / "runs" / RUN_ID
INPUT_SHA = "05c6da90b5c8e509ea57132026d781822e1399d7693f469ec08c307bff9342cc"
PARENT_SHA = "42aeabcf2f7ca79efc568c515bfd5989715cdc0270f59acaad3bfe46c974bd1f"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(report: dict, name: str) -> tuple[list[str], list[list]]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in table["columns"]], [r for instance in table["instances"] for r in instance["rows"]]


def check() -> dict:
    issues: list[str] = []

    def demand(condition: bool, label: str) -> None:
        if not condition:
            issues.append(label)

    invocation = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    demand(sha(HERE / "both-zero-input.json") == sha(RUN / "input.json") == INPUT_SHA == contract["input_sha256"], "frozen input differs")
    demand(sha(HERE.parent / "C06-alternative-resource-v1.0.0" / "primary-0-artf-2-input.json") == PARENT_SHA == contract["parent_input_sha256"], "accepted parent differs")
    demand(invocation["run_id"] == closure["run_id"] == RUN_ID and invocation["variant"] == "both-zero", "run identity differs")
    demand(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], "session-0 SSH provenance differs")
    demand(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "queue or GUI identity differs")
    demand(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], "native source drift or error")
    for key, filename in {"input": "both-zero-input.json", "parent": None, "contract": "contract.json", "builder": "build.py", "checker": "check_roundtrip.py", "runner_script": "run_native_ssh.ps1"}.items():
        if filename is not None:
            demand(closure["source_hashes_before"][key] == sha(HERE / filename), f"{key} run-time source seal differs")
    demand(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal differs")
    demand([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "native step sequence differs")
    demand(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "native step or GUI guard failed")
    for name, item in closure["raw"].items():
        path = RUN / name
        demand(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"raw seal differs: {name}")
    demand(json.loads((RUN / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"], "roundtrip checker failed")
    source = populated(parse_native(RUN / "input.json"))
    exported = populated(parse_native(RUN / "roundtrip-raw.json"))
    demand(len(source) == 20 and all(exported.get(name) == table for name, table in source.items()), "20 source table roundtrip differs")
    warnings: set[str] = set()
    for name in ("import.log", "export.log", "run.log", "report-export.log"):
        log = (RUN / name).read_text(encoding="utf-8-sig", errors="replace")
        demand(not re.search(r"\(error\s+#\d+\)", log, re.I), f"conversion error in {name}")
        warnings.update(re.findall(r"warning\s+#(\d+)", log, re.I))
    demand(warnings == {"108", "126"}, "warning set differs")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    for aircraft in (0, 1):
        sid = f"TEACH-AIR-01,{aircraft}"
        demand(len(re.findall(rf"Time: 7\.5 <{sid}> preparation started", log)) == 1, f"preparation start differs: {sid}")
        demand(len(re.findall(rf"Time: 7\.5  subtask \d+ seqno 1 within system preparation task \d+ on <{sid}> requests resources", log)) == 1, f"resource request differs: {sid}")
        demand(len(re.findall(rf"Time: 8\.66667  subtask \d+ seqno 1 within system preparation task \d+ on <{sid}> resource waiting stopped", log)) == 1, f"resource wait stop differs: {sid}")
        demand(len(re.findall(rf"Time: 8\.66667 <{sid}> turnround ended", log)) == 1, f"turnaround differs: {sid}")
    demand(len(re.findall(r"Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed", log)) == 2, "primary availability attempts differ")
    demand(len(re.findall(r"Availability test on  <P-ALT at <BASE-01,0>> request for: 1 failed", log)) == 2, "alternative availability attempts differ")
    demand(not re.search(r"allocated to maintenance task:|starts performing|subtask .* completed|mission starting|mission success", log), "unexpected booking, work or mission success")
    demand(len(re.findall(r"Time: 8\.66667 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled", log)) == 1, "mission cancellation differs")
    demand("systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log, "terminal readiness marker absent")
    report = parse_native(RUN / "report-raw.json")
    cols, rr = rows(report, "ResultSummary")
    demand(len(rr) == 1 and rr[0][cols.index("MTMF")] == 0 and rr[0][cols.index("NREP")] == 1, "mission summary differs")
    cols, rr = rows(report, "ResourceResultsTotal")
    demand(len(rr) == 1 and rr[0][cols.index("NR")] == 0 and all(rr[0][cols.index(name)] == 0 for name in ("NRMO", "NRMA", "NRUM", "NRLA")) and rr[0][cols.index("NRW")] > 0, "resource total or waiting measure differs")
    cols, rr = rows(report, "ResourceResults")
    demand(len(rr) == 72 and all(row[cols.index("NR")] == 0 and row[cols.index("NRMO")] == 0 for row in rr), "resource series differs")
    demand([rr[i][cols.index("NRW")] for i in (15, 16)] == [2, 2] and math.isclose(rr[17][cols.index("NRW")], 2 / 3, abs_tol=1e-6) and all(rr[i][cols.index("NRW")] == 0 for i in list(range(15)) + list(range(18, 72))), "resource waiting bins differ")
    cols, rr = rows(report, "SystemResults")
    demand(len(rr) == 72 and rr[-1][cols.index("NSYRY")] == 2 and all(row[cols.index(name)] == 0 for row in rr for name in ("NFAIL", "NREPT", "NSYMO")), "system series or terminal state differs")
    demand(rr[15][cols.index("NSYMP")] == 2 and rr[16][cols.index("NSYMP")] == 2 and math.isclose(rr[17][cols.index("NSYMP")], 2 / 3, abs_tol=1e-6) and rr[18][cols.index("NSYRY")] == 2, "preparation wait or return bins differ")
    cols, rr = rows(report, "StockTotalResults")
    demand(len(rr) == 72 and all(row[cols.index(name)] == 0 for row in rr for name in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), "inventory movement differs")
    return {"schema": "simlox-c06-both-resource-zero-author-validation/v1", "passed": not issues, "issues": issues, "run_id": RUN_ID, "input_sha256": INPUT_SHA, "exact_diff_sha256": sha(HERE / "exact-diff.json"), "closure_sha256": sha(RUN / "closure.json"), "model_log_sha256": sha(RUN / "model.log"), "report_sha256": sha(RUN / "report-raw.json"), "warning_numbers": sorted(warnings), "observed_cancellation_hour": 8.66667, "scope": "fixed all-zero preparation resource boundary with cancellation and cleanup"}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)

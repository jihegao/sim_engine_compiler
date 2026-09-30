"""Author replay of fixed RPROB=0/1 endpoint observations."""

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
PARENT = HERE.parent / "C06-both-resource-zero-v1.0.0" / "both-zero-input.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(report: dict, name: str) -> tuple[list[str], list[list]]:
    t = next(t for t in report["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in t["columns"]], [r for instance in t["instances"] for r in instance["rows"]]


def check(variant: str) -> dict:
    issues: list[str] = []

    def demand(condition: bool, label: str) -> None:
        if not condition:
            issues.append(label)

    run_id = f"c06-{variant}-20260930-01"
    run = HERE / "runs" / run_id
    inv = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    cl = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    demand(sha(PARENT) == CONTRACT["parent_input_sha256"], "accepted parent SHA differs")
    demand(sha(HERE / f"{variant}-input.json") == sha(run / "input.json") == CONTRACT["input_sha256"][variant], "frozen input differs")
    demand(inv["run_id"] == cl["run_id"] == run_id and inv["variant"] == variant, "run identity differs")
    demand(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "SSH provenance differs")
    demand(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "queue/GUI provenance differs")
    demand(cl["error"] is None and cl["source_hashes_before"] == cl["source_hashes_after"], "native source drift/error")
    for key, path in {"input": HERE / f"{variant}-input.json", "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
        demand(cl["source_hashes_before"][key] == sha(path), f"runtime {key} source seal differs")
    demand(cl["invocation_sha256"] == sha(run / "invocation.json"), "invocation seal differs")
    demand([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "native step/GUI guard differs")
    for name, item in cl["raw"].items():
        path = run / name
        demand(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"raw seal differs: {name}")
    demand(json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"], "roundtrip checker failed")
    source = populated(parse_native(run / "input.json"))
    exported = populated(parse_native(run / "roundtrip-raw.json"))
    demand(len(source) == 20 and all(exported.get(name) == row for name, row in source.items()), "20 populated source table roundtrip differs")
    warnings: set[str] = set()
    for name in ("import.log", "export.log", "run.log", "report-export.log"):
        text = (run / name).read_text(encoding="utf-8-sig", errors="replace")
        demand(not re.search(r"\(error\s+#\d+\)", text, re.I), f"conversion error in {name}")
        warnings.update(re.findall(r"warning\s+#(\d+)", text, re.I))
    demand(warnings == {"108", "126"}, "warning set differs")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    for aircraft in (0, 1):
        sid = f"TEACH-AIR-01,{aircraft}"
        demand(len(re.findall(rf"Time: 7\.5 <{sid}> preparation started", log)) == 1, f"preparation start differs: {sid}")
        demand(len(re.findall(rf"Time: 7\.5  subtask \d+ seqno 1 within system preparation task \d+ on <{sid}> resource availability test", log)) == 1, f"resource test differs: {sid}")
    demand(not re.search(r"<P-(?:CREW|ALT) at <BASE-01,0>> allocated to maintenance task: 1", log), "typed resource was allocated")
    report = parse_native(run / "report-raw.json")
    cols, rr = table(report, "ResultSummary")
    demand(len(rr) == 1 and rr[0][cols.index("NREP")] == 1 and rr[0][cols.index("MTMF")] == (1 if variant == "rprob-0" else 0), "mission summary differs")
    cols, rr = table(report, "ResourceResultsTotal")
    demand(len(rr) == 1 and all(rr[0][cols.index(name)] == 0 for name in ("NR", "NRMO", "NRMA", "NRUM", "NRLA")), "resource stock/use differs")
    demand((rr[0][cols.index("NRW")] == 0) if variant == "rprob-0" else rr[0][cols.index("NRW")] > 0, "total resource waiting differs")
    cols, resource = table(report, "ResourceResults")
    demand(len(resource) == 72 and all(row[cols.index(name)] == 0 for row in resource for name in ("NR", "NRMO", "NRMA", "NRUM")), "resource series stock/use differs")
    cols, systems = table(report, "SystemResults")
    demand(len(systems) == 72 and systems[-1][cols.index("NSYRY")] == 2 and all(row[cols.index(name)] == 0 for row in systems for name in ("NFAIL", "NREPT")), "system series or terminal state differs")
    cols, stock = table(report, "StockTotalResults")
    demand(len(stock) == 72 and all(row[cols.index(name)] == 0 for row in stock for name in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), "stock ledger differs")
    if variant == "rprob-0":
        demand(not re.search(r"Availability test on  <P-(?:CREW|ALT) at <BASE-01,0>> request for: 1 failed", log), "resource demand unexpectedly sampled")
        demand(len(re.findall(r"starts performing, planned to last for 0\.333333 hours", log)) == 2 and len(re.findall(r"Time: 7\.83333  subtask \d+ seqno 1 within system preparation task \d+ on <TEACH-AIR-01,[01]> completed", log)) == 2, "resource-free preparation timing differs")
        demand("Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and "Time: 9 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log and "mission cancelled" not in log, "mission success timing differs")
        demand(all(row[table(report, "ResourceResults")[0].index("NRW")] == 0 for row in resource), "resource waiting unexpectedly reported")
        cols, systems = table(report, "SystemResults")
        demand(math.isclose(systems[15][cols.index("NSYMP")], 4 / 3, abs_tol=1e-6) and systems[16][cols.index("NSYMO")] == 2 and systems[17][cols.index("NSYMO")] == 2, "work and mission bins differ")
    else:
        demand(len(re.findall(r"Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed", log)) == 2 and len(re.findall(r"Availability test on  <P-ALT at <BASE-01,0>> request for: 1 failed", log)) == 2, "resource requirement/availability differs")
        demand("Time: 8.66667 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled" in log and len(re.findall(r"Time: 8\.66667  subtask \d+ seqno 1 within system preparation task \d+ on <TEACH-AIR-01,[01]> resource waiting stopped", log)) == 2, "cancellation/wait cleanup differs")
        demand("starts performing" not in log and "mission starting" not in log, "unexpected work or mission start")
        cols, resource = table(report, "ResourceResults")
        demand([resource[i][cols.index("NRW")] for i in (15, 16)] == [2, 2] and math.isclose(resource[17][cols.index("NRW")], 2 / 3, abs_tol=1e-6) and all(resource[i][cols.index("NRW")] == 0 for i in list(range(15)) + list(range(18, 72))), "waiting resource bins differ")
        cols, systems = table(report, "SystemResults")
        demand(systems[15][cols.index("NSYMP")] == systems[16][cols.index("NSYMP")] == 2 and math.isclose(systems[17][cols.index("NSYMP")], 2 / 3, abs_tol=1e-6), "waiting system bins differ")
    return {"variant": variant, "passed": not issues, "issues": issues, "input_sha256": CONTRACT["input_sha256"][variant], "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "warning_numbers": sorted(warnings)}


if __name__ == "__main__":
    variants = [check(v) for v in ("rprob-0", "rprob-1")]
    result = {"schema": "simlox-c06-rprob-endpoints-author-validation/v1", "passed": all(v["passed"] for v in variants), "variants": variants, "scope": "RPROB zero/one endpoints with both resource types at zero; intermediate values unverified"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)

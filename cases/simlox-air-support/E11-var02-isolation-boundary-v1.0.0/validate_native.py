"""Author replay of two E11.var02 boundary arms and accepted after control."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_IDS = {"before": "e11-var02-before-v100-ssh-20261003-01",
           "at": "e11-var02-at-v100-ssh-20261003-01"}
CLOSURES = {"before": "42c7fdc49d52283ef037484bc1efc2f829669ec08d66e91ac689eaf1ea077888",
            "at": "d974cd9dc97a695cf5b09af07b6b5982d41e71e0b202411fafc375dc3c6dc8e2"}
RAW_NAMES = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
             "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
             "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: Path) -> dict:
    return {t["name"]: t for t in parse_native(path)["report"]["tables"]}


def rows(table: dict) -> list[dict]:
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for inst in table["instances"] for row in inst["rows"]]


def main() -> int:
    failures: list[str] = []
    checks = 0

    def ck(label: str, result: bool) -> None:
        nonlocal checks
        checks += 1
        if not result:
            failures.append(label)

    contract, diff = (read(HERE / n) for n in ("contract.json", "exact-diff.json"))
    parent = ROOT / contract["accepted_parent"]["package"]
    parent_run = parent / "runs" / contract["accepted_parent"]["run_id"]
    ck("frozen contract and diff", contract["case_id"] == "E11" and contract["variant_id"] == "E11.var02" and contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    ck("accepted parent pins", sha(parent / "native-input.json") == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"] and sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"] and sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"])
    ck("source fingerprint", all(sha(HERE / f"native-input-{a}.json") == contract["arms"][a]["native_input_sha256"] == diff["arms"][a]["source_sha256"] for a in RUN_IDS))
    ck("policy-only source delta", diff["unchanged_parent_tables"] == 30 and all([(x["table"], x["row"], x["column"]) for x in diff["arms"][a]["changes"]] == [("ProblemDescription", 0, "PDESC"), ("TransportPolicyProfile", 0, "DURN"), ("TransportPolicyProfile", 1, "STIM"), ("TransportPolicyProfile", 1, "DURN")] for a in RUN_IDS))
    reports, logs = {}, {}
    for arm, run_id in RUN_IDS.items():
        run = HERE / "runs" / run_id
        ck(f"{arm} closure seal", sha(run / "closure.json") == CLOSURES[arm])
        inv, closure, steps = (read(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm} native identity", inv["case_id"] == "E11" and inv["variant_id"] == "E11.var02" and inv["arm"] == closure["arm"] == arm and inv["run_id"] == closure["run_id"] == run_id)
        ck(f"{arm} guarded SSH GUI queue", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
        ck(f"{arm} source stable", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
        pins = inv["source_hashes_before"]
        ck(f"{arm} local source pins", all(pins[key] == sha(HERE / name) for key, name in (("before_input", "native-input-before.json"), ("at_input", "native-input-at.json"), ("contract", "contract.json"), ("exact_diff", "exact-diff.json"), ("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1"))))
        ck(f"{arm} parent/native pins", pins["parent"] == contract["accepted_parent"]["input_sha256"] and pins["parent_closure"] == contract["accepted_parent"]["native_closure_sha256"] and pins["parent_index"] == contract["accepted_parent"]["evidence_index_sha256"] and pins["simlox_exe"] == contract["source"]["simlox_exe_sha256"] and pins["manual"] == contract["source"]["manual_pdf_sha256"] and pins["dictionary"] == contract["source"]["dictionary_sha256"])
        ck(f"{arm} five guarded steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
        ck(f"{arm} raw set", set(closure["raw"]) == RAW_NAMES)
        for name, seal in closure["raw"].items():
            ck(f"{arm} raw {name}", (run / name).stat().st_size == seal["bytes"] > 4 and sha(run / name) == seal["sha256"])
        before, after = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{arm} 22-table roundtrip", sha(run / "input.json") == contract["arms"][arm]["native_input_sha256"] and read(run / "roundtrip-validation.json")["passed"] is True and len(before) == 22 and all(after.get(n) == t for n, t in before.items()))
        conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} conversion", "Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in conversion and Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1, "2076": 1, "2077": 1}) and "Starting simulation..." in conversion and "Saving results ..." in conversion)
        ck(f"{arm} native output", all((run / n).stat().st_size > 1000 for n in ("model.sxo", "model.log", "report-raw.json")))
        reports[arm] = report(run / "report-raw.json")
        logs[arm] = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    reports["after"] = report(parent_run / "report-raw.json")
    for arm, rep in reports.items():
        ck(f"{arm} report tables", set(rep) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        sys_rows, stock_rows = rows(rep["SystemResults"]), rows(rep["StockTotalResults"])
        ck(f"{arm} 72 aligned bins", len(sys_rows) == len(stock_rows) == 72 and all(sys_rows[i]["STINT"] == stock_rows[i]["STINT"] == i / 2 and sys_rows[i]["ETINT"] == stock_rows[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
        ck(f"{arm} one fault repair demand", sum(r["NFAIL"] or 0 for r in sys_rows) == sum(r["NREPT"] or 0 for r in sys_rows) == sum(r["NDF"] or 0 for r in stock_rows) == 1)
        ck(f"{arm} terminal", sys_rows[-1]["NSYRY"] == 1 and stock_rows[-1]["NBO"] == 0)
    ck("summary parity", reports["before"]["ResultSummary"] == reports["at"]["ResultSummary"] == reports["after"]["ResultSummary"] and abs(rows(reports["at"]["ResultSummary"])[0]["MSUF"] - 2 / 3) < 1e-5)
    ck("before/at aggregate parity", all(reports["before"][n] == reports["at"][n] for n in ("ResultSummary", "SystemResults", "StockTotalResults")))
    bsys, bst = rows(reports["before"]["SystemResults"]), rows(reports["before"]["StockTotalResults"])
    asys, ast = rows(reports["after"]["SystemResults"]), rows(reports["after"]["StockTotalResults"])
    ck("bounded report differences", {i for i in range(72) if bsys[i] != asys[i]} == {20, 21, 22} and {i for i in range(72) if bst[i] != ast[i]} == {20, 21})
    ck("zero versus one hour backorder", sum(r["NBO"] or 0 for r in bst) == 0 and abs(sum(r["NBO"] or 0 for r in ast) / 2 - 1) < 1e-6)
    ck("five sixths availability gain", abs((sum(r["NSYA"] or 0 for r in bsys) - sum(r["NSYA"] or 0 for r in asys)) / 2 - 5 / 6) < 1e-5)
    for arm, e in logs.items():
        ck(f"{arm} same first fault and demand", "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in e and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Item demand arrives" in e and "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives" in e)
        ck(f"{arm} ID0 h10 delivery", "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in e and "Time: 10  transport task 2 starts with 1 items/systems, transport time: 0" in e and "Time: 10  transport task 2 arrives with 1 items/systems" in e and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 0" in e)
        ck(f"{arm} h10.5 ready and missions", "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready" in e and e.count("mission aborted:") == 1 and e.count("mission success:") == 2)
        ck(f"{arm} physical task closure", e.count("starts with 1 items/systems, transport time: 0") == e.count("arrives with 1 items/systems") == 2)
        ck(f"{arm} no resource allocation", "requests resources: no resources needed" in e and "allocated to maintenance task" not in e)
    before_e, at_e = logs["before"], logs["at"]
    ck("before h10.1667 upward", "Time: 10.1667  transport task 3 starts with 1 items/systems, transport time: 0" in before_e and "Time: 10.1667 <TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,1>" in before_e and "Time: 11.1667 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in before_e)
    ck("at h10 outbound then delayed return", "Time: 10.1667  transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> attached to  scheduled transport task 0" in at_e and "Time: 12  scheduled transport task 0 starts with 1 items/systems, transport time: 0" in at_e and "Time: 12 <TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,1>" in at_e and "Time: 13 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in at_e)
    ck("at zero-payload downward cancel", "Time: 12  scheduled transport task 1 cancelled with 0 items/systems" in at_e)
    result = {"schema": "simlox-e11-var02-isolation-boundary-v100-author-validation/v1", "passed": not failures,
              "checks": checks, "differences": failures, "scope": "bounded_native_cli_replay",
              "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

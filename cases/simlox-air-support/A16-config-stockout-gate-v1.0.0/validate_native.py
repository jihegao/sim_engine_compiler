"""Author replay of the sealed A16 B-configuration stockout control."""
import hashlib
import json
from pathlib import Path

from check_roundtrip import native_json, populated

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "A16-two-config-reconfiguration-v1.0.0"
RUN = HERE / "runs" / "a16-config-stockout-v100-20261001-01"
OUT = HERE / "author-validation-2026-10-01.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(table):
    columns = [column["name"] for column in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def main():
    checks = []

    def need(ok, label):
        if not ok:
            raise AssertionError(label)
        checks.append(label)

    contract = native_json(HERE / "contract.json")
    source = HERE / "native-input.json"
    need(sha(BASE / "native-input.json") == contract["parent_sha256"], "baseline parent frozen")
    need(sha(source) == sha(RUN / "input.json") == contract["input_sha256"], "stockout input frozen")
    before = populated(native_json(BASE / "native-input.json"))
    after = populated(native_json(source))
    need({name for name in before if before[name] != after[name]} == {"ProblemDescription", "StockAllocation"}, "only two business tables change")
    stock_rows = rows(next(t for t in native_json(source)["model"]["tables"] if t["name"] == "StockAllocation"))
    need([(r["IID"], r["STSIZ"]) for r in stock_rows] == [("TEACH-LRU-01", 1), ("TEACH-LRU-A", 1), ("TEACH-LRU-B", 0)], "only B stock starts empty")
    closure, invocation = native_json(RUN / "closure.json"), native_json(RUN / "invocation.json")
    need(closure["error"] is None and closure["invocation_sha256"] == sha(RUN / "invocation.json"), "sealed invocation")
    need(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stable through run")
    need(all((RUN / name).is_file() and (RUN / name).stat().st_size == meta["bytes"] and sha(RUN / name) == meta["sha256"] for name, meta in closure["raw"].items()), "all raw hashes and lengths")
    need(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "SSH mutex and preserved GUI identity")
    steps = native_json(RUN / "steps.json")
    need([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps), "five successful guarded steps")
    exported = populated(native_json(RUN / "roundtrip-raw.json"))
    need(len(after) == 21 and all(exported.get(name) == value for name, value in after.items()) and native_json(RUN / "roundtrip-validation.json")["passed"], "exact 21-table native roundtrip")
    need("Input conversion completed. Errors: 0" in (RUN / "run.log").read_text(encoding="utf-8-sig"), "zero conversion errors")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    need("Time: 7 <TEACH-LRU-A,0,BASE-01,0> Reconfiguration item demand arrives" in log and "Time: 7 <TEACH-AIR-01,0> reconfig started" in log and "Time: 8 <CONF-A-MISSION," in log and "mission starting, duration: 2 : <TEACH-CONF-A,0>" in log, "A booking, fit and launch retained")
    need("Time: 10 <CONF-A-MISSION," in log and "Time: 10 <CONF-A-MISSION,TEACH-UNIT,0,0,0> mission success:" in log, "A mission succeeds")
    need("Time: 19 <CONF-B-MISSION,TEACH-UNIT,0,0,1> mission waiting:  timeout at 20.3333" in log and "Time: 20.3333 <CONF-B-MISSION,TEACH-UNIT,0,0,1> mission cancelled:" in log, "B mission waits and cancels")
    need("TEACH-LRU-B,0,BASE-01,0> Reconfiguration item demand arrives" not in log and "Take replacement item <TEACH-LRU-B" not in log and "reconfig started, mission: <CONF-B-MISSION" not in log and "mission starting, duration: 2 : <TEACH-CONF-B,0>" not in log, "no B booking, stock draw, work or launch")
    need("Time: 31 <TEACH-CONF-A,0> reconfig started, mission: <BASE-MISSION" in log and "Time: 31.1667 <TEACH-LRU-A,0,BASE-01,0> Put back replacement item" in log and "Time: 32 <BASE-MISSION," in log and "mission starting, duration: 2 : <TEACH-AIR-01,0>" in log and "Time: 34 <BASE-MISSION,TEACH-UNIT,0,0,2> mission success:" in log, "A-to-base removal and third mission success")
    for item, levels in (("A", [1, 0, 1]), ("B", [0])):
        observed = [int(line.split("Level: ")[1].split()[0]) for line in log.splitlines() if f"Stock at: <TEACH-LRU-{item},0,BASE-01,0> Level: " in line]
        need(observed == levels, f"{item} stock conservation")
    report = {table["name"]: table for table in native_json(RUN / "report-raw.json")["report"]["tables"]}
    system, stock, summary = rows(report["SystemResults"]), rows(report["StockTotalResults"]), rows(report["ResultSummary"])[0]
    need(len(system) == len(stock) == 72 and summary["RTIUP"] == 36, "72 half-hour report bins")
    need([(r["STINT"], r["NRCFG"]) for r in system if r["NRCFG"]] == [(7, 1), (31, 1)], "only A-fit and A-removal reported")
    need([(r["STINT"], r["NDR"]) for r in stock if r["NDR"]] == [(7, 1)] and sum(r["NBO"] for r in stock) == 0, "one stock draw; no native backorder event")
    need(abs(summary["MSUF"] - 2 / 3) < 1e-6 and system[-1]["NSYRY"] == 1, "two successes, one cancellation, terminal ready")
    result = {"schema": "simlox-a16-stockout-author-validation/v1", "passed": True, "decision": "GO_bounded_CBSID_stock_booking_gate", "check_count": len(checks), "checks": checks, "limits": contract["limits"] + ["No B backorder event is observed; the evidence is waiting and cancellation before B item demand or reconfiguration start."]}
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "checks": len(checks), "sha256": sha(OUT)}))


if __name__ == "__main__":
    main()

"""Author replay of the sealed A16 base-to-A-to-B-to-base native run."""
import hashlib
import json
from pathlib import Path

from check_roundtrip import native_json, populated

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "a16-two-config-v100-20261001-01"
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
    closure, invocation = native_json(RUN / "closure.json"), native_json(RUN / "invocation.json")
    source = HERE / "native-input.json"
    need(sha(source) == sha(RUN / "input.json") == contract["input_sha256"], "frozen input and copied run source")
    need(closure["error"] is None and closure["invocation_sha256"] == sha(RUN / "invocation.json"), "sealed invocation")
    need(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stable through run")
    need(all((RUN / name).is_file() and (RUN / name).stat().st_size == meta["bytes"] and sha(RUN / name) == meta["sha256"] for name, meta in closure["raw"].items()), "all raw hashes and lengths")
    need(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "SSH mutex and preserved GUI identity")
    steps = native_json(RUN / "steps.json")
    need([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps), "five successful guarded steps")
    source_tables, export_tables = populated(native_json(source)), populated(native_json(RUN / "roundtrip-raw.json"))
    need(len(source_tables) == 21 and all(export_tables.get(name) == value for name, value in source_tables.items()) and native_json(RUN / "roundtrip-validation.json")["passed"], "exact 21-table native roundtrip")
    need("Input conversion completed. Errors: 0" in (RUN / "run.log").read_text(encoding="utf-8-sig"), "zero conversion errors")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    for hour, before, mission, after in ((7, "TEACH-AIR-01", "CONF-A-MISSION", "TEACH-CONF-A"), (19, "TEACH-CONF-A", "CONF-B-MISSION", "TEACH-CONF-B"), (31, "TEACH-CONF-B", "BASE-MISSION", "TEACH-AIR-01")):
        need(f"Time: {hour} <{before},0> reconfig started, mission: <{mission}," in log, f"reconfiguration starts at {hour}")
        need(f"Time: {hour+1} <{mission}," in log and f"mission starting, duration: 2 : <{after},0>" in log, f"requested configuration launches at {hour+1}")
        need(f"Time: {hour+3} <{mission}," in log and "mission success:" in log.split(f"Time: {hour+3} <{mission},", 1)[1].splitlines()[0], f"mission succeeds at {hour+3}")
    for hour, item in ((7, "A"), (19, "B")):
        demand = f"Time: {hour} <TEACH-LRU-{item},0,BASE-01,0> Reconfiguration item demand arrives"
        start = f"Time: {hour} <{'TEACH-AIR-01' if hour == 7 else 'TEACH-CONF-A'},0> reconfig started"
        need(log.index(demand) < log.index(start), f"{item} item booked before work at {hour}")
        need(f"Time: {hour} <TEACH-LRU-{item},0,BASE-01,0> Take replacement item" in log, f"{item} spare physically drawn")
    for hour, item in (("19.1667", "A"), ("31.1667", "B")):
        need(f"Time: {hour} <TEACH-LRU-{item},0,BASE-01,0> Put back replacement item" in log, f"{item} item returned")
    need("Time: 19  system reconfig remove task" in log and "Time: 19  system reconfig fit task" in log and "Time: 19.1667  system reconfig remove task" in log and "Time: 19.3333  system reconfig fit task" in log, "parallel remove and fit with 10/20-minute completion")
    for item, levels in (("A", [1, 0, 1]), ("B", [1, 0, 1])):
        observed = [int(line.split("Level: ")[1].split()[0]) for line in log.splitlines() if f"Stock at: <TEACH-LRU-{item},0,BASE-01,0> Level: " in line]
        need(observed == levels, f"{item} stock conservation")
    report = {table["name"]: table for table in native_json(RUN / "report-raw.json")["report"]["tables"]}
    system, stock, summary = rows(report["SystemResults"]), rows(report["StockTotalResults"]), rows(report["ResultSummary"])[0]
    need(len(system) == len(stock) == 72 and summary["RTIUP"] == 36, "72 half-hour report bins")
    need([(r["STINT"], r["NRCFG"]) for r in system if r["NRCFG"]] == [(7, 1), (19, 1), (31, 1)], "three reported configuration intervals")
    need([(r["STINT"], r["NDR"]) for r in stock if r["NDR"]] == [(7, 1), (19, 1)] and sum(r["NBO"] for r in stock) == 0, "two stock demands and no backorders")
    need(all(summary[key] == 1 for key in ("MTMF", "MSTF", "MSUF", "STMF")) and system[-1]["NSYRY"] == 1, "three successes and one terminal ready aircraft")
    result = {"schema": "simlox-a16-two-config-author-validation/v1", "passed": True, "decision": "GO_bounded_CBSID_reconfiguration", "check_count": len(checks), "checks": checks, "limits": contract["limits"]}
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "checks": len(checks), "sha256": sha(OUT)}))


if __name__ == "__main__":
    main()

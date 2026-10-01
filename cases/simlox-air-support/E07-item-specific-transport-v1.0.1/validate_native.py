"""Author replay of the sealed E07 item-specific route against accepted E04."""
import hashlib
import json
from pathlib import Path

from check_roundtrip import native_json, populated

HERE = Path(__file__).resolve().parent
AIR = HERE.parent
RUN = HERE / "runs" / "e07-item-route-v101-20261001-01"
CONTROL = AIR / "E04-upstream-transport-fast-v1.0.0" / "runs" / "e04-fast-v100-ssh-20260929-01"
OUT = HERE / "author-validation-2026-10-01.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(table):
    columns = [x["name"] for x in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def report(run):
    tables = {x["name"]: x for x in native_json(run / "report-raw.json")["report"]["tables"]}
    return {name: records(table) for name, table in tables.items()}


def main():
    checks = []

    def need(condition, label):
        if not condition:
            raise AssertionError(label)
        checks.append(label)

    contract = native_json(HERE / "contract.json")
    parent = AIR / contract["parent_case"] / "native-input.json"
    source = HERE / "native-input.json"
    need(sha(parent) == contract["parent_sha256"] and sha(source) == contract["input_sha256"] == sha(RUN / "input.json"), "accepted parent and frozen child")
    need(sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) == contract["manual_pdf_sha256"] and sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")) == contract["table_dictionary_sha256"], "installed manual and dictionary")
    parent_tables = {t["name"]: t for t in native_json(parent)["model"]["tables"]}
    child_tables = {t["name"]: t for t in native_json(source)["model"]["tables"]}
    need({name for name in parent_tables if parent_tables[name] != child_tables[name]} == {"ProblemDescription"} and set(child_tables) - set(parent_tables) == {"ItemStationStructure"}, "exact two-table source delta")
    item_link = records(child_tables["ItemStationStructure"])
    general = records(child_tables["StationStructure"])
    need(len(item_link) == 1 and (item_link[0]["IID"], item_link[0]["STID"], item_link[0]["MSTID"], item_link[0]["TFRMS"], item_link[0]["TTOMS"], item_link[0]["DFRAC"], item_link[0]["OPOL"]) == ("TEACH-LRU-01", "BASE-01", "DEPOT-01", 1, 3, 1, "FAST"), "item-specific route fields")
    need(item_link[0]["CFRMS"] is None and item_link[0]["CTOMS"] is None and general[0]["TFRMS"] == general[0]["TTOMS"] == 2, "complete native schema and unchanged general link")
    invocation, closure = native_json(RUN / "invocation.json"), native_json(RUN / "closure.json")
    need(closure["error"] is None and closure["invocation_sha256"] == sha(RUN / "invocation.json"), "sealed successful closure")
    need(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stable during run")
    need(all((RUN / name).is_file() and (RUN / name).stat().st_size == meta["bytes"] and sha(RUN / name) == meta["sha256"] for name, meta in closure["raw"].items()), "all original raw hashes and lengths")
    need(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "session-0 SSH, mutex and GUI")
    steps = native_json(RUN / "steps.json")
    need([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "five successful native steps")
    before, after = populated(native_json(source)), populated(native_json(RUN / "roundtrip-raw.json"))
    need(len(before) == 22 and all(after.get(name) == contents for name, contents in before.items()) and native_json(RUN / "roundtrip-validation.json")["passed"], "exact 22-table native roundtrip")
    need("Input conversion completed. Errors: 0, Warnings: 1" in (RUN / "run.log").read_text(encoding="utf-8-sig"), "zero conversion errors, only log warning")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    control_log = (CONTROL / "model.log").read_text(encoding="utf-8-sig")
    need(sha(CONTROL / "model.log") == "7df3278befbc1f8da8051d3024eedfebb321ee40ec1595992a808391ca0561a2" and sha(CONTROL / "report-raw.json") == "3284c19ccce1237ca651cd50c6c0fb3320e9ed914a77f61c75cb4830e624c376", "accepted E04 raw control fingerprints")
    need("Time: 10  transport task 0 starts with 1 items/systems, transport time: 1" in log and "Time: 10  transport task 0 starts with 1 items/systems, transport time: 2" in control_log, "item override shortens downward shipment")
    need("Time: 10.1667  transport task 2 starts with 1 items/systems, transport time: 3" in log and "Time: 10.1667  transport task 2 starts with 1 items/systems, transport time: 2" in control_log, "item override lengthens upward shipment")
    need("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in log and "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives" in log, "FAST demand and base backorder")
    need("Time: 11 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in log and "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 1" in log, "physical spare arrival and one-hour shortage")
    need("Time: 11.3333 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log and "Time: 12.3333 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in control_log, "fit and readiness shift one hour earlier")
    need("Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>" in log and "Time: 14.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,1>" in log, "faulty LRU route and one-hour depot repair")
    need("Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in log and "Time: 14.1667 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in log, "physical stock draw and repaired return identities")
    need(log.count("mission success:") == 2 and log.count("mission aborted:") == 1, "one abort and two later successes")
    child, control = report(RUN), report(CONTROL)
    system, stock, summary = child["SystemResults"], child["StockTotalResults"], child["ResultSummary"][0]
    need(len(system) == len(stock) == len(control["SystemResults"]) == len(control["StockTotalResults"]) == 72 and all((r["STINT"], r["ETINT"]) == (i / 2, (i + 1) / 2) for i, r in enumerate(system)), "aligned 72 half-hour bins")
    need(sum(r["NFAIL"] for r in system) == sum(r["NREPT"] for r in system) == 1 and sum(r["NDF"] for r in stock) == 1, "one failure, system repair and stock demand")
    need(sum(r["NBO"] for r in stock) == 2 and sum(r["NBO"] for r in control["StockTotalResults"]) == 4, "one-hour versus two-hour backorder occupancy")
    need(abs(summary["MSUF"] - 2 / 3) < 1e-6 and summary == control["ResultSummary"][0] and system[-1]["NSYRY"] == 1 and stock[-1]["NBO"] == 0, "same mission factors and terminal ready/no-backorder state")
    result = {"schema": "simlox-e07-item-route-author-validation/v1", "passed": True, "decision": "GO_bounded_item_specific_record_override", "check_count": len(checks), "checks": checks, "limits": contract["limits"]}
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "checks": len(checks), "sha256": sha(OUT)}))


if __name__ == "__main__":
    main()

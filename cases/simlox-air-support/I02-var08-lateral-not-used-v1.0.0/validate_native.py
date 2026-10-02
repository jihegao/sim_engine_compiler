"""Author replay of I02.var08 OUT demand in a genuine lateral group."""
import hashlib
import json
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
AIR = HERE.parent
RUNS = HERE / "runs"
CHILD = RUNS / "i02-var08-lateral-out-v100-ssh-20261002-01"
PARENT = AIR / "E08-var01-immediate-lateral-v1.0.2"
CONTROL = PARENT / "runs" / "e08-immediate-on-v102-ssh-20261002-01"
OUT = HERE / "author-validation.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, r)) for instance in table["instances"] for r in instance["rows"]]


def report(path):
    return {t["name"]: rows(t) for t in parse_native(path)["report"]["tables"]}


def main():
    checks = []

    def need(ok, label):
        if not ok:
            raise AssertionError(label)
        checks.append(label)

    contract = parse_native(HERE / "contract.json")
    parent_source = PARENT / "on-input.json"
    child_source = HERE / "native-input.json"
    template = AIR / "I02-var02-out-transfer-v1.0.0" / "native-input.json"
    need(sha(parent_source) == contract["direct_parent"]["sha256"] and
         sha(template) == contract["transfer_schema_source"]["sha256"] and
         sha(child_source) == contract["source_sha256"] == sha(CHILD / "input.json"), "frozen accepted parent/schema/child")
    need(sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen exact diff")
    source_tables = {t["name"]: t for t in parse_native(child_source)["model"]["tables"]}
    parent_tables = {t["name"]: t for t in parse_native(parent_source)["model"]["tables"]}
    need(set(source_tables) - set(parent_tables) == {"ItemTransfer"} and
         {n for n in parent_tables if parent_tables[n] != source_tables[n]} == {"ProblemDescription"}, "only OUT table plus description")
    need(rows(source_tables["ItemTransfer"]) == [{"STFID": "BASE-01", "STTID": "<OUTSIDE>", "IID": "TEACH-LRU-01", "TFTIME": 2, "TFQTY": 1, "TFDT": 0, "NOTE": None}], "one h2 OUT request")
    need(rows(source_tables["Control"])[0]["ENLAT"] == "Y" and
         rows(source_tables["StockAllocation"])[0]["STSIZ"] == 0 and
         rows(source_tables["StationLateralSupport"])[0]["LSTID"] == "BASE-02", "enabled lateral peer retained")
    invocation = parse_native(CHILD / "invocation.json")
    closure = parse_native(CHILD / "closure.json")
    need(closure["error"] is None and closure["invocation_sha256"] == sha(CHILD / "invocation.json") and
         closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "clean native closure")
    need(len(closure["raw"]) == 12 and all((CHILD / n).stat().st_size == x["bytes"] and sha(CHILD / n) == x["sha256"] for n, x in closure["raw"].items()), "12 native raw seals")
    need(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and
         invocation["gui"]["pid"] == 13340 and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "SSH queue and GUI identity")
    steps = parse_native(CHILD / "steps.json")
    need([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and
         all(s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "five native steps")
    before, after = populated(parse_native(child_source)), populated(parse_native(CHILD / "roundtrip-raw.json"))
    need(len(before) == 25 and all(after.get(n) == t for n, t in before.items()) and
         parse_native(CHILD / "roundtrip-validation.json")["passed"], "exact 25 populated-table roundtrip")
    need("Input conversion completed. Errors: 0, Warnings: 1" in (CHILD / "run.log").read_text(encoding="utf-8-sig") and
         (CHILD / "model.sxo").stat().st_size > 4, "zero converter errors and nonempty SXO")
    log = (CHILD / "model.log").read_text(encoding="utf-8-sig")
    control_log = (CONTROL / "model.log").read_text(encoding="utf-8-sig")
    need("Time: 2 <TEACH-LRU-01,0,BASE-01,0> Item transfer demand arrives from OUT-transfer" in log and
         "Time: 2 <TEACH-LRU-01,0,BASE-01,0> Item transfer backorder added" in log and
         "Time: 2  item transfer task 0 (OUT)  starts with 0 items" in log, "h2 transfer demand processed with zero physical items")
    h2 = "\n".join(line for line in log.splitlines() if line.startswith("Time: 2 "))
    need("Lateral support" not in h2 and "BASE-02" not in h2 and "transport request" not in h2, "no h2 lateral peer draw")
    need("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Lateral support from: <TEACH-LRU-01,0,BASE-02,0>" in log and
         "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Lateral support from: <TEACH-LRU-01,0,BASE-02,0>" in control_log, "later ordinary demand activates same lateral route")
    need("Time: 10.5 <TEACH-LRU-01,0,BASE-01,0> Item transfer backorder removed" in log and
         "Time: 10.5  item transfer task 1 (OUT)  starts with 1 items" in log and
         "Time: 10.5 <TEACH-LRU-01,0,BASE-01,0> Backorder removed" not in log, "later lateral spare diverted to transfer backorder")
    need(log.count("mission aborted:") == 1 and log.count("mission cancelled:") == 2 and "mission success:" not in log, "aircraft remains down, later missions cancel")

    data = {}
    for station in ("base01", "base02", "depot"):
        run = RUNS / f"i02-var08-{station}-report-v100-ssh-20261002-01"
        iv, cl = parse_native(run / "invocation.json"), parse_native(run / "closure.json")
        need(cl["error"] is None and cl["exit_code"] == 0 and cl["invocation_sha256"] == sha(run / "invocation.json") and
             cl["source_hashes_before"] == cl["source_hashes_after"] == iv["source_hashes_before"] and
             cl["source_hashes_before"]["sxo"] == sha(CHILD / "model.sxo"), station + " sealed report source")
        need(len(cl["raw"]) == 2 and all((run / n).stat().st_size == x["bytes"] and sha(run / n) == x["sha256"] for n, x in cl["raw"].items()), station + " two raw seals")
        data[station] = report(run / "item-report-raw.json")
        item = data[station]["ItemResults"]
        need(len(item) == 72 and all((r["STINT"], r["ETINT"]) == (i / 2, (i + 1) / 2) for i, r in enumerate(item)), station + " 72 half-hour bins")
        parent_item = report(PARENT / "runs" / f"e08-on-{station}-report-v102-ssh-20261002-01" / "item-report-raw.json")["ItemResults"]
        if station != "base01":
            need(item == parent_item, station + " ledger unchanged from accepted control")

    base = data["base01"]["ItemResults"]
    peer = data["base02"]["ItemResults"]
    need(all(peer[i]["STOHA"] == 1 for i in range(0, 20)) and base[4]["STOHA"] == 0, "peer spare persists from h2 through h10")
    need(all(r["NBO"] == 1 for r in base[20:]) and base[-1]["STOHA"] == 0, "ordinary BASE backorder persists to horizon")
    need(base[-1]["STSZ"] == 0 and peer[-1]["STOHA"] == 1 and data["depot"]["ItemResults"][-1]["STOHA"] == 1, "terminal stock and absent BASE spare")
    child_report = report(CHILD / "report-raw.json")
    control_report = report(CONTROL / "report-raw.json")
    need(len(child_report["SystemResults"]) == len(child_report["StockTotalResults"]) == 72 and
         child_report["SystemResults"][-1]["NSYRY"] == 0 and control_report["SystemResults"][-1]["NSYRY"] == 1, "terminal aircraft down versus ready control")
    need(child_report["ResultSummary"][0]["MSUF"] == 0 and
         control_report["ResultSummary"][0]["MSUF"] > 0, "mission success fraction drops to zero")
    result = {"schema": "simlox-i02-var08-genuine-lateral-author-validation/v1", "passed": True,
              "decision": "GO_restricted_direct_transfer_no_lateral_with_indirect_later_fulfillment",
              "check_count": len(checks), "checks": checks, "limits": contract["limits"]}
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "checks": len(checks), "sha256": sha(OUT)}))


if __name__ == "__main__":
    main()

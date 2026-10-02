"""Author replay: scheduled future peer spare gives no observed DLAYL contrast."""
import hashlib
import json
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = HERE / "runs"
ARMS = ("off", "on")
STATIONS = ("base-01", "base-02", "depot")
REPORTS = ("ItemResults", "SystemResults", "StockTotalResults", "MissionResults", "ResultSummary")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, r)) for instance in table["instances"] for r in instance["rows"]]


def report(path):
    return {t["name"]: t for t in parse_native(path)["report"]["tables"]}


def main():
    checks = []

    def need(ok, label):
        if not ok:
            raise AssertionError(label)
        checks.append(label)

    contract = parse_native(HERE / "contract.json")
    parent = ROOT / contract["direct_parent"]["package"] / "on-input.json"
    donor = ROOT / contract["transfer_schema_donor"]["package"] / "native-input.json"
    need(sha(parent) == contract["direct_parent"]["source_sha256"] and
         sha(donor) == contract["transfer_schema_donor"]["source_sha256"], "accepted source and donor")
    need(sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "exact diff sealed")
    need(sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) ==
         contract["installed_source_sha256"]["manual_pdf"] and
         sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")) ==
         contract["installed_source_sha256"]["table_dictionary"], "installed manual and dictionary")
    sources = {arm: HERE / f"{arm}-input.json" for arm in ARMS}
    models = {arm: {t["name"]: t for t in parse_native(path)["model"]["tables"]} for arm, path in sources.items()}
    need(all(sha(sources[a]) == contract[f"{a}_input_sha256"] and len(populated(parse_native(sources[a]))) == 25
             for a in ARMS), "both 25-table frozen source inputs")
    need(set(models["off"]) == set(models["on"]) and
         {n for n in models["off"] if models["off"][n] != models["on"][n]} ==
         {"LateralSupport", "ProblemDescription"} and
         [rows(models[a]["LateralSupport"])[0]["DLAYL"] for a in ARMS] == ["N", "Y"] and
         rows(models["off"]["ItemTransfer"]) == rows(models["on"]["ItemTransfer"]) ==
         [{"STFID": "DEPOT-01", "STTID": "BASE-02", "IID": "TEACH-LRU-01", "TFTIME": 9.0,
           "TFQTY": 1, "TFDT": 2.0, "NOTE": None}], "isolated DLAYL contrast and future transfer")
    need(all(rows(models[a]["Control"])[0]["ENLAT"] == "Y" and
             rows(models[a]["Item"])[0]["TRACK"] == "Y" and
             next(r for r in rows(models[a]["StockAllocation"]) if r["STID"] == "BASE-02")["STSIZ"] == 0
             for a in ARMS), "lateral on, tracking on, empty peer opening stock")
    logs, output, native_closures = {}, {}, {}
    total_raw = 0
    for arm in ARMS:
        run = RUNS / f"e08-dlayl-{arm}-v100-ssh-20261002-01"
        inv, closure = (parse_native(run / n) for n in ("invocation.json", "closure.json"))
        native_closures[arm] = sha(run / "closure.json")
        need(closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and
             inv["input_sha256"] == sha(sources[arm]) == sha(run / "input.json"), f"{arm} native invocation")
        need(closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"] and
             inv["source_hashes_before"]["donor"] == sha(donor) and
             inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"] and
             inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
             inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1,
             f"{arm} frozen sources and native guard")
        need(len(closure["raw"]) == 12 and all((run / n).stat().st_size == m["bytes"] and
             sha(run / n) == m["sha256"] for n, m in closure["raw"].items()), f"{arm} 12 native raw seals")
        total_raw += len(closure["raw"])
        steps = parse_native(run / "steps.json")
        need([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and
             all(s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{arm} five native steps")
        rt = parse_native(run / "roundtrip-validation.json")
        need(rt["passed"] and len(rt["populated_tables"]) == 25 and
             "Input conversion completed. Errors: 0," in (run / "run.log").read_text(encoding="utf-8-sig"),
             f"{arm} zero conversion errors and exact 25-table roundtrip")
        logs[arm] = (run / "model.log").read_bytes()
        log = logs[arm].decode("utf-8-sig")
        for marker in ("Time: 9  item transfer task 0 (BETWEEN)  starts with 1 items, transfer time: 2",
                       "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Lateral support check, ordinary remaining time: 2",
                       "Time: 11  item transfer task 0 (BETWEEN)  arrives with 1 items",
                       "Time: 11 <TEACH-LRU-01,0,BASE-02,0> Put back replacement item <TEACH-LRU-01,0,0> to stock",
                       "Time: 14.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,1>",
                       "Time: 15.1667 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
                       "Time: 15.5 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>"):
            need(marker in log, f"{arm} event {marker[:53]}")
        need("from <BASE-02,0> to <BASE-01,0>" not in log and
             "Take replacement item <TEACH-LRU-01,0,0> from stock" in log,
             f"{arm} transfer item stays at peer rather than lateral")
        output[arm] = {}
        for station in STATIONS:
            sr = RUNS / f"e08-dlayl-{arm}-{station}-report-v100-ssh-20261002-01"
            ri, rc = (parse_native(sr / n) for n in ("invocation.json", "closure.json"))
            need(rc["error"] is None and rc["invocation_sha256"] == sha(sr / "invocation.json") and
                 len(rc["raw"]) == 2 and all((sr / n).stat().st_size == m["bytes"] and
                 sha(sr / n) == m["sha256"] for n, m in rc["raw"].items()), f"{arm} {station} report seals")
            total_raw += len(rc["raw"])
            need(ri["source_closure_sha256"] == native_closures[arm] and
                 ri["source_hashes_before"]["sxo"] == sha(run / "model.sxo") and
                 ri["session_id"] == 0 and "sshd.exe" in ri["ssh_ancestor_names"] and
                 ri["gui"]["pid"] == 13340, f"{arm} {station} SXO/report guard")
            output[arm][station] = report(sr / "item-report-raw.json")
            need(all(len(rows(output[arm][station][n])) == 72 for n in REPORTS[:-1]) and
                 len(rows(output[arm][station]["ResultSummary"])) == 1,
                 f"{arm} {station} interval and summary row counts")
    need(logs["off"] == logs["on"], "OFF and ON physical event logs byte equal")
    for station in STATIONS:
        for name in REPORTS:
            need(output["off"][station][name] == output["on"][station][name],
                 f"{station} {name} OFF/ON cell equality")
    peer = rows(output["on"]["base-02"]["ItemResults"])
    depot = rows(output["on"]["depot"]["ItemResults"])
    base = rows(output["on"]["base-01"]["ItemResults"])
    system = rows(output["on"]["base-01"]["SystemResults"])
    at = lambda data, hour: next(r for r in data if r["STINT"] == hour)
    need(at(peer, 10)["STOHA"] == 0 and at(peer, 11)["STOHA"] == 1 and
         at(peer, 35.5)["STOHA"] == 1, "peer future item arrival and terminal spare")
    need(at(depot, 10)["NBO"] == 1 and at(depot, 15.5)["NBO"] == 0 and
         at(depot, 35.5)["STOHA"] == 0, "depot ordinary backorder and terminal stock")
    need(at(base, 10)["NBO"] == 1 and at(base, 14.5)["NBO"] == 1 and
         at(base, 15.5)["NBO"] == 0 and at(base, 35.5)["STOHA"] == 0,
         "base backorder persists until repaired ordinary shipment")
    need(at(system, 15)["NSYRY"] == 0 and at(system, 15.5)["NSYRY"] == 1,
         "aircraft ready after h15.5")
    need(total_raw == 36, "eight closures seal 36 raw files")
    out = {"schema": "simlox-e08-var03-delayed-lateral-author-replay/v1", "passed": True,
           "checks": checks, "check_count": len(checks), "sealed_raw_files": total_raw,
           "decision": "NO_GO_positive_DLAYL_effect_for_scheduled_future_peer_transfer; bounded_negative_observation"}
    path = HERE / "author-validation.json"
    encoded = (json.dumps(out, indent=2) + "\n").encode()
    if path.exists():
        assert path.read_bytes() == encoded, "frozen author validation differs"
    else:
        path.write_bytes(encoded)
    print(json.dumps({"checks": len(checks), "sha256": sha(path), "sealed_raw_files": total_raw}))


if __name__ == "__main__":
    main()

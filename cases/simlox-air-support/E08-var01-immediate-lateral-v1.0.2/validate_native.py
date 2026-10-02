"""Author replay of sealed E08 immediate-lateral on/off native evidence."""
import hashlib
import json
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
OUT = HERE / "author-validation.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(table):
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def report(path):
    tables = parse_native(path)["report"]["tables"]
    return {table["name"]: rows(table) for table in tables}


def seal(run, need, label):
    invocation = parse_native(run / "invocation.json")
    closure = parse_native(run / "closure.json")
    need(closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json"), label + " closure")
    need(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], label + " frozen sources")
    need(all((run / name).is_file() and (run / name).stat().st_size == meta["bytes"] and sha(run / name) == meta["sha256"]
             for name, meta in closure["raw"].items()), label + " raw hashes")
    need(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and
         invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
         invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, label + " guarded session")
    return invocation, closure


def main():
    checks = []

    def need(ok, label):
        if not ok:
            raise AssertionError(label)
        checks.append(label)

    contract = parse_native(HERE / "contract.json")
    parent = HERE.parent / contract["parent_case"] / "native-input.json"
    need(sha(parent) == contract["parent_sha256"], "accepted E07 parent")
    need(sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) == contract["manual_pdf_sha256"] and
         sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")) == contract["dictionary_sha256"], "installed manual and dictionary")
    source = {v: HERE / f"{v}-input.json" for v in ("on", "off")}
    need(sha(source["on"]) == contract["on_input_sha256"] and sha(source["off"]) == contract["off_input_sha256"], "frozen on/off source inputs")
    need(sha(HERE / "exact-diff.json") == "f7fd31360b4f111fd504494bd8312e5132c330abbfddd3b30766bc7dac46d3a0", "frozen exact diff")
    models = {v: {t["name"]: t for t in parse_native(source[v])["model"]["tables"]} for v in source}
    need(set(models["on"]) == set(models["off"]) and
         {name for name in models["on"] if models["on"][name] != models["off"][name]} == {"ProblemDescription", "Control"}, "on/off differs only ENLAT and description tables")
    need(rows(models["on"]["StationLateralSupport"]) == [{"LGID": "LAT-01", "STID": "BASE-01", "LSTID": "BASE-02", "TFRLS": 0.5, "TTOLS": 0.5, "NOTE": None}] and
         rows(models["on"]["LateralSupport"])[0]["LSRUL"] == "IMMEDIATE", "genuine lateral group and peer route")
    need([r["RTYPE"] for r in rows(models["on"]["ResultCollection"])] == ["MISSION", "SYSTEM", "ITEM"] and
         rows(models["on"]["Item"])[0]["TRACK"] == "Y", "item result collection enabled")

    native = {}
    for variant in ("on", "off"):
        run = RUNS / f"e08-immediate-{variant}-v102-ssh-20261002-01"
        native[variant] = run
        invocation, _ = seal(run, need, variant + " native")
        need(invocation["input_sha256"] == sha(source[variant]) == sha(run / "input.json"), variant + " input source fingerprint")
        steps = parse_native(run / "steps.json")
        need([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and
             all(s["status"] == ("calc_observed" if s["name"] == "calc" else "completed") and
                 s["exit_code"] == 0 and s["gui_preserved"] for s in steps), variant + " native steps")
        before, after = populated(parse_native(source[variant])), populated(parse_native(run / "roundtrip-raw.json"))
        need(len(before) == 24 and all(after.get(name) == contents for name, contents in before.items()) and
             parse_native(run / "roundtrip-validation.json")["passed"], variant + " exact 24-table roundtrip")
        need("Input conversion completed. Errors: 0, Warnings: 1" in (run / "run.log").read_text(encoding="utf-8-sig"), variant + " zero conversion errors")
        need((run / "model.sxo").stat().st_size > 4 and (run / "report-raw.json").stat().st_size > 4, variant + " nonempty SXO and default report")

    logs = {v: (native[v] / "model.log").read_text(encoding="utf-8-sig") for v in native}
    need("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Lateral support from: <TEACH-LRU-01,0,BASE-02,0>" in logs["on"] and
         "Lateral support from:" not in logs["off"], "lateral selected only when enabled")
    need("<<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-02,0>,<TEACH-LRU-01,0,BASE-01,0>> started" in logs["on"] and
         "Time: 10.5 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>" in logs["on"], "peer item 1 moves to demand base in half an hour")
    need("<<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started" in logs["off"] and
         "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in logs["off"], "ordinary depot item 0 moves to demand base in one hour")
    need("Time: 10.5 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 0.5" in logs["on"] and
         "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 1" in logs["off"], "backorder wait follows chosen route")
    need("<<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-02,0>> started" in logs["on"] and
         "Time: 11 <TEACH-LRU-01,0,BASE-02,0> Put back replacement item <TEACH-LRU-01,0,0> to stock" in logs["on"], "lateral donor replenished from depot")
    need(logs["on"].count("mission success:") == logs["off"].count("mission success:") == 2 and
         logs["on"].count("mission aborted:") == logs["off"].count("mission aborted:") == 1, "mission event counts preserved")

    results = {}
    for variant in ("on", "off"):
        results[variant] = {}
        for station in ("base01", "base02", "depot"):
            run = RUNS / f"e08-{variant}-{station}-report-v102-ssh-20261002-01"
            invocation, closure = seal(run, need, f"{variant} {station} report")
            need(closure["exit_code"] == 0 and invocation["source_run_id"] == native[variant].name and
                 closure["source_hashes_before"]["sxo"] == sha(native[variant] / "model.sxo"), f"{variant} {station} report source")
            need("Export completed!" in (run / "report-export.log").read_text(encoding="utf-8-sig"), f"{variant} {station} report export")
            data = report(run / "item-report-raw.json")
            item = data["ItemResults"]
            expected_stid = {"base01": "BASE-01", "base02": "BASE-02", "depot": "DEPOT-01"}[station]
            need(len(item) == 72 and all(r["IID"] == "TEACH-LRU-01" and r["STID"] == expected_stid and
                 (r["STINT"], r["ETINT"]) == (i / 2, (i + 1) / 2) for i, r in enumerate(item)), f"{variant} {station} aligned ITEM bins")
            results[variant][station] = data

    def at(variant, station, hour):
        return results[variant][station]["ItemResults"][int(hour * 2)]

    need((at("on", "base01", 10)["NBO"], at("on", "base01", 10.5)["NBO"]) == (1, 0) and
         (at("off", "base01", 10)["NBO"], at("off", "base01", 10.5)["NBO"], at("off", "base01", 11)["NBO"]) == (1, 1, 0), "one versus two half-hour base backorder bins")
    need((at("on", "base02", 10)["STOHA"], at("on", "base02", 11)["STOHA"]) == (0, 1) and
         at("off", "base02", 10)["STOHA"] == 1, "peer stock draw and replenishment only with lateral")
    need(at("on", "depot", 10)["STOHA"] == at("off", "depot", 10)["STOHA"] == 0, "depot issued a physical spare in each arm")
    need(all(results[v][s]["ItemResults"][-1]["NBO"] == 0 for v in results for s in results[v]) and
         all(results[v][s]["ItemResults"][-1]["STOHA"] == {"base01": 0, "base02": 1, "depot": 1}[s] for v in results for s in results[v]), "terminal station stock and backorders")
    on_system = results["on"]["base01"]["SystemResults"]
    off_system = results["off"]["base01"]["SystemResults"]
    need(len(on_system) == len(off_system) == 72 and on_system[21]["NSYRY"] > off_system[21]["NSYRY"] and
         on_system[-1]["NSYRY"] == off_system[-1]["NSYRY"] == 1, "earlier system readiness and same terminal state")
    need(results["on"]["base01"]["ResultSummary"] == results["off"]["base01"]["ResultSummary"] and
         results["on"]["base01"]["MissionResults"] == results["off"]["base01"]["MissionResults"], "mission summary and bins invariant")
    result = {"schema": "simlox-e08-var01-v102-author-validation/v1", "passed": True,
              "decision": "GO_bounded_immediate_lateral_control", "check_count": len(checks), "checks": checks,
              "limits": contract["limits"]}
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "checks": len(checks), "sha256": sha(OUT)}))


if __name__ == "__main__":
    main()

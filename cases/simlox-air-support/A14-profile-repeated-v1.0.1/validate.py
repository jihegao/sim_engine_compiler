"""Author replay of the bounded A14 repeated profile dependency case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VARIANTS = ("control", "explicit", "profile")
RUNS = {v: HERE / "runs" / f"a14-profile-{v}-v101-20261001-01" for v in VARIANTS}
EXPECTED = {
    "parent": "f81445ad2daba09321e7a55ad67c5355b7e4a14ec3a58bbf10fbfcd18b343376",
    "donor": "e795c5fcf563f8e42ab9e9cb161a925bec3b06157cbbecde7901e99bfec91d85",
    "control": "68c43a51e199462cfb8bda26fa23de90f5ed4776d5feff92e5339640e1330111",
    "explicit": "10cc545f9fb842048518ac94902d5854e1b3e5148114e8b2a3613ff09a22a381",
    "profile": "11993115206c2176c45f83e4706ede703b5f1a994ed7c0ad737fe37c07c759cb",
    "diff": "a264958ea90db6c9d06ba904df126159553b4a7c34005724f1373f4eb05ff3e3",
}
checks = 0


def yes(value: bool, reason: str) -> None:
    global checks
    if not value:
        raise AssertionError(reason)
    checks += 1


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(doc: dict, name: str, root: str = "report") -> list[dict]:
    matches = [t for t in doc[root]["tables"] if t["name"] == name]
    yes(len(matches) == 1, f"{name} unique")
    tab = matches[0]
    cols = [c["name"] for c in tab["columns"]]
    out = []
    for instance in tab["instances"]:
        for values in instance["rows"]:
            yes(len(values) == len(cols), f"{name} rectangular")
            out.append(dict(zip(cols, values, strict=True)))
    return out


def source() -> None:
    contract = read(HERE / "contract.json")
    yes(contract["case_id"] == "A14" and contract["variant_id"] == "A14.var06" and
        contract["case_version"] == "1.0.1-candidate", "contract identity")
    yes(contract["parent"]["input_sha256"] == EXPECTED["parent"], "accepted A14 parent contract")
    yes(contract["profile_donor"]["input_sha256"] == EXPECTED["donor"], "accepted A09 donor contract")
    yes(contract["inputs_sha256"] == {v: EXPECTED[v] for v in VARIANTS}, "frozen input contract")
    yes(contract["exact_diff_sha256"] == EXPECTED["diff"], "frozen exact diff contract")
    yes(sha(ROOT / "A14-continuous-end-abort-v1.0.1" / "control-input.json") == EXPECTED["parent"], "A14 parent source")
    yes(sha(ROOT / "A09-hierarchical-operation-profile-v1.0.1" / "native-nested.json") == EXPECTED["donor"], "A09 donor source")
    yes(sha(HERE / "exact-diff.json") == EXPECTED["diff"], "exact diff source")
    yes(sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) == contract["source"]["manual_sha256"], "manual source")
    yes(sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")) == contract["source"]["dictionary_sha256"], "dictionary source")
    docs = {v: parse_native(HERE / f"{v}-input.json") for v in VARIANTS}
    for variant in VARIANTS:
        yes(sha(HERE / f"{variant}-input.json") == EXPECTED[variant], f"{variant} input source")
    tabs = {v: {t["name"]: t for t in docs[v]["model"]["tables"]} for v in VARIANTS}
    yes(set(tabs["explicit"]) - set(tabs["control"]) == {"MissionDependence"}, "explicit table addition")
    yes(set(tabs["profile"]) - set(tabs["control"]) == {"MissionDependenceProfile"}, "profile table addition")
    for variant in ("explicit", "profile"):
        yes(all(tabs[variant][n] == tabs["control"][n] for n in tabs["control"] if n != "ProblemDescription"),
            f"{variant} common tables identical")
    yes(rows(docs["explicit"], "MissionDependence", "model") == [
        {"DUNID": "TEACH-UNIT", "DMTID": "EXECUTE", "DSTIM": t,
         "PUNID": "TEACH-UNIT", "PMTID": "SUPPORT", "PSTIM": t,
         "DTYPE": "CONTINUOUS", "MUTD": "N", "DTTOL": None, "NOTE": None}
        for t in (8.0, 32.0)], "two exact explicit dependence rows")
    yes(rows(docs["profile"], "MissionDependenceProfile", "model") == [
        {"PRID": "A14-WAVE", "DMTID": "EXECUTE", "DSTIM": 8.0,
         "PMTID": "SUPPORT", "PSTIM": 8.0, "DTYPE": "CONTINUOUS",
         "MUTD": "N", "DTTOL": None, "NOTE": None}], "one exact profile dependence row")
    op = rows(docs["control"], "OperationProfile", "model")
    yes([(r["PRID"], r["SPRID"], r["STIM"], r["IQTY"], r["IPER"]) for r in op] == [
        ("BASIC-SCHEDULE", "A14-WAVE", 0.0, 2, 48.0),
        ("A14-WAVE", "SUPPORT", 8.0, 1, 0),
        ("A14-WAVE", "EXECUTE", 8.0, 1, 0)], "nested profile recipe")
    rc = rows(docs["control"], "ResultCollection", "model")
    yes([(r["RTYPE"], r["RCSTA"], r["RCEND"], r["RCINT"]) for r in rc] ==
        [("MISSION", 0, 40.0, 0.5), ("SYSTEM", 0, 40.0, 0.5)], "corrected explicit collection windows")
    yes(sha(ROOT / "A14-profile-repeated-v1.0.0" / "review" / "independent-readonly-2026-10-01.json") ==
        "5156486dacca7febbce6b20e6dd076a99ecc024452dec45eae0a88907d445748", "v100 diagnostic retained")


def replay(variant: str) -> None:
    path = RUNS[variant]
    seal, inv, steps = (read(path / name) for name in ("closure.json", "invocation.json", "steps.json"))
    yes(seal["error"] is None and seal["run_id"] == path.name, f"{variant} successful closure")
    yes(seal["invocation_sha256"] == sha(path / "invocation.json"), f"{variant} invocation closure")
    yes(seal["source_hashes_before"] == seal["source_hashes_after"], f"{variant} source stable")
    source_hash = seal["source_hashes_before"]
    yes((source_hash["input"], source_hash["parent"], source_hash["profile_donor"], source_hash["exact_diff"]) ==
        (EXPECTED[variant], EXPECTED["parent"], EXPECTED["donor"], EXPECTED["diff"]), f"{variant} lineage")
    for key, name in (("contract", "contract.json"), ("builder", "build.py"),
                      ("diff_checker", "describe_diff.py"), ("checker", "check_roundtrip.py"),
                      ("runner_script", "run_native_ssh.ps1")):
        yes(source_hash[key] == sha(HERE / name), f"{variant} sealed {key}")
    yes(inv["case_id"] == "A14" and inv["case_version"] == "1.0.1-candidate" and
        inv["variant"] == variant and inv["execution_mode"] == "ssh_cli_v1", f"{variant} invocation")
    yes(inv["session_id"] == 0 and inv["ssh_connection_present"] and inv["gui"]["pid"] == 13340 and
        inv["gui"]["session_id"] == 1 and "sshd.exe" in inv["ssh_ancestor_names"], f"{variant} session and GUI")
    yes(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant} host mutex")
    yes([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{variant} five steps")
    for step in steps:
        yes(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"{variant} {step['name']} result")
    for name, item in seal["raw"].items():
        yes((path / name).stat().st_size == item["bytes"] and sha(path / name) == item["sha256"], f"{variant} raw {name}")
    yes(sha(path / "input.json") == EXPECTED[variant], f"{variant} copied source")
    rt = read(path / "roundtrip-validation.json")
    yes(rt["passed"] and not rt["differences"] and len(rt["populated_tables"]) == (13 if variant == "control" else 14), f"{variant} native source roundtrip")
    before, after = (populated(parse_native(path / name)) for name in ("input.json", "roundtrip-raw.json"))
    for name, tab in before.items():
        yes(after.get(name) == tab, f"{variant} roundtrip {name}")
    conversion = (path / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    yes("Input conversion completed. Errors: 0, Warnings: 2" in conversion and
        "warning #108" in conversion and "warning #126" in conversion, f"{variant} conversion")
    yes((path / "model.sxo").stat().st_size > 1000, f"{variant} nonempty SXO")
    events = (path / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    yes(events.count("mission starting,") == 4, f"{variant} four starts")
    for wave, (hour, sid, eid) in enumerate(((8, 0, 1), (32, 2, 3))):
        yes(f"Time: {hour-1} <TEACH-UNIT> mission ordered: SUPPORT" in events, f"{variant} wave {wave} support ordered")
        yes(f"Time: {hour-1} <TEACH-UNIT> mission ordered: EXECUTE" in events, f"{variant} wave {wave} execute ordered")
        yes(f"Time: {hour} <SUPPORT,TEACH-UNIT,0,0,{sid}> mission starting, duration: 2" in events, f"{variant} wave {wave} support start")
        yes(f"Time: {hour} <EXECUTE,TEACH-UNIT,0,0,{eid}> mission starting, duration: 4" in events, f"{variant} wave {wave} execute start")
        yes(f"Time: {hour+2} <SUPPORT,TEACH-UNIT,0,0,{sid}> mission success:" in events, f"{variant} wave {wave} support success")
        if variant == "control":
            yes(f"Time: {hour+4} <EXECUTE,TEACH-UNIT,0,0,{eid}> mission success:" in events, f"{variant} wave {wave} execute success")
        else:
            yes(f"Time: {hour+2} <EXECUTE,TEACH-UNIT,0,0,{eid}> mission aborted:" in events, f"{variant} wave {wave} execute abort")
            yes(f"Time: {hour+4} <EXECUTE,TEACH-UNIT,0,0,{eid}> mission success:" not in events, f"{variant} wave {wave} no success")
    yes(events.count("mission aborted:") == (0 if variant == "control" else 2), f"{variant} abort count")
    yes("failure occurred" not in events.lower(), f"{variant} no random failure")
    report = parse_native(path / "report-raw.json")
    summary, = rows(report, "ResultSummary")
    yes((summary["NREP"], summary["RTILW"], summary["RTIUP"]) == (1, 0, 40), f"{variant} report horizon")
    factor = 1 if variant == "control" else 2 / 3
    yes(abs(summary["MTMF"] - factor) < 1e-6 and abs(summary["STMF"] - factor) < 1e-6, f"{variant} factors")
    yes(summary["MSTF"] == summary["MSUF"] == 0, f"{variant} fixed-only factors")
    systems, stock = rows(report, "SystemResults"), rows(report, "StockTotalResults")
    yes(len(systems) == len(stock) == 80, f"{variant} 80 paired bins")
    for i, (sy, st) in enumerate(zip(systems, stock, strict=True)):
        hour = i / 2
        yes((sy["STINT"], sy["ETINT"], st["STINT"], st["ETINT"]) ==
            (hour, hour + 0.5, hour, hour + 0.5), f"{variant} bin {i} window")
        operating = (2 if 8 <= hour < 10 or 32 <= hour < 34 else
                     1 if variant == "control" and (10 <= hour < 12 or 34 <= hour < 36) else 0)
        yes(sy["NSYMO"] == operating and sy["NSYMS"] == 0, f"{variant} bin {i} operating")
        yes(sy["NSYA"] == 2 and sy["NSYRY"] + sy["NSYMA"] == 2, f"{variant} bin {i} aircraft ledger")
        yes(all(sy[k] == 0 for k in ("NREPT", "NPMT", "NFAIL", "NDAM", "NSYRP", "NSYPM", "NROBT", "NRCFG")), f"{variant} bin {i} no maintenance")
        yes(all(st[k] == 0 for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), f"{variant} bin {i} no stock demand")
    yes(sum(sy["NSYMO"] * .5 for sy in systems) == (12 if variant == "control" else 8), f"{variant} operation exposure")
    yes(systems[-1]["NSYRY"] == 2 and systems[-1]["NSYMA"] == 0, f"{variant} terminal ready")


def main() -> None:
    source()
    for variant in VARIANTS:
        replay(variant)
    yes(sha(RUNS["explicit"] / "model.log") == sha(RUNS["profile"] / "model.log"), "explicit/profile byte-identical events")
    explicit = parse_native(RUNS["explicit"] / "report-raw.json")["report"]["tables"]
    profile = parse_native(RUNS["profile"] / "report-raw.json")["report"]["tables"]
    yes({t["name"]: t for t in explicit if t["name"] != "ProblemDescription"} ==
        {t["name"]: t for t in profile if t["name"] != "ProblemDescription"}, "explicit/profile report tables equivalent")
    result = {"schema": "simlox-a14-profile-repeated-author-validation/v1", "passed": True,
              "checks": checks, "decision": "bounded_go_two_wave_profile_explicit_equivalence",
              "runs": {v: RUNS[v].name for v in VARIANTS},
              "excluded_diagnostic": "A14-profile-repeated-v1.0.0 has only 32 System bins and failed its 80-bin frozen contract",
              "finding": "One MissionDependenceProfile row expands the two A09-style waves to the same events and report rows as two explicit MissionDependence rows; each dependent EXECUTE aborts at its SUPPORT completion.",
              "limits": ["One two-level profile with IQTY=1 leaves and two no-failure waves in one unit.",
                         "Other profiles, IQTY>1 leaves, overlaps, MUTD, DTTOL, GUI visual and cross-engine behavior unverified."]}
    output = HERE / "review" / "author-validation-2026-10-01.json"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"passed": True, "checks": checks, "decision": result["decision"]}))


if __name__ == "__main__":
    main()

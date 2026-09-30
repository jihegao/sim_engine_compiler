"""Author replay of the bounded A14 continuous-precedent completion case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = {v: HERE / "runs" / f"a14-{v}-v101-20261001-01"
        for v in ("control", "dependent")}
EXPECTED = {
    "parent": "997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea",
    "control": "f81445ad2daba09321e7a55ad67c5355b7e4a14ec3a58bbf10fbfcd18b343376",
    "dependent": "67484243a3b35395e21dcd6554a95c2637986086c4523d5e1ba99e2890d21de3",
    "diff": "3669fb6886d969f0fb4fd18306053eef085bff25ec181dff561f1ff11ac35680",
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
    yes(contract["parent"]["input_sha256"] == EXPECTED["parent"], "parent contract")
    yes(contract["inputs_sha256"] == {v: EXPECTED[v] for v in RUNS}, "input contract")
    yes(contract["exact_diff_sha256"] == EXPECTED["diff"], "diff contract")
    yes(sha(ROOT / "A05-continuous-baseline-v1.0.1" / "native-continuous.json") == EXPECTED["parent"], "parent source")
    yes(sha(HERE / "exact-diff.json") == EXPECTED["diff"], "diff source")
    for variant in RUNS:
        yes(sha(HERE / f"{variant}-input.json") == EXPECTED[variant], f"{variant} input")
    yes(sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) == contract["source"]["manual_sha256"], "manual fingerprint")
    yes(sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")) == contract["source"]["dictionary_sha256"], "dictionary fingerprint")
    control = {t["name"]: t for t in parse_native(HERE / "control-input.json")["model"]["tables"]}
    dependent = {t["name"]: t for t in parse_native(HERE / "dependent-input.json")["model"]["tables"]}
    yes(set(dependent) - set(control) == {"MissionDependence"} and not (set(control) - set(dependent)), "one dependence table delta")
    yes(all(control[n] == dependent[n] for n in set(control) if n != "ProblemDescription"), "all other tables identical")
    yes(rows(parse_native(HERE / "dependent-input.json"), "MissionDependence", "model") ==
        [{"DUNID": "TEACH-UNIT", "DMTID": "EXECUTE", "DSTIM": 8.0,
          "PUNID": "TEACH-UNIT", "PMTID": "SUPPORT", "PSTIM": 8.0,
          "DTYPE": "CONTINUOUS", "MUTD": "N", "DTTOL": None, "NOTE": None}], "one explicit continuous row")
    mission_types = rows(parse_native(HERE / "control-input.json"), "MissionType", "model")
    yes([(r["MTID"], r["NOS"], r["MNOS"], r["DURN"], r["MPAT"]) for r in mission_types] ==
        [("SUPPORT", 1, 1, 2.0, "CONTINUOUS"), ("EXECUTE", 1, 1, 4.0, "CONTINUOUS")], "mission settings")


def run(variant: str, path: Path) -> None:
    seal, inv, steps = (read(path / n) for n in ("closure.json", "invocation.json", "steps.json"))
    yes(seal["error"] is None and seal["run_id"] == path.name, f"{variant} closure success")
    yes(seal["invocation_sha256"] == sha(path / "invocation.json"), f"{variant} invocation seal")
    yes(seal["source_hashes_before"] == seal["source_hashes_after"], f"{variant} source stable")
    sources = seal["source_hashes_before"]
    yes(sources["input"] == EXPECTED[variant] and sources["parent"] == EXPECTED["parent"], f"{variant} input lineage")
    for key, file in (("contract", "contract.json"), ("builder", "build.py"),
                      ("exact_diff", "exact-diff.json"), ("diff_checker", "describe_diff.py"),
                      ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1")):
        yes(sources[key] == sha(HERE / file), f"{variant} sealed {key}")
    yes(inv["case_id"] == "A14" and inv["variant"] == variant and inv["execution_mode"] == "ssh_cli_v1", f"{variant} provenance")
    yes(inv["session_id"] == 0 and inv["ssh_connection_present"] and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, f"{variant} session/GUI")
    yes(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant} mutex")
    yes([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{variant} steps")
    yes(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{variant} step results")
    for name, item in seal["raw"].items():
        yes((path / name).stat().st_size == item["bytes"] and sha(path / name) == item["sha256"], f"{variant} raw {name}")
    yes(sha(path / "input.json") == EXPECTED[variant], f"{variant} copied input")
    rt = read(path / "roundtrip-validation.json")
    yes(rt["passed"] and not rt["differences"] and len(rt["populated_tables"]) == (13 if variant == "control" else 14), f"{variant} roundtrip")
    before, after = (populated(parse_native(path / file)) for file in ("input.json", "roundtrip-raw.json"))
    yes(all(after.get(k) == v for k, v in before.items()), f"{variant} business rows roundtrip")
    conversion = (path / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    yes("Input conversion completed. Errors: 0, Warnings: 2" in conversion, f"{variant} converter")
    yes("warning #108" in conversion and "warning #126" in conversion, f"{variant} warnings")
    yes((path / "model.sxo").stat().st_size > 1000, f"{variant} nonempty SXO")
    events = (path / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    report = parse_native(path / "report-raw.json")
    for name, air, duration in (("SUPPORT", 0, 2), ("EXECUTE", 1, 4)):
        yes(f"Time: 7 <TEACH-UNIT> mission ordered: {name}" in events, f"{variant} {name} order")
        yes(f"Time: 7 <{name},TEACH-UNIT,0,0,{air}> mission allocates system: <TEACH-AIR-01,{air}>" in events, f"{variant} {name} allocation")
        yes(f"Time: 8 <{name},TEACH-UNIT,0,0,{air}> mission starting, duration: {duration}" in events, f"{variant} {name} start")
    yes("Time: 10 <SUPPORT,TEACH-UNIT,0,0,0> mission success:" in events, f"{variant} support success")
    yes(events.count("mission starting,") == 2, f"{variant} two starts")
    if variant == "control":
        yes("Time: 12 <EXECUTE,TEACH-UNIT,0,0,1> mission success:" in events, "control execution success")
        yes("mission aborted:" not in events, "control no abort")
        yes(events.count("mission success:") == 2 and events.count("mission success,") == 2, "control success and arrival markers")
    else:
        yes("Time: 10 <EXECUTE,TEACH-UNIT,0,0,1> mission aborted:" in events, "dependent abort at predecessor end")
        yes("Time: 10 <EXECUTE,TEACH-UNIT,0,0,1> aborted mission completed:" in events, "dependent aborted completion")
        yes("Time: 12 <EXECUTE" not in events, "dependent no hour-12 success")
        yes(events.count("mission aborted:") == 1, "dependent single abort")
    yes("failure occurred" not in events.lower(), f"{variant} no random failure")
    summary, = rows(report, "ResultSummary")
    yes((summary["NREP"], summary["RTILW"], summary["RTIUP"]) == (1, 0, 16), f"{variant} report scope")
    expected_factor = 1.0 if variant == "control" else 2 / 3
    yes(abs(summary["MTMF"] - expected_factor) < 1e-6 and abs(summary["STMF"] - expected_factor) < 1e-6, f"{variant} completion factors")
    yes(summary["MSTF"] == summary["MSUF"] == 0, f"{variant} continuous excluded fixed factors")
    systems, stock = rows(report, "SystemResults"), rows(report, "StockTotalResults")
    yes(len(systems) == len(stock) == 32, f"{variant} 32 half-hour bins")
    for i, (sy, st) in enumerate(zip(systems, stock, strict=True)):
        hour = i / 2
        yes((sy["STINT"], sy["ETINT"], st["STINT"], st["ETINT"]) == (hour, hour + .5, hour, hour + .5), f"{variant} bin {i} alignment")
        operating = 2 if 8 <= hour < 10 else (1 if variant == "control" and 10 <= hour < 12 else 0)
        yes(sy["NSYMO"] == operating and sy["NSYMS"] == 0, f"{variant} bin {i} mission state")
        yes(sy["NSYA"] == 2 and sy["NSYRY"] + sy["NSYMA"] == 2, f"{variant} bin {i} aircraft ledger")
        yes(all(sy[k] == 0 for k in ("NREPT", "NPMT", "NFAIL", "NDAM", "NSYRP", "NSYPM", "NROBT", "NRCFG")), f"{variant} bin {i} no failure/maintenance")
        yes(all(st[k] == 0 for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), f"{variant} bin {i} no stock demand")
    yes(sum(sy["NSYMO"] * .5 for sy in systems) == (6 if variant == "control" else 4), f"{variant} aircraft operating hours")
    yes(systems[-1]["NSYRY"] == 2 and systems[-1]["NSYMA"] == 0, f"{variant} terminal ready")


def diagnostic() -> None:
    base = ROOT / "A14-continuous-mutual-v1.0.0" / "runs"
    runs = {v: base / f"a14-{v}-v100-20261001-01" for v in ("control", "oneway", "mutual", "opposing")}
    for variant, path in runs.items():
        seal = read(path / "closure.json")
        yes(seal["error"] is None and seal["source_hashes_before"] == seal["source_hashes_after"], f"diagnostic {variant} closed")
        yes(all(sha(path / name) == entry["sha256"] for name, entry in seal["raw"].items()), f"diagnostic {variant} raw seal")
    yes(sha(runs["mutual"] / "model.log") == sha(runs["opposing"] / "model.log"), "MUTD and opposing identical event logs")
    opposing = (runs["opposing"] / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    yes(opposing.count("mission starting,") == 2 and "Time: 8 <EXECUTE" in opposing, "opposing launched, deadlock hypothesis falsified")


def main() -> None:
    source()
    for variant, path in RUNS.items():
        run(variant, path)
    diagnostic()
    result = {
        "schema": "simlox-a14-continuous-end-abort-author-validation/v1",
        "passed": True, "checks": checks, "decision": "bounded_go_continuous_precedent_completion_abort",
        "runs": {v: p.name for v, p in RUNS.items()},
        "excluded_diagnostic": [f"a14-{v}-v100-20261001-01" for v in ("control", "oneway", "mutual", "opposing")],
        "finding": "The one explicit CONTINUOUS dependence row aborts EXECUTE at hour 10 when SUPPORT completes; without it EXECUTE succeeds at hour 12.",
        "limits": ["MUTD/deadlock hypothesis from v1.0.0 failed under coincident schedules and is not accepted.",
                   "DTTOL, suspension, regenerative gaps, hierarchy, cross-unit, GUI and cross-engine behavior unverified."],
    }
    output = HERE / "review" / "author-validation-2026-10-01.json"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"passed": True, "checks": checks, "decision": result["decision"]}))


if __name__ == "__main__":
    main()

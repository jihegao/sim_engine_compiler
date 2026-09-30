"""Independent, standard-library-only replay of A13.var02 sealed CLI evidence.

Reads frozen sources and raw runs; writes only the review JSON next to this file.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parent
STAMP = "2026-10-01"
OUT = HERE / f"independent-readonly-{STAMP}.json"
RUNS = {
    "control": "a13-var02-cross-control-v100-20261001-01",
    "dependency": "a13-var02-cross-dependency-v100-20261001-01",
}
FROZEN = {
    "contract": (CASE / "contract.json", "e7f95ad58b5b5c5319d3c3516b6677e902c144f5bcad481f8b1d975485a76244"),
    "builder": (CASE / "build.py", "f467574f6195d2ece54f9837c5678545cc48647115ebf5bae8cda98a2dec3f39"),
    "exact_diff": (CASE / "exact-diff.json", "427803769d7d122757ab1d8e35876688ce812dd06474dbe8cb8829ce4747f45a"),
    "diff_checker": (CASE / "describe_diff.py", "ff3d62aa9e309f89a1af98574a7b2883265a864f49e6a232571fc9cf12276515"),
    "checker": (CASE / "check_roundtrip.py", "1dcc721c0c9c0fdc7e9cc8c2a2c2e0147604b7fe20a2ac0c7810ca1a9b0628d2"),
    "runner_script": (CASE / "run_native_ssh.ps1", "90d269b4567b02291df1b5a2e756af58e99883aada39e076b38917c674d35bc5"),
    "parent": (ROOT / "A13-start-dependence-v1.0.0/dependent-input.json", "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"),
    "structure": (ROOT / "A17-multi-unit-group-v1.0.0/native-input.json", "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"),
    "input_control": (CASE / "control-input.json", "d3dc5b7a6cb59365b67c917dbc923283f3c8245b0f7547ffdbe5505a32ae9a03"),
    "input_dependency": (CASE / "dependency-input.json", "9bd317fdbd356c039c5db85dfb75077d78b1cb524cf52e845854e5754a30472a"),
    "simlox_exe": (Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"), "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path: Path):
    s = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        out = []
        quoted = escaped = False
        for i, ch in enumerate(s):
            if quoted:
                out.append(ch)
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    quoted = False
            elif ch == '"':
                quoted = True
                out.append(ch)
            elif ch == "," and s[i + 1 :].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(ch)
        return json.loads("".join(out))


def tables(doc, key):
    items = doc[key]["tables"]
    result = {t["name"]: t for t in items}
    if len(items) != len(result):
        raise ValueError("duplicate table names")
    return result


def rows(t):
    return [r for inst in t["instances"] for r in inst["rows"]]


def indexed(t):
    columns = [c["name"] for c in t["columns"]]
    return [dict(zip(columns, r)) for r in rows(t)]


class Replay:
    def __init__(self):
        self.check_count = 0
        self.failures = []
        self.details = {}

    def ck(self, condition, label):
        self.check_count += 1
        if not condition:
            self.failures.append(label)


def source_replay(r: Replay):
    for name, (path, expected) in FROZEN.items():
        r.ck(path.is_file() and sha(path) == expected, f"frozen fingerprint: {name}")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    r.ck(manual.is_file() and sha(manual) == "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3", "installed manual fingerprint")
    contract = native_json(CASE / "contract.json")
    r.ck(contract["variant_id"] == "A13.var02" and contract["version"] == "1.0.0-candidate", "contract identity")
    r.ck(contract["parent_input_sha256"] == FROZEN["parent"][1] and contract["structural_input_sha256"] == FROZEN["structure"][1], "contract lineage")
    docs = {name: native_json(path) for name, path in (("parent", FROZEN["parent"][0]), ("structure", FROZEN["structure"][0]), ("control", FROZEN["input_control"][0]), ("dependency", FROZEN["input_dependency"][0]))}
    tt = {k: tables(v, "model") for k, v in docs.items()}
    diff = native_json(CASE / "exact-diff.json")
    expected_changed = {"MissionDependence", "OperationProfile", "Operations", "ProblemDescription", "Station", "SystemDeployment", "Unit"}
    for name in RUNS:
        base, child = tt["parent"], tt[name]
        changed = {n for n in base.keys() | child.keys() if base.get(n) != child.get(n)}
        r.ck(changed == expected_changed, f"{name} exact changed table names")
        got = {n: {"before": base[n]["instances"] if n in base else None, "after": child[n]["instances"] if n in child else None} for n in sorted(changed)}
        frozen = diff["variants"][name]
        r.ck(got == frozen["changed_tables"] and sorted((base.keys() & child.keys()) - changed) == frozen["unchanged_tables"], f"{name} independently recomputed exact diff")
        r.ck(frozen["input_sha256"] == FROZEN[f"input_{name}"][1], f"{name} diff input fingerprint")
        for table in ("Station", "Unit", "SystemDeployment"):
            r.ck(child[table]["instances"] == tt["structure"][table]["instances"], f"{name} A17 {table} rows")
        r.ck(sum(bool(rows(t)) for t in child.values()) == (13 if name == "control" else 14), f"{name} source row-containing table count")
    pair_changes = {n for n in tt["control"].keys() | tt["dependency"].keys() if tt["control"].get(n) != tt["dependency"].get(n)}
    r.ck(pair_changes == {"ProblemDescription", "MissionDependence"}, "pair exact table difference")
    r.ck("MissionDependence" not in tt["control"] and indexed(tt["dependency"]["MissionDependence"]) == [{"DUNID": "TEACH-UNIT-2", "DMTID": "FOLLOW", "DSTIM": 10, "PUNID": "TEACH-UNIT", "PMTID": "RECON", "PSTIM": 8, "DTYPE": "START", "MUTD": None, "DTTOL": None, "NOTE": None}], "cross-unit START identity")
    r.ck(indexed(tt["dependency"]["SystemDeployment"])[0]["QTYPS"] == 1 and indexed(tt["dependency"]["SystemDeployment"])[1]["QTYPS"] == 1, "one aircraft per unit")
    r.details["source"] = {"changed_tables": sorted(expected_changed), "pair_changed_tables": sorted(pair_changes), "parent_sha256": FROZEN["parent"][1], "a17_sha256": FROZEN["structure"][1]}


def event_at(log: str, time: float, fragment: str) -> bool:
    return f"Time: {time:g} {fragment}" in log


def report_replay(r: Replay, name: str, report):
    t = tables(report, "report")
    r.ck(set(t) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{name} report tables")
    summary = indexed(t["ResultSummary"])
    r.ck(len(summary) == 1 and summary[0] == {"NREP": 1, "RTILW": 0, "RTIUP": 24, "MTMF": 1, "RSMTMF": 0, "MSTF": 1, "RSMSTF": 0, "MSUF": 1, "RSMSUF": 0, "STMF": 1, "RSSTMF": 0}, f"{name} summary factors")
    sys = indexed(t["SystemResults"])
    stock = indexed(t["StockTotalResults"])
    r.ck(len(sys) == len(stock) == 48, f"{name} 48 system and stock bins")
    for i in range(48):
        h = i / 2
        active = int(7 <= h < 12) + int(9 <= h < (12 if name == "control" else 14))
        operating = int(8 <= h < 12) + int((10 if name == "control" else 12) <= h < (12 if name == "control" else 14))
        prep = active - operating
        want = {"UNID": "Total over all Units", "SID": "Total over all Systems", "STINT": h, "ETINT": h + .5, "NSYRY": 2 - active, "NSYMA": active, "NSYMO": operating, "NSYMR": prep, "NSYA": 2, "FTMO": operating / 2, "STACC": operating}
        got = sys[i]
        for key, val in want.items():
            r.ck(got[key] == val, f"{name} system bin {i} {key}")
        r.ck(all(val in (0, None) for key, val in got.items() if key not in want), f"{name} system bin {i} other metrics zero")
        expected_stock = {"STINT": h, "ETINT": h + .5, "PNB": 1}
        r.ck(all(stock[i][key] == val for key, val in expected_stock.items()) and all(val in (0, None) for key, val in stock[i].items() if key not in expected_stock), f"{name} stock bin {i}")
    r.ck(sum(row["NSYMO"] * .5 for row in sys) == 6, f"{name} six aircraft operating hours")
    r.ck(sys[-1]["NSYRY"] == 2 and sys[-1]["NSYMA"] == 0, f"{name} terminal aircraft ready")
    r.details.setdefault("runs", {})[name]["metrics"] = {"system_bins": len(sys), "stock_bins": len(stock), "aircraft_operating_hours": sum(row["NSYMO"] * .5 for row in sys), "terminal_ready": sys[-1]["NSYRY"]}


def run_replay(r: Replay, name: str):
    run = CASE / "runs" / RUNS[name]
    inv = native_json(run / "invocation.json")
    closure = native_json(run / "closure.json")
    expected_hashes = {key: value[1] for key, value in FROZEN.items() if key not in ("input_control", "input_dependency")}
    expected_hashes["input"] = FROZEN[f"input_{name}"][1]
    expected_hashes["python"] = "372c2eae555b344520bf147be0096e009069aeca4e7f78d6aecea6d53158056a"
    r.ck(inv["variant"] == name and inv["run_id"] == RUNS[name] and closure["run_id"] == RUNS[name], f"{name} invocation identity")
    r.ck(inv["original_run_dir"].lower() == str(run).lower() and inv["publication_state"] == "not_published", f"{name} original run path and state")
    r.ck(inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"], f"{name} session-zero SSH")
    r.ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1 and bool(inv["gui"]["start_utc"]), f"{name} mutex and GUI guard")
    r.ck(closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None, f"{name} closure invocation and success")
    for key, expected in expected_hashes.items():
        r.ck(inv["source_hashes_before"].get(key) == expected and closure["source_hashes_before"].get(key) == expected and closure["source_hashes_after"].get(key) == expected, f"{name} source seal {key}")
    r.ck(inv["input_sha256"] == expected_hashes["input"] and inv["simlox_exe_sha256"] == expected_hashes["simlox_exe"], f"{name} primary invocation hashes")
    actual_raw = {p.name for p in run.iterdir() if p.is_file() and p.name not in ("invocation.json", "closure.json")}
    r.ck(set(closure["raw"]) == actual_raw, f"{name} closure complete raw list")
    for file, meta in closure["raw"].items():
        path = run / file
        r.ck(path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"{name} raw seal {file}")
    r.ck(sha(run / "input.json") == expected_hashes["input"], f"{name} copied input seal")
    steps = native_json(run / "steps.json")
    r.ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{name} five steps")
    for step in steps:
        r.ck(step["exit_code"] == 0 and step["gui_preserved"] is True and step["status"] == ("calc_observed" if step["name"] == "calc" else "completed") and step["error"] is None and step["started_utc"] <= step["completed_utc"], f"{name} step {step['name']}")
    r.ck(run.joinpath("model.sxo").stat().st_size > 4 and run.joinpath("model.sxi").stat().st_size > 4, f"{name} usable native artifacts")
    r.ck("Import completed!" in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace") and "Export completed!" in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"), f"{name} import export completion")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    r.ck("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc and "warning #108" in calc and "warning #126" in calc and "error #" not in calc.lower(), f"{name} converter result")
    before = tables(native_json(run / "input.json"), "model")
    after = tables(native_json(run / "roundtrip-raw.json"), "model")
    populated = {n: t for n, t in before.items() if rows(t)}
    r.ck(len(populated) == (13 if name == "control" else 14), f"{name} source row-containing count")
    for table, src in populated.items():
        r.ck(table in after and src["columns"] == after[table]["columns"] and src["instances"] == after[table]["instances"], f"{name} exact native roundtrip {table}")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    recon = "<RECON,TEACH-UNIT,0,0,0>"
    follow = "<FOLLOW,TEACH-UNIT-2,0,0,1>"
    for h, fragment in ((7, "<TEACH-UNIT> mission ordered: RECON"), (7, f"{recon} mission allocates system: <TEACH-AIR-01,0>"), (8, f"{recon} mission starting, duration: 4 : <TEACH-AIR-01,0>"), (9, "<TEACH-UNIT-2> mission ordered: FOLLOW"), (9, f"{follow} mission allocates system: <TEACH-AIR-01,1>"), (10 if name == "control" else 12, f"{follow} mission starting, duration: 2 : <TEACH-AIR-01,1>"), (12, f"{recon} mission success:"), (12, f"{recon} mission completed: <TEACH-AIR-01,0>"), (12 if name == "control" else 14, f"{follow} mission success:"), (12 if name == "control" else 14, f"{follow} mission completed: <TEACH-AIR-01,1>"), (12, "<TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>, mission success"), (12 if name == "control" else 14, "<TEACH-AIR-01,BASE-02,0> System arrives <TEACH-AIR-01,1>, mission success")):
        r.ck(event_at(log, h, fragment), f"{name} event {h} {fragment}")
    for h, unit, base, air in ((0, "TEACH-UNIT", "BASE-01", 0), (0, "TEACH-UNIT-2", "BASE-02", 1), (12, "TEACH-UNIT", "BASE-01", 0), (12 if name == "control" else 14, "TEACH-UNIT-2", "BASE-02", 1)):
        r.ck(event_at(log, h, f"<TEACH-AIR-01,{air}> nbr ready increased at unit: <{unit} at <{base},0>>"), f"{name} ready ledger {unit} at {h}")
    r.ck(not any(word in log.lower() for word in ("mission cancelled", "mission failed", "failure occurs", "shortage")), f"{name} no adverse mission event")
    r.ck(len(re.findall(r"mission starting, duration:", log)) == 2 and len(re.findall(r"mission success:", log)) == 2 and len(re.findall(r"System arrives", log)) == 2, f"{name} two missions and returns")
    r.details.setdefault("runs", {})[name] = {"run_id": RUNS[name], "closure_sha256": sha(run / "closure.json"), "invocation_sha256": sha(run / "invocation.json"), "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "follow_launch_hour": 10 if name == "control" else 12}
    report_replay(r, name, native_json(run / "report-raw.json"))


def main():
    r = Replay()
    try:
        source_replay(r)
        for name in RUNS:
            run_replay(r, name)
    except Exception as exc:
        r.failures.append(f"replay exception: {type(exc).__name__}: {exc}")
    result = {"schema": "simlox-a13-var02-independent-readonly/v1", "passed": not r.failures, "verdict": "GO" if not r.failures else "NO-GO", "check_count": r.check_count, "failures": r.failures, "details": r.details, "scope": "one fixed-seed pair of two explicit units; observed cross-unit START launch delay", "limits": ["Displayed hour-12 RECON success, FOLLOW start, RECON completion and BASE-01 arrival do not establish strict internal return-before-launch order.", "Unit-group-owned dependence, failure, repeated identity, other seeds, GUI visual behavior and cross-engine parity are untested."]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "check_count": r.check_count, "failures": r.failures, "report": str(OUT)}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

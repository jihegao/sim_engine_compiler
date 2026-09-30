"""Independent standard-library replay of sealed group-owned START runs."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
OUT = CASE / "review/independent-readonly-2026-10-01.json"
IDS = {v: f"a13-var02-group-{v}-v100-20261001-01" for v in ("control", "dependency")}
SOURCE = {"control": "92c0687d1e62b2aa0e8168b3ca764eb2dedd67869fb94ae8efa61085934a26a1", "dependency": "faddaf0834483c8ba842b5e0f97c2c4b6bcd737612ec0bafaa10677e30ec4475"}
PARENT = ROOT / "A13-var02-cross-unit-start-v1.0.0/dependency-input.json"
A17 = ROOT / "A17-multi-unit-group-v1.0.0/native-input.json"
FROZEN = {
    "parent": (PARENT, "9bd317fdbd356c039c5db85dfb75077d78b1cb524cf52e845854e5754a30472a"),
    "structure": (A17, "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"),
    "contract": (CASE / "contract.json", "9352f2bbfe8f241911106289df97d3c9f85b3e9a1fafb48f2e6225345820228c"),
    "builder": (CASE / "build.py", "2eb4211a1a1c321ae27e65a7b228588d7ec6e0412b174db3d954d20e9c92db95"),
    "exact_diff": (CASE / "exact-diff.json", "94dc9640f0467d7cb7ad2f29299b0149d3ed2eba5880d0968c391c5a38ac3d9b"),
    "diff_checker": (CASE / "describe_diff.py", "bfb41f735c1f35c49947dc6169ab70969efd3c14d9160c859717b72f91189241"),
    "checker": (CASE / "check_roundtrip.py", "29dfe0b0a4b875f0e687d7c2ac03d01c2b307d5fd57b5d8935bf69b6399cc16a"),
    "validator": (CASE / "validate.py", "f35cf15d21b606dcd626c95bd4ec9c782890029c1ea63b50c2caa47e00c6372a"),
    "runner_script": (CASE / "run_native_ssh.ps1", "c25a2033107c116e9c8ca7ed3b18c5d84e69cbe3b3177d35952971f5aac3b5de"),
    "simlox_exe": (Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"), "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"),
    "python": (Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"), "372c2eae555b344520bf147be0096e009069aeca4e7f78d6aecea6d53158056a"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path):
    text = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        out, quote, escape = [], False, False
        for i, ch in enumerate(text):
            if quote:
                out.append(ch)
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    quote = False
            elif ch == '"':
                quote = True
                out.append(ch)
            elif ch == "," and text[i + 1 :].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(ch)
        return json.loads("".join(out))


def tabs(doc, key):
    seq = doc[key]["tables"]
    d = {t["name"]: t for t in seq}
    if len(d) != len(seq):
        raise ValueError("duplicate table")
    return d


def rows(t):
    return [r for i in t["instances"] for r in i["rows"]]


def records(t):
    cols = [c["name"] for c in t["columns"]]
    if any(len(row) != len(cols) for row in rows(t)):
        raise ValueError("nonrectangular table")
    return [dict(zip(cols, row)) for row in rows(t)]


class Audit:
    def __init__(self):
        self.count = 0
        self.failures = []
        self.runs = {}

    def ck(self, condition, message):
        self.count += 1
        if not condition:
            self.failures.append(message)


def source_checks(a):
    for key, (path, expected) in FROZEN.items():
        a.ck(path.is_file() and sha(path) == expected, f"frozen {key} hash")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    a.ck(manual.is_file() and sha(manual) == "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3", "manual hash")
    c = parse(CASE / "contract.json")
    a.ck(c["variant_id"] == "A13.var02" and c["parent_input_sha256"] == FROZEN["parent"][1] and c["structural_input_sha256"] == FROZEN["structure"][1], "contract identity and lineage")
    sources = {name: tabs(parse(path), "model") for name, path in (("parent", PARENT), ("a17", A17), ("control", CASE / "control-input.json"), ("dependency", CASE / "dependency-input.json"))}
    diff = parse(CASE / "exact-diff.json")
    expected = {"MissionDependence", "MissionType", "Operations", "ProblemDescription", "Station", "SystemDeployment", "Unit", "UnitGroup", "UnitGroupMember"}
    for v in IDS:
        path = CASE / f"{v}-input.json"
        a.ck(sha(path) == SOURCE[v], f"{v} input hash")
        x, base = sources[v], sources["parent"]
        changed = {n for n in x.keys() | base.keys() if x.get(n) != base.get(n)}
        a.ck(changed == expected, f"{v} exact changed tables")
        calculated = {n: {"before": base[n]["instances"] if n in base else None, "after": x[n]["instances"] if n in x else None} for n in sorted(changed)}
        frozen = diff["variants"][v]
        a.ck(calculated == frozen["changed_tables"] and sorted((x.keys() & base.keys()) - changed) == frozen["unchanged_tables"] and frozen["input_sha256"] == SOURCE[v], f"{v} exact saved diff")
        a.ck(sum(bool(rows(t)) for t in x.values()) == (15 if v == "control" else 16), f"{v} row-containing count")
        for n in ("UnitGroup", "UnitGroupMember"):
            a.ck(x[n] == sources["a17"][n], f"{v} A17 {n}")
        for n in ("Station", "Unit", "SystemDeployment"):
            a.ck(x[n]["columns"] == sources["a17"][n]["columns"] and rows(x[n])[:2] == rows(sources["a17"][n]) and len(rows(x[n])) == 3, f"{v} A17 {n} and third row")
        a.ck([(z["UNID"], z["STID"]) for z in records(x["Unit"])] == [("TEACH-UNIT", "BASE-01"), ("TEACH-UNIT-2", "BASE-02"), ("TEACH-UNIT-3", "BASE-03")], f"{v} unit base topology")
        a.ck([(z["USTID"], z["QTYPS"]) for z in records(x["SystemDeployment"])] == [("TEACH-UNIT", 1), ("TEACH-UNIT-2", 1), ("TEACH-UNIT-3", 1)], f"{v} three aircraft deployment")
        a.ck([(z["USTID"], z["PRID"]) for z in records(x["Operations"])] == [("TEACH-GROUP", "RECON-SCHEDULE"), ("TEACH-UNIT-3", "FOLLOW-SCHEDULE")], f"{v} operation owners")
        a.ck(next(z for z in records(x["MissionType"]) if z["MTID"] == "RECON")["NOS"] == 2 and next(z for z in records(x["MissionType"]) if z["MTID"] == "RECON")["MNOS"] == 2, f"{v} two RECON aircraft required")
    pair = {n for n in sources["control"].keys() | sources["dependency"].keys() if sources["control"].get(n) != sources["dependency"].get(n)}
    a.ck(pair == {"ProblemDescription", "MissionDependence"} and "MissionDependence" not in sources["control"], "pair-only dependence and description")
    dep = records(sources["dependency"]["MissionDependence"])
    a.ck(len(dep) == 1 and tuple(dep[0][n] for n in ("DUNID", "DMTID", "DSTIM", "PUNID", "PMTID", "PSTIM", "DTYPE")) == ("TEACH-UNIT-3", "FOLLOW", 10, "TEACH-GROUP", "RECON", 8, "START"), "group-owned START key")
    a.ck(diff["parent_sha256"] == FROZEN["parent"][1] and diff["structural_source_sha256"] == FROZEN["structure"][1], "diff lineage")


def event(log, hour, fragment):
    return f"Time: {hour:g} {fragment}" in log


def report_checks(a, v, report):
    t = tabs(report, "report")
    a.ck(set(t) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{v} report tables")
    a.ck(records(t["ResultSummary"]) == [{"NREP": 1, "RTILW": 0, "RTIUP": 24, "MTMF": 1, "RSMTMF": 0, "MSTF": 1, "RSMSTF": 0, "MSUF": 1, "RSMSUF": 0, "STMF": 1, "RSSTMF": 0}], f"{v} summary")
    sy, st = records(t["SystemResults"]), records(t["StockTotalResults"])
    a.ck(len(sy) == len(st) == 48, f"{v} 48 system and stock bins")
    end = 12 if v == "control" else 14
    launch = 10 if v == "control" else 12
    for i, (x, y) in enumerate(zip(sy, st)):
        h = i / 2
        assigned = 2 * int(7 <= h < 12) + int(9 <= h < end)
        operating = 2 * int(8 <= h < 12) + int(launch <= h < end)
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems", "STINT": h, "ETINT": h + .5, "NSYRY": 3 - assigned, "NSYMA": assigned, "NSYMO": operating, "NSYMR": assigned - operating, "NSYA": 3, "STACC": operating}
        for key, val in expected.items():
            a.ck(x[key] == val, f"{v} system bin {i} {key}")
        a.ck(abs(x["FTMO"] - operating / 3) < 1e-6, f"{v} system bin {i} FTMO")
        a.ck(all(val in (0, None) for key, val in x.items() if key not in expected and key != "FTMO"), f"{v} system bin {i} remaining metrics")
        stock_expected = {"STINT": h, "ETINT": h + .5, "PNB": 1}
        a.ck(all(y[key] == val for key, val in stock_expected.items()) and all(val in (0, None) for key, val in y.items() if key not in stock_expected), f"{v} stock bin {i}")
    a.ck(sum(.5 * x["NSYMO"] for x in sy) == 10 and sum(.5 * x["NSYMA"] for x in sy) == (13 if v == "control" else 15), f"{v} operating and assigned integrals")
    a.ck(sy[-1]["NSYRY"] == 3 and sy[-1]["NSYMA"] == sy[-1]["NSYMO"] == 0, f"{v} terminal three ready")
    return t


def run_checks(a, v):
    run = CASE / "runs" / IDS[v]
    inv, clo, steps = (parse(run / f) for f in ("invocation.json", "closure.json", "steps.json"))
    expected = {n: digest for n, (_, digest) in FROZEN.items()}
    expected["input"] = SOURCE[v]
    a.ck(inv["run_id"] == clo["run_id"] == IDS[v] and inv["variant"] == v and inv["variant_id"] == "A13.var02", f"{v} identity")
    a.ck(inv["original_run_dir"].lower() == str(run).lower() and inv["publication_state"] == "not_published", f"{v} raw location")
    a.ck(inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"], f"{v} session0 SSH")
    a.ck(inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1 and bool(inv["gui"]["start_utc"]), f"{v} mutex and GUI")
    a.ck(clo["invocation_sha256"] == sha(run / "invocation.json") and clo["error"] is None, f"{v} closure seal and status")
    for key, digest in expected.items():
        a.ck(inv["source_hashes_before"].get(key) == digest and clo["source_hashes_before"].get(key) == digest and clo["source_hashes_after"].get(key) == digest, f"{v} source seal {key}")
    a.ck(inv["input_sha256"] == SOURCE[v] and inv["validator_sha256"] == expected["validator"] and sha(run / "input.json") == SOURCE[v], f"{v} invocation and copied input hashes")
    files = {p.name for p in run.iterdir() if p.is_file() and p.name not in ("invocation.json", "closure.json")}
    a.ck(set(clo["raw"]) == files, f"{v} raw closure coverage")
    for file, meta in clo["raw"].items():
        p = run / file
        a.ck(p.stat().st_size == meta["bytes"] and sha(p) == meta["sha256"], f"{v} raw hash {file}")
    a.ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{v} five steps")
    for s in steps:
        a.ck(s["exit_code"] == 0 and s["gui_preserved"] is True and s["status"] == ("calc_observed" if s["name"] == "calc" else "completed") and s["error"] is None and s["started_utc"] <= s["completed_utc"], f"{v} step {s['name']}")
    a.ck((run / "model.sxi").stat().st_size > 4 and (run / "model.sxo").stat().st_size > 4, f"{v} native artifacts")
    a.ck("Import completed!" in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace") and "Export completed!" in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"), f"{v} import export completion")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    a.ck("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc and sorted(map(int, re.findall(r"warning #(\d+)", calc))) == [108, 126] and not re.search(r"error #\d+", calc, re.I) and "Saving results" in calc, f"{v} conversion and calculation")
    before, after = tabs(parse(run / "input.json"), "model"), tabs(parse(run / "roundtrip-raw.json"), "model")
    populated = {n: t for n, t in before.items() if rows(t)}
    a.ck(len(populated) == (15 if v == "control" else 16), f"{v} row-containing source count")
    for n, t in populated.items():
        a.ck(n in after and t["columns"] == after[n]["columns"] and t["instances"] == after[n]["instances"], f"{v} roundtrip {n}")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    recon, follow = "<RECON,TEACH-GROUP,0,0,0>", "<FOLLOW,TEACH-UNIT-3,0,0,1>"
    launch, end = (10, 12) if v == "control" else (12, 14)
    events = [(7, "<TEACH-GROUP> mission ordered: RECON"), (7, f"{recon} mission allocates system: <TEACH-AIR-01,0>"), (7, f"{recon} mission allocates system: <TEACH-AIR-01,1>"), (8, f"{recon} mission starting, duration: 4 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>"), (9, "<TEACH-UNIT-3> mission ordered: FOLLOW"), (9, f"{follow} mission allocates system: <TEACH-AIR-01,2>"), (launch, f"{follow} mission starting, duration: 2 : <TEACH-AIR-01,2>"), (12, f"{recon} mission success:"), (12, f"{recon} mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>"), (end, f"{follow} mission success:"), (end, f"{follow} mission completed: <TEACH-AIR-01,2>")]
    for h, fragment in events:
        a.ck(event(log, h, fragment), f"{v} event {h} {fragment}")
    for aircraft, unit, base, return_hour in ((0, "TEACH-UNIT", "BASE-01", 12), (1, "TEACH-UNIT-2", "BASE-02", 12), (2, "TEACH-UNIT-3", "BASE-03", end)):
        a.ck(event(log, 0, f"<TEACH-AIR-01,{aircraft}> nbr ready increased at unit: <{unit} at <{base},0>>"), f"{v} initial {unit} ready")
        a.ck(event(log, return_hour, f"<TEACH-AIR-01,{base},0> System arrives <TEACH-AIR-01,{aircraft}>, mission success"), f"{v} {unit} return")
        a.ck(event(log, return_hour, f"<TEACH-AIR-01,{aircraft}> nbr ready increased at unit: <{unit} at <{base},0>>"), f"{v} terminal {unit} ready")
    a.ck(len(re.findall(r"mission starting, duration:", log)) == len(re.findall(r"mission success:", log)) == len(re.findall(r"mission completed:", log)) == 2 and len(re.findall(r"System arrives", log)) == 3, f"{v} mission and return cardinality")
    a.ck(not re.search(r"mission (?:abort|cancel|fail)|shortage|failure occurs", log, re.I), f"{v} no adverse event")
    report = parse(run / "report-raw.json")
    table = report_checks(a, v, report)
    a.runs[v] = {"run_id": IDS[v], "closure_sha256": sha(run / "closure.json"), "invocation_sha256": sha(run / "invocation.json"), "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "follow_launch_hour": launch, "system_bins": 48, "stock_bins": 48, "operating_aircraft_hours": 10, "assigned_aircraft_hours": 13 if v == "control" else 15, "terminal_ready": 3}
    return table


def main():
    a = Audit()
    try:
        source_checks(a)
        reports = {v: run_checks(a, v) for v in IDS}
        changes = {n for n in reports["control"] if reports["control"][n] != reports["dependency"][n]}
        a.ck(changes == {"ProblemDescription", "SystemResults"}, "paired report table difference")
        a.ck(reports["control"]["ResultSummary"] == reports["dependency"]["ResultSummary"] and reports["control"]["StockTotalResults"] == reports["dependency"]["StockTotalResults"], "paired summary and stock equality")
    except Exception as exc:
        a.failures.append(f"exception: {type(exc).__name__}: {exc}")
    result = {"schema": "simlox-a13-var02-group-owned-independent-readonly/v1", "passed": not a.failures, "verdict": "GO" if not a.failures else "NO-GO", "check_count": a.count, "failures": a.failures, "runs": a.runs, "scope": "one fixed-seed pair with a two-member group-owned RECON precedent and third explicit-unit FOLLOW dependent", "limits": ["Displayed hour-12 success, dependent start, precedent completion and arrivals do not prove strict internal return-before-launch ordering.", "No failure, repeated identity, implicit unit, other seed, GUI visual, or cross-engine claim."]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "check_count": a.count, "failures": a.failures, "report": str(OUT)}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

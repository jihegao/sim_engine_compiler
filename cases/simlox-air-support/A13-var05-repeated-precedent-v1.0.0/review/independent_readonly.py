"""Independent standard-library replay of the A13.var05 sealed native pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
OUT = CASE / "review/independent-readonly-2026-10-01.json"
IDS = {v: f"a13-var05-repeat-{v}-v100-20261001-01" for v in ("control", "dependency")}
SOURCE = {"control": "7ce565e2d9644f25560de726d983bab4b8d647f6352b1857a9b2b03d0b61f73b", "dependency": "155e83d3ffc24d51784ec892f296bed8df505a379eb7b3e3ca72218e9aa88dff"}
FROZEN = {
    "parent": (ROOT / "A13-start-dependence-v1.0.0/dependent-input.json", "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"),
    "structure": (ROOT / "A13-var01-multiple-predecessors-v1.0.0/multiple-input.json", "1d2226850d07d7caf5f58e825bb2d3fdf498f7626fb58e4a6ed4bcfa469d18ae"),
    "contract": (CASE / "contract.json", "58672696dfcdba1aca2d0753d8d9f75675f567c151922d61999b30b9a9f0e086"),
    "builder": (CASE / "build.py", "533c42534363fd5eaf4e2e378b53b9e30fa83ca267bc9e2375920c52d1b4f601"),
    "exact_diff": (CASE / "exact-diff.json", "d6b41991865d494b88fe031695a5737cafa67cd8f9bccf9d6f678ffcd37d7b01"),
    "diff_checker": (CASE / "describe_diff.py", "d7b57d517c5d31c895e5ae80ce600238eb40acaf0c8ba3bcfbf2afdefe0f0ee6"),
    "checker": (CASE / "check_roundtrip.py", "1001c03ab39396f05cc9e40f2c989660ec650287d903dee99effb543980c651b"),
    "validator": (CASE / "validate.py", "e6842a9e66ce529a85615d11188b3c002a687a6c2420d0e591e83f46b86537ae"),
    "runner_script": (CASE / "run_native_ssh.ps1", "e00a1ac3eea1024186e16a2c42a568e87a2ef62aabae4bd56a52c122022e55de"),
    "python": (Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"), "372c2eae555b344520bf147be0096e009069aeca4e7f78d6aecea6d53158056a"),
    "simlox_exe": (Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"), "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path):
    s = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        out, quoted, esc = [], False, False
        for i, ch in enumerate(s):
            if quoted:
                out.append(ch)
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
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


def tables(doc, root):
    seq = doc[root]["tables"]
    result = {x["name"]: x for x in seq}
    if len(result) != len(seq):
        raise ValueError("duplicate table")
    return result


def rows(table):
    return [r for i in table["instances"] for r in i["rows"]]


def records(table):
    cols = [c["name"] for c in table["columns"]]
    if any(len(r) != len(cols) for r in rows(table)):
        raise ValueError("nonrectangular table")
    return [dict(zip(cols, r)) for r in rows(table)]


class Audit:
    def __init__(self):
        self.n = 0
        self.failures = []
        self.details = {}

    def ck(self, yes, label):
        self.n += 1
        if not yes:
            self.failures.append(label)


def source_checks(a):
    for name, (path, digest) in FROZEN.items():
        a.ck(path.is_file() and sha(path) == digest, f"frozen {name}")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    a.ck(manual.is_file() and sha(manual) == "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3", "manual seal")
    contract = parse(CASE / "contract.json")
    a.ck(contract["variant_id"] == "A13.var05" and contract["parent_input_sha256"] == FROZEN["parent"][1] and contract["structural_input_sha256"] == FROZEN["structure"][1] and 274 in contract["source"]["pages"], "contract identity, lineage and IPER manual page")
    docs = {n: tables(parse(p), "model") for n, p in (("parent", FROZEN["parent"][0]), ("donor", FROZEN["structure"][0]), ("control", CASE / "control-input.json"), ("dependency", CASE / "dependency-input.json"))}
    saved = parse(CASE / "exact-diff.json")
    for v in IDS:
        child, parent = docs[v], docs["parent"]
        a.ck(sha(CASE / f"{v}-input.json") == SOURCE[v], f"{v} input fingerprint")
        changed = {n for n in child.keys() | parent.keys() if child.get(n) != parent.get(n)}
        a.ck(changed == ({"MissionDependence", "OperationProfile", "ProblemDescription", "SystemDeployment"} if v == "control" else {"OperationProfile", "ProblemDescription", "SystemDeployment"}), f"{v} exact parent delta")
        computed = {n: {"before": parent[n]["instances"] if n in parent else None, "after": child[n]["instances"] if n in child else None} for n in sorted(changed)}
        a.ck(computed == saved["variants"][v]["changed_tables"] and sorted((child.keys() & parent.keys()) - changed) == saved["variants"][v]["unchanged_tables"] and saved["variants"][v]["input_sha256"] == SOURCE[v], f"{v} saved diff equality")
        a.ck(sum(bool(rows(t)) for t in child.values()) == (13 if v == "control" else 14), f"{v} row-containing count")
        a.ck(child["SystemDeployment"] == docs["donor"]["SystemDeployment"], f"{v} three-aircraft donor")
        a.ck([(r["SPRID"], r["STIM"], r["IQTY"], r["IPER"]) for r in records(child["OperationProfile"])] == [("RECON", 8, 2, 0), ("FOLLOW", 10, 1, 0)], f"{v} same-time RECON profile")
    pair = {n for n in docs["control"].keys() | docs["dependency"].keys() if docs["control"].get(n) != docs["dependency"].get(n)}
    a.ck(pair == {"ProblemDescription", "MissionDependence"} and "MissionDependence" not in docs["control"], "pair-only dependence and description")
    dep = records(docs["dependency"]["MissionDependence"])
    a.ck(len(dep) == 1 and tuple(dep[0][k] for k in ("DUNID", "DMTID", "DSTIM", "PUNID", "PMTID", "PSTIM", "DTYPE")) == ("TEACH-UNIT", "FOLLOW", 10, "TEACH-UNIT", "RECON", 8, "START"), "ambiguous START key")
    a.ck(saved["parent_sha256"] == FROZEN["parent"][1] and saved["structural_source_sha256"] == FROZEN["structure"][1], "diff lineage")


def shared(a, v):
    p = CASE / "runs" / IDS[v]
    inv, clo, steps = (parse(p / n) for n in ("invocation.json", "closure.json", "steps.json"))
    expected = {k: digest for k, (_, digest) in FROZEN.items()}
    expected["input"] = SOURCE[v]
    a.ck(inv["run_id"] == clo["run_id"] == IDS[v] and inv["variant"] == v and inv["variant_id"] == "A13.var05", f"{v} run identity")
    a.ck(inv["original_run_dir"].lower() == str(p).lower() and inv["publication_state"] == "not_published", f"{v} run location")
    a.ck(inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"], f"{v} session0 SSH")
    a.ck(inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1 and bool(inv["gui"]["start_utc"]), f"{v} mutex GUI")
    a.ck(clo["invocation_sha256"] == sha(p / "invocation.json") and clo["error"] is None, f"{v} invocation closure")
    for key, digest in expected.items():
        a.ck(inv["source_hashes_before"].get(key) == digest and clo["source_hashes_before"].get(key) == digest and clo["source_hashes_after"].get(key) == digest, f"{v} frozen source {key}")
    a.ck(inv["input_sha256"] == SOURCE[v] and inv["validator_sha256"] == expected["validator"] and sha(p / "input.json") == SOURCE[v], f"{v} input and validator pins")
    raw = {q.name for q in p.iterdir() if q.is_file() and q.name not in ("invocation.json", "closure.json")}
    a.ck(set(clo["raw"]) == raw, f"{v} raw set")
    for name, meta in clo["raw"].items():
        q = p / name
        a.ck(q.stat().st_size == meta["bytes"] and sha(q) == meta["sha256"], f"{v} raw seal {name}")
    a.ck([s["name"] for s in steps[:3]] == ["import", "export", "calc"] and [s["status"] for s in steps[:3]] == ["completed", "completed", "calc_observed"], f"{v} first three native steps")
    for s in steps:
        a.ck(s["exit_code"] == 0 and s["gui_preserved"] is True and s["error"] is None and s["started_utc"] <= s["completed_utc"], f"{v} guarded step {s['name']}")
    a.ck((p / "model.sxi").stat().st_size > 4 and "Import completed!" in (p / "import.log").read_text(encoding="utf-8-sig", errors="replace") and "Export completed!" in (p / "export.log").read_text(encoding="utf-8-sig", errors="replace"), f"{v} import/export")
    before, after = tables(parse(p / "input.json"), "model"), tables(parse(p / "roundtrip-raw.json"), "model")
    occupied = {n: t for n, t in before.items() if rows(t)}
    a.ck(len(occupied) == (13 if v == "control" else 14), f"{v} native source table count")
    for name, t in occupied.items():
        a.ck(name in after and t["columns"] == after[name]["columns"] and t["instances"] == after[name]["instances"], f"{v} native roundtrip {name}")
    a.details[v] = {"run_id": IDS[v], "closure_sha256": sha(p / "closure.json"), "invocation_sha256": sha(p / "invocation.json"), "run_log_sha256": sha(p / "run.log")}
    return p, inv, steps, (p / "run.log").read_text(encoding="utf-8-sig", errors="replace")


def control(a):
    p, inv, steps, calc = shared(a, "control")
    a.ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and [s["status"] for s in steps] == ["completed", "completed", "calc_observed", "completed", "completed"], "control five complete steps")
    a.ck("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc and sorted(map(int, re.findall(r"warning #(\d+)", calc))) == [108, 126] and not re.search(r"error #\d+", calc, re.I) and "Saving results" in calc, "control clean conversion")
    a.ck((p / "model.sxo").stat().st_size > 4 and (p / "report-raw.json").stat().st_size > 4 and (p / "model.log").stat().st_size > 4, "control valid simulation files")
    log = (p / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    mapping = {"<RECON,TEACH-UNIT,0,0,0>": 0, "<RECON,TEACH-UNIT,0,0,1>": 1, "<FOLLOW,TEACH-UNIT,0,0,2>": 2}
    for mission, air in mapping.items():
        kind = "RECON" if air in (0, 1) else "FOLLOW"
        alloc, launch = (7, 8) if kind == "RECON" else (9, 10)
        for h, phrase in ((alloc, f"{mission} mission allocates system: <TEACH-AIR-01,{air}>"), (launch, f"{mission} mission starting, duration: {4 if kind == 'RECON' else 2} : <TEACH-AIR-01,{air}>"), (12, f"{mission} mission success:"), (12, f"{mission} mission completed: <TEACH-AIR-01,{air}>"), (12, f"<TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,{air}>, mission success")):
            a.ck(f"Time: {h:g} {phrase}" in log, f"control {mission} event {h} {phrase}")
        a.ck(f"Time: 0 <TEACH-AIR-01,{air}> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>" in log and f"Time: 12 <TEACH-AIR-01,{air}> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>" in log, f"control aircraft {air} ready ledger")
    a.ck(len(re.findall(r"mission ordered: RECON", log)) == 2 and len(re.findall(r"mission starting, duration:", log)) == len(re.findall(r"mission success:", log)) == len(re.findall(r"mission completed:", log)) == 3 and len(re.findall(r"System arrives", log)) == 3 and not re.search(r"mission (?:abort|cancel|fail)|shortage|failure occurs", log, re.I), "control three distinct successful missions")
    report = tables(parse(p / "report-raw.json"), "report")
    a.ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "control report table set")
    a.ck(records(report["ResultSummary"]) == [{"NREP": 1, "RTILW": 0, "RTIUP": 24, "MTMF": 1, "RSMTMF": 0, "MSTF": 1, "RSMSTF": 0, "MSUF": 1, "RSMSUF": 0, "STMF": 1, "RSSTMF": 0}], "control summary factors")
    sy, st = records(report["SystemResults"]), records(report["StockTotalResults"])
    a.ck(len(sy) == len(st) == 48, "control 48 system/stock bins")
    for i, (x, y) in enumerate(zip(sy, st)):
        h = i / 2
        assigned = 2 * int(7 <= h < 12) + int(9 <= h < 12)
        operating = 2 * int(8 <= h < 12) + int(10 <= h < 12)
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems", "STINT": h, "ETINT": h + .5, "NSYRY": 3 - assigned, "NSYMA": assigned, "NSYMO": operating, "NSYMR": assigned - operating, "NSYA": 3, "STACC": operating}
        for key, val in expected.items():
            a.ck(x[key] == val, f"control bin {i} {key}")
        a.ck(abs(x["FTMO"] - operating / 3) < 1e-6 and all(z in (0, None) for k, z in x.items() if k not in expected and k != "FTMO"), f"control bin {i} remaining system metrics")
        expected_stock = {"STINT": h, "ETINT": h + .5, "PNB": 1}
        a.ck(all(y[k] == z for k, z in expected_stock.items()) and all(z in (0, None) for k, z in y.items() if k not in expected_stock), f"control bin {i} stock")
    a.ck(sum(.5 * x["NSYMO"] for x in sy) == 10 and sum(.5 * x["NSYMA"] for x in sy) == 13 and sy[-1]["NSYRY"] == 3, "control integrals and terminal ready")
    a.details["control"].update({"model_log_sha256": sha(p / "model.log"), "report_sha256": sha(p / "report-raw.json"), "mission_ids": sorted(mapping), "operating_aircraft_hours": 10, "assigned_aircraft_hours": 13, "terminal_ready": 3})


def dependency(a):
    p, inv, steps, calc = shared(a, "dependency")
    a.ck([s["name"] for s in steps] == ["import", "export", "calc", "check_import_export"] and [s["status"] for s in steps] == ["completed", "completed", "calc_observed", "completed"], "dependency four guarded steps and no report")
    a.ck("Input conversion completed. Errors: 1, Warnings: 2, Notes: 0" in calc and sorted(map(int, re.findall(r"warning #(\d+)", calc))) == [108, 126], "dependency converter totals")
    errors = re.findall(r"\(error #(\d+)\)\s*([^\r\n]*)", calc)
    a.ck(errors == [("222", "Duplicate precedent missions found at the unit: TEACH-UNIT / RECON / 8.000000")], "dependency exact #222 diagnostic")
    a.ck(re.search(r"Form: MissionDependence\s+rec 1: \(error #222\)", calc) is not None, "dependency error form and record")
    a.ck((p / "model.sxo").stat().st_size == 4 and not (p / "model.log").exists() and not (p / "report-raw.json").exists() and not (p / "report-export.log").exists(), "dependency invalid SXO and no simulation/report")
    a.details["dependency"].update({"sxo_bytes": 4, "converter_errors": 1, "error_code": 222, "error_text": errors[0][1] if errors else None, "behavior_status": "no simulation behavior accepted"})


def main():
    a = Audit()
    try:
        source_checks(a)
        control(a)
        dependency(a)
    except Exception as exc:
        a.failures.append(f"exception: {type(exc).__name__}: {exc}")
    result = {"schema": "simlox-a13-var05-independent-readonly/v1", "passed": not a.failures, "verdict": "GO" if not a.failures else "NO-GO", "check_count": a.n, "failures": a.failures, "runs": a.details, "scope": "installed SIMLOX version: IQTY=2/IPER=0 control produces two same-time RECON missions; matching START key is rejected by converter #222", "limits": ["Converter-rejected dependency has no mission behavior or report to accept.", "No claim for other repetition counts, periods, units, mission types, engines, or GUI visual behavior."]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "check_count": a.n, "failures": a.failures, "report": str(OUT)}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

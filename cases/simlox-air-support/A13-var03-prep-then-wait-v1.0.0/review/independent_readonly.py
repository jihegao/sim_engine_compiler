"""Independent read-only replay for fresh A13.var03 v1.0.0 pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
OUT = CASE / "review/independent-readonly-2026-10-01.json"
IDS = {v: f"a13-var03-prep-{v}-v100-20261001-02" for v in ("control", "dependency")}
SOURCE = {"control": "2ccbd3af8ce6a892572b7a3e89ae83cff2bbecdf6215959f4d1c2e13b8463f8e", "dependency": "36782317de6c04583ce8be4eb076f6cac2f8819d1fb1ac652ee9425f0bbbc873"}
FROZEN = {
    "parent": (ROOT / "A13-start-dependence-v1.0.0/dependent-input.json", "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"),
    "structure": (ROOT / "B01-fixed-preparation-v1.0.1/native-input.json", "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"),
    "contract": (CASE / "contract.json", "d4d7b5677af21644e12d37d38791305b6c353c3ab63686972a112f25272197b7"),
    "builder": (CASE / "build.py", "88cc02ff0552065fb56be50f0cff124f77531e91133939272261d03093340de1"),
    "exact_diff": (CASE / "exact-diff.json", "1b136fde29fa10abed7bc1692d229ce6c1f2070075bc50225d4a2eef14b1f28b"),
    "diff_checker": (CASE / "describe_diff.py", "1230530a78485bcf2ce68d45d8a9296ad39543457a57e4deae6f416c2764a208"),
    "checker": (CASE / "check_roundtrip.py", "14f66583395b7cb79258287462074fd8e56983e8d398b659439617dcf48cbaf3"),
    "validator": (CASE / "validate.py", "9b3ffc09392abf51e4fd084f30b73e5a848734e911b6ea68495b1343d006245c"),
    "runner_script": (CASE / "run_native_ssh.ps1", "343bef3d06454cebf84d7f45368aff199ebd21fd0460c4ef96e9289353f7be40"),
    "simlox_exe": (Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"), "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"),
    "python": (Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"), "372c2eae555b344520bf147be0096e009069aeca4e7f78d6aecea6d53158056a"),
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    s = p.read_text(encoding="utf-8-sig")
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        out, quote, esc = [], False, False
        for i, c in enumerate(s):
            if quote:
                out.append(c)
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    quote = False
            elif c == '"':
                quote = True
                out.append(c)
            elif c == "," and s[i + 1 :].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(c)
        return json.loads("".join(out))


def tables(d, root):
    seq = d[root]["tables"]
    result = {t["name"]: t for t in seq}
    if len(result) != len(seq):
        raise ValueError("duplicate table")
    return result


def rows(t):
    return [r for i in t["instances"] for r in i["rows"]]


def records(t):
    cols = [c["name"] for c in t["columns"]]
    if any(len(r) != len(cols) for r in rows(t)):
        raise ValueError("nonrectangular row")
    return [dict(zip(cols, r)) for r in rows(t)]


class Audit:
    def __init__(self):
        self.n = 0
        self.failures = []
        self.runs = {}

    def ck(self, condition, label):
        self.n += 1
        if not condition:
            self.failures.append(label)


def source(a):
    for key, (path, digest) in FROZEN.items():
        a.ck(path.is_file() and sha(path) == digest, f"frozen {key}")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    a.ck(manual.is_file() and sha(manual) == "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3", "installed manual hash")
    contract = read(CASE / "contract.json")
    a.ck(contract["version"] == "1.0.0-candidate" and contract["variant_id"] == "A13.var03" and contract["parent_input_sha256"] == FROZEN["parent"][1] and contract["structural_input_sha256"] == FROZEN["structure"][1], "contract lineage")
    T = {name: tables(read(path), "model") for name, path in (("parent", FROZEN["parent"][0]), ("b01", FROZEN["structure"][0]), ("control", CASE / "control-input.json"), ("dependency", CASE / "dependency-input.json"))}
    diff = read(CASE / "exact-diff.json")
    for v in IDS:
        child, parent = T[v], T["parent"]
        a.ck(sha(CASE / f"{v}-input.json") == SOURCE[v], f"{v} input hash")
        changes = {n for n in child.keys() | parent.keys() if child.get(n) != parent.get(n)}
        a.ck(changes == ({"MissionDependence", "MissionPreparation", "ProblemDescription", "Tasks"} if v == "control" else {"MissionPreparation", "ProblemDescription", "Tasks"}), f"{v} exact changed tables")
        calculated = {n: {"before": parent[n]["instances"] if n in parent else None, "after": child[n]["instances"] if n in child else None} for n in sorted(changes)}
        a.ck(calculated == diff["variants"][v]["changed_tables"] and sorted((child.keys() & parent.keys()) - changes) == diff["variants"][v]["unchanged_tables"] and diff["variants"][v]["input_sha256"] == SOURCE[v], f"{v} exact saved diff")
        a.ck(sum(bool(rows(t)) for t in child.values()) == (15 if v == "control" else 16), f"{v} source row table count")
        a.ck(records(child["MissionPreparation"]) == [{"MTID": "FOLLOW", "SID": "TEACH-AIR-01", "STID": "BASE-01", "DURN": .5, "TID": "PREP-FIXED", "DURND": None, "NOTE": None}], f"{v} FOLLOW preparation row")
        task = records(child["Tasks"])
        a.ck(len(task) == 1 and task[0]["TID"] == "PREP-FIXED" and task[0]["DESCR"] == "Fixed 30-minute FOLLOW preparation", f"{v} task identity")
        a.ck(child["MissionPreparation"]["columns"] == T["b01"]["MissionPreparation"]["columns"] and child["Tasks"]["columns"] == T["b01"]["Tasks"]["columns"], f"{v} B01 schema")
    pair = {n for n in T["control"].keys() | T["dependency"].keys() if T["control"].get(n) != T["dependency"].get(n)}
    a.ck(pair == {"ProblemDescription", "MissionDependence"} and "MissionDependence" not in T["control"], "pair discriminator")
    dep = records(T["dependency"]["MissionDependence"])
    a.ck(len(dep) == 1 and tuple(dep[0][k] for k in ("DUNID", "DMTID", "DSTIM", "PUNID", "PMTID", "PSTIM", "DTYPE")) == ("TEACH-UNIT", "FOLLOW", 10, "TEACH-UNIT", "RECON", 8, "START"), "START row identity")
    a.ck(diff["parent_sha256"] == FROZEN["parent"][1] and diff["structural_source_sha256"] == FROZEN["structure"][1], "diff lineage")


def event(s, h, text):
    return f"Time: {h:g} {text}" in s


def report(a, v, doc):
    t = tables(doc, "report")
    a.ck(set(t) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{v} report table set")
    a.ck(records(t["ResultSummary"]) == [{"NREP": 1, "RTILW": 0, "RTIUP": 24, "MTMF": 1, "RSMTMF": 0, "MSTF": 1, "RSMSTF": 0, "MSUF": 1, "RSMSUF": 0, "STMF": 1, "RSSTMF": 0}], f"{v} summary")
    sy, st = records(t["SystemResults"]), records(t["StockTotalResults"])
    a.ck(len(sy) == len(st) == 48, f"{v} 48 bins")
    end, start = (12, 10) if v == "control" else (14, 12)
    for i, (x, y) in enumerate(zip(sy, st)):
        h = i / 2
        assigned = int(7 <= h < 12) + int(9 <= h < end)
        operating = int(8 <= h < 12) + int(start <= h < end)
        prep = int(h == 9)
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems", "STINT": h, "ETINT": h + .5, "NSYRY": 2 - assigned, "NSYMA": assigned, "NSYMO": operating, "NSYMP": prep, "NSYMR": assigned - operating - prep, "NSYA": 2, "FTMO": operating / 2, "STACC": operating, "NPSTA": prep, "NPSUC": int(h == 9.5)}
        for key, val in expected.items():
            a.ck(x[key] == val, f"{v} system bin {i} {key}")
        a.ck(all(z in (0, None) for k, z in x.items() if k not in expected), f"{v} system bin {i} other metrics")
        stock_expected = {"STINT": h, "ETINT": h + .5, "PNB": 1}
        a.ck(all(y[k] == z for k, z in stock_expected.items()) and all(z in (0, None) for k, z in y.items() if k not in stock_expected), f"{v} stock bin {i}")
    a.ck(sum(x["NSYMO"] * .5 for x in sy) == 6 and sum(x["NSYMA"] * .5 for x in sy) == (8 if v == "control" else 10), f"{v} operating and assigned integrals")
    a.ck(sum(x["NSYMP"] * .5 for x in sy) == .5 and sum(x["NPSTA"] for x in sy) == sum(x["NPSUC"] for x in sy) == 1, f"{v} positive prep integral")
    a.ck(sy[-1]["NSYRY"] == 2 and sy[-1]["NSYMA"] == sy[-1]["NSYMO"] == 0, f"{v} terminal ready")
    return t


def run(a, v):
    p = CASE / "runs" / IDS[v]
    inv, clo, steps = (read(p / n) for n in ("invocation.json", "closure.json", "steps.json"))
    expected = {k: digest for k, (_, digest) in FROZEN.items()}
    expected["input"] = SOURCE[v]
    a.ck(inv["variant"] == v and inv["run_id"] == clo["run_id"] == IDS[v] and inv["variant_id"] == "A13.var03" and inv["case_version"] == "1.0.0-candidate", f"{v} run identity")
    a.ck(inv["original_run_dir"].lower() == str(p).lower() and inv["publication_state"] == "not_published", f"{v} original location")
    a.ck(inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"], f"{v} SSH session0")
    a.ck(inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1 and bool(inv["gui"]["start_utc"]), f"{v} queue GUI")
    a.ck(clo["invocation_sha256"] == sha(p / "invocation.json") and clo["error"] is None, f"{v} invocation closure")
    for k, digest in expected.items():
        a.ck(inv["source_hashes_before"].get(k) == digest and clo["source_hashes_before"].get(k) == digest and clo["source_hashes_after"].get(k) == digest, f"{v} source seal {k}")
    a.ck(inv["input_sha256"] == SOURCE[v] and inv["validator_sha256"] == expected["validator"] and sha(p / "input.json") == SOURCE[v], f"{v} input/validator pins")
    raw = {q.name for q in p.iterdir() if q.is_file() and q.name not in ("invocation.json", "closure.json")}
    a.ck(set(clo["raw"]) == raw, f"{v} complete raw list")
    for file, meta in clo["raw"].items():
        q = p / file
        a.ck(q.stat().st_size == meta["bytes"] and sha(q) == meta["sha256"], f"{v} raw {file} seal")
    a.ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{v} five steps")
    for s in steps:
        a.ck(s["exit_code"] == 0 and s["gui_preserved"] is True and s["status"] == ("calc_observed" if s["name"] == "calc" else "completed") and s["error"] is None and s["started_utc"] <= s["completed_utc"], f"{v} step {s['name']}")
    a.ck((p / "model.sxi").stat().st_size > 4 and (p / "model.sxo").stat().st_size > 4 and (p / "report-raw.json").stat().st_size > 4, f"{v} usable artifacts")
    a.ck("Import completed!" in (p / "import.log").read_text(encoding="utf-8-sig", errors="replace") and "Export completed!" in (p / "export.log").read_text(encoding="utf-8-sig", errors="replace"), f"{v} import/export completion")
    calc = (p / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    a.ck("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc and sorted(map(int, re.findall(r"warning #(\d+)", calc))) == [108, 126] and not re.search(r"error #\d+", calc, re.I) and "Saving results" in calc, f"{v} native conversion")
    src, exp = tables(read(p / "input.json"), "model"), tables(read(p / "roundtrip-raw.json"), "model")
    occupied = {n: t for n, t in src.items() if rows(t)}
    a.ck(len(occupied) == (15 if v == "control" else 16), f"{v} row-containing count")
    for n, t in occupied.items():
        a.ck(n in exp and t["columns"] == exp[n]["columns"] and t["instances"] == exp[n]["instances"], f"{v} native roundtrip {n}")
    log = (p / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    recon, follow = "<RECON,TEACH-UNIT,0,0,0>", "<FOLLOW,TEACH-UNIT,0,0,1>"
    start, end = (10, 12) if v == "control" else (12, 14)
    event_list = [(7, f"{recon} mission allocates system: <TEACH-AIR-01,0>"), (8, f"{recon} mission starting, duration: 4 : <TEACH-AIR-01,0>"), (9, f"{follow} mission allocates system: <TEACH-AIR-01,1>"), (start, f"{follow} mission starting, duration: 2 : <TEACH-AIR-01,1>"), (12, f"{recon} mission success:"), (12, f"{recon} mission completed: <TEACH-AIR-01,0>"), (end, f"{follow} mission success:"), (end, f"{follow} mission completed: <TEACH-AIR-01,1>"), (12, "<TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>, mission success"), (end, "<TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,1>, mission success"), (7, f"<TEACH-AIR-01,0> preparation started, mission: {recon}"), (7, f"<TEACH-AIR-01,0> preparation ended, mission: {recon}"), (9, f"<TEACH-AIR-01,1> preparation started, mission: {follow}"), (9.5, f"<TEACH-AIR-01,1> preparation ended, mission: {follow}"), (9, " subtask 0 seqno 0 within system preparation task 0 on <TEACH-AIR-01,1> starts performing, planned to last for 0.5 hours"), (9.5, " subtask 0 seqno 0 within system preparation task 0 on <TEACH-AIR-01,1> completed")]
    for h, phrase in event_list:
        a.ck(event(log, h, phrase), f"{v} event {h} {phrase}")
    a.ck(len(re.findall(r"preparation started,", log)) == len(re.findall(r"preparation ended,", log)) == 2 and len(re.findall(r"starts performing, planned to last for 0.5 hours", log)) == 1, f"{v} instant RECON plus one positive FOLLOW prep")
    a.ck(len(re.findall(r"mission starting, duration:", log)) == len(re.findall(r"mission success:", log)) == len(re.findall(r"mission completed:", log)) == 2 and len(re.findall(r"System arrives", log)) == 2 and not re.search(r"mission (?:abort|cancel|fail)|shortage|failure occurs", log, re.I), f"{v} two successful missions")
    t = report(a, v, read(p / "report-raw.json"))
    a.runs[v] = {"run_id": IDS[v], "closure_sha256": sha(p / "closure.json"), "invocation_sha256": sha(p / "invocation.json"), "model_log_sha256": sha(p / "model.log"), "report_sha256": sha(p / "report-raw.json"), "follow_launch_hour": start, "positive_prep_interval": [9, 9.5], "system_bins": 48, "stock_bins": 48, "operating_aircraft_hours": 6, "terminal_ready": 2}
    return t


def excluded(a):
    diagnostic = CASE / "failed" / "validator-spacing-20261001"
    a.ck(sha(diagnostic / "validate-precorrection.py") == "6683f1817ef2ed9deef7a4fccaae07af7417aed0308e7baf9a1beb09b68d0f1c",
         "retained original validator hash")
    failure = read(diagnostic / "author-replay-failure.json")
    a.ck(failure["passed"] is False and failure["checks_before_failure"] == 76 and
         "positive preparation work" in failure["error"], "old author replay failure provenance")
    for v in IDS:
        p = CASE / "runs" / f"a13-var03-prep-{v}-v100-20261001-01"
        inv, clo = read(p / "invocation.json"), read(p / "closure.json")
        a.ck(clo["invocation_sha256"] == sha(p / "invocation.json") and
             inv["validator_sha256"] == sha(diagnostic / "validate-precorrection.py"),
             f"excluded {v} diagnostic source seal")
        log = (p / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        a.ck("Time: 9  subtask" in log and "Time: 7 <TEACH-AIR-01,0> preparation started" in log and "Time: 7 <TEACH-AIR-01,0> preparation ended" in log, f"excluded {v} formatting/lifecycle observation")
        fresh = CASE / "runs" / IDS[v]
        a.ck(sha(p / "model.log") == sha(fresh / "model.log") and
             sha(p / "report-raw.json") == sha(fresh / "report-raw.json"),
             f"excluded {v} native behavior matches fresh run")


def main():
    a = Audit()
    try:
        source(a)
        reports = {v: run(a, v) for v in IDS}
        a.ck({n for n in reports["control"] if reports["control"][n] != reports["dependency"][n]} == {"ProblemDescription", "SystemResults"}, "report pair delta")
        a.ck(reports["control"]["ResultSummary"] == reports["dependency"]["ResultSummary"] and reports["control"]["StockTotalResults"] == reports["dependency"]["StockTotalResults"], "summary/stock pair equality")
        excluded(a)
    except Exception as e:
        a.failures.append(f"exception: {type(e).__name__}: {e}")
    result = {"schema": "simlox-a13-var03-prep-wait-independent-readonly/v1", "passed": not a.failures, "verdict": "GO" if not a.failures else "NO-GO", "check_count": a.n, "failures": a.failures, "runs": a.runs, "excluded_diagnostic": "Earlier -01 native runs were valid, but the preserved original author replay failed its preparation text/lifecycle assertions; only fresh -02 runs support this verdict.", "scope": "one fixed-seed pair: positive FOLLOW preparation before START-dependent launch wait", "limits": ["Same displayed hour-12 success/launch/completion/return timestamps do not prove internal ordering.", "No resource-constrained preparation, failure, repeated missions, other seeds, GUI visual behavior or cross-engine parity."]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "check_count": a.n, "failures": a.failures, "report": str(OUT)}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

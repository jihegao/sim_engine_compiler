"""Read-only replay of D01.var03's predeclared terminal direct-repair gate."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import validate_native as native  # noqa: E402

RUN_ID = "d01-var03-terminal-v010-ssh-20261006-01"
INPUT_SHA = "63c77c19f875b667db815999b17fd1e2ee053c6c0dbe620c2772b8175a387bac"
PARENT_SHA = "d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
PARENT = HERE.parent / "D01-system-direct-repair-v1.0.0"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
       "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
       "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def events(log: str, expression: str) -> list[float]:
    return [float(x) for x in re.findall(expression, log, re.M)]


def validate(run: Path) -> dict:
    failures: list[str] = []
    checks = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(label)

    def near(label: str, actual: float, expected: float) -> None:
        ck(label, abs(actual - expected) < 1e-5)

    ck("run identity", run.name == RUN_ID)
    ck("frozen child and copied input", sha(HERE / "native-input.json") == sha(run / "input.json") == INPUT_SHA)
    ck("accepted parent input", sha(PARENT / "native-input.json") == PARENT_SHA)
    inv, closure, steps = (load(run / filename) for filename in
                           ("invocation.json", "closure.json", "steps.json"))
    ck("invocation identity", inv.get("schema") == "simlox-d01-var03-v010-native-candidate/ssh-cli-v1"
       and inv.get("case_id") == "D01" and inv.get("variant_id") == "D01.var03"
       and inv.get("run_id") == RUN_ID and inv.get("input_sha256") == INPUT_SHA
       and inv.get("parent_sha256") == PARENT_SHA and inv.get("simlox_exe_sha256") == EXE_SHA)
    for key, filename in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"),
                          ("checker_sha256", "check_roundtrip.py"),
                          ("diff_checker_sha256", "check_parent_diff.py"),
                          ("validator_sha256", "validate_native_cli.py"),
                          ("runner_script_sha256", "run_native_ssh.ps1")):
        ck(f"frozen {filename}", inv.get(key) == sha(HERE / filename))
    ck("SSH and serial queue", inv.get("session_id") == 0 and inv.get("ssh_connection_present") is True
       and "sshd.exe" in inv.get("ssh_ancestor_names", [])
       and inv.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue")
    gui = inv.get("gui", {})
    ck("fresh GUI guard record", gui.get("pid") == 13340 and gui.get("session_id") == 1
       and gui.get("start_utc") == "2026-09-28T10:09:56.8261381Z")
    ck("closure identity", closure.get("schema") == "simlox-d01-var03-v010-native-closure/v1"
       and closure.get("run_id") == RUN_ID and closure.get("error") is None
       and closure.get("invocation_sha256") == sha(run / "invocation.json"))
    ck("source bytes stable", closure.get("source_hashes_before") == closure.get("source_hashes_after")
       == inv.get("source_hashes_before"))
    ck("raw inventory", set(closure.get("raw", {})) == RAW)
    for filename, seal in closure.get("raw", {}).items():
        path = run / filename
        ck(f"raw {filename}", path.is_file() and path.stat().st_size == seal.get("bytes")
           and sha(path) == seal.get("sha256"))
    ck("step order and success", [(s.get("name"), s.get("status"), s.get("exit_code"),
                                    s.get("gui_preserved")) for s in steps] ==
       [(name, "completed", 0, True) for name in
        ("import", "export", "check_import_export", "calc", "jsonreport")])
    roundtrip = load(run / "roundtrip-validation.json")
    ck("all 14 authored tables roundtrip", roundtrip.get("passed") is True
       and roundtrip.get("differences") == [] and len(roundtrip.get("populated_tables", [])) == 14
       and native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"])

    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    counts = re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", conversion)
    ck("zero-error classified conversion", counts == [("0", "2", "0")]
       and Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1, "126": 1})
       and "This system contains no items: TEACH-AIR-01" in conversion
       and not re.search(r"\(error #\d+\)", conversion))
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("native stop hour", log.splitlines()[1] == "34.25")
    ck("exact three mission starts", events(log, r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission starting,") == [8, 20, 32])
    ck("exact aborts", events(log, r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission aborted:") == [9.8829, 33.8602])
    ck("one middle success", events(log, r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:") == [22])
    ck("both aborted missions return", re.findall(
       r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> aborted mission completed:", log, re.M)
       == [("10", "0"), ("34", "2")])
    ck("aborted aircraft arrive at base", events(log,
       r"^Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>, *$") == [10, 34])
    lifecycle = Counter(re.findall(
       r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> "
       r"(mission created|mission starting|mission success|mission completed|mission cancelled|mission aborted|aborted mission completed)",
       log, re.M))
    ck("no extra mission lifecycle", lifecycle == Counter({
       ("7", "0", "mission created"): 1, ("8", "0", "mission starting"): 1,
       ("9.8829", "0", "mission aborted"): 1, ("10", "0", "aborted mission completed"): 1,
       ("19", "1", "mission created"): 1, ("20", "1", "mission starting"): 1,
       ("22", "1", "mission success"): 1, ("22", "1", "mission completed"): 1,
       ("31", "2", "mission created"): 1, ("32", "2", "mission starting"): 1,
       ("33.8602", "2", "mission aborted"): 1, ("34", "2", "aborted mission completed"): 1}))
    ck("two observed failures", events(log, r"^Time: ([\d.]+) <TEACH-AIR-01,0> critical random failure added") == [9.8829, 33.8602])
    ck("two direct repair starts", re.findall(r"^Time: ([\d.]+)  system DIRP task (\d+) on <TEACH-AIR-01,0> started$", log, re.M) == [("10", "0"), ("34", "1")])
    ck("second repair working with half-hour plan", "Time: 34  direct repair subtask 1 seqno 0 within system DIRP task 1 on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours" in log)
    ck("first repair completes", re.findall(r"^Time: ([\d.]+)  system DIRP task (\d+) on <TEACH-AIR-01,0> completed$", log, re.M) == [("10.5", "0")])
    ck("first ready restored", "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log)
    ck("no second completion or ready", "system DIRP task 1 on <TEACH-AIR-01,0> completed" not in log
       and not re.search(r"^Time: 34\.5 .*System ready", log, re.M))
    ck("event horizon", not events(log, r"^Time: ([\d.]+) ") or
       max(events(log, r"^Time: ([\d.]+) ")) <= 34.25)

    report = json.loads(native.remove_trailing_commas((run / "report-raw.json").read_bytes()))
    system = native.table_rows(report, "SystemResults")
    stock = native.table_rows(report, "StockTotalResults")
    summary = native.table_rows(report, "ResultSummary")
    grid = [(i * .25, (i + 1) * .25) for i in range(137)]
    ck("137 system quarter-hour bins", len(system) == 137 and
       [(r["STINT"], r["ETINT"]) for r in system] == grid)
    ck("137 stock quarter-hour bins", len(stock) == 137 and
       [(r["STINT"], r["ETINT"]) for r in stock] == grid)
    if len(system) == len(stock) == 137:
        system_zero = {"NSYMC", "NSYMP", "NSYMT", "NSYMS", "NSYAL", "NSYPM", "NSYTP",
                       "NSYWR", "NSYWI", "NSYLA", "NSYUH", "NPMT", "NDAM", "NPMS",
                       "NROBT", "NRCFG", "STREQ", "STF", "STLOW", "SYDTU", "NSYSW",
                       "NPSTA", "NPSUC"}
        stock_zero = {"NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT"}
        stock_null = {"NBOU", "ROS", "ROST", "WT", "WTT", "WTS"}
        for i, (s, st) in enumerate(zip(system, stock, strict=True)):
            t = i * .25
            allocated = any(a <= t < b for a, b in ((7, 10.5), (19, 22), (31, 34.25)))
            mission = any(a <= t < b for a, b in ((8, 10), (20, 22), (32, 34)))
            preparation = any(a <= t < b for a, b in ((7, 8), (19, 20), (31, 32)))
            repair = 10 <= t < 10.5 or 34 <= t < 34.25
            expected_system = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                               "STINT": t, "ETINT": t + .25,
                               **{key: 0 for key in system_zero},
                               "NSYRY": int(not allocated),
                               "NSYMA": int(any(a <= t < b for a, b in ((7, 10), (19, 22), (31, 34)))),
                               "NSYMO": int(mission), "NSYMR": int(preparation),
                               "NSYUA": int(repair), "NSYA": int(not repair),
                               "FTMO": int(mission), "NSYRP": int(repair),
                               "NREPT": int(t == 10.5), "NFAIL": int(t in (9.75, 33.75)),
                               "STACC": int(mission),
                               "SYDT": .5 if t == 10.25 else None,
                               "NSYDT": int(t == 10.25)}
            expected_stock = {"STINT": t, "ETINT": t + .25, "PNB": 1,
                              **{key: 0 for key in stock_zero},
                              **{key: None for key in stock_null}}
            ck(f"system bin {i} full ledger", s == expected_system)
            ck(f"stock bin {i} full ledger (PNB aggregate)", st == expected_stock)
        for key, expected in (("NSYRY", 24.5), ("NSYMA", 9), ("NSYMO", 6),
                              ("NSYA", 33.5), ("FTMO", 6), ("NSYRP", .75)):
            near(f"integral {key}", sum(r[key] * .25 for r in system), expected)
        ck("terminal interval still in repair", system[-1]["NSYRP"] == 1
           and system[-1]["NSYRY"] == 0 and system[-1]["NSYA"] == 0)
    ck("one of three missions succeeds", len(summary) == 1 and summary[0].get("NREP") == 1
       and summary[0].get("RTIUP") == 34.25 and abs(summary[0].get("MSUF", -1) - 1/3) < 1e-6)
    return {"schema": "simlox-d01-var03-v010-author-native-validation/v1", "run_id": run.name,
            "passed": not failures, "checks": checks, "differences": failures,
            "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"),
            "scope": "fixed_seed_terminal_direct_repair_cli_candidate", "publication_state": "not_published"}


if __name__ == "__main__":
    answer = validate(Path(sys.argv[1]))
    print(json.dumps(answer, ensure_ascii=False, indent=2))
    sys.exit(0 if answer["passed"] else 1)

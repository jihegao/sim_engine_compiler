"""Independent read-only replay of the sealed D01.var03 v0.1.1 run."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN_ID = "d01-var03-terminal-v011-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
PARENT = ROOT / "D01-system-direct-repair-v1.0.0"
PARENT_RUN = PARENT / "runs" / "d01-v100-ssh-20260929-01"
OLD = ROOT / "D01-var03-terminal-repair-v0.1.0"
OLD_RUN = OLD / "runs" / "d01-var03-terminal-v010-ssh-20261006-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # The native default exporter leaves trailing commas. Change only a
        # parser copy, never the sealed report bytes.
        return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


def tables(doc, container: str):
    return {t["name"]: t for t in doc[container]["tables"]}


def rows(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for inst in table["instances"] for row in inst["rows"]]


def main():
    failed = []
    count = 0

    def ck(label, ok):
        nonlocal count
        count += 1
        if not ok:
            failed.append(label)

    contract = read_json(CASE / "contract.json")
    inv, closure, step_list = [read_json(RUN / n) for n in ("invocation.json", "closure.json", "steps.json")]
    ck("contract pin", sha(CASE / "contract.json") == "c5fe170e7a7370d51de4f2f5b08204d982cc6c44272f5eed97f9354e852ab6b7")
    ck("run closure pin", sha(RUN / "closure.json") == "d17ef79e8d832a5c89197ce35d97e8a0245f2ce8194e61b7d4ddabc45b8d7195")
    source_paths = {
        "input": CASE / "native-input.json",
        "parent": PARENT / "native-input.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-09-29.md",
        "parent_closure": PARENT_RUN / "closure.json",
        "a02_signoff": ROOT / "A02-single-aircraft-repeated-missions" / "cli-scope-signoff-2026-09-29.md",
        "j05_signoff": ROOT / "J05-collection-window-v1.0.1" / "cli-scope-signoff-2026-10-01.md",
        "d05_signoff": ROOT / "D05-var04-horizon-in-repair-v1.0.0" / "cli-scope-signoff-2026-09-30.md",
        "precursor_closure": OLD_RUN / "closure.json",
        "precursor_failure_seal": OLD_RUN / "failure-seal.json",
        "precursor_independent_review": OLD / "review" / "independent-postfailure-2026-10-06.md",
        "contract": CASE / "contract.json",
        "builder": CASE / "build.py",
        "checker": CASE / "check_roundtrip.py",
        "diff_checker": CASE / "check_parent_diff.py",
        "validator": CASE / "validate_native_cli.py",
        "runner_script": CASE / "run_native_ssh.ps1",
    }
    ck("source map stable", closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
    for key, path in source_paths.items():
        ck(f"source {key}", sha(path) == closure["source_hashes_before"][key])
    ck("parent contract references", sha(PARENT / "native-input.json") == contract["parent"]["input_sha256"]
       and sha(PARENT_RUN / "closure.json") == contract["parent"]["closure_sha256"])
    ck("precursor contract references", sha(OLD_RUN / "closure.json") == contract["excluded_precursor"]["closure_sha256"]
       and sha(OLD_RUN / "failure-seal.json") == contract["excluded_precursor"]["failure_seal_sha256"])
    for label, location in (("parent", PARENT_RUN), ("excluded", OLD_RUN), ("child", RUN)):
        obj = read_json(location / "closure.json")
        for name, seal in obj["raw"].items():
            path = location / name
            ck(f"{label} raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    for name, seal in read_json(OLD_RUN / "failure-seal.json")["files"].items():
        path = OLD_RUN / name
        ck(f"excluded failure seal {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    ck("child closure and invocation", closure["error"] is None and closure["run_id"] == RUN_ID
       and closure["invocation_sha256"] == sha(RUN / "invocation.json")
       and inv["run_id"] == RUN_ID and inv["input_sha256"] == sha(RUN / "input.json"))
    ck("SSH and GUI", inv["session_id"] == 0 and inv["ssh_connection_present"]
       and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
       and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1
       and inv["gui"]["start_utc"] == "2026-09-28T10:09:56.8261381Z")
    ck("five guarded steps", [(x["name"], x["status"], x["exit_code"], x["gui_preserved"])
       for x in step_list] == [(n, "completed", 0, True) for n in
                            ("import", "export", "check_import_export", "calc", "jsonreport")])
    ck("raw source copied", sha(RUN / "input.json") == sha(CASE / "native-input.json"))

    src = tables(read_json(RUN / "input.json"), "model")
    exp = tables(read_json(RUN / "roundtrip-raw.json"), "model")
    populated = [name for name, t in src.items() if any(inst["rows"] for inst in t["instances"])]
    ck("14 authored tables", len(populated) == 14)
    for name in populated:
        a, b = src[name], exp[name]
        ck(f"roundtrip {name}", a["columns"] == b["columns"] and
           [r for inst in a["instances"] for r in inst["rows"]] ==
           [r for inst in b["instances"] for r in inst["rows"]])
    parent_src = tables(read_json(PARENT / "native-input.json"), "model")
    diffs = []
    parent_count = 0
    for name, t in parent_src.items():
        other = src[name]
        ck(f"table metadata {name}", t["columns"] == other["columns"] and
           len(t["instances"]) == len(other["instances"]))
        for inst_no, (a, b) in enumerate(zip(t["instances"], other["instances"], strict=True)):
            ck(f"instance geometry {name}/{inst_no}", a["instance_name"] == b["instance_name"] and
               len(a["rows"]) == len(b["rows"]))
            for row_no, (ra, rb) in enumerate(zip(a["rows"], b["rows"], strict=True)):
                for col, old, new in zip(t["columns"], ra, rb, strict=True):
                    parent_count += 1
                    if old != new:
                        diffs.append((name, row_no, col["name"], old, new))
    ck("194 cell keys", parent_count == 194)
    ck("eight exact source changes", {(n, row, col) for n, row, col, _, _ in diffs} ==
       {("ProblemDescription", 0, "PDESC"), ("Control", 0, "SIMPE"),
        ("Control", 0, "RCINT"), ("Control", 0, "RCEND"),
        *(("ResultCollection", row, col) for row in (0, 1) for col in ("RCINT", "RCEND"))})
    ck("roundtrip checker recorded pass", read_json(RUN / "roundtrip-validation.json")["passed"] is True)
    calc = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter 0/2/0", re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", calc)
       == [("0", "2", "0")])
    ck("sole reviewed warnings", Counter(re.findall(r"\(warning #(\d+)\)", calc)) == Counter({"108": 1, "126": 1})
       and "This system contains no items: TEACH-AIR-01" in calc and "(error #" not in calc)
    ck("valid native SXO", (RUN / "model.sxo").stat().st_size > 4)

    child_log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    parent_prefix = [line for line in parent_log.splitlines() if line.startswith("Time: ")
                     and float(line.split()[1]) <= 34.375]
    child_events = [line for line in child_log.splitlines() if line.startswith("Time: ")]
    ck("102 event lines equal parent prefix", len(child_events) == 102 and child_events == parent_prefix)
    ck("native stop header", child_log.splitlines()[:2] == ["SIMLOX LOG FILE", "34.375"])
    ck("mission lifecycle", [(int(m.group(1)), m.group(2)) for m in re.finditer(
       r"<BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> (mission created|mission starting|mission success|mission completed|mission aborted|aborted mission completed)", child_log)] ==
       [(0, "mission created"), (0, "mission starting"), (0, "mission aborted"), (0, "aborted mission completed"),
        (1, "mission created"), (1, "mission starting"), (1, "mission success"), (1, "mission completed"),
        (2, "mission created"), (2, "mission starting"), (2, "mission aborted"), (2, "aborted mission completed")])
    ck("one completed repair", len(re.findall(r"^Time: [\d.]+  system DIRP task \d+ on <TEACH-AIR-01,0> completed$", child_log, re.M)) == 1
       and "Time: 10.5  system DIRP task 0 on <TEACH-AIR-01,0> completed" in child_log)
    ck("second task working unfinished", "Time: 34  system DIRP task 1 on <TEACH-AIR-01,0> started" in child_log
       and "Time: 34  direct repair subtask 1 seqno 0 within system DIRP task 1 on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours" in child_log
       and "system DIRP task 1 on <TEACH-AIR-01,0> completed" not in child_log)

    report = read_json(RUN / "report-raw.json")
    rt = tables(report, "report")
    system = rows(rt["SystemResults"])
    stock = rows(rt["StockTotalResults"])
    ck("275 System rows", len(system) == 275)
    ck("275 Stock rows", len(stock) == 275)
    sys_zero = {"NSYMC", "NSYMP", "NSYMT", "NSYMS", "NSYAL", "NSYPM", "NSYTP", "NSYWR", "NSYWI", "NSYLA",
                "NSYUH", "NPMT", "NDAM", "NPMS", "NROBT", "NRCFG", "STREQ", "STF", "STLOW", "SYDTU",
                "NSYSW", "NPSTA", "NPSUC"}
    st_zero = {"NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT"}
    st_null = {"NBOU", "ROS", "ROST", "WT", "WTT", "WTS"}
    for i, (s, st) in enumerate(zip(system, stock, strict=True)):
        t = i / 8
        mission = (8 <= t < 10) or (20 <= t < 22) or (32 <= t < 34)
        prepared = (7 <= t < 8) or (19 <= t < 20) or (31 <= t < 32)
        repair = (10 <= t < 10.5) or (34 <= t < 34.375)
        allocated = (7 <= t < 10.5) or (19 <= t < 22) or (31 <= t < 34.375)
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                    "STINT": t, "ETINT": t + .125, **{k: 0 for k in sys_zero},
                    "NSYRY": int(not allocated), "NSYMA": int((7 <= t < 10) or (19 <= t < 22) or (31 <= t < 34)),
                    "NSYMO": int(mission), "NSYMR": int(prepared), "NSYUA": int(repair),
                    "NSYA": int(not repair), "FTMO": int(mission), "NSYRP": int(repair),
                    "NREPT": int(t == 10.5), "NFAIL": int(t in (9.875, 33.75)),
                    "STACC": int(mission), "SYDT": .5 if t == 10 else None, "NSYDT": int(t == 10)}
        ck(f"System row {i}", s == expected)
        ck(f"Stock row {i}", st == {"STINT": t, "ETINT": t + .125, "PNB": 1,
                                    **{k: 0 for k in st_zero}, **{k: None for k in st_null}})
    ck("terminal unavailable in repair", system[-1]["NSYRP"] == 1 and system[-1]["NSYRY"] == 0
       and system[-1]["NSYA"] == 0 and system[-1]["SYDT"] is None and system[-1]["NSYDT"] == 0)
    for key, expected in (("NSYRY", 24.5), ("NSYMA", 9), ("NSYMO", 6), ("NSYA", 33.5),
                          ("FTMO", 6), ("NSYRP", .875)):
        ck(f"integral {key}", abs(sum(row[key] / 8 for row in system) - expected) < 1e-9)
    ck("failure/repair totals", sum(x["NFAIL"] for x in system) == 2
       and sum(x["NREPT"] for x in system) == 1 and sum(x["NBO"] for x in stock) == 0)
    summary = rows(rt["ResultSummary"])
    ck("one of three missions succeeds", len(summary) == 1 and summary[0]["NREP"] == 1
       and summary[0]["RTIUP"] == 34.375 and abs(summary[0]["MSUF"] - 1 / 3) < 1e-6)

    original = read_json(CASE / "review" / "author-native-validation-2026-10-06.json")
    corrected = read_json(CASE / "review" / "author-readonly-replay-v012-2026-10-06.json")
    ck("preserved original strict false negative", sha(CASE / "review" / "author-native-validation-2026-10-06.json") ==
       "e9c6f3cb85d8b78cce09a17083c05b937b5bb0aefaaa4e3e2fa43c01cc603e82"
       and original["passed"] is False and original["checks"] == 604
       and original["differences"] == ["system bin 80 full ledger", "system bin 83 full ledger"])
    ck("separate correction pin", sha(CASE / "validate_native_cli_v012.py") ==
       "b030de4613abab794bf39d5b61b955f0b7dc9d45ade5e5008fdf294706abd851"
       and sha(CASE / "review" / "author-readonly-replay-v012-2026-10-06.json") ==
       "132ea6153ccb1d115198006e59f61cb631762051b4cedf4dd2201e2bfeaa87de")
    ck("v012 reviewed result", corrected["passed"] is True and corrected["checks"] == 605
       and corrected["differences"] == [])
    result = {"schema": "simlox-d01-var03-independent-replay/v1", "verdict": "GO_BOUNDED" if not failed else "NO_GO",
              "checks": count, "failed": failed, "run_id": RUN_ID,
              "closure_sha256": sha(RUN / "closure.json"), "model_log_sha256": sha(RUN / "model.log"),
              "report_sha256": sha(RUN / "report-raw.json"),
              "limits": ["One fixed-seed terminal in-progress direct system repair, not post-horizon completion.",
                         "SYDT and NSYDT at the repair-start bin are native report attribution; completion is established by event and NREPT.",
                         "StockTotalResults.PNB is aggregate, not physical on-hand inventory; no stocked item is modeled."]}
    out = CASE / "review" / "independent-verdict.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

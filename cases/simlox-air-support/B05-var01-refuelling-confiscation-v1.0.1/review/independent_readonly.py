"""Independent, read-only B05.var01 v1.0.1 replay from sealed native artifacts.

Standard library only. Never imports or executes the author's builder, checker,
validator, runner, or SIMLOX. Writes only its JSON review in this directory.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LIB = REPO / "cases/simlox-air-support"
CASE = LIB / "B05-var01-refuelling-confiscation-v1.0.1"
PARENT = LIB / "B02-serial-preparation-v1.0.2/native-input.json"
OUT = CASE / "review/independent-readonly-2026-09-30.json"
VARIANTS = ("inspect-control", "refuelling")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
SIMLOX = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
checks = {}
failures = []


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name: str, got, want) -> None:
    ok = got == want
    checks[name] = {"passed": ok}
    if not ok or len(str(got)) < 180:
        checks[name].update({"observed": got, "expected": want})
    if not ok:
        failures.append(name)


def approx(name: str, got, want, tolerance=0.00002) -> None:
    ok = len(got) == len(want) and all(abs(a-b) <= tolerance for a,b in zip(got,want))
    checks[name] = {"passed": ok, "observed": got, "expected": want, "tolerance": tolerance}
    if not ok:
        failures.append(name)


def parse(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Native SIMLOX reports contain a trailing comma in the tables array.
        out = []
        quoted = escaped = False
        for i, c in enumerate(raw):
            if quoted:
                out.append(c)
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == '"':
                    quoted = False
            elif c == '"':
                quoted = True
                out.append(c)
            elif c == "," and raw[i+1:].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(c)
        return json.loads("".join(out))


def tab(doc, name: str, root="model"):
    found = [t for t in doc[root]["tables"] if t["name"] == name]
    assert len(found) == 1, (name, len(found))
    return found[0]


def rows(doc, name: str, root="model"):
    t = tab(doc, name, root)
    names = [c["name"] for c in t["columns"]]
    assert len(names) == len(set(names))
    return [dict(zip(names, row)) for inst in t["instances"] for row in inst["rows"]]


def map_tables(doc):
    return {t["name"]: t for t in doc["model"]["tables"]}


def changes(before, after):
    a, b = map_tables(before), map_tables(after)
    assert set(a) == set(b)
    def body(t):
        return {k:v for k,v in t.items() if k != "name"}
    return {name: {"before": body(a[name]), "after": body(b[name])} for name in sorted(a) if a[name] != b[name]}


def event(log: str, phrase: str):
    found = []
    for line in log.splitlines():
        if phrase in line:
            m = re.match(r"Time: ([0-9.]+) (.*)", line)
            assert m, line
            found.append((float(m.group(1)), m.group(2)))
    return found


def hours(log: str, phrase: str):
    return [t for t, _ in event(log, phrase)]


def names_and_times(log: str, phrase: str):
    return [(t, re.search(r"<(?:BASIC|SECOND)-MISSION,TEACH-UNIT,0,0,\d+>", s).group(0)) for t,s in event(log, phrase)]


def event_check(prefix: str, log: str, phrase: str, expected_times):
    approx(prefix + " " + phrase, hours(log, phrase), expected_times)


def review_variant(v: str, contract, diff, parent):
    run = CASE / "runs" / f"b05-var01-v101-{v}-20260930-01"
    inv = parse(run / "invocation.json")
    closure = parse(run / "closure.json")
    steps = parse(run / "steps.json")
    source = parse(CASE / f"{v}-input.json")
    inp = parse(run / "input.json")
    roundtrip = parse(run / "roundtrip-raw.json")
    report = parse(run / "report-raw.json")
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    label = v + ": "

    check(label + "source sha", digest(CASE / f"{v}-input.json"), diff["input_sha256"][v])
    check(label + "parent sha", digest(PARENT), contract["parent_input_sha256"])
    check(label + "input sha", digest(run / "input.json"), inv["input_sha256"])
    check(label + "input equal source", inp, source)
    check(label + "parent diff", changes(parent, source), diff["parent_differences"][v])
    check(label + "contract sha", digest(CASE / "contract.json"), inv["contract_sha256"])
    check(label + "builder sha", digest(CASE / "build.py"), inv["builder_sha256"])
    check(label + "roundtrip checker sha", digest(CASE / "check_roundtrip.py"), inv["checker_sha256"])
    check(label + "runner sha", digest(CASE / "run_native_ssh.ps1"), inv["runner_script_sha256"])
    # The app-managed Python runtime at this path may update after the sealed
    # run. Its current hash is recorded below as a caveat, while closure
    # before/after provides the run-time binding.
    check(label + "SIMLOX sha", digest(SIMLOX), inv["simlox_exe_sha256"])
    check(label + "invocation binding", (inv["run_id"], inv["variant"], inv["parent_sha256"], inv["original_run_dir"].lower()), (run.name, v, contract["parent_input_sha256"], str(run).lower()))
    check(label + "source stable during run", closure["source_hashes_before"], closure["source_hashes_after"])
    check(label + "source hash set", closure["source_hashes_before"], inv["source_hashes_before"])
    check(label + "invocation sealed", digest(run / "invocation.json"), closure["invocation_sha256"])
    check(label + "closure run ID", closure["run_id"], inv["run_id"])
    check(label + "closure error", closure["error"], None)
    check(label + "sealed file count", len(closure["raw"]), 12)
    for fname, seal in closure["raw"].items():
        p = run / fname
        check(label + "seal " + fname, (p.stat().st_size, digest(p)), (seal["bytes"], seal["sha256"]))
    check(label + "native outputs nonempty", all((run / n).stat().st_size > 0 for n in ("model.sxi", "model.sxo", "model.log", "report-raw.json")), True)
    check(label + "session/SSH", (inv["execution_mode"], inv["session_id"], inv["ssh_connection_present"], "sshd.exe" in inv["ssh_ancestor_names"]), ("ssh_cli_v1", 0, True, True))
    check(label + "GUI identity", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["gui"]["start_utc"]), (13340, 1, "2026-09-28T10:09:56.8261381Z"))
    check(label + "queue mutex", inv["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
    check(label + "step names", [s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"])
    check(label + "step exits/status/GUI", [(s["exit_code"], s["status"], s["gui_preserved"], s["error"]) for s in steps], [(0,"completed",True,None)]*5)
    check(label + "step ordered times", all(steps[i]["completed_utc"] <= steps[i+1]["started_utc"] for i in range(4)), True)
    check(label + "planned command equality", [(s["name"],s["arguments"]) for s in steps[:4]], [(s["name"],s["arguments"]) for s in inv["planned_commands"]])
    check(label + "import completed", "Import completed!" in (run / "import.log").read_text(), True)
    check(label + "export log nonempty", (run / "export.log").stat().st_size > 0, True)
    runlog = (run / "run.log").read_text()
    m = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog)
    check(label + "conversion summary", m.groups() if m else None, ("0","2","0"))
    check(label + "warnings", re.findall(r"warning #(\d+)", runlog), ["108","126"])
    check(label + "report export", "Generating Json-report" in (run / "report-export.log").read_text(), True)
    nonempty = {name: rows(inp,name) for name,t in map_tables(inp).items() if any(i["rows"] for i in t["instances"])}
    check(label + "source populated table count", len(nonempty), 17)
    check(label + "roundtrip all source tables", nonempty, {name: rows(roundtrip,name) for name in nonempty})
    check(label + "source model setup", (rows(inp,"OperationProfile"), rows(inp,"MissionType"), rows(inp,"TaskBreakDown")), (rows(source,"OperationProfile"), rows(source,"MissionType"), rows(source,"TaskBreakDown")))

    expected_tags = ["<BASIC-MISSION,TEACH-UNIT,0,0,0>","<BASIC-MISSION,TEACH-UNIT,0,0,1>","<SECOND-MISSION,TEACH-UNIT,0,0,2>"]
    created = names_and_times(log,"mission created:")
    check(label + "three distinct tags", [tag for _,tag in created], expected_tags)
    approx(label + "mission notices", hours(log,"mission ordered:"), [1,7,7.25])
    approx(label + "created times", [t for t,_ in created], [1,7,7.25])
    check(label + "two launches same aircraft", [tag for _,tag in names_and_times(log,"mission starting,")], [expected_tags[0], expected_tags[2]])
    approx(label + "launch times", hours(log,"mission starting,"), [2,8.25])
    approx(label + "success times", hours(log,"mission success:"), [4,10.25])
    approx(label + "completion times", hours(log,"mission completed:"), [4,10.25])
    check(label + "cancelled tag", [tag for _,tag in names_and_times(log,"mission cancelled:")], [expected_tags[1]])
    approx(label + "cancelled time", hours(log,"mission cancelled:"), [7.58333])
    approx(label + "confiscation transfer", hours(log,"mission gives away system:"), [7.25])
    approx(label + "preassignment", hours(log,"mission preassigns a system:"), [7.25])
    check(label + "aircraft allocation", all("<TEACH-AIR-01,0>" in s for _,s in event(log,"mission allocates system:")), True)
    approx(label + "ready increased", hours(log,"nbr ready increased at unit:"), [0,4,7.25,10.25])
    approx(label + "ready decreased", hours(log,"nbr ready decreased at unit:"), [1,7,7.25])
    approx(label + "system ready at terminal mission", hours(log,"systems ready:"), [0,4,10.25])
    approx(label + "second BASIC SEQ1 performing", [t for t,s in event(log,"seqno 1 within system preparation task 1") if "starts performing" in s], [7])
    approx(label + "second BASIC SEQ1 completed", [t for t,s in event(log,"seqno 1 within system preparation task 1") if s.endswith("completed")], [7.16667])
    approx(label + "second BASIC SEQ2 stop", [t for t,s in event(log,"seqno 2 within system preparation task 1") if s.endswith("stopped")], [7.25])
    approx(label + "second preparation start", [t for t,s in event(log,"preparation started, mission:") if expected_tags[2] in s], [7.25])
    prep_end = 7.75 if v == "inspect-control" else 7.58333
    approx(label + "second preparation end", [t for t,s in event(log,"preparation ended, mission:") if expected_tags[2] in s], [prep_end])
    seq1_second = [t for t,s in event(log,"seqno 1 within system preparation task 2") if "starts performing" in s]
    skipped = [t for t,s in event(log,"seqno 1 within system preparation task 2") if s.endswith("skipped")]
    approx(label + "SECOND SEQ1 work", seq1_second, [7.25] if v == "inspect-control" else [])
    approx(label + "SECOND SEQ1 skip", skipped, [] if v == "inspect-control" else [7.25])
    approx(label + "SECOND SERVICE work", [t for t,s in event(log,"seqno 2 within system preparation task 2") if "starts performing" in s], [7.41667 if v == "inspect-control" else 7.25])
    approx(label + "SECOND SERVICE completion", [t for t,s in event(log,"seqno 2 within system preparation task 2") if s.endswith("completed")], [prep_end])
    if v == "refuelling":
        check(label + "native refuelling label on SEQ1", all("refuelling subtask" in s for _,s in event(log,"seqno 1 within system preparation task")), True)

    summary = rows(report,"ResultSummary","report")
    check(label + "report table names", [t["name"] for t in report["report"]["tables"]], ["ProblemDescription","ResultSummary","SystemResults","StockTotalResults"])
    check(label + "report description", rows(report,"ProblemDescription","report"), rows(inp,"ProblemDescription"))
    check(label + "result summary count", len(summary), 1)
    check(label + "summary horizon", (summary[0]["NREP"],summary[0]["RTILW"],summary[0]["RTIUP"]), (1,0,36))
    sy = rows(report,"SystemResults","report")
    check(label + "72 bins", len(sy), 72)
    check(label + "half-hour continuity", [(r["STINT"],r["ETINT"]) for r in sy], [(i/2,(i+1)/2) for i in range(72)])
    check(label + "one total-system identity", {(r["UNID"],r["SID"]) for r in sy}, {("Total over all Units","Total over all Systems")})
    approx(label + "four flight hours STACC", [sum(r["STACC"]*0.5 for r in sy)], [4])
    approx(label + "four flight hours FTMO", [sum(r["FTMO"]*0.5 for r in sy)], [4])
    check(label + "flight profiles agree", [r["STACC"] for r in sy], [r["FTMO"] for r in sy])
    check(label + "flight/mission profiles agree", [r["NSYMO"] for r in sy], [r["FTMO"] for r in sy])
    check(label + "first and second flight bins", {r["STINT"]: r["STACC"] for r in sy if r["STACC"]}, {2:1,2.5:1,3:1,3.5:1,8:0.5,8.5:1,9:1,9.5:1,10:0.5})
    by_start = {r["STINT"]:r for r in sy}
    approx(label + "prep bin 7-7.5", [by_start[7]["NSYMP"]], [1])
    approx(label + "prep bin 7.5-8", [by_start[7.5]["NSYMP"]], [0.5 if v == "inspect-control" else 1/6])
    check(label + "prep start bin", (by_start[7]["NPSTA"],by_start[7.5]["NPSUC"]), (2,1))
    terminal = by_start[35.5]
    check(label + "terminal state", (terminal["ETINT"],terminal["NSYRY"],terminal["NSYMA"],terminal["NSYMO"],terminal["NPSTA"]), (36,1,0,0,0))
    check(label + "no observed failure", {r["NFAIL"] for r in sy}, {0})
    stock = rows(report,"StockTotalResults","report")
    check(label + "72 stock bins", len(stock), 72)
    check(label + "stock half-hour continuity", [(r["STINT"],r["ETINT"]) for r in stock], [(i/2,(i+1)/2) for i in range(72)])
    return {"run_id":run.name,"summary":summary[0],"system_rows":sy,"stock_rows":stock,"report":report,"event_log":log,"closure_sha256":digest(run / "closure.json"),"recorded_python_sha256":inv["python_sha256"]}


def main():
    contract = parse(CASE / "contract.json")
    diff = parse(CASE / "exact-diff.json")
    parent = parse(PARENT)
    check("contract variant/version", (contract["variant_id"],contract["version"],contract["publication_state"]), ("B05.var01","1.0.1","not_published"))
    check("exact diff parent", diff["parent_sha256"], digest(PARENT))
    control = parse(CASE / "inspect-control-input.json")
    refuel = parse(CASE / "refuelling-input.json")
    check("pairwise source diff", changes(control,refuel), diff["pairwise_differences"])
    check("pairwise changed tables", sorted(changes(control,refuel)), ["ProblemDescription","TaskBreakDown"])
    prep_control = rows(control,"TaskBreakDown")
    prep_refuel = rows(refuel,"TaskBreakDown")
    check("only SEQ1 type changed", [(r["SEQ"],r["SUTID"],r["DURN"]) for r in prep_control], [(1,"INSPECT",1/6),(2,"SERVICE",1/3)])
    check("refuelling direct reference", [(r["SEQ"],r["SUTID"],r["DURN"]) for r in prep_refuel], [(1,"<REFUELLING>",1/6),(2,"SERVICE",1/3)])
    check("builtin not defined in SubTaskType", "<REFUELLING>" not in [r["SUTID"] for r in rows(refuel,"SubTaskType")], True)
    results = {v: review_variant(v,contract,diff,parent) for v in VARIANTS}
    c,r = results["inspect-control"],results["refuelling"]
    check("same result summary", c["summary"], r["summary"])
    check("same stock report", c["stock_rows"], r["stock_rows"])
    # The descriptive label and one preparation-work bin are the only raw
    # report changes; all other half-hour fields remain exactly equal.
    differences = []
    for i,(a,b) in enumerate(zip(c["system_rows"],r["system_rows"])):
        for field in a:
            if a[field] != b[field]:
                differences.append((i/2,field,a[field],b[field]))
    check("system-bin differences", differences, [(7.5,"NSYMP",0.5,0.1666666716337204),(7.5,"NSYMR",0.5,0.8333333134651184)])
    # Negative controls demonstrate source, event and bin predicates reject
    # altered in-memory values without modifying sealed evidence.
    check("negative control source hash", hashlib.sha256((CASE / "refuelling-input.json").read_bytes()+b"x").hexdigest() != diff["input_sha256"]["refuelling"], True)
    check("negative control missing skip", len(event(r["event_log"].replace(" skipped", " omitted"),"seqno 1 within system preparation task 2 on <TEACH-AIR-01,0> skipped")) != 1, True)
    check("negative control terminal ready", (r["system_rows"][-1]["NSYRY"]-1) != 1, True)
    decision = "GO_bounded_native_cli_candidate" if not failures else "NO_GO"
    result = {"schema":"simlox-b05-var01-v101-independent-readonly-review/v1","reviewer_script_sha256":digest(Path(__file__)),"decision":decision,"passed":not failures,"failures":failures,"check_count":len(checks),"checks":checks,"run_ids":{v:results[v]["run_id"] for v in VARIANTS},"closure_sha256":{v:results[v]["closure_sha256"] for v in VARIANTS},"runtime_python_sha256":{"recorded_at_run":results["refuelling"]["recorded_python_sha256"],"current_at_review":digest(PYTHON)},"observed":{"first_BASIC_flight_hours":[2,4],"confiscation_hour":7.25,"BASIC_cancellation_hour_printed":7.58333,"SECOND_flight_hours":[8.25,10.25],"SECOND_preparation_end_hour_printed":{"inspect-control":7.75,"refuelling":7.58333},"refuelling_SECOND_SEQ1":"native skipped marker; no positive-duration work","control_SECOND_SEQ1":"positive-duration work from 7.25 to 7.41667","terminal_hour":36,"terminal_ready_count":1},"scope":"One deterministic one-aircraft post-flight, active-preparation confiscation pair under pinned SIMLOX CLI and sealed source; direct built-in REFUELLING reference is skipped for SECOND while ordinary INSPECT repeats.","caveats":["Native log establishes the skipped marker and work timing, not fuel quantity or a general fuel-state rule.","The built-in refuelling step also performs before the first flight; post-flight need is demonstrated by the 7-hour execution after 2-4 flight, not by a measured fuel quantity.","The app-managed Python executable currently differs from its recorded run-time SHA-256; invocation and closure agree on the original before/after value, but current local bytes cannot independently reproduce it.","GUI model review, other preparation mechanisms, later flight reset, remote PM reset, resource waits, cross-engine parity and publication remain unverified.","Native report JSON has a trailing comma; raw byte hashes are checked before independent tolerant parsing."]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes((json.dumps(result,indent=2,ensure_ascii=False,default=list)+"\n").encode("utf-8"))
    print(json.dumps({"passed":result["passed"],"decision":decision,"checks":len(checks),"failures":failures,"report":str(OUT)},indent=2))
    return not failures


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

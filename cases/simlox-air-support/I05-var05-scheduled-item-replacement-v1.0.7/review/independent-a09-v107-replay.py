#!/usr/bin/env python3
"""Read-only independent replay of sealed I05.var05 v1.0.7 evidence."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
REVIEW = CASE / "review"
RUN_ID = "i05-var05-item-replacement-v107-ssh-20261009-01"
RAW = CASE / "runs" / RUN_ID / "raw"
SEAL = REVIEW / "v107-failure-seal.json"
SEAL_SHA = "90ab30ca55d18d1432a9b4f5ae0aab8d15375361c6855c4231ff2224bed9e7a0"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def near(a, b, eps=0.00011):
    return abs(float(a) - float(b)) <= eps

def strict_pairs(items):
    out = {}
    for key, value in items:
        if key in out:
            raise AssertionError("duplicate JSON key " + key)
        out[key] = value
    return out

def read_report(path):
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8")
    marks = re.findall(r",(\s*[\]}])", text)
    assert len(marks) == 1, f"expected exactly one trailing-comma marker, found {len(marks)}"
    normalized = re.sub(r",(\s*[\]}])", r"\1", text)
    return json.loads(normalized, object_pairs_hook=strict_pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(AssertionError(x)))

def rows(report, name):
    tables = [t for t in report["report"]["tables"] if t["name"] == name]
    assert len(tables) == 1, f"table {name} cardinality"
    cols = [c["name"] for c in tables[0]["columns"]]
    assert len(cols) == len(set(cols))
    flat = [r for ins in tables[0]["instances"] for r in ins["rows"]]
    assert all(len(r) == len(cols) for r in flat)
    return cols, [dict(zip(cols, row)) for row in flat]

def count(value):
    assert not isinstance(value, bool) and isinstance(value, (int, float))
    assert math.isfinite(float(value)) and float(value).is_integer() and value >= 0
    return int(value)

def main():
    assert SEAL.stat().st_size == 6315 and sha(SEAL) == SEAL_SHA
    seal = json.loads(SEAL.read_text(encoding="utf-8"), object_pairs_hook=strict_pairs)
    assert seal["status"] == "NO_GO_BEHAVIOR_CHECKER_FAILURE_PENDING_INDEPENDENT_REVIEW"
    assert seal["native_dispatches"] == 1 and seal["retry_count"] == 0
    assert seal["run_id"] == RUN_ID and seal["behavior_validation_file"] == "absent"
    pins = seal["raw_files"] + seal["supporting_files"]
    assert len(seal["raw_files"]) == 14 and len(seal["supporting_files"]) == 10
    for entry in pins:
        p = CASE / entry["path"]
        assert p.is_file(), entry["path"]
        assert p.stat().st_size == entry["bytes"], entry["path"] + " size"
        assert sha(p) == entry["sha256"], entry["path"] + " hash"
        assert p.stat().st_file_attributes == entry["attributes"], entry["path"] + " attrs"
    custody = json.loads((CASE / "runs" / RUN_ID / "raw-custody.json").read_text(encoding="utf-8"))
    assert custody["file_count"] == 14 and custody["all_copy_bytes_match"] is True
    by_name = {Path(e["path"]).name: e for e in seal["raw_files"]}
    assert len(by_name) == 14
    for entry in custody["files"]:
        assert entry["name"] in by_name
        assert entry["bytes"] == by_name[entry["name"]]["bytes"]
        assert entry["sha256"] == by_name[entry["name"]]["sha256"]
        assert entry["original_attributes"] == 32
        assert entry["copy_attributes_after_readonly"] == 33
    log_bytes = (RAW / "model.log").read_bytes()
    assert not log_bytes.startswith(b"\xef\xbb\xbf")
    assert log_bytes.endswith(b"\r\n") and log_bytes.count(b"\n") == log_bytes.count(b"\r\n")
    lines = log_bytes.decode("utf-8").splitlines()
    clock = re.compile(r"^Time: ([0-9]+(?:\.[0-9]+)?)\s+")
    timed = [(float(m.group(1)), line, i) for i, line in enumerate(lines) if (m := clock.match(line))]
    assert len(lines) == 214, len(lines)
    assert all(timed[i][0] <= timed[i+1][0] for i in range(len(timed)-1))
    task_pat = re.compile(r"^Time: ([0-9]+(?:\.[0-9]+)?)\s+system SURP task ([0-9]+) on <TEACH-AIR-01,0> (started|completed)$")
    task = {}
    for line in lines:
        if m := task_pat.fullmatch(line):
            t, ident, state = float(m.group(1)), m.group(2), m.group(3)
            assert state not in task.setdefault(ident, {}), (ident, state)
            task[ident][state] = t
    assert set(task) == {"0", "2", "4"}
    assert all(set(x) == {"started", "completed"} for x in task.values())
    tasks = sorted((x["started"], x["completed"], ident) for ident, x in task.items())
    assert all(start > 5 and near(end-start, 1.5) for start, end, _ in tasks)
    loose = re.compile(r"system SURP task ([0-9]+) on <TEACH-AIR-01,0> (started|completed)")
    loose_matches = [(ident, state) for _, line, _ in timed if (m := loose.search(line))
                     for ident, state in [(m.group(1), m.group(2))]]
    assert len(loose_matches) > 6
    assert len([x for x in loose_matches if x == ("0", "started")]) > 1

    def events(pattern):
        pat = re.compile(pattern)
        return [(t, m.group(1), i) for t, line, i in timed if (m := pat.search(line))]

    damage = events(r"Damage BATTLE-HIT occured\. Damaged items: <TEACH-LRU-01,0,(\d+)>")
    demand = events(r"Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,(\d+)>$")
    issue = events(r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock\s*$")
    removed = events(r"Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)> from position <TEACH-AIR-01,BASE-01,0> damaged")
    repair_start = events(r"Start repair of item <TEACH-LRU-01,0,(\d+)>$")
    repair_work = events(r"direct repair subtask \d+ seqno 0 within item DIRP task \d+ on <TEACH-LRU-01,0,(\d+)> starts performing, planned to last for 1 hours$")
    repair_done = events(r"Finished repair of item <TEACH-LRU-01,0,(\d+)>$")
    arrival = events(r"Replacement item arrives <TEACH-LRU-01,0,(\d+)>$")
    returned = events(r"Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock\s*$")
    streams = [damage,demand,issue,removed,repair_start,repair_work,repair_done,arrival,returned]
    assert all(len(x) == 3 for x in streams), [len(x) for x in streams]
    assert [x[1] for x in damage] == ["1","2","3"]
    assert [x[1] for x in issue] == ["0","1","2"]
    for stream in [demand,removed,repair_start,repair_work,repair_done,arrival,returned]:
        assert [x[1] for x in stream] == ["1","2","3"]
    cycles = []
    for i in range(3):
        d,q,s,x,r,w,c,a,b = [stream[i] for stream in streams]
        ts,te,ident = tasks[i]
        assert d[0] < q[0] and near(q[0],s[0])
        assert s[0] <= x[0] <= r[0] <= w[0] < c[0]
        assert near(c[0]-w[0],1) and near(c[0],a[0]) and near(c[0],b[0])
        assert near(ts,s[0]) and near(te,w[0]+0.75) and te < c[0]
        assert re.fullmatch(r"\s+Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:\s*", lines[s[2]+1])
        assert re.fullmatch(r"\s+Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,"+b[1]+r">,\s*", lines[b[2]+1])
        cycles.append({"task_id":ident,"damage":d[0],"issue":s[0],"aircraft_ready":te,
                       "repair_start":w[0],"restock":b[0],"draw_id":s[1],"returned_id":b[1]})
    report = read_report(RAW / "report-raw.json")
    names = [x["name"] for x in report["report"]["tables"]]
    assert names == ["ProblemDescription","ResultSummary","SystemResults","StockTotalResults"]
    parent_index = CASE.parent / "H02-var04-item-damage-replacement-fallback-v1.0.0" / "evidence-index.json"
    parent_run = json.loads(parent_index.read_text(encoding="utf-8"))["accepted_runs"]["fallback"]
    parent_report_path = Path(parent_run["local_path"]) / "report-raw.json"
    assert sha(parent_report_path) == parent_run["report_sha256"]
    parent_report = read_report(parent_report_path)
    assert [t["name"] for t in parent_report["report"]["tables"]] == names
    for name in names:
        observed = [c["name"] for t in report["report"]["tables"] if t["name"] == name for c in t["columns"]]
        accepted = [c["name"] for t in parent_report["report"]["tables"] if t["name"] == name for c in t["columns"]]
        assert observed == accepted, "report columns differ from accepted parent: " + name
    summary_cols, summary = rows(report,"ResultSummary")
    system_cols, system = rows(report,"SystemResults")
    stock_cols, stock = rows(report,"StockTotalResults")
    assert len(summary_cols)==11 and len(system_cols)==40 and len(stock_cols)==16
    assert len(summary)==1 and len(system)==72 and len(stock)==72
    typed_cells = sum(len(t["columns"])*sum(len(ins["rows"]) for ins in t["instances"])
                      for t in report["report"]["tables"])
    assert typed_cells == 4044
    def bins(events):
        out=[0]*72
        for t,_,_ in events:
            assert 0 <= t < 36
            out[min(int(math.floor((t+1e-9)*2)),71)] += 1
        return out
    damage_bins = bins(damage)
    completion_bins = bins([(end, ident, -1) for start,end,ident in tasks])
    demand_bins = bins(demand)
    assert [count(r["NDAM"]) for r in system] == damage_bins
    assert [count(r["NREPT"]) for r in system] == completion_bins
    assert [count(r["NDD"]) for r in stock] == demand_bins
    assert [count(r["NWT"]) for r in stock] == demand_bins
    assert all(count(r["NBO"])==0 and near(r["PNB"],1) for r in stock)
    for i,(sysrow,stkrow) in enumerate(zip(system,stock)):
        assert sysrow["UNID"]=="Total over all Units" and sysrow["SID"]=="Total over all Systems"
        assert near(sysrow["STINT"],i/2) and near(sysrow["ETINT"],(i+1)/2)
        assert near(stkrow["STINT"],i/2) and near(stkrow["ETINT"],(i+1)/2)
        assert near(sum(float(sysrow[k] or 0) for k in ("NSYA","NSYUA","NSYLA")),1)
        assert near(sum(float(sysrow[k] or 0) for k in ("NSYRY","NSYMA","NSYUA","NSYLA")),1)
        assert near(sysrow["NFAIL"] or 0,0) and near(sysrow["NSYLA"] or 0,0)
    exposure=sum(float(r["NSYRP"] or 0) for r in system)/2
    assert near(exposure,4.5,0.0002)
    assert near(system[-1]["NSYRY"],1)
    assert near(summary[0]["MSTF"],1) and near(summary[0]["MSUF"],0)
    return {"verdict":"CHECKER_DEFECT_WITH_BOUNDED_RAW_BEHAVIOR_PASS",
            "sealed_files_verified":len(pins),"raw_files":14,"raw_copies_checked":14,
            "physical_lines":len(lines),"timed_lines":len(timed),
            "task_pairs":tasks,"legacy_unanchored_task_matches":len(loose_matches),
            "legacy_task0_started_matches":len([x for x in loose_matches if x==("0","started")]),
            "cycles":cycles,"report_rows":{"summary":len(summary),"system":len(system),"stock":len(stock)},
            "report_typed_cells":typed_cells,"report_system_repair_hours":exposure,
            "damage_bins_nonzero":[i for i,x in enumerate(damage_bins) if x],
            "completion_bins_nonzero":[i for i,x in enumerate(completion_bins) if x],
            "demand_bins_nonzero":[i for i,x in enumerate(demand_bins) if x],
            "limitations":["Only report fields asserted by the frozen checker were replayed; other report values retain byte custody without semantic acceptance.","The original v107 checker failed and its missing validation output remains missing; this replay does not reclassify the native attempt as accepted."]}

if __name__ == "__main__":
    print(json.dumps(main(),sort_keys=True,indent=2))
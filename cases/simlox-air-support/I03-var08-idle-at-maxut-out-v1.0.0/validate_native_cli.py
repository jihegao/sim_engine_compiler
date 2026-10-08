"""Read-only bounded I03.var08 child behavior checker."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
from build import parse,typed_equal
from event_ledger import parse_bytes as check_log
from report_oracle import parse as parse_report,validate as check_report
from source_gate import INPUT_SHA,RUN_ID

HERE=Path(__file__).resolve().parent
SCHEMA="i03-var08-idle-maxut-behavior/v1"

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def converter(text,run):
    def exact_path(label,suffix):
        lines=re.findall(rf"(?m)^{re.escape(label)}: ([^\r\n]+)\r?$",text)
        assert len(lines)==1,(label,lines)
        expected=str((run.resolve()/f"model.{suffix}")).replace("\\","/")
        assert lines[0].replace("\\","/")==expected,(label,lines[0],expected)
    exact_path("Input file","sxi")
    exact_path("Output file","sxo")
    exact_path("File","sxi")
    assert len(re.findall(r"(?m)^Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0\r?$",text))==1
    warnings=re.findall(r"(?m)^Form: ([^\r\n]+)\r?\n(rec [^\r\n]+)\r?$",text)
    assert warnings==[
        ("Control","rec 1: (warning #108) Enabling simulation log may generate extensive data in log file"),
        ("System","rec 1: (warning #126) This system contains no items: TEACH-AIR-01"),
    ],warnings
    assert len(re.findall(r"(?m)^Form: ",text))==len(re.findall(r"(?m)^rec ",text))==2
    codes=[(kind.lower(),code) for kind,code in re.findall(r"\b(warning|error|notice|note)\s*#(\d+)",text,re.I)]
    assert codes==[("warning","108"),("warning","126")],codes
    assert text.count("Input conversion completed.")==1
    assert text.count("Starting simulation")==text.count("Saving results")==1

def check(run,log_override=None,report_override=None):
    assert run.name==RUN_ID
    assert sha(run/"input.json")==INPUT_SHA
    assert typed_equal(parse((HERE/"native-input.json").read_bytes()),parse((run/"input.json").read_bytes()))
    log_bytes=(run/"model.log").read_bytes() if log_override is None else log_override
    timeline=check_log(log_bytes)
    raw_report=(run/"report-raw.json").read_bytes() if report_override is None else report_override
    report=check_report(parse_report(raw_report),True)
    converter((run/"model-run.log").read_text(encoding="utf-8-sig",errors="strict"),run)
    terminal=timeline["terminal"]
    assert {k:terminal[k] for k in ("local","nominal","booked","reserved_OUT","pending_OUT","backorder","ready_aircraft")}=={
        "local":1,"nominal":1,"booked":0,"reserved_OUT":0,"pending_OUT":0,"backorder":0,"ready_aircraft":2}
    return {"schema":SCHEMA,"passed":True,"issues":[],"run_id":RUN_ID,
            "input_sha256":INPUT_SHA,"report_cell_checks":report["cells_checked"],
            "timed_event_records":sum(line.startswith("Time:") for line in log_bytes.decode("utf-8-sig").splitlines()),
            "timeline":timeline,"report":report}

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("run",type=Path)
    args=ap.parse_args()
    try:result=check(args.run)
    except Exception as exc:result={"schema":SCHEMA,"passed":False,"issues":[f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(result,ensure_ascii=False,separators=(",",":")))
    raise SystemExit(0 if result["passed"] else 1)

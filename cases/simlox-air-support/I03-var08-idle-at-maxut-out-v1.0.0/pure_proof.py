"""One-shot local PURE proof with original binary streams; no native command."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

HERE=Path(__file__).resolve().parent
PYTHON=Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
SOURCES=("contract.json","native-input.json","exact-diff.json","build.py",
         "event_ledger.py","report_oracle.py","source_gate.py","check_roundtrip.py",
         "validate_native_cli.py","self_check.py","run_native_ssh.ps1")
TOOLS=(("build",["build.py"]),("context",["copy_context.py"]),
       ("source",["source_gate.py","--mode","live"]),
       ("selfcheck",["self_check.py"]),
       ("inventory",["make_source_inventory.py","--provisional"]),
       ("manifest",["make_prelaunch_manifest.py","--provisional"]))

def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def pin(path):
    data=path.read_bytes()
    return {"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}

def capture():
    assert sys.argv[1:]==["--capture"]
    run=HERE/"runs"/"i03-var08-idle-maxut-out-v100-ssh-20261008-01"
    assert not run.exists()
    name="local-pure-"+dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+"-"+uuid.uuid4().hex[:8]
    directory=HERE/"test-output"/name
    directory.mkdir(parents=True,exist_ok=False)
    before={n:pin(HERE/n) for n in SOURCES}
    checks=[]
    for label,argv in TOOLS:
        command=[str(PYTHON),"-X","utf8","-B",str(HERE/argv[0]),*argv[1:]]
        out=directory/(label+"-stdout.bin")
        err=directory/(label+"-stderr.bin")
        started=utc()
        with out.open("xb") as stdout,err.open("xb") as stderr:
            proc=subprocess.run(command,cwd=HERE,stdout=stdout,stderr=stderr)
        checks.append({"name":label,"command":command,"started_utc":started,
                       "completed_utc":utc(),"actual_exit":proc.returncode,
                       "stdout_path":str(out),"stdout":pin(out),
                       "stderr_path":str(err),"stderr":pin(err)})
        if proc.returncode!=0 or err.stat().st_size!=0:break
    after={n:pin(HERE/n) for n in SOURCES}
    receipt={"schema":"i03-var08-local-pure-proof/v1","native_calls":0,
             "run_absent_before_and_after":not run.exists(),"source_before":before,
             "source_after":after,"checks":checks,
             "passed":len(checks)==len(TOOLS) and all(type(c["actual_exit"]) is int and c["actual_exit"]==0 and c["stderr"]["bytes"]==0 for c in checks) and before==after}
    path=directory/"receipt.json"
    with path.open("xb") as f:f.write((json.dumps(receipt,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    for f in directory.iterdir():f.chmod(0o444)
    print(json.dumps({"receipt":str(path),**pin(path),"passed":receipt["passed"]},sort_keys=True))
    return 0 if receipt["passed"] else 1

if __name__=="__main__":raise SystemExit(capture())

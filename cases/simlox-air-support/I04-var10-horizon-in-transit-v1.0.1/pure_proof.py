"""One-shot local PURE proof with original binary streams; no native command."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid
from make_source_inventory import paths as owned_paths

HERE=Path(__file__).resolve().parent
PYTHON=Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
SOURCES=tuple(owned_paths(True))
TOOLS=(("build",["build.py"]),("context",["copy_context.py"]),
       ("source",["source_gate.py","--mode","live"]),
       ("selfcheck",["self_check.py"]),
       ("converter",["test_converter_gate.ps1"]),
       ("inventory",["make_source_inventory.py","--provisional"]),
       ("manifest",["make_prelaunch_manifest.py","--provisional"]))

def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def pin(path):
    data=path.read_bytes()
    return {"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}

def capture():
    assert sys.argv[1:]==["--capture"]
    run=Path(r"C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\tmp\native-runs\i04v10-v101-20261008-01")
    assert not run.exists()
    name="local-pure-"+dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+"-"+uuid.uuid4().hex[:8]
    directory=HERE/"test-output"/name
    before={n:pin(HERE/n) for n in SOURCES}
    for name in SOURCES:
        assert (HERE/name).stat().st_file_attributes & 1, (name,"source not read-only")
    directory.mkdir(parents=True,exist_ok=False)
    checks=[]
    failure=None
    try:
        for label,argv in TOOLS:
            if label == "converter":
                command=["powershell.exe","-NoProfile","-NonInteractive","-File",str(HERE/argv[0])]
            else:
                command=[str(PYTHON),"-X","utf8","-B",str(HERE/argv[0]),*argv[1:]]
            out=directory/(label+"-stdout.bin")
            err=directory/(label+"-stderr.bin")
            started=utc()
            actual_exit=None
            capture_error=None
            try:
                with out.open("xb") as stdout,err.open("xb") as stderr:
                    proc=subprocess.run(command,cwd=HERE,stdout=stdout,stderr=stderr)
                    actual_exit=proc.returncode
            except Exception as exc:
                capture_error=f"{type(exc).__name__}: {exc}"
            checks.append({"name":label,"command":command,"started_utc":started,
                           "completed_utc":utc(),"actual_exit":actual_exit,
                           "capture_error":capture_error,
                           "stdout_path":str(out),"stdout":pin(out) if out.is_file() else None,
                           "stderr_path":str(err),"stderr":pin(err) if err.is_file() else None})
            if type(actual_exit) is not int or actual_exit!=0 or not err.is_file() or err.stat().st_size!=0:
                break
    except Exception as exc:
        failure=f"{type(exc).__name__}: {exc}"
    observed_after={n:pin(HERE/n) if (HERE/n).is_file() else None for n in SOURCES}
    receipt={"schema":"i04-var10-local-pure-proof/v101","native_calls":0,
             "native_run_directory":str(run),
             "run_absent_before_and_after":not run.exists(),"source_before":before,
             "source_after":observed_after,"checks":checks,"capture_error":failure,
             "passed":failure is None and len(checks)==len(TOOLS) and all(
                 type(c["actual_exit"]) is int and c["actual_exit"]==0 and
                 c["stderr"] is not None and c["stderr"]["bytes"]==0 for c in checks)
                 and before==observed_after}
    path=directory/"receipt.json"
    with path.open("xb") as f:f.write((json.dumps(receipt,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    for f in directory.iterdir():f.chmod(0o444)
    print(json.dumps({"receipt":str(path),**pin(path),"passed":receipt["passed"]},sort_keys=True))
    return 0 if receipt["passed"] else 1

if __name__=="__main__":raise SystemExit(capture())

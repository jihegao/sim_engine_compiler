"""Read-only independent replay of D14.var04 native converter rejection."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent
PARENT = CASE.parent / "D14-var01-monitored-item-pm-v1.0.1"
Y_SOURCE = PARENT / "native-input-monitored.json"
N_SOURCE = PARENT / "native-input-system-converted.json"
Y_CLOSURE = PARENT / "runs/d14-var01-monitored-v101-ssh-20261002-01/closure.json"
N_CLOSURE = PARENT / "runs/d14-var01-system-converted-v101-ssh-20261002-01/closure.json"
SOURCE = CASE / "native-input.json"
RUN = CASE / "runs/d14-var04-position-monit-y-v100-ssh-20261002-01"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICT = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
OUT = CASE / "independent-verdict.json"
COUNT = 0
FAILURES = []


def check(ok, label):
    global COUNT
    COUNT += 1
    if not ok:
        FAILURES.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(path):
    return {t["name"]:t for t in read(path)["model"]["tables"]}


def rows(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names,row)) for inst in table["instances"] for row in inst["rows"]]


def main():
    contract, diff = read(CASE/"contract.json"), read(CASE/"exact-diff.json")
    check(sha(Y_SOURCE)==contract["accepted_parent"]["input_sha256"]==diff["parent_sha256"],"accepted MONIT Y source")
    check(sha(Y_CLOSURE)==contract["accepted_parent"]["native_closure_sha256"],"accepted MONIT Y closure")
    check(sha(SOURCE)==contract["input_sha256"]==diff["input_sha256"],"frozen child source")
    check(sha(CASE/"exact-diff.json")==contract["exact_diff_sha256"],"frozen exact diff")
    check(sha(MANUAL)==contract["source"]["manual_sha256"],"manual SHA")
    check(sha(DICT)==contract["source"]["dictionary_sha256"],"dictionary SHA")
    check(sha(EXE)=="fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "native CLI SHA")
    old, new = tables(Y_SOURCE), tables(SOURCE)
    check(set(old)==set(new),"same table topology")
    actual={n:{"before":old[n],"after":new[n]} for n in old if old[n]!=new[n]}
    check(actual==diff["changed"] and set(actual)=={"MaterielPM","ProblemDescription"},
          "exact position MID and description table delta")
    old_pm, pm = rows(old["MaterielPM"])[0], rows(new["MaterielPM"])[0]
    check({k:(old_pm[k],pm[k]) for k in old_pm if old_pm[k]!=pm[k]}=={"MID":("TEACH-LRU-01","POS-A")} and
          pm["MONIT"]==old_pm["MONIT"]=="Y" and pm["PMID"]=="LRU-OP2",
          "position MID alone changed while MONIT Y held")
    check(rows(new["MaterielPosition"])[0]["MPID"]=="POS-A", "position source identity exists")
    closure, invocation, steps = [read(RUN/name) for name in ("closure.json","invocation.json","steps.json")]
    check(closure["run_id"]==invocation["run_id"]==RUN.name,"run identity")
    check(sha(RUN/"invocation.json")==closure["invocation_sha256"],"invocation SHA")
    check(invocation["source_hashes_before"]==closure["source_hashes_before"]==closure["source_hashes_after"],
          "pre/post source seals stable")
    pins={"input":SOURCE,"parent_y":Y_SOURCE,"parent_y_closure":Y_CLOSURE,
          "parent_n":N_SOURCE,"parent_n_closure":N_CLOSURE,
          "contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json",
          "builder":CASE/"build.py","diff_builder":CASE/"describe_diff.py",
          "checker":CASE/"check_roundtrip.py","runner":CASE/"run_native_ssh.ps1",
          "python":PYTHON,"exe":EXE,"manual":MANUAL,"dictionary":DICT}
    for key,path in pins.items():
        check(sha(path)==closure["source_hashes_before"][key],f"source seal {key}")
    check(len(closure["raw"])==9,"nine negative-run raw seals")
    for name,seal in closure["raw"].items():
        path=RUN/name
        check(path.exists() and path.stat().st_size==seal["bytes"],f"raw size {name}")
        check(sha(path)==seal["sha256"],f"raw digest {name}")
    check(sha(RUN/"input.json")==sha(SOURCE),"native input matches frozen source")
    check(invocation["execution_mode"]=="session0_ssh_cli" and invocation["session_id"]==0 and
          "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]],"SSH session zero")
    check(invocation["queue_mutex"]=="Global\\SimloxIssue18NativeQueue" and
          invocation["gui"]["pid"]==13340 and invocation["gui"]["session_id"]==1,
          "mutex and GUI preservation")
    check([s["name"] for s in steps]==["import","export","calc","check_import_export"],
          "four ordered diagnostic steps")
    for s in steps:
        check(s["exit_code"]==0 and s["gui_preserved"] is True and
              s["status"] in ("completed","expected_rejection"),f"diagnostic step {s['name']}")
    check(steps[2]["status"]=="expected_rejection", "calculation rejected as predeclared")
    exported=tables(RUN/"roundtrip-raw.json")
    populated=[n for n,t in new.items() if any(inst["rows"] for inst in t["instances"])]
    check(len(populated)==20 and set(exported)>=set(new),"twenty authored row-containing tables")
    for name in populated:
        check(exported[name]["columns"]==new[name]["columns"] and
              exported[name]["instances"]==new[name]["instances"],f"native roundtrip {name}")
    log=(RUN/"run.log").read_text(encoding="utf-8-sig",errors="replace")
    check("Form: MaterielPM" in log and
          "rec 1: (error #361) MONIT is not allowed for materiel positions:  POS-A" in log,
          "exact #361 position-MONIT rejection")
    check("Input conversion completed. Errors: 1, Warnings: 1, Notes: 0" in log and
          log.count("(error #") == 1 and "warning #108" in log,
          "one conversion error and only expected warning")
    check((RUN/"model.sxo").stat().st_size==4 and not (RUN/"model.log").exists() and
          not (RUN/"report-raw.json").exists(),"four-byte unusable SXO and no event/report output")
    result={"schema":"simlox-independent-readonly-d14-var04/v1","passed":not FAILURES,
            "verdict":"GO: bounded native #361 converter rejection" if not FAILURES else
                      "NO-GO: independent replay failed","checks_passed":COUNT-len(FAILURES),
            "checks_total":COUNT,"failures":FAILURES,
            "evidence":{"input_sha256":sha(SOURCE),"parent_input_sha256":sha(Y_SOURCE),
                        "closure_sha256":sha(RUN/"closure.json"),"run_log_sha256":sha(RUN/"run.log"),
                        "roundtrip_sha256":sha(RUN/"roundtrip-raw.json"),"sxo_bytes":(RUN/"model.sxo").stat().st_size},
            "finding":"With the accepted MONIT=Y item PM source changed only from MaterielPM.MID TEACH-LRU-01 to position POS-A (plus description), the installed native converter reports MaterielPM error #361: MONIT is not allowed for materiel positions. Import/export preserves all 20 authored row-containing tables. The 4-byte SXO contains no usable simulation result and no event or JSON report was produced.",
            "limits":["One PM row, position and installed SIMLOX version; this is a converter boundary, not a runtime PM outcome.",
                      "It does not reject MONIT=N position PM or all position-linked PM configurations.",
                      "No GUI visual or cross-engine claim."]}
    OUT.write_bytes((json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8"))
    print(json.dumps({"passed":result["passed"],"checks_total":COUNT,"failures":FAILURES,
                      "verdict":result["verdict"],"output":str(OUT)},ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__=="__main__":
    raise SystemExit(main())

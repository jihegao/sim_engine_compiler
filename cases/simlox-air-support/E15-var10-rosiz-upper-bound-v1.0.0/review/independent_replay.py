"""Independent, read-only replay of the sealed E15.var10 diagnostic."""
import hashlib
import json
import pathlib
import re

CASE = pathlib.Path(__file__).resolve().parents[1]
BASE = CASE.parent
RUN = CASE / "runs/e15-var10-rosiz-over-limit-v100-ssh-20261005-01"
PARENT = BASE / "E15-var07-explicit-istoh-v1.0.1"
E02 = BASE / "E02-zero-stock-local-backorder-v1.0.0"
OUT = CASE / "review/independent-verdict.json"
checks = []


def check(label, good):
    checks.append({"name": label, "passed": bool(good)})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path):
    raw = path.read_text(encoding="utf-8-sig")
    chars = []
    quoted = escaped = False
    for i, ch in enumerate(raw):
        if quoted:
            chars.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
            chars.append(ch)
        elif ch == ',':
            j = i + 1
            while j < len(raw) and raw[j].isspace():
                j += 1
            if j == len(raw) or raw[j] not in "]}":
                chars.append(ch)
        else:
            chars.append(ch)
    return json.loads("".join(chars))


contract = data(CASE / "contract.json")
closure = data(RUN / "closure.json")
inv = data(RUN / "invocation.json")
outcome = data(RUN / "outcome.json")
steps = data(RUN / "steps.json")
source_paths = {
    "contract": CASE / "contract.json",
    "input": CASE / "native-input.json",
    "builder": CASE / "build.py",
    "roundtrip_checker": CASE / "check_roundtrip.py",
    "parent_input": PARENT / "native-input-explicit-three.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-02.md",
    "e02_input": E02 / "native-input.json",
    "e02_signoff": E02 / "cli-scope-signoff-2026-09-29.md",
    "exe": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": CASE / "run_native_ssh.ps1",
    "python": pathlib.Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check("run identity", closure["run_id"] == contract["run_id"] == inv["run_id"])
check("invocation seal", closure["invocation_sha256"] == sha(RUN / "invocation.json"))
check("session zero and SSH ancestor", inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"])
check("protected GUI recorded", inv["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
check("global queue recorded", inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
check("source before/after identical", closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
for key, path in source_paths.items():
    check("source seal " + key, sha(path) == closure["source_hashes_before"][key])
check("parent input pin", sha(source_paths["parent_input"]) == contract["prerequisites"]["E15"]["input_sha256"])
check("E02 input pin", sha(source_paths["e02_input"]) == contract["prerequisites"]["E02"]["input_sha256"])
check("copied input seal", sha(RUN / "input.json") == sha(CASE / "native-input.json"))
check("raw closure count", len(closure["raw"]) == 11)
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    check("raw seal " + name, path.exists() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
check("three completed guarded steps", [s["name"] for s in steps] == ["import", "export", "calc_converter_gate"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))

parent = data(source_paths["parent_input"])
child = data(CASE / "native-input.json")
stock = next(t for t in child["model"]["tables"] if t["name"] == "StockAllocation")
depot = next(r for r in stock["instances"][0]["rows"] if r[:3] == ["AIR_BASIC", "TEACH-DU-01", "DEPOT-01"])
check("31 table source", len(child["model"]["tables"]) == len(parent["model"]["tables"]) == 31)
check("one-cell ROSIZ delta", depot[3:7] == [4, 6, None, 3] and all(
    (lambda a, b: a == b)(p, {**c, "instances": [{**c["instances"][0], "rows": [r[:4] + [2] + r[5:] if r[:3] == depot[:3] else r for r in c["instances"][0]["rows"]]}]})
    if c["name"] == "StockAllocation" else p == c
    for p, c in zip(parent["model"]["tables"], child["model"]["tables"])))
check("manual arithmetic", depot[3] - depot[4] == -2 and depot[4] > depot[3] + 1)

exported = native_json(RUN / "roundtrip-raw.json")
export_tables = {(t["name"], i["instance_name"]): (t["columns"], i["rows"]) for t in exported["model"]["tables"] for i in t["instances"]}
authored = 0
for table in child["model"]["tables"]:
    for instance in table["instances"]:
        if instance["rows"]:
            authored += 1
            got = export_tables.get((table["name"], instance["instance_name"]))
            check("authored roundtrip " + table["name"] + "/" + instance["instance_name"], got == (table["columns"], instance["rows"]))
check("21 authored row-containing instances", authored == 21)

log = (RUN / "run.log").read_text(encoding="utf-8-sig")
events = (RUN / "model.log").read_text(encoding="utf-8-sig")
parent_events = (PARENT / "runs/e15-var07-explicit-three-v101-ssh-20261002-01/model.log").read_text(encoding="utf-8-sig")
check("zero errors and warning 108+168", re.search(r"Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0", log) and re.findall(r"\(warning #(\d+)\)", log) == ["108", "168"])
check("specific ROSIZ warning", "Reorder size too large (ROSIZ > STSIZ+1): TEACH-DU-01" in log)
check("calculation completed", "Starting simulation..." in log and "Saving results ..." in log and (RUN / "model.sxo").stat().st_size > 4)
check("three mission outcomes", events.count("mission starting, duration: 2") == 3 and events.count("mission aborted:") == 1 and events.count("mission success") >= 2)
check("stock opening and demand", "Level: 3 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>" in events and "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Item demand arrives" in events)
check("no reorder task in child", "reorder task" not in events and "Delivery with" not in events)
check("accepted parent does reorder", "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started" in parent_events and "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives" in parent_events)
check("same physical first failure and repair", "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in events and "Time: 10.1667 <TEACH-DU-01,0,BASE-01,0> Item discarded: <TEACH-DU-01,0,4>" in events and "Time: 10.5  system SURP task 0 on <TEACH-AIR-01,0> completed" in events)
check("frozen negative gate failed", outcome["converter_summary"] == [0, 2, 0] and outcome["expected_negative"] is False and closure["expected_negative"] is False and outcome["error"] == "expected converter error absent")
check("no report export sealed", not any(n.startswith("report") for n in closure["raw"]))

failures = [x["name"] for x in checks if not x["passed"]]
result = {
    "decision": "NO_GO_FROZEN_NEGATIVE_GATE",
    "passed": not failures,
    "checks_passed": len(checks) - len(failures),
    "checks_total": len(checks),
    "failures": failures,
    "run_id": contract["run_id"],
    "closure_sha256": sha(RUN / "closure.json"),
    "source_input_sha256": sha(CASE / "native-input.json"),
    "observed": "Converter errors 0, warnings #108 and #168; valid 358607-byte SXO and native event log. The child has no h10 reorder task or h11 two-item delivery seen in the accepted parent.",
    "scope": "Sealed diagnostic of this installed CLI, source, and seed. No formal acceptance of the predeclared error-rejection hypothesis; no report-bin or population claim.",
}
OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({k: result[k] for k in ("decision", "checks_passed", "checks_total", "failures")}, ensure_ascii=False))

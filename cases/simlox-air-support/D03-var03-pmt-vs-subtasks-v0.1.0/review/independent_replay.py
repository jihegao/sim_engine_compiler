"""Independent, read-only D03.var03 replay from sealed native and parent bytes."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN_ID = "d03-var03-pmt4-task1-v010-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
PARENT = ROOT / "D03-calendar-pm-v1.0.0"
PRUN = PARENT / "runs" / "d03-calendar-v100-ssh-20261001-02"
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
OUT = CASE / "review" / "independent-verdict.json"

PINS = {
    "input": (CASE / "native-input.json", "59642b8ef5ac9e48c45110223b147cf776e0be4e0e8983a2e9507b1412074a36"),
    "parent": (PARENT / "native-input.json", "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"),
    "parent_signoff": (PARENT / "cli-scope-signoff-2026-09-30.md", "8c609dc19b1a4b7f027da9538096c5171244609b80cab9026e1ad360cd9006d1"),
    "parent_closure": (PRUN / "closure.json", "9cd845f957105eb8659809ec09cf380ae5df68a63babb264d70631c164f7d2d8"),
    "a02_signoff": (ROOT / "A02-single-aircraft-repeated-missions" / "cli-scope-signoff-2026-09-29.md", "608eef828a65ef7a8c738a3ec227b890421c29248ee8addd9e992a4c7e7e919e"),
    "b02_evidence": (ROOT / "B02-serial-preparation-v1.0.2" / "evidence-2026-09-29.md", "bceddd5983e9187bf8be19464b04ad5b2136bf665f6d4d9d676928b8c2354c61"),
    "contract_review": (CASE / "review" / "independent-contract-go-2026-10-06.md", "b6f29fe0f3fbe26cbb564a687318f6600d6977feba76da8174f4b0a0c83a60fc"),
    "j09_signoff": (ROOT / "J09-var05-pmt-fallback-pair-v1.0.1" / "cli-scope-signoff-2026-10-04.md", "42d1d718462057e64208b7bd1d8d45e8d2d17fece7b22b9242b0f14f62701ac9"),
    "contract": (CASE / "contract.json", "8c020a92a4be471f43d6bb401ed0c7c80b5c54b58cd6eb6e4f5a2830d5bd52bd"),
    "builder": (CASE / "build.py", "a81b556f74822dd2a4b606dcbc7282fe25b7e639b317db6b08a3997ff40507f1"),
    "checker": (CASE / "check_roundtrip.py", "dc22174c799b7c9b97bfd0af219f1e1f9b513681f5e1a0de1495659d25e0a8fc"),
    "diff_checker": (CASE / "check_parent_diff.py", "0fdaff2b6f0a2b2daf14176d1d8a26f0eb94de8c93cac0fac1d8dadc4c732ee0"),
    "validator": (CASE / "validate_native_cli.py", "412b6f7be9f79d9e9f9dbe5c1bc00eb65642585ef2c1746e68655e95004c678d"),
    "python": (PYTHON, "372c2eae555b344520bf147be0096e009069aeca4e7f78d6aecea6d53158056a"),
    "runner_script": (CASE / "run_native_ssh.ps1", "27c374086ede87b9dcb4a3c024d4b5069fc6bce3367801d60d0e4ad8c1579bff"),
    "simlox_exe": (EXE, "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"),
}

count = 0
failures: list[dict] = []


def check(label: str, actual: object, expected: object) -> None:
    global count
    count += 1
    if actual != expected:
        failures.append({"check": label, "actual": actual, "expected": expected})


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        out = []
        quoted = escaped = False
        for i, char in enumerate(text):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == "," and text[i + 1 :].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def tables(doc: dict, root: str) -> dict[str, dict]:
    result = {}
    for table in doc[root]["tables"]:
        name = table["name"]
        check("unique " + root + " table " + name, name in result, False)
        result[name] = table
    return result


def rows(table: dict) -> list[dict]:
    fields = [column["name"] for column in table["columns"]]
    result = []
    for instance in table["instances"]:
        for raw in instance["rows"]:
            check("rectangular " + table["name"] + " row " + str(len(result)), len(raw), len(fields))
            result.append(dict(zip(fields, raw)))
    return result


def cells(doc: dict) -> dict[tuple, object]:
    result = {}
    for name, table in tables(doc, "model").items():
        for i, instance in enumerate(table["instances"]):
            for j, raw in enumerate(instance["rows"]):
                for column, value in zip(table["columns"], raw):
                    result[(name, i, j, column["name"])] = value
    return result


def sealed_raw(directory: Path, closure: dict, label: str) -> None:
    check(label + " raw count", len(closure["raw"]), 12)
    for name, seal in sorted(closure["raw"].items()):
        path = directory / name
        check(label + " raw present " + name, path.is_file(), True)
        if path.is_file():
            check(label + " raw bytes " + name, path.stat().st_size, seal["bytes"])
            check(label + " raw SHA " + name, digest(path), seal["sha256"])


def main() -> None:
    try:
        contract = load(CASE / "contract.json")
        parent_closure = load(PRUN / "closure.json")
        closure = load(RUN / "closure.json")
        invocation = load(RUN / "invocation.json")
        steps = load(RUN / "steps.json")
        roundtrip = load(RUN / "roundtrip-validation.json")
        check("child closure SHA", digest(RUN / "closure.json"), "b587edc3e63247b079fa3410d784cd27dd3e6ee568e32fecd2969b7812a7ec6a")
        check("parent closure status", parent_closure["error"], None)
        check("child closure status", closure["error"], None)
        check("parent closure schema", parent_closure["schema"], "simlox-d03-calendar-v100-native-closure/v1")
        check("child closure schema", closure["schema"], "simlox-d03-var03-v010-native-closure/v1")
        check("child run ID", closure["run_id"], RUN_ID)
        check("invocation seal", closure["invocation_sha256"], digest(RUN / "invocation.json"))
        sealed_raw(PRUN, parent_closure, "parent")
        sealed_raw(RUN, closure, "child")
        for key, (path, expected) in sorted(PINS.items()):
            check("source file SHA " + key, digest(path), expected)
            check("closure before source SHA " + key, closure["source_hashes_before"][key], expected)
            check("closure after source SHA " + key, closure["source_hashes_after"][key], expected)
            check("invocation source SHA " + key, invocation["source_hashes_before"][key], expected)
        check("manual PDF SHA", digest(MANUAL), contract["source"]["manual_pdf_sha256"])
        check("contract input SHA", contract["accepted_parent"]["input_sha256"], PINS["parent"][1])
        check("run copied input SHA", digest(RUN / "input.json"), PINS["input"][1])

        parent_model = native_json(PINS["parent"][0])
        child_model = native_json(PINS["input"][0])
        before, after = cells(parent_model), cells(child_model)
        check("216 authored source keys", len(before), 216)
        check("source keys retained", set(after), set(before))
        changes = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
        check("one PMT source change", changes, {("PMLocation", 0, 0, "PMT"): (1.0, 4.0)})
        exported_doc = native_json(RUN / "roundtrip-raw.json")
        exported = cells(exported_doc)
        authored_tables = {name: table for name, table in tables(child_model, "model").items() if rows(table)}
        exported_tables = tables(exported_doc, "model")
        check("18 authored populated tables", len(authored_tables), 18)
        for name, table in sorted(authored_tables.items()):
            check("roundtrip table present " + name, name in exported_tables, True)
            check("roundtrip columns " + name, exported_tables[name]["columns"], table["columns"])
            check("roundtrip rows " + name, rows(exported_tables[name]), rows(table))
        for key, value in sorted(after.items()):
            check("roundtrip authored cell " + repr(key), exported.get(key, object()), value)
        check("roundtrip checker outcome", roundtrip["passed"], True)
        check("roundtrip checker schema", roundtrip["schema"], "simlox-d03-var03-v010-import-export/v1")

        check("invocation SSH session", invocation["session_id"], 0)
        check("invocation SSH connection", invocation["ssh_connection_present"], True)
        check("invocation sshd ancestry", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        check("queue mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("protected GUI PID", invocation["gui"]["pid"], 13340)
        check("protected GUI session", invocation["gui"]["session_id"], 1)
        check("protected GUI start", invocation["gui"]["start_utc"], "2026-09-28T10:09:56.8261381Z")
        check("four planned native commands", [x["name"] for x in invocation["planned_commands"]], ["import", "export", "calc", "jsonreport"])
        check("five ordered guarded steps", [x["name"] for x in steps], ["import", "export", "check_import_export", "calc", "jsonreport"])
        for i, step in enumerate(steps):
            check("step " + str(i) + " exit", step["exit_code"], 0)
            check("step " + str(i) + " status", step["status"], "completed")
            check("step " + str(i) + " GUI", step["gui_preserved"], True)
            check("step " + str(i) + " chronological", step["started_utc"] <= step["completed_utc"], True)
            if i:
                check("step " + str(i) + " follows prior", steps[i-1]["completed_utc"] <= step["started_utc"], True)
        run_log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        summary = re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
        check("one converter summary", summary, [("0", "2", "0")])
        check("exact converter warning codes", re.findall(r"\(warning #(\d+)\)", run_log), ["108", "126"])
        check("no converter errors", re.findall(r"\(error #(\d+)\)", run_log), [])
        check("item-free warning target", "This system contains no items: TEACH-AIR-01" in run_log, True)
        check("valid child SXO", (RUN / "model.sxo").stat().st_size > 4, True)

        parent_log = (PRUN / "model.log").read_bytes()
        child_log = (RUN / "model.log").read_bytes()
        check("event log byte parity", child_log, parent_log)
        text = "\n".join(child_log.decode("utf-8-sig", errors="replace").splitlines())
        def event_times(pattern: str) -> list[float]:
            return [float(t) for t in re.findall(pattern, text, re.M)]
        check("PM starts", event_times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started$"), [24.0, 49.0])
        check("PM completes", event_times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed$"), [25.0, 50.0])
        check("one-hour subtask starts", event_times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours$"), [24.0, 49.0])
        check("one-hour subtask completes", event_times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> completed$"), [25.0, 50.0])
        check("mission starts", event_times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission starting, duration: 2 : <TEACH-AIR-01,0>$"), [8.0, 20.0, 32.0])
        check("mission successes", event_times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success: $"), [10.0, 22.0, 34.0])
        check("mission completions", event_times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission completed: <TEACH-AIR-01,0>$"), [10.0, 22.0, 34.0])
        check("no abort or cancellation", bool(re.search(r"mission (?:aborted|cancelled|canceled)", text, re.I)), False)

        check("parent report SHA", digest(PRUN / "report-raw.json"), "a9cc414e9b40da06be620e5fb64c52e0db41ec6fe959ac0874497d358232a84e")
        check("child report byte parity", (RUN / "report-raw.json").read_bytes(), (PRUN / "report-raw.json").read_bytes())
        preport = tables(native_json(PRUN / "report-raw.json"), "report")
        creport = tables(native_json(RUN / "report-raw.json"), "report")
        for name, ncols, nrows in [("ResultSummary", 11, 1), ("SystemResults", 40, 120), ("StockTotalResults", 16, 120)]:
            p, c = preport[name], creport[name]
            check(name + " column count", len(c["columns"]), ncols)
            check(name + " row count", len(rows(c)), nrows)
            check(name + " column metadata", c["columns"], p["columns"])
            for i, (pr, cr) in enumerate(zip(rows(p), rows(c))):
                for field in [x["name"] for x in p["columns"]]:
                    check(name + " row " + str(i) + " field " + field, cr[field], pr[field])
        system = rows(creport["SystemResults"])
        stock = rows(creport["StockTotalResults"])
        for i, row in enumerate(system):
            check("system interval start " + str(i), row["STINT"], i/2)
            check("system interval end " + str(i), row["ETINT"], (i+1)/2)
        for i, row in enumerate(stock):
            check("stock interval start " + str(i), row["STINT"], i/2)
            check("stock interval end " + str(i), row["ETINT"], (i+1)/2)
        check("report horizon", rows(creport["ResultSummary"])[0]["RTIUP"], 60)
        check("PM start bins", [r["STINT"] for r in system if r["NPMS"] == 1], [24, 49])
        check("PM completion bins", [r["STINT"] for r in system if r["NPMT"] == 1], [25, 50])
        for field, expected in [("NSYRY",49),("NSYA",58),("NSYMO",6),("NSYPM",2)]:
            check(field + " half-hour integral", sum(r[field]*.5 for r in system), expected)
        for field, expected in [("NPMS",2),("NPMT",2),("NFAIL",0),("NREPT",0)]:
            check(field + " count", sum(r[field] for r in system), expected)
        check("terminal ready aircraft", system[-1]["NSYRY"], 1)
        check("terminal PM occupation", system[-1]["NSYPM"], 0)
    except Exception as exc:
        failures.append({"check": "replay exception", "actual": type(exc).__name__ + ": " + str(exc), "expected": "none"})
    verdict = {
        "schema": "simlox-d03-var03-v010-independent-replay/v1",
        "run_id": RUN_ID,
        "verdict": "GO_BOUNDED" if not failures else "NO_GO",
        "checks": count,
        "failures": failures,
        "scope": "One seed, one aircraft, PMT 1 to 4 with a referenced one-hour CAL24 subtask; exact parent parity through hour 60.",
        "limits": ["No general PMT precedence across other tasks or distributions.", "No conflicting missions or resource contention.", "No GUI visual or cross-engine claim."]
    }
    OUT.write_bytes((json.dumps(verdict, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": verdict["verdict"], "checks": count, "failures": failures[:3]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

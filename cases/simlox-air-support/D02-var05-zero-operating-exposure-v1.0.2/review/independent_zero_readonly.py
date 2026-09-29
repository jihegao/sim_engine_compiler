"""Independent read-only replay of D02.var05 zero-initiation and prior probes.

Only standard-library parsing of frozen source and sealed native artifacts.
Does not import author code or invoke SIMLOX.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
PARENT = ROOT / "D02-var01-traditional-op-hours-v1.0.0/native-input.json"
RUN_ID = "d02-var05-zero-op-v102-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
OUTPUT = CASE / "review/independent-zero-2026-09-30.json"
PARENT_SHA = "9e6d264330c6f7b41752ed8b0c09a32ac45089cec9ec823ad5e3367ce7f348e2"
CHILD_SHA = "b82bfd03fc1b2fab3ab7a5ffb257f9b129793636eb2969475fb1792062232f44"
PRIOR = [
    ("1.0.0", "d02-var05-zero-op-v100-ssh-20260930-01", "dc64f5644ef146cdef1ab8364bd57be0a28251f0d2f6130a45c0b90c876d2a8d"),
    ("1.0.1", "d02-var05-zero-op-v101-ssh-20260930-01", "6d4b0efb01f028b09eea055d557ea1dfe7f50d22a9e6088b2de6fe1173990b08"),
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path, native: bool = False):
    content = path.read_text(encoding="utf-8-sig")
    if native:
        content = re.sub(r",\s*([}\]])", r"\1", content)
    return json.loads(content)


def tables(document, key="model"):
    return {table["name"]: table for table in document[key]["tables"]}


def rows(table):
    fields = [column["name"] for column in table["columns"]]
    return [dict(zip(fields, row)) for part in table["instances"] for row in part["rows"]]


def run_seal(check, label: str, folder: Path, source_path: Path, expected_sha: str, *, accepted: bool):
    invocation = load(folder / "invocation.json")
    closure = load(folder / "closure.json")
    steps = load(folder / "steps.json")
    prefix = label + ": "
    check(prefix + "source SHA", sha(source_path), expected_sha)
    check(prefix + "copied input SHA", sha(folder / "input.json"), expected_sha)
    check(prefix + "run identity", [invocation["run_id"], closure["run_id"]], [folder.name, folder.name])
    check(prefix + "input and parent invocation binding", [invocation["input_sha256"], invocation["parent_sha256"]], [expected_sha, PARENT_SHA])
    check(prefix + "closure binds invocation", closure["invocation_sha256"], sha(folder / "invocation.json"))
    check(prefix + "source stable during run", closure["source_hashes_before"], closure["source_hashes_after"])
    check(prefix + "invocation/closure fingerprints agree", invocation["source_hashes_before"], closure["source_hashes_before"])
    check(prefix + "source fingerprint input/parent", [closure["source_hashes_before"]["input"], closure["source_hashes_before"]["parent"]], [expected_sha, PARENT_SHA])
    for key, filename in (("contract", "contract.json"), ("builder", "build.py"),
                          ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1")):
        check(prefix + f"sealed local {key} bytes", sha(source_path.parent / filename), closure["source_hashes_before"][key])
    check(prefix + "guarded SSH and GUI identity", [invocation["execution_mode"], invocation["session_id"], invocation["ssh_connection_present"], invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["queue_mutex"]],
          ["ssh_cli_v1", 0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"])
    check(prefix + "raw artifact count", len(closure["raw"]), 12 if accepted else 8)
    for name, claim in sorted(closure["raw"].items()):
        path = folder / name
        check(prefix + "raw sealed " + name, [path.stat().st_size, sha(path)], [claim["bytes"], claim["sha256"]])
    check(prefix + "all attempted steps guarded GUI", all(s["gui_preserved"] for s in steps), True)
    check(prefix + "native import and export completed", [s["name"] for s in steps[:2]], ["import", "export"])
    check(prefix + "import/export exit zero", [s["exit_code"] for s in steps[:2]], [0, 0])
    check(prefix + "native import/export completion markers", ["Import completed!" in (folder / "import.log").read_text(encoding="utf-8-sig"),
                                                                 "Export completed!" in (folder / "export.log").read_text(encoding="utf-8-sig")], [True, True])
    source_tables = tables(load(source_path))
    exported = tables(load(folder / "roundtrip-raw.json", native=True))
    populated = [name for name, table in source_tables.items() if any(part["rows"] for part in table["instances"])]
    check(prefix + "no source table absent in export", sorted(source_tables.keys() - exported.keys()), [])
    check(prefix + "all row-containing source tables roundtrip", all(source_tables[name] == exported.get(name) for name in populated), True)
    return invocation, closure, steps, populated


def main():
    checks = []

    def check(name, actual, expected):
        checks.append({"name": name, "passed": actual == expected, "actual": actual, "expected": expected})

    contract = load(CASE / "contract.json")
    delta = load(CASE / "parent-diff.json")
    child = load(CASE / "native-input.json")
    parent = load(PARENT)
    check("accepted D02.var01 parent SHA", sha(PARENT), PARENT_SHA)
    check("frozen v1.0.2 source SHA", sha(CASE / "native-input.json"), CHILD_SHA)
    check("contract source binding", [contract["parent"]["input_sha256"], contract["native_input_sha256"]], [PARENT_SHA, CHILD_SHA])
    check("diff source binding", [delta["parent_input_sha256"], delta["child_input_sha256"]], [PARENT_SHA, CHILD_SHA])

    pt, ct = tables(parent), tables(child)
    changed = sorted(name for name in pt if pt[name] != ct.get(name))
    check("same model table set", sorted(pt), sorted(ct))
    check("only description and profile tables changed", changed, ["OperationProfile", "ProblemDescription"])
    check("diff exact changed table set", sorted(delta["changed_tables_only"]), changed)
    check("29 parent tables unchanged", len(pt) - len(changed), 29)
    check("diff records exact parent and child tables", all(delta["changed_tables"][name] == {"parent": pt[name], "child": ct[name]} for name in changed), True)
    check("no table added or removed", delta["added_tables_only"], [])
    before, after = rows(pt["OperationProfile"]), rows(ct["OperationProfile"])
    check("three profile rows retained", [len(before), len(after)], [3, 3])
    check("profile schedule fixed", [row["STIM"] for row in after], [8.0, 20.0, 52.0])
    check("only IQTY differs for every row", [[key for key in p if p[key] != c[key]] for p, c in zip(before, after)], [["IQTY"]] * 3)
    check("initiation quantities one to zero", [[row["IQTY"] for row in before], [row["IQTY"] for row in after]], [[1, 1, 1], [0, 0, 0]])
    check("Operations still names valid schedule", [(r["PRID"], r["USTID"]) for r in rows(ct["Operations"])],
          [("BASIC-SCHEDULE", "TEACH-UNIT")])
    check("traditional OPHOURS and FRT fixed", [rows(ct[name])[0][field] for name in ("System", "Item") for field in ("OPID", "FRT")],
          ["OPHOURS", 300000, "OPHOURS", 300000])
    check("seed/horizon unchanged", [rows(ct["Control"])[0][key] for key in ("RSEED", "SIMPE", "RCEND")], ["1", 60.0, 60.0])

    invoke, closure, steps, populated = run_seal(check, "accepted", RUN, CASE / "native-input.json", CHILD_SHA, accepted=True)
    check("accepted contract/builder/checker/runner sealed current bytes",
          [sha(CASE / path) for path in ("contract.json", "build.py", "check_roundtrip.py", "run_native_ssh.ps1")],
          [closure["source_hashes_before"][key] for key in ("contract", "builder", "checker", "runner_script")])
    check("accepted 18 row-containing tables", len(populated), 18)
    check("accepted all five steps complete/exit zero", [(s["name"], s["exit_code"], s["status"]) for s in steps],
          [(name, 0, "completed") for name in ("import", "export", "calc", "jsonreport", "check_import_export")])
    check("accepted closure no error", closure["error"], None)
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    model_log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    check("accepted conversion counts", conversion.groups() if conversion else None, ("0", "1", "0"))
    check("accepted only warning #108", re.findall(r"warning #(\d+)", run_log), ["108"])
    check("accepted nonempty calculated model and report", [(RUN / "model.sxo").stat().st_size > 4, (RUN / "report-raw.json").stat().st_size > 4], [True, True])
    check("native simulation completed", ["Starting simulation..." in run_log, "Saving results ..." in run_log], [True, True])
    check("no native mission lifecycle events", re.findall(r"mission (?:ordered|created|activated|starting|completed|success|aborted|suspended|resumed)", model_log), [])
    check("no native random failure or repair event", re.findall(r"critical random failure added|critical CM failure mode added|System to repair|Start repair of item", model_log), [])
    check("only expected start-of-day records", re.findall(r"Time: (\d+)  Start of day no \d+", model_log), ["0", "24", "48"])
    check("initial stock of one spare remains recorded", "Level: 1 Items:<TEACH-LRU-01,0,0>" in model_log, True)
    report = tables(load(RUN / "report-raw.json", native=True), "report")
    system = rows(report["SystemResults"])
    stock = rows(report["StockTotalResults"])
    check("one summary, 120 system and stock bins", [len(rows(report["ResultSummary"])), len(system), len(stock)], [1, 120, 120])
    for name, ledger in (("system", system), ("stock", stock)):
        check(f"{name} exact 0-60 half-hour bins", [(r["STINT"], r["ETINT"]) for r in ledger],
              [(i / 2, (i + 1) / 2) for i in range(120)])
    check("zero mission operation/preparation/failure/repair counts", [sum(r[key] or 0 for r in system) for key in
          ("NSYMO", "NSYMA", "NFAIL", "NREPT", "NSYRP", "NPMT", "NPMS", "STREQ", "STACC")], [0] * 9)
    check("one ready aircraft every bin", [r["NSYRY"] for r in system], [1] * 120)
    check("zero backorders/issues and no stock requests", [sum(r[key] or 0 for r in stock) for key in
          ("NBO", "NDF", "NWT", "NDD", "NDR")], [0] * 5)
    check("report one repetition and hour-60 stop", [rows(report["ResultSummary"])[0][key] for key in ("NREP", "RTILW", "RTIUP")], [1, 0, 60])

    prior_observations = []
    for version, run_id, expected_sha in PRIOR:
        package = ROOT / f"D02-var05-zero-operating-exposure-v{version}"
        run = package / "runs" / run_id
        record = next(x for x in contract["prior_probes"] if x["version"].startswith(version))
        check(version + ": contract failed-probe binding", [record["run_id"], record["input_sha256"]], [run_id, expected_sha])
        prior_invoke, prior_closure, prior_steps, prior_populated = run_seal(check, version, run, package / "native-input.json", expected_sha, accepted=(version == "1.0.1"))
        prior_log = (run / "run.log").read_text(encoding="utf-8-sig")
        prior_source = tables(load(package / "native-input.json"))
        if version == "1.0.0":
            check(version + ": empty profile and dangling Operations PRID", [len(rows(prior_source["OperationProfile"])), rows(prior_source["Operations"])[0]["PRID"]], [0, "BASIC-SCHEDULE"])
            check(version + ": native #77 names dangling profile", re.search(r"Form: Operations\s+rec 1: \(error #77\) Unknown operational profile \(PRID\):\s+BASIC-SCHEDULE", prior_log) is not None, True)
            check(version + ": conversion error/warning/note counts", re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", prior_log).groups(), ("1", "1", "3"))
            check(version + ": runner rejected unusable SXO", [prior_closure["error"], (run / "model.sxo").stat().st_size], ["calc output model.sxo absent/empty", 4])
            check(version + ": no report", (run / "report-raw.json").exists(), False)
        else:
            check(version + ": empty profile and Operations", [len(rows(prior_source["OperationProfile"])), len(rows(prior_source["Operations"]))], [0, 0])
            check(version + ": converter synthesized default profile", "Default operational profile generated for unit: TEACH-UNIT" in prior_log, True)
            prior_model_log = (run / "model.log").read_text(encoding="utf-8-sig")
            check(version + ": default 60-hour mission at zero", re.search(r"^Time: 0 .*mission starting, duration: 60", prior_model_log, re.M) is not None, True)
            check(version + ": first traditional failure at 1.8829", re.search(r"^Time: 1\.8829 <TEACH-AIR-01,0> critical random failure added", prior_model_log, re.M) is not None, True)
            check(version + ": completed but inadequate zero-exposure control", [prior_closure["error"], len(prior_steps)], [None, 5])
        prior_observations.append({"version": version, "run_id": run_id, "input_sha256": expected_sha,
                                   "invocation_sha256": sha(run / "invocation.json"), "closure_sha256": sha(run / "closure.json"),
                                   "runner_error": prior_closure["error"], "row_containing_tables": len(prior_populated)})

    result = {
        "schema": "simlox-d02-var05-independent-zero-readonly/v1",
        "reviewer": "independent standard-library read-only replay; no author imports or native process",
        "case_id": "D02", "variant_id": "D02.var05", "run_id": RUN_ID,
        "passed": all(c["passed"] for c in checks),
        "passed_count": sum(c["passed"] for c in checks),
        "failed_count": sum(not c["passed"] for c in checks),
        "checks": checks,
        "hashes": {"parent_input": sha(PARENT), "child_input": sha(CASE / "native-input.json"),
                   "child_invocation": sha(RUN / "invocation.json"), "child_closure": sha(RUN / "closure.json"),
                   "child_model_log": sha(RUN / "model.log"), "child_report_raw": sha(RUN / "report-raw.json")},
        "observed": {"zero_missions": True, "zero_failures": True, "zero_reported_operating_hours": True,
                     "ready_aircraft_each_bin": 1, "report_bins": 120,
                     "conversion": {"errors": 0, "warnings": 1, "warning_codes": [108]},
                     "prior_probes": prior_observations},
        "decision": "bounded_zero_initiation_cli_evidence_accepted" if all(c["passed"] for c in checks) else "review_failed",
        "limits": [
            "The accepted model retains three scheduled profile rows with IQTY=0, so no mission is instantiated. The internal OPHOURS counter is not directly reported.",
            "A quiet zero-initiation run under one seed supports this boundary only; it does not by itself prove a general operating-hour failure clock algorithm.",
            "v1.0.0 had a dangling Operations PRID and native conversion error #77; v1.0.1 synthesized a default 60-hour mission and had operating exposure. Neither is zero-exposure evidence.",
            "Custom OperationParameter IDs, explicit FailureMode clocks, active missions with zero usage, other seeds, GUI visuals and cross-engine behavior are untested.",
        ],
        "publication_state": "independent_review_only",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": [c for c in checks if not c["passed"]],
                      "output": str(OUTPUT)}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

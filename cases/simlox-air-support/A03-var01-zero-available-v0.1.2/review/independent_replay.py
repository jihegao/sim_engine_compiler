"""Independent, read-only replay of the sealed A03 zero-deployment run.

Only the resulting verdict in this review directory is written. This does not
import the author validator or invoke SIMLOX.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REVIEW = Path(__file__).resolve().parent
CASE = REVIEW.parent
ROOT = CASE.parent
PARENT = ROOT / "A03-var01-one-of-two-v0.1.0"
OLD10 = ROOT / "A03-var01-zero-available-v0.1.0"
OLD11 = ROOT / "A03-var01-zero-available-v0.1.1"
PRUN = PARENT / "runs/a03-var01-one-of-two-v010-ssh-20261006-01"
R10 = OLD10 / "runs/a03-var01-zero-v010-ssh-20261006-01"
R11 = OLD11 / "runs/a03-var01-zero-v011-ssh-20261006-01"
RUN_ID = "a03-var01-zero-v012-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
CONTRACT_SHA = "e0697933960d2f0da96de0c85d8c7d8bc752d1dfdbcfb23d06760747589f9c22"
INPUT_SHA = "567c66db4faa12ab6e82ea72613f6b2d293ab608ebaed6a79f7daf2996e25f9b"
RUNNER_SHA = "e25eae73c6d3586561f9a541fdc767172bbf120043375673f13ca7b704ee75c9"
VALIDATOR_SHA = "2486b18e417f8c904f783403c0faf38cb3608f1bf71d04563bb6e3781b83a03f"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path: Path):
    """Parse a copy in memory; discard only commas immediately before ] or }."""
    source = path.read_text(encoding="utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for index, char in enumerate(source):
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
        elif char == ",":
            following = index + 1
            while following < len(source) and source[following].isspace():
                following += 1
            if following >= len(source) or source[following] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def table_map(document, section: str):
    entries = document[section]["tables"]
    result = {entry["name"]: entry for entry in entries}
    if len(result) != len(entries):
        raise ValueError(f"duplicate {section} table")
    return result


def rows(table):
    fields = [col["name"] for col in table["columns"]]
    if len(fields) != len(set(fields)):
        raise ValueError("duplicate result column")
    result = []
    for instance in table["instances"]:
        for row in instance["rows"]:
            if len(row) != len(fields):
                raise ValueError("nonrectangular result")
            result.append(dict(zip(fields, row)))
    return fields, result


def source_paths():
    a03 = ROOT / "A03-two-aircraft-formation-v1.0.1"
    a02 = ROOT / "A02-single-aircraft-repeated-missions"
    return {
        "child_input": CASE / "native-input.json",
        "child_contract": CASE / "contract.json",
        "contract_review": REVIEW / "independent-contract-go-2026-10-06.md",
        "builder": CASE / "build.py",
        "parent_diff_checker": CASE / "check_parent_diff.py",
        "roundtrip_checker": CASE / "check_roundtrip.py",
        "shared_parser": ROOT / "tools/validate_native.py",
        "behavior_validator": CASE / "validate_native_cli.py",
        "runner_script": CASE / "run_native_ssh.ps1",
        "accepted_input": PARENT / "native-input.json",
        "accepted_contract": PARENT / "contract.json",
        "accepted_signoff": PARENT / "cli-scope-signoff-2026-10-06.md",
        "accepted_index": PARENT / "evidence-index.json",
        "accepted_verdict": PARENT / "review/independent-verdict.json",
        "accepted_closure": PRUN / "closure.json",
        "diagnostic_input": OLD10 / "native-input.json",
        "diagnostic_contract": OLD10 / "contract.json",
        "diagnostic_runner": OLD10 / "run_native_ssh.ps1",
        "diagnostic_closure": R10 / "closure.json",
        "diagnostic_failure_seal": R10 / "failure-seal.json",
        "diagnostic_run_log": R10 / "run.log",
        "diagnostic_model_log": R10 / "model.log",
        "diagnostic_v011_input": OLD11 / "native-input.json",
        "diagnostic_v011_contract": OLD11 / "contract.json",
        "diagnostic_v011_runner": OLD11 / "run_native_ssh.ps1",
        "diagnostic_v011_validator": OLD11 / "validate_native_cli.py",
        "diagnostic_v011_closure": R11 / "closure.json",
        "diagnostic_v011_report": R11 / "report-raw.json",
        "diagnostic_v011_author": OLD11 / "review/author-validation.json",
        "diagnostic_v011_review": OLD11 / "review/independent-diagnostic-2026-10-06.md",
        "a03_input": a03 / "native-input.json",
        "a03_signoff": a03 / "cli-scope-signoff-2026-09-29.md",
        "a02_input": a02 / "native-input.json",
        "a02_signoff": a02 / "cli-scope-signoff-2026-09-29.md",
        "installed_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
        "installed_manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "installed_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        "prelaunch_approval": REVIEW / "independent-prelaunch-go.json",
    }


def replay():
    checks = 0
    failures: list[str] = []

    def check(label, actual, expected):
        nonlocal checks
        checks += 1
        if actual != expected:
            failures.append(f"{label}: {actual!r} != {expected!r}")

    def sealed(label, folder, closure_path, field="raw", count=None):
        doc = native_json(closure_path)
        seals = doc[field]
        if count is not None:
            check(f"{label} seal count", len(seals), count)
        for name, info in sorted(seals.items()):
            path = folder / name
            check(f"{label} {name} SHA", sha(path), info["sha256"])
            check(f"{label} {name} bytes", path.stat().st_size, info["bytes"])
        return doc

    contract = native_json(CASE / "contract.json")
    check("contract SHA", sha(CASE / "contract.json"), CONTRACT_SHA)
    check("input SHA", sha(CASE / "native-input.json"), INPUT_SHA)
    check("runner SHA", sha(CASE / "run_native_ssh.ps1"), RUNNER_SHA)
    check("validator SHA", sha(CASE / "validate_native_cli.py"), VALIDATOR_SHA)
    check("reserved run", contract["ownership"]["native_run_id_reserved"], RUN_ID)
    check("parent input pin", sha(PARENT / "native-input.json"), contract["accepted_parent"]["input_sha256"])
    check("parent contract pin", sha(PARENT / "contract.json"), contract["accepted_parent"]["contract_sha256"])
    check("parent signoff pin", sha(PARENT / "cli-scope-signoff-2026-10-06.md"), contract["accepted_parent"]["signoff_sha256"])
    check("parent index pin", sha(PARENT / "evidence-index.json"), contract["accepted_parent"]["evidence_index_sha256"])
    check("parent verdict pin", sha(PARENT / "review/independent-verdict.json"), contract["accepted_parent"]["independent_verdict_sha256"])
    check("parent closure pin", sha(PRUN / "closure.json"), contract["accepted_parent"]["closure_sha256"])
    parent = sealed("parent", PRUN, PRUN / "closure.json", count=12)
    check("parent accepted", parent["error"], None)

    old10 = contract["excluded_v010_diagnostic"]
    for field, path in {
        "input_sha256": OLD10 / "native-input.json", "contract_sha256": OLD10 / "contract.json",
        "runner_sha256": OLD10 / "run_native_ssh.ps1", "closure_sha256": R10 / "closure.json",
        "failure_seal_sha256": R10 / "failure-seal.json", "run_log_sha256": R10 / "run.log",
        "model_log_sha256": R10 / "model.log",
    }.items():
        check("v010 " + field, sha(path), old10[field])
    c10 = sealed("v010 closure", R10, R10 / "closure.json", count=10)
    f10 = sealed("v010 failure", R10, R10 / "failure-seal.json", field="files", count=12)
    check("v010 rejected by frozen gate", c10["error"], "converter diagnostics differ")
    check("v010 failure classification", f10["publication_state"], "excluded")
    check("v010 has no report", (R10 / "report-raw.json").exists(), False)

    old11 = contract["excluded_v011_diagnostic"]
    for field, path in {
        "input_sha256": OLD11 / "native-input.json", "contract_sha256": OLD11 / "contract.json",
        "runner_sha256": OLD11 / "run_native_ssh.ps1", "validator_sha256": OLD11 / "validate_native_cli.py",
        "closure_sha256": R11 / "closure.json", "report_sha256": R11 / "report-raw.json",
        "author_validation_sha256": OLD11 / "review/author-validation.json",
        "independent_diagnostic_sha256": OLD11 / "review/independent-diagnostic-2026-10-06.md",
    }.items():
        check("v011 " + field, sha(path), old11[field])
    c11 = sealed("v011", R11, R11 / "closure.json", count=12)
    check("v011 raw completed", c11["error"], None)
    author11 = native_json(OLD11 / "review/author-validation.json")
    check("v011 remains NO_GO", author11["decision"], "NO_GO")
    check("v011 failed check count", author11["checks"], 4445)
    check("v011 72 failures", len(author11["failures"]), 72)
    for index, failure in enumerate(author11["failures"]):
        check(f"v011 failure {index}", failure.startswith(f"report/System[{index}].FTMO zero:"), True)

    parent_model = table_map(native_json(PARENT / "native-input.json"), "model")
    child_model = table_map(native_json(CASE / "native-input.json"), "model")
    check("model table order", list(child_model), list(parent_model))
    changed = []
    cells = 0
    for name, old in parent_model.items():
        new = child_model[name]
        check(f"{name} columns", new["columns"], old["columns"])
        check(f"{name} instance count", len(new["instances"]), len(old["instances"]))
        fields = [c["name"] for c in old["columns"]]
        for ii, (oi, ni) in enumerate(zip(old["instances"], new["instances"])):
            check(f"{name} instance {ii} name", ni["instance_name"], oi["instance_name"])
            check(f"{name} instance {ii} rows", len(ni["rows"]), len(oi["rows"]))
            for ri, (orow, nrow) in enumerate(zip(oi["rows"], ni["rows"])):
                check(f"{name} row {ri} width", len(nrow), len(orow))
                for field, before, after in zip(fields, orow, nrow):
                    cells += 1
                    if before != after:
                        changed.append((name, ii, ri, field, before, after))
    check("155 authored cells", cells, 155)
    check("sole source edit", changed, [("SystemDeployment", 0, 0, "QTYPS", 1, 0)])
    check("child same as excluded source", sha(CASE / "native-input.json"), sha(OLD11 / "native-input.json"))

    closure = sealed("child", RUN, RUN / "closure.json", count=12)
    check("child raw names", set(closure["raw"]), {
        "input.json", "model.sxi", "import.log", "roundtrip-raw.json", "export.log",
        "roundtrip-validation.json", "steps.json", "model.sxo", "run.log",
        "model.log", "report-raw.json", "report-export.log",
    })
    invocation = native_json(RUN / "invocation.json")
    steps = native_json(RUN / "steps.json")
    check("closure run", closure["run_id"], RUN_ID)
    check("closure no error", closure["error"], None)
    check("no failure seal", (RUN / "failure-seal.json").exists(), False)
    check("invocation SHA", sha(RUN / "invocation.json"), closure["invocation_sha256"])
    check("source before/after", closure["source_hashes_before"], closure["source_hashes_after"])
    check("invocation source map", invocation["source_hashes_before"], closure["source_hashes_before"])
    paths = source_paths()
    check("source labels", set(closure["source_hashes_before"]), set(paths))
    for label, path in sorted(paths.items()):
        check(f"source {label} SHA", sha(path), closure["source_hashes_before"][label])
    check("copied input", sha(RUN / "input.json"), INPUT_SHA)
    check("invocation input", invocation["input_sha256"], INPUT_SHA)
    check("invocation contract", invocation["contract_sha256"], CONTRACT_SHA)
    check("invocation runner", invocation["runner_script_sha256"], RUNNER_SHA)
    approval = native_json(REVIEW / "independent-prelaunch-go.json")
    for label, expected in (
        ("decision", "GO_PRELAUNCH"), ("run_id", RUN_ID),
        ("contract_sha256", CONTRACT_SHA), ("input_sha256", INPUT_SHA),
        ("runner_sha256", RUNNER_SHA), ("validator_sha256", VALIDATOR_SHA),
    ):
        check("approval " + label, approval[label], expected)
    check("SSH session 0", invocation["session_id"], 0)
    check("SSH present", invocation["ssh_connection_present"], True)
    check("sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
    check("mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
    check("GUI identity", tuple(invocation["gui"][x] for x in ("pid", "session_id", "start_unix_ms")),
          (13340, 1, 1790590196826))
    check("step order", [s["name"] for s in steps],
          ["import", "export", "check_import_export", "calc", "jsonreport"])
    for i, step in enumerate(steps):
        check(f"step {i} outcome", (step["status"], step["exit_code"], step["gui_preserved"]),
              ("completed", 0, True))

    exported = table_map(native_json(RUN / "roundtrip-raw.json"), "model")
    authored = [name for name, tab in child_model.items() if any(i["rows"] for i in tab["instances"])]
    check("row-containing table count", len(authored), 13)
    for name in authored:
        check(f"roundtrip {name} columns", exported[name]["columns"], child_model[name]["columns"])
        check(f"roundtrip {name} instances", exported[name]["instances"], child_model[name]["instances"])
    rt = native_json(RUN / "roundtrip-validation.json")
    check("roundtrip checker pass", rt["passed"], True)
    check("roundtrip source SHA", rt["source_sha256"], INPUT_SHA)
    check("roundtrip export SHA", rt["roundtrip_sha256"], sha(RUN / "roundtrip-raw.json"))
    check("roundtrip SXI SHA", rt["sxi_sha256"], sha(RUN / "model.sxi"))

    log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check("converter 0/3/1", "Input conversion completed. Errors: 0, Warnings: 3, Notes: 1" in log, True)
    check("warning codes", sorted(re.findall(r"\(warning #(\d+)\)", log)), ["108", "126", "486"])
    check("notice codes", re.findall(r"\(notice #(\d+)\)", log), ["184"])
    check("no converter error", re.findall(r"\(error #(\d+)\)", log), [])
    check("notice target", bool(re.search(r"Form: SystemDeployment\s+rec 1: \(notice #184\) Number of systems deployed \(QTYPS\) is zero: TEACH-AIR-01/TEACH-UNIT", log)), True)
    check("unit warning target", bool(re.search(r"Form: Unit\s+rec 1: \(warning #486\) No systems deployed at unit: TEACH-UNIT", log)), True)
    check("valid SXO", (RUN / "model.sxo").stat().st_size > 4, True)

    events = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    check("36 hour log", events[1], "36")
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    expected_events = [
        "Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION",
        f"Time: 7 {mission} mission created: ",
        f"Time: 7 {mission} mission activated, systems requested: 2",
        f"Time: 7 {mission} mission waiting:  timeout at 8.33333",
        f"Time: 8.33333 {mission} mission cancelled: ",
    ]
    for event in expected_events:
        check("event " + event.strip(), events.count(event), 1)
    check("exactly one mission creation", sum(" mission created:" in x for x in events), 1)
    check("exactly one mission cancellation", sum(" mission cancelled:" in x for x in events), 1)
    check("no physical aircraft ID", any(re.search(r"<TEACH-AIR-01,\d+>", x) for x in events), False)
    for name, pattern in (
        ("allocation", r"mission allocates system:"), ("launch", r"mission starting,"),
        ("success", r"mission success:"), ("completion", r"mission completed:"),
        ("maintenance/failure", r"failure occurs|PM task starting|Repair task starting|task starting:"),
        ("stock/transport", r"backorder|Delivery|transport started|stock issued|item issued"),
    ):
        check("no " + name, bool(re.search(pattern, "\n".join(events), re.I)), False)

    report = table_map(native_json(RUN / "report-raw.json"), "report")
    baseline = table_map(native_json(PRUN / "report-raw.json"), "report")
    check("four report tables", list(report), list(baseline))
    sfields, system = rows(report["SystemResults"])
    check("System column names", sfields, rows(baseline["SystemResults"])[0])
    check("72 System bins", len(system), 72)
    check("40 System fields", len(sfields), 40)
    for i, row in enumerate(system):
        for field in sfields:
            expected = (
                "Total over all Units" if field == "UNID" else
                "Total over all Systems" if field == "SID" else
                i / 2 if field == "STINT" else
                (i + 1) / 2 if field == "ETINT" else
                None if field in ("FTMO", "SYDT") else 0
            )
            check(f"System[{i}].{field}", row[field], expected)
    stock_fields, stock = rows(report["StockTotalResults"])
    parent_stock_fields, parent_stock = rows(baseline["StockTotalResults"])
    check("Stock columns", stock_fields, parent_stock_fields)
    check("72 Stock bins", len(stock), 72)
    check("16 Stock fields", len(stock_fields), 16)
    for i, (actual, prior) in enumerate(zip(stock, parent_stock)):
        for field in stock_fields:
            check(f"Stock[{i}].{field}", actual[field], prior[field])
    summary_fields, summary = rows(report["ResultSummary"])
    check("11 summary fields", len(summary_fields), 11)
    check("one summary row", len(summary), 1)
    check("summary columns", summary_fields, rows(baseline["ResultSummary"])[0])
    for field in summary_fields:
        check("Summary." + field, summary[0][field], {"NREP": 1, "RTILW": 0, "RTIUP": 36}.get(field, 0))
    check("description columns", rows(report["ProblemDescription"])[0], rows(baseline["ProblemDescription"])[0])
    check("inherited description", rows(report["ProblemDescription"])[1], rows(baseline["ProblemDescription"])[1])

    return {
        "schema": "simlox-a03-var01-zero-v012-independent-replay/v1",
        "run_id": RUN_ID,
        "decision": "GO_BOUNDED" if not failures else "NO_GO",
        "checks": checks,
        "failures": failures,
        "contract_sha256": CONTRACT_SHA,
        "input_sha256": INPUT_SHA,
        "closure_sha256": sha(RUN / "closure.json"),
        "model_log_sha256": sha(RUN / "model.log"),
        "report_sha256": sha(RUN / "report-raw.json"),
        "scope": "one fixed-seed explicit QTYPS=0 CLI run; 72 half-hour System and Stock bins",
        "limits": [
            "v0.1.0 and v0.1.1 remain excluded diagnostics under their frozen gates",
            "FTMO and SYDT null are observed for this zero-deployment source and horizon only",
            "no omitted-deployment, other seed, GUI, alternate model, or cross-engine claim",
        ],
    }


if __name__ == "__main__":
    try:
        verdict = replay()
    except Exception as exc:
        verdict = {"schema": "simlox-a03-var01-zero-v012-independent-replay/v1",
                   "run_id": RUN_ID, "decision": "NO_GO", "checks": 0,
                   "failures": [f"replay exception: {type(exc).__name__}: {exc}"]}
    (REVIEW / "independent-verdict.json").write_text(
        json.dumps(verdict, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{verdict['decision']} {verdict['checks']} checks; {len(verdict['failures'])} failures")
    raise SystemExit(0 if verdict["decision"] == "GO_BOUNDED" else 1)

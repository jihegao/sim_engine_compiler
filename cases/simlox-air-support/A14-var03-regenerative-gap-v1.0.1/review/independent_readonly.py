"""Independent, standard-library, read-only replay of A14.var03 v1.0.1 raw runs.

Only the adjacent review JSON is written. No author implementation is imported.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
OLD = BASE / "A14-var03-regenerative-gap-v1.0.0"
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
VARIANTS = (
    "regenerative-control", "regenerative-zero", "regenerative-tolerant",
    "fixed-control", "fixed-tolerant",
)
SOURCE_FILES = {
    "parent": BASE / "A14-continuous-end-abort-v1.0.1" / "control-input.json",
    "donor_turnround": BASE / "B04-cross-midnight-turnround-v1.0.1" / "turnround-input.json",
    "donor_dependence": BASE / "A14-continuous-end-abort-v1.0.1" / "dependent-input.json",
    "contract": CASE / "contract.json", "builder": CASE / "build.py",
    "exact_diff": CASE / "exact-diff.json", "diff_checker": CASE / "describe_diff.py",
    "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
}
EXPECTED_FACTORS = {
    "regenerative-control": (0.9607843160629272, 0.7313432693481445),
    "regenerative-zero": (0.9215686321258545, 0.7014925479888916),
    "regenerative-tolerant": (0.9607843160629272, 0.7313432693481445),
    "fixed-control": (1.0, 1.0),
    "fixed-tolerant": (0.7804877758026123, 0.7804877758026123),
}


class Audit:
    def __init__(self) -> None:
        self.count = 0
        self.failures: list[str] = []

    def check(self, condition: bool, label: str) -> None:
        self.count += 1
        if not condition:
            self.failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jread(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    """Remove trailing commas from a parser copy without changing raw evidence."""
    raw = path.read_text(encoding="utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for i, ch in enumerate(raw):
        if quoted:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
            out.append(ch)
        elif ch == "," and raw[i + 1 :].lstrip().startswith(("]", "}")):
            continue
        else:
            out.append(ch)
    return json.loads("".join(out))


def tables(doc: dict, root: str) -> dict[str, dict]:
    result = {}
    for table in doc[root]["tables"]:
        name = table["name"]
        if name in result:
            raise ValueError(f"duplicate {root} table {name}")
        result[name] = table
    return result


def populated(tab: dict) -> bool:
    return any(instance["rows"] for instance in tab["instances"])


def flat(tab: dict) -> tuple[list, list]:
    return tab["columns"], [row for instance in tab["instances"] for row in instance["rows"]]


def near(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=0, abs_tol=1e-6)


def overlap(a: float, b: float, c: float, d: float) -> float:
    return max(0.0, min(b, d) - max(a, c))


def interval_sum(segments: list[tuple[float, float]], a: float, b: float) -> float:
    return sum(overlap(a, b, x, y) for x, y in segments) / (b - a)


def expected_segments(variant: str) -> dict[str, list[tuple[float, float]]]:
    regenerative = variant.startswith("regenerative")
    zero = variant == "regenerative-zero"
    fixed_dependent = variant == "fixed-tolerant"
    support = [(8.0, 12.0)] + ([(12.5, 14.5)] if regenerative else [])
    execute = [(8.0, 12.0), (12.5, 14.25)] if zero else [(8.0, 12.0)] if fixed_dependent else [(8.0, 14.25)]
    turnround = [(12.0, 12.5)] + ([(14.5, 15.0)] if regenerative else [])
    return {
        "operating": support + execute,
        "suspended": [(12.0, 12.5)] if zero else [],
        "turnround": turnround,
    }


def check_source(audit: Audit, contract: dict, diff: dict) -> dict[str, str]:
    expected = {
        "parent": contract["parent"]["sha256"],
        "donor_turnround": contract["structural_donors"]["turnround"]["sha256"],
        "donor_dependence": contract["structural_donors"]["dependence"]["sha256"],
        "contract": "5fc7c76a1f623804d07a1b227fcdae3e0464173f0be992c2577e6472e4d733f1",
        "exact_diff": contract["exact_diff_sha256"],
        "builder": "199103d61feb8ae576a751eeb709f59ff8c1aa1eea93359223bae59f5fbcf7c4",
        "diff_checker": "f47f3ea06ee97ade37773159cc2e6c19d0ce21c9ca2e3e9fecb03ff72749690c",
        "checker": "296b8880c164922be48af43349b47dcceb72dcbce468d53e247cbc092e5f64c6",
        "runner_script": "b621ddbf5c675b789f1048def778b39d926b87941ac02a1b5246a103263a2c61",
        "simlox_exe": contract["source"]["installed_executable_sha256"],
    }
    actual = {name: sha(path) for name, path in SOURCE_FILES.items()}
    for name, value in expected.items():
        audit.check(actual[name] == value, f"source SHA {name}")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    audit.check(sha(manual) == contract["source"]["installed_manual_sha256"], "installed manual SHA")
    audit.check(diff["parent_sha256"] == actual["parent"], "diff parent SHA")
    parent = tables(native_json(SOURCE_FILES["parent"]), "model")
    variant_tables: dict[str, dict] = {}
    for variant in VARIANTS:
        source = CASE / f"{variant}-input.json"
        current = tables(native_json(source), "model")
        variant_tables[variant] = current
        audit.check(sha(source) == contract["inputs_sha256"][variant], f"input SHA {variant}")
        audit.check(source.read_bytes() == (OLD / f"{variant}-input.json").read_bytes(), f"v100 input identity {variant}")
        delta = diff["variants"][variant]
        changed = {n for n in parent.keys() | current.keys() if parent.get(n) != current.get(n)}
        audit.check(changed == set(delta["changed_tables"]), f"exact changed table set {variant}")
        audit.check(all(parent[name]["columns"] == current[name]["columns"] for name in parent.keys() & current.keys()), f"unchanged source column schema {variant}")
        for name in changed:
            item = delta["changed_tables"][name]
            before = None if name not in parent else parent[name]["instances"]
            after = None if name not in current else current[name]["instances"]
            audit.check(before == item["before"] and after == item["after"], f"exact table delta {variant}.{name}")
        audit.check(sum(populated(t) for t in current.values()) == (15 if "zero" in variant or "tolerant" in variant else 14), f"source table count {variant}")
    for pair, expected_changed in diff["contrasts"].items():
        first, second = pair.split(":")
        x, y = variant_tables[first], variant_tables[second]
        actual_changed = {n for n in x.keys() | y.keys() if x.get(n) != y.get(n)}
        audit.check(actual_changed == set(expected_changed), f"pair contrast {pair}")
    return actual


def check_events(audit: Audit, variant: str, log: str) -> dict:
    regenerative = variant.startswith("regenerative")
    zero = variant == "regenerative-zero"
    fixed_dep = variant == "fixed-tolerant"
    support_ids = ["<SUPPORT,TEACH-UNIT,0,0,0>"] + (["<SUPPORT,TEACH-UNIT,0,1,1>"] if regenerative else [])
    execute_id = "<EXECUTE,TEACH-UNIT,0,0,2>" if regenerative else "<EXECUTE,TEACH-UNIT,0,0,1>"
    event_lines = [line for line in log.splitlines() if line.startswith("Time:")]

    def hits(time: float, identity: str, text: str) -> list[str]:
        prefix = f"Time: {time:g} {identity} {text}"
        return [line for line in event_lines if line.startswith(prefix)]

    for i, sid in enumerate(support_ids):
        begin, end = (8.0, 12.0) if i == 0 else (12.5, 14.5)
        for time, event in [(begin, "mission starting"), (end, "mission success"), (end, "mission completed")]:
            audit.check(len(hits(time, sid, event)) == 1, f"{variant} {sid} {event} {time}")
        audit.check(any("<TEACH-AIR-01,0>" in line for line in hits(begin, sid, "mission starting")), f"{variant} SUPPORT aircraft 0")
    for time, event in [(8.0, "mission starting")]:
        audit.check(len(hits(time, execute_id, event)) == 1, f"{variant} EXECUTE {event} {time}")
    audit.check(any("<TEACH-AIR-01,1>" in line for line in hits(8, execute_id, "mission starting")), f"{variant} EXECUTE aircraft 1")
    expected_exec = [(12.0, "mission aborted")] if fixed_dep else [(14.25, "mission success"), (14.25, "mission completed")]
    for time, event in expected_exec:
        audit.check(len(hits(time, execute_id, event)) == 1, f"{variant} EXECUTE {event} {time}")
    transitions = [(float(re.match(r"Time: ([0-9.]+)", line).group(1)), word)
                   for line in event_lines if execute_id in line
                   for word in ("mission suspended", "mission resumed", "mission aborted", "mission success") if word in line]
    expected_transitions = ([(12.0, "mission suspended"), (12.5, "mission resumed"), (14.25, "mission success")] if zero
                            else [(8.0, "mission suspended"), (8.0, "mission resumed"), (12.0, "mission aborted")] if fixed_dep
                            else [(14.25, "mission success")])
    audit.check(transitions == expected_transitions, f"{variant} EXECUTE transition sequence")
    for start, finish in ([(12.0, 12.5), (14.5, 15.0)] if regenerative else [(12.0, 12.5)]):
        for time, event in [(start, "turnround started"), (finish, "turnround ended")]:
            prefix = f"Time: {time:g} <TEACH-AIR-01,0> {event}, mission:"
            audit.check(sum(line.startswith(prefix) for line in event_lines) == 1, f"{variant} SUPPORT {event} {time}")
    audit.check("failure occurred" not in log.lower() and "repair started" not in log.lower(), f"{variant} no failure/repair events")
    return {"execute_id": execute_id, "support_ids": support_ids, "execute_transitions": transitions}


def check_report(audit: Audit, variant: str, report: dict, old_report: dict) -> dict:
    tab = tables(report, "report")
    old_tab = tables(old_report, "report")
    audit.check(set(tab) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{variant} report table set")
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        audit.check(tab[name] == old_tab[name], f"{variant} full {name} repeat from excluded diagnostic")
    summary = dict(zip((c["name"] for c in tab["ResultSummary"]["columns"]), tab["ResultSummary"]["instances"][0]["rows"][0]))
    audit.check(summary["NREP"] == 1 and summary["RTILW"] == 0 and summary["RTIUP"] == 16, f"{variant} summary horizon")
    audit.check(near(summary["MTMF"], EXPECTED_FACTORS[variant][0]) and near(summary["STMF"], EXPECTED_FACTORS[variant][1]), f"{variant} summary factors")
    audit.check(all(near(summary[name], (1 if variant.startswith("fixed") else 0)) for name in ("MSTF", "MSUF")), f"{variant} fixed mission factors")
    sys = tab["SystemResults"]
    columns = [c["name"] for c in sys["columns"]]
    sys_rows = [dict(zip(columns, row)) for instance in sys["instances"] for row in instance["rows"]]
    audit.check(len(sys_rows) == 32, f"{variant} 32 system bins")
    seg = expected_segments(variant)
    for index, row in enumerate(sys_rows):
        start, end = index / 2, (index + 1) / 2
        operating = interval_sum(seg["operating"], start, end)
        suspended = interval_sum(seg["suspended"], start, end)
        turnround = interval_sum(seg["turnround"], start, end)
        audit.check(near(row["STINT"], start) and near(row["ETINT"], end), f"{variant} system bin time {index}")
        # Both aircraft are assigned at h7 and cease being ready before h8 launch.
        assigned_notice = 2 if 7 <= start < 8 else 0
        audit.check(all(near(row[key], value) for key, value in (("NSYMO", operating), ("NSYMS", suspended), ("NSYMT", turnround), ("NSYRY", 2-operating-suspended-turnround-assigned_notice), ("NSYA", 2))), f"{variant} system bin ledger {index}")
        audit.check(all(row[key] == 0 for key in ("NFAIL", "NDAM", "NPMT", "NPMS", "NSYRP", "NSYPM", "NROBT", "NRCFG", "NSYUA", "NSYAL")), f"{variant} no failure/repair/PM {index}")
    metrics = {name: sum((row["ETINT"]-row["STINT"])*row[key] for row in sys_rows)
               for name, key in (("operating", "NSYMO"), ("suspended", "NSYMS"), ("turnround", "NSYMT"))}
    expect = {"regenerative-control": (12.25, 0, 1), "regenerative-zero": (11.75, .5, 1),
              "regenerative-tolerant": (12.25, 0, 1), "fixed-control": (10.25, 0, .5), "fixed-tolerant": (8, 0, .5)}[variant]
    audit.check(all(near(metrics[key], value) for key, value in zip(("operating", "suspended", "turnround"), expect)), f"{variant} integrated system hours")
    audit.check(all(near(sys_rows[-1][key], value) for key, value in (("NSYRY", 2), ("NSYMO", 0), ("NSYMS", 0), ("NSYMT", 0))), f"{variant} terminal two ready")
    stock = tab["StockTotalResults"]
    stock_cols = [c["name"] for c in stock["columns"]]
    stock_rows = [dict(zip(stock_cols, row)) for instance in stock["instances"] for row in instance["rows"]]
    audit.check(len(stock_rows) == 32, f"{variant} 32 stock bins")
    for index, row in enumerate(stock_rows):
        audit.check(near(row["STINT"], index/2) and near(row["ETINT"], (index+1)/2), f"{variant} stock bin time {index}")
        audit.check(all(row[key] == 0 for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")) and row["PNB"] == 1, f"{variant} stock no movement {index}")
    return {"metrics": metrics, "summary": {key: summary[key] for key in ("MTMF", "MSTF", "MSUF", "STMF")}, "system_bins": len(sys_rows), "stock_bins": len(stock_rows)}


def check_run(audit: Audit, contract: dict, source_hashes: dict, variant: str) -> dict:
    run_id = f"a14-var03-{variant}-v101-20261001-01"
    run = CASE / "runs" / run_id
    old_run = OLD / "runs" / f"a14-var03-{variant}-v100-20261001-01"
    invocation, closure, steps = (jread(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    audit.check(invocation["run_id"] == closure["run_id"] == run_id and invocation["variant"] == variant, f"{variant} run identity")
    audit.check(invocation["case_version"] == "1.0.1-candidate" and "v101" in invocation["schema"] and "v101" in closure["schema"], f"{variant} version")
    audit.check(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{variant} invocation seal")
    audit.check(closure["error"] is None and closure["publication_state"] == "not_published", f"{variant} closure clean/unpublished")
    audit.check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], f"{variant} source stable")
    audit.check(all(closure["source_hashes_before"][key] == value for key, value in source_hashes.items()), f"{variant} source seal matches current")
    audit.check(closure["source_hashes_before"]["input"] == contract["inputs_sha256"][variant] == invocation["input_sha256"], f"{variant} selected input SHA")
    audit.check(closure["source_hashes_before"]["python"] == invocation["python_sha256"], f"{variant} Python runtime seal")
    raw = closure["raw"]
    audit.check(set(raw) == {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json", "import.log", "export.log", "run.log", "model.log", "report-export.log", "roundtrip-validation.json", "steps.json"}, f"{variant} raw file manifest")
    for name, record in raw.items():
        path = run / name
        audit.check(path.is_file() and path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], f"{variant} raw seal {name}")
    audit.check((run / "model.sxo").stat().st_size > 1000, f"{variant} full SXO")
    audit.check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"], f"{variant} SSH session provenance")
    audit.check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant} host mutex")
    gui = invocation["gui"]
    audit.check(gui["pid"] == 13340 and gui["session_id"] == 1 and bool(gui["start_utc"]), f"{variant} GUI identity")
    audit.check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{variant} five native steps")
    audit.check(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True and s["completed_utc"] for s in steps), f"{variant} step completion/GUI")
    audit.check([x["name"] for x in invocation["planned_commands"]] == ["import", "export", "calc", "jsonreport"], f"{variant} planned CLI")
    audit.check(all(run_id in x["arguments"] for x in invocation["planned_commands"]), f"{variant} CLI paths isolated")
    audit.check(invocation["planned_check"]["output"].endswith("roundtrip-validation.json"), f"{variant} planned roundtrip")
    for filename, marker in (("import.log", "Import completed!"), ("export.log", "Export completed!")):
        audit.check(marker in (run / filename).read_text(encoding="utf-8-sig", errors="replace"), f"{variant} {filename} completion")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    audit.check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in run_log, f"{variant} converter zero errors")
    audit.check(set(re.findall(r"warning #(\d+)", run_log)) == {"108", "126"}, f"{variant} warning set")
    audit.check("Saving results" in run_log and "Result saving time" in run_log, f"{variant} simulation saved results")
    before, after = tables(native_json(run / "input.json"), "model"), tables(native_json(run / "roundtrip-raw.json"), "model")
    supplied = {name for name, table in before.items() if populated(table)}
    audit.check(len(supplied) == (15 if "zero" in variant or "tolerant" in variant else 14), f"{variant} row table count")
    for name in supplied:
        audit.check(name in after and flat(before[name]) == flat(after[name]), f"{variant} exact roundtrip {name}")
    audit.check(sha(run / "input.json") == sha(CASE / f"{variant}-input.json"), f"{variant} source/run byte identity")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    audit.check((run / "model.log").read_bytes() == (old_run / "model.log").read_bytes(), f"{variant} old/new byte-identical event log")
    audit.check((run / "report-raw.json").read_bytes() == (old_run / "report-raw.json").read_bytes(), f"{variant} old/new byte-identical report")
    events = check_events(audit, variant, log)
    report = check_report(audit, variant, native_json(run / "report-raw.json"), native_json(old_run / "report-raw.json"))
    return {"run_id": run_id, "closure_sha256": sha(run / "closure.json"), "input_sha256": sha(run / "input.json"), "event": events, **report}


def main() -> int:
    audit = Audit()
    try:
        contract = jread(CASE / "contract.json")
        diff = jread(CASE / "exact-diff.json")
        audit.check(contract["case_version"] == "1.0.1-candidate" and contract["publication_state"] == "not_published", "candidate contract identity")
        audit.check(contract["excluded_diagnostic"]["reason"].startswith("The frozen v1.0.0 prediction"), "v100 diagnostic explicitly excluded")
        sources = check_source(audit, contract, diff)
        for variant, expected_closure in contract["excluded_diagnostic"]["run_closure_sha256"].items():
            old = OLD / "runs" / f"a14-var03-{variant}-v100-20261001-01"
            audit.check(sha(old / "closure.json") == expected_closure, f"v100 diagnostic closure {variant}")
            old_closure = jread(old / "closure.json")
            audit.check(all((old / name).stat().st_size == rec["bytes"] and sha(old / name) == rec["sha256"] for name, rec in old_closure["raw"].items()), f"v100 diagnostic raw seal {variant}")
        runs = {variant: check_run(audit, contract, sources, variant) for variant in VARIANTS}
        result = {"schema": "simlox-a14-var03-v101-independent-readonly/v1", "passed": not audit.failures,
                  "verdict": "bounded_GO" if not audit.failures else "NO_GO", "check_count": audit.count,
                  "failures": audit.failures, "contract_sha256": sha(CASE / "contract.json"),
                  "script_sha256": sha(Path(__file__)), "source_hashes": sources, "runs": runs,
                  "scope": "five fresh guarded native runs; one executable, seed, two aircraft, regenerative/fixed SUPPORT and DTTOL endpoints; prior v100 remains excluded",
                  "limits": ["No general DTTOL law or abort rule", "No same-time internal priority, failure, shortage, GUI visual, or cross-engine claim"]}
    except Exception as exc:
        result = {"schema": "simlox-a14-var03-v101-independent-readonly/v1", "passed": False,
                  "verdict": "NO_GO", "check_count": audit.count, "failures": audit.failures + [f"review exception: {type(exc).__name__}: {exc}"],
                  "contract_sha256": sha(CASE / "contract.json"), "script_sha256": sha(Path(__file__))}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "verdict", "check_count", "failures")}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

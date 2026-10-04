"""Independent, read-only replay of the frozen F04.var02 CLI evidence.

The only write is review/independent-verdict.json. No author module is imported.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import statistics


CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
REVIEW = Path(__file__).resolve().parent
RUN_IDS = {
    "a": "f04-var02-stochastic-v100-repeat-a-ssh-20261004-01",
    "b": "f04-var02-stochastic-v100-repeat-b-ssh-20261004-01",
}
RUN_CLOSURES = {
    "a": "e61172db53cbaf56555ee1be7585284e5e709a72490c0a5d3306fb0da13f8be9",
    "b": "3af2e89cbe7a40073cf53cec2e2cd5b088e7491198861eb190b1ea417e108a66",
}
RAW_NAMES = {
    "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
    "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
    "replication-report-raw.json", "replication-report-export.log", "steps.json",
    "roundtrip-validation.json",
}
STEPS = ["import", "export", "calc", "jsonreport", "replication_report", "check_import_export"]
UNITS = ("TEACH-UNIT", "TEACH-UNIT-2")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


class Audit:
    def __init__(self) -> None:
        self.total = 0
        self.passed = 0
        self.failures: list[str] = []

    def check(self, condition: bool, label: str) -> None:
        self.total += 1
        if condition:
            self.passed += 1
        else:
            self.failures.append(label)


def rows(doc: dict, name: str) -> list[dict]:
    matches = [t for t in doc["report"]["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"report table {name}: {len(matches)} matches")
    table = matches[0]
    columns = [c["name"] for c in table["columns"]]
    result = []
    for instance in table["instances"]:
        for record in instance["rows"]:
            if len(record) != len(columns):
                raise ValueError(f"nonrectangular report table {name}")
            result.append(dict(zip(columns, record)))
    return result


def default_report(path: Path, audit: Audit, label: str) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        json.loads(raw)
        audit.check(False, f"{label}: expected native trailing comma absent")
        return json.loads(raw)
    except json.JSONDecodeError:
        corrected, count = re.subn(r",(?=\s*\]\s*\}\s*\}\s*$)", "", raw)
        audit.check(count == 1, f"{label}: default report correction was not one final comma")
        return json.loads(corrected)


def t_975(df: int) -> float:
    """Numerically invert Student's t CDF without author code or a statistics package."""
    constant = math.exp(math.lgamma((df + 1) / 2) - math.lgamma(df / 2)) / math.sqrt(df * math.pi)

    def density(x: float) -> float:
        return constant * (1 + x * x / df) ** (-(df + 1) / 2)

    def cdf(x: float) -> float:
        pieces = 2000
        width = x / pieces
        area = density(0) + density(x)
        for index in range(1, pieces):
            area += (4 if index % 2 else 2) * density(index * width)
        return 0.5 + area * width / 3

    low, high = 0.0, 5.0
    for _ in range(50):
        mid = (low + high) / 2
        if cdf(mid) < 0.975:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def source_delta(audit: Audit, contract: dict) -> dict:
    parent = CASES / "F04-var01-deterministic-43day-v1.0.1"
    one = CASES / "F04-var02-risk-pilot-v0.1.0"
    pilot = CASES / "F04-var02-risk-variance-pilot-v0.2.0"
    pins = [
        (CASE / "native-input.json", contract["input_sha256"], "candidate input"),
        (CASE / "exact-diff.json", contract["exact_diff_sha256"], "exact diff"),
        (parent / "native-input.json", contract["accepted_parent"]["input_sha256"], "parent input"),
        (parent / "runs/f04-var01-repeat-a-v101-ssh-20261004-01/closure.json", contract["accepted_parent"]["closure_sha256"], "parent closure"),
        (parent / "cli-scope-signoff-2026-10-04.md", contract["accepted_parent"]["signoff_sha256"], "parent signoff"),
        (one / "native-input.json", contract["excluded_pilots"]["one_rep_input_sha256"], "one-rep input"),
        (one / "runs/f04-var02-risk-pilot-v010-ssh-20261004-01/closure.json", contract["excluded_pilots"]["one_rep_closure_sha256"], "one-rep closure"),
        (pilot / "native-input.json", contract["excluded_pilots"]["variance_input_sha256"], "32-rep input"),
        (pilot / "runs/f04-var02-risk-variance-v020-ssh-20261004-01/closure.json", contract["excluded_pilots"]["variance_closure_sha256"], "32-rep closure"),
        (pilot / "variance-analysis.json", contract["excluded_pilots"]["variance_analysis_sha256"], "32-rep analysis"),
        (CASE / "runs/report-settings/replications-enabled.sxs", contract["report_settings"]["one_byte_outpr_enabled_sha256"], "OUTRP settings"),
    ]
    for path, expected, label in pins:
        audit.check(path.is_file() and sha(path) == expected, f"source pin: {label}")
    installed = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
    selector = CASE / "runs/report-settings/replications-enabled.sxs"
    audit.check(sha(installed) == contract["report_settings"]["installed_sha256"], "installed settings pin")
    before, after = installed.read_bytes(), selector.read_bytes()
    audit.check(len(before) == len(after), "selector length")
    audit.check([(i, before[i], after[i]) for i in range(min(len(before), len(after))) if before[i] != after[i]] == [(67165, 78, 89)], "one-byte OUTRP selector")

    old = {t["name"]: t for t in read(parent / "native-input.json")["model"]["tables"]}
    new = {t["name"]: t for t in read(CASE / "native-input.json")["model"]["tables"]}
    audit.check(len(old) == 32 and len(new) == 33 and set(new) - set(old) == {"ReplicationResultControlSystem"}, "parent table topology")
    changes = []
    for name, table in old.items():
        child = new[name]
        audit.check(table["columns"] == child["columns"], f"columns retained: {name}")
        audit.check(len(table["instances"]) == len(child["instances"]), f"instances retained: {name}")
        for a, b in zip(table["instances"], child["instances"]):
            audit.check(len(a["rows"]) == len(b["rows"]), f"row count retained: {name}")
            for index, (ra, rb) in enumerate(zip(a["rows"], b["rows"]), 1):
                audit.check(len(ra) == len(rb), f"row width retained: {name}/{index}")
                for col, x, y in zip(table["columns"], ra, rb):
                    if x != y:
                        changes.append((name, index, col["name"], x, y))
    expected = [
        ("ProblemDescription", 1, "PDESC", "F04.var01 v1.0.1 eight-aircraft 43-day deterministic two-base regression", "F04.var02 v1.0.0 eight-aircraft 43-day stochastic risk replication"),
        ("Control", 1, "NREPS", 1, 128), ("Control", 1, "TCLEV", None, 0.0),
        ("System", 1, "FRT", 0.0, 1000000.0),
        ("Item", 1, "FRT", 0.0, 1000000.0), ("Item", 2, "FRT", 0.0, 1000000.0),
        ("MissionType", 2, "MFF", 0.0, 1.0),
    ]
    audit.check(changes == expected, "seven exact parent-to-child changes")
    diff = read(CASE / "exact-diff.json")
    audit.check(len(diff["changed_cells"]) == 7 and diff["other_cells"] == "unchanged", "diff declaration")
    audit.check(diff["appended_table"] == new["ReplicationResultControlSystem"], "diff appended table")
    replication_rows = new["ReplicationResultControlSystem"]["instances"][0]["rows"]
    audit.check(replication_rows == [["TEACH-AIR-01", "TEACH-UNIT", "Y", "N", "N", None], ["TEACH-AIR-01", "TEACH-UNIT-2", "Y", "N", "N", None]], "two unit TOTAL-only controls")
    old32 = {t["name"]: t for t in read(pilot / "native-input.json")["model"]["tables"]}
    audit.check(set(old32) == set(new), "32-to-128 table identity")
    audit.check(all(old32[n] == new[n] for n in new if n not in {"Control", "ProblemDescription"}), "32-to-128 business identity")
    return {"parent_sha256": sha(parent / "native-input.json"), "input_sha256": sha(CASE / "native-input.json"), "changed_cells": len(changes), "replication_control_rows": len(replication_rows)}


def run_replay(audit: Audit, arm: str, contract: dict, author: dict, tcrit: float) -> dict:
    run = CASE / "runs" / RUN_IDS[arm]
    closure = read(run / "closure.json")
    invocation = read(run / "invocation.json")
    steps = read(run / "steps.json")
    source = closure["source_hashes_before"]
    audit.check(sha(run / "closure.json") == RUN_CLOSURES[arm], f"{arm}: closure pin")
    audit.check(closure["error"] is None and closure["publication_state"] == "not_published", f"{arm}: closure outcome")
    audit.check(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{arm}: invocation seal")
    audit.check(source == closure["source_hashes_after"] == invocation["source_hashes_before"], f"{arm}: source before/after")
    for key, path in {"native_input": CASE / "native-input.json", "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json", "report_settings": CASE / "runs/report-settings/replications-enabled.sxs", "build.py": CASE / "build.py", "describe_diff.py": CASE / "describe_diff.py", "make_report_settings.py": CASE / "make_report_settings.py", "check_roundtrip.py": CASE / "check_roundtrip.py", "run_native_ssh.ps1": CASE / "run_native_ssh.ps1"}.items():
        audit.check(source.get(key) == sha(path), f"{arm}: live source {key}")
    audit.check(set(closure["raw"]) == RAW_NAMES, f"{arm}: exact 14 raw names")
    for name in RAW_NAMES:
        info = closure["raw"][name]
        path = run / name
        audit.check(path.stat().st_size == info["bytes"] and sha(path) == info["sha256"], f"{arm}: raw seal {name}")
    audit.check((run / "input.json").read_bytes() == (CASE / "native-input.json").read_bytes(), f"{arm}: frozen input copy")
    audit.check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", f"{arm}: guarded invocation")
    audit.check(invocation["gui"]["pid"] == 13340, f"{arm}: GUI identity")
    audit.check([s["name"] for s in steps] == STEPS, f"{arm}: step sequence")
    for step in steps:
        audit.check(step["status"] == "completed" and step["exit_code"] == 0, f"{arm}: step {step['name']}")
    for step in steps[:5]:
        audit.check(step["gui_preserved"] is True, f"{arm}: GUI after {step['name']}")
    roundtrip = read(run / "roundtrip-validation.json")
    audit.check(roundtrip["passed"] and len(roundtrip["populated_tables"]) == 31 and roundtrip["source_sha256"] == contract["input_sha256"], f"{arm}: checker verdict")
    authored = {t["name"]: t for t in read(run / "input.json")["model"]["tables"] if any(i["rows"] for i in t["instances"])}
    exported = {t["name"]: t for t in read(run / "roundtrip-raw.json")["model"]["tables"]}
    for name, table in authored.items():
        later = exported.get(name)
        audit.check(later is not None and later["columns"] == table["columns"] and later["instances"] == table["instances"], f"{arm}: independent table roundtrip {name}")
    runlog = (run / "run.log").read_text(encoding="utf-8-sig")
    audit.check(re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog) == [("0", "1", "0")], f"{arm}: converter counts")
    audit.check(re.findall(r"\(warning #(\d+)\)", runlog) == ["108"] and not re.search(r"\((?:error|notice) #", runlog), f"{arm}: converter codes")
    default = default_report(run / "report-raw.json", audit, arm)
    enabled = read(run / "replication-report-raw.json")
    names_default = {t["name"] for t in default["report"]["tables"]}
    names_enabled = {t["name"] for t in enabled["report"]["tables"]}
    audit.check(names_enabled - names_default == {"Replications", "SystemResultsReplicationTotal", "SystemResultsReplication"}, f"{arm}: OUTRP tables")
    reps = rows(enabled, "Replications")
    totals = rows(enabled, "SystemResultsReplicationTotal")
    horizon = rows(enabled, "SystemResultsReplication")
    audit.check(len(reps) == 128 and [r["REPNO"] for r in reps] == list(range(1, 129)), f"{arm}: 128 ordered replications")
    audit.check(len({r["RSEED"] for r in reps}) == 128 and reps[0]["RSEED"] == "1", f"{arm}: replication seeds")
    audit.check(len(totals) == len(horizon) == 256, f"{arm}: two-unit total/horizon counts")
    by_key = {(r["REPLID"], r["UNID"]): r for r in totals}
    horizons = {(r["REPLID"], r["UNID"]): r for r in horizon}
    expected = {(i, u) for i in range(1, 129) for u in UNITS}
    audit.check(len(by_key) == len(horizons) == 256 and set(by_key) == set(horizons) == expected, f"{arm}: exact rep/unit keys")
    for key in expected:
        total, one = by_key[key], horizons[key]
        audit.check(total["SID"] == one["SID"] == "TEACH-AIR-01" and (one["STINT"], one["ETINT"]) == (0, 1032), f"{arm}: horizon identity {key}")
        audit.check(total["NFAIL"] == one["NFAIL"] and math.isclose(total["STACC"], one["STACC"], abs_tol=1e-6), f"{arm}: horizon metric parity {key}")
    event = (run / "model.log").read_text(encoding="utf-8-sig")
    event_patterns = [r"^Time: [\d.]+ <[^>]+> mission starting,", r"^Time: [\d.]+ <[^>]+> mission success:", r"^Time: [\d.]+ <[^>]+> mission aborted:", r"^Time: [\d.]+ <TEACH-AIR-01,\d+> critical random failure added"]
    event_counts = [len(re.findall(pattern, event, re.M)) for pattern in event_patterns]
    audit.check(event_counts == [63, 43, 20, 27], f"{arm}: first-rep event counts")
    audit.check(math.isclose(reps[0]["FMSUC"], 43 / 63, abs_tol=1e-6) and sum(by_key[(1, u)]["NFAIL"] for u in UNITS) == 27, f"{arm}: first-rep report parity")
    pilot_log = CASES / "F04-var02-risk-variance-pilot-v0.2.0/runs/f04-var02-risk-variance-v020-ssh-20261004-01/model.log"
    audit.check(sha(run / "model.log") == sha(pilot_log), f"{arm}: first-rep pilot log identity")
    metrics = {
        "mission_success_fraction": [r["FMSUC"] for r in reps],
        "aircraft_flight_hours": [1032 * sum(by_key[(i, u)]["STACC"] for u in UNITS) for i in range(1, 129)],
        "observed_failures": [sum(by_key[(i, u)]["NFAIL"] for u in UNITS) for i in range(1, 129)],
    }
    intervals = {}
    for name, values in metrics.items():
        mean = statistics.mean(values)
        sd = statistics.stdev(values)
        half = tcrit * sd / math.sqrt(128)
        limit = 0.05 if name == "mission_success_fraction" else (0.05 if name == "aircraft_flight_hours" else 0.10) * mean
        intervals[name] = {"mean": mean, "sample_sd": sd, "halfwidth_t95": half, "allowed_halfwidth": limit, "minimum": min(values), "maximum": max(values), "passed": half <= limit}
        audit.check(half <= limit, f"{arm}: precision {name}")
        claimed = author["run_reports"][arm]["metrics"][name]
        for field, actual in (("mean", mean), ("sample_sd", sd), ("nominal_t95_halfwidth", half), ("allowed_halfwidth", limit)):
            audit.check(math.isclose(claimed[field], actual, abs_tol=1e-8, rel_tol=1e-8), f"{arm}: author {name}/{field}")
    summary = rows(default, "ResultSummary")[0]
    audit.check(summary["NREP"] == 128 and (summary["RTILW"], summary["RTIUP"]) == (0, 1032), f"{arm}: summary horizon")
    for aggregate, source_col in (("MTMF", "FMTAC"), ("MSTF", "FMSTA"), ("MSUF", "FMSUC"), ("STMF", "FSTAC")):
        audit.check(math.isclose(summary[aggregate], statistics.mean(r[source_col] for r in reps), abs_tol=1e-6), f"{arm}: summary mean {aggregate}")
    system = rows(default, "SystemResults")
    stock = rows(default, "StockTotalResults")
    resource = rows(default, "ResourceResults")
    for name, table in (("SystemResults", system), ("StockTotalResults", stock), ("ResourceResults", resource)):
        audit.check(len(table) == 2064, f"{arm}: {name} bin count")
        for index, record in enumerate(table):
            audit.check(math.isclose(record["STINT"], index / 2, abs_tol=1e-8) and math.isclose(record["ETINT"], (index + 1) / 2, abs_tol=1e-8), f"{arm}: {name} bin {index}")
    audit.check(math.isclose(sum(r["NFAIL"] for r in system), intervals["observed_failures"]["mean"], abs_tol=1e-6), f"{arm}: aggregate failures")
    flight_integral = sum((r["ETINT"] - r["STINT"]) * r["STACC"] for r in system)
    audit.check(math.isclose(flight_integral, intervals["aircraft_flight_hours"]["mean"], abs_tol=1e-5), f"{arm}: aggregate flight hours")
    audit.check(all(math.isclose(r["NSYA"] + r["NSYUA"], 8, abs_tol=1e-4) for r in system), f"{arm}: eight-aircraft conservation")
    descriptive = author["run_reports"][arm]["aggregate_descriptive"]
    for key, table, field in (("stock_backorder_item_hours", stock, "NBO"), ("resource_booked_hours", resource, "NRUM"), ("resource_queued_hours", resource, "NRW")):
        value = sum((r["ETINT"] - r["STINT"]) * r[field] for r in table)
        audit.check(math.isclose(value, descriptive[key], abs_tol=1e-6), f"{arm}: descriptive {key}")
    audit.check(system[-1]["NSYRY"] == descriptive["terminal_ready"] and system[-1]["NSYUA"] == descriptive["terminal_unavailable"], f"{arm}: terminal fleet")
    empirical_sem = statistics.stdev(metrics["mission_success_fraction"]) / math.sqrt(128)
    audit.check(not math.isclose(summary["RSMSUF"], empirical_sem, abs_tol=1e-8), f"{arm}: RSM is not empirical SEM")
    return {"run_id": run.name, "closure_sha256": sha(run / "closure.json"), "raw_seals": len(closure["raw"]), "replications": len(reps), "system_total_rows": len(totals), "first_replication_event_counts": dict(zip(("mission_starts", "mission_successes", "mission_aborts", "critical_random_failures"), event_counts)), "metrics": intervals, "default_report_trailing_comma": True, "native_RSMSUF": summary["RSMSUF"], "empirical_FMSUC_SEM": empirical_sem}


def replay() -> dict:
    audit = Audit()
    contract = read(CASE / "contract.json")
    author = read(CASE / "author-native-validation-2026-10-04.json")
    audit.check(contract["case_id"] == "F04" and contract["variant_id"] == "F04.var02" and contract["parameters"]["nreps"] == 128 and contract["parameters"]["tclev"] == 0, "contract identity")
    audit.check(author["decision"] == "GO_BOUNDED", "author bounded verdict")
    source = source_delta(audit, contract)
    tcrit = t_975(127)
    audit.check(abs(tcrit - 1.9788195347) < 1e-8, "independent Student t critical value")
    reports = {arm: run_replay(audit, arm, contract, author, tcrit) for arm in RUN_IDS}
    for name in ("model.log", "report-raw.json", "replication-report-raw.json"):
        audit.check(sha(CASE / "runs" / RUN_IDS["a"] / name) == sha(CASE / "runs" / RUN_IDS["b"] / name), f"same-seed byte identity {name}")
    audit.check(all(author["same_seed_repeat_byte_identical"].values()), "author repeat verdict")
    return {"schema": "simlox-f04-var02-independent-readonly/v1", "passed": not audit.failures, "verdict": "GO_BOUNDED" if not audit.failures else "NO_GO", "checks_total": audit.total, "checks_passed": audit.passed, "failures": audit.failures, "source": source, "student_t_127_975": tcrit, "runs": reports, "limits": ["The fixed 128 draws yield nominal intervals for this configured pseudo-random stream; they do not prove independence or broader population precision.", "Same-seed repeat identity checks execution repeatability and does not double the sample size.", "Only first-replication events are visible in ENLOG; later event timelines are not independently enumerated.", "Native default report contains one trailing comma. Raw bytes are preserved; only that terminal comma is removed for parsing. The OUTRP report parses strictly.", "Native ResultSummary RSM* values are not the empirical sample standard errors computed from per-replication rows.", "Stock backorder and resource observations are aggregate descriptions without per-replication intervals."]}


if __name__ == "__main__":
    try:
        result = replay()
    except Exception as exc:
        result = {"schema": "simlox-f04-var02-independent-readonly/v1", "passed": False, "verdict": "NO_GO", "checks_total": 1, "checks_passed": 0, "failures": [f"replay exception: {type(exc).__name__}: {exc}"]}
    target = REVIEW / "independent-verdict.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": result["verdict"], "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "verdict_sha256": sha(target)}))
    raise SystemExit(0 if result["passed"] else 1)

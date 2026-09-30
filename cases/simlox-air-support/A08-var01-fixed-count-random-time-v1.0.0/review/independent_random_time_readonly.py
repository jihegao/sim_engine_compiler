"""Independent read-only replay of A08.var01 aggregate and 32 seed runs."""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PARENT = CASE.parent / "A02-single-aircraft-repeated-missions" / "native-input.json"
AGG_INPUT = CASE / "native-input.json"
AGG_RUN_ID = "a08-var01-random-time-v100-ssh-20260930-01"
MATRIX_RUN_ID = "a08-var01-seed-matrix-v100-ssh-20260930-04"
AGG_RUN = CASE / "runs" / AGG_RUN_ID
MATRIX_RUN = CASE / "runs" / MATRIX_RUN_ID
OUT = CASE / "review" / "independent-random-time-2026-09-30.json"
PARENT_SHA = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
AGG_SHA = "df7ecf0549fc8b1a506095194b97dac810afc395a76b4c478cfe43eec1838920"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
START_RE = re.compile(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission starting, duration: 2 : <TEACH-AIR-01,(\d+)>")
SUCCESS_RE = re.compile(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission success:")
FINISH_RE = re.compile(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission completed: <TEACH-AIR-01,(\d+)>")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native: bool = False) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    if native:
        out, quoted, escaped = [], False, False
        for i, c in enumerate(raw):
            if quoted:
                out.append(c)
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == '"':
                    quoted = False
            elif c == '"':
                quoted = True
                out.append(c)
            elif c == "," and re.match(r"\s*[}\]]", raw[i + 1:]):
                continue
            else:
                out.append(c)
        raw = "".join(out)
    return json.loads(raw)


def table(doc: dict, root: str, name: str) -> dict:
    matches = [t for t in doc[root]["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError((name, len(matches)))
    return matches[0]


def rows(doc: dict, root: str, name: str) -> list[dict]:
    t = table(doc, root, name)
    fields = [c["name"] for c in t["columns"]]
    return [dict(zip(fields, r)) for inst in t["instances"] for r in inst["rows"]]


def near(x: float, y: float, tolerance: float = 1e-4) -> bool:
    return math.isclose(x, y, abs_tol=tolerance, rel_tol=0)


def event_map(text: str, pattern: re.Pattern) -> dict[int, tuple[float, int | None]]:
    result = {}
    for line in text.splitlines():
        m = pattern.match(line)
        if m:
            key = int(m.group(2))
            if key in result:
                raise ValueError((pattern.pattern, key, "duplicate"))
            result[key] = (float(m.group(1)), int(m.group(3)) if m.lastindex == 3 else None)
    return result


def t_critical_975(df: int) -> float:
    """Solve Student-t CDF with Simpson integration; avoids external statistics code."""
    coefficient = math.exp(math.lgamma((df + 1) / 2) - math.lgamma(df / 2)) / math.sqrt(df * math.pi)
    def cdf(x: float) -> float:
        n = 2048
        h = x / n
        def pdf(v: float) -> float:
            return coefficient * (1 + v*v/df) ** (-(df + 1) / 2)
        integral = pdf(0) + pdf(x)
        integral += 4 * sum(pdf(k*h) for k in range(1, n, 2))
        integral += 2 * sum(pdf(k*h) for k in range(2, n, 2))
        return .5 + integral*h/3
    lo, hi = 0.0, 4.0
    for _ in range(42):
        mid = (lo + hi)/2
        if cdf(mid) < .975:
            lo = mid
        else:
            hi = mid
    return (lo + hi)/2


def main() -> None:
    checks = []
    def ck(name: str, actual: object, expected: object) -> None:
        passed = actual == expected
        checks.append({"name": name, "passed": passed, **({} if passed else
            {"actual": repr(actual)[:650], "expected": repr(expected)[:650]})})

    contract = load(CASE / "contract.json")
    matrix_contract = load(CASE / "contract-seed-matrix-v1.json")
    diff = load(CASE / "exact-diff.json")
    manifest = load(CASE / "seed-matrix-v1.json")
    parent, agg = load(PARENT), load(AGG_INPUT)
    ck("accepted A02 parent hash", sha(PARENT), PARENT_SHA)
    ck("frozen aggregate source hash", sha(AGG_INPUT), AGG_SHA)
    ck("installed manual hash", sha(MANUAL), MANUAL_SHA)
    ck("source contracts bind parent/aggregate/manual", (contract["parent"]["input_sha256"],
       contract["native_input_sha256"], contract["source"]["manual_pdf_sha256"],
       matrix_contract["parent_contract_sha256"], matrix_contract["aggregate_input_sha256"],
       matrix_contract["seed_manifest_sha256"], matrix_contract["seed_generator_sha256"]),
       (PARENT_SHA, AGG_SHA, MANUAL_SHA, sha(CASE / "contract.json"), AGG_SHA,
        sha(CASE / "seed-matrix-v1.json"), sha(CASE / "build_seed_matrix.py")))
    pt = {t["name"]: t for t in parent["model"]["tables"]}
    at = {t["name"]: t for t in agg["model"]["tables"]}
    changed = {n for n in pt if pt[n] != at[n]}
    ck("same source table names", set(pt), set(at))
    ck("exact five changed tables", changed,
       {"ProblemDescription", "Control", "SystemDeployment", "OperationProfile", "Unit"})
    ck("26 other tables unchanged", len(set(pt)-changed), 26)
    ck("same table schemas", all(pt[n]["columns"] == at[n]["columns"] for n in pt), True)
    ck("exact-diff source bindings and content", (diff["parent_sha256"], diff["child_sha256"],
       set(diff["changed_tables_only"]), diff["unchanged_table_count"],
       all(diff["changed_tables"][n] == {"before": pt[n], "after": at[n]} for n in changed)),
       (PARENT_SHA, AGG_SHA, changed, 26, True))
    pc, ac = rows(parent, "model", "Control")[0], rows(agg, "model", "Control")[0]
    ck("Control NREPS only 1 to32", {k: (v, ac[k]) for k, v in pc.items() if v != ac[k]},
       {"NREPS": (1, 32)})
    ck("horizon, interval, fixed seed", (ac["SIMPE"], ac["RCEND"], ac["RCINT"], ac["RSEED"]),
       (36, 36, .5, "1"))
    ps, a_s = rows(parent, "model", "SystemDeployment")[0], rows(agg, "model", "SystemDeployment")[0]
    ck("deployment QTYPS1 to3 only", {k: (v, a_s[k]) for k, v in ps.items() if v != a_s[k]},
       {"QTYPS": (1, 3)})
    profile = rows(agg, "model", "OperationProfile")
    ck("single fixed-count random-time profile", len(profile), 1)
    ck("profile values", (profile[0]["STIM"], profile[0]["ITYPE"], profile[0]["IQTY"],
       profile[0]["IQTYD"], profile[0]["IPER"], profile[0]["IDISP"],
       profile[0]["DTIM"]), (8, "RANDOM", 3, None, 12, "RANDOM", 1/3))
    ck("mission fixed template retained", rows(agg, "model", "MissionType"),
       rows(parent, "model", "MissionType"))
    ck("zero failure rate retained", rows(agg, "model", "System")[0]["FRT"], 0)
    ck("unit/problem label changes only", (
       {k for k, v in rows(parent, "model", "Unit")[0].items()
        if v != rows(agg, "model", "Unit")[0][k]},
       {k for k, v in rows(parent, "model", "ProblemDescription")[0].items()
        if v != rows(agg, "model", "ProblemDescription")[0][k]}),
       ({"DESCR"}, {"PDESC"}))

    aggregate_inv, aggregate_closure, aggregate_steps = (load(AGG_RUN / n) for n in
       ("invocation.json", "closure.json", "steps.json"))
    def guard(inv: dict) -> tuple:
        return (inv["execution_mode"], inv["session_id"],
           inv["ssh_connection_present"],
           "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]],
           inv["queue_mutex"], inv["gui"]["pid"], inv["gui"]["session_id"],
           bool(inv["gui"]["start_utc"]))
    guard_expected = ("ssh_cli_v1", 0, True, True,
       "Global\\SimloxIssue18NativeQueue", 13340, 1, True)
    ck("aggregate invocation guard", guard(aggregate_inv), guard_expected)
    aggregate_runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    ck("aggregate runner SSH/mutex/GUI guard statements", all(s in aggregate_runner for s in
       ("SSH_CONNECTION", "sshd.exe", "WaitOne(0)",
        "Global\\SimloxIssue18NativeQueue", "13340", "Assert-Gui")), True)
    ck("aggregate invocation/run source", (aggregate_inv["run_id"],
       aggregate_inv["input_sha256"], aggregate_inv["parent_sha256"],
       sha(AGG_RUN / "input.json")), (AGG_RUN_ID, AGG_SHA, PARENT_SHA, AGG_SHA))
    ck("aggregate closure clean/source stable/invocation bound", (
       aggregate_closure["error"], aggregate_closure["run_id"],
       aggregate_closure["source_hashes_before"] == aggregate_closure["source_hashes_after"],
       aggregate_closure["invocation_sha256"],
       aggregate_inv["source_hashes_before"] == aggregate_closure["source_hashes_before"]),
       (None, AGG_RUN_ID, True, sha(AGG_RUN / "invocation.json"), True))
    aggregate_sources = {"input": AGG_INPUT, "parent": PARENT,
       "contract": CASE / "contract.json", "builder": CASE / "build.py",
       "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1"}
    for name, path in aggregate_sources.items():
        ck("aggregate source seal " + name, aggregate_closure["source_hashes_before"][name], sha(path))
    ck("aggregate raw inventory", (len(aggregate_closure["raw"]), set(aggregate_closure["raw"])),
       (12, {p.name for p in AGG_RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"}))
    for name, stamp in aggregate_closure["raw"].items():
        p = AGG_RUN / name
        ck("aggregate raw seal " + name, (stamp["bytes"], stamp["sha256"]),
           (p.stat().st_size, sha(p)))
    ck("aggregate five completed steps/GUI preserved", [(s["name"], s["status"],
       s["exit_code"], s["gui_preserved"]) for s in aggregate_steps],
       [(n, "completed", 0, True) for n in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("aggregate CLI arguments planned", [s["arguments"] for s in aggregate_steps[:4]],
       [s["arguments"] for s in aggregate_inv["planned_commands"]])
    agg_export = load(AGG_RUN / "roundtrip-raw.json", native=True)
    populated = [t for t in agg["model"]["tables"] if any(i["rows"] for i in t["instances"])]
    ck("13 aggregate source row-containing tables", len(populated), 13)
    ck("aggregate source row/schema roundtrip", all(
       table(agg_export, "model", t["name"])["columns"] == t["columns"] and
       table(agg_export, "model", t["name"])["instances"] == t["instances"]
       for t in populated), True)
    agg_rt = load(AGG_RUN / "roundtrip-validation.json")
    ck("aggregate checker artifact agrees", (agg_rt["passed"], agg_rt["differences"],
       agg_rt["source_sha256"], agg_rt["roundtrip_sha256"]),
       (True, [], AGG_SHA, sha(AGG_RUN / "roundtrip-raw.json")))
    def conversion(path: Path) -> tuple:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        return (re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", text),
                sorted(re.findall(r"warning #(\d+)", text)))
    ck("aggregate conversion and warnings", conversion(AGG_RUN / "run.log"),
       ([("0", "2", "0")], ["108", "126"]))
    agg_event = (AGG_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("aggregate log exposes one three-mission group", (agg_event.count("SIMLOX LOG FILE"),
       len(event_map(agg_event, START_RE))), (1, 3))
    agg_report = load(AGG_RUN / "report-raw.json", native=True)
    agg_summary = rows(agg_report, "report", "ResultSummary")[0]
    agg_system, agg_stock = (rows(agg_report, "report", n) for n in
       ("SystemResults", "StockTotalResults"))
    ck("aggregate summary NREP32/full success", (agg_summary["NREP"], agg_summary["RTIUP"],
       agg_summary["MTMF"], agg_summary["MSTF"], agg_summary["MSUF"], agg_summary["STMF"]),
       (32, 36, 1, 1, 1, 1))
    ck("aggregate 72 aligned half-hour bins", (len(agg_system), len(agg_stock),
       all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(agg_system)),
       all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(agg_stock))),
       (72, 72, True, True))
    agg_hours = sum((r["NSYMO"] or 0)*.5 for r in agg_system)
    ck("aggregate mean six operation-hours", near(agg_hours, 6), True)
    ck("aggregate no failure/repair/stock and terminal ready3", (
       all((r[k] or 0) == 0 for r in agg_system for k in ("NFAIL", "NREPT", "NSYRP")),
       all((r[k] or 0) == 0 for r in agg_stock for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NWT")),
       agg_system[-1]["NSYRY"], agg_system[-1]["NSYA"]), (True, True, 3, 3))

    matrix_inv, matrix_closure, matrix_steps = (load(MATRIX_RUN / n) for n in
       ("invocation.json", "closure.json", "steps.json"))
    ck("seed manifest names, range and aggregate hash", (
       manifest["parent_input_sha256"], [x["seed"] for x in manifest["seeds"]],
       [x["input_name"] for x in manifest["seeds"]]),
       (AGG_SHA, list(range(1, 33)), [f"seed-{s:02d}.json" for s in range(1, 33)]))
    ck("matrix invocation guard and identity", (guard(matrix_inv), matrix_inv["run_id"]),
       (("ssh_cli_seed_matrix_v1", *guard_expected[1:]), MATRIX_RUN_ID))
    ck("matrix invocation seed list matches manifest", matrix_inv["seeds"], manifest["seeds"])
    ck("matrix closure clean, all 160 steps, source stable", (
       matrix_closure["error"], matrix_closure["run_id"],
       matrix_closure["completed_steps"], matrix_closure["expected_steps"],
       matrix_closure["source_hashes_before"] == matrix_closure["source_hashes_after"],
       matrix_closure["invocation_sha256"],
       matrix_inv["source_hashes_before"] == matrix_closure["source_hashes_before"]),
       (None, MATRIX_RUN_ID, 160, 160, True, sha(MATRIX_RUN / "invocation.json"), True))
    matrix_sources = {"aggregate_input": AGG_INPUT, "seed_manifest": CASE / "seed-matrix-v1.json",
       "initial_contract": CASE / "contract.json",
       "matrix_contract": CASE / "contract-seed-matrix-v1.json",
       "builder": CASE / "build.py", "seed_builder": CASE / "build_seed_matrix.py",
       "checker": CASE / "check_roundtrip.py",
       "seed_checker": CASE / "check_seed_roundtrip.py",
       "runner_script": CASE / "run_native_seed_matrix_ssh.ps1"}
    for name, path in matrix_sources.items():
        ck("matrix source seal " + name, matrix_closure["source_hashes_before"][name], sha(path))
    matrix_runner = (CASE / "run_native_seed_matrix_ssh.ps1").read_text(encoding="utf-8-sig")
    ck("matrix runner SSH/mutex/GUI guard statements", all(s in matrix_runner for s in
       ("SSH_CONNECTION", "sshd.exe", "WaitOne(0)",
        "Global\\SimloxIssue18NativeQueue", "13340", "Assert-Gui")), True)
    ck("matrix raw inventory 353 files", (len(matrix_closure["raw"]), set(matrix_closure["raw"])),
       (353, {p.relative_to(MATRIX_RUN).as_posix() for p in MATRIX_RUN.rglob("*") if p.is_file()}
        - {"closure.json", "invocation.json"}))
    for name, stamp in matrix_closure["raw"].items():
        p = MATRIX_RUN / name
        ck("matrix raw seal " + name, (stamp["bytes"], stamp["sha256"]),
           (p.stat().st_size, sha(p)))
    ck("160 matrix steps ordered by seed and type", [(x["seed"], x["name"],
       x["status"], x["exit_code"], x["gui_preserved"]) for x in matrix_steps],
       [(seed, name, "completed", 0, True) for seed in range(1, 33) for name in
        ("import", "export", "calc", "jsonreport", "check_import_export")])

    triples: list[list[float]] = []
    seed_summaries = []
    max_ledger_error = 0.0
    for entry in manifest["seeds"]:
        seed = entry["seed"]
        seed_source = CASE / "seed-inputs" / entry["input_name"]
        seed_run = MATRIX_RUN / f"seed-{seed:02d}"
        source = load(seed_source)
        ck(f"seed {seed:02d} source/run SHA", (sha(seed_source), sha(seed_run / "input.json"),
           (seed_run / "input.json").read_bytes() == seed_source.read_bytes()),
           (entry["input_sha256"], entry["input_sha256"], True))
        sat = {t["name"]: t for t in source["model"]["tables"]}
        altered = {n for n in at if at[n] != sat[n]}
        ck(f"seed {seed:02d} exact table delta", altered,
           {"Control", "ProblemDescription"})
        sc = rows(source, "model", "Control")[0]
        ck(f"seed {seed:02d} exact Control delta", {k: (v, sc[k]) for k, v in ac.items()
           if v != sc[k]}, {"NREPS": (32, 1), **({} if seed == 1 else
           {"RSEED": ("1", str(seed))})})
        ck(f"seed {seed:02d} PDESC-only label", {k for k, v in
           rows(agg, "model", "ProblemDescription")[0].items() if
           v != rows(source, "model", "ProblemDescription")[0][k]}, {"PDESC"})
        seed_export = load(seed_run / "roundtrip-raw.json", native=True)
        ck(f"seed {seed:02d} independent 13-table roundtrip", all(
           table(seed_export, "model", t["name"])["columns"] == t["columns"] and
           table(seed_export, "model", t["name"])["instances"] == t["instances"]
           for t in source["model"]["tables"] if any(i["rows"] for i in t["instances"])), True)
        seed_rt = load(seed_run / "roundtrip-validation.json")
        ck(f"seed {seed:02d} checker file and conversion", (
           seed_rt["passed"], seed_rt["differences"], seed_rt["input_sha256"],
           seed_rt["roundtrip_sha256"], conversion(seed_run / "run.log")),
           (True, [], entry["input_sha256"], sha(seed_run / "roundtrip-raw.json"),
            ([("0", "2", "0")], ["108", "126"])))
        text = (seed_run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        started, success, completed = (event_map(text, pattern) for pattern in
           (START_RE, SUCCESS_RE, FINISH_RE))
        ck(f"seed {seed:02d} three distinct starts/successes/completions", (
           len(started), set(started), set(success), set(completed)),
           (3, set(started), set(started), set(started)))
        ordered = sorted((t, key, aircraft) for key, (t, aircraft) in started.items())
        starts = [x[0] for x in ordered]
        triples.append(starts)
        ck(f"seed {seed:02d} starts in [8,20) and completes two hours later", all(
           8 <= t < 20 and key in success and key in completed and
           near(success[key][0] - t, 2, .001) and
           near(completed[key][0] - t, 2, .001) and
           completed[key][1] == aircraft for t, key, aircraft in ordered), True)
        ck(f"seed {seed:02d} no cancellation/failure/repair/backorder", all(s not in text.lower()
           for s in ("mission cancelled", "mission aborted", "critical random failure added",
                     "direct repair subtask", "backorder")), True)
        report = load(seed_run / "report-raw.json", native=True)
        summary = rows(report, "report", "ResultSummary")[0]
        system, stock = (rows(report, "report", n) for n in
           ("SystemResults", "StockTotalResults"))
        ck(f"seed {seed:02d} one-replication summary", (summary["NREP"],
           summary["RTIUP"], summary["MTMF"], summary["MSTF"],
           summary["MSUF"], summary["STMF"]), (1, 36, 1, 1, 1, 1))
        ck(f"seed {seed:02d} 72 aligned half-hour bins", (len(system), len(stock),
           all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(system)),
           all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(stock))),
           (72, 72, True, True))
        hours = sum((r["NSYMO"] or 0)*.5 for r in system)
        ck(f"seed {seed:02d} six aircraft-hours and terminal three ready", (
           near(hours, 6), system[-1]["NSYRY"], system[-1]["NSYA"],
           system[-1]["NSYMO"]), (True, 3, 3, 0))
        ck(f"seed {seed:02d} no failure/repair/stock result activity", (
           all((r[k] or 0) == 0 for r in system for k in ("NFAIL", "NREPT", "NSYRP")),
           all((r[k] or 0) == 0 for r in stock for k in
              ("NBO", "NDF", "NDD", "NDR", "NDP", "NWT"))), (True, True))
        # Compare every interval to the three event-derived two-hour occupation spans.
        errors = []
        for r in system:
            lo, hi = r["STINT"], r["ETINT"]
            inferred = sum(max(0.0, min(hi, t + 2) - max(lo, t)) / .5 for t in starts)
            errors.append(abs((r["NSYMO"] or 0) - inferred))
        max_ledger_error = max(max_ledger_error, *errors)
        ck(f"seed {seed:02d} event-to-every-bin operation ledger", max(errors) < .001, True)
        ck(f"seed {seed:02d} event terminal ready3", "systems ready: 3" in text
           and max(float(m.group(1)) for m in re.finditer(
             r"Time: ([\d.]+) <TEACH-UNIT at <BASE-01,0>> systems ready: 3", text)) < 22,
           True)
        seed_summaries.append({"seed": seed, "start_hours": starts,
           "model_log_sha256": sha(seed_run / "model.log"),
           "report_raw_sha256": sha(seed_run / "report-raw.json"),
           "operating_aircraft_hours": hours})

    ck("seed-1 event log equals aggregate exposed log", (MATRIX_RUN / "seed-01" / "model.log").read_bytes(),
       (AGG_RUN / "model.log").read_bytes())
    ck("at least two distinct seed triples", len(set(tuple(x) for x in triples)) > 1, True)
    flat = [t for triple in triples for t in triple]
    ck("96 retained timestamps", len(flat), 96)
    mean, variance = statistics.mean(flat), statistics.variance(flat)
    critical = t_critical_975(len(flat) - 1)
    half_width = critical * math.sqrt(variance / len(flat))
    ck("t quantile df95 sane", near(critical, 1.985251, .00001), True)
    ck("nominal 95-percent half-width <=1h", half_width <= 1, True)

    passed = all(c["passed"] for c in checks)
    result = {"schema": "simlox-a08-var01-independent-readonly/v1",
       "reviewer": "Standalone standard-library read-only replay; no author validator import or native invocation",
       "passed": passed, "passed_count": sum(c["passed"] for c in checks),
       "failed_count": sum(not c["passed"] for c in checks),
       "failed": [c for c in checks if not c["passed"]], "checks": checks,
       "hashes": {"parent_input": sha(PARENT), "aggregate_input": sha(AGG_INPUT),
          "aggregate_invocation": sha(AGG_RUN / "invocation.json"),
          "aggregate_closure": sha(AGG_RUN / "closure.json"),
          "aggregate_model_log": sha(AGG_RUN / "model.log"),
          "aggregate_report_raw": sha(AGG_RUN / "report-raw.json"),
          "matrix_manifest": sha(CASE / "seed-matrix-v1.json"),
          "matrix_invocation": sha(MATRIX_RUN / "invocation.json"),
          "matrix_closure": sha(MATRIX_RUN / "closure.json"),
          "matrix_steps": sha(MATRIX_RUN / "steps.json")},
       "observed": {"aggregate_NREP": agg_summary["NREP"],
          "aggregate_event_groups_exposed": agg_event.count("SIMLOX LOG FILE"),
          "aggregate_mean_operating_aircraft_hours": agg_hours,
          "matrix_seed_count": 32, "matrix_completed_steps_including_checkers": len(matrix_steps),
          "matrix_starts_by_seed": seed_summaries,
          "timestamp_count": len(flat), "mean_start_hour": mean,
          "sample_start_variance_hours_squared": variance,
          "student_t_critical_df95": critical,
          "nominal_95_percent_mean_half_width_hours": half_width,
          "maximum_event_to_bin_count_error": max_ledger_error},
       "decision": "bounded_fixed_count_random_time_accepted" if passed else
          "review_rejected_pending_resolution",
       "limits": [
          "The 32-replication aggregate log exposes only one replication; the 32 explicit-seed matrix provides 32 separately observed one-replication timelines, not the aggregate run's hidden 31 timelines.",
          "The one-seed aggregate and explicit seed-1 logs match byte for byte; this does not establish stream identity for different NREPS or engines.",
          "The 96 rounded event-log timestamps retain native printed precision; reported statistics are computed from those printed values.",
          "The 32 seeds are a fixed convenience matrix. A nominal Student-t interval describes its mean under assumptions and does not prove uniformity or independence.",
          "Each seed's per-bin ledger is checked against its own starts. Aggregate bins are replication averages and are not used to infer individual aggregate replication events.",
          "Other random mission quantities, distributions, periods, GUI visual behavior and cross-engine equivalence remain untested."],
       "publication_state": "independent_review_only"}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "passed_count": result["passed_count"],
       "failed": result["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()

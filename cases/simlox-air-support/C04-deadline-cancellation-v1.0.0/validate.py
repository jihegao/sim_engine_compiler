"""Source-bound C04 CLI assertions against sealed native artifacts."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import validate_native as native  # noqa: E402
import build  # noqa: E402

CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
       "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}
OWNERS = ("<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>")
TAG = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def events(path: Path) -> list[tuple[int, float, str]]:
    return [(line_no, float(match[1]), match[2].strip())
            for line_no, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1)
            if (match := re.match(r"^Time:\s*([0-9.eE+\-]+)\s+(.*)$", line))]


def check(run: Path) -> dict:
    errors = []
    for name in RAW | {"invocation.json", "closure.json"}:
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            errors.append(f"missing or empty artifact: {name}")
    if errors:
        return {"passed": False, "differences": errors}
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    variant = invocation.get("variant_id")
    if variant not in build.VARIANTS:
        return {"passed": False, "differences": ["unknown variant"]}
    spec = CONTRACT["variants"][variant]
    parent_name = spec["parent_variant"]
    parent = HERE.parent / "C03-shared-crew-formation-v1.0.2" / "inputs" / f"{parent_name}.json"
    source, diff = build.build(variant)
    if (sha(parent) != spec["parent_input_sha256"]
            or sha(HERE / "inputs" / f"{variant}.json") != spec["input_sha256"]
            or sha(HERE / "parent-diffs" / f"{variant}.json") != spec["parent_diff_sha256"]
            or (HERE / "inputs" / f"{variant}.json").read_bytes() != source
            or (HERE / "parent-diffs" / f"{variant}.json").read_bytes() != diff):
        errors.append("published parent, exact diff or generated source differs")
    for field, path in {"contract_sha256": HERE / "contract.json", "expected_ledger_sha256": HERE / "expected-ledger.json", "builder_sha256": HERE / "build.py",
                        "validator_sha256": HERE / "validate.py", "runner_sha256": HERE / "run_native_ssh.ps1",
                        "launcher_sha256": HERE / "invoke_loopback.ps1",
                        "parent_diff_sha256": HERE / "parent-diffs" / f"{variant}.json"}.items():
        if invocation.get(field) != sha(path):
            errors.append(f"source binding differs: {field}")
    if (invocation.get("case_id") != "C04" or invocation.get("case_version") != "1.0.0"
            or invocation.get("run_id") != run.name or invocation.get("variant_id") != variant
            or invocation.get("input_sha256") != spec["input_sha256"]
            or invocation.get("parent_variant") != parent_name
            or invocation.get("parent_input_sha256") != spec["parent_input_sha256"]
            or invocation.get("session_id") != 0 or "sshd.exe" not in invocation.get("ssh_ancestor_names", [])
            or invocation.get("coexisting_gui", {}).get("pid") != 13340
            or invocation.get("coexisting_gui", {}).get("session_id") != 1):
        errors.append("native invocation identity differs")
    if sha(run / "input.json") != spec["input_sha256"]:
        errors.append("run input differs from frozen source")
    if (closure.get("run_id") != run.name or closure.get("variant_id") != variant
            or closure.get("invocation_sha256") != sha(run / "invocation.json")
            or set(closure.get("raw", {})) != RAW):
        errors.append("closure identity or inventory differs")
    for name, record in closure.get("raw", {}).items():
        path = run / name
        if not path.is_file() or path.stat().st_size != record.get("bytes") or sha(path) != record.get("sha256"):
            errors.append(f"raw closure differs: {name}")
    steps = load(run / "steps.json")
    if ([step.get("name") for step in steps] != ["import", "export", "calc", "jsonreport"]
            or any(step.get("exit_code") != 0 or step.get("coexisting_gui_present_after") is not True for step in steps)):
        errors.append("native step or GUI coexistence differs")
    roundtrip = native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
    if not roundtrip["all_equal"]:
        errors.append(f"business rows changed on native roundtrip: {roundtrip['changed']}")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", run_log))
    if conversion is None or conversion.group(1) != "0" or warnings != Counter({"108": 1, "126": 1}):
        errors.append(f"conversion or warning allowlist differs: {dict(warnings)}")

    trace = events(run / "model.log")
    if not trace or any(left[1] > right[1] for left, right in zip(trace, trace[1:])):
        errors.append("native event chronology absent or unordered")
    def matching(marker: str) -> list[tuple[int, float, str]]:
        return [row for row in trace if marker in row[2]]
    def times(label: str, found: list[tuple[int, float, str]], wanted: tuple[float, ...]) -> None:
        if len(found) != len(wanted) or any(abs(row[1] - hour) > 1e-4 for row, hour in zip(found, wanted)):
            errors.append(f"{label} timeline differs: {[(r[1], r[2]) for r in found]}")
    times("notice", matching(" mission ordered:"), (7.5,))
    cancellations = matching(TAG + " mission cancelled:")
    launches = matching(TAG + " mission starting, duration:")
    requests = matching(" requests resources")
    leases = matching(" allocated to maintenance task:")
    releases = matching(" deallocated from  maintenance task:")
    work = matching(" starts performing,")
    if variant.startswith("crew-") or variant == "horizon-wait":
        times("two owner requests", requests, (7.5, 7.5))
        if {owner for row in requests for owner in OWNERS if owner in row[2]} != set(OWNERS):
            errors.append("resource request owner set differs")
    if variant == "crew-before":
        times("launch", launches, (8.5,))
        times("no cancellation", cancellations, ())
        times("crew work", work, (7.5, 8.0))
        times("crew lease", leases, (7.5, 8.0))
        times("crew release", releases, (8.0, 8.5))
    elif variant == "crew-equal":
        times("same-time launch", launches, (8.5,))
        times("no same-time cancellation", cancellations, ())
        times("crew work", work, (7.5, 8.0))
        times("crew lease", leases, (7.5, 8.0))
        times("crew release", releases, (8.0, 8.5))
        ended = matching(OWNERS[1] + " preparation ended, mission:")
        if len(ended) != 1 or ended[0][1] != 8.5 or not launches or ended[0][0] >= launches[0][0]:
            errors.append("same-time second preparation must precede fixed-profile launch")
    elif variant == "crew-after":
        times("no launch", launches, ())
        times("cutoff cancellation", cancellations, (8.49,))
        times("first and partial second work", work, (7.5, 8.0))
        times("first and partial second lease", leases, (7.5, 8.0))
        times("first and cancellation release", releases, (8.0, 8.49))
        times("partial work stop", matching("subtask 1 seqno 1 within system preparation task 1 on " + OWNERS[1] + " stopped"), (8.49,))
        times("partial cleanup", matching("subtask 1 seqno 1 within system preparation task 1 on " + OWNERS[1] + " frees resources"), (8.49,))
        times("partial proportional turnround", matching(OWNERS[1] + " turnround started, mission: " + TAG + " reduction factor: 0.98"), (8.49,))
    elif variant == "aircraft-missing":
        times("no launch", launches, ())
        times("missing aircraft cancellation", cancellations, (8.0,))
        times("one aircraft allocation", matching(TAG + " mission allocates system:"), (7.5,))
        times("one aircraft work", work, (7.5,))
        times("one crew lease", leases, (7.5,))
        times("one crew release", releases, (8.0,))
        times("mission waiting at latest preparation start", matching(TAG + " mission waiting:  timeout at 8"), (7.5,))
        if any(OWNERS[1] in row[2] for row in trace):
            errors.append("nonexistent second aircraft appears in log")
    elif variant == "crew-zero":
        times("no launch", launches, ())
        times("no work", work, ())
        times("no lease", leases, ())
        times("missing crew cancellation", cancellations, (8.0,))
        times("wait stops", matching(" resource waiting stopped"), (8.0, 8.0))
        if {owner for row in matching(" resource waiting stopped") for owner in OWNERS if owner in row[2]} != set(OWNERS):
            errors.append("crew-zero wait-stop owners differ")
        if cancellations and any(row[0] <= cancellations[0][0] for row in matching(" resource waiting stopped")):
            errors.append("crew-zero waiting stopped before cancellation")
    elif variant == "horizon-wait":
        times("no launch", launches, ())
        times("no cancellation before horizon", cancellations, ())
        times("no work", work, ())
        times("no lease", leases, ())
    if len(leases) != len(releases):
        errors.append("crew lease/release imbalance at end")
    for lease, release in zip(leases, releases):
        if lease[0] >= release[0]:
            errors.append("crew released before lease")
    expected_owner_counts = {"crew-before": 2, "crew-equal": 2, "crew-after": 2,
                             "aircraft-missing": 1, "crew-zero": 2, "horizon-wait": 2}
    expected_count = expected_owner_counts[variant]
    times("owner allocations", matching(TAG + " mission allocates system:"), (7.5,) * expected_count)
    times("preparation begins", matching(" preparation started, mission: " + TAG), (7.5,) * expected_count)
    if variant != "horizon-wait":
        completed = {"crew-before": (8.0, 8.5), "crew-equal": (8.0, 8.5),
                     "crew-after": (8.0, 8.49), "aircraft-missing": (8.0,), "crew-zero": (8.0, 8.0)}[variant]
        times("preparation end or cleanup", matching(" preparation ended, mission: " + TAG), completed)
    task_prefix = "subtask "
    bookings = matching(" books resources")
    frees = matching(" frees resources")
    if variant in ("crew-before", "crew-equal", "crew-after"):
        times("bookings", bookings, (7.5, 8.0))
        times("freeing", frees, (8.0, 8.49 if variant == "crew-after" else 8.5))
    elif variant == "aircraft-missing":
        times("booking", bookings, (7.5,))
        times("freeing", frees, (8.0,))
    elif variant == "crew-zero":
        times("no booking", bookings, ())
        times("no freeing", frees, ())
    for owner in OWNERS[:expected_count]:
        own_request = [row for row in requests if owner in row[2]]
        own_book = [row for row in bookings if owner in row[2]]
        own_work = [row for row in work if owner in row[2]]
        own_free = [row for row in frees if owner in row[2]]
        if len(own_request) != 1:
            errors.append(f"request identity differs: {owner}")
        if variant != "crew-zero" and variant != "horizon-wait":
            if (len(own_book) != 1 or len(own_work) != 1 or len(own_free) != 1
                    or not own_request[0][0] < own_book[0][0] < own_work[0][0] < own_free[0][0]):
                errors.append(f"request/booking/work/free owner order differs: {owner}")
            elif "planned to last for 0.5 hours" not in own_work[0][2]:
                errors.append(f"planned work duration differs: {owner}")
    if len(leases) == len(bookings) == len(work):
        for booking, lease, started in zip(bookings, leases, work):
            if not booking[0] < lease[0] < started[0]:
                errors.append("booking/lease/work order differs")
    if len(frees) == len(releases):
        for freed, release in zip(frees, releases):
            if not freed[0] < release[0]:
                errors.append("free/release order differs")
    if variant in ("crew-before", "crew-equal", "crew-after") and len(releases) == 2 and len(leases) == 2:
        if not releases[0][0] < leases[1][0]:
            errors.append("second owner leased before first owner release")
    times("mission created", matching(TAG + " mission created:"), (7.5,))
    times("mission activated", matching(TAG + " mission activated, systems requested: 2"), (7.5,))
    if variant in ("crew-before", "crew-equal"):
        times("mission success", matching(TAG + " mission success:"), (9.5,))
        times("mission completion", matching(TAG + " mission completed:"), (9.5,))
    else:
        times("no mission success", matching(TAG + " mission success:"), ())
        times("no mission completion", matching(TAG + " mission completed:"), ())

    report = load(run / "report-raw.json")
    summary = native.table_rows(report, "ResultSummary")
    system = native.table_rows(report, "SystemResults")
    resource = native.table_rows(report, "ResourceResults")
    expected_intervals = 16 if variant == "horizon-wait" else 72
    success = int(variant in ("crew-before", "crew-equal"))
    if len(summary) != 1 or any(summary[0].get(key) != value for key, value in
            {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": success,
             "MSTF": success, "MSUF": success, "STMF": success}.items()):
        errors.append("native result summary differs")
    if len(system) != expected_intervals or len(resource) != expected_intervals:
        errors.append(f"result interval count differs: {len(system)}, {len(resource)}")
    for index, (s, r) in enumerate(zip(system, resource)):
        hour = index / 2
        if any(abs(row.get("STINT", -1) - hour) > 1e-5 or abs(row.get("ETINT", -1) - hour - .5) > 1e-5 for row in (s, r)):
            errors.append(f"noncontiguous result interval {index}")
        if r.get("NRUM", -1) < 0 or r.get("NRW", -1) < 0 or r.get("NRUM", 0) > r.get("NR", -1):
            errors.append(f"invalid resource occupancy interval {index}")
        if variant == "horizon-wait":
            continue
        aircraft = 1 if variant == "aircraft-missing" else 2
        crew = 2 if variant == "aircraft-missing" else 0 if variant == "crew-zero" else 1
        if variant in ("crew-before", "crew-equal"):
            ready = 0 if 7.5 <= hour < 9.5 else 2
            assigned = 2 if 7.5 <= hour < 9.5 else 0
            preparing = 2 if hour == 7.5 else 1 if hour == 8 else 0
            prep_started = 2 if hour == 7.5 else 0
            prep_succeeded = 1 if hour in (8, 8.5) else 0
            flying = 1 if hour in (8.5, 9) else 0
            busy = 1 if hour in (7.5, 8) else 0
            waiting = 1 if hour == 7.5 else 0
        elif variant == "crew-after":
            ready = 0 if hour == 7.5 else .04 if hour == 8 else 2
            assigned = 2 if hour == 7.5 else 1.96 if hour == 8 else 0
            preparing = 2 if hour == 7.5 else .98 if hour == 8 else 0
            prep_started = 2 if hour == 7.5 else 0
            prep_succeeded = 1 if hour == 8 else 0
            flying = 0
            busy = 1 if hour == 7.5 else .98 if hour == 8 else 0
            waiting = 1 if hour == 7.5 else 0
        elif variant == "aircraft-missing":
            ready = 0 if hour == 7.5 else 1
            assigned = 1 if hour == 7.5 else 0
            preparing = 1 if hour == 7.5 else 0
            prep_started = 1 if hour == 7.5 else 0
            prep_succeeded = 1 if hour == 8 else 0
            flying = 0
            busy = 1 if hour == 7.5 else 0
            waiting = 0
        else:
            ready = 0 if hour == 7.5 else 2
            assigned = 2 if hour == 7.5 else 0
            preparing = 2 if hour == 7.5 else 0
            prep_started = 2 if hour == 7.5 else 0
            prep_succeeded = 0
            flying = 0
            busy = 0
            waiting = 2 if hour == 7.5 else 0
        expected_system = {"NSYA": aircraft, "NSYRY": ready, "NSYMA": assigned,
                           "NSYMP": preparing, "NPSTA": prep_started, "NPSUC": prep_succeeded,
                           "FTMO": flying, "NSYMO": 2 * flying}
        expected_resource = {"NR": crew, "NRUM": busy, "NRW": waiting}
        if any(abs(s.get(key, -100) - value) > 1e-4 for key, value in expected_system.items()):
            errors.append(f"system ledger interval {index} differs")
        if any(abs(r.get(key, -100) - value) > 1e-4 for key, value in expected_resource.items()):
            errors.append(f"resource ledger interval {index} differs")
    if system and any(abs(system[-1].get(key, -100) - value) > 1e-5 for key, value in
                      {"NSYA": 1 if variant == "aircraft-missing" else 2,
                       "NSYRY": 1 if variant == "aircraft-missing" else 2,
                       "NSYMA": 0, "NSYMP": 0, "NSYMO": 0}.items()):
        errors.append("end aircraft stock, readiness or assignment differs")
    if resource and resource[-1].get("NRUM") != 0:
        errors.append("end crew occupancy not released")
    if variant == "horizon-wait" and resource and resource[-1].get("NRW") != 2:
        errors.append("horizon waiting state differs")
    observed = {"launch_hours": [r[1] for r in launches], "cancellation_hours": [r[1] for r in cancellations],
                "resource_request_count": len(requests), "lease_count": len(leases), "release_count": len(releases),
                "system_intervals": len(system), "resource_intervals": len(resource)}
    return {"schema": "simlox-c04-source-bound-validation/v1", "case_id": "C04", "version": "1.0.0",
            "variant_id": variant, "run_id": run.name, "passed": not errors, "differences": errors,
            "observed": observed, "roundtrip": roundtrip, "publication_state": "not_published"}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate.py RUN_DIRECTORY")
    result = check(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)

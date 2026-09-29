"""Independent, read-only replay of C04 source-bound native CLI evidence.

This reviewer does not import the case builder, author validator, or their helpers.
It checks the published C03 source, every declared field change, sealed native
artifacts, individual owner event chains, and all system/resource report intervals.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C03-shared-crew-formation-v1.0.2" / "inputs"
PARENT_HASHES = {
    "staffing-2": "83b454bd145621f36571a87cdf8abcbccc184f07ab8f9ad5f3111651c78881e0",
    "staffing-1": "159f5fa91d50afbd0d15840f8f007c62a3775d02d718152004017e20e545b789",
    "staffing-0": "50682827a363aeb2cb35f860f78671fffd1ea48fbea655ce664eb2c1e2b19267",
}
DELTAS = {
    "crew-before": ("staffing-1", {"OperationProfile.DTIM": 0.51}),
    "crew-equal": ("staffing-1", {"OperationProfile.DTIM": 0.5}),
    "crew-after": ("staffing-1", {"OperationProfile.DTIM": 0.49}),
    "aircraft-missing": ("staffing-2", {"SystemDeployment.QTYPS": 1, "OperationProfile.DTIM": 0.5}),
    "crew-zero": ("staffing-0", {"OperationProfile.DTIM": 0.5}),
    "horizon-wait": ("staffing-0", {"Control.SIMPE": 8.0, "ResultCollection.RCEND": 8.0}),
}
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
       "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}
OWNERS = ("<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>")
MISSION = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
EPS = 1e-4


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(path: Path) -> dict | list:
    """SIMLOX JSON sometimes has commas before closing arrays or objects."""
    src = path.read_text(encoding="utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for pos, char in enumerate(src):
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
            nxt = pos + 1
            while nxt < len(src) and src[nxt].isspace():
                nxt += 1
            if nxt >= len(src) or src[nxt] not in "}]":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def tables(document: dict, root: str) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for table in document[root]["tables"]:
        keys = [column["name"] for column in table["columns"]]
        result[table["name"]] = [dict(zip(keys, row, strict=True))
                                 for instance in table.get("instances", [])
                                 for row in instance.get("rows", []) if any(cell is not None and cell != "" for cell in row)]
    return result


def near(a: object, b: object, tol: float = EPS) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol
    return a == b


def text_events(path: Path) -> list[tuple[int, float, str]]:
    found = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
        match = re.match(r"^Time:\s*([0-9.eE+\-]+)\s+(.*)$", line)
        if match:
            found.append((number, float(match[1]), match[2].strip()))
    return found


def expected_segments(variant: str) -> dict:
    if variant in {"crew-before", "crew-equal"}:
        return {"quantity": 2, "capacity": 1, "launch": 8.5, "cancel": None,
                "prep": [(7.5, 8), (7.5, 8.5)], "ready": [(8, 8.5)],
                "leases": [(7.5, 8), (8, 8.5)], "waits": [(7.5, 8)], "flight": (8.5, 9.5),
                "prep_starts": (7.5, 7.5), "prep_success": (8, 8.5)}
    if variant == "crew-after":
        return {"quantity": 2, "capacity": 1, "launch": None, "cancel": 8.49,
                "prep": [(7.5, 8), (7.5, 8.49)], "ready": [(8, 8.49)],
                "leases": [(7.5, 8), (8, 8.49)], "waits": [(7.5, 8)], "flight": None,
                "prep_starts": (7.5, 7.5), "prep_success": (8,)}
    if variant == "aircraft-missing":
        return {"quantity": 1, "capacity": 2, "launch": None, "cancel": 8,
                "prep": [(7.5, 8)], "ready": [], "leases": [(7.5, 8)], "waits": [], "flight": None,
                "prep_starts": (7.5,), "prep_success": (8,)}
    if variant == "crew-zero":
        return {"quantity": 2, "capacity": 0, "launch": None, "cancel": 8,
                "prep": [(7.5, 8), (7.5, 8)], "ready": [], "leases": [],
                "waits": [(7.5, 8), (7.5, 8)], "flight": None,
                "prep_starts": (7.5, 7.5), "prep_success": ()}
    raise ValueError(variant)


def overlap(span: tuple[float, float], start: float, end: float) -> float:
    return max(0.0, min(span[1], end) - max(span[0], start)) / (end - start)


def check_source(variant: str, contract: dict, errors: list[str]) -> tuple[dict, dict]:
    parent_name, expected = DELTAS[variant]
    parent_path = PARENT / f"{parent_name}.json"
    child_path = HERE / "inputs" / f"{variant}.json"
    diff_path = HERE / "parent-diffs" / f"{variant}.json"
    spec = contract["variants"][variant]
    if digest(parent_path) != PARENT_HASHES[parent_name] or spec["parent_input_sha256"] != PARENT_HASHES[parent_name]:
        errors.append(f"{variant}: published C03 parent hash differs")
    if digest(child_path) != spec["input_sha256"] or digest(diff_path) != spec["parent_diff_sha256"]:
        errors.append(f"{variant}: frozen child or parent-diff hash differs")
    if spec["parent_variant"] != parent_name:
        errors.append(f"{variant}: declared parent variant differs")
    before, after = tables(decode(parent_path), "model"), tables(decode(child_path), "model")
    if before.keys() != after.keys():
        errors.append(f"{variant}: business table inventory differs")
    changes = {}
    for name in before.keys() & after.keys():
        if len(before[name]) != len(after[name]):
            errors.append(f"{variant}: {name} row count changed")
            continue
        for index, (left, right) in enumerate(zip(before[name], after[name])):
            if left.keys() != right.keys():
                errors.append(f"{variant}: {name}[{index}] column inventory changed")
            for key in left.keys() & right.keys():
                if not near(left[key], right[key], tol=0):
                    changes[f"{name}.{key}"] = right[key]
    if changes != expected:
        errors.append(f"{variant}: exact published C03 field delta differs: {changes!r} != {expected!r}")
    recorded = decode(diff_path)
    expected_by_table: dict[str, dict] = {}
    for path, value in expected.items():
        table_name, field_name = path.split(".", 1)
        expected_by_table.setdefault(table_name, {})[field_name] = value
    if (recorded.get("parent_input_sha256") != PARENT_HASHES[parent_name]
            or recorded.get("child_input_sha256") != digest(child_path)
            or recorded.get("changed_fields") != expected_by_table
            or set(recorded.get("tables", {})) != {key.split(".", 1)[0] for key in expected}):
        errors.append(f"{variant}: recorded source delta metadata differs")
    for name, pair in recorded.get("tables", {}).items():
        if pair.get("parent_rows") != before.get(name) or pair.get("child_rows") != after.get(name):
            errors.append(f"{variant}: recorded {name} row delta differs")
    return after, recorded


def check_events(variant: str, events: list[tuple[int, float, str]], log_text: str,
                 errors: list[str]) -> dict:
    expected = expected_segments(variant)
    def find(phrase: str) -> list[tuple[int, float, str]]:
        return [entry for entry in events if phrase in entry[2]]
    def require(label: str, found: list[tuple[int, float, str]], times: tuple[float, ...]) -> None:
        got = tuple(row[1] for row in found)
        if len(got) != len(times) or any(not near(a, b) for a, b in zip(got, times)):
            errors.append(f"{variant}: {label} times {got} != {times}")
    if any(a[1] > b[1] for a, b in zip(events, events[1:])):
        errors.append(f"{variant}: ENLOG time decreased")
    require("notice", find("<TEACH-UNIT> mission ordered: BASIC-MISSION"), (7.5,))
    require("creation", find(MISSION + " mission created:"), (7.5,))
    require("formation demand", find(MISSION + " mission activated, systems requested: 2"), (7.5,))
    allocated = find(MISSION + " mission allocates system:")
    require("aircraft allocations", allocated, expected["prep_starts"])
    active_owners = OWNERS[:expected["quantity"]]
    if {o for row in allocated for o in OWNERS if o in row[2]} != set(active_owners):
        errors.append(f"{variant}: allocated owner identity differs")
    for owner, begin, end in zip(active_owners, expected["prep_starts"], expected["prep"]):
        require(owner + " preparation start", find(owner + " preparation started, mission:"), (begin,))
        require(owner + " preparation end", find(owner + " preparation ended, mission:"), (end[1],))
        require(owner + " resource request", [e for e in find(" requests resources") if owner in e[2]], (begin,))
    if expected["quantity"] == 1 and any(OWNERS[1] in e[2] for e in events):
        errors.append(f"{variant}: nonexistent aircraft appeared in ENLOG")
    req = find(" requests resources")
    booked, started = find(" books resources"), find(" starts performing,")
    completed = [e for e in events if "subtask" in e[2] and e[2].endswith(" completed")]
    freed = find(" frees resources")
    stopped = [e for e in events if "subtask" in e[2] and e[2].endswith(" stopped")
               and "resource waiting stopped" not in e[2]]
    waiting_stop = find(" resource waiting stopped")
    leases = find(" allocated to maintenance task:")
    releases = find(" deallocated from  maintenance task:")
    require("booking", booked, tuple(a for a, _ in expected["leases"]))
    require("work", started, tuple(a for a, _ in expected["leases"]))
    require("subtask success", completed, expected["prep_success"])
    require("free", freed, tuple(b for _, b in expected["leases"]))
    require("lease", leases, tuple(a for a, _ in expected["leases"]))
    require("release", releases, tuple(b for _, b in expected["leases"]))
    require("wait received", find(" resource received"), (8,) if variant in {"crew-before", "crew-equal", "crew-after"} else ())
    require("wait stop", waiting_stop, (8, 8) if variant == "crew-zero" else ())
    require("work stop", stopped, (8.49,) if variant == "crew-after" else (8, 8) if variant == "crew-zero" else ())
    require("launch", find(MISSION + " mission starting, duration:"),
            (expected["launch"],) if expected["launch"] is not None else ())
    require("cancel", find(MISSION + " mission cancelled:"),
            (expected["cancel"],) if expected["cancel"] is not None else ())
    require("mission success", find(MISSION + " mission success:"),
            (9.5,) if expected["launch"] is not None else ())
    require("mission completion", find(MISSION + " mission completed:"),
            (9.5,) if expected["launch"] is not None else ())
    if expected["launch"] is not None:
        for label, row in (("launch", find(MISSION + " mission starting, duration:")),
                           ("completion", find(MISSION + " mission completed:"))):
            if len(row) != 1 or not row[0][2].endswith(",".join(OWNERS)):
                errors.append(f"{variant}: {label} did not name both aircraft")
        second_completion = [e for e in completed if OWNERS[1] in e[2]]
        second_release = releases[-1:]
        second_prep_end = find(OWNERS[1] + " preparation ended, mission:")
        launch_event = find(MISSION + " mission starting, duration:")
        if not (len(second_completion) == len(second_release) == len(second_prep_end) == len(launch_event) == 1
                and second_completion[0][0] < second_release[0][0] < second_prep_end[0][0] < launch_event[0][0]):
            errors.append(f"{variant}: final preparation/release/launch line order differs")
    if variant == "aircraft-missing":
        require("latest prep-start timeout", find(MISSION + " mission waiting:  timeout at 8"), (7.5,))
    if variant == "crew-after":
        require("proportional partial turnround", find(OWNERS[1] + " turnround started, mission:"), (8.49,))
        if not any("reduction factor: 0.98" in line[2] for line in find(OWNERS[1] + " turnround started")):
            errors.append(f"{variant}: 0.98 proportional turnround factor absent")
        ordered_stop = [e for e in events if OWNERS[1] in e[2] and e[2].endswith(" ordered to stop")]
        if not (len(ordered_stop) == 1 and find(MISSION + " mission cancelled:")[0][0]
                < ordered_stop[0][0] < releases[-1][0] < stopped[-1][0]):
            errors.append(f"{variant}: cancel/ordered-stop/release/stopped line order differs")
    if variant == "crew-zero" and not all(find(MISSION + " mission cancelled:")[0][0] < e[0] for e in waiting_stop):
        errors.append(f"{variant}: wait termination preceded cancellation")
    if expected["cancel"] is not None:
        lines = log_text.splitlines()
        cancel_rows = [i for i, line in enumerate(lines) if MISSION + " mission cancelled:" in line]
        ready = OWNERS[0] if variant in {"crew-after", "aircraft-missing"} else ""
        in_prep = OWNERS[1] if variant == "crew-after" else ",".join(OWNERS) if variant == "crew-zero" else ""
        if len(cancel_rows) != 1 or len(lines) <= cancel_rows[0] + 2:
            errors.append(f"{variant}: cancellation state snapshot absent")
        else:
            got_ready = lines[cancel_rows[0] + 1].strip()
            got_prep = lines[cancel_rows[0] + 2].strip()
            if got_ready != ("Systems ready: " + ready).strip() or got_prep != ("Systems in prep: " + in_prep).strip():
                errors.append(f"{variant}: cancellation ready/preparing owner snapshot differs")
    if variant == "aircraft-missing":
        prepared = find(OWNERS[0] + " preparation ended, mission:")
        cancelled = find(MISSION + " mission cancelled:")
        if len(prepared) != 1 or len(cancelled) != 1 or prepared[0][0] >= cancelled[0][0]:
            errors.append(f"{variant}: one aircraft did not finish preparation before same-time cancel")
    # Lease rows give a quantity, not an owner ID. Bind each lease to the adjacent
    # owner-specific book/work chain and each release to the owner-specific free row.
    for owner in active_owners:
        owned_request = [e for e in req if owner in e[2]]
        if not owned_request:
            continue
        owned_work = [e for e in started if owner in e[2]]
        owned_book = [e for e in booked if owner in e[2]]
        owned_free = [e for e in freed if owner in e[2]]
        if owned_work:
            nearby_lease = [e for e in leases if owned_book and owned_book[0][0] < e[0] < owned_work[0][0]]
            nearby_release = [e for e in releases if owned_free and owned_free[0][0] < e[0]]
            if not (len(owned_book) == len(owned_work) == len(owned_free) == len(nearby_lease) == 1
                    and owned_request[0][0] < owned_book[0][0] < nearby_lease[0][0] < owned_work[0][0]
                    < owned_free[0][0] and nearby_release):
                errors.append(f"{variant}: {owner} request/book/lease/work/release chain differs")
        elif owned_book or owned_free:
            errors.append(f"{variant}: {owner} booked/freed crew without work")
    return {"allocated_owners": [o for o in OWNERS if any(o in e[2] for e in allocated)],
            "launch_hours": [e[1] for e in find(MISSION + " mission starting, duration:")],
            "cancel_hours": [e[1] for e in find(MISSION + " mission cancelled:")],
            "requests": len(req), "leases": len(leases), "releases": len(releases)}


def check_intervals(variant: str, report: dict, errors: list[str]) -> dict:
    expected = expected_segments(variant)
    data = tables(report, "report")
    system, resource, summary = data["SystemResults"], data["ResourceResults"], data["ResultSummary"]
    if len(system) != 72 or len(resource) != 72:
        errors.append(f"{variant}: expected 72 half-hour system/resource rows, found {len(system)}/{len(resource)}")
    for idx, (s, r) in enumerate(zip(system, resource)):
        a, b = idx / 2, idx / 2 + .5
        for row, label in ((s, "system"), (r, "resource")):
            if not near(row.get("STINT"), a) or not near(row.get("ETINT"), b):
                errors.append(f"{variant}: {label} interval {idx} time differs")
        prep = sum(overlap(span, a, b) for span in expected["prep"])
        ready = sum(overlap(span, a, b) for span in expected["ready"])
        flight = 2 * overlap(expected["flight"], a, b) if expected["flight"] else 0
        assigned = prep + ready + flight
        predictions = {
            "NSYA": expected["quantity"], "NSYRY": expected["quantity"] - assigned,
            "NSYMA": assigned, "NSYMP": prep, "NSYMR": ready, "NSYMO": flight,
            "NSYMT": 0, "NSYUA": 0,
            "NPSTA": sum(a <= t < b for t in expected["prep_starts"]),
            "NPSUC": sum(a <= t < b for t in expected["prep_success"]),
        }
        for key, wanted in predictions.items():
            if not near(s.get(key), wanted, tol=5e-5):
                errors.append(f"{variant}: SystemResults[{idx}].{key}={s.get(key)!r}, expected {wanted!r}")
        resource_predictions = {
            "NR": expected["capacity"],
            "NRUM": sum(overlap(span, a, b) for span in expected["leases"]),
            "NRW": sum(overlap(span, a, b) for span in expected["waits"]),
        }
        for key, wanted in resource_predictions.items():
            if not near(r.get(key), wanted, tol=5e-5):
                errors.append(f"{variant}: ResourceResults[{idx}].{key}={r.get(key)!r}, expected {wanted!r}")
    if len(summary) != 1:
        errors.append(f"{variant}: result summary row count differs")
    else:
        wanted = {"NREP": 1, "RTILW": 0, "RTIUP": 36,
                  "MTMF": int(expected["launch"] is not None),
                  "MSTF": int(expected["launch"] is not None),
                  "MSUF": int(expected["launch"] is not None),
                  "STMF": int(expected["launch"] is not None)}
        for key, value in wanted.items():
            if not near(summary[0].get(key), value):
                errors.append(f"{variant}: ResultSummary.{key}={summary[0].get(key)!r}, expected {value!r}")
    return {"system_intervals": len(system), "resource_intervals": len(resource),
            "last_system": {key: system[-1].get(key) for key in ("NSYA", "NSYRY", "NSYMA", "NSYMP", "NSYMO")},
            "last_resource": {key: resource[-1].get(key) for key in ("NR", "NRUM", "NRW")}}


def review_run(run: Path, contract: dict) -> dict:
    errors: list[str] = []
    variant = run.name.split("-ssh-")[0].removeprefix("c04-v100-")
    if variant not in DELTAS or variant == "horizon-wait":
        return {"run_id": run.name, "passed": False,
                "differences": ["not one of the five C04 acceptance variants; horizon probe is nonpublished"]}
    try:
        source, _ = check_source(variant, contract, errors)
        for name in RAW | {"invocation.json", "closure.json", "validation.json", "run-manifest.json"}:
            if not (run / name).is_file() or (run / name).stat().st_size <= 4:
                errors.append(f"{variant}: missing/empty {name}")
        if errors and any("missing/empty" in error for error in errors):
            return {"run_id": run.name, "variant_id": variant, "passed": False, "differences": errors}
        invocation, closure, manifest = (decode(run / name) for name in
                                         ("invocation.json", "closure.json", "run-manifest.json"))
        spec = contract["variants"][variant]
        if (invocation.get("run_id") != run.name or invocation.get("variant_id") != variant
                or invocation.get("case_id") != "C04" or invocation.get("case_version") != contract["version"]
                or invocation.get("input_sha256") != spec["input_sha256"]
                or invocation.get("parent_input_sha256") != PARENT_HASHES[DELTAS[variant][0]]
                or invocation.get("session_id") != 0 or invocation.get("execution_mode") != "ssh_cli_v1"
                or "sshd.exe" not in invocation.get("ssh_ancestor_names", [])
                or invocation.get("coexisting_gui", {}).get("pid") != 13340
                or invocation.get("coexisting_gui", {}).get("session_id") != 1
                or invocation.get("coexisting_gui", {}).get("responding_at_preflight") is not True):
            errors.append(f"{variant}: SSH/session-0/GUI/source invocation differs")
        bound = {"contract_sha256": HERE / "contract.json",
                 "expected_ledger_sha256": HERE / "expected-ledger.json",
                 "builder_sha256": HERE / "build.py", "validator_sha256": HERE / "validate.py",
                 "runner_sha256": HERE / "run_native_ssh.ps1",
                 "launcher_sha256": HERE / "invoke_loopback.ps1",
                 "parent_diff_sha256": HERE / "parent-diffs" / f"{variant}.json"}
        for key, path in bound.items():
            if invocation.get(key) != digest(path):
                errors.append(f"{variant}: invocation binding {key} differs")
        if digest(run / "input.json") != spec["input_sha256"]:
            errors.append(f"{variant}: run input differs from frozen child")
        if closure.get("run_id") != run.name or closure.get("variant_id") != variant or set(closure.get("raw", {})) != RAW:
            errors.append(f"{variant}: raw closure inventory differs")
        if closure.get("invocation_sha256") != digest(run / "invocation.json"):
            errors.append(f"{variant}: closure invocation hash differs")
        for name, record in closure.get("raw", {}).items():
            path = run / name
            if not path.is_file() or path.stat().st_size != record.get("bytes") or digest(path) != record.get("sha256"):
                errors.append(f"{variant}: raw closure {name} differs")
        if (manifest.get("run_id") != run.name or manifest.get("variant_id") != variant
                or manifest.get("input_sha256") != spec["input_sha256"]
                or manifest.get("invocation_sha256") != digest(run / "invocation.json")
                or manifest.get("closure_sha256") != digest(run / "closure.json")
                or manifest.get("validation_sha256") != digest(run / "validation.json")
                or manifest.get("execution_mode") != "ssh_cli_v1"):
            errors.append(f"{variant}: run manifest linkage differs")
        steps = decode(run / "steps.json")
        if ([step.get("name") for step in steps] != ["import", "export", "calc", "jsonreport"]
                or any(step.get("exit_code") != 0 or step.get("coexisting_gui_present_after") is not True for step in steps)):
            errors.append(f"{variant}: native four-step or preserved GUI evidence differs")
        if tables(decode(run / "roundtrip-raw.json"), "model") != source:
            errors.append(f"{variant}: native roundtrip business rows differ from frozen child")
        run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
        warnings = Counter(re.findall(r"\(warning #(\d+)\)", run_log))
        if not conversion or conversion.group(1) != "0" or warnings != Counter({"108": 1, "126": 1}):
            errors.append(f"{variant}: conversion or warning allowlist differs: {dict(warnings)}")
        log_text = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        event_result = check_events(variant, text_events(run / "model.log"), log_text, errors)
        interval_result = check_intervals(variant, decode(run / "report-raw.json"), errors)
        author = decode(run / "validation.json")
        if author.get("passed") is not True or author.get("differences"):
            errors.append(f"{variant}: author validation did not pass")
        return {"run_id": run.name, "variant_id": variant, "passed": not errors,
                "differences": errors, "event_result": event_result, "interval_result": interval_result,
                "hashes": {name: digest(run / name) for name in
                           ("invocation.json", "closure.json", "validation.json", "run-manifest.json",
                            "model.sxi", "model.sxo", "model.log", "report-raw.json")}}
    except (OSError, KeyError, ValueError, TypeError, IndexError) as exc:
        errors.append(f"{variant}: reviewer could not complete replay: {type(exc).__name__}: {exc}")
        return {"run_id": run.name, "variant_id": variant, "passed": False, "differences": errors}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    contract = decode(HERE / "contract.json")
    results = [review_run(run.resolve(), contract) for run in args.runs]
    if len({row.get("variant_id") for row in results}) != len(results):
        results.append({"passed": False, "differences": ["duplicate variant in review set"]})
    output = {"schema": "simlox-c04-independent-readonly-review/v1", "case_id": "C04",
              "case_version": contract["version"], "reviewer_independent_of_author_code": True,
              "reviewer_sha256": digest(Path(__file__).resolve()),
              "publication_state": "not_published", "passed": all(row["passed"] for row in results),
              "runs": results}
    encoded = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded.encode("utf-8"))
    print(encoded, end="")
    if not output["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

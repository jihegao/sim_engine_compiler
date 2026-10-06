"""Independent, read-only C06.var03 evidence replay.

The author validator is never imported.  This module has no native/process-control
calls.  Run only after both guarded native closures exist; it writes one LF verdict
inside this review directory.  The frozen contract supplies the hypothesis, while
expected report values below are calculated from the accepted C06 parent and an
independent interval ledger.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
REPO = CASE.parents[2]
CONTRACT_SHA = "48a29f63e819e85dc3f9de856199c63441f32f34104dade338ef1ca246bd2384"
SHAPES = {
    "ProblemDescription": (1, 1),
    "ResultSummary": (1, 11),
    "SystemResults": (72, 40),
    "StockTotalResults": (72, 16),
    "ResourceResults": (72, 16),
    "ResourceResultsTotal": (1, 14),
}
GUI = {"pid": 13340, "session_id": 1,
       "start_utc": "2026-09-28T10:09:56.8261381Z"}
CHILD_CLOSURES = {
    1: {"bytes": 11640,
        "sha256": "c81a9187f4eaa81527569c23d5986244a755c3c36c785765daa48827a71de360"},
    3: {"bytes": 11640,
        "sha256": "9c04671966c7226f86cfe4f22efaba7d9e8dfa1a1d44c235ab33851265564a71"},
}


class Audit:
    def __init__(self) -> None:
        self.checks = 0
        self.failures: list[str] = []

    def check(self, condition: bool, label: str) -> None:
        self.checks += 1
        if not condition:
            self.failures.append(label)

    def eq(self, got: object, wanted: object, label: str) -> None:
        preview = lambda value: repr(value)[:240]
        self.check(got == wanted,
                   f"{label}: {preview(got)} != {preview(wanted)}")

    def value(self, got: object, wanted: object, label: str) -> None:
        if isinstance(wanted, (int, float)) and not isinstance(wanted, bool):
            self.check(isinstance(got, (int, float)) and not isinstance(got, bool)
                       and math.isclose(got, wanted, rel_tol=0, abs_tol=2e-5),
                       f"{label}: {got!r} != {wanted!r}")
        else:
            self.eq(got, wanted, label)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def pin(a: Audit, path: Path, record: dict, label: str, git: bool = False) -> None:
    try:
        if git:
            rel = path.relative_to(REPO).as_posix()
            data = subprocess.check_output(["git", "show", f"HEAD:{rel}"],
                                           cwd=REPO, stderr=subprocess.DEVNULL)
        else:
            data = path.read_bytes()
        a.eq(len(data), record["bytes"], label + " bytes")
        a.eq(sha(data), record["sha256"], label + " SHA256")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        a.check(False, f"{label}: {exc}")


def source_pins(a: Audit, group: dict, label: str) -> None:
    a.eq(len(group["source_files"]), group["source_file_count"],
         label + " source inventory")
    for name, record in group["source_files"].items():
        path = REPO / record["path"]
        pin(a, path, record["local_disk"], f"{label} {name} local")
        pin(a, path, record["published_git"], f"{label} {name} Git", True)


def model_tables(doc: dict) -> dict[str, dict]:
    return {t["name"]: t for t in doc["model"]["tables"]}


def rows(table: dict) -> list[list]:
    return table["instances"][0]["rows"]


def columns(table: dict) -> list[str]:
    return [x["name"] for x in table["columns"]]


def native_json(path: Path) -> dict:
    # Some accepted native reports contain trailing commas. Strip them only
    # outside JSON strings, preserving sealed raw bytes and literal text.
    raw = path.read_text(encoding="utf-8-sig")
    in_string = escaped = False
    output: list[str] = []
    for i, ch in enumerate(raw):
        if in_string:
            output.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
            output.append(ch)
        elif ch == ",":
            next_i = i + 1
            while next_i < len(raw) and raw[next_i].isspace():
                next_i += 1
            if next_i < len(raw) and raw[next_i] in ("}", "]"):
                continue
            output.append(ch)
        else:
            output.append(ch)
    return json.loads("".join(output))


def report(path: Path) -> dict[str, tuple[list[str], list[list]]]:
    doc = native_json(path)["report"]
    result: dict[str, tuple[list[str], list[list]]] = {}
    for table in doc["tables"]:
        if table["name"] in result or len(table["instances"]) != 1:
            raise ValueError(f"noncanonical report table topology: {table['name']}")
        all_rows = [row for instance in table["instances"]
                    for row in instance["rows"]]
        result[table["name"]] = (columns(table), all_rows)
    return result


def fields(table: tuple[list[str], list[list]], index: int = 0) -> dict:
    names, all_rows = table
    return dict(zip(names, all_rows[index], strict=True))


def overlap(start: float, end: float, left: float, right: float) -> float:
    return max(0.0, min(end, right) - max(start, left))


def expected_system(parent: dict, factor: int, i: int) -> dict:
    # Parent ARTF2 is the timing control.  Keep its zero/null/identity fields,
    # then independently recompute every time-dependent field for this arm.
    out = fields(parent["SystemResults"], i).copy()
    left, right = i / 2, (i + 1) / 2
    prep_end = 7.5 + max(2, factor) / 3
    mission_end = prep_end + 1
    prep = 4 * overlap(7.5, prep_end, left, right)
    mission = 4 * overlap(prep_end, mission_end, left, right)
    assigned = prep + mission
    out.update(NSYRY=2 - assigned, NSYMA=assigned, NSYMO=mission,
               NSYMP=prep, NSYMR=0, FTMO=mission / 2,
               STACC=mission, NPSTA=2 if i == 15 else 0,
               NPSUC=2 if i == math.floor(prep_end * 2) else 0)
    return out


def expected_resource(parent: dict, factor: int, i: int) -> dict:
    out = fields(parent["ResourceResults"], i).copy()
    left, right = i / 2, (i + 1) / 2
    prep_end = 7.5 + max(2, factor) / 3
    occupancy = 8 * overlap(7.5, prep_end, left, right)
    out.update(NR=4, NRUM=occupancy, NRA=4, NRN=4)
    return out


def exact_report(a: Audit, got: dict, baseline: dict, factor: int,
                 description: str) -> None:
    a.eq(set(got), set(SHAPES), f"factor{factor} report table set")
    compared_cells = 0
    for name, shape in SHAPES.items():
        if name not in got:
            continue
        got_names, got_rows = got[name]
        base_names, base_rows = baseline[name]
        a.eq((len(got_rows), len(got_names)), shape,
             f"factor{factor} {name} dimensions")
        a.eq(got_names, base_names, f"factor{factor} {name} columns")
        if got_names != base_names:
            continue
        for i, row in enumerate(got_rows[:shape[0]]):
            a.eq(len(row), shape[1], f"factor{factor} {name} row{i} width")
            if len(row) != shape[1]:
                continue
            if name == "ProblemDescription":
                wanted = {"PDESC": description}
            elif name == "SystemResults":
                wanted = expected_system(baseline, factor, i)
            elif name == "ResourceResults":
                wanted = expected_resource(baseline, factor, i)
            elif name == "ResourceResultsTotal":
                wanted = fields(baseline[name]).copy()
                wanted.update(NR=4, NRA=4, NRN=4,
                              NRUM=4 * max(2, factor) / (3 * 36))
            else:
                wanted = dict(zip(base_names, base_rows[i], strict=True))
            for field, value in zip(got_names, row, strict=True):
                a.value(value, wanted[field],
                        f"factor{factor} {name}[{i}].{field}")
                compared_cells += 1
    a.eq(compared_cells, 5210, f"factor{factor} all report cells compared")


def source_delta(a: Audit, contract: dict, candidate: dict, factor: int,
                 parent: dict) -> None:
    base, child = model_tables(parent), model_tables(candidate)
    a.eq(set(child), set(base), f"factor{factor} table topology")
    a.eq({name for name in base if base[name] != child[name]},
         set(contract["planned_source"]["changed_tables_from_parent_only"]),
         f"factor{factor} changed tables")
    for name in base:
        if name not in contract["planned_source"]["changed_tables_from_parent_only"]:
            a.eq(child[name], base[name], f"factor{factor} unchanged {name}")
    for name in ("Resource", "ResourceAllocation"):
        expected = contract["planned_source"]["added_rows_common"][name]
        a.eq(columns(child[name]), expected["columns"],
             f"factor{factor} {name} columns")
        a.eq(rows(child[name]), rows(base[name]) + expected["rows"],
             f"factor{factor} {name} exact rows")
    sub = child["SubTaskResource"]
    wanted = contract["planned_source"]["added_SubTaskResource"][f"factor{factor}"]
    a.eq(columns(sub), contract["planned_source"]["added_SubTaskResource"]["columns"],
         f"factor{factor} SubTaskResource columns")
    a.eq(rows(sub), rows(base["SubTaskResource"]) + [wanted],
         f"factor{factor} SubTaskResource exact rows")
    a.eq(len(rows(child["ProblemDescription"])), 1,
         f"factor{factor} one description")
    a.eq(columns(child["ProblemDescription"]),
         columns(base["ProblemDescription"]),
         f"factor{factor} description columns")
    a.eq(rows(child["ProblemDescription"]),
         [[contract["planned_source"]["arms"][f"factor{factor}"]["description"]]],
         f"factor{factor} exact description")


def verify_run_seal(a: Audit, run: dict, label: str) -> Path:
    folder = Path(run["path"])
    for key in ("closure", "invocation"):
        pin(a, folder / f"{key}.json", run[key], f"{label} {key}")
    a.eq(len(run["raw"]), run["raw_count"], f"{label} raw inventory")
    for name, record in run["raw"].items():
        pin(a, folder / name, record, f"{label} raw {name}")
    closure = read_json(folder / "closure.json")
    a.eq(closure["raw"], run["raw"], f"{label} closure raw map")
    a.eq(closure["invocation_sha256"], run["invocation"]["sha256"],
         f"{label} invocation closure pin")
    return folder


def event_lines(log: str) -> list[tuple[float, str]]:
    found = []
    for line in log.splitlines():
        match = re.match(r"\s*Time:\s*([0-9]+(?:\.[0-9]+)?)\s+(.*)", line)
        if match:
            found.append((float(match.group(1)), match.group(2)))
    return found


def timed(a: Audit, events: list[tuple[float, str]], needle: str,
          expected: float, label: str, count: int = 1) -> None:
    matched = [when for when, text in events if needle in text]
    a.eq(len(matched), count, f"{label} count")
    for when in matched:
        a.value(when, expected, f"{label} time")


def physical(a: Audit, factor: int, log: str) -> None:
    events = event_lines(log)
    finish = 7.5 + max(2, factor) / 3
    mission_end = finish + 1
    duration = max(2, factor) / 3
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    timed(a, events, f"{mission} mission activated, systems requested: 2",
          7.5, f"factor{factor} mission activation")
    timed(a, events, f"{mission} mission starting, duration: 1",
          finish, f"factor{factor} launch")
    timed(a, events, f"{mission} mission success:",
          mission_end, f"factor{factor} success")
    timed(a, events, f"{mission} mission completed:",
          mission_end, f"factor{factor} completion")
    for aircraft in (0, 1):
        id_token = f"<TEACH-AIR-01,{aircraft}>"
        subtask = (f"subtask {aircraft} seqno 1 within system preparation "
                   f"task {aircraft} on {id_token}")
        timed(a, events, f"{mission} mission allocates system: {id_token}",
              7.5, f"factor{factor} ID{aircraft} allocation")
        for label, when, suffix in (
            ("subtask start", 7.5, "started"),
            ("availability test", 7.5, "resource availability test"),
            ("book resources", 7.5, "books resources"),
            ("planned work", 7.5, "starts performing, planned to last for"),
            ("subtask completion", finish, "completed"),
            ("free resources", finish, "frees resources"),
        ):
            timed(a, events, subtask + " " + suffix, when,
                  f"factor{factor} ID{aircraft} {label}")
        planned = re.search(re.escape(subtask) +
                            r" starts performing, planned to last for ([0-9.]+) hours",
                            log)
        a.check(planned is not None, f"factor{factor} ID{aircraft} work duration logged")
        if planned:
            a.value(float(planned.group(1)), duration,
                    f"factor{factor} ID{aircraft} max factor duration")
        timed(a, events, f"System arrives {id_token}, mission success",
              mission_end, f"factor{factor} ID{aircraft} return")
        test_start = log.find(subtask + " resource availability test")
        test_end = log.find(subtask + " books resources", test_start)
        a.check(test_start >= 0 and test_end > test_start,
                f"factor{factor} ID{aircraft} typed test block")
        if test_start >= 0 and test_end > test_start:
            block = log[test_start:test_end]
            for resource, state in (("P-CREW", "failed"),
                                    ("P-AUX", "failed"),
                                    ("P-ALT", "OK"),
                                    ("P-AUXALT", "OK")):
                a.check(f"<{resource} at <BASE-01,0>> request for: 1 {state}" in block,
                        f"factor{factor} ID{aircraft} {resource} test {state}")
        booking_start = log.find(subtask + " books resources")
        booking_end = log.find(subtask + " starts performing", booking_start)
        a.check(booking_start >= 0 and booking_end > booking_start,
                f"factor{factor} ID{aircraft} booking block")
        if booking_start >= 0 and booking_end > booking_start:
            block = log[booking_start:booking_end]
            for resource in ("P-ALT", "P-AUXALT"):
                a.eq(block.count(
                    f"<{resource} at <BASE-01,0>> allocated to maintenance task: 1"),
                    1, f"factor{factor} ID{aircraft} one {resource} booking")
        release_start = log.find(subtask + " frees resources")
        release_end = log.find(
            f"subtask {aircraft} seqno 1 check return remote resources",
            release_start)
        a.check(release_start >= 0 and release_end > release_start,
                f"factor{factor} ID{aircraft} release block")
        if release_start >= 0 and release_end > release_start:
            block = log[release_start:release_end]
            for resource in ("P-ALT", "P-AUXALT"):
                a.eq(block.count(
                    f"<{resource} at <BASE-01,0>> deallocated from  maintenance task: 1"),
                    1, f"factor{factor} ID{aircraft} one {resource} release")
    for resource, booked in (("P-CREW", 0), ("P-AUX", 0),
                             ("P-ALT", 2), ("P-AUXALT", 2)):
        a.eq(sum(f"<{resource} at <BASE-01,0>> allocated to maintenance task: 1"
                 in line for _, line in events), booked,
             f"factor{factor} {resource} booking count")
        a.eq(sum(f"<{resource} at <BASE-01,0>> deallocated from  maintenance task: 1"
                 in line for _, line in events), booked,
             f"factor{factor} {resource} release count")
        if booked:
            timed(a, events,
                  f"<{resource} at <BASE-01,0>> allocated to maintenance task: 1",
                  7.5, f"factor{factor} {resource} booking", count=2)
            timed(a, events,
                  f"<{resource} at <BASE-01,0>> deallocated from  maintenance task: 1",
                  finish, f"factor{factor} {resource} release", count=2)
    a.check("mission cancelled" not in log and "mission aborted" not in log,
            f"factor{factor} no cancellation/abort")
    a.check("failure occurred" not in log.lower() and "failed item" not in log.lower(),
            f"factor{factor} no fault-driven repair")
    wait_lines = [line.strip() for line in log.splitlines()
                  if "Tasks waiting for resources at: <BASE-01,0>" in line]
    a.check(bool(wait_lines) and all(line.endswith("0") for line in wait_lines),
            f"factor{factor} no unresolved resource wait")
    ready2 = [when for when, text in events
              if "<TEACH-UNIT at <BASE-01,0>> systems ready: 2" in text]
    a.eq(len(ready2), 2, f"factor{factor} opening/terminal two-ready count")
    for got, wanted in zip(ready2, (0, mission_end)):
        a.value(got, wanted, f"factor{factor} opening/terminal ready time")


def child_run(a: Audit, contract: dict, manifest: dict,
              expected_sources: dict[str, str], factor: int,
              candidate: dict, baseline: dict) -> dict:
    arm = f"factor{factor}"
    run_id = contract["planned_source"]["arms"][arm]["run_id"]
    folder = CASE / "runs" / run_id
    a.check(folder.is_dir(), f"{arm} reserved native run exists")
    pin(a, folder / "closure.json", CHILD_CLOSURES[factor],
        f"{arm} independently frozen closure")
    closure = read_json(folder / "closure.json")
    invocation_path = folder / "invocation.json"
    invocation = read_json(invocation_path)
    a.eq(closure["run_id"], run_id, f"{arm} closure run ID")
    a.eq(invocation["run_id"], run_id, f"{arm} invocation run ID")
    a.eq(invocation["arm"], arm, f"{arm} invocation arm")
    a.eq(closure["invocation_sha256"], sha(invocation_path.read_bytes()),
         f"{arm} invocation raw SHA seal")
    a.eq(closure["source_hashes_before"], expected_sources,
         f"{arm} source before frozen manifest")
    a.eq(closure["source_hashes_after"], expected_sources,
         f"{arm} source after frozen manifest")
    a.eq(invocation["source_hashes_before"], expected_sources,
         f"{arm} invocation source manifest")
    a.eq(invocation["manifest_sha256"], sha((CASE / "prelaunch-manifest.json").read_bytes()),
         f"{arm} invocation manifest SHA")
    approval_path = HERE / "independent-prelaunch-go.json"
    approval = read_json(approval_path)
    a.eq(invocation["approval_sha256"], sha(approval_path.read_bytes()),
         f"{arm} invocation independent approval SHA")
    a.eq(closure["manifest_sha256"],
         sha((CASE / "prelaunch-manifest.json").read_bytes()),
         f"{arm} closure manifest SHA")
    a.eq(closure["approval_sha256"], sha(approval_path.read_bytes()),
         f"{arm} closure independent approval SHA")
    a.eq(invocation["approved_preflight_sha256"], approval["preflight_sha256"],
         f"{arm} invocation SSH0 preflight SHA")
    a.eq(closure["approved_preflight_sha256"], approval["preflight_sha256"],
         f"{arm} closure SSH0 preflight SHA")
    a.eq(Path(invocation["approved_preflight_path"]).resolve(),
         (CASE / approval["preflight_relative_path"]).resolve(),
         f"{arm} approved preflight path")
    a.eq(invocation["input_sha256"],
         sha((CASE / f"{arm}-input.json").read_bytes()),
         f"{arm} authored input SHA")
    a.eq(invocation["contract_sha256"], CONTRACT_SHA,
         f"{arm} invocation contract SHA")
    a.eq(invocation["session_id"], 0, f"{arm} SSH session0")
    a.check("sshd.exe" in invocation["ssh_ancestors"],
            f"{arm} SSH ancestry")
    a.eq(invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue",
         f"{arm} global mutex")
    a.eq(invocation["gui"],
         {"pid": 13340, "session_id": 1,
          "start_unix_ms": 1790590196826, "responding": True},
         f"{arm} protected GUI")
    a.eq(invocation["execution_mode"], "ssh_cli_v1",
         f"{arm} execution mode")
    a.eq(invocation["publication_state"], "not_published",
         f"{arm} publication state")
    raw = closure["raw"]
    a.eq(set(raw) | {"closure.json", "invocation.json"},
         {p.name for p in folder.iterdir() if p.is_file()},
         f"{arm} complete raw inventory")
    for filename, seal in raw.items():
        pin(a, folder / filename, seal, f"{arm} raw {filename}")
    # The runner passes $null into a [string] parameter; PowerShell serializes
    # the successful value as the empty string. Preserve and assert that byte fact.
    a.eq(closure["error"], "", f"{arm} empty native/behavior error string")
    a.eq(closure["publication_state"], "not_published",
         f"{arm} closure publication state")
    a.eq(sha((folder / "input.json").read_bytes()),
         sha((CASE / f"{arm}-input.json").read_bytes()),
         f"{arm} exact copied source SHA")
    steps = read_json(folder / "steps.json")
    a.eq([s["name"] for s in steps],
         ["import", "export", "check_import_export", "calc",
          "jsonreport", "check_behavior"],
         f"{arm} guarded six-step order")
    native_pids: list[int] = []
    for step in steps:
        a.eq(step["status"], "completed", f"{arm} {step['name']} completed")
        a.eq(step["exit_code"], 0, f"{arm} {step['name']} exit0")
        a.eq(step["gui_preserved"], True,
             f"{arm} {step['name']} preserved GUI")
        if step["name"] in ("import", "export", "calc", "jsonreport"):
            a.check(isinstance(step.get("child_pid"), int) and
                    step["child_pid"] != 13340,
                    f"{arm} {step['name']} separate native child PID")
            a.eq(step.get("child_session_id"), 0,
                 f"{arm} {step['name']} native child session0")
            if isinstance(step.get("child_pid"), int):
                native_pids.append(step["child_pid"])
    a.eq(len(set(native_pids)), 4, f"{arm} four distinct native children")
    runlog = (folder / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    a.check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog,
            f"{arm} converter count 0/2/0")
    a.eq(sorted(re.findall(r"warning\s*#(\d+)", runlog, flags=re.I)),
         ["108", "126"], f"{arm} only converter warnings 108/126")
    a.eq(re.findall(r"error\s*#(\d+)", runlog, flags=re.I), [],
         f"{arm} zero converter error lines")
    exported = model_tables(native_json(folder / "roundtrip-raw.json"))
    authored = model_tables(candidate)
    populated = [name for name, table in authored.items()
                 if any(instance["rows"] for instance in table["instances"])]
    a.eq(len(populated), 20, f"{arm} 20 row-containing authored tables")
    for name in populated:
        a.eq(exported[name]["columns"], authored[name]["columns"],
             f"{arm} {name} exact roundtrip columns")
        a.eq(exported[name]["instances"], authored[name]["instances"],
             f"{arm} {name} exact all-instance rows")
    physical(a, factor, (folder / "model.log").read_text(encoding="utf-8-sig",
                                               errors="replace"))
    actual_report = report(folder / "report-raw.json")
    description = contract["planned_source"]["arms"][arm]["description"]
    exact_report(a, actual_report, baseline, factor, description)
    return actual_report


def main() -> dict:
    a = Audit()
    contract_bytes = (CASE / "contract.json").read_bytes()
    a.eq(sha(contract_bytes), CONTRACT_SHA, "frozen contract")
    contract = json.loads(contract_bytes)
    a.eq(contract["variant_id"], "C06.var03", "variant")
    a.eq(sum(r * n for r, n in SHAPES.values()), 5210,
         "independent per-arm report cell count")
    a.eq(contract["predeclared_native_acceptance"]["reports"]["total_pair_cells"],
         10420, "contract pair report cell count")
    excluded = contract["excluded_diagnostic"]
    a.eq(excluded["classification"], "NO_GO_CONTRACT", "v100 excluded")
    a.eq(excluded["native_child_count"], 0, "v100 no native child")
    for key in ("frozen_contract", "independent_no_go_memo"):
        item = excluded[key]
        pin(a, REPO / "cases" / "simlox-air-support" / item["path"], item,
            f"v100 {key}")
    for key in ("accepted_C03_prerequisite", "accepted_C06_parent"):
        source_pins(a, contract[key], key)
    for record in contract["accepted_C06_var02_context"]["pins"].values():
        path = REPO / record["path"]
        pin(a, path, record["local_disk"], "C06.var02 " + path.name + " local")
        pin(a, path, record["published_git"], "C06.var02 " + path.name + " Git", True)
    pin(a, Path(contract["manual"]["installed_pdf"]),
        contract["manual"]["seal"], "installed manual")
    parent_record = contract["accepted_C06_parent"]
    parent_path = REPO / parent_record["input"]["path"]
    parent = read_json(parent_path)
    parent_folder = verify_run_seal(a, parent_record["run"], "accepted C06 parent")
    verify_run_seal(a, contract["accepted_C03_prerequisite"]["staffing_2_run"],
                    "accepted C03 prerequisite")
    baseline = report(parent_folder / "report-raw.json")

    candidate: dict[int, dict] = {}
    for factor in (1, 3):
        path = CASE / f"factor{factor}-input.json"
        a.check(path.is_file(), f"factor{factor} frozen child input exists")
        if path.is_file():
            candidate[factor] = read_json(path)
            source_delta(a, contract, candidate[factor], factor, parent)
    if len(candidate) == 2:
        first, third = model_tables(candidate[1]), model_tables(candidate[3])
        a.eq({name for name in first if first[name] != third[name]},
             {"ProblemDescription", "SubTaskResource"},
             "exact pairwise changed tables")
        for name in first:
            if name not in ("ProblemDescription", "SubTaskResource"):
                a.eq(first[name], third[name], f"pair identical {name}")
        a.eq(rows(first["SubTaskResource"])[0],
             rows(third["SubTaskResource"])[0],
             "first required resource row invariant")
        a.eq(rows(first["SubTaskResource"])[1][6], 1.0,
             "factor1 second ARTF")
        a.eq(rows(third["SubTaskResource"])[1][6], 3.0,
             "factor3 second ARTF")

    # The contract is immutable.  The separate prelaunch manifest and closures
    # bind the child source and evidence.  Refuse to issue a verdict early.
    manifest_path = CASE / "prelaunch-manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("separate prelaunch manifest pending")
    manifest = read_json(manifest_path)
    a.eq(manifest["schema"], "c06-var03-v101-prelaunch-manifest/v1",
         "prelaunch manifest schema")
    a.eq(manifest["contract_sha256"], CONTRACT_SHA,
         "prelaunch manifest contract")
    expected_sources: dict[str, str] = {}
    for record in manifest["source_files"]:
        key = record["key"]
        a.check(key not in expected_sources, f"unique manifest key {key}")
        expected_sources[key] = record["sha256"]
        pin(a, Path(record["path"]), record,
            f"prelaunch source {key}")
    a.eq(manifest["accepted_parent_closure_sha256"],
         parent_record["run"]["closure"]["sha256"],
         "manifest accepted C06 closure")
    a.eq(manifest["accepted_c03_closure_sha256"],
         contract["accepted_C03_prerequisite"]["staffing_2_run"]["closure"]["sha256"],
         "manifest accepted C03 closure")
    approvals = CASE / "review" / "independent-prelaunch-go.json"
    a.check(approvals.is_file(), "independent prelaunch approval exists")
    if approvals.is_file():
        approval = read_json(approvals)
        a.eq(approval["decision"], "GO_PRELAUNCH", "prelaunch decision")
        a.eq(approval["manifest_sha256"], sha(manifest_path.read_bytes()),
             "prelaunch approval manifest pin")
        a.eq(approval["runner_sha256"], expected_sources["runner_script"],
             "prelaunch approval runner pin")
        a.eq(approval["validator_sha256"], expected_sources["behavior_validator"],
             "prelaunch approval validator pin")
        a.eq(approval["contract_sha256"], CONTRACT_SHA,
             "prelaunch approval contract pin")
        a.eq(approval["factor1_input_sha256"], expected_sources["factor1_input"],
             "prelaunch approval factor1 input pin")
        a.eq(approval["factor3_input_sha256"], expected_sources["factor3_input"],
             "prelaunch approval factor3 input pin")
        a.eq(approval["run_ids"],
             [contract["planned_source"]["arms"][arm]["run_id"]
              for arm in ("factor1", "factor3")],
             "prelaunch approval unique pair IDs")
        preflight = CASE / approval["preflight_relative_path"]
        pin(a, preflight, {"bytes": preflight.stat().st_size,
                           "sha256": approval["preflight_sha256"]},
            "approved SSH0 preflight raw")

    if not all((CASE / "runs" / contract["planned_source"]["arms"][arm]["run_id"]
                / "closure.json").is_file() for arm in ("factor1", "factor3")):
        raise RuntimeError("both immutable native child closures are pending")
    pair_reports: dict[int, dict] = {}
    for factor in (1, 3):
        pair_reports[factor] = child_run(a, contract, manifest, expected_sources,
                                         factor, candidate[factor], baseline)
    a.eq(pair_reports[1]["SystemResults"], baseline["SystemResults"],
         "factor1 full 72x40 System parent parity")
    a.eq(pair_reports[1]["StockTotalResults"],
         pair_reports[3]["StockTotalResults"],
         "full stock pair parity")
    a.eq(pair_reports[1]["ResultSummary"],
         pair_reports[3]["ResultSummary"],
         "full summary pair parity")
    for factor in (1, 3):
        resources = pair_reports[factor]["ResourceResults"]
        systems = pair_reports[factor]["SystemResults"]
        use_hours = sum(fields(resources, i)["NRUM"] * 0.5 for i in range(72))
        prep_hours = sum(fields(systems, i)["NSYMP"] * 0.5 for i in range(72))
        flight_hours = sum(fields(systems, i)["NSYMO"] * 0.5 for i in range(72))
        a.value(use_hours, 4 * max(2, factor) / 3,
                f"factor{factor} resource person-hour integral")
        a.value(prep_hours, 2 * max(2, factor) / 3,
                f"factor{factor} aircraft prep-hour integral")
        a.value(flight_hours, 2,
                f"factor{factor} two-aircraft flight-hour integral")
    return {
        "schema": "c06-var03-v101-independent-verdict/v1",
        "case_id": "C06.var03", "contract_sha256": CONTRACT_SHA,
        "decision": "GO_BOUNDED" if not a.failures else "NO_GO",
        "checks": a.checks, "failures": a.failures,
        "scope": "Two guarded fixed-seed native arms with two simultaneous alternative resource requirements.",
        "limits": [
            "One two-aircraft mission and one subtask with ARTF pair (2,1) versus (2,3); no general max-factor law.",
            "Both primaries have zero capacity, alternatives two each, RPROB one; no partial or probabilistic alternatives.",
            "Typed event and aggregate resource conservation; persistent resource IDs are not observable.",
            "No new GUI observation or other engine/seed result.",
        ],
    }


if __name__ == "__main__":
    outcome = main()
    (HERE / "independent-verdict.json").write_bytes(
        (json.dumps(outcome, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    print(outcome["decision"], outcome["checks"], "checks")

"""Independent read-only C02.var01 physical and full-report replay.

The sealed accepted control may be checked with --control-only before the child
exists. The default mode fails closed until the approved child run is sealed.
This file imports no author implementation and never writes raw evidence.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
CONTRACT_SHA = "e8cce2aeae398f8e725365ab7472b0a7a92b9681cc63299e581d642e76ef9d12"
PARENT = ROOT / "cases/simlox-air-support/C02-joint-resources-v1.0.2"
TABLES = ("ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal")
SHAPE = {"ProblemDescription": (1, 1), "ResultSummary": (1, 11), "SystemResults": (72, 40), "StockTotalResults": (72, 16), "ResourceResults": (72, 16), "ResourceResultsTotal": (1, 14)}
INSTANCE = {"ProblemDescription": "", "ResultSummary": "", "SystemResults": "Total over all Units;Total over all Systems;0.00;36.00", "StockTotalResults": "0.00;36.00;", "ResourceResults": "Total over all Resources;Total over all Stations;0.00;36.00", "ResourceResultsTotal": "Total over all Resources;Total over all Stations;0.00;36.00"}
SUMMARY = ("NREP", "RTILW", "RTIUP", "MTMF", "RSMTMF", "MSTF", "RSMSTF", "MSUF", "RSMSUF", "STMF", "RSSTMF")


class Audit:
    def __init__(self):
        self.checks = 0
        self.failures = []
        self.report_cells = 0

    def yes(self, condition, label):
        self.checks += 1
        if not condition:
            self.failures.append(label)

    def eq(self, actual, expected, label):
        if isinstance(expected, bool) or expected is None or isinstance(expected, str):
            good = type(actual) is type(expected) and actual == expected
        elif isinstance(expected, (float, int)):
            good = type(actual) in (float, int) and math.isfinite(actual) and actual == expected
        else:
            good = type(actual) is type(expected) and actual == expected
        self.yes(good, label)

    def numeric(self, actual, expected, bound, label):
        self.yes(type(actual) in (int, float) and math.isfinite(actual) and abs(actual - expected) <= bound, label)

    def cell(self, actual, expected, label, bound=0):
        self.report_cells += 1
        if bound:
            self.numeric(actual, expected, bound, label)
        else:
            self.eq(actual, expected, label)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def native_json(raw):
    """Remove native trailing commas only outside JSON strings, in memory."""
    source = raw.decode("utf-8-sig")
    out = []
    quoted = escaped = False
    for i, ch in enumerate(source):
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
        elif ch == ",":
            j = i + 1
            while j < len(source) and source[j].isspace():
                j += 1
            if j >= len(source) or source[j] not in "]}":
                out.append(ch)
        else:
            out.append(ch)
    return json.loads("".join(out))


def sealed(a, path, pin, label):
    a.yes(path.is_file(), label + " exists")
    if path.is_file():
        raw = path.read_bytes()
        a.eq(len(raw), pin["bytes"], label + " size")
        a.eq(digest(raw), pin["sha256"], label + " sha256")
        return raw
    return b""


def published_sources(a, contract):
    """Check the accepted source's local and published Git bytes separately."""
    base = contract["ownership"]["base_commit"]
    evidence = contract["accepted_evidence"]
    cases = ROOT / "cases/simlox-air-support"

    def blob(package, relative, pin, label):
        path = cases / package / relative
        sealed(a, path, pin, label + " local")
        git_path = "cases/simlox-air-support/" + package + "/" + relative
        result = subprocess.run(["git", "show", base + ":" + git_path], cwd=ROOT,
                                capture_output=True, check=False)
        a.eq(result.returncode, 0, label + " published Git blob exists")
        if result.returncode == 0:
            return result.stdout
        return b""

    classification = evidence["classification"]
    for pin in classification["source_files"]:
        raw = blob(classification["package"], pin["path"], pin,
                   "classification " + pin["path"])
        a.eq(len(raw), pin["bytes"], "classification Git bytes " + pin["path"])
        a.eq(digest(raw), pin["sha256"], "classification Git SHA " + pin["path"])
    parent = evidence["C02_parent"]
    for pin in parent["source_files_dual_local_and_git"]:
        raw = blob(parent["package"], pin["path"], pin["local_disk"],
                   "C02 parent " + pin["path"])
        a.eq(len(raw), pin["published_git"]["bytes"], "C02 parent Git bytes " + pin["path"])
        a.eq(digest(raw), pin["published_git"]["sha256"], "C02 parent Git SHA " + pin["path"])
    c01 = evidence["C01_capacity_zero_context"]
    for name, pin in c01["source_files_dual_local_and_git"].items():
        raw = blob(c01["package"], name,
                   {"bytes": pin["local_bytes"], "sha256": pin["local_sha256"]},
                   "C01 prerequisite " + name)
        a.eq(len(raw), pin["published_git_bytes"], "C01 Git bytes " + name)
        a.eq(digest(raw), pin["published_git_sha256"], "C01 Git SHA " + name)


def table_map(doc, root):
    return {table["name"]: table for table in doc[root]["tables"]}


def rows(table):
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for inst in table["instances"] for row in inst["rows"]]


def flat_cells(doc):
    result = {}
    for name, table in table_map(doc, "model").items():
        cols = [c["name"] for c in table["columns"]]
        for ii, inst in enumerate(table["instances"]):
            for ri, row in enumerate(inst["rows"]):
                for ci, value in enumerate(row):
                    result[name, ii, ri, cols[ci]] = value
    return result


def source_isolation(a, parent, child, contract):
    """Compare complete model topology after only the two allowed cell changes."""
    expected = copy.deepcopy(parent)
    data = table_map(expected, "model")
    allocations = data["ResourceAllocation"]
    names = [c["name"] for c in allocations["columns"]]
    rows_ = allocations["instances"][0]["rows"]
    selected = [r for r in rows_ if dict(zip(names, r))["RID"] == "P-CREW"]
    a.eq(len(selected), 1, "one P-CREW allocation row")
    if len(selected) != 1:
        return
    selected[0][names.index("RQTY")] = 0
    desired = contract["source_design"]["sole_child_delta"][1]["after"]
    data["ProblemDescription"]["instances"][0]["rows"][0][0] = desired
    a.eq(child, expected, "entire child model exact two-cell delta including metadata")
    old, new = flat_cells(parent), flat_cells(child)
    a.eq(set(old), set(new), "child same authored cell keys")
    differences = [(key, old[key], new.get(key)) for key in old if old[key] != new.get(key)]
    a.eq(differences, [(("ProblemDescription", 0, 0, "PDESC"), contract["source_design"]["sole_child_delta"][1]["before"], desired), (("ResourceAllocation", 0, 0, "RQTY"), 1, 0)], "two exact source cells")


def roundtrip(a, authored, exported, label):
    left, right = authored["model"]["tables"], exported["model"]["tables"]
    a.eq([t["name"] for t in right], [t["name"] for t in left], label + " table order")
    populated = 0
    for before, after in zip(left, right):
        name = before["name"]
        a.eq(after["columns"], before["columns"], label + " " + name + " columns/types/order")
        a.eq(len(after["instances"]), len(before["instances"]), label + " " + name + " instance count")
        for origin, native in zip(before["instances"], after["instances"]):
            a.eq(native["instance_name"], origin["instance_name"], label + " " + name + " instance name")
            a.eq(native["rows"][:len(origin["rows"])], origin["rows"], label + " " + name + " rows")
            if origin["rows"]:
                populated += 1
            for row in native["rows"][len(origin["rows"]):]:
                a.yes(all(value is None for value in row), label + " " + name + " extra null placeholder only")
    a.eq(populated, 20, label + " 20 row-containing tables")


def diagnostics(a, run_log, label):
    a.yes(re.search(r"Control\s*\r?\nrec 1: \(warning #108\)", run_log) is not None, label + " #108 Control rec1")
    a.yes(re.search(r"System\s*\r?\nrec 1: \(warning #126\)", run_log) is not None, label + " #126 System rec1")
    a.eq(len(re.findall(r"\(warning #\d+\)", run_log)), 2, label + " two warnings")
    a.yes("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in run_log, label + " 0/2/0")


def extract_time(line):
    match = re.match(r"Time: ([0-9]+(?:\.[0-9]+)?)\b", line)
    return float(match.group(1)) if match else None


def printed_uncertainty(token):
    decimals = len(token.partition(".")[2])
    return 0 if decimals == 0 else 0.5 * 10 ** (-decimals)


def selected_time(a, lines, fragment, label):
    matches = [(i, line) for i, line in enumerate(lines) if fragment in line]
    a.eq(len(matches), 1, label + " unique")
    if len(matches) != 1:
        return math.nan, math.inf, -1
    index, line = matches[0]
    match = re.match(r"Time: ([0-9]+(?:\.[0-9]+)?)\b", line)
    a.yes(match is not None, label + " timestamp")
    if not match:
        return math.nan, math.inf, index
    token = match.group(1)
    return float(token), printed_uncertainty(token), index


def physical_parent(a, log):
    lines = log.splitlines()
    required = [
        "mission ordered: BASIC-MISSION",
        "mission activated, systems requested: 1",
        "mission allocates system: <TEACH-AIR-01,0>",
        "preparation started, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>",
        "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> requests resources",
        "Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK",
        "Availability test on  <E-GSE at <BASE-01,0>> request for: 1 OK",
        "<P-CREW at <BASE-01,0>> allocated to maintenance task: 1",
        "<E-GSE at <BASE-01,0>> allocated to maintenance task: 1",
        "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing",
        "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed",
        "<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1",
        "<E-GSE at <BASE-01,0>> deallocated from  maintenance task: 1",
        "mission starting, duration: 2 : <TEACH-AIR-01,0>",
        "mission success:",
        "mission completed: <TEACH-AIR-01,0>",
        "System arrives <TEACH-AIR-01,0>",
        "System ready <TEACH-AIR-01,0>",
    ]
    indices = []
    for fragment in required:
        matches = [i for i, line in enumerate(lines) if fragment in line]
        a.eq(len(matches), 1 if fragment != "System ready <TEACH-AIR-01,0>" else 2, "control event " + fragment)
        indices.append(matches[0] if matches else -1)
    a.yes(all(x < y for x, y in zip(indices, indices[1:])), "control physical order")
    for fragment, hour in (("mission ordered: BASIC-MISSION", 7), ("starts performing", 7), ("subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed", 7.5), ("mission starting, duration: 2", 8), ("mission success:", 10)):
        match = next((line for line in lines if fragment in line), "")
        a.eq(extract_time(match), hour, "control time " + fragment)
    a.yes("mission cancelled" not in log, "control not cancelled")
    a.eq(log.count("allocated to maintenance task: 1"), 2, "control two bookings")
    a.eq(log.count("deallocated from  maintenance task: 1"), 2, "control two releases")


def physical_child(a, log):
    lines = log.splitlines()
    fragments = [
        "mission ordered: BASIC-MISSION",
        "mission activated, systems requested: 1",
        "mission allocates system: <TEACH-AIR-01,0>",
        "preparation started, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>",
        "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> requests resources",
        "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> resource availability test",
        "Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed",
        "Availability test on  <E-GSE at <BASE-01,0>> request for: 1 OK",
        "mission cancelled:",
        "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> ordered to stop",
        "resource waiting stopped",
        "preparation ended, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>",
        "System arrives <TEACH-AIR-01,0>",
        "System ready <TEACH-AIR-01,0>",
    ]
    indices = []
    for fragment in fragments:
        matches = [i for i, line in enumerate(lines) if fragment in line]
        if fragment == "System ready <TEACH-AIR-01,0>":
            a.yes(len(matches) >= 1, "child terminal ready event")
        else:
            a.eq(len(matches), 1, "child event " + fragment)
        indices.append(matches[0] if matches else -1)
    a.yes(all(x < y for x, y in zip(indices, indices[1:])), "child typed event order")
    cancel, uncertainty, _ = selected_time(a, lines, "mission cancelled:", "child cancellation")
    a.yes(7 < cancel <= 8 + 1 / 3, "child cancellation after request and by latest launch")
    for fragment in ("mission allocates system", "preparation started", "requests resources", "resource availability test"):
        match = next((line for line in lines if fragment in line), "")
        a.eq(extract_time(match), 7, "child h7 " + fragment)
    for fragment in ("System arrives <TEACH-AIR-01,0>", "preparation ended, mission:"):
        match = next((line for line in lines if fragment in line), "")
        a.numeric(extract_time(match), cancel, uncertainty, "child release at cancellation " + fragment)
    for forbidden in ("books resources", "allocated to maintenance task:", "deallocated from  maintenance task:", "starts performing", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed", "mission starting", "mission success", "mission completed"):
        a.yes(forbidden not in log, "child excludes " + forbidden)
    a.eq(log.count("mission ordered: BASIC-MISSION"), 1, "one mission")
    return cancel, uncertainty


def expected_rows(role, index, cancel=None):
    """Source/event-derived values for all System, Stock, Resource columns."""
    start, end = index / 2, (index + 1) / 2
    parent = role == "parent"
    system = {name: 0 for name in ("UNID", "SID", "STINT", "ETINT", "NSYRY", "NSYMA", "NSYMO", "NSYMC", "NSYMP", "NSYMT", "NSYMS", "NSYMR", "NSYUA", "NSYA", "NSYAL", "FTMO", "NSYRP", "NSYPM", "NSYTP", "NSYWR", "NSYWI", "NSYLA", "NSYUH", "NREPT", "NPMT", "NFAIL", "NDAM", "NPMS", "NROBT", "NRCFG", "STREQ", "STACC", "STF", "STLOW", "SYDT", "SYDTU", "NSYDT", "NSYSW", "NPSTA", "NPSUC")}
    system.update(UNID="Total over all Units", SID="Total over all Systems", STINT=start, ETINT=end, NSYA=1, SYDT=None)
    if parent:
        if index < 14 or index >= 20:
            system["NSYRY"] = 1
        elif index == 14:
            system.update(NSYMA=1, NSYMP=1, NPSTA=1)
        elif index == 15:
            system.update(NSYMA=1, NSYMR=1, NPSUC=1)
        else:
            system.update(NSYMA=1, NSYMO=1, FTMO=1, STACC=1)
    else:
        assert cancel is not None
        prep = max(0, min(end, cancel) - max(start, 7)) / 0.5
        system.update(NSYRY=1 - prep, NSYMA=prep, NSYMP=prep)
        if index == 14:
            system["NPSTA"] = 1
    stock = {name: 0 for name in ("STINT", "ETINT", "NBO", "NBOU", "ROS", "ROST", "WT", "WTT", "WTS", "PNB", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")}
    stock.update(STINT=start, ETINT=end, PNB=1, NBOU=None, ROS=None, ROST=None, WT=None, WTT=None, WTS=None)
    resource = {name: 0 for name in ("RID", "STID", "STINT", "ETINT", "NR", "NRMO", "NRMA", "NRUM", "NRLA", "NRW", "NRA", "NRN", "NRF", "NRRI", "NRRT", "NRRO")}
    qty = 2 if parent else 1
    resource.update(RID="Total over all Resources", STID="Total over all Stations", STINT=start, ETINT=end, NR=qty, NRA=qty, NRN=qty)
    if parent and index == 14:
        resource["NRUM"] = 2
    if not parent:
        assert cancel is not None
        resource["NRW"] = max(0, min(end, cancel) - max(start, 7)) / 0.5
    return system, stock, resource


def compare_table(a, table, expected, label, fractional_bounds=None):
    cols = [column["name"] for column in table["columns"]]
    actual_rows = rows(table)
    a.eq(len(actual_rows), len(expected), label + " row count")
    for index, (actual, values) in enumerate(zip(actual_rows, expected)):
        a.eq(set(actual), set(values), f"{label} row {index} columns")
        for field in cols:
            bound = (fractional_bounds or {}).get((index, field), 0)
            a.cell(actual[field], values[field], f"{label} row {index} {field}", bound)


def report_oracle(a, model, report, role, cancel=None, cancel_uncertainty=0):
    actual = table_map(report, "report")
    source = table_map(model, "model")
    a.eq(list(actual), list(TABLES), role + " six ordered tables")
    for name in TABLES:
        t = actual.get(name)
        a.yes(t is not None, role + " table " + name)
        if t is None:
            return
        a.eq(len(t["instances"]), 1, role + " " + name + " one instance")
        a.eq(t["instances"][0]["instance_name"], INSTANCE[name], role + " " + name + " instance metadata")
        a.eq((len(rows(t)), len(t["columns"])), SHAPE[name], role + " " + name + " shape")
    description = source["ProblemDescription"]["instances"][0]["rows"][0][0]
    compare_table(a, actual["ProblemDescription"], [{"PDESC": description}], role + " description")
    summary = {name: 0 for name in SUMMARY}
    summary.update(NREP=1, RTIUP=36)
    if role == "parent":
        summary.update(MTMF=1, MSTF=1, MSUF=1, STMF=1)
    compare_table(a, actual["ResultSummary"], [summary], role + " summary")
    sys_rows, stock_rows, resource_rows = [], [], []
    system_bounds, resource_bounds = {}, {}
    for index in range(72):
        s, st, r = expected_rows(role, index, cancel)
        sys_rows.append(s)
        stock_rows.append(st)
        resource_rows.append(r)
        if role == "child" and cancel is not None:
            start, end = index / 2, (index + 1) / 2
            fraction = max(0, min(end, cancel) - max(start, 7)) / 0.5
            if 0 < fraction < 1:
                bound = min(2.1e-5, cancel_uncertainty / 0.5 + 5e-7)
                for field in ("NSYRY", "NSYMA", "NSYMP"):
                    system_bounds[index, field] = bound
                resource_bounds[index, "NRW"] = bound
    compare_table(a, actual["SystemResults"], sys_rows, role + " System", system_bounds)
    compare_table(a, actual["StockTotalResults"], stock_rows, role + " Stock")
    compare_table(a, actual["ResourceResults"], resource_rows, role + " Resource", resource_bounds)
    qty = 2 if role == "parent" else 1
    total = {name: 0 for name in ("RID", "STID", "NR", "NRMO", "NRMA", "NRUM", "NRLA", "NRW", "NRA", "NRN", "NRF", "NRRI", "NRRT", "NRRO")}
    total.update(RID="Total over all Resources", STID="Total over all Stations", NR=qty, NRA=qty, NRN=qty)
    total["NRUM"] = 1 / 36 if role == "parent" else 0
    total["NRW"] = 0 if role == "parent" else (cancel - 7) / 36
    bound = {(0, "NRUM"): 5e-7} if role == "parent" else {(0, "NRW"): min(1e-6, cancel_uncertainty / 36 + 5e-7)}
    compare_table(a, actual["ResourceResultsTotal"], [total], role + " ResourceTotal", bound)
    a.eq(a.report_cells % 5210, 0, role + " 5210 cells completed")


def parent_run(a, contract):
    parent = contract["accepted_evidence"]["C02_parent"]
    spec = next(row for row in parent["accepted_runs"] if row["role"] == "single_both")
    run = Path(spec["local_run_dir"])
    a.eq(spec["run_id"], "c02-v102-single-both-ssh-20260929-02", "accepted control identity")
    for name, record in spec["raw"].items():
        sealed(a, run / name, record, "accepted control " + name)
    sealed(a, run / "closure.json", spec["closure"], "accepted control closure")
    sealed(a, run / "invocation.json", spec["invocation"], "accepted control invocation")
    source_record = contract["source_design"]["parent_input"]
    model_raw = sealed(a, ROOT / source_record["path"], source_record, "accepted control model")
    a.eq((run / "input.json").read_bytes(), model_raw, "run input equals published control")
    model = native_json(model_raw)
    roundtrip(a, model, native_json((run / "roundtrip-raw.json").read_bytes()), "accepted control")
    diagnostics(a, (run / "run.log").read_text(encoding="utf-8-sig"), "accepted control")
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    physical_parent(a, log)
    report = native_json((run / "report-raw.json").read_bytes())
    report_oracle(a, model, report, "parent")
    return model, report


def child_provenance(a, run, run_id, closure):
    """Reconcile frozen approval, invocation, stages and every sealed run byte."""
    manifest_path = PACKAGE / "prelaunch-manifest.json"
    approval_path = PACKAGE / "review/independent-prelaunch-go.json"
    a.yes(manifest_path.is_file(), "prelaunch manifest exists")
    a.yes(approval_path.is_file(), "independent prelaunch approval exists")
    if not manifest_path.is_file() or not approval_path.is_file():
        return
    manifest_raw, approval_raw = manifest_path.read_bytes(), approval_path.read_bytes()
    manifest, approval = json.loads(manifest_raw), json.loads(approval_raw)
    manifest_sha, approval_sha = digest(manifest_raw), digest(approval_raw)
    a.eq(manifest.get("schema"), "c02-var01-v101-prelaunch-manifest/v1", "manifest schema")
    a.eq(manifest.get("run_id"), run_id, "manifest run ID")
    a.eq(manifest.get("contract_sha256"), CONTRACT_SHA, "manifest contract SHA")
    entries = manifest.get("source_files", [])
    a.eq(len(entries), manifest.get("source_count"), "manifest source count")
    keys = [entry.get("key") for entry in entries]
    a.eq(len(keys), len(set(keys)), "manifest unique source keys")
    source_map = {entry["key"]: entry["sha256"] for entry in entries}
    for entry in entries:
        path = Path(entry["path"])
        historical = entry["key"] in ("catalog:publication_index_at_selection", "root_selection_original",
                                       "root_instructions_original")
        if historical:
            # Explicit historical copies permit replay after the shared catalog changes.
            archive_name = {"catalog:publication_index_at_selection": "publication-index-at-selection.json",
                            "root_selection_original": "c02-var01-owner-selection-20261007.json",
                            "root_instructions_original": "c02-var01-root-instructions-20261007.json"}[entry["key"]]
            archive = PACKAGE / "preserved-context" / archive_name
            sealed(a, archive, entry, "historical source " + entry["key"])
            if entry["key"] == "catalog:publication_index_at_selection":
                a.yes(path.is_file(), "current shared catalog exists")
            if entry["key"] == "catalog:publication_index_at_selection" and path.is_file():
                original = json.loads(archive.read_bytes())
                current = json.loads(path.read_bytes())
                a.eq({k: v for k, v in current.items() if k != "entries"},
                     {k: v for k, v in original.items() if k != "entries"},
                     "shared catalog metadata retained")
                a.eq(current.get("entries", [])[:len(original["entries"])], original["entries"],
                     "shared catalog prior entries retained")
        elif path.is_file():
            sealed(a, path, entry, "manifest source " + entry["key"])
        else:
            a.yes(False, "manifest source absent " + entry["key"])
    a.eq(approval.get("schema"), "c02-var01-v101-independent-prelaunch-go/v1", "approval schema")
    a.eq(approval.get("decision"), "GO_PRELAUNCH", "approval decision")
    a.eq(approval.get("run_id"), run_id, "approval run ID")
    for key, wanted in (("manifest_sha256", manifest_sha),
                        ("contract_sha256", CONTRACT_SHA),
                        ("runner_sha256", source_map.get("runner_script")),
                        ("validator_sha256", source_map.get("behavior_validator")),
                        ("input_sha256", source_map.get("child_input")),
                        ("independent_replay_sha256", digest(Path(__file__).read_bytes()))):
        a.eq(approval.get(key), wanted, "approval " + key)
    receipt_relative = approval.get("preflight_relative_path", "")
    a.yes(bool(re.fullmatch(r"review[/\\]preflight-ssh0-\d{8}T\d{9}Z\.json", receipt_relative)),
          "approved owned receipt path")
    receipt_path = PACKAGE / receipt_relative
    if receipt_path.is_file():
        receipt_raw = sealed(a, receipt_path, {"bytes": receipt_path.stat().st_size,
                                               "sha256": approval.get("preflight_sha256")},
                             "approved preflight receipt")
        receipt = json.loads(receipt_raw)
        a.eq(receipt.get("schema"), "c02-var01-v101-ssh-preflight/v1", "preflight schema")
        a.eq(receipt.get("run_id"), run_id, "preflight run ID")
        a.eq(receipt.get("manifest_sha256"), manifest_sha, "preflight manifest")
        a.eq(receipt.get("source_hashes"), source_map, "preflight complete source map")
        a.eq(receipt.get("source_map_sha256"), approval.get("source_map_sha256"), "preflight map seal")
        for key, wanted in (("ssh_session", 0), ("ps_major", 5), ("mutex_free", True),
                            ("run_dirs_absent", True), ("native_process_started", False),
                            ("wts_active_gui_count", 1), ("accepted_raw_seals", 55),
                            ("accepted_closures", 5), ("accepted_invocations", 5)):
            a.eq(receipt.get(key), wanted, "preflight " + key)
        a.yes("sshd.exe" in receipt.get("ssh_ancestors", []), "preflight sshd ancestor")
        a.eq(receipt.get("gui"), {"pid": 13340, "session_id": 1,
                                   "start_unix_ms": 1790590196826, "responding": True},
             "preflight protected GUI")
    else:
        a.yes(False, "approved preflight receipt exists")
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    a.eq(invocation.get("schema"), "c02-var01-v101-invocation/v1", "invocation schema")
    a.eq(invocation.get("run_id"), run_id, "invocation run ID")
    a.eq(invocation.get("original_run_dir"), str(run), "invocation run path")
    for key, wanted in (("input_sha256", source_map.get("child_input")),
                        ("contract_sha256", CONTRACT_SHA), ("manifest_sha256", manifest_sha),
                        ("approval_sha256", approval_sha),
                        ("approved_preflight_sha256", approval.get("preflight_sha256")),
                        ("independent_replay_sha256", approval.get("independent_replay_sha256")),
                        ("runner_script_sha256", source_map.get("runner_script")),
                        ("session_id", 0), ("source_hashes_before", source_map),
                        ("publication_state", "not_published")):
        a.eq(invocation.get(key), wanted, "invocation " + key)
    a.eq(invocation.get("approved_preflight_path"), str(receipt_path), "invocation preflight path")
    a.eq(invocation.get("queue_mutex"), "Global\\SimloxIssue18NativeQueue", "invocation mutex")
    a.yes("sshd.exe" in invocation.get("ssh_ancestors", []), "invocation sshd ancestor")
    a.eq(invocation.get("gui"), {"pid": 13340, "session_id": 1,
                                   "start_unix_ms": 1790590196826, "responding": True},
         "invocation protected GUI")
    names = ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    a.eq([s.get("name") for s in steps], names, "six ordered native/checker stages")
    for stage in steps:
        label = "stage " + stage.get("name", "unknown")
        a.eq(stage.get("status"), "completed", label + " status")
        a.eq(stage.get("exit_code"), 0, label + " actual OS exit")
        a.eq(stage.get("child_session_id"), 0, label + " session0")
        a.yes(type(stage.get("child_pid")) is int and stage["child_pid"] > 0, label + " PID")
        a.eq(stage.get("capture_error"), None, label + " capture error")
        a.eq(stage.get("gui_preserved"), True, label + " GUI")
        checker_stdout = {"check_import_export": "roundtrip-validation.json",
                          "check_behavior": "author-validation.json"}
        for stream in ("stdout", "stderr"):
            path = stage.get(stream + "_path")
            filename = (checker_stdout.get(stage["name"], stage["name"] + "-stdout.txt")
                        if stream == "stdout" else stage["name"] + "-stderr.txt")
            a.eq(path, str(run / filename), label + " " + stream + " path")
            a.yes((run / filename).is_file(), label + " " + stream + " exists")
    for name, filename, schema in (("check_import_export", "roundtrip-validation.json", "c02-var01-v101-roundtrip/v1"),
                                   ("check_behavior", "author-validation.json", "c02-var01-v101-behavior/v1")):
        result_path = run / filename
        if result_path.is_file():
            result = json.loads(result_path.read_text(encoding="utf-8-sig"))
            a.eq(result.get("schema"), schema, name + " checker schema")
            a.eq(result.get("passed"), True, name + " checker pass")
            a.eq(result.get("input_sha256"), source_map.get("child_input"), name + " input SHA")
            if name == "check_import_export":
                a.eq(result.get("authored_row_tables"), 20, "roundtrip table count")
                a.eq(result.get("issues"), [], "roundtrip issues empty")
                a.eq(result.get("export_sha256"), digest((run / "roundtrip-raw.json").read_bytes()),
                     "roundtrip export SHA")
            else:
                a.eq(result.get("run_id"), run_id, "behavior run ID")
                a.eq(result.get("report_cell_checks"), 10420, "behavior 10420 report cells")
                a.eq(result.get("parent", {}).get("cells"), 5210, "behavior parent cells")
                a.eq(result.get("child", {}).get("cells"), 5210, "behavior child cells")
    a.eq(closure.get("schema"), "c02-var01-v101-closure/v1", "closure schema")
    a.eq(closure.get("manifest_sha256"), manifest_sha, "closure manifest")
    a.eq(closure.get("approval_sha256"), approval_sha, "closure approval")
    a.eq(closure.get("approved_preflight_sha256"), approval.get("preflight_sha256"), "closure preflight")
    a.eq(closure.get("source_hashes_before"), source_map, "closure source map before")
    a.eq(closure.get("source_hashes_after"), source_map, "closure source map after")
    a.eq(closure.get("error"), "", "closure no error")
    a.eq(closure.get("publication_state"), "not_published", "closure prepublication state")
    actual_raw = {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json", "failure-seal.json"}
    a.eq(set(closure.get("raw", {})), actual_raw, "closure seals every raw file")
    a.yes(not (run / "failure-seal.json").exists(), "no failure seal on accepted run")


def child_run(a, contract, parent_model, parent_report):
    run_id = contract["ownership"]["sole_new_run_id"]
    run = PACKAGE / "runs" / run_id
    a.yes(run.is_dir(), "sealed child run directory")
    if not run.is_dir():
        return
    for name in ("input.json", "model.log", "report-raw.json", "roundtrip-raw.json", "closure.json", "invocation.json", "steps.json"):
        a.yes((run / name).is_file(), "child raw " + name)
    if a.failures:
        return
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8"))
    a.eq(closure.get("run_id"), run_id, "child closure run ID")
    raw = closure.get("raw", {})
    a.yes(len(raw) >= 11, "child raw seal count")
    for name, record in raw.items():
        sealed(a, run / name, record, "child sealed " + name)
    a.eq(digest((run / "invocation.json").read_bytes()), closure.get("invocation_sha256"), "child invocation seal")
    child_provenance(a, run, run_id, closure)
    child_raw = (run / "input.json").read_bytes()
    child_model = native_json(child_raw)
    source_isolation(a, parent_model, child_model, contract)
    package_input = PACKAGE / "native-input.json"
    a.yes(package_input.is_file(), "frozen child input exists")
    if package_input.is_file():
        a.eq(package_input.read_bytes(), child_raw, "run input exact frozen source")
    roundtrip(a, child_model, native_json((run / "roundtrip-raw.json").read_bytes()), "child")
    diagnostics(a, (run / "run.log").read_text(encoding="utf-8-sig"), "child")
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    cancel, uncertainty = physical_child(a, log)
    child_report = native_json((run / "report-raw.json").read_bytes())
    report_oracle(a, child_model, child_report, "child", cancel, uncertainty)
    left = rows(table_map(parent_report, "report")["StockTotalResults"])
    right = rows(table_map(child_report, "report")["StockTotalResults"])
    for i, (x, y) in enumerate(zip(left, right)):
        for field in x:
            a.eq(x[field], y[field], f"child Stock matched control row {i} {field}")


def self_check(a, contract, parent_model):
    """Synthetic role-swapped fixture is parser/accounting coverage, not native proof."""
    spec = next(r for r in contract["accepted_evidence"]["C02_parent"]["accepted_runs"] if r["role"] == "single_equipment_zero_control")
    run = Path(spec["local_run_dir"])
    source = copy.deepcopy(parent_model)
    tables = table_map(source, "model")
    names = [c["name"] for c in tables["ResourceAllocation"]["columns"]]
    for row_ in tables["ResourceAllocation"]["instances"][0]["rows"]:
        if row_[names.index("RID")] == "P-CREW":
            row_[names.index("RQTY")] = 0
        if row_[names.index("RID")] == "E-GSE":
            row_[names.index("RQTY")] = 1
    tables["ProblemDescription"]["instances"][0]["rows"][0][0] = contract["source_design"]["sole_child_delta"][1]["after"]
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    log = log.replace("<P-CREW at <BASE-01,0>> request for: 1 OK", "<P-CREW at <BASE-01,0>> request for: 1 failed")
    log = log.replace("<E-GSE at <BASE-01,0>> request for: 1 failed", "<E-GSE at <BASE-01,0>> request for: 1 OK")
    report = native_json((run / "report-raw.json").read_bytes())
    table_map(report, "report")["ProblemDescription"]["instances"][0]["rows"][0][0] = tables["ProblemDescription"]["instances"][0]["rows"][0][0]
    fixture = Audit()
    source_isolation(fixture, parent_model, source, contract)
    cancel, uncertainty = physical_child(fixture, log)
    report_oracle(fixture, source, report, "child", cancel, uncertainty)
    a.yes(not fixture.failures and fixture.report_cells == 5210, "synthetic role-swapped fixture 5210 cells")

    def reject(label, mutated_log=None, mutated_report=None, mutated_source=None):
        probe = Audit()
        if mutated_source is not None:
            source_isolation(probe, parent_model, mutated_source, contract)
        elif mutated_log is not None:
            physical_child(probe, mutated_log)
        else:
            report_oracle(probe, source, mutated_report, "child", cancel, uncertainty)
        a.yes(bool(probe.failures), "rejection: " + label)

    wrong = copy.deepcopy(source)
    table_map(wrong, "model")["Control"]["instances"][0]["rows"][0][0] = 2
    reject("third source cell", mutated_source=wrong)
    reject("extra booking", mutated_log=log + "\nTime: 7 <E-GSE at <BASE-01,0>> allocated to maintenance task: 1\n")
    reject("unexpected launch", mutated_log=log + "\nTime: 8 mission starting\n")
    reject("late cancellation", mutated_log=log.replace("Time: 7.58333", "Time: 8.5"))
    reject("missing cancellation", mutated_log=log.replace("mission cancelled:", "mission remains active:"))
    reject("reversed typed test order", mutated_log=log.replace("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed", "TMP").replace("Availability test on  <E-GSE at <BASE-01,0>> request for: 1 OK", "Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed").replace("TMP", "Availability test on  <E-GSE at <BASE-01,0>> request for: 1 OK"))

    def cell_mutation(name, row, field, value):
        clone = copy.deepcopy(report)
        t = table_map(clone, "report")[name]
        cols = [c["name"] for c in t["columns"]]
        t["instances"][0]["rows"][row][cols.index(field)] = value
        reject(name + " " + field, mutated_report=clone)

    cell_mutation("SystemResults", 0, "NSYMO", 1e-9)
    cell_mutation("SystemResults", 14, "NPSTA", False)
    cell_mutation("StockTotalResults", 0, "ROS", 0)
    cell_mutation("ResourceResults", 15, "NRW", 0.1668)
    cell_mutation("ResourceResultsTotal", 0, "NRW", 0.01622)
    cell_mutation("ResultSummary", 0, "NREP", 2)
    cell_mutation("SystemResults", 71, "NSYRY", 0)
    boundary_log = log.replace("Time: 7.58333", "Time: 7.50000")
    boundary_cancel, boundary_uncertainty = physical_child(Audit(), boundary_log)
    a.eq(boundary_cancel, 7.5, "synthetic boundary cancellation value")
    a.eq(boundary_uncertainty, 0.000005, "synthetic boundary retains printed precision")
    boundary = copy.deepcopy(report)
    for name, updates in (
        ("SystemResults", {"NSYRY": 1, "NSYMA": 0, "NSYMP": 0}),
        ("ResourceResults", {"NRW": 0}),
    ):
        t = table_map(boundary, "report")[name]
        cols = [c["name"] for c in t["columns"]]
        for field, value in updates.items():
            t["instances"][0]["rows"][15][cols.index(field)] = value
    total = table_map(boundary, "report")["ResourceResultsTotal"]
    total_cols = [c["name"] for c in total["columns"]]
    total["instances"][0]["rows"][0][total_cols.index("NRW")] = 0.5 / 36
    boundary_audit = Audit()
    report_oracle(boundary_audit, source, boundary, "child", boundary_cancel, boundary_uncertainty)
    a.yes(not boundary_audit.failures and boundary_audit.report_cells == 5210, "synthetic exact 7.50000 boundary ledger")
    system = table_map(boundary, "report")["SystemResults"]
    cols = [c["name"] for c in system["columns"]]
    for field, value in (("NSYMP", 1e-9), ("NSYRY", 1 - 1e-9)):
        mutation = copy.deepcopy(boundary)
        table_map(mutation, "report")["SystemResults"]["instances"][0]["rows"][15][cols.index(field)] = value
        check = Audit()
        report_oracle(check, source, mutation, "child", boundary_cancel, boundary_uncertainty)
        a.yes(bool(check.failures), "synthetic boundary exact-field rejection " + field)
    a.eq(a.report_cells, 5210, "fixture checks separate from accepted evidence cell count")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-only", action="store_true", help="Audit accepted control while child is absent")
    parser.add_argument("--self-check", action="store_true", help="Exercise synthetic child parser and rejection probes")
    args = parser.parse_args()
    a = Audit()
    contract_raw = (PACKAGE / "contract.json").read_bytes()
    a.eq(digest(contract_raw), CONTRACT_SHA, "frozen contract")
    contract = json.loads(contract_raw)
    published_sources(a, contract)
    parent_model, parent_report = parent_run(a, contract)
    if args.self_check:
        self_check(a, contract, parent_model)
    elif not args.control_only:
        child_run(a, contract, parent_model, parent_report)
    result = {"decision": "GO_BOUNDED" if not a.failures and not (args.control_only or args.self_check) else "STATIC_ONLY" if not a.failures else "NO_GO", "checks": a.checks, "report_cells": a.report_cells, "failures": a.failures[:30]}
    print(json.dumps(result, sort_keys=True))
    return 0 if not a.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

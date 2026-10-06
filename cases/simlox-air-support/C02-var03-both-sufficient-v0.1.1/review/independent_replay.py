"""Independent, read-only C02.var03 replay of the four accepted final runs."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parents[2]
ACCEPTED = ROOT / "cases/simlox-air-support/C02-joint-resources-v1.0.2"
CONTRACT_SHA = "97bf1d7392aa8b3b5c626b737193fec42485e31604f791614bd22b6d8e904a9d"
OLD_NO_GO_SHA = "381d65f09678f26177efb8fa5417014dbda18fca2865d3cf17433c24a3b7ceec"
ROLES = {
    "single_both": "single-both",
    "serial_both": "serial-both",
    "single_equipment_zero_control": "single-equipment-zero",
    "serial_equipment_zero_control": "serial-equipment-zero",
}


class Audit:
    def __init__(self) -> None:
        self.checks = 0
        self.failures: list[str] = []

    def equal(self, actual: object, expected: object, label: str) -> None:
        self.checks += 1
        if actual != expected:
            self.failures.append(f"{label}: {actual!r} != {expected!r}")

    def true(self, condition: bool, label: str) -> None:
        self.equal(bool(condition), True, label)

    def near(self, actual: object, expected: float, label: str, tolerance: float = 1e-6) -> None:
        self.true(isinstance(actual, (int, float)) and abs(actual - expected) <= tolerance, label)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"origin/simlox/main:{path}"], cwd=ROOT)


def data_json(raw: bytes) -> dict:
    text = raw.decode("utf-8-sig")
    # Native exports contain trailing commas. Normalize only the parser copy.
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text))


def tables(doc: dict, root: str) -> dict[str, dict]:
    return {table["name"]: table for table in doc[root]["tables"]}


def cell_map(doc: dict) -> dict[tuple[str, int, int, str], object]:
    out = {}
    for name, table in tables(doc, "model").items():
        cols = [c["name"] for c in table["columns"]]
        for ii, inst in enumerate(table["instances"]):
            for ri, row in enumerate(inst["rows"]):
                for ci, value in enumerate(row):
                    out[name, ii, ri, cols[ci]] = value
    return out


def report_cells(doc: dict) -> dict[tuple[str, int, int, str], object]:
    out = {}
    for name, table in tables(doc, "report").items():
        cols = [c["name"] for c in table["columns"]]
        for ii, inst in enumerate(table["instances"]):
            for ri, row in enumerate(inst["rows"]):
                for ci, value in enumerate(row):
                    out[name, ii, ri, cols[ci]] = value
    return out


def seal(a: Audit, path: Path, record: dict, label: str) -> None:
    a.true(path.is_file(), f"{label} exists")
    if path.is_file():
        b = path.read_bytes()
        a.equal(len(b), record["bytes"], f"{label} bytes")
        a.equal(sha(b), record["sha256"], f"{label} SHA")


def ordered(a: Audit, log: str, fragments: list[str], label: str) -> None:
    pos = -1
    for frag in fragments:
        next_pos = log.find(frag, pos + 1)
        a.true(next_pos > pos, f"{label} ordered {frag}")
        if next_pos > pos:
            pos = next_pos


def main() -> int:
    a = Audit()
    contract_file = CASE / "contract.json"
    a.equal(sha(contract_file.read_bytes()), CONTRACT_SHA, "corrected contract SHA")
    contract = json.loads(contract_file.read_bytes())
    old_case = CASE.parent / "C02-var03-both-sufficient-v0.1.0"
    a.equal(
        sha((old_case / "review/independent-contract-2026-10-07.md").read_bytes()),
        OLD_NO_GO_SHA,
        "excluded old NO_GO memo",
    )
    a.equal(contract["variant_id"], "C02.var03", "variant")
    a.equal(contract["publication_state"], "not_published", "publication state")
    source = contract["accepted_source"]
    for field, relative in (
        ("contract_sha256", "contract.json"),
        ("original_independent_report_sha256", "review/independent-readonly-2026-09-29.json"),
        ("evidence_report_sha256", "evidence-2026-09-29.md"),
    ):
        a.equal(sha((ACCEPTED / relative).read_bytes()), source[field], f"accepted {relative}")
    a.equal(
        sha(Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf").read_bytes()),
        contract["manual"]["installed_pdf_sha256"],
        "installed manual",
    )

    published = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", "origin/simlox/main", "cases/simlox-air-support/C02-joint-resources-v1.0.2/"],
        cwd=ROOT, text=True,
    ).splitlines()
    a.equal(len(published), 18, "accepted published file count")
    exception = source["published_local_byte_exception"]
    for relative in published:
        local = (ROOT / relative).read_bytes()
        remote = git_blob(relative)
        if relative.endswith("/.gitignore"):
            a.equal(len(local), exception["local_crlf_bytes"], "local .gitignore bytes")
            a.equal(sha(local), exception["local_sha256"], "local .gitignore SHA")
            a.equal(len(remote), exception["published_git_lf_bytes"], "published .gitignore bytes")
            a.equal(sha(remote), exception["published_git_sha256"], "published .gitignore SHA")
        else:
            a.equal(local, remote, f"accepted disk/Git {relative}")

    models: dict[str, dict] = {}
    reports: dict[str, dict] = {}
    raw_reports: dict[str, bytes] = {}
    raw_logs: dict[str, bytes] = {}
    run_seals = 0
    for role, variant in ROLES.items():
        spec = source["arms"][role]
        a.equal(Path(spec["input"]).stem, variant, f"{role} input identity")
        input_bytes = (ACCEPTED / spec["input"]).read_bytes()
        a.equal(sha(input_bytes), spec["input_sha256"], f"{role} input SHA")
        models[role] = data_json(input_bytes)
        run = Path(source["raw_location"]) / spec["run_id"]
        closure_bytes = (run / "closure.json").read_bytes()
        a.equal(sha(closure_bytes), spec["closure_sha256"], f"{role} closure SHA")
        closure = json.loads(closure_bytes)
        a.equal(closure["run_id"], spec["run_id"], f"{role} closure run ID")
        a.equal(closure["input_sha256"], spec["input_sha256"], f"{role} closure input")
        a.equal(sha((run / "invocation.json").read_bytes()), closure["invocation_sha256"], f"{role} invocation")
        a.equal(len(closure["raw"]), 11, f"{role} raw count")
        run_seals += len(closure["raw"])
        for name, record in closure["raw"].items():
            seal(a, run / name, record, f"{role} {name}")
        a.equal((run / "input.json").read_bytes(), input_bytes, f"{role} run input copy")

        roundtrip = data_json((run / "roundtrip-raw.json").read_bytes())
        authored = tables(models[role], "model")
        exported = tables(roundtrip, "model")
        a.equal(set(exported), set(authored), f"{role} roundtrip tables")
        row_containing = 0
        for name, orig in authored.items():
            actual = exported[name]
            expected_columns = [(c["name"], c["datatype"]) for c in orig["columns"]]
            actual_columns = [(c["name"], c["datatype"]) for c in actual["columns"]]
            a.equal(actual_columns, expected_columns, f"{role} {name} columns")
            a.equal(len(actual["instances"]), len(orig["instances"]), f"{role} {name} instances")
            for ii, (left, right) in enumerate(zip(orig["instances"], actual["instances"])):
                if left["rows"]:
                    row_containing += 1
                    a.equal(right["instance_name"], left["instance_name"], f"{role} {name}/{ii} instance")
                    a.equal(right["rows"][:len(left["rows"])], left["rows"], f"{role} {name}/{ii} rows")
                    for extra in right["rows"][len(left["rows"]):]:
                        a.true(all(v is None for v in extra), f"{role} {name}/{ii} only null extra")
                else:
                    for extra in right["rows"]:
                        a.true(all(v is None for v in extra), f"{role} {name}/{ii} null placeholder")
        a.equal(row_containing, 20, f"{role} row-containing authored tables")

        raw_reports[role] = (run / "report-raw.json").read_bytes()
        raw_logs[role] = (run / "model.log").read_bytes()
        reports[role] = data_json(raw_reports[role])
        rts = tables(reports[role], "report")
        a.equal(set(rts), {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"}, f"{role} six report tables")
        for name, length in (("ProblemDescription", 1), ("ResultSummary", 1), ("SystemResults", 72), ("StockTotalResults", 72), ("ResourceResults", 72), ("ResourceResultsTotal", 1)):
            a.equal(sum(len(i["rows"]) for i in rts[name]["instances"]), length, f"{role} {name} rows")
        a.equal(
            rts["ProblemDescription"]["instances"][0]["rows"],
            authored["ProblemDescription"]["instances"][0]["rows"],
            f"{role} report description matches source",
        )
        cells = report_cells(reports[role])
        a.equal(len(cells), 5210, f"{role} report cell count")
        for key, value in cells.items():
            a.true(value is None or isinstance(value, (str, int, float, bool)), f"{role} report cell {key}")
        for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
            t = rts[name]
            cols = [c["name"] for c in t["columns"]]
            si, ei = cols.index("STINT"), cols.index("ETINT")
            for n, row in enumerate(t["instances"][0]["rows"]):
                a.equal(row[si], n / 2, f"{role} {name} bin {n} start")
                a.equal(row[ei], (n + 1) / 2, f"{role} {name} bin {n} end")

        # Construct the complete row ledgers from event times and fixed source
        # quantities, rather than accepting the native report as its own oracle.
        available = role in ("single_both", "serial_both")
        quantities = 2 if available else 1
        summary = rts["ResultSummary"]
        summary_values = dict(zip((c["name"] for c in summary["columns"]), summary["instances"][0]["rows"][0]))
        for name, value in {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": int(available), "MSTF": int(available), "MSUF": int(available), "STMF": int(available)}.items():
            a.equal(summary_values[name], value, f"{role} summary {name}")
        for name in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF"):
            a.equal(summary_values[name], 0, f"{role} summary {name}")
        for n in range(72):
            start, end = n / 2, (n + 1) / 2
            system = {c["name"]: 0 for c in rts["SystemResults"]["columns"]}
            system.update(UNID="Total over all Units", SID="Total over all Systems", STINT=start, ETINT=end, NSYRY=1, NSYA=1, SYDT=None)
            if n == 14:
                system.update(NSYRY=0, NSYMA=1, NSYMP=1, NPSTA=1)
            elif available and n == 15:
                system.update(NSYRY=0, NSYMA=1, NSYMR=1, NPSUC=1)
            elif available and 16 <= n <= 19:
                system.update(NSYRY=0, NSYMA=1, NSYMO=1, FTMO=1, STACC=1)
            elif not available and n == 15:
                system.update(NSYRY=5 / 6, NSYMA=1 / 6, NSYMP=1 / 6)
            actual_system = dict(zip((c["name"] for c in rts["SystemResults"]["columns"]), rts["SystemResults"]["instances"][0]["rows"][n]))
            for field, expected in system.items():
                actual = actual_system[field]
                if isinstance(expected, float):
                    a.near(actual, expected, f"{role} System bin {n} {field}")
                else:
                    a.equal(actual, expected, f"{role} System bin {n} {field}")

            stock = {c["name"]: 0 for c in rts["StockTotalResults"]["columns"]}
            stock.update(STINT=start, ETINT=end, PNB=1)
            stock.update({name: None for name in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS")})
            actual_stock = dict(zip((c["name"] for c in rts["StockTotalResults"]["columns"]), rts["StockTotalResults"]["instances"][0]["rows"][n]))
            for field, expected in stock.items():
                a.equal(actual_stock[field], expected, f"{role} Stock bin {n} {field}")

            resource = {c["name"]: 0 for c in rts["ResourceResults"]["columns"]}
            resource.update(RID="Total over all Resources", STID="Total over all Stations", STINT=start, ETINT=end, NR=quantities, NRA=quantities, NRN=quantities)
            if available and n == 14:
                resource["NRUM"] = 2 if role == "single_both" else 2 / 3
            if not available and n == 14:
                resource["NRW"] = 1
            if not available and n == 15:
                resource["NRW"] = 1 / 6
            actual_resource = dict(zip((c["name"] for c in rts["ResourceResults"]["columns"]), rts["ResourceResults"]["instances"][0]["rows"][n]))
            for field, expected in resource.items():
                actual = actual_resource[field]
                if isinstance(expected, float):
                    a.near(actual, expected, f"{role} Resource bin {n} {field}")
                else:
                    a.equal(actual, expected, f"{role} Resource bin {n} {field}")
        total = rts["ResourceResultsTotal"]
        total_values = dict(zip((c["name"] for c in total["columns"]), total["instances"][0]["rows"][0]))
        a.equal(total_values["RID"], "Total over all Resources", f"{role} ResourceTotal RID")
        a.equal(total_values["STID"], "Total over all Stations", f"{role} ResourceTotal STID")
        for field in ("NR", "NRA", "NRN"):
            a.equal(total_values[field], quantities, f"{role} ResourceTotal {field}")
        expected_usage = 1 / 36 if role == "single_both" else 1 / 108 if role == "serial_both" else 0
        expected_wait = 0 if available else (7 / 12) / 36
        a.near(total_values["NRUM"], expected_usage, f"{role} ResourceTotal NRUM")
        a.near(total_values["NRW"], expected_wait, f"{role} ResourceTotal NRW")
        for field in set(total_values) - {"RID", "STID", "NR", "NRA", "NRN", "NRUM", "NRW"}:
            a.equal(total_values[field], 0, f"{role} ResourceTotal {field}")

    a.equal(run_seals, 44, "four run raw seals")
    maps = {role: cell_map(doc) for role, doc in models.items()}
    for good, zero in (("single_both", "single_equipment_zero_control"), ("serial_both", "serial_equipment_zero_control")):
        g, z = maps[good], maps[zero]
        a.equal(set(g), set(z), f"{good} versus zero source keys")
        changes = [(key, g[key], z[key]) for key in g if g[key] != z[key]]
        a.equal(changes, [(("ResourceAllocation", 0, 2, "RQTY"), 1, 0)], f"{good} one capacity cell")
    single, serial = maps["single_both"], maps["serial_both"]
    only_serial = set(serial) - set(single)
    only_single = set(single) - set(serial)
    changed_common = [(key, single[key], serial[key]) for key in single.keys() & serial.keys() if single[key] != serial[key]]
    a.equal(only_single, set(), "single-only source cells")
    a.true(all(key[0] == "TaskBreakDown" and key[2] == 1 for key in only_serial), "serial adds only SERVICE row")
    a.equal(len(only_serial), len(tables(models["serial_both"], "model")["TaskBreakDown"]["columns"]), "serial SERVICE cell count")
    a.equal(changed_common, [(("TaskBreakDown", 0, 0, "DURN"), 0.5, 1 / 6)], "only common topology duration change")
    a.equal(single[("ResourceAllocation", 0, 0, "RQTY")], 1, "crew capacity one")
    a.equal(serial[("ResourceAllocation", 0, 0, "RQTY")], 1, "serial crew capacity one")

    # Compare every available-arm report cell; exactly two NRUM cells may differ.
    sc, rc = report_cells(reports["single_both"]), report_cells(reports["serial_both"])
    a.equal(set(sc), set(rc), "available report cell keys")
    differences = {}
    for key in sc:
        a.checks += 1
        if sc[key] != rc[key]:
            differences[key] = (sc[key], rc[key])
    a.equal(set(differences), {("ResourceResults", 0, 14, "NRUM"), ("ResourceResultsTotal", 0, 0, "NRUM")}, "only two NRUM report differences")
    for key, expected in {
        ("ResourceResults", 0, 14, "NRUM"): (2, 2 / 3),
        ("ResourceResultsTotal", 0, 0, "NRUM"): (1 / 36, 1 / 108),
    }.items():
        value = differences.get(key)
        a.true(value is not None and all(abs(float(v) - e) < 1e-6 for v, e in zip(value, expected)), f"{key} expected numeric pair")
    a.equal(raw_logs["single_equipment_zero_control"], raw_logs["serial_equipment_zero_control"], "zero-control log bytes")
    a.equal(raw_reports["single_equipment_zero_control"], raw_reports["serial_equipment_zero_control"], "zero-control report bytes")
    for key, value in report_cells(reports["single_equipment_zero_control"]).items():
        a.equal(value, report_cells(reports["serial_equipment_zero_control"])[key], f"zero report {key}")

    for role, finish in (("single_both", "7.5"), ("serial_both", "7.16667")):
        log = raw_logs[role].decode("utf-8-sig")
        ordered(a, log, [
            "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>",
            "Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK",
            "Availability test on  <E-GSE at <BASE-01,0>> request for: 1 OK",
            "<P-CREW at <BASE-01,0>> allocated to maintenance task: 1",
            "<E-GSE at <BASE-01,0>> allocated to maintenance task: 1",
            "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing",
            f"Time: {finish}  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed",
            f"Time: {finish}  <P-CREW at <BASE-01,0>> deallocated",
            f"Time: {finish}  <E-GSE at <BASE-01,0>> deallocated",
            "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting",
            "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success",
            "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed: <TEACH-AIR-01,0>",
            "System ready <TEACH-AIR-01,0>",
        ], role)
        a.true("mission cancelled" not in log, f"{role} no cancellation")
        a.equal(log.count("allocated to maintenance task: 1"), 2, f"{role} exactly two resource allocations")
        if role == "serial_both":
            ordered(a, log, ["Time: 7.16667  <E-GSE at <BASE-01,0>> deallocated", "subtask 1 seqno 2", "requests resources: no resources needed", "Time: 7.5  subtask 1 seqno 2", "Time: 8 <BASIC-MISSION"], "serial unresourced SERVICE")
    for role in ("single_equipment_zero_control", "serial_equipment_zero_control"):
        log = raw_logs[role].decode("utf-8-sig")
        ordered(a, log, [
            "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>",
            "Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK",
            "Availability test on  <E-GSE at <BASE-01,0>> request for: 1 failed",
            "Time: 7.58333 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled",
            "Time: 7.58333 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>",
            "System ready <TEACH-AIR-01,0>",
        ], role)
        a.true("allocated to maintenance task: 1" not in log, f"{role} no partial lease")
        a.true("starts performing" not in log, f"{role} no work")
        a.true("mission starting" not in log, f"{role} no launch")

    verdict = {
        "schema": "simlox-c02-var03-independent-readonly-replay/v1",
        "decision": "GO_BOUNDED" if not a.failures else "NO_GO",
        "checks_passed": a.checks - len(a.failures),
        "checks_total": a.checks,
        "failures": a.failures,
        "contract_sha256": CONTRACT_SHA,
        "run_ids": {role: source["arms"][role]["run_id"] for role in ROLES},
        "raw_seals": run_seals,
        "report_cells_each": 5210,
        "scope": "Four accepted fixed-seed C02 final runs; available single versus serial topology with matched equipment-zero controls.",
        "limits": "No new native run, isolated single-cell topology effect, general resource release/acquisition or deadline rule, GUI visual, or cross-engine claim.",
    }
    out = CASE / "review/independent-verdict.json"
    out.write_bytes((json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"decision": verdict["decision"], "checks": a.checks, "failures": a.failures[:12]}, indent=2))
    return 0 if not a.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

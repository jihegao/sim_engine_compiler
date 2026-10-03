"""Independent read-only standard-library replay of E12's sealed two-base run."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "E07-item-specific-transport-v1.0.1"
RUN = CASE / "runs" / "e12-symmetric-two-bases-v100-ssh-20261003-01"
PRUN = PARENT / "runs" / "e07-item-route-v101-20261001-01"
OUT = Path(__file__).with_name("independent-verdict.json")


class Audit:
    def __init__(self) -> None:
        self.passed = 0
        self.failures: list[str] = []

    def check(self, value: bool, label: str) -> None:
        if value:
            self.passed += 1
        else:
            self.failures.append(label)

    def eq(self, actual: object, expected: object, label: str) -> None:
        self.check(actual == expected, f"{label}: expected {expected!r}, got {actual!r}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native_report: bool = False) -> dict | list:
    data = path.read_text(encoding="utf-8-sig")
    if native_report:
        data = re.sub(r",\s*([}\]])", r"\1", data)
    return json.loads(data)


def table_map(path: Path, root: str = "model") -> dict[str, dict]:
    return {t["name"]: t for t in load(path, root == "report")[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance.get("rows", [])]


def records(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]


def event(a: Audit, log: str, hour: str, phrase: str) -> None:
    a.check(any(line.startswith(f"Time: {hour} ") and phrase in line for line in log.splitlines()), f"h{hour}: {phrase}")


def expected_system_row(i: int, names: list[str]) -> dict:
    expected = {name: 0 for name in names}
    expected.update(UNID="Total over all Units", SID="Total over all Systems", STINT=i / 2, ETINT=(i + 1) / 2, NSYA=2, NSYRY=2, SYDT=None)
    if i in range(14, 20) or i in range(38, 44) or i in range(62, 68):
        expected.update(NSYRY=0, NSYMA=2)
        if i in (14, 15, 38, 39, 62, 63):
            expected["NSYMR"] = 2
        else:
            expected.update(NSYMO=2, FTMO=1, STACC=2)
    if i == 19:
        expected["NFAIL"] = 1
    if i == 20:
        expected.update(NSYRY=1, NSYUA=1, NSYA=1, NSYRP=1, NSYDT=1, SYDT=0.5)
    if i == 21:
        expected["NREPT"] = 1
    return expected


def expected_stock_row(i: int, names: list[str]) -> dict:
    expected = {name: 0 for name in names}
    expected.update(STINT=i / 2, ETINT=(i + 1) / 2, NBOU=None, ROS=None, ROST=None, WT=None, WTT=None, WTS=None, PNB=1)
    if i == 20:
        expected.update(ROS=0, ROST=0, WT=0, WTT=0, NDF=1, NWT=1)
    return expected


def main() -> dict:
    a = Audit()
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    inv = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    steps = load(RUN / "steps.json")
    source = table_map(CASE / "native-input.json")
    parent = table_map(PARENT / "native-input.json")
    exported = table_map(RUN / "roundtrip-raw.json")
    result = table_map(RUN / "report-raw.json", "report")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")

    a.eq(contract["case_id"], "E12", "contract identity")
    a.eq(sha(CASE / "native-input.json"), contract["native_input_sha256"], "input pin")
    a.eq(sha(CASE / "exact-diff.json"), contract["exact_diff_sha256"], "diff pin")
    a.eq(sha(PARENT / "native-input.json"), contract["accepted_parent"]["input_sha256"], "E07 parent input pin")
    a.eq(sha(PRUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"], "E07 parent closure pin")
    a.eq(sha(PARENT / "evidence-index.json"), contract["accepted_parent"]["evidence_index_sha256"], "E07 parent index pin")
    installed = {
        "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    }
    for key, path in installed.items():
        pin = "simlox_exe_sha256" if key == "simlox_exe" else "manual_pdf_sha256" if key == "manual" else "dictionary_sha256"
        a.eq(sha(path), contract["source"][pin], f"installed {key} pin")
    a.eq(diff["parent_sha256"], sha(PARENT / "native-input.json"), "diff parent pin")
    a.eq(diff["source_sha256"], sha(CASE / "native-input.json"), "diff child pin")
    a.eq(diff["changed_tables"], ["ProblemDescription", "Station", "StockAllocation"], "declared changed tables")
    a.eq(set(source), set(parent), "same source table set")
    a.eq(len(source), 32, "32 source tables")
    a.eq([name for name in sorted(source) if source[name] != parent[name]], ["ProblemDescription", "Station", "StockAllocation"], "actual changed tables")
    for name in sorted(source):
        a.eq(source[name]["columns"], parent[name]["columns"], f"schema {name}")
        if name not in {"ProblemDescription", "Station", "StockAllocation"}:
            a.eq(source[name], parent[name], f"unchanged parent table {name}")
    a.eq(len(diff["changes"]), 3, "three changed cells")
    for item in diff["changes"]:
        name = item["table"]
        old = rows(parent[name]); new = rows(source[name])
        column = next(i for i, c in enumerate(source[name]["columns"]) if c["name"] == item["column"])
        a.eq(old[item["row"]][column], item["before"], f"parent {name}.{item['column']}")
        a.eq(new[item["row"]][column], item["after"], f"child {name}.{item['column']}")
        changes = [(i, j) for i, (x, y) in enumerate(zip(old, new)) for j, (v, w) in enumerate(zip(x, y)) if v != w]
        a.eq(changes, [(item["row"], column)], f"sole changed cell in {name}")
    a.eq(records(source["Station"])[0]["QTY"], 2, "symmetric BASE quantity two")
    a.eq(records(source["StockAllocation"])[0]["STSIZ"], 1, "one local spare per BASE source")
    a.eq(source["ItemStationStructure"], parent["ItemStationStructure"], "FAST item route unchanged")
    a.eq(source["Operations"], parent["Operations"], "mission schedule unchanged")

    a.eq(inv["run_id"], RUN.name, "run identity")
    a.eq(inv["input_sha256"], sha(CASE / "native-input.json"), "invocation input")
    a.eq(inv["execution_mode"], "ssh_cli_v1", "SSH mode")
    a.eq(inv["session_id"], 0, "session zero")
    a.check(inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"], "SSH ancestry")
    a.eq(inv["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "queue mutex")
    a.eq(inv["gui"]["pid"], 13340, "GUI PID")
    a.eq(inv["gui"]["session_id"], 1, "GUI session")
    a.eq(closure["invocation_sha256"], sha(RUN / "invocation.json"), "invocation seal")
    a.eq(closure["source_hashes_before"], closure["source_hashes_after"], "source stability")
    a.eq(closure["source_hashes_before"], inv["source_hashes_before"], "invocation source agreement")
    source_paths = {
        "input": CASE / "native-input.json", "parent": PARENT / "native-input.json",
        "parent_closure": PRUN / "closure.json", "parent_index": PARENT / "evidence-index.json",
        "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
        "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
        "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        **installed,
    }
    for key, path in sorted(source_paths.items()):
        a.eq(closure["source_hashes_before"][key], sha(path), f"frozen source {key}")
    a.eq(len(closure["raw"]), 12, "12 raw seals")
    for name, meta in sorted(closure["raw"].items()):
        path = RUN / name
        a.check(path.is_file(), f"raw exists {name}")
        if path.is_file():
            a.eq(path.stat().st_size, meta["bytes"], f"raw size {name}")
            a.eq(sha(path), meta["sha256"], f"raw SHA {name}")
    a.eq(sha(RUN / "input.json"), sha(CASE / "native-input.json"), "run input copy")
    a.eq([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "five steps")
    for step in steps:
        a.eq(step["exit_code"], 0, f"{step['name']} exit")
        a.eq(step["status"], "completed", f"{step['name']} status")
        a.check(step["gui_preserved"] is True, f"{step['name']} GUI preserved")
        a.eq(step["error"], None, f"{step['name']} error")
    authored = [name for name, table in source.items() if rows(table)]
    a.eq(len(authored), 22, "22 authored row-containing tables")
    a.eq(set(exported), set(source), "native export table set")
    for name in sorted(authored):
        a.eq(exported[name], source[name], f"exact roundtrip {name}")
    a.check((RUN / "model.sxo").stat().st_size > 4, "valid nontrivial SXO")
    a.eq(re.findall(r"\(error #(\d+)\)", converter), [], "zero converter errors")
    a.eq(re.findall(r"\(warning #(\d+)\)", converter), ["108"], "only warning #108")
    a.check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter, "converter counts")

    a.check("Time: 0 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>" in log, "base0 unique unit/aircraft")
    a.check("Time: 0 <TEACH-UNIT at <BASE-01,1>> systems ready: 1 :<TEACH-AIR-01,1>" in log, "base1 unique unit/aircraft")
    for base, item in ((0, 1), (1, 2)):
        a.check(f"Time: 0 <TEACH-LRU-01,0,BASE-01,{base}> Stock initiated \n  Stock at: <TEACH-LRU-01,0,BASE-01,{base}> Level: 1 Items:<TEACH-LRU-01,0,{item}>" in log.replace("\r\n", "\n"), f"base{base} opening physical spare ID{item}")
    a.check("Time: 0 <TEACH-LRU-01,0,DEPOT-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log.replace("\r\n", "\n"), "depot opening physical spare ID0")
    for mid, base, aircraft, order, start, finish in [(0, 0, 0, 7, 8, 10), (1, 1, 1, 7, 8, 10), (2, 0, 0, 19, 20, 22), (3, 1, 1, 19, 20, 22), (4, 0, 0, 31, 32, 34), (5, 1, 1, 31, 32, 34)]:
        ident = f"<BASIC-MISSION,TEACH-UNIT,{base},0,{mid}>"
        event(a, log, str(order), f"{ident} mission created:")
        event(a, log, str(order), f"{ident} mission allocates system: <TEACH-AIR-01,{aircraft}>")
        event(a, log, str(start), f"{ident} mission starting, duration: 2 : <TEACH-AIR-01,{aircraft}>")
        event(a, log, str(finish), f"{ident} {'aborted mission completed:' if mid == 0 else 'mission completed:'}")
        if mid != 0:
            event(a, log, str(finish), f"{ident} mission success:")
    a.eq(len(re.findall(r"mission created:", log)), 6, "six mission opportunities")
    a.eq(len(re.findall(r"mission starting, duration:", log)), 6, "six mission starts")
    a.eq(len(re.findall(r"mission aborted:", log)), 1, "one base0 first-wave abort")
    a.eq(len(re.findall(r"mission success:", log)), 5, "five mission successes")
    a.eq(len(re.findall(r"mission cancelled:", log)), 0, "no mission cancellations")
    for hour, phrase in [
        ("9.8829", "<TEACH-AIR-01,0> critical random failure added"),
        ("10", "<TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,1> from stock"),
        ("10", "<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock"),
        ("10.5", "<TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>"),
        ("11", "<TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>"),
        ("11", "<TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,0> to stock"),
        ("13.1667", "<TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,3>"),
        ("14.1667", "<TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,3>"),
        ("14.1667", "<TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,3> to stock"),
    ]:
        event(a, log, hour, phrase)
    a.check("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,3>" in log, "base0 failed installed ID3")
    a.eq(len(re.findall(r"<TEACH-LRU-01,0,BASE-01,1> Take replacement item", log)), 0, "base1 physical spare ID2 untouched")
    a.eq(len(re.findall(r"Backorder added", log)), 0, "no physical backorder")
    a.check("Time: 10  transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started" in log, "depot ID0 travels only to base0")
    a.check("Time: 10.1667  transport request <<TEACH-LRU-01,0,3>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started" in log, "failed ID3 travels only from base0")
    a.eq(len(re.findall(r"transport request .*BASE-01,1", log)), 0, "base1 has no physical transport request")
    a.eq(len(re.findall(r"books resources|frees resources", log)), 0, "no resource bookings")
    for base in (0, 1):
        a.check(f"Time: 34 <TEACH-UNIT at <BASE-01,{base}>> systems ready: 1 :<TEACH-AIR-01,{base}>" in log, f"base{base} terminal aircraft ready")
    a.check("Time: 11 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,0> to stock \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log.replace("\r\n", "\n"), "base0 terminal stock restored ID0")
    a.check("Time: 14.1667 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,3> to stock \n  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,3>" in log.replace("\r\n", "\n"), "depot terminal stock ID3")

    a.eq(set(result), {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table set")
    summary = records(result["ResultSummary"])[0]
    a.eq((summary["NREP"], summary["MTMF"], summary["MSTF"], summary["MSUF"], summary["STMF"]), (1, 1, 1, 0.8333333134651184, 1), "six-mission summary factors")
    system = records(result["SystemResults"])
    stock = records(result["StockTotalResults"])
    a.eq(len(system), 72, "72 system bins")
    a.eq(len(stock), 72, "72 stock bins")
    system_names = list(system[0]); stock_names = list(stock[0])
    for i, (s, t) in enumerate(zip(system, stock)):
        a.eq(s, expected_system_row(i, system_names), f"complete SystemResults bin {i}")
        a.eq(t, expected_stock_row(i, stock_names), f"complete StockTotalResults bin {i}")
    a.eq(sum(r["NSYMO"] * 0.5 for r in system), 12, "12 reported aircraft operating hours")
    a.eq(sum(r["NFAIL"] for r in system), 1, "one system failure bin")
    a.eq(sum(r["NBO"] * 0.5 for r in stock), 0, "zero aggregate backorder hours")
    a.eq(system[-1]["NSYRY"], 2, "two terminal ready systems")
    a.eq(stock[-1]["NBO"], 0, "terminal no backorder")

    verdict = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "E12",
        "run_id": RUN.name,
        "passed": not a.failures,
        "verdict": "GO: bounded symmetric two-base expansion" if not a.failures else "NO-GO: independent replay mismatch",
        "checks_passed": a.passed,
        "checks_total": a.passed + len(a.failures),
        "failures": a.failures,
        "evidence": {"closure_sha256": sha(RUN / "closure.json"), "parent_closure_sha256": sha(PRUN / "closure.json"), "authored_tables_exact_roundtrip": len(authored), "system_stock_bins_each": 72, "physical_base_spares": {"BASE-01,0": 1, "BASE-01,1": 2}, "depot_opening_spare": 0, "failed_installed_id_base0": 3, "terminal_ready_aircraft": 2, "mission_outcomes": ["abort", "success", "success", "success", "success", "success"]},
        "limits": [
            "One QTY=2 symmetric source, one seed, one first fault and one support link; no explicit two-base comparator.",
            "Aggregate report bins do not identify each base. Independent base/aircraft/stock attribution comes from physical native event identities.",
            "No group default or override, alternate support scheme, GUI visual or cross-engine claim.",
        ],
    }
    OUT.write_bytes((json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return verdict


if __name__ == "__main__":
    verdict = main()
    print(json.dumps({key: verdict[key] for key in ("verdict", "checks_passed", "checks_total", "failures")}, indent=2))
    sys.exit(0 if verdict["passed"] else 1)

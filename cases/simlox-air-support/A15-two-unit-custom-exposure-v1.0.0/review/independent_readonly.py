"""Independent read-only replay of A15 two-unit KM evidence; stdlib only."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import struct

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
RUNS = CASE / "runs"
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
PARENT = BASE / "J07-unit-type-report-v1.0.0" / "native-input.json"
DEFAULT = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
VARS = ("a-hour-b-mission", "a-mission-b-hour")
NATIVE_IDS = {VARS[0]: "a15-two-unit-swap-a-v100-20261001-01", VARS[1]: "a15-two-unit-swap-b-v100-20261001-01"}
SHORT = {VARS[0]: "a", VARS[1]: "b"}
SXOS = {VARS[0]: "7347162aaff3c017b66da2b8b4d7d653db7d7ab1b7c1e0d9814bb10b145c372e", VARS[1]: "7bed452f7eb37ba236d616263fc9529241be83fd65f12d04147bc574e9ae1831"}
CLOSURES = {VARS[0]: "38fce23f882537c809bef906dd134b76e16c6c86d4f35c8f2d24eb3cd6ddfd27", VARS[1]: "dca1b507376db23c7300347f0576838ce7317a9049c20844d96067b42df1279b"}
SETTINGS = {"all": "c2f9862c89f2aae0200d8f7a4f16a2e21b7c6ff896b42548c41b98e673f3f9b7", "unit-a": "aa88c6dfd319640a577fe345933a8bf143bd215fe6514ed915593d5504b12d39", "unit-b": "05074aed026f1c32c8a76992a4fc03dbf222776128a6910dc9b4664bff88ffd4"}
REPORT_HELPERS = {"builder": "5b357afc8fd8d888dd0e7e7fed68601879e4aff8f1ff0c3c3e0625b315c067a1", "runner": "04b07a18bb87d48c392013ea45914dbfba026ca359bf20831ca4a326bedb02c9"}


class Audit:
    def __init__(self) -> None:
        self.n = 0
        self.failures: list[str] = []

    def check(self, yes: bool, label: str) -> None:
        self.n += 1
        if not yes:
            self.failures.append(label)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8-sig"))


def native(p: Path) -> dict:
    raw = p.read_text(encoding="utf-8-sig")
    out = []
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
        elif ch == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
            continue
        else:
            out.append(ch)
    return json.loads("".join(out))


def tables(doc: dict, root: str) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for t in doc[root]["tables"]:
        if t["name"] in found:
            raise ValueError("duplicate table " + t["name"])
        found[t["name"]] = t
    return found


def rows(t: dict) -> list[list]:
    return [r for instance in t["instances"] for r in instance["rows"]]


def recs(t: dict) -> list[dict]:
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, r)) for r in rows(t)]


def near(x: float, y: float) -> bool:
    return math.isclose(x, y, rel_tol=0, abs_tol=1e-5)


def seal(a: Audit, directory: Path, closure: dict, prefix: str) -> None:
    a.check(closure["invocation_sha256"] == sha(directory / "invocation.json"), prefix + " invocation seal")
    for name, record in closure["raw"].items():
        path = directory / name
        a.check(path.is_file() and path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], prefix + " raw " + name)


def settings_and_sources(a: Audit, contract: dict) -> dict[str, str]:
    files = {"parent": PARENT, "contract": CASE / "contract.json", "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py", "exact_diff": CASE / "exact-diff.json", "checker": CASE / "check_roundtrip.py", "native_runner": CASE / "run_native_ssh.ps1", "report_builder": CASE / "make_report_settings.py", "report_runner": CASE / "report_existing_sxo_ssh.ps1", "manual": MANUAL, "exe": EXE, "default": DEFAULT}
    actual = {k: sha(v) for k, v in files.items()}
    expected = {"parent": contract["parent_input_sha256"], "builder": contract["builder_sha256"], "diff_builder": contract["diff_builder_sha256"], "exact_diff": contract["exact_diff_sha256"], "manual": contract["manual_sha256"], "contract": "41aa34267ebd6dd663fc859f44e267d73801f214b045e4d090164d013b0f8379", "checker": "33cbe34a5602f6d8367eb0d2c68fc2dfbdad4e75085b764829eba534fbc1d5cb", "native_runner": "5e66e3cc511bb8d1b37fcc785025870727c9ec80b5ecdfa27429050e510030c5", "report_builder": REPORT_HELPERS["builder"], "report_runner": REPORT_HELPERS["runner"], "exe": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "default": "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d"}
    for name, value in expected.items():
        a.check(actual[name] == value, "source " + name + " SHA")
    all_bytes = (RUNS / "report-settings" / "all.sxs").read_bytes()
    a.check(sha(RUNS / "report-settings" / "all.sxs") == SETTINGS["all"], "all settings SHA")
    a.check(len(all_bytes) == len(DEFAULT.read_bytes()) and sum(x != y for x, y in zip(all_bytes, DEFAULT.read_bytes())) == 12, "all settings 12-byte remap")
    for selector, unit in (("unit-a", b"TEACH-UNIT"), ("unit-b", b"TEACH-UNIT-2")):
        selected = (RUNS / "report-settings" / (selector + ".sxs")).read_bytes()
        a.check(sha(RUNS / "report-settings" / (selector + ".sxs")) == SETTINGS[selector], selector + " settings SHA")
        a.check(selected.count(unit + b"\0") >= 1 and selected.count(b"MissionSettings\0") == all_bytes.count(b"MissionSettings\0"), selector + " typed selector")
    j07 = BASE / "J07-unit-type-report-v1.0.0"
    a.check("accepted A17" in (j07 / "README.md").read_text(encoding="utf-8") and "GO" in (j07 / "cli-scope-signoff-2026-10-01.md").read_text(encoding="utf-8"), "accepted J07 parent publication")
    mechanism = load(BASE / "A15-custom-operation-report-v1.0.0" / "review" / "independent-readonly-2026-10-01.json")
    a.check(mechanism["passed"] is True and mechanism["success"]["per-hour"]["accumulated"]["KM"] == mechanism["success"]["per-mission"]["accumulated"]["KM"] == 120, "accepted A15 custom-operation mechanism")
    return actual


def source_delta(a: Audit, contract: dict) -> None:
    diff = load(CASE / "exact-diff.json")
    parent = tables(native(PARENT), "model")
    a.check(diff["parent_sha256"] == sha(PARENT), "exact diff parent hash")
    children = {}
    for variant in VARS:
        p = CASE / (variant + "-input.json")
        child = tables(native(p), "model")
        children[variant] = child
        a.check(sha(p) == contract["input_sha256"][variant] == diff["child_sha256"][variant], variant + " input hash")
        delta = diff["changes"][variant]
        modified = {k for k in parent.keys() & child.keys() if parent[k] != child[k]}
        added = child.keys() - parent.keys()
        a.check(modified == {"ProblemDescription", "OperationParameter"} and added == {"MissionTypeUtilization"} and not (parent.keys() - child.keys()), variant + " exact table set")
        for name in modified:
            a.check(parent[name] == delta["modified"][name]["parent"] and child[name] == delta["modified"][name]["child"], variant + " exact modified " + name)
        a.check(child["MissionTypeUtilization"] == delta["added"]["MissionTypeUtilization"], variant + " exact added utilization")
        a.check(sum(bool(rows(t)) for t in child.values()) == 16, variant + " 16 row tables")
        a.check(all(not rows(child[name]) for name in ("Resource", "ResourceAllocation", "TaskResource", "SubTaskResource", "MaterielPM", "ItemRepair")), variant + " no typed resource/PM/repair inputs")
        utilization = recs(child["MissionTypeUtilization"])
        expected = [(60, "1/HOUR"), (120, "1/MISSION")] if variant == VARS[0] else [(120, "1/MISSION"), (60, "1/HOUR")]
        a.check([(r["UTIL"], r["UTILU"]) for r in utilization] == expected and [r["MTID"] for r in utilization] == ["MISSION-A", "MISSION-B"], variant + " typed rate")
    a.check({k for k in children[VARS[0]] if children[VARS[0]][k] != children[VARS[1]][k]} == set(diff["pair_different_tables"]) == {"MissionTypeUtilization", "ProblemDescription"}, "pair differs only rates and description")


def native_run(a: Audit, contract: dict, sources: dict, variant: str) -> tuple[Path, dict]:
    directory = RUNS / NATIVE_IDS[variant]
    inv, cl, steps = (load(directory / f) for f in ("invocation.json", "closure.json", "steps.json"))
    a.check(inv["run_id"] == cl["run_id"] == NATIVE_IDS[variant] and inv["variant"] == variant, variant + " native identity")
    a.check(cl["error"] is None and cl["source_hashes_before"] == cl["source_hashes_after"] == inv["source_hashes_before"], variant + " stable source closure")
    expected = {"input": contract["input_sha256"][variant], "parent": sources["parent"], "contract": sources["contract"], "builder": sources["builder"], "checker": sources["checker"], "runner_script": sources["native_runner"], "simlox_exe": sources["exe"]}
    a.check(all(cl["source_hashes_before"][k] == v for k, v in expected.items()), variant + " native source hashes")
    seal(a, directory, cl, variant + " native")
    a.check(inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"], variant + " session0 SSH")
    a.check(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, variant + " mutex/GUI")
    a.check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), variant + " five guarded steps")
    a.check(sha(directory / "input.json") == contract["input_sha256"][variant] and sha(directory / "model.sxo") == SXOS[variant] and sha(directory / "closure.json") == CLOSURES[variant], variant + " input/SXO/closure SHA")
    a.check((directory / "model.sxo").stat().st_size > 1000, variant + " valid SXO")
    source, exported = tables(native(directory / "input.json"), "model"), tables(native(directory / "roundtrip-raw.json"), "model")
    business = {name for name, t in source.items() if rows(t)}
    a.check(len(business) == 16, variant + " 16 roundtrip tables")
    for name in business:
        a.check(name in exported and source[name]["columns"] == exported[name]["columns"] and rows(source[name]) == rows(exported[name]), variant + " exact roundtrip " + name)
    log = (directory / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    a.check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log and set(re.findall(r"warning #(\d+)", log)) == {"108", "126"}, variant + " converter")
    text = (directory / "model.log").read_text(encoding="utf-8-sig")
    for mission, unit, aircraft, mid in (("MISSION-A", "TEACH-UNIT", 0, 0), ("MISSION-B", "TEACH-UNIT-2", 1, 1)):
        identity = f"<{mission},{unit},0,0,{mid}>"
        for time, event in ((8, "mission starting"), (10, "mission success"), (10, "mission completed")):
            a.check(sum(line.startswith(f"Time: {time} {identity} {event}") for line in text.splitlines()) == 1, variant + f" {mission} {event}")
        a.check(f"Time: 8 {identity} mission starting, duration: 2 : <TEACH-AIR-01,{aircraft}>" in text, variant + " mission aircraft " + mission)
        a.check(f"Time: 10 <TEACH-AIR-01,BASE-0{aircraft+1},0> System arrives <TEACH-AIR-01,{aircraft}>, mission success" in text, variant + " terminal return " + mission)
    a.check("failure occurred" not in text.lower() and "repair started" not in text.lower() and "mission aborted" not in text.lower(), variant + " no failure/abort")
    report = tables(native(directory / "report-raw.json"), "report")
    a.check(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, variant + " default report scope")
    summary = recs(report["ResultSummary"])[0]
    a.check(summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["STMF"] == 1, variant + " default summary")
    sys, stock = recs(report["SystemResults"]), recs(report["StockTotalResults"])
    a.check(len(sys) == len(stock) == 72, variant + " native 72 bins")
    for i, (s, k) in enumerate(zip(sys, stock)):
        start = i/2
        a.check(near(s["STINT"],start) and near(s["ETINT"],start+.5) and near(k["STINT"],start) and near(k["ETINT"],start+.5), variant + f" bin time {i}")
        a.check(near(s["NSYMO"],2 if 8<=start<10 else 0) and s["NSYA"] == 2 and s["NFAIL"] == s["NPMT"] == s["NDAM"] == 0, variant + f" system/negative {i}")
        a.check(all(k[n] == 0 for n in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), variant + f" stock negative {i}")
    a.check(sys[-1]["NSYRY"] == 2 and sys[-1]["NSYMO"] == 0, variant + " terminal ready two")
    return directory, report


def operation_report(a: Audit, variant: str, selector: str, native_dir: Path, native_report: dict, sources: dict) -> dict:
    rid = f"a15-two-unit-{SHORT[variant]}-{selector}-20261001-01"
    directory = RUNS / rid
    inv, cl = load(directory / "invocation.json"), load(directory / "closure.json")
    a.check(inv["run_id"] == cl["run_id"] == rid and inv["selector"] == cl["selector"] == selector and inv["variant"] == cl["variant"] == variant, rid + " identity")
    seal(a, directory, cl, rid)
    a.check(cl["error"] is None and cl["exit_code"] == 0 and set(cl["raw"]) == {"report-raw.json", "report-export.log"}, rid + " clean report-only closure")
    expected = {"sxo": SXOS[variant], "source_closure": CLOSURES[variant], "settings": SETTINGS[selector], "default": sources["default"], "exe": sources["exe"], "builder": sources["report_builder"], "runner": sources["report_runner"]}
    a.check(inv["source_hashes"] == cl["source_hashes"] == expected and inv["source_run_id"] == NATIVE_IDS[variant], rid + " source/settings seal")
    a.check(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, rid + " SSH/mutex/GUI")
    command = inv["command"]
    a.check(str(native_dir / "model.sxo") in command and str(RUNS / "report-settings" / (selector + ".sxs")) in command and " -report -rpts " in command and " -rjexport " in command, rid + " selected command")
    log = (directory / "report-export.log").read_text(encoding="utf-8-sig", errors="replace")
    a.check("Report completed" in log and "Export completed!" in log and not any(x in log for x in ("could not be loaded", "Reverting to default settings", "Failed to open file")), rid + " no fallback/completion")
    report = tables(native(directory / "report-raw.json"), "report")
    a.check(set(report) == set(native_report) | {"MissionOperationAccumulated", "MissionOperationTotalAccumulated", "MissionOperation", "MissionOperationTotal"}, rid + " report table scope")
    for name in native_report:
        a.check(report[name]["columns"] == native_report[name]["columns"] and rows(report[name]) == rows(native_report[name]), rid + " parent report rows " + name)
    selected = "Total over all Units" if selector == "all" else "TEACH-UNIT" if selector == "unit-a" else "TEACH-UNIT-2"
    factor = 2 if selector == "all" else 1
    acc_total = {r["OPID"]: r for r in recs(report["MissionOperationTotalAccumulated"])}
    average = {r["OPID"]: r for r in recs(report["MissionOperationTotal"])}
    a.check(set(acc_total) == set(average) == {"KM", "OPHOURS"}, rid + " total OPID pair")
    a.check(all(r["UNID"] == selected for r in list(acc_total.values())+list(average.values())), rid + " selected unit label")
    a.check(near(acc_total["KM"]["SOACC"],120*factor) and near(acc_total["OPHOURS"]["SOACC"],2*factor), rid + " accumulated 120 per unit")
    a.check(near(average["KM"]["SOACC"],120*factor/36) and near(average["OPHOURS"]["SOACC"],2*factor/36), rid + " horizon-average denominator")
    for table_name in ("MissionOperation", "MissionOperationAccumulated"):
        data = recs(report[table_name])
        a.check(len(data) == 128 and all(r["UNID"] == selected for r in data), rid + " " + table_name + " selector/rows")
        for opid, baseline in (("KM",60*factor),("OPHOURS",factor)):
            sequence = [r for r in data if r["OPID"] == opid]
            first = 16 if opid == "KM" else 0
            a.check([r["STINT"] for r in sequence] == [i/2 for i in range(first,72)], rid + " " + table_name + " " + opid + " bins")
            for r in sequence:
                start = r["STINT"]
                expected = baseline * (max(0,min(start+.5,10)-8) if table_name.endswith("Accumulated") else (1 if 8<=start<10 else 0))
                a.check(near(r["SOACC"],expected), rid + f" {table_name} {opid} {start:g}")
    return {"run_id": rid, "closure_sha256": sha(directory / "closure.json"), "report_sha256": sha(directory / "report-raw.json"), "unit": selected, "KM_accumulated": acc_total["KM"]["SOACC"], "KM_per_horizon_hour": average["KM"]["SOACC"]}


def main() -> int:
    a = Audit()
    try:
        contract = load(CASE / "contract.json")
        a.check(contract["publication_state"] == "not_published" and contract["parent_publication_id"] == "J07.var05.unit_type_report_selection.1.0.0", "candidate/parent contract")
        sources = settings_and_sources(a, contract)
        source_delta(a, contract)
        native_runs = {v: native_run(a, contract, sources, v) for v in VARS}
        a.check((native_runs[VARS[0]][0] / "model.log").read_bytes() == (native_runs[VARS[1]][0] / "model.log").read_bytes(), "swapped source event logs byte-identical")
        reports = {v: {s: operation_report(a, v, s, native_runs[v][0], native_runs[v][1], sources) for s in SETTINGS} for v in VARS}
        for v in VARS:
            a.check(near(reports[v]["all"]["KM_accumulated"], reports[v]["unit-a"]["KM_accumulated"] + reports[v]["unit-b"]["KM_accumulated"]), v + " 240 = 120+120")
        for s in SETTINGS:
            left = tables(native(RUNS / reports[VARS[0]][s]["run_id"] / "report-raw.json"), "report")
            right = tables(native(RUNS / reports[VARS[1]][s]["run_id"] / "report-raw.json"), "report")
            a.check(set(left) == set(right) and all(left[n]["columns"] == right[n]["columns"] and rows(left[n]) == rows(right[n]) for n in left if n != "ProblemDescription"), "swapped pair report data equal " + s)
        result = {"schema": "simlox-a15-two-unit-independent-readonly/v1", "passed": not a.failures, "verdict": "bounded_GO" if not a.failures else "NO_GO", "check_count": a.n, "failures": a.failures, "script_sha256": sha(Path(__file__)), "contract_sha256": sha(CASE / "contract.json"), "source_hashes": sources, "native_closure_sha256": {v: sha(native_runs[v][0] / "closure.json") for v in VARS}, "reports": reports, "scope": "Two separate unit-owned complete 8-10 fixed missions; KM rate forms swapped; per-unit/all-unit report-only SOACC", "limits": ["No group-member aggregation or single-formation inference", "KM is an abstract user-defined unit", "No partial-mission, failure/PM consumption, GUI visual or cross-engine claim"]}
    except Exception as exc:
        result = {"schema": "simlox-a15-two-unit-independent-readonly/v1", "passed": False, "verdict": "NO_GO", "check_count": a.n, "failures": a.failures + [f"review exception: {type(exc).__name__}: {exc}"], "script_sha256": sha(Path(__file__))}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "verdict", "check_count", "failures")}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

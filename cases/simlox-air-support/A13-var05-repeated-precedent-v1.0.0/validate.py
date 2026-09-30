"""Source-bound replay of repeated-RECON control and ambiguous predecessor key."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated, validate as check_roundtrip

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = HERE / "runs"
PARENT = ROOT / "A13-start-dependence-v1.0.0" / "dependent-input.json"
STRUCTURE = ROOT / "A13-var01-multiple-predecessors-v1.0.0" / "multiple-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
IDS = {v: f"a13-var05-repeat-{v}-v100-20261001-01" for v in ("control", "dependency")}
SOURCE_SHA = {"control": "7ce565e2d9644f25560de726d983bab4b8d647f6352b1857a9b2b03d0b61f73b", "dependency": "155e83d3ffc24d51784ec892f296bed8df505a379eb7b3e3ca72218e9aa88dff"}
PARENT_SHA = "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"
STRUCTURE_SHA = "1d2226850d07d7caf5f58e825bb2d3fdf498f7626fb58e4a6ed4bcfa469d18ae"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
checks = 0


def ck(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        raise ValueError(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(doc: dict, root: str = "model") -> dict[str, dict]:
    result = {t["name"]: t for t in doc[root]["tables"]}
    ck(len(result) == len(doc[root]["tables"]), "duplicate table")
    return result


def rows(t: dict) -> list[list]:
    return [r for ins in t["instances"] for r in ins["rows"]]


def fields(t: dict, row: list) -> dict:
    return dict(zip((c["name"] for c in t["columns"]), row))


def source_gate() -> None:
    for path, expected, label in ((PARENT, PARENT_SHA, "parent"), (STRUCTURE, STRUCTURE_SHA, "structure"), (MANUAL, MANUAL_SHA, "manual"), (EXE, EXE_SHA, "executable")):
        ck(sha(path) == expected, f"{label} SHA")
    sources = {v: parse_native(HERE / f"{v}-input.json") for v in IDS}
    tab = {v: tables(sources[v]) for v in IDS}
    for v in IDS:
        ck(sha(HERE / f"{v}-input.json") == SOURCE_SHA[v], f"{v} input SHA")
        ck(len(populated(sources[v])) == (13 if v == "control" else 14), f"{v} table count")
    ck("MissionDependence" not in tab["control"], "control has no dependency table")
    ck(set(tab["dependency"]) == set(tab["control"]) | {"MissionDependence"}, "pair table set")
    ck(all(tab["control"][name] == tab["dependency"][name] for name in tab["control"] if name != "ProblemDescription"), "pair only START/description")
    dep = [fields(tab["dependency"]["MissionDependence"], r) for r in rows(tab["dependency"]["MissionDependence"])]
    ck(len(dep) == 1 and tuple(dep[0][k] for k in ("DUNID", "DMTID", "DSTIM", "PUNID", "PMTID", "PSTIM", "DTYPE")) == ("TEACH-UNIT", "FOLLOW", 10, "TEACH-UNIT", "RECON", 8, "START"), "ambiguous predecessor key")
    deploy = [fields(tab["control"]["SystemDeployment"], r) for r in rows(tab["control"]["SystemDeployment"])]
    ck(len(deploy) == 1 and (deploy[0]["SID"], deploy[0]["USTID"], deploy[0]["QTYPS"]) == ("TEACH-AIR-01", "TEACH-UNIT", 3), "three aircraft")
    donor = tables(parse_native(STRUCTURE))
    ck(tab["control"]["SystemDeployment"] == donor["SystemDeployment"], "accepted three-aircraft topology")
    profiles = [fields(tab["control"]["OperationProfile"], r) for r in rows(tab["control"]["OperationProfile"])]
    ck([(r["SPRID"], r["STIM"], r["IQTY"], r["IPER"]) for r in profiles] == [("RECON", 8, 2, 0), ("FOLLOW", 10, 1, 0)], "same-time repeat profile")
    parent = tables(parse_native(PARENT))
    ck(all(tab["dependency"][name] == parent[name] for name in parent if name not in ("ProblemDescription", "SystemDeployment", "OperationProfile")), "parent isolation")
    diff = parse_native(HERE / "exact-diff.json")
    ck(diff["parent_sha256"] == PARENT_SHA and diff["structural_source_sha256"] == STRUCTURE_SHA and all(diff["variants"][v]["input_sha256"] == SOURCE_SHA[v] for v in IDS), "exact diff lineage")


def common(variant: str) -> tuple[Path, dict, dict, list, str]:
    run = RUNS / IDS[variant]
    inv, clo, steps = (parse_native(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck(inv["run_id"] == clo["run_id"] == IDS[variant] and inv["variant"] == variant and inv["variant_id"] == "A13.var05", f"{variant} identity")
    ck(inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"], f"{variant} SSH")
    ck(inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, f"{variant} queue/GUI")
    ck(inv["input_sha256"] == SOURCE_SHA[variant] and inv["parent_sha256"] == PARENT_SHA and inv["structure_sha256"] == STRUCTURE_SHA, f"{variant} lineage")
    ck(sha(run / "invocation.json") == clo["invocation_sha256"] and clo["error"] is None, f"{variant} closure")
    ck(clo["source_hashes_before"] == clo["source_hashes_after"] == inv["source_hashes_before"], f"{variant} source stability")
    paths = {"input": HERE / f"{variant}-input.json", "parent": PARENT, "structure": STRUCTURE, "contract": HERE / "contract.json", "builder": HERE / "build.py", "exact_diff": HERE / "exact-diff.json", "diff_checker": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py", "validator": HERE / "validate.py", "python": PYTHON, "runner_script": HERE / "run_native_ssh.ps1", "simlox_exe": EXE}
    for key, path in paths.items():
        ck(sha(path) == clo["source_hashes_before"][key], f"{variant} {key} SHA")
    ck(set(clo["raw"]) == {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}, f"{variant} raw set")
    for name, rec in clo["raw"].items():
        p = run / name
        ck(p.stat().st_size == rec["bytes"] and sha(p) == rec["sha256"], f"{variant} raw {name}")
    ck([s["name"] for s in steps[:3]] == ["import", "export", "calc"], f"{variant} first three steps")
    ck([s["status"] for s in steps[:3]] == ["completed", "completed", "calc_observed"], f"{variant} first three statuses")
    ck(all(s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps), f"{variant} step/GUI")
    ck(all(steps[i]["arguments"] == inv["planned_commands"][i]["arguments"] for i in range(3)), f"{variant} CLI args")
    rt = check_roundtrip(run)
    ck(rt["passed"] is True and parse_native(run / "roundtrip-validation.json")["passed"] is True, f"{variant} exact import/export")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    return run, inv, clo, steps, calc


def control() -> dict:
    run, inv, clo, steps, calc = common("control")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "control steps")
    ck(steps[3]["arguments"] == inv["planned_report"]["arguments"] and steps[3]["status"] == steps[4]["status"] == "completed", "control report/checker")
    ck("Input conversion completed. Errors: 0," in calc and not re.search(r"error #\d+", calc, re.I), "control zero converter errors")
    ck("Saving results" in calc and (run / "model.sxo").stat().st_size > 4 and (run / "report-raw.json").stat().st_size > 4, "control valid simulation")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    all_mission_ids: set[str] = set()
    all_aircraft_ids: set[str] = set()
    for mission, count, alloc, start, end, aircraft in (("RECON", 2, 7, 8, 12, {"0", "1"}), ("FOLLOW", 1, 9, 10, 12, {"2"})):
        rx = rf"^Time: ([0-9.]+) <({mission},TEACH-UNIT,0,0,[0-9]+)> mission (allocates system:|starting,|success:|completed:)(.*)$"
        events = [(float(t), ident, kind, detail) for t, ident, kind, detail in re.findall(rx, log, re.M)]
        by_kind = {kind: [(t, ident, detail) for t, ident, k, detail in events if k == kind] for kind in ("allocates system:", "starting,", "success:", "completed:")}
        for kind, expected_time in (("allocates system:", alloc), ("starting,", start), ("success:", end), ("completed:", end)):
            ck(len(by_kind[kind]) == count and all(t == expected_time for t, _, _ in by_kind[kind]), f"control {mission} {kind} count/time")
        identities = {ident for _, ident, _ in by_kind["allocates system:"]}
        ck(len(identities) == count and all({ident for _, ident, _ in by_kind[kind]} == identities for kind in ("starting,", "success:", "completed:")), f"control {mission} distinct stable mission identities")
        allocated_aircraft = {n for _, _, detail in by_kind["allocates system:"] for n in re.findall(r"<TEACH-AIR-01,([0-9]+)>", detail)}
        ck(allocated_aircraft == aircraft and all(any(f"<TEACH-AIR-01,{n}>" in detail for _, _, detail in by_kind[kind]) for kind in ("starting,", "completed:") for n in aircraft), f"control {mission} distinct aircraft")
        all_mission_ids |= identities
        all_aircraft_ids |= allocated_aircraft
    ck(len(all_mission_ids) == len(all_aircraft_ids) == 3, "control three disjoint identities/aircraft")
    ck(len(re.findall(r" mission starting,", log)) == 3 and not re.search(r"mission (?:abort|cancel|fail)", log, re.I), "control three successful missions")
    report = parse_native(run / "report-raw.json")
    rt = tables(report, "report")
    sy, st, sm = (rt[name] for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
    ck(len(rows(sy)) == len(rows(st)) == 48 and len(rows(sm)) == 1, "control report rows")
    sf = fields(sm, rows(sm)[0])
    ck(all(sf[k] == value for k, value in {"NREP": 1, "RTILW": 0, "RTIUP": 24}.items()), "control report horizon")
    assigned_hours = operating_hours = 0.0
    for i, (a, b) in enumerate(zip(rows(sy), rows(st))):
        a, b = fields(sy, a), fields(st, b)
        t = i / 2
        ck(a["STINT"] == b["STINT"] == t and a["ETINT"] == b["ETINT"] == t + .5, f"bin{i} interval")
        assigned = 2 * int(7 <= t < 12) + int(9 <= t < 12)
        operating = 2 * int(8 <= t < 12) + int(10 <= t < 12)
        ck(a["NSYA"] == 3 and a["NSYMA"] == assigned and a["NSYMO"] == operating and a["NSYRY"] == 3 - assigned, f"bin{i} aircraft")
        ck(a["UNID"] == "Total over all Units" and a["SID"] == "Total over all Systems", f"bin{i} aggregate")
        ck(all(a[k] == 0 for k in ("NFAIL", "NDAM", "NPMS", "NROBT", "NRCFG")), f"bin{i} no failure")
        ck(all(b[k] == 0 for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), f"bin{i} no stock movement")
        assigned_hours += .5 * a["NSYMA"]
        operating_hours += .5 * a["NSYMO"]
    ck((assigned_hours, operating_hours) == (13, 10) and fields(sy, rows(sy)[-1])["NSYRY"] == 3, "control integrated/terminal")
    return {"run_id": IDS["control"], "closure_sha256": sha(run / "closure.json"), "report_sha256": sha(run / "report-raw.json"), "assigned_hours": assigned_hours, "operating_hours": operating_hours}


def dependency() -> dict:
    run, _, _, steps, calc = common("dependency")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "check_import_export"], "dependency no report step")
    ck(steps[-1]["status"] == "completed", "dependency roundtrip step")
    m = re.search(r"Input conversion completed\. Errors: ([1-9][0-9]*),", calc)
    ck(m is not None, "dependency converter rejection")
    form = re.search(r"Form:\s*MissionDependence\b([\s\S]*?)(?:\r?\nForm:|Input conversion completed\.)", calc)
    ck(form is not None, "dependency error attributed to MissionDependence form")
    diagnostics = re.findall(r"\(error #([0-9]+)\)\s*([^\r\n]*)", form.group(1), re.I)
    ck(bool(diagnostics) and any(re.search(r"(?:IQTY|ambig|uniqu|multiple|more than one|duplicate)", message, re.I) and re.search(r"(?:precedent|PUNID|PMTID|PSTIM|RECON)", message, re.I) for _, message in diagnostics), "specific repeated-predecessor ambiguity diagnostic")
    ck((run / "model.sxo").stat().st_size == 4 and not (run / "report-raw.json").exists(), "dependency invalid output/no report")
    return {"run_id": IDS["dependency"], "closure_sha256": sha(run / "closure.json"), "converter_error_count": int(m.group(1)), "diagnostics": diagnostics}


def main() -> int:
    try:
        source_gate()
        observed = {"control": control(), "dependency": dependency()}
        result = {"schema": "simlox-a13-var05-repeated-precedent-v100-author-replay/v1", "passed": True, "checks": checks, "runs": observed, "scope": "installed-version converter acceptance for one repeated predecessor key"}
    except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration) as exc:
        result = {"schema": "simlox-a13-var05-repeated-precedent-v100-author-replay/v1", "passed": False, "checks_before_failure": checks, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

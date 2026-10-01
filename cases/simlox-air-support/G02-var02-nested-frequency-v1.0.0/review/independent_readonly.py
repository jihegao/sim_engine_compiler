"""Independent standard-library replay of the sealed G02.var02 nested panel.

Reads only frozen source and native artifacts. It never imports package code or
invokes SIMLOX. The only output is the deterministic review JSON beside this file.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import statistics

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
CONTRACT = CASE / "contract.json"
PARENT = ROOT / "G02-var01-position-modes-v1.0.0" / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
OUTPUT = CASE / "review" / "independent-readonly-2026-10-02.json"
SEEDS = tuple(range(2, 14))
ARMS = ("nested-baseline", "nested-qty-two", "nested-env-two")
ONE_LEVEL = ROOT / "G02-var03-quantity-environment-v1.0.1" / "runs"
ONE_LEVEL_INDEX = ONE_LEVEL.parent / "evidence-index.json"
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}
T975_DF11 = 2.200985160082949


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, native: bool = False) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    if native:
        # SIMLOX emits trailing commas. Remove only commas outside strings that
        # immediately precede a closing array/object token.
        out: list[str] = []
        quoted = escaped = False
        for i, char in enumerate(raw):
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
            elif char == "," and re.match(r"\s*[}\]]", raw[i + 1:]):
                continue
            else:
                out.append(char)
        raw = "".join(out)
    return json.loads(raw)


def table(doc: dict, root: str, name: str) -> dict:
    found = [t for t in doc[root]["tables"] if t["name"] == name]
    assert len(found) == 1, (root, name, len(found))
    return found[0]


def rows(doc: dict, root: str, name: str) -> list[dict]:
    t = table(doc, root, name)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row, strict=True)) for ins in t["instances"] for row in ins["rows"]]


def populated(doc: dict) -> dict[str, dict]:
    result = {}
    for t in doc["model"]["tables"]:
        assert t["name"] not in result
        all_rows = [row for ins in t["instances"] for row in ins["rows"]]
        if all_rows:
            assert all(len(row) == len(t["columns"]) for row in all_rows)
            result[t["name"]] = {"columns": t["columns"], "rows": all_rows}
    return result


def canonical_source(parent: dict, seed: int, arm: str) -> bytes:
    doc = deepcopy(parent)
    desc = table(doc, "model", "ProblemDescription")
    desc_cols = [c["name"] for c in desc["columns"]]
    desc["instances"][0]["rows"][0][desc_cols.index("PDESC")] = (
        f"G02.var02 seed {seed} 256-replication {arm} frequency propagation control")
    control = table(doc, "model", "Control")
    cc = [c["name"] for c in control["columns"]]
    assert len(control["instances"][0]["rows"]) == 1
    cr = control["instances"][0]["rows"][0]
    cr[cc.index("NREPS")] = 256
    cr[cc.index("RSEED")] = str(seed)
    fm = table(doc, "model", "FailureMode")
    fc = [c["name"] for c in fm["columns"]]
    for mode in ("FM-POS-A", "FM-POS-B"):
        match = [r for r in fm["instances"][0]["rows"] if r[fc.index("FMID")] == mode]
        assert len(match) == 1
        match[0][fc.index("FRQ")] = 50000.0
    ms = table(doc, "model", "MaterielStructure")
    mc = [c["name"] for c in ms["columns"]]
    match = [r for r in ms["instances"][0]["rows"]
             if r[mc.index("MID")] == "POS-B" and r[mc.index("MMID")] == "TEACH-AIR-01"]
    assert len(match) == 1
    assert match[0][mc.index("QTYPM")] == 1 and match[0][mc.index("ENVF")] == 1.0
    positions = table(doc, "model", "MaterielPosition")
    positions["instances"][0]["rows"].append(["POS-B-CH", "Child position under B", None])
    lru_b = [r for r in ms["instances"][0]["rows"]
             if r[mc.index("MID")] == "TEACH-LRU-01" and r[mc.index("MMID")] == "POS-B"]
    assert len(lru_b) == 1
    lru_b[0][mc.index("MMID")] = "POS-B-CH"
    ms["instances"][0]["rows"].insert(ms["instances"][0]["rows"].index(lru_b[0]),
                                           ["POS-B-CH", "POS-B", 1, 1.0, None, None])
    b_mode = [r for r in fm["instances"][0]["rows"] if r[fc.index("FMID")] == "FM-POS-B"]
    assert len(b_mode) == 1
    b_mode[0][fc.index("MID")] = "POS-B-CH"
    if arm == "nested-qty-two":
        match[0][mc.index("QTYPM")] = 2
    elif arm == "nested-env-two":
        match[0][mc.index("ENVF")] = 2.0
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def check(condition: bool, label: str, failures: list[str], counter: list[int]) -> None:
    counter[0] += 1
    if not condition:
        failures.append(label)


def check_run(seed: int, arm: str, contract: dict, parent: dict, reference: dict,
              failures: list[str], counter: list[int]) -> dict:
    run_id = f"g02-var02-seed{seed:02d}-{arm}-20261002-01"
    run = CASE / "runs" / run_id
    inv = read_json(run / "invocation.json")
    closure = read_json(run / "closure.json")
    steps = read_json(run / "steps.json")
    actual_input = run / "input.json"
    source_raw = canonical_source(parent, seed, arm)
    check(actual_input.read_bytes() == source_raw, f"{run_id}: exact derived source", failures, counter)
    check(inv.get("input_sha256") == digest(actual_input) and
          inv.get("seed") == seed and inv.get("variant") == arm and inv.get("run_id") == run_id,
          f"{run_id}: invocation/input identity", failures, counter)
    check(inv.get("schema") == "simlox-g02-var02-nested-v100-native-candidate/ssh-cli-v1"
          and closure.get("schema") == "simlox-g02-var02-nested-v100-native-closure/v1"
          and closure.get("run_id") == run_id and closure.get("error") is None
          and closure.get("invocation_sha256") == digest(run / "invocation.json"),
          f"{run_id}: invocation/closure", failures, counter)
    check(inv.get("session_id") == 0 and inv.get("ssh_connection_present") is True
          and "sshd.exe" in inv.get("ssh_ancestor_names", [])
          and inv.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue"
          and inv.get("gui", {}).get("pid") == 13340 and inv["gui"].get("session_id") == 1,
          f"{run_id}: SSH/mutex/GUI", failures, counter)
    names = ["import", "export", "calc", "jsonreport", "check_import_export"]
    check([s.get("name") for s in steps] == names and all(
          s.get("status") == "completed" and s.get("exit_code") == 0 and s.get("gui_preserved") is True
          for s in steps), f"{run_id}: five steps", failures, counter)
    commands = inv.get("planned_commands", [])
    check([c.get("name") for c in commands] == names[:4]
          and "-threads 1 -calc" in commands[2].get("arguments", ""),
          f"{run_id}: calc thread command", failures, counter)
    sources = {
        "input": actual_input, "parent": PARENT, "manual": MANUAL,
        "dictionary": DICTIONARY, "contract": CONTRACT,
        "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py",
        "runner_script": CASE / "run_native_ssh.ps1", "python": PYTHON,
        "simlox_exe": EXE,
    }
    before = inv.get("source_hashes_before", {})
    check(before == closure.get("source_hashes_before") == closure.get("source_hashes_after")
          and set(before) == set(sources), f"{run_id}: source seal set", failures, counter)
    for name, path in sources.items():
        check(before.get(name) == digest(path), f"{run_id}: source {name}", failures, counter)
    check(set(closure.get("raw", {})) == RAW, f"{run_id}: 12 raw seals", failures, counter)
    for name in RAW:
        record = closure.get("raw", {}).get(name, {})
        path = run / name
        check(path.is_file() and path.stat().st_size == record.get("bytes") and
              digest(path) == record.get("sha256"), f"{run_id}: raw {name}", failures, counter)
    source = read_json(actual_input)
    exported = read_json(run / "roundtrip-raw.json", native=True)
    before_tables, after_tables = populated(source), populated(exported)
    check(len(before_tables) == 18 and all(after_tables.get(k) == v for k, v in before_tables.items()),
          f"{run_id}: 18 table roundtrip", failures, counter)
    check(read_json(run / "roundtrip-validation.json").get("passed") is True,
          f"{run_id}: checker result", failures, counter)
    ctrl = rows(source, "model", "Control")
    check(len(ctrl) == 1 and ctrl[0].get("NREPS") == 256 and
          ctrl[0].get("RSEED") == str(seed) and ctrl[0].get("SIMPE") == 36,
          f"{run_id}: control", failures, counter)
    fm = rows(source, "model", "FailureMode")
    check({r["FMID"]: r["FRQ"] for r in fm} == {"FM-POS-A": 50000.0, "FM-POS-B": 50000.0},
          f"{run_id}: mode rates", failures, counter)
    ms = [r for r in rows(source, "model", "MaterielStructure")
          if r.get("MID") == "POS-B" and r.get("MMID") == "TEACH-AIR-01"]
    check(len(ms) == 1 and ms[0]["QTYPM"] == (2 if arm == "nested-qty-two" else 1)
          and ms[0]["ENVF"] == (2.0 if arm == "nested-env-two" else 1.0),
          f"{run_id}: factor", failures, counter)
    nested_positions = [r for r in rows(source, "model", "MaterielPosition")
                        if r.get("MPID") == "POS-B-CH"]
    nested_edges = rows(source, "model", "MaterielStructure")
    check(len(nested_positions) == 1 and any(
          r.get("MID") == "POS-B-CH" and r.get("MMID") == "POS-B" and
          r.get("QTYPM") == 1 and r.get("ENVF") == 1 for r in nested_edges)
          and any(r.get("MID") == "TEACH-LRU-01" and r.get("MMID") == "POS-B-CH"
                  for r in nested_edges)
          and {r["FMID"]: r["MID"] for r in fm} ==
              {"FM-POS-A": "POS-A", "FM-POS-B": "POS-B-CH"},
          f"{run_id}: nested path and FM binding", failures, counter)
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
    check(bool(match) and tuple(map(int, match.groups())) == (0, 1, 0)
          and re.findall(r"\(warning #(\d+)\)", log) == ["108"]
          and (run / "model.sxo").stat().st_size > 4,
          f"{run_id}: zero error/classified warning", failures, counter)
    report = read_json(run / "report-raw.json", native=True)
    summary = rows(report, "report", "ResultSummary")
    system = rows(report, "report", "SystemResults")
    stock = rows(report, "report", "StockTotalResults")
    check(len(summary) == 1 and summary[0].get("NREP") == 256
          and summary[0].get("RTILW") == 0 and summary[0].get("RTIUP") == 36,
          f"{run_id}: result summary horizon/replications", failures, counter)
    check(all(0 <= summary[0][key] <= 1 for key in ("MTMF", "MSTF", "MSUF", "STMF"))
          and all(summary[0][key] >= 0 for key in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")),
          f"{run_id}: mission fractions/errors", failures, counter)
    check(len(system) == len(stock) == 72 and all(
          math.isclose(r["STINT"], i / 2, abs_tol=1e-8) and
          math.isclose(r["ETINT"], (i + 1) / 2, abs_tol=1e-8) and
          math.isclose(stock[i]["STINT"], i / 2, abs_tol=1e-8) and
          math.isclose(stock[i]["ETINT"], (i + 1) / 2, abs_tol=1e-8)
          for i, r in enumerate(system)), f"{run_id}: 72 aligned bins", failures, counter)
    check(all(0 <= (r[key] or 0) <= 1 + 1e-6
              for r in system for key in ("NSYA", "NSYRY", "NSYMA", "NSYMO", "NSYRP"))
          and all((r["NFAIL"] or 0) >= 0 and (r["NREPT"] or 0) >= 0 for r in system),
          f"{run_id}: bounded System ledger", failures, counter)
    fail_mean = sum(float(r["NFAIL"] or 0) for r in system)
    repair_mean = sum(float(r["NREPT"] or 0) for r in system)
    failures_256 = round(fail_mean * 256)
    repairs_256 = round(repair_mean * 256)
    check(math.isclose(fail_mean * 256, failures_256, abs_tol=1e-5)
          and math.isclose(repair_mean * 256, repairs_256, abs_tol=1e-5)
          and failures_256 == repairs_256,
          f"{run_id}: integer aggregate failure/repair counts", failures, counter)
    check(all((r.get("NBO") or 0) == 0 and (r.get("NDF") or 0) == 0
              and (r.get("NDD") or 0) == 0 and (r.get("NDR") or 0) == 0
              and (r.get("NDP") or 0) == 0 and (r.get("NLD") or 0) == 0
              and (r.get("NWT") or 0) == 0 for r in stock),
          f"{run_id}: no stock demand", failures, counter)
    check(system[-1].get("NSYRY") == 1 and system[-1].get("NSYRP") == 0,
          f"{run_id}: terminal ready", failures, counter)
    events = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    first_modes = re.findall(r"system CM task \d+ on <TEACH-AIR-01,0> FMID: (FM-POS-[AB])", events)
    observed_failures = re.findall(
        r"critical CM failure mode added, now\s+\d+ failures:\s+Failure Mode: (FM-POS-[AB]) on materiel: <(POS-A|POS-B-CH),\d+> connection path: ([^\n]+)",
        events)
    check(first_modes == [mode for mode, _, _ in observed_failures]
          and all((mode == "FM-POS-A" and position == "POS-A") or
                  (mode == "FM-POS-B" and position == "POS-B-CH" and
                   " - POS-B - POS-B-CH" in path)
                  for mode, position, path in observed_failures),
          f"{run_id}: first-replication CM modes", failures, counter)
    one_level_arm = arm.removeprefix("nested-")
    one_level_run = ONE_LEVEL / f"g02-var03-seed{seed:02d}-{one_level_arm}-20261002-01"
    reference_record = reference[one_level_run.name]
    check(reference_record["report_sha256"] == digest(one_level_run / "report-raw.json")
          and reference_record["input_sha256"] == digest(one_level_run / "input.json"),
          f"{run_id}: published one-level reference seal", failures, counter)
    one_level_report = read_json(one_level_run / "report-raw.json", native=True)
    def without_description(doc: dict) -> dict:
        clean = deepcopy(doc)
        clean["report"]["tables"] = [t for t in clean["report"]["tables"]
                                      if t["name"] != "ProblemDescription"]
        return clean
    this_tables = {t["name"]: t for t in without_description(report)["report"]["tables"]}
    ref_tables = {t["name"]: t for t in without_description(one_level_report)["report"]["tables"]}
    report_differences = sorted(name for name in set(this_tables) | set(ref_tables)
                                if this_tables.get(name) != ref_tables.get(name))
    return {
        "run_id": run_id, "seed": seed, "arm": arm,
        "input_sha256": digest(actual_input), "invocation_sha256": digest(run / "invocation.json"),
        "closure_sha256": digest(run / "closure.json"),
        "report_sha256": digest(run / "report-raw.json"),
        "model_log_sha256": digest(run / "model.log"),
        "failures_per_256": failures_256, "repairs_per_256": repairs_256,
        "mtmf": summary[0]["MTMF"], "msuf": summary[0]["MSUF"],
        "first_rep_cm_modes": first_modes,
        "nested_b_failure_paths": [path for mode, _, path in observed_failures if mode == "FM-POS-B"],
        "one_level_reference_run": one_level_run.name,
        "one_level_reference_report_sha256": digest(one_level_run / "report-raw.json"),
        "one_level_table_differences_excluding_description": report_differences,
        "one_level_report_equal_excluding_description": not report_differences,
    }


def contrast(records: list[dict], arm: str) -> dict:
    by = {(r["seed"], r["arm"]): r for r in records}
    differences = [by[(seed, arm)]["failures_per_256"] - by[(seed, "nested-baseline")]["failures_per_256"]
                   for seed in SEEDS]
    n = len(differences)
    avg = statistics.mean(differences)
    sd = statistics.stdev(differences)
    half = T975_DF11 * sd / math.sqrt(n)
    positives = sum(d > 0 for d in differences)
    # Under an exchangeable symmetric sign null, each independent seed's sign
    # is Bernoulli(1/2). Zeros are retained as nonpositive, per the contract.
    p_one_sided = sum(math.comb(n, k) for k in range(positives, n + 1)) / (2 ** n)
    return {"arm": arm, "paired_differences_failures_per_256": differences,
            "mean_difference": avg, "sample_sd": sd,
            "nominal_student_t_95_interval": [avg - half, avg + half],
            "positive_seeds": positives, "one_sided_exact_sign_p": p_one_sided,
            "bonferroni_threshold": 0.025,
            "predeclared_direction_pass": avg > 0 and p_one_sided < 0.025}


def main() -> None:
    contract = read_json(CONTRACT)
    parent_raw = PARENT.read_bytes()
    assert digest(PARENT) == contract["direct_parent"]["input_sha256"]
    assert digest(MANUAL) == contract["source"]["manual_sha256"]
    assert digest(DICTIONARY) == contract["source"]["dictionary_sha256"]
    assert digest(EXE) == contract["source"]["exe_sha256"]
    assert tuple(contract["panel"]["seeds"]) == SEEDS
    assert tuple(contract["panel"]["variants_per_seed"]) == ARMS
    assert contract["panel"]["replications_per_variant_seed"] == 256
    parent = json.loads(parent_raw)
    index = read_json(ONE_LEVEL_INDEX)
    assert index["case_id"] == "G02" and index["variant_id"] == "G02.var03"
    reference = {r["run_id"]: r for r in index["accepted_runs"]}
    assert len(reference) == 36
    failures: list[str] = []
    counter = [0]
    records = [check_run(seed, arm, contract, parent, reference, failures, counter)
               for seed in SEEDS for arm in ARMS]
    check(len(records) == 36, "36 run matrix", failures, counter)
    contrasts = [contrast(records, arm) for arm in ARMS[1:]]
    check(all(x["predeclared_direction_pass"] for x in contrasts),
          "predeclared positive contrasts", failures, counter)
    check(any(r["nested_b_failure_paths"] for r in records),
          "at least one first-replication nested B path", failures, counter)
    reference_mismatches = [r["run_id"] for r in records
                            if not r["one_level_report_equal_excluding_description"]]
    result = {
        "schema": "simlox-g02-var02-independent-nested-seed-panel/v1",
        "reviewer": "independent standard-library raw replay; no author module imports",
        "contract_sha256": digest(CONTRACT), "parent_input_sha256": digest(PARENT),
        "one_level_published_index_sha256": digest(ONE_LEVEL_INDEX),
        "run_count": len(records), "raw_seal_count": len(records) * len(RAW),
        "check_count": counter[0], "failures": failures, "passed": not failures,
        "verdict": "GO_BOUNDED_SEED_PANEL" if not failures else "NO_GO",
        "runs": records, "contrasts": contrasts,
        "one_level_reference_comparison": {
            "matched_runs": len(records) - len(reference_mismatches),
            "mismatched_runs": reference_mismatches,
            "scope": "observed report equality after excluding ProblemDescription, not a general structural equivalence claim",
        },
        "limits": [
            "Each report contains 256-replication aggregate bin averages; the first-only ENLOG cannot attribute all aggregate failures to a position or show the other 255 event histories.",
            "The Student t intervals are nominal across twelve selected pseudo-random seeds; exact sign p values require an independent symmetric-sign null and do not prove a population law.",
            "QTYPM=2 changes ancestor multiplicity, while ENVF=2 changes its environment factor. Positive contrasts do not prove equal mechanisms, exact doubling, or physical replacement multiplicity.",
            "All 36 nested/one-level report matches are observations for this panel. The nested first-replication path differs, and report equality does not establish generic one-level/multilevel equivalence.",
            "The scope is this SIMLOX installation, fixed source/horizon, seeds 2 through 13, and these three models.",
        ],
    }
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": counter[0],
                      "failures": failures, "contrasts": contrasts}, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

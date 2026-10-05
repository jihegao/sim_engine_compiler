"""Independent, read-only replay of the sealed E03.var01 CLI evidence."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "e03-var01-single-v010-ssh-20261006-01"
OUT = Path(__file__).with_name("independent-verdict.json")
PARENT = CASES / "E03-two-aircraft-shared-spare-v1.0.0"
EXPECTED_SOURCE = {
    "input": (CASE / "native-input.json", "0fd7210b04aa8383a7288d3af0374fc96265c19f8d315612bee23a85c4d63879"),
    "parent": (PARENT / "native-input.json", "657c0d52116c09ef2dbd009209f461f6fb4ed3570327c4305e0e4608f208cbf0"),
    "parent_signoff": (PARENT / "cli-scope-signoff-2026-09-29.md", "dedf59901c805c7bbfd6c7421f02d0b051d0fbbc38c97819970988203e47c4e1"),
    "parent_closure": (PARENT / "runs" / "e03-v100-ssh-20260929-01" / "closure.json", "b200b18fbbed80dcc7ff9e9f4e2e1d7952734449b49a400a509d054090a9b7d6"),
    "e02_signoff": (CASES / "E02-zero-stock-local-backorder-v1.0.0" / "cli-scope-signoff-2026-09-29.md", "c28abcac8c3b8a55d0f58adf87ec3038555102d6b7bc2b35dc84ab9793e42ad6"),
    "a03_signoff": (CASES / "A03-two-aircraft-formation-v1.0.1" / "cli-scope-signoff-2026-09-29.md", "6c8d3998f20e216d0403b807866fcbe306f68ebc6f376693334435e808747b2b"),
    "contract": (CASE / "contract.json", "b9b64467ebf0f9d8864e4a440fcab0ccaff6994ea6e065cd144396da069c5f6c"),
    "builder": (CASE / "build.py", "2f5184f2fe9dd4557a23fa32e9ddd1cd7fdc12a524522943764b4d4f22dab601"),
    "checker": (CASE / "check_roundtrip.py", "d51f8a1e49609db7340c3e556574d2b237010bb51b0cef7282dd78177571b1c1"),
    "diff_checker": (CASE / "check_parent_diff.py", "50df24e315c0430d02d40ba6818da04f67d0cf09fbdcc202d1eaf3bbb509b8a2"),
    "validator": (CASE / "validate_native_cli.py", "b88c25d1e8b94ee2b52e6ca53ca0d376f30524d36259a97bb6a00a7102875967"),
    "runner_script": (CASE / "run_native_ssh.ps1", "90f35bb930e25e77e81ac805bb31b3fce6ae105e31f93dc8f7c12035ad6ab25e"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def js(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report_js(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    # Native -jsonreport has trailing commas. Normalize only this parser copy.
    return json.loads(re.sub(r",\s*(?=[}\]])", "", raw))


def tables(model: dict) -> dict:
    return {t["name"]: t for t in model["model"]["tables"]}


def rows(table: dict) -> list:
    return [r for inst in table["instances"] for r in inst["rows"]]


def report_rows(report: dict, name: str) -> list[dict]:
    t = next(t for t in report["report"]["tables"] if t["name"] == name)
    assert len(t["instances"]) == 1
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, r)) for r in t["instances"][0]["rows"]]


def near(a: float, b: float, tol: float = 3e-5) -> bool:
    return math.isclose(float(0 if a is None else a), float(0 if b is None else b), rel_tol=0, abs_tol=tol)


def overlap(a: float, b: float, start: float, end: float) -> float:
    return max(0.0, min(b, end) - max(a, start))


def main() -> dict:
    failed: list[str] = []
    checks = 0

    def ck(label: str, result: bool) -> None:
        nonlocal checks
        checks += 1
        if not result:
            failed.append(label)

    closure = js(RUN / "closure.json")
    invocation = js(RUN / "invocation.json")
    ck("run identity", closure["run_id"] == RUN.name)
    ck("immutable invocation", sha(RUN / "invocation.json") == closure["invocation_sha256"])
    ck("no runner error", closure["error"] is None)
    ck("candidate unpublished", closure["publication_state"] == "not_published")
    for key, (path, digest) in EXPECTED_SOURCE.items():
        ck(f"source {key} disk pin", path.is_file() and sha(path) == digest)
        ck(f"source {key} before", closure["source_hashes_before"].get(key) == digest)
        ck(f"source {key} after", closure["source_hashes_after"].get(key) == digest)
    ck("all source before/after", closure["source_hashes_before"] == closure["source_hashes_after"])
    ck("copied native input", (RUN / "input.json").read_bytes() == (CASE / "native-input.json").read_bytes())
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw {name} bytes", path.is_file() and path.stat().st_size == seal["bytes"])
        ck(f"raw {name} SHA", path.is_file() and sha(path) == seal["sha256"])
    ck("12 raw seals", len(closure["raw"]) == 12)
    parent_closure = js(EXPECTED_SOURCE["parent_closure"][0])
    parent_run = EXPECTED_SOURCE["parent_closure"][0].parent
    ck("parent 12 raw seals", len(parent_closure["raw"]) == 12)
    for name, seal in parent_closure["raw"].items():
        path = parent_run / name
        ck(f"parent raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])

    steps = js(RUN / "steps.json")
    ck("five recorded stages", [s["name"] for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport"])
    for step in steps:
        ck(f"step {step['name']} succeeded", step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] is True)
    ck("SSH session zero", invocation.get("ssh_session_id") == 0 or invocation.get("session_id") == 0)
    ck("valid SXO", (RUN / "model.sxo").stat().st_size > 1000)
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
    ck("converter 0/1/0", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog)
    ck("sole #108", re.findall(r"\((?:warning|error|note) #(\d+)\)", runlog) == ["108"])

    authored = tables(js(CASE / "native-input.json"))
    exported = tables(js(RUN / "roundtrip-raw.json"))
    parent = tables(js(EXPECTED_SOURCE["parent"][0]))
    populated = [name for name, table in authored.items() if rows(table)]
    ck("20 authored row-containing tables", len(populated) == 20)
    for name in populated:
        a, e = authored[name], exported[name]
        ck(f"roundtrip {name} columns", [(c["name"], c["datatype"]) for c in a["columns"]] == [(c["name"], c["datatype"]) for c in e["columns"]])
        ck(f"roundtrip {name} instances/rows", [(i["instance_name"], i["rows"]) for i in a["instances"]] == [(i["instance_name"], i["rows"]) for i in e["instances"]])
    changed = []
    for name in parent:
        if name not in authored:
            changed.append((name, "missing"))
            continue
        p, a = parent[name], authored[name]
        ck(f"source {name} columns", p["columns"] == a["columns"])
        pr, ar = rows(p), rows(a)
        ck(f"source {name} row count", len(pr) == len(ar))
        for ri, (rp, ra) in enumerate(zip(pr, ar)):
            for ci, (vp, va) in enumerate(zip(rp, ra)):
                if vp != va:
                    changed.append((name, ri, p["columns"][ci]["name"], vp, va))
    ck("parent-child exact two-cell delta", len(changed) == 2 and {tuple(c[:3]) for c in changed} == {("ProblemDescription", 0, "PDESC"), ("OperationProfile", 0, "IQTY")})
    ck("IQTY 2 to 1", any(c[0] == "OperationProfile" and c[3:] == (2, 1) for c in changed))

    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    def time_for(fragment: str) -> float:
        hit = re.search(r"(?m)^Time: ([0-9.]+) .*" + re.escape(fragment), log)
        ck(f"event {fragment}", hit is not None)
        return float(hit.group(1)) if hit else float("nan")

    ck("one mission created", len(re.findall(r"mission created:", log)) == 1)
    ck("one mission launched", len(re.findall(r"mission starting, duration:", log)) == 1)
    ck("aircraft zero assigned", "mission allocates system: <TEACH-AIR-01,0>" in log)
    ck("mission aborted and completed", log.count("mission aborted:") == 1 and log.count("aborted mission completed:") == 1)
    ck("one critical failure", log.count("critical random failure added") == 1)
    ck("failed installed physical ID1", log.count("subitem failed: <TEACH-LRU-01,0,1>") == 2)
    demand = time_for("Item demand arrives from pos")
    issue = time_for("Take replacement item <TEACH-LRU-01,0,0> from stock")
    remove = time_for("remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed")
    fit = time_for("fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> completed")
    repair_start = time_for("Start repair of item <TEACH-LRU-01,0,1>")
    repair_end = time_for("Finished repair of item <TEACH-LRU-01,0,1>")
    failure = time_for("critical random failure added")
    ck("single physical demand/issue/return", log.count("Item demand arrives from pos") == 1 and log.count("Take replacement item") == 1 and log.count("Put back replacement item") == 1)
    ck("physical order", 8 < failure < demand == issue < remove == repair_start < fit < repair_end < 36)
    ck("half-hour system work", near(fit - demand, 0.5, 2e-5))
    ck("four-hour item repair", near(repair_end - repair_start, 4, 1e-4))
    ck("no backorder", "Backorder" not in log and "backorder" not in log.lower())
    ck("opening ID0 stock", "Level: 1 Items:<TEACH-LRU-01,0,0>" in log)
    ck("issue depletes physical stock", "Take replacement item <TEACH-LRU-01,0,0> from stock \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:" in log)
    ck("failed ID1 returned to stock", "Put back replacement item <TEACH-LRU-01,0,1> to stock \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>" in log)
    ready = re.findall(r"(?m)^Time: [0-9.]+ <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :(.*)$", log)
    terminal_ids = re.findall(r"<TEACH-AIR-01,([01])>", ready[-1]) if ready else []
    ck("terminal aircraft set", len(terminal_ids) == 2 and set(terminal_ids) == {"0", "1"})
    ck("author ordering false negative", terminal_ids == ["1", "0"] and js(CASE / "review" / "author-replay-v010-failed.json")["differences"] == ["terminal aircraft ready"])
    corrected = js(CASE / "review" / "author-replay-v011.json")
    ck("corrected author replay bounded", corrected["passed"] is True and corrected["checks"] == 64 and corrected["frozen_prelaunch_validator_sha256"] == EXPECTED_SOURCE["validator"][1])

    rep = report_js(RUN / "report-raw.json")
    system = report_rows(rep, "SystemResults")
    stock = report_rows(rep, "StockTotalResults")
    summary = report_rows(rep, "ResultSummary")
    ck("report 72+72 bins", len(system) == len(stock) == 72)
    ck("one summary row", len(summary) == 1)
    if summary:
        ck("single aborted mission summary", summary[0]["NREP"] == 1 and summary[0]["MSTF"] == 1 and summary[0]["MSUF"] == 0)
        ck("failure time summary", near(summary[0]["MTMF"], failure, 2e-5) is False and near(summary[0]["MTMF"], failure - 8, 2e-5))
    sys_nonzero = {"STINT", "ETINT", "NSYRY", "NSYA", "NSYMA", "NSYMR", "NSYMO", "NSYUA", "FTMO", "NSYRP", "NFAIL", "STACC", "SYDT", "NSYDT", "NREPT"}
    stk_nonzero = {"STINT", "ETINT", "PNB", "NDF", "NWT"}
    for i, (sr, tr) in enumerate(zip(system, stock)):
        a, b = i / 2, (i + 1) / 2
        ck(f"system grid {i}", near(sr["STINT"], a, 1e-9) and near(sr["ETINT"], b, 1e-9))
        ck(f"stock grid {i}", near(tr["STINT"], a, 1e-9) and near(tr["ETINT"], b, 1e-9))
        prep = overlap(a, b, 7, 8) / 0.5
        mission = overlap(a, b, 8, demand) / 0.5
        work = overlap(a, b, demand, fit) / 0.5
        ck(f"system occupation {i}", all(near(sr[k], v) for k, v in {
            "NSYMR": prep, "NSYMA": prep + mission, "NSYMO": mission,
            "NSYRP": work, "NSYUA": work, "NSYRY": 2 - prep - mission - work,
            "NSYA": 2 - work, "STACC": mission,
        }.items()))
        ck(f"system event counts {i}", sr["NFAIL"] == int(a <= failure < b) and sr["NREPT"] == int(a <= fit < b) and sr["NSYDT"] == int(a <= failure < b))
        ck(f"stock event counts {i}", tr["NDF"] == int(a <= demand < b) and tr["NWT"] == int(a <= demand < b) and tr["NBO"] == 0 and tr["PNB"] == 1)
        ck(f"zero other system fields {i}", all(v == 0 for k, v in sr.items() if k not in sys_nonzero and isinstance(v, (int, float))))
        ck(f"zero other stock fields {i}", all(v == 0 for k, v in tr.items() if k not in stk_nonzero and isinstance(v, (int, float))))
        ck(f"flight/downtime {i}", near(sr["FTMO"], overlap(a, b, 8, demand), 3e-5) and near(sr["SYDT"], 0.5 if a <= failure < b else 0))
    ck("system availability integral", near(sum(r["NSYA"] * 0.5 for r in system), 71.5, 2e-5))
    ck("system repair occupancy integral", near(sum(r["NSYRP"] * 0.5 for r in system), 0.5, 2e-5))
    ck("one failure/repair/demand", sum(r["NFAIL"] for r in system) == sum(r["NREPT"] for r in system) == sum(r["NDF"] for r in stock) == 1)
    ck("no backorder in all bins", all(r["NBO"] == 0 for r in stock))

    verdict = {
        "schema": "simlox-e03-var01-v010-independent-postrun/v1",
        "run_id": RUN.name,
        "verdict": "GO_BOUNDED" if not failed else "NO_GO",
        "checks": checks,
        "passed_checks": checks - len(failed),
        "differences": failed,
        "closure_sha256": sha(RUN / "closure.json"),
        "invocation_sha256": sha(RUN / "invocation.json"),
        "model_log_sha256": sha(RUN / "model.log"),
        "report_raw_sha256": sha(RUN / "report-raw.json"),
        "terminal_ready_ids_in_logged_order": terminal_ids,
        "physical_timeline_hours": {"failure": failure, "demand_and_spare_issue": demand, "remove_complete_and_item_repair_start": remove, "fit_complete_and_aircraft_ready": fit, "item_repair_complete_and_restock": repair_end},
        "scope": "one seeded mission, one observed physical LRU demand, no backorder; CLI event/report replay only",
        "limits": ["terminal ready list order has no identity meaning", "StockTotalResults.PNB is not physical on-hand inventory", "installed spare ID0 is issued and fitted by the SURP task, but no separate installed-ID inventory table is claimed", "not a general stock-allocation policy or controlled stochastic causal estimate"],
    }
    OUT.write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return verdict


if __name__ == "__main__":
    result = main()
    print(f"{result['verdict']} {result['passed_checks']}/{result['checks']}")
    for difference in result["differences"]:
        print("FAIL", difference)
    raise SystemExit(0 if result["verdict"] == "GO_BOUNDED" else 1)

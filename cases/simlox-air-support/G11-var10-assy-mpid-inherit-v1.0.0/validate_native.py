"""Read-only author replay of one ASSY/MPID inherited Prelife native run."""
import hashlib
import json
import re
from pathlib import Path
from check_roundtrip import native_json, populated

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/g11-var10-assy-inherit-v100-ssh-20261003-01"
PARENT = HERE.parent / "G11-var04-inherit-item-prelife-v1.0.1"
PARENT_RUN = PARENT / "runs/g11-var04-explicit-control-v101-ssh-20261002-01"
PARENT_SHA = "76cd71fe989b84a8f8c5c23007926a417c8f01c820cfc534846216e4a9fe7311"
PARENT_CLOSURE = "60ae9d2e2feadb6843cec3d1bb53c7afa7b59fc9374d5a35018df1aa1a2cb4f7"
INPUT_SHA = "859db9ad998d8350b76bed1962473353015026b3e66ab6e31481f277774b0879"
CONTRACT_SHA = "3d7b2f65bdd18858ca90168460f91598fac269de7271a25b60738ef78b5be48a"
DIFF_SHA = "b65fa682b7cd13b88488ccea084efec13364ebd15215976ac8e3048b760efacd"

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding="utf-8-sig"))
def rows(doc, name):
    t = next(t for t in doc["model"]["tables"] if t["name"] == name)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row)) for inst in t["instances"] for row in inst["rows"]]
def vals(t, field):
    i = [c["name"] for c in t["columns"]].index(field)
    return [row[i] for inst in t["instances"] for row in inst["rows"]]
class Audit:
    def __init__(self): self.checks, self.errors = 0, []
    def need(self, ok, label):
        self.checks += 1
        if not ok: self.errors.append(label)

def main():
    a = Audit()
    for name, path, expected in (("parent", PARENT / "native-input-explicit-control.json", PARENT_SHA), ("parent closure", PARENT_RUN / "closure.json", PARENT_CLOSURE), ("input", HERE / "native-input-assy-inherit.json", INPUT_SHA), ("contract", HERE / "contract.json", CONTRACT_SHA), ("diff", HERE / "exact-diff.json", DIFF_SHA)):
        a.need(sha(path) == expected, f"{name} SHA")
    source, parent = native_json(HERE / "native-input-assy-inherit.json"), native_json(PARENT / "native-input-explicit-control.json")
    before = {t["name"]: t for t in parent["model"]["tables"]}; after = {t["name"]: t for t in source["model"]["tables"]}
    a.need({n for n in after if after[n] != before[n]} == {"Item", "MaterielStructure", "Prelife", "PrelifeData", "PrelifeStructure", "ProblemDescription"}, "six-table delta")
    physical = rows(source, "MaterielStructure")
    a.need([(r["MID"], r["MMID"]) for r in physical] == [("TEACH-ASSY-01", "TEACH-AIR-01"), ("POS-A", "TEACH-ASSY-01"), ("TEACH-LRU-01", "POS-A")], "physical path")
    assy = [r for r in rows(source, "Item") if r["IID"] == "TEACH-ASSY-01"]
    a.need(len(assy) == 1 and assy[0]["TYPE"] == "ASSY" and all(v is None for k, v in assy[0].items() if k not in {"IID", "DESCR", "TYPE"}), "non-logistics ASSY")
    a.need([(r["PLID"], r["MPLID"], r["MPLIND"]) for r in rows(source, "PrelifeStructure")] == [("PL-ASSY", "PL-SYS", "SYS-60"), ("PL-POS", "PL-ASSY", "ASSY-INH"), ("PL-LRU", "PL-POS", "POS-INH")], "prelife path")
    a.need([(r["PLID"], r["TYPE"], r["AGE"]) for r in rows(source, "PrelifeData")] == [("PL-SYS", "FIXED", 60), ("PL-ASSY", "INHERIT", 0), ("PL-POS", "INHERIT", 0), ("PL-LRU", "FIXED", 20)], "prelife age types")
    for table in ("StockAllocation", "ItemRepair", "ItemReplacement", "PMReplacement"):
        a.need(all("TEACH-ASSY-01" not in r.values() for r in rows(source, table)), f"ASSY absent {table}")
    closure, invocation, steps = (read(RUN / n) for n in ("closure.json", "invocation.json", "steps.json"))
    a.need(closure["arm"] == "assy-inherit" and closure["run_id"] == RUN.name and closure["error"] is None, "closure identity")
    a.need(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    a.need(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH session")
    a.need(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "GUI guard")
    a.need(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "queue mutex")
    a.need(invocation["prelife_log_option_before"] == "NO" and closure["prelife_log_option_after"] == "NO", "registry restore")
    a.need([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "five steps")
    for s in steps: a.need(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"], f"step {s['name']}")
    for key, digest in {"input": INPUT_SHA, "parent": PARENT_SHA, "parent_closure": PARENT_CLOSURE, "contract": CONTRACT_SHA, "exact_diff": DIFF_SHA}.items(): a.need(closure["source_hashes_before"].get(key) == digest, f"pinned {key}")
    for key, digest in closure["source_hashes_before"].items(): a.need(closure["source_hashes_after"].get(key) == digest, f"source unchanged {key}")
    a.need(len(closure["raw"]) == 13, "raw count")
    for name, seal in closure["raw"].items():
        p = RUN / name
        a.need(p.is_file() and p.stat().st_size == seal["bytes"] and sha(p) == seal["sha256"], f"raw {name}")
    roundtrip = read(RUN / "roundtrip-validation.json")
    authored, exported = populated(native_json(RUN / "input.json")), populated(native_json(RUN / "roundtrip-raw.json"))
    a.need(roundtrip["passed"] and not roundtrip["differences"] and len(authored) == 23 and roundtrip["populated_tables"] == sorted(authored), "roundtrip verdict")
    for name, body in authored.items(): a.need(exported.get(name) == body, f"roundtrip {name}")
    log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    a.need(re.findall(r"\(warning #(\d+)\)", log) == ["108"] and "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in log and "(error #" not in log and "(notice #" not in log, "conversion gate")
    prelife = (RUN / "model_Prelife.log").read_text(encoding="utf-8-sig")
    ages = [(m, n, float(x)) for m, n, x in re.findall(r"\*\*(TEACH-AIR-01|TEACH-ASSY-01|POS-A|TEACH-LRU-01)\*\*([^*]+)\*\* Age\[CALHOURS\]:([0-9.]+)", prelife)]
    a.need(ages == [("TEACH-AIR-01", "SYS-60", 60.), ("TEACH-ASSY-01", "ASSY-INH", 60.), ("POS-A", "POS-INH", 60.), ("TEACH-LRU-01", "LRU-20", 20.)], "native inherited ages")
    event = (RUN / "model.log").read_text(encoding="utf-8-sig")
    for pattern, times in ((r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,0> started", [80.]), (r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed", [80.5]), (r"Time: ([0-9.]+)  item PM task \d+ on <TEACH-LRU-01,0,0> started", [80.25]), (r"Time: ([0-9.]+)  item PM task \d+ on <TEACH-LRU-01,0,0> completed", [81.25])):
        a.need([float(x) for x in re.findall(pattern, event)] == times, f"PM {pattern[-12:]}")
    a.need(re.findall(r"item requiring maintenance is <TEACH-LRU-01,0,(\d+)>", event) == ["0"] and re.findall(r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock", event) == ["2"] and re.findall(r"Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock", event) == ["0"], "physical stock route")
    a.need("TEACH-ASSY-01" not in event and "backorder" not in event.lower() and not re.search(r"mission (started|success:|cancelled)", event, re.I), "ASSY/logistics/mission exclusions")
    report = {t["name"]: t for t in native_json(RUN / "report-raw.json")["report"]["tables"]}
    prior = {t["name"]: t for t in native_json(PARENT_RUN / "report-raw.json")["report"]["tables"]}
    a.need(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report tables")
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"): a.need(report[name] == prior[name], f"parent report {name}")
    for name in ("SystemResults", "StockTotalResults"):
        starts, ends = vals(report[name], "STINT"), vals(report[name], "ETINT")
        a.need(len(starts) == 192 and starts[0] == 0 and ends[-1] == 96 and all(x == y for x, y in zip(ends, starts[1:])), f"{name} bins")
    a.need(vals(report["SystemResults"], "NSYRY")[-1] == 1 and vals(report["StockTotalResults"], "PNB")[-1] == 1, "terminal ready/stock")
    result = {"schema": "simlox-g11-var10-assy-mpid-inherit-author-replay/v1", "case_id": "G11", "variant_id": "G11.var10", "version": "1.0.0", "checks": a.checks, "passed_checks": a.checks-len(a.errors), "passed": not a.errors, "differences": a.errors, "run_id": RUN.name, "closure_sha256": sha(RUN / "closure.json"), "prelife_log_sha256": sha(RUN / "model_Prelife.log"), "event_log_sha256": sha(RUN / "model.log"), "report_sha256": sha(RUN / "report-raw.json"), "native_prelife_path": ages, "scope": "one inherited ASSY and MPID above fixed-age LRU, first PM only", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1

if __name__ == "__main__": raise SystemExit(main())

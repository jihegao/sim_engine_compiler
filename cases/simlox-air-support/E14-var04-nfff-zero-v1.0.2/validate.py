"""Replay the frozen E14.var04 one-cell JSON-import rejection."""

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
RUN = HERE / "runs" / CONTRACT["run_id"]
PRIOR = HERE.parent / CONTRACT["previous_excluded"]["package"]
PRIOR_RUN = PRIOR / "runs" / CONTRACT["previous_excluded"]["run_id"]
checks = 0


def check(value, label):
    global checks
    checks += 1
    if not value:
        raise AssertionError(label)


def pin(path, sha, size=None):
    data = path.read_bytes()
    check(hashlib.sha256(data).hexdigest() == sha, f"hash {path}")
    if size is not None:
        check(len(data) == size, f"bytes {path}")
    return data


check(CONTRACT["variant_id"] == "E14.var04" and CONTRACT["version"] == "1.0.2-candidate", "contract identity")
prior = CONTRACT["previous_excluded"]
pin(PRIOR_RUN / "closure.json", prior["closure_sha256"])
pin(PRIOR_RUN / "import.log", prior["import_log_sha256"])
pin(PRIOR / "evidence-index.json", prior["index_sha256"])
closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
check(closure["run_id"] == CONTRACT["run_id"] and closure["expected_negative"] and closure["error"] is None, "closure verdict")
pin(RUN / "invocation.json", closure["invocation_sha256"])
check(closure["source_hashes_before"] == closure["source_hashes_after"], "source unchanged")
check(len(closure["raw"]) == 8, "eight raw seals")
for name, meta in closure["raw"].items():
    pin(RUN / name, meta["sha256"], meta["bytes"])
pin(RUN / "input.json", CONTRACT["source"]["input_sha256"])
outcome = json.loads((RUN / "outcome.json").read_text(encoding="utf-8-sig"))
check(outcome["expected_negative"] and outcome["error"] is None, "outcome gate")
check(outcome["import_export"] == "target_nfff_erased_only", "roundtrip gate")
log = (RUN / "import.log").read_text(encoding="utf-8-sig")
rejections = re.findall(r"Value \([^)]*\) in record: \d+, Column: \S+ Table: \S+ cannot be imported[^\r\n]*", log)
check(len(rejections) == 1 and rejections[0].startswith("Value (0) in record: 2, Column: NFFF Table: ItemStructure cannot be imported"), "sole target rejection")
check(outcome["import_diagnostic"] == rejections[0], "recorded diagnostic")
source = json.loads((RUN / "input.json").read_text(encoding="utf-8-sig"))
exported = json.loads((RUN / "roundtrip-raw.json").read_text(encoding="utf-8-sig"))
source_tables = {t["name"]: t for t in source["model"]["tables"]}
export_tables = {t["name"]: t for t in exported["model"]["tables"]}
populated = [name for name, t in source_tables.items() if any(i["rows"] for i in t["instances"])]
check(len(source_tables) == 31 and len(populated) == 21, "table cardinality")
for name in populated:
    before = [row for i in source_tables[name]["instances"] for row in i["rows"]]
    after = [row for i in export_tables[name]["instances"] for row in i["rows"]]
    check(source_tables[name]["columns"] == export_tables[name]["columns"], f"columns {name}")
    if name == "ItemStructure":
        check(before[1][0] == "TEACH-SRU-01" and before[1][4] == 4 and before[1][6] == 0, "target input")
        before[1][6] = None
    check(before == after, f"authored rows {name}")
steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
check([s["name"] for s in steps] == ["import", "export"], "only two native stages")
for step in steps:
    check(step["exit_code"] == 0 and step["gui_preserved"] and step["status"] == "completed", f"step {step['name']}")
check(not any((RUN / name).exists() for name in ("run.log", "model.sxo", "model.log", "selected-report-raw.json")), "no calc/simulation/report")
verdict = {"schema": "simlox-e14-var04-author-import-negative-validation/v1", "verdict": "GO_BOUNDED_IMPORT_NEGATIVE",
           "checks": checks, "passed": checks, "raw_seals": 8, "run_id": CONTRACT["run_id"],
           "scope": "One NFFF0 JSON-import cell rejection/erasure; no converter or physical simulation claim"}
(HERE / "review" / "author-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(verdict))

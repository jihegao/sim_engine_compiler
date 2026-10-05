"""Source-bound validation of the one E14.var05 calc-only converter negative."""

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
OLD = HERE.parent / CONTRACT["frozen_failed_import_arm"]["package"]
OLD_RUN = OLD / "runs" / CONTRACT["frozen_failed_import_arm"]["run_id"]
RUN = HERE / "runs" / CONTRACT["run_id"]
checks = 0


def check(value, label):
    global checks
    checks += 1
    if not value:
        raise AssertionError(label)


def pin(path, expected, size=None):
    raw = path.read_bytes()
    check(hashlib.sha256(raw).hexdigest() == expected, f"SHA {path}")
    if size is not None:
        check(len(raw) == size, f"size {path}")
    return raw


old = CONTRACT["frozen_failed_import_arm"]
check(CONTRACT["variant_id"] == "E14.var05" and CONTRACT["version"] == "1.0.1-candidate", "contract identity")
pin(OLD / "contract.json", old["contract_sha256"])
pin(OLD_RUN / "input.json", old["input_sha256"])
pin(OLD_RUN / "model.sxi", old["sxi_sha256"], old["sxi_bytes"])
pin(OLD_RUN / "import.log", old["import_log_sha256"])
pin(OLD_RUN / "roundtrip-raw.json", old["roundtrip_export_sha256"])
old_closure = json.loads(pin(OLD_RUN / "closure.json", old["closure_sha256"]))
check(len(old_closure["raw"]) == 8, "old raw count")
for name, item in old_closure["raw"].items():
    pin(OLD_RUN / name, item["sha256"], item["bytes"])
check(old_closure["source_hashes_before"] == old_closure["source_hashes_after"], "old source stability")

source = json.loads((OLD_RUN / "input.json").read_text(encoding="utf-8-sig"))
exported = json.loads((OLD_RUN / "roundtrip-raw.json").read_text(encoding="utf-8-sig"))
for doc in (source, exported):
    structure = next(t for t in doc["model"]["tables"] if t["name"] == "ItemStructure")
    row = structure["instances"][0]["rows"][1]
    check(row[0] == "TEACH-SRU-01" and row[4] == 4 and row[6] == 5, "NFFF5/RRF4 retained")

closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
invocation = pin(RUN / "invocation.json", closure["invocation_sha256"])
check(json.loads(invocation)["run_id"] == CONTRACT["run_id"], "new run identity")
check(closure["run_id"] == CONTRACT["run_id"] and closure["expected_negative"] and closure["error"] is None, "closure negative success")
check(closure["source_hashes_before"] == closure["source_hashes_after"], "new source stability")
check(len(closure["raw"]) == 5, "five calc raw seals")
for name, item in closure["raw"].items():
    pin(RUN / name, item["sha256"], item["bytes"])
pin(RUN / "model.sxi", old["sxi_sha256"], old["sxi_bytes"])
check((RUN / "model.sxo").stat().st_size == 4, "invalid four-byte SXO")
check(not any((RUN / name).exists() for name in ("model.log", "selected-report-raw.json")), "no event/report")
steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
check(len(steps) == 1 and steps[0]["name"] == "calc_converter_gate" and steps[0]["exit_code"] == 0 and steps[0]["gui_preserved"], "single guarded calc step")
outcome = json.loads((RUN / "outcome.json").read_text(encoding="utf-8-sig"))
check(outcome["converter_summary"] == [1, 1, 0], "converter summary")
check(outcome["error_codes"] == ["143"], "sole error 143")
check(outcome["copied_sxi_sha256_before"] == old["sxi_sha256"] == outcome["copied_sxi_sha256_after"], "SXI unchanged through calc")
check(outcome["copied_sxi_bytes_after"] == old["sxi_bytes"] and outcome["expected_negative"] and outcome["error"] is None, "accepted outcome")
log = (RUN / "run.log").read_text(encoding="utf-8-sig")
check(re.findall(r"\(warning #(\d+)\)", log) == ["108"], "only classified logging warning")
check(re.findall(r"\(error #(\d+)\)", log) == ["143"], "only target error")
check(re.search(r"Form: ItemStructure\s*\nrec 2: \(error #143\).*NFFF.*RRF.*TEACH-SRU-01/TEACH-LRU-01", log) is not None, "target relation attribution")
check(not (RUN / "model.log").exists(), "no simulated event log")

verdict = {"schema": "simlox-e14-var05-author-calc-negative-validation/v1", "passed": True,
           "checks": checks, "verdict": "GO_BOUNDED_CONVERTER_NEGATIVE",
           "run_id": CONTRACT["run_id"], "converter_errors": 1, "error_code": 143,
           "warning_code": 108, "old_raw_seals": 8, "new_raw_seals": 5,
           "scope": "One copied NFFF5/RRF4 SXI, one converter rejection; no invalid-input simulation or general upper-bound claim"}
(HERE / "review" / "author-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(verdict))

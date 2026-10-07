"""Independent read-only identity and report-shape preflight for B03.var01."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = next(p for p in HERE.parents if (p / ".git").exists())
CONTRACT = HERE / "contract.json"
EXPECTED = "7bb562507914516fffc2d4f30d9a28ba05dbd4d6f4150c0d475a921fa14e10b9"


def hash_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def check(path, pin):
    raw = path.read_bytes()
    assert len(raw) == pin["bytes"] and hash_bytes(raw) == pin["sha256"], str(path)
    return raw


def native_json(path):
    # SIMLOX output has structural trailing commas. This is a read-only shape
    # probe, not a substitute for the future string-aware full-cell parser.
    text = path.read_text(encoding="utf-8-sig")
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def main():
    assert hash_bytes(CONTRACT.read_bytes()) == EXPECTED
    c = json.loads(CONTRACT.read_bytes())
    assert c["case_id"] == "B03" and c["variant_id"] == "B03.var01"
    assert c["ownership"]["new_native_runs"] == 0
    assert len(c["accepted_source_files"]) == 38
    for pin in c["accepted_source_files"]:
        path = REPO / pin["path"]
        check(path, pin["local_disk"])
        blob = subprocess.run(["git", "show", c["base_commit"] + ":" + pin["path"]],
                              cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=True).stdout
        assert len(blob) == pin["published_git_at_base"]["bytes"]
        assert hash_bytes(blob) == pin["published_git_at_base"]["sha256"]
    for pin in c["installed"].values():
        check(Path(pin["path"]), pin)
    catalog = REPO / c["published_parent_scope"]["catalog_path"]
    check(catalog, c["published_parent_scope"]["catalog_snapshot_at_base"]["local_disk"])
    catalog_git = subprocess.run(["git", "show", c["base_commit"] + ":" + c["published_parent_scope"]["catalog_path"]],
                                 cwd=REPO, stdout=subprocess.PIPE, check=True).stdout
    assert len(catalog_git) == c["published_parent_scope"]["catalog_snapshot_at_base"]["published_git_at_base"]["bytes"]
    assert hash_bytes(catalog_git) == c["published_parent_scope"]["catalog_snapshot_at_base"]["published_git_at_base"]["sha256"]
    assert len(c["parent_runs"]) == 2
    for run in c["parent_runs"]:
        directory = Path(run["original_directory"])
        check(directory / "closure.json", run["closure"])
        check(directory / "invocation.json", run["invocation"])
        closure = json.loads((directory / "closure.json").read_text(encoding="utf-8-sig"))
        invocation = json.loads((directory / "invocation.json").read_text(encoding="utf-8-sig"))
        assert closure["run_id"] == invocation["run_id"] == run["run_id"]
        assert closure["raw"] == run["raw"]
        assert closure["invocation_sha256"] == run["invocation"]["sha256"]
        for name, pin in run["raw"].items():
            check(directory / name, pin)
        for name, pin in run["other_local_files"].items():
            check(directory / name, pin)
    good = c["parent_runs"][1]
    report = native_json(Path(good["original_directory"]) / "report-raw.json")
    tables = report["report"]["tables"]
    expected = c["full_report_gate"]["native_tables_in_order"]
    assert [t["name"] for t in tables] == [t["name"] for t in expected]
    shape = [(t["name"], sum(len(i["rows"]) for i in t["instances"]), len(t["columns"])) for t in tables]
    assert [(a, b, d) for a, b, d in shape] == [(x["name"], x["rows"], x["columns"]) for x in expected]
    assert sum(r * col for _, r, col in shape) == c["full_report_gate"]["total_cells"] == 4044
    print(json.dumps({"decision": "PASS_CONTRACT_BYTES_AND_SHAPE", "source_local_git": 38,
                      "installed": 3, "runs": 2, "raw": 22,
                      "report_tables": len(shape), "report_cells": 4044}, sort_keys=True))


if __name__ == "__main__":
    main()

"""Strict, deterministic B03.var01 v0.1.2 evidence index builder; dry by default."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PY = sys.executable
CONTRACT_SHA = "28765ddfeb99c595318d63cc0bd9e6a364bd2122d8a592b2fdd81a4d0a4cea44"
PINS = {
    "replay_v2.py": "d6d1798c7cb2428a59a70cf3040cbbe39af11fc79dfef5ca8624cbbe2018bcb9",
    "self_check_v2.py": "1ac865b65ad83f009a3f3753db87368ed2364d5615abdbbb7b369b4d0d7e0bc7",
    "METHOD-v2.md": "5fd93e80d75de41090d828f372d8b9e3d7d35b21b5f9f253174e7319c34a3a69",
    "author-verdict.json": "cfe5c599f9f20881e65b04e93bd1d9b00df76ff4aed7d27aec4c72fcb2601567",
    "review/independent-contract-go-2026-10-07.md": "8d2eba9d13389e04be02500ce0afb727a42fad6f75fef3d159c67188e8895917",
    "review/independent_replay_v4.py": "37d781293f2f6c9892598239296b18ac3c4d2e10473d042d74a2c3527fe3507f",
    "review/independent-verdict-v012.json": "8076bb5d9a17b4c50ea8bd184303226c033bf1d900277cb066bc3c3803e90b0c",
    "review/independent-postrun-go-2026-10-07.md": "78d9d8227813c88432678884c0f5ee11124e6e80f07d14fa2e9469c40e6ec24e",
    "preserved-root-v012-gates/custody-map.json": "a5f63a67249c09051dfc0732b7d01f6b43d2ba55be626ba21d8b79ae3dfd80b0",
    "raw-custody-map.json": "8163f63702e41eb5a362d086f2626ee45a1745dba1ba14d34fb1ba0ed1211c6b",
}
INDEX = HERE / "evidence-index.json"
EXCLUDED_REVIEW_PREFIXES = (
    "review/independent-content", "review/independent-staged", "review/independent-remote",
    "review/independent-publication", "review/independent-pr-",
)


def pin(path: Path) -> dict[str, object]:
    b = path.read_bytes()
    return {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def exact(path: Path, expected: dict[str, object]) -> None:
    assert pin(path) == {"bytes": expected["bytes"], "sha256": expected["sha256"]}, str(path)


def checked_command(name: str) -> dict[str, object]:
    completed = subprocess.run([PY, "-X", "utf8", "-B", str(HERE / name)],
                               cwd=REPO, capture_output=True)
    assert completed.returncode == 0 and not completed.stderr, (name, completed.stderr.decode("utf-8", "replace"))
    return json.loads(completed.stdout)


def historical_context(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    out = []
    for item in entries:
        original = REPO / item["original_path"]
        copy = HERE / item["inert_copy_path"]
        exact(copy, item)
        if original.exists():
            exact(original, item)
        out.append({"original_path": str(original), "copy_path": item["inert_copy_path"],
                    "bytes": item["bytes"], "sha256": item["sha256"],
                    "original_present_at_build": original.exists()})
    return out


def build() -> dict[str, object]:
    assert pin(HERE / "contract.json")["sha256"] == CONTRACT_SHA
    assert (HERE / ".gitattributes").read_bytes() == b"* -text\n"
    for name, sha in PINS.items():
        assert pin(HERE / name)["sha256"] == sha, name
    c = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    assert c["package"] == HERE.name and c["version"] == "0.1.2"
    assert c["preservation_and_limits"]["no_new_native"] is True
    author = checked_command("replay_v2.py")
    probes = checked_command("self_check_v2.py")
    independent = checked_command("review/independent_replay_v4.py")
    saved_author = json.loads((HERE / "author-verdict.json").read_text(encoding="utf-8"))
    saved_independent = json.loads((HERE / "review/independent-verdict-v012.json").read_text(encoding="utf-8"))
    assert author["decision"] == saved_author["decision"] == "GO_BOUNDED_AUTHOR_REPLAY"
    assert independent == saved_independent and independent["decision"] == "GO_BOUNDED"
    assert author["report_cells"] == independent["full_expected_report_cells"] == probes["baseline_cells"] == 4044
    assert probes["semantic_mutations_rejected"] == saved_author["semantic_mutations_rejected"] == 53
    assert independent["semantic_mutation_rejections"] == 35
    assert author["contract_sha256"] == independent["contract_sha256"] == CONTRACT_SHA
    assert author["new_native_runs"] == independent["new_native_runs"] == 0
    refs = []
    for item in c["accepted_source_files"]:
        original = REPO / item["path"]
        exact(original, item["local_disk"])
        blob = subprocess.check_output(["git", "show", f"{c['base_commit']}:{item['path']}"], cwd=REPO)
        assert {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()} == item["published_git_at_base"]
        refs.append({"path": Path(os.path.relpath(original, HERE)).as_posix(),
                     "local_disk": item["local_disk"], "published_git_at_base": item["published_git_at_base"]})
    assert len(refs) == 38
    raw_map = json.loads((HERE / "raw-custody-map.json").read_text(encoding="utf-8"))
    raw = raw_map["records"]
    assert len(raw) == 30
    for item in raw:
        exact(Path(item["original_path"]), item)
    installed = []
    for kind, item in c["installed"].items():
        exact(Path(item["path"]), item)
        installed.append({"role": kind, "path": item["path"], "bytes": item["bytes"], "sha256": item["sha256"]})
    context = historical_context(c["excluded_v010"]["files"])
    context += historical_context(c["excluded_v011"]["files"] + c["excluded_v011"]["root_probe_context"])
    gate_map = json.loads((HERE / "preserved-root-v012-gates/custody-map.json").read_text(encoding="utf-8"))
    assert len(gate_map["files"]) == 27
    for item in gate_map["files"]:
        copy = HERE / item["copy_path"]
        exact(copy, item)
        original = REPO / item["original_path"]
        if original.exists():
            exact(original, item)
        context.append({"original_path": str(original), "copy_path": item["copy_path"],
                        "bytes": item["bytes"], "sha256": item["sha256"],
                        "original_present_at_build": original.exists()})
    for name in ["b03-var01-v012-root-contract-freeze-20261007.json",
                 "freeze-b03-var01-v012-contract-20261007.py"]:
        copy = HERE / "preserved-root-context" / name
        original = REPO / "tmp" / name
        assert copy.exists()
        if original.exists():
            assert pin(copy) == pin(original)
        context.append({"original_path": str(original), "copy_path": copy.relative_to(HERE).as_posix(),
                        **pin(copy), "original_present_at_build": original.exists()})
    source = []
    for file in sorted(HERE.rglob("*")):
        if not file.is_file():
            continue
        rel = file.relative_to(HERE).as_posix()
        if rel == INDEX.name or "__pycache__" in file.parts or file.suffix == ".pyc" or "/runs/" in f"/{rel}/":
            continue
        if rel.startswith(EXCLUDED_REVIEW_PREFIXES):
            continue
        source.append({"path": rel, **pin(file)})
    assert len({item["path"] for item in source}) == len(source)
    return {"schema": "b03-var01-evidence-index/v0.1.2",
            "publication_id": "B03.var01.cold_first_full_report.0.1.2",
            "case_id": "B03", "variant_id": "B03.var01",
            "version": "0.1.2", "classification": "cold_first_full_report_readonly",
            "publication_state": "reusable_published", "bounded_decision": "GO_BOUNDED_RETROSPECTIVE_FULL_REPORT",
            "contract_sha256": CONTRACT_SHA, "source_base_commit": c["base_commit"],
            "new_native_runs": 0, "accepted_run_id": c["parent_runs"][1]["run_id"],
            "excluded_failed_run_id": c["parent_runs"][0]["run_id"],
            "author_v1_decision": "NO_GO_AUTHOR_METHOD_REVIEW", "contract_v010_decision": "NO_GO_CONTRACT",
            "contract_v011_decision": "NO_GO_FULL_REPORT_FORMULA_SCOPE",
            "author_method_sha256": PINS["replay_v2.py"],
            "independent_method_sha256": PINS["review/independent_replay_v4.py"],
            "author_semantic_rejections": 53, "independent_semantic_rejections": 35,
            "report_cells_checked": 4044, "physical_timed_lines": 121,
            "system_presentation_zero_cells": 360,
            "source_count": len(source), "source": source, "source_files": source,
            "accepted_source_refs": refs, "installed": installed, "raw_files": raw,
            "raw_record_count": len(raw), "context_copies": context,
            "limits": ["The parent already published the explicit cold/hot physical sequence; no new behavior is claimed.",
                       "Five System zero fields and empty-stock PNB/nulls are bounded native presentation, not general formulas.",
                       "Historical invocation lacks individual native child PID/session.",
                       "No same-MTID history switch, cold-only causal, GUI, cross-engine, performance or whole-case claim."],
            "source_location_policy": "Package-relative publishable source pins use exact bytes and * -text; historical originals have named inert copies.",
            "raw_location_policy": raw_map["raw_location_policy"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="create the index only if absent")
    args = parser.parse_args()
    data = (json.dumps(build(), sort_keys=True, indent=2) + "\n").encode("utf-8")
    outcome = {"schema": "b03-var01-evidence-index-build/v0.1.2", "bytes": len(data),
               "sha256": hashlib.sha256(data).hexdigest(), "written": False}
    if args.write:
        with INDEX.open("xb") as handle:
            handle.write(data)
        outcome["written"] = True
    elif INDEX.exists():
        assert INDEX.read_bytes() == data, "existing index differs from current strict dry build"
    print(json.dumps(outcome, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

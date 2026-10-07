"""Build the bounded C02.var01 publication index without changing sealed evidence.

``--write-maps`` is a one-time authoring step. The ordinary invocation and
``--write`` verify all existing bytes and never overwrite an index.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE.parent
REPO = HERE.parents[2]
RUN_ID = "c02-var01-v101-personnel0-ssh-20261007-01"
RUN = HERE / "runs" / RUN_ID
BASE = "1a80bbe5bcfb0351f27c55c7e0cf665bc761e4c6"
CONTRACT_SHA = "e8cce2aeae398f8e725365ab7472b0a7a92b9681cc63299e581d642e76ef9d12"
MANIFEST_SHA = "c1c2665b9e8c8a7e054c47395a91110e0f4852605573ca49bc6aa69b2308e6e2"
CLOSURE_SHA = "d418d9a3ea70b8c6358b5f94bfc99427ba84fb336f7c6bba193ef7268dcbe68d"
INVOCATION_SHA = "334102b4a84884137d042933824524fd73a2072db86eea4fd87c84447e33f318"
INDEPENDENT = {
    "review/independent_replay.py": "f3513bd42042597a49b6bf276117dc3a458d48ab079b4297b14a3be9aa19578f",
    "review/independent-replay-original-no-go-2026-10-07.md": "c294ea23babb8d17451d5999dfc3a94042c3e1034bd34b64b49b16a4636ab06e",
    "review/independent_replay_v2.py": "56f904d082c27320e906c95f29b7be7c038decbeb4dc02ee41c64c4c462a4d00",
    "review/independent-verdict.json": "0d3369579cd8589f924b77d492090bf88f836177cb0a80b118eb7e20b1e7fc3c",
    "review/independent-postrun-review-2026-10-07.md": "5b21481d069954436f8cfb614093fdca85658dfe25fcfba1bf2eff9c0c9a8f8d",
}
CONTEXT_DIR = HERE / "preserved-publication-context"
RAW_MAP = HERE / "raw-custody-map.json"
CONTEXT_MAP = HERE / "context-custody-map.json"


def identity(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check(path: Path, expected: dict) -> None:
    actual = identity(path)
    assert actual == {"bytes": expected["bytes"], "sha256": expected["sha256"]}, str(path)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def relative(path: Path) -> str:
    return os.path.relpath(path, HERE).replace("\\", "/")


def verify_gate() -> tuple[dict, dict, dict]:
    check(HERE / "contract.json", {"bytes": 48041, "sha256": CONTRACT_SHA})
    check(HERE / "prelaunch-manifest.json", {"bytes": 52079, "sha256": MANIFEST_SHA})
    check(RUN / "closure.json", {"bytes": 47422, "sha256": CLOSURE_SHA})
    assert identity(RUN / "invocation.json")["sha256"] == INVOCATION_SHA
    for name, digest in INDEPENDENT.items():
        assert identity(HERE / name)["sha256"] == digest, name
    contract = load(HERE / "contract.json")
    manifest = load(HERE / "prelaunch-manifest.json")
    closure = load(RUN / "closure.json")
    assert contract["ownership"]["base_commit"] == BASE
    assert len(manifest["source_files"]) == manifest["source_count"] == 155
    assert closure["run_id"] == manifest["run_id"] == RUN_ID
    assert closure["error"] == closure["step_error"] == ""
    assert closure["manifest_sha256"] == MANIFEST_SHA
    assert closure["invocation_sha256"] == INVOCATION_SHA
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["source_hashes_before"]) == 155
    assert len(closure["raw"]) == 23
    for name, spec in closure["raw"].items():
        check(RUN / name, spec)
    assert len([p for p in RUN.iterdir() if p.is_file()]) == 25
    verdict = load(HERE / "review/independent-verdict.json")
    assert verdict["decision"] == "GO_BOUNDED" and verdict["checks"] == 13434
    assert verdict["report_cells"] == 10420 and verdict["failures"] == []
    assert verdict["original_approved_replay_sha256"] == INDEPENDENT["review/independent_replay.py"]
    assert verdict["retrospective_replay_v2_sha256"] == INDEPENDENT["review/independent_replay_v2.py"]
    assert verdict["original_replay_no_go_memo_sha256"] == INDEPENDENT["review/independent-replay-original-no-go-2026-10-07.md"]
    result = subprocess.run([sys.executable, "-B", str(HERE / "review/independent_replay_v2.py")],
                            cwd=REPO, text=True, encoding="utf-8", capture_output=True, check=True)
    reproduced = json.loads(result.stdout)
    assert reproduced["decision"] == "GO_BOUNDED" and reproduced["checks"] == 13434
    assert reproduced["report_cells"] == 10420 and reproduced["failures"] == []
    return contract, manifest, closure


def raw_records(contract: dict, closure: dict) -> list[dict]:
    records: list[dict] = []

    def add(role: str, run_dir: Path, name: str, spec: dict) -> None:
        path = run_dir / name
        check(path, spec)
        records.append({"role": role, "original_path": str(path), "name": name,
                        "bytes": spec["bytes"], "sha256": spec["sha256"]})

    parent = contract["accepted_evidence"]["C02_parent"]
    for run in parent["accepted_runs"]:
        directory = Path(run["local_run_dir"])
        role = "accepted_C02_" + run["role"]
        add(role, directory, "closure.json", run["closure"])
        add(role, directory, "invocation.json", run["invocation"])
        for name, spec in sorted(run["raw"].items()):
            add(role, directory, name, spec)
    c01 = contract["accepted_evidence"]["C01_capacity_zero_context"]
    directory = Path(c01["local_run_dir"])
    for kind in ("closure", "invocation"):
        add("accepted_C01_cap0", directory, c01[kind]["path"], c01[kind])
    for name, spec in sorted(c01["raw"].items()):
        add("accepted_C01_cap0", directory, name, spec)
    add("new_C02_personnel0", RUN, "closure.json", {"bytes": 47422, "sha256": CLOSURE_SHA})
    add("new_C02_personnel0", RUN, "invocation.json", identity(RUN / "invocation.json"))
    for name, spec in sorted(closure["raw"].items()):
        add("new_C02_personnel0", RUN, name, spec)
    assert len(records) == 90 and len({x["original_path"] for x in records}) == 90
    assert sum(x["role"].startswith("accepted_") and x["name"] not in ("closure.json", "invocation.json") for x in records) == 55
    assert sum(x["role"] == "new_C02_personnel0" and x["name"] not in ("closure.json", "invocation.json") for x in records) == 23
    return sorted(records, key=lambda x: x["original_path"])


def context_records() -> list[dict]:
    records = []
    for copy in sorted(CONTEXT_DIR.iterdir()):
        if not copy.is_file():
            continue
        original = REPO / "tmp" / copy.name
        spec = identity(copy)
        if original.exists():
            check(original, spec)
        records.append({"original_path": str(original), "copy_path": relative(copy), **spec})
    assert len(records) == 23, len(records)
    required = ("c02-var01-v101-native-driver-20261007.ps1",
                "c02-var01-v101-independent-bom-failure-20261007.json",
                "c02-var01-v101-postrun-owner-20261007.json",
                "c02-var01-v101-root-postrun-seal-20261007.json")
    assert all(any(r["copy_path"].endswith(name) for r in records) for name in required)
    return records


def accepted_source_refs(contract: dict) -> list[dict]:
    refs = []

    def add(path: Path, disk: dict, git: dict) -> None:
        check(path, disk)
        git_path = path.relative_to(REPO).as_posix()
        blob = subprocess.run(["git", "show", f"{BASE}:{git_path}"], cwd=REPO,
                              capture_output=True, check=True).stdout
        assert len(blob) == git["bytes"] and hashlib.sha256(blob).hexdigest() == git["sha256"], git_path
        refs.append({"path": relative(path), "local_disk": disk, "published_git": git})

    ev = contract["accepted_evidence"]
    classification = ev["classification"]
    for spec in classification["source_files"]:
        path = CASES / classification["package"] / spec["path"]
        add(path, {"bytes": spec["bytes"], "sha256": spec["sha256"]},
            {"bytes": spec["bytes"], "sha256": spec["sha256"]})
    parent = ev["C02_parent"]
    for spec in parent["source_files_dual_local_and_git"]:
        add(CASES / parent["package"] / spec["path"], spec["local_disk"], spec["published_git"])
    c01 = ev["C01_capacity_zero_context"]
    for name, spec in c01["source_files_dual_local_and_git"].items():
        add(CASES / c01["package"] / name,
            {"bytes": spec["local_bytes"], "sha256": spec["local_sha256"]},
            {"bytes": spec["published_git_bytes"], "sha256": spec["published_git_sha256"]})
    assert len(refs) == 47
    return sorted(refs, key=lambda x: x["path"])


def sources() -> list[dict]:
    found = []
    for directory in (CASES / "C02-var01-personnel-zero-v1.0.0", HERE):
        assert directory.is_dir()
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or any(part in ("runs", "__pycache__") for part in path.parts):
                continue
            if path == HERE / "evidence-index.json":
                continue
            if path.parent.name == "review" and path.name.startswith((
                    "independent-content-", "independent-publication-", "independent-staged-", "independent-remote-")):
                continue
            found.append({"path": relative(path), **identity(path)})
    assert len({x["path"] for x in found}) == len(found)
    return sorted(found, key=lambda x: x["path"])


def build() -> dict:
    contract, manifest, closure = verify_gate()
    raw = raw_records(contract, closure)
    context = context_records()
    assert load(RAW_MAP) == raw
    assert load(CONTEXT_MAP) == context
    refs = accepted_source_refs(contract)
    source = sources()
    assert any(x["path"] == "review/independent_replay_v2.py" for x in source)
    assert any(x["path"] == "../C02-var01-personnel-zero-v1.0.0/contract.json" for x in source)
    return {
        "schema": "c02-var01-personnel-zero-evidence-index/v1",
        "case_id": "C02", "variant_id": "C02.var01", "version": "1.0.1",
        "publication_state": "reusable_published",
        "bounded_decision": "GO_BOUNDED_AFTER_SEPARATE_READONLY_REPLAY_REPAIR",
        "original_approved_replay_decision": "NO_GO_INDEPENDENT_REPLAY_BOM",
        "native_runs": 1, "native_reruns": 0, "run_id": RUN_ID,
        "contract_sha256": CONTRACT_SHA, "prelaunch_manifest_sha256": MANIFEST_SHA,
        "closure_sha256": CLOSURE_SHA, "invocation_sha256": INVOCATION_SHA,
        "original_independent_method_sha256": INDEPENDENT["review/independent_replay.py"],
        "original_independent_no_go_sha256": INDEPENDENT["review/independent-replay-original-no-go-2026-10-07.md"],
        "corrected_readonly_method_sha256": INDEPENDENT["review/independent_replay_v2.py"],
        "independent_verdict_sha256": INDEPENDENT["review/independent-verdict.json"],
        "independent_checks": 13434, "independent_report_cells": 10420,
        "parent_and_child_report_cells_each": 5210,
        "accepted_source_base_commit": BASE,
        "accepted_source_ref_count": len(refs),
        "accepted_context_raw_seals": 55, "child_raw_seals": 23,
        "child_run_file_count": 25,
        "raw_record_count_including_closure_invocation": len(raw),
        "raw_location_policy": "Raw runs remain ignored at their original paths. Restore exact SHA/size bytes in raw-custody-map.json; no native rerun or synthesized substitute. Local disk and base Git source bytes are separate identities.",
        "scope": "One fixed-seed personnel-zero child; typed crew request failed, equipment availability succeeded, no booking/work/launch, cancellation printed h7.58333, ready terminal. Full parent+child report cells reconciled. Original approved reader failed on PS5 BOM; a separately versioned read-only reader passed without changing physical, source, raw, report, or numeric gates.",
        "limits": "No universal all-or-none booking rule, cancellation clock, GUI equivalence, cross-engine result, or performance claim.",
        "source_count": len(source), "source": source, "source_files": source,
        "raw_files": raw, "context_copies": context,
        "accepted_source_refs": refs,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-maps", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    assert not (args.write_maps and args.write)
    if args.write_maps:
        contract = load(HERE / "contract.json")
        closure = load(RUN / "closure.json")
        for path, value in ((RAW_MAP, raw_records(contract, closure)),
                            (CONTEXT_MAP, context_records())):
            assert not path.exists(), "never overwrite custody map: " + str(path)
            path.write_bytes(encoded(value))
        print(json.dumps({"raw_records": 90, "context_copies": 23, "written": True}, sort_keys=True))
        return
    index = build()
    data = encoded(index)
    target = HERE / "evidence-index.json"
    if target.exists():
        assert target.read_bytes() == data, "indexed source/raw bytes changed"
    if args.write:
        assert not target.exists(), "never overwrite a frozen index"
        target.write_bytes(data)
    print(json.dumps({"source_count": index["source_count"], "raw_records": len(index["raw_files"]),
                      "accepted_source_refs": len(index["accepted_source_refs"]),
                      "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                      "written": args.write}, sort_keys=True))


if __name__ == "__main__":
    main()

"""Deterministic byte-only index for the one sealed I04.var10 v1.0.1 run."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from copy_postrun_context import verify as verify_context
from make_preflight_custody import candidate as preflight_candidate, encode as preflight_encode
from make_raw_custody import candidate as raw_candidate, encode as raw_encode
from source_gate import HERE, REPO, verify as verify_sources

INDEX = HERE / "evidence-index.json"
INVENTORY = HERE / "source-inventory.json"
MANIFEST = HERE / "prelaunch-manifest.json"
RUN = REPO / "tmp/native-runs/i04v10-v101-20261008-01"
CATALOG = REPO / "cases/simlox-air-support/publication-index-v1.json"
CONTRACT = HERE / "execution-contract.json"
ENTRY = HERE / "publication-entry.json"
INVENTORY_PIN = {"bytes": 43251, "sha256": "3f5609725b222c11ea322228b9f5b5bddce7e78bee3ca864e8803292803a9844"}
MANIFEST_PIN = {"bytes": 584393, "sha256": "32153d25a7426b6300cd2594ca221b491376a70e72e0780828e972b713df0ad6"}
READER_SHA = "0109ac2d539c625e84df2db3f4c9bf1cb045ead2dfd5dc40765022cef46efea5"
GO_SHA = "fca43bf8e9b8232eb1443e3bf620bb3a71b49696d316dde9e65744d126fa8f0e"
NATIVE_RECEIPT = REPO / "tmp/i04-var10-root-native-proofs-v101-20261008/20261008T141303055254Z-76c96921/receipt.json"
NATIVE_SHA = "82a078a33588621daeaf8641cdbe877aa2820d3d6ef3c87ee8e67aedbb554312"
REPLAY_RECEIPT = REPO / "tmp/i04-var10-root-sealed-replay-v101-20261008/20261008T141626170671Z-ad3cc985/receipt.json"
REPLAY_SHA = "760d0d0273d3a9bcff391f2e649f4fe790516ed19553d00a7a5275619b330620"
AMEND_PROOF = REPO / "tmp/i04-var10-postrun-context-amend-v101-20261008-01"
AMEND_METHOD = REPO / "tmp/i04-var10-postrun-context-amend-capture-v101-20261008.py"
AMEND_SHA = "b3077a689b072d901eef4ea3f775c92de31bf86f2fc7a2857589a0b23cb75521"
POSTRUN_REVIEW = (
    "review/independent-prelaunch-go.json",
    "review/preflight-ssh0-20261008T140249252Z.json",
    "review/independent-postrun-go-v101-2026-10-08.md",
)
RUNTIME_EXCLUSIONS = {"runs", "test-output", "transport-evidence"}


def pin_bytes(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def pin(path: Path) -> dict:
    return pin_bytes(path.read_bytes())


def read(path: Path) -> dict:
    value = json.loads(path.read_bytes())
    assert type(value) is dict
    return value


def encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def exact_int(value, expected: int) -> None:
    assert type(value) is int and value == expected


def original_proof_rows() -> list[dict]:
    assert pin(AMEND_METHOD) == {"bytes": 2120,
        "sha256": "5adbbf73d3e333df3a4f0754984a8d38cf7eb84fa449dc907bc5df4061a21eca"}
    receipt = read(AMEND_PROOF / "receipt.json")
    assert pin(AMEND_PROOF / "receipt.json")["sha256"] == AMEND_SHA
    assert receipt["schema"] == "i04-var10-v101-postrun-context-amend-original-capture/v1"
    exact_int(receipt["actual_exit"], 0)
    assert receipt["native_dispatch"] is False
    assert receipt["method_before"] == receipt["method_after"]
    assert receipt["method_before"]["capture_method"] == pin(AMEND_METHOD)
    assert receipt["method_before"]["copier"] == pin(HERE / "copy_postrun_context.py")
    assert receipt["argv"][-2:] == [str(HERE / "copy_postrun_context.py"), "--write"]
    assert receipt["streams"] == {name: pin(AMEND_PROOF / name) for name in ("stdout.bin", "stderr.bin")}
    assert (AMEND_PROOF / "stderr.bin").read_bytes() == b""
    files = (AMEND_METHOD, AMEND_PROOF / "receipt.json", AMEND_PROOF / "stdout.bin", AMEND_PROOF / "stderr.bin")
    rows = []
    for path in files:
        assert path.stat().st_file_attributes & 1
        rows.append({"path": str(path), **pin(path), "original_mandatory": True,
                     "role": "postrun_context_amend_capture"})
    return rows


def source_rows(context: dict, development: dict, frozen: dict) -> list[dict]:
    names = [row["relative_path"] for row in frozen["source_files"]]
    assert len(names) == len(set(names)) == 114
    for row in frozen["source_files"]:
        assert pin(HERE / row["relative_path"]) == {key: row[key] for key in ("bytes", "sha256")}
    contract = read(CONTRACT)
    author = [name for name in contract["future_author_files"] if name != INDEX.name]
    assert set(author) == {
        "README-publication.md", "REPRODUCTION-postrun.md", "results-summary.json",
        "cli-scope-signoff-2026-10-08.md", "publication-entry.json", "make_evidence_index.py",
        "copy_postrun_context.py", "postrun-context-custody.json", "postrun-context-originals.json",
        "make_raw_custody.py", "make_preflight_custody.py"}
    copies = [row["owned_copy"] for row in context["records"] if row["owned_copy"] is not None]
    assert copies == [f"preserved-postrun/postrun-{index:03d}.bytes" for index in range(98)]
    drafts = [row["path"] for row in development["records"]]
    assert drafts == [f"preserved-postrun-development/draft-{index:03d}.bytes" for index in range(9)]
    names += ["source-inventory.json", "prelaunch-manifest.json"]
    names += author + list(contract["future_custody_files"]) + list(POSTRUN_REVIEW) + copies + drafts
    assert len(names) == len(set(names))
    expected = set(names)
    observed = set()
    for path in HERE.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(HERE).as_posix()
        if relative == INDEX.name or relative.split("/", 1)[0] in RUNTIME_EXCLUSIONS:
            continue
        if path.suffix == ".pyc" and "__pycache__" in path.relative_to(HERE).parts:
            continue
        observed.add(relative)
    assert observed == expected, {"unexpected": sorted(observed - expected),
                                  "missing": sorted(expected - observed)}
    assert len(expected) == 241
    if INDEX.exists():
        for relative in expected:
            assert (HERE / relative).stat().st_file_attributes & 1, relative
    return [{"path": relative, **pin(HERE / relative)} for relative in sorted(expected)]


def captured_verdict() -> dict:
    assert pin(HERE / "review/independent_replay.py")["sha256"] == READER_SHA
    assert pin(HERE / "review/independent-postrun-go-v101-2026-10-08.md")["sha256"] == GO_SHA
    assert pin(NATIVE_RECEIPT)["sha256"] == NATIVE_SHA
    native = read(NATIVE_RECEIPT)
    exact_int(native["actual_exit"], 0)
    assert native["native_dispatch"] is True and native["native_acceptance_claim"] is False
    assert native["decision"] == "NO_GO_PRESERVE_FAILURE"
    assert native["method_before"] == native["method_after"]
    assert native["streams"]["stderr.bin"]["bytes"] == 0
    assert pin(REPLAY_RECEIPT)["sha256"] == REPLAY_SHA
    replay = read(REPLAY_RECEIPT)
    exact_int(replay["actual_exit"], 0)
    assert replay["source_map_unchanged"] is True
    assert replay["method_before"] == replay["method_after"]
    assert replay["streams"]["stderr.bin"]["bytes"] == 0
    assert pin(RUN / "author-validation.json") == {"bytes": 777,
        "sha256": "22555c1c164878713d28ac2f5d7c8f726bab04a4403e5bcd98be1f4671fd9e32"}
    behavior = read(RUN / "author-validation.json")
    assert behavior["schema"] == "i04-var10-horizon-transit-behavior/v101" and behavior["passed"] is True
    assert behavior["issues"] == [] and behavior["native_run_directory"] == str(RUN)
    for key, expected in (("log_lines", 61), ("timed_event_records", 53), ("report_cell_checks", 1244), ("native_calls", 0)):
        exact_int(behavior[key], expected)
    assert behavior["terminal"] == {"arrived_id0_before_horizon": False, "assigned_terminal": 0,
        "first_mission_completed": 1, "initial_aircraft": 2, "microstates": 53,
        "source_ready_terminal": 0, "target_ready_terminal": 1, "transit_terminal": 1}
    return {"native_transport_child_actual_exit": 0, "root_wrapper_decision": "NO_GO_PRESERVE_FAILURE",
            "root_native_receipt_sha256": NATIVE_SHA, "independent_recovered_replay": "GO_BOUNDED",
            "independent_replay_receipt_sha256": REPLAY_SHA,
            "independent_go_sha256": GO_SHA, "report_cells_checked": 1244,
            "log_lines": 61, "timed_event_records": 53}


def build() -> dict:
    assert pin(INVENTORY) == INVENTORY_PIN and pin(MANIFEST) == MANIFEST_PIN
    frozen, manifest = read(INVENTORY), read(MANIFEST)
    exact_int(frozen["source_count"], 114)
    exact_int(manifest["source_count"], 1651)
    assert len(frozen["source_files"]) == 114 and len(manifest["source_files"]) == 1651
    source = verify_sources("sealed")
    assert source["catalog"]["historical_prefix_checked"] == 499
    assert source["parent_sources"] == 401 and source["parent_git_disk_pairs"] == 403
    assert source["accepted_dependency_pairs"] == 76 and source["parent_manifest_roles"] == 456
    context_summary = verify_context()
    assert context_summary["original_count"] == 103 and context_summary["owned_copy_count"] == 98
    assert context_summary["mandatory_host_count"] == 5
    context = read(HERE / "postrun-context-originals.json")
    development = read(HERE / "preserved-postrun-development/custody.json")
    assert len(development["records"]) == 9
    raw = raw_candidate()
    preflight = preflight_candidate()
    assert raw_encode(raw) == (HERE / "preserved-raw/custody.json").read_bytes()
    assert preflight_encode(preflight) == (HERE / "preserved-preflight/custody.json").read_bytes()
    exact_int(raw["mandatory_original_count"], 192)
    exact_int(preflight["mandatory_original_count"], 30)
    assert len(raw["records"]) == 192 and len(preflight["records"]) == 30
    entry = read(ENTRY)
    assert entry["publication_id"] == "I04.var10.horizon_in_transit.1.0.1"
    exact_int(entry["new_native_runs"], 1)
    exact_int(entry["accepted_parent_runs_repeated"], 0)
    catalog = read(CATALOG)
    matching = [row for row in catalog["entries"] if row["publication_id"] == entry["publication_id"]]
    assert len(matching) <= 1
    if matching:
        assert matching[0] == entry
    return {"schema": "i04-var10-v101-deterministic-evidence-index/v1",
            "publication_id": entry["publication_id"],
            "historical_catalog_prefix_entries": 499,
            "frozen_owned_sources": 114, "frozen_prelaunch_roles": 1651,
            "source_count": 241,
            "source_files": source_rows(context, development, frozen),
            "mandatory_original_raw_count": 192,
            "mandatory_original_preflight_count": 30,
            "postrun_context_original_count": 103,
            "postrun_context_owned_copy_count": 98,
            "postrun_context_mandatory_host_count": 5,
            "mandatory_original_proofs": original_proof_rows(),
            "captured_verdict": captured_verdict()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--candidate", type=Path)
    args = parser.parse_args()
    assert sum((args.write, args.dry, args.candidate is not None)) <= 1
    data = encode(build())
    if args.candidate is not None:
        target = args.candidate.absolute()
        assert target.parent.is_dir() and target.is_relative_to(REPO / "tmp")
        with target.open("xb") as stream:
            stream.write(data)
        target.chmod(0o444)
    elif args.write:
        assert not INDEX.exists()
        with INDEX.open("xb") as stream:
            stream.write(data)
        INDEX.chmod(0o444)
    elif not args.dry:
        assert INDEX.read_bytes() == data
        assert INDEX.stat().st_file_attributes & 1
    print(json.dumps({"source_count": 241, "bytes": len(data),
                      "sha256": pin_bytes(data)["sha256"],
                      "mode": "candidate" if args.candidate else "write" if args.write else "dry" if args.dry else "verify"}, sort_keys=True))


if __name__ == "__main__":
    main()

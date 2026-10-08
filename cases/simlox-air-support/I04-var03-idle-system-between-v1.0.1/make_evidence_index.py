"""Deterministic index of fixed source, original raw, and small proof custody.

Default and --dry never rerun a native command, checker, or semantic reader.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from copy_postrun_context import candidate as context_candidate, development
from make_preflight_custody import candidate as preflight_candidate
from make_raw_custody import candidate as raw_candidate
from model_common import encode, pin, read, typed_equal
from source_gate import HERE, REPO, RUN_ID, verify as verify_source

INDEX = HERE / "evidence-index.json"
INVENTORY = HERE / "source-inventory.json"
MANIFEST = HERE / "prelaunch-manifest.json"
RUN = HERE / "runs" / RUN_ID
CATALOG = REPO / "cases/simlox-air-support/publication-index-v1.json"
PUBLICATION_ID = "I04.var03.idle_system_between.1.0.1"
INVENTORY_PIN = {"bytes": 93926, "sha256": "b5cac833294ea73d8f103579a779630205988e131007ada76dc009c44279aa1a"}
MANIFEST_PIN = {"bytes": 161922, "sha256": "d05541613248279a5620349ade72bcaf80b12f3be042b470694f45b6efa690f3"}
READER_SHA = "e9ffcb9a491d39402fab9ac320c1611a1b1149f70ce35b6ff604ce67e79021f3"
GO_SHA = "d5b7ea964e65ddb57d248562dab82f53bce565f6d0ac7a161c4eccc5b8ebf7c7"
VERDICT_SHA = "45bd3d5898446cc4efc6e70665e8731aaf7b73b41a55934d5a392e79d21d6414"
EXCLUDED_REVIEW_PREFIXES = ("review/independent-content-", "review/independent-staged-",
                            "review/independent-remote-", "review/independent-pr-")
EXTRA_REVIEW = (
    "review/preflight-ssh0-20261008T054617008Z.json",
    "review/independent-prelaunch-pure-go-2026-10-08.md",
    "review/independent-prelaunch-pure-go-addendum-2026-10-08.md",
    "review/independent-prelaunch-guard-hold-2026-10-08.md",
    "review/independent-prelaunch-wts-state-2026-10-08.md",
    "review/independent-prelaunch-wts-recovery-2026-10-08.md",
    "review/independent-prelaunch-go.json",
    "review/independent-prelaunch-go-2026-10-08.md",
    "review/independent-postrun-go-2026-10-08.md",
)
EXTRA_AUTHOR = (
    "source-inventory.json", "prelaunch-manifest.json",
    "README-publication.md", "REPRODUCTION-postrun.md", "results-summary.json",
    "cli-scope-signoff-2026-10-08.md", "publication-entry.json",
    "make_evidence_index.py", "copy_postrun_context.py",
    "postrun-context-originals.json", "postrun-context-custody.json",
    "make_raw_custody.py", "raw-custody-map.json",
    "make_preflight_custody.py", "preflight-custody-map.json",
)


def owned_bytes(context, suffix: str) -> bytes:
    found = [row for row in context["records"] if
             row["original_path"].replace("\\", "/").endswith(suffix)]
    assert len(found) == 1, suffix
    row = found[0]
    data = (HERE / row["owned_copy"]).read_bytes()
    assert {"bytes": len(data), "sha256": pin(HERE / row["owned_copy"])["sha256"]} == \
           {k: row[k] for k in ("bytes", "sha256")}
    return data


def sources(context):
    assert pin(INVENTORY) == INVENTORY_PIN and pin(MANIFEST) == MANIFEST_PIN
    frozen = read(INVENTORY)
    assert frozen["source_count"] == len(frozen["source_files"]) == 251
    assert read(MANIFEST)["source_count"] == 456
    base = [row["relative_path"] for row in frozen["source_files"]]
    assert len(base) == len(set(base))
    for row in frozen["source_files"]:
        assert pin(HERE / row["relative_path"]) == {k: row[k] for k in ("bytes", "sha256")}
    dev = read(HERE / "preserved-postrun-development/custody.json")
    assert dev["schema"] == "i04-var03-v101-postrun-development-custody/v1"
    assert dev["originals_optional_after_publication"] is True
    assert dev["first_draft_original_binary_streams_captured"] is True
    assert len(dev["records"]) == 13
    copies = [row["owned_copy"] for row in context["records"]]
    draft_copies = [row["owned_copy"] for row in dev["records"]]
    assert copies == [f"preserved-postrun/postrun-{i:03d}.bytes" for i in range(111)]
    assert draft_copies == [f"preserved-postrun-development/draft-{i:03d}.bytes"
                          for i in range(13)]
    extra = [*EXTRA_AUTHOR, *EXTRA_REVIEW, "preserved-postrun/custody.json",
             "preserved-postrun-development/custody.json", *copies, *draft_copies]
    expected = set(base) | set(extra)
    assert len(expected) == len(base) + len(extra)
    actual = set()
    for path in HERE.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(HERE).as_posix()
        top = relative.split("/", 1)[0]
        if relative == INDEX.name or top in ("runs", "transport-evidence", "test-output"):
            continue
        if path.suffix == ".pyc" and "__pycache__" in path.relative_to(HERE).parts:
            continue
        if any(relative.startswith(prefix) and "/" not in relative[len(prefix):]
               for prefix in EXCLUDED_REVIEW_PREFIXES):
            continue
        actual.add(relative)
    assert actual == expected, {"unindexed": sorted(actual - expected),
                                "missing": sorted(expected - actual)}
    return [{"path": relative, **pin(HERE / relative)} for relative in sorted(expected)]


def captured_verdict(context):
    assert pin(HERE / "review/independent_replay.py")["sha256"] == READER_SHA
    assert pin(HERE / "review/independent-postrun-go-2026-10-08.md")["sha256"] == GO_SHA
    suffix = "tmp/i04-var03-root-sealed-replay-v101-20261008/20261008T065358193780Z-30866710/"
    receipt = json.loads(owned_bytes(context, suffix + "receipt.json"))
    stdout = owned_bytes(context, suffix + "stdout.bin")
    stderr = owned_bytes(context, suffix + "stderr.bin")
    assert type(receipt["actual_exit"]) is int and receipt["actual_exit"] == 0
    assert receipt["source_map_unchanged"] is True
    assert receipt["method_before"] == receipt["method_after"]
    assert receipt["method_before"]["reader"]["sha256"] == READER_SHA
    assert receipt["method_before"]["manifest"] == MANIFEST_PIN
    assert receipt["streams"]["stdout.bin"] == {"bytes": len(stdout),
           "sha256": pin_bytes(stdout)}
    assert receipt["streams"]["stderr.bin"] == {"bytes": 0, "sha256": pin_bytes(b"")}
    assert stderr == b"" and pin_bytes(stdout) == VERDICT_SHA
    verdict = json.loads(stdout)
    assert verdict == {"decision": "GO_BOUNDED", "historical_catalog_prefix_entries": 496,
                       "log_lines": 118, "original_raw_files": 25, "paired_differences": 5,
                       "report_cells_checked": 4044, "run_id": RUN_ID,
                       "source_records": 456, "timed_event_records": 104}
    return verdict


def pin_bytes(data):
    from hashlib import sha256
    return sha256(data).hexdigest()


def author_receipts():
    rt = read(RUN / "roundtrip-validation.json")
    behavior = read(RUN / "author-validation.json")
    assert rt["schema"] == "i04-var03-idle-between-roundtrip/v101"
    assert rt["passed"] is True and rt["issues"] == []
    assert {k: rt[k] for k in ("tables", "authored_rows", "authored_cells", "exported_rows",
                                   "exported_cells", "all_null_placeholder_tables")} == {
        "tables": 34, "authored_rows": 22, "authored_cells": 223,
        "exported_rows": 40, "exported_cells": 407, "all_null_placeholder_tables": 18}
    assert behavior["schema"] == "i04-var03-idle-between-behavior/v101"
    assert behavior["passed"] is True and behavior["issues"] == []
    assert behavior["run_id"] == RUN_ID
    for key, expected in (("report_cell_checks", 4044), ("paired_differences", 5),
                          ("log_lines", 118), ("timed_event_records", 104)):
        assert type(behavior[key]) is int and behavior[key] == expected
    assert behavior["terminal"]["terminal_target_ready"] == 2
    assert rt["input_sha256"] == behavior["input_sha256"] == pin(HERE / "native-input.json")["sha256"]
    assert rt["export_sha256"] == behavior["export_sha256"] == pin(RUN / "roundtrip-raw.json")["sha256"]
    return {"roundtrip_passed": True, "behavior_passed": True,
            "child_report_cells": 4044, "paired_report_differences": 5}


def build():
    gate = verify_source("sealed")
    assert gate["accepted_disk_git_pairs"] == 76
    assert gate["mandatory_accepted_original_raw"] == 114
    assert gate["catalog"]["historical_prefix_checked"] == 496
    context_summary = context_candidate()
    assert context_summary["records"] == 111
    dev_summary = development(False)
    assert dev_summary["records"] == 13
    context = read(HERE / "preserved-postrun/custody.json")
    assert len(context["records"]) == 111
    raw = raw_candidate()
    preflight = preflight_candidate()
    assert len(raw["records"]) == raw["mandatory_original_count"] == 153
    assert len(preflight["records"]) == preflight["mandatory_original_count"] == 15
    assert (HERE / "raw-custody-map.json").read_bytes() == encode(raw)
    assert (HERE / "preflight-custody-map.json").read_bytes() == encode(preflight)
    entry = read(HERE / "publication-entry.json")
    assert entry["publication_id"] == PUBLICATION_ID
    assert type(entry["new_native_runs"]) is int and entry["new_native_runs"] == 1
    assert type(entry["accepted_parent_runs_repeated"]) is int and entry["accepted_parent_runs_repeated"] == 0
    live = read(CATALOG)
    archived = read(HERE / "preserved-context/publication-index-local-496.json.bytes")
    assert typed_equal(archived["entries"], live["entries"][:496])
    matches = [row for row in live["entries"] if row["publication_id"] == PUBLICATION_ID]
    assert (len(live["entries"]) == 496 and not matches) or \
           (len(live["entries"]) >= 497 and len(matches) == 1 and typed_equal(matches[0], entry))
    selection = read(HERE / "preserved-context/root-selection.json")
    assert len(selection["accepted_source_refs"]) == 76
    sources = sources_for_index(context)
    return {"schema": "i04-var03-v101-bounded-original-evidence-index/v1",
            "publication_id": PUBLICATION_ID, "decision": "GO_POSTRUN_BOUNDED", "run_id": RUN_ID,
            "new_native_runs": 1, "accepted_parent_runs_repeated": 0,
            "source_count": len(sources), "source_files": sources,
            "raw_count": 153, "raw_files": raw["records"],
            "preflight_original_count": 15, "preflight_original_files": preflight["records"],
            "accepted_source_pairs": selection["accepted_source_refs"],
            "historical_catalog": {"prefix_entries": 496,
                                   "local_archive": selection["catalog_local"],
                                   "base_git_blob": selection["catalog_git"],
                                   "always_check_live_prefix_metadata_unique_ids": True},
            "custody": {"frozen_prelaunch_owned_sources": 251,
                        "frozen_prelaunch_manifest_records": 456,
                        "prelaunch_context_originals": 181,
                        "private_local_only_originals": 2,
                        "postrun_small_owned_copies": 111,
                        "development_owned_copies": 13,
                        "postrun_map_sha256": context_summary["map_sha256"],
                        "development_map_sha256": dev_summary["sha256"]},
            "independent_verdict": captured_verdict(context),
            "author_receipts": author_receipts(),
            "limitations": ["One original fixed-source child; accepted parent was not rerun.",
                            "Accepted, child, transport, and preflight original bytes remain mandatory.",
                            "Two unrelated-chat app-context originals are mandatory local-only, never published as full copies.",
                            "The v1.0.0 routing NO_GO and v1.0.1 WTS hold remain historical evidence.",
                            "No general transfer, identity, GUI, performance, or cross-engine claim."],
            "postindex_review_excluded_prefixes": list(EXCLUDED_REVIEW_PREFIXES)}


def sources_for_index(context):
    return sources(context)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    assert not (args.dry and args.write)
    value = build()
    data = encode(value)
    if args.write:
        assert not INDEX.exists()
        with INDEX.open("xb") as stream:
            stream.write(data)
    elif not args.dry:
        assert INDEX.read_bytes() == data
    print(json.dumps({"schema": value["schema"], "source_count": value["source_count"],
                      "raw_count": value["raw_count"],
                      "preflight_original_count": value["preflight_original_count"],
                      "bytes": len(data), "sha256": pin_bytes(data),
                      "written": args.write, "native_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()

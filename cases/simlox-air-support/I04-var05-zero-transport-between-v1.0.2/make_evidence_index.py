"""Deterministic postrun index; default and --dry perform byte audits only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from copy_postrun_context import candidate as context_candidate, development
from make_preflight_custody import candidate as preflight_candidate
from make_raw_custody import candidate as raw_candidate
from source_gate import HERE, REPO, verify as source_verify

INDEX = HERE / "evidence-index.json"
INVENTORY = HERE / "source-inventory.json"
MANIFEST = HERE / "prelaunch-manifest.json"
RUN = REPO / "tmp/native-runs/i04v05-v102-20261008-01"
CATALOG = REPO / "cases/simlox-air-support/publication-index-v1.json"
PUBLICATION_ID = "I04.var05.zero_transport_between.1.0.2"
INVENTORY_PIN = {"bytes": 74886, "sha256": "b7a106a15be1c19e62e0ca2a952afcfe02e71a3fa110d26de9db38c75fe78cf8"}
MANIFEST_PIN = {"bytes": 1489689, "sha256": "4929d0003ab466460cba8e23192f3cbcac46cedc8b3a3e70da010267048f378c"}
FROZEN_READER_SHA = "1011bb6e21719cf767cc416610ffb11d02c1f819e56a0ae03d0a081fed5b14b2"
SUPPLEMENTAL_READER_SHA = "7c8a30b3ca51b9db17614ba24617f84b1000845a86d6c73485bbf6402ca917b0"
GO_SHA = "f0d384471a25d4a74f4487357ea4ca70c64ed6ea095f17f6e5f6daff49cffb80"
OLD_NO_GO_SHA = "dcfd7bceee7df9c6fa717e05c30949f765e18cf03e8a6407c6ce552e5523c1a4"
EXCLUDED_REVIEW_PREFIXES = ("review/independent-content-", "review/independent-staged-",
                            "review/independent-remote-", "review/independent-pr-")
EXTRA_REVIEW = (
    "review/preflight-ssh0-20261008T102550066Z.json",
    "review/independent-prelaunch-inventory-candidate-go.json",
    "review/independent-prelaunch-manifest-candidate-go.json",
    "review/independent-prelaunch-pure-go-2026-10-08.md",
    "review/independent-prelaunch-go.json",
    "review/independent-prelaunch-go-2026-10-08.md",
    "review/independent-postrun-receipt-reader-v1.py",
    "review/independent-postrun-go.json",
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


def pin_bytes(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def pin(path: Path) -> dict:
    return pin_bytes(path.read_bytes())


def read(path: Path) -> dict:
    return json.loads(path.read_bytes())


def encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def owned_bytes(context: dict, suffix: str) -> bytes:
    found = [r for r in context["records"] if
             r["original_path"].replace("\\", "/").endswith(suffix)]
    assert len(found) == 1, suffix
    row = found[0]
    data = (HERE / row["owned_copy"]).read_bytes()
    assert pin_bytes(data) == {k: row[k] for k in ("bytes", "sha256")}
    return data


def capture(context: dict, prefix: str, expected_exit: int) -> tuple[dict, bytes]:
    assert type(expected_exit) is int
    receipt = json.loads(owned_bytes(context, prefix + "/receipt.json"))
    stdout = owned_bytes(context, prefix + "/stdout.bin")
    stderr = owned_bytes(context, prefix + "/stderr.bin")
    assert type(receipt["actual_exit"]) is int and receipt["actual_exit"] == expected_exit
    streams = receipt["streams"]
    assert streams["stdout.bin"] == pin_bytes(stdout)
    assert streams["stderr.bin"] == pin_bytes(stderr)
    if expected_exit == 0:
        assert stderr == b""
    else:
        assert stdout == b"" and stderr
    return receipt, stdout


def sources(context: dict, dev: dict) -> list[dict]:
    assert pin(INVENTORY) == INVENTORY_PIN and pin(MANIFEST) == MANIFEST_PIN
    frozen = read(INVENTORY)
    manifest = read(MANIFEST)
    assert frozen["source_count"] == len(frozen["source_files"]) == 198
    assert manifest["source_count"] == len(manifest["source_files"]) == 4203
    base = [row["relative_path"] for row in frozen["source_files"]]
    assert len(base) == len(set(base))
    for row in frozen["source_files"]:
        assert pin(HERE / row["relative_path"]) == {k: row[k] for k in ("bytes", "sha256")}
    copies = [row["owned_copy"] for row in context["records"]]
    assert copies == [f"preserved-postrun/postrun-{i:03d}.bytes" for i in range(len(copies))]
    drafts = [row["owned_copy"] for row in dev["drafts"]]
    assert drafts == [f"preserved-postrun-development/draft-{i:03d}.bytes" for i in range(3)]
    extra = [*EXTRA_AUTHOR, *EXTRA_REVIEW, "preserved-postrun/custody.json",
             "preserved-postrun-development/custody.json", *copies, *drafts]
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


def captured_verdict(context: dict) -> dict:
    assert pin(HERE / "review/independent_replay.py")["sha256"] == FROZEN_READER_SHA
    assert pin(HERE / "review/independent-postrun-receipt-reader-v1.py")["sha256"] == SUPPLEMENTAL_READER_SHA
    assert pin(HERE / "review/independent-postrun-go.json")["sha256"] == GO_SHA
    assert pin(REPO / "tmp/i04-var05-v102-independent-postrun-no-go-20261008.md")["sha256"] == OLD_NO_GO_SHA
    old = "tmp/i04-var05-root-sealed-replay-v102-20261008/20261008T103341946032Z-fb4f3039"
    first, _ = capture(context, old, 1)
    assert first["streams"]["stderr.bin"]["sha256"] == "cb5e73a8956fd874029ff3f4ad9ef2c88522f9d77f1d52f001cbec67a5bc7c4f"
    new = "tmp/i04-var05-root-supplemental-replay-v102-20261008/20261008T104257687711Z-edc7361d"
    receipt, stdout = capture(context, new, 0)
    assert receipt["source_map_unchanged"] is True
    assert receipt["method_before"] == receipt["method_after"]
    assert receipt["method_before"]["reader"]["sha256"] == SUPPLEMENTAL_READER_SHA
    assert receipt["method_before"]["manifest"] == MANIFEST_PIN
    verdict = json.loads(stdout)
    assert verdict == {"converter_lines": 17, "decision": "GO_BOUNDED",
                       "historical_catalog_prefix_entries": 497, "log_lines": 118,
                       "original_raw_files": 25, "paired_differences": 3,
                       "report_cells_checked": 4044,
                       "run_id": "i04-var05-zero-transport-between-v102-ssh-20261008-01",
                       "source_roles": 4203, "timed_event_records": 104,
                       "unique_physical_paths": 1257}
    audit = "tmp/i04-var05-root-review-proofs-v102-20261008/supplemental-direct-byte-audit-20261008T104443832006Z-1b84d6aa"
    capture(context, audit, 0)
    negative = "tmp/i04-var05-root-review-proofs-v102-20261008/supplemental-negatives-20261008T104127750871Z-bd09d9a6"
    capture(context, negative, 0)
    return {"first_frozen_reader_decision": "NO_GO_POSTRUN_AS_FROZEN",
            "first_frozen_reader_receipt_sha256": "910a3e062b7eae6bc28ba4d9f1b7ad10c12eecfe9db047fdc61d39993bc3e417",
            "supplemental_decision": verdict,
            "supplemental_receipt_sha256": "4cef9905050cb3b0418bfd40bdb63e0ee8537b96d21b904fabc25a12d61b4348",
            "direct_audit_receipt_sha256": "2b54220d4d1c43ea5ced28da15fd0c3b860a037ad5ada8141b59418f309e634b"}


def author_receipts() -> dict:
    rt, behavior = read(RUN / "roundtrip-validation.json"), read(RUN / "author-validation.json")
    assert rt["schema"] == "i04-var05-zero-between-roundtrip/v102"
    assert rt["passed"] is True and rt["issues"] == []
    assert {k: rt[k] for k in ("tables", "authored_rows", "authored_cells",
                                   "exported_rows", "exported_cells", "all_null_placeholder_tables")} == {
        "tables": 34, "authored_rows": 22, "authored_cells": 223,
        "exported_rows": 40, "exported_cells": 407, "all_null_placeholder_tables": 18}
    assert behavior["schema"] == "i04-var05-zero-between-behavior/v102"
    assert behavior["passed"] is True and behavior["issues"] == []
    assert behavior["native_run_directory"] == str(RUN)
    for key, expected in (("report_cell_checks", 4044), ("paired_differences", 3),
                          ("log_lines", 118), ("timed_event_records", 104),
                          ("native_calls", 0)):
        assert type(behavior[key]) is int and behavior[key] == expected
    assert behavior["terminal"]["target_ready_terminal"] == 2
    assert rt["input_sha256"] == behavior["input_sha256"] == pin(HERE / "native-input.json")["sha256"]
    assert rt["export_sha256"] == behavior["export_sha256"] == pin(RUN / "roundtrip-raw.json")["sha256"]
    return {"roundtrip_passed": True, "behavior_passed": True,
            "child_report_cells": 4044, "paired_report_differences": 3,
            "observed_log_lines": 118, "observed_timed_events": 104}


def build() -> dict:
    gate = source_verify("sealed")
    assert gate["accepted_current_disk_git_pairs"] == 403
    assert gate["mandatory_accepted_original_raw"] == 168
    assert gate["catalog"]["historical_prefix_checked"] == 497
    context_summary = context_candidate()
    dev_summary = development()
    context = read(HERE / "preserved-postrun/custody.json")
    dev = read(HERE / "preserved-postrun-development/custody.json")
    assert len(context["records"]) == context_summary["records"]
    assert dev_summary["drafts"] == 3 and dev_summary["partial_originals"] == 96
    raw = raw_candidate()
    pref = preflight_candidate()
    assert len(raw["records"]) == raw["mandatory_original_count"] == 207
    assert len(pref["records"]) == pref["mandatory_original_count"] == 15
    assert (HERE / "raw-custody-map.json").read_bytes() == encode(raw)
    assert (HERE / "preflight-custody-map.json").read_bytes() == encode(pref)
    entry = read(HERE / "publication-entry.json")
    assert entry["publication_id"] == PUBLICATION_ID
    assert type(entry["new_native_runs"]) is int and entry["new_native_runs"] == 1
    assert type(entry["accepted_parent_runs_repeated"]) is int and entry["accepted_parent_runs_repeated"] == 0
    live = read(CATALOG)
    archived = read(HERE / "preserved-context/catalog-local-497.json.bytes")
    assert archived["entries"] == live["entries"][:497]
    matches = [row for row in live["entries"] if row["publication_id"] == PUBLICATION_ID]
    assert (len(live["entries"]) == 497 and not matches) or \
           (len(live["entries"]) >= 498 and len(matches) == 1 and matches[0] == entry)
    source_rows = sources(context, dev)
    return {"schema": "i04-var05-v102-bounded-original-evidence-index/v1",
            "publication_id": PUBLICATION_ID, "decision": "GO_BOUNDED_SUPPLEMENTAL_AFTER_FROZEN_NO_GO",
            "run_id": "i04-var05-zero-transport-between-v102-ssh-20261008-01",
            "new_native_runs": 1, "accepted_parent_runs_repeated": 0,
            "source_count": len(source_rows), "source_files": source_rows,
            "raw_count": 207, "raw_files": raw["records"],
            "preflight_original_count": 15, "preflight_original_files": pref["records"],
            "accepted_source_pairs": 403,
            "historical_catalog": {"prefix_entries": 497,
                                   "owned_local": gate["catalog"]["owned_local"],
                                   "owned_git": gate["catalog"]["owned_git"],
                                   "always_check_live_prefix_metadata_unique_ids": True},
            "custody": {"frozen_prelaunch_owned_sources": 198,
                        "frozen_prelaunch_manifest_records": 4203,
                        "postrun_small_owned_copies": len(context["records"]),
                        "development_owned_drafts": 3,
                        "development_partial_originals": 96,
                        "historical_private_originals_local_only": 2,
                        "postrun_map_sha256": context_summary["map_sha256"],
                        "development_map_sha256": dev_summary["sha256"]},
            "independent_verdict": captured_verdict(context),
            "author_receipts": author_receipts(),
            "limitations": ["One fixed-source original child; accepted parent was not rerun.",
                            "The frozen prelaunch reader's original receipt failure remains NO_GO.",
                            "The supplemental reader added only the exact path receipt key and its strict type/value check.",
                            "Accepted, child, native transport and preflight originals remain mandatory on the host.",
                            "Two private app-context originals remain local-only; no full unrelated-chat snapshot is published.",
                            "No general transfer, identity, GUI, performance or cross-engine claim."],
            "postindex_review_excluded_prefixes": list(EXCLUDED_REVIEW_PREFIXES)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    assert not (args.dry and args.write)
    value = build()
    data = encode(value)
    if args.write:
        assert not INDEX.exists()
        with INDEX.open("xb") as out:
            out.write(data)
    elif not args.dry:
        assert INDEX.read_bytes() == data
    print(json.dumps({"schema": value["schema"], "source_count": value["source_count"],
                      "raw_count": value["raw_count"],
                      "preflight_original_count": value["preflight_original_count"],
                      "bytes": len(data), "sha256": pin_bytes(data)["sha256"],
                      "written": args.write, "native_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()

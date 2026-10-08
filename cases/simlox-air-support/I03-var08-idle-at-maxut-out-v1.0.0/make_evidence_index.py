"""Deterministic I03.var08 original-evidence index; default and --dry are read-only.

This rehashes recorded originals and captured receipts. It does not rerun native,
accepted-parent, author, checker or independent behavior procedures.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from copy_postrun_context import candidate as context_candidate, body as context_body
from make_preflight_custody import candidate as preflight_candidate, body as preflight_body
from make_raw_custody import candidate as raw_candidate, body as raw_body
from source_gate import HERE, REPO, catalog, git_tree, parse, pin, verify as verify_source

INDEX = HERE / "evidence-index.json"
INVENTORY = HERE / "source-inventory.json"
MANIFEST = HERE / "prelaunch-manifest.json"
RUN_ID = "i03-var08-idle-maxut-out-v100-ssh-20261008-01"
RUN = HERE / "runs" / RUN_ID
PUBLICATION_ID = "I03.var08.idle_maxut_out.1.0.0"
INVENTORY_SHA = "f2bc7bea6d68ef404b8fcb990b58e8ba27e428869922eec44713a8ce99be5ece"
MANIFEST_SHA = "e93579a085ca6716cbf9778724a1454a726016af49a64db5a4017a07d1905b78"
INDEPENDENT_SHA = "4f2a96484c181260ae3586658caa984556562e2bae5ff7ab3211f602dded5cda"
INDEPENDENT_GO_SHA = "f237e4f09c5429706a7c5dcdb1e49f66ce14ba792666e72fcd0cdcb4579866de"
INDEPENDENT_STDOUT_SHA = "983d6577b42076a18ba8c29807194c41bd2a87812951660309edeab49bbab7b3"
ROOT_NATIVE_RECEIPT_SHA = "704f155d7358d2be719029c2f518c7c906e3dd814d39ea6ba7469c5bc9012a25"
EXCLUDED_REVIEW_PREFIXES = ("review/independent-content-", "review/independent-staged-",
                            "review/independent-remote-", "review/independent-pr-")
ADDITIONAL = (
    "source-inventory.json", "prelaunch-manifest.json",
    "publication-entry.json", "README-publication.md", "REPRODUCTION-postrun.md",
    "cli-scope-signoff-2026-10-08.md",
    "copy_postrun_context.py", "postrun-context-originals.json", "postrun-context-custody.json",
    "make_raw_custody.py", "raw-custody-map.json",
    "make_preflight_custody.py", "preflight-custody-map.json",
    "make_evidence_index.py",
    "review/preflight-ssh0-20261008T032845886Z.json",
    "review/independent-prelaunch-go.json",
    "review/independent-prelaunch-go-2026-10-08.md",
    "review/independent-postrun-go-2026-10-08.md",
    "preserved-postrun-development/README-publication-overclaim-draft.bytes",
    "preserved-postrun-development/signoff-overclaim-draft.bytes",
    "preserved-postrun-development/publication-entry-overclaim-draft.bytes",
)


def strict_json(data: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key {key}")
            result[key] = value
        return result
    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def body(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def custody_copy(context: dict, original_suffix: str) -> bytes:
    rows = [row for row in context["records"] if
            row["original_path"].replace("\\", "/").endswith(original_suffix)]
    assert len(rows) == 1, original_suffix
    data = (HERE / rows[0]["owned_copy"]).read_bytes()
    assert pin(data) == {key: rows[0][key] for key in ("bytes", "sha256")}
    return data


def source_files(context: dict) -> list[dict]:
    inv_bytes = INVENTORY.read_bytes()
    assert pin(inv_bytes)["sha256"] == INVENTORY_SHA
    inventory = strict_json(inv_bytes)
    assert inventory["source_count"] == len(inventory["source_files"]) == 85
    frozen = [row["relative_path"] for row in inventory["source_files"]]
    assert len(frozen) == len(set(frozen))
    for row in inventory["source_files"]:
        assert pin((HERE / row["relative_path"]).read_bytes()) == \
               {key: row[key] for key in ("bytes", "sha256")}
    assert pin(MANIFEST.read_bytes())["sha256"] == MANIFEST_SHA
    manifest = strict_json(MANIFEST.read_bytes())
    assert manifest["source_count"] == len(manifest["source_files"]) == 287
    extras = list(ADDITIONAL) + [row["owned_copy"] for row in context["records"]]
    assert len(extras) == len(set(extras)) and not set(extras).intersection(frozen)
    expected = set(frozen) | set(extras)
    actual = {path.relative_to(HERE).as_posix() for path in HERE.rglob("*")
              if path.is_file() and path.name != INDEX.name
              and not any(part in {"runs", "transport-evidence", "test-output", "__pycache__"}
                          for part in path.relative_to(HERE).parts)
              and not any(path.relative_to(HERE).as_posix().startswith(prefix)
                          for prefix in EXCLUDED_REVIEW_PREFIXES)}
    assert actual == expected, {"unindexed": sorted(actual - expected),
                                "missing": sorted(expected - actual)}
    return [{"path": name, **pin((HERE / name).read_bytes())} for name in sorted(expected)]


def captured_verdict(context: dict) -> dict:
    assert pin((HERE / "review/independent_replay.py").read_bytes())["sha256"] == INDEPENDENT_SHA
    assert pin((HERE / "review/independent-postrun-go-2026-10-08.md").read_bytes())["sha256"] == INDEPENDENT_GO_SHA
    stdout = custody_copy(context, "tmp/i03-var08-independent-sealed-native-20261008-01/stdout.bin")
    stderr = custody_copy(context, "tmp/i03-var08-independent-sealed-native-20261008-01/stderr.bin")
    receipt = strict_json(custody_copy(context,
                    "tmp/i03-var08-independent-sealed-native-20261008-01/receipt.json"))
    assert type(receipt["actual_exit"]) is int and receipt["actual_exit"] == 0
    assert receipt["method"]["sha256"] == INDEPENDENT_SHA
    assert receipt["stdout"] == pin(stdout) and pin(stdout)["sha256"] == INDEPENDENT_STDOUT_SHA
    assert receipt["stderr"] == pin(stderr) == pin(b"")
    verdict = strict_json(stdout)
    assert verdict == {"closure_raw_files": 23, "export_cells": 383,
                       "mode": "GO_BOUNDED_SEALED_ORIGINAL_NATIVE",
                       "native_and_checker_stages": 6, "original_run_files": 25,
                       "report_cells": 5210, "source_and_custody_pins": 232,
                       "source_cells": 242, "timed_events": 113}
    return verdict


def author_receipts() -> dict:
    roundtrip = strict_json((RUN / "roundtrip-validation.json").read_bytes())
    behavior = strict_json((RUN / "author-validation.json").read_bytes())
    assert roundtrip["schema"] == "i03-var08-idle-maxut-roundtrip/v1"
    assert roundtrip["passed"] is True and roundtrip["issues"] == []
    assert [roundtrip[key] for key in ("tables", "authored_rows", "exported_rows",
                                        "authored_cells", "exported_cells",
                                        "all_null_placeholder_tables")] == [36, 28, 39, 242, 383, 11]
    assert roundtrip["input_sha256"] == pin((HERE / "native-input.json").read_bytes())["sha256"]
    assert roundtrip["export_sha256"] == pin((RUN / "roundtrip-raw.json").read_bytes())["sha256"]
    assert behavior["schema"] == "i03-var08-idle-maxut-behavior/v1"
    assert behavior["passed"] is True and behavior["issues"] == []
    assert behavior["run_id"] == RUN_ID and behavior["input_sha256"] == roundtrip["input_sha256"]
    assert type(behavior["report_cell_checks"]) is type(behavior["timed_event_records"]) is int
    assert behavior["report_cell_checks"] == 5210 and behavior["timed_event_records"] == 113
    terminal = behavior["timeline"]["terminal"]
    assert {key: terminal[key] for key in ("local", "nominal", "booked", "reserved_OUT",
                                            "pending_OUT", "backorder", "ready_aircraft")} == \
           {"local": 1, "nominal": 1, "booked": 0, "reserved_OUT": 0,
            "pending_OUT": 0, "backorder": 0, "ready_aircraft": 2}
    return {"roundtrip": roundtrip, "behavior": behavior}


def build() -> dict:
    assert (HERE / ".gitattributes").read_bytes() == b"* -text\n"
    gate = verify_source("sealed")
    assert gate["counts"] == {"accepted_source_git_pairs": 81,
                               "mandatory_accepted_original_raw": 108,
                               "required_docs": 8, "installed": 3}
    assert gate["catalog"]["historical_prefix_checked"] == 495
    context = context_candidate()
    assert context_body(context) == (HERE / "postrun-context-custody.json").read_bytes()
    assert len(context["records"]) == 86
    raw = raw_candidate()
    assert raw_body(raw) == (HERE / "raw-custody-map.json").read_bytes()
    assert len(raw["records"]) == 147
    preflight = preflight_candidate()
    assert preflight_body(preflight) == (HERE / "preflight-custody-map.json").read_bytes()
    assert len(preflight["records"]) == 15
    root_receipt_bytes = custody_copy(context,
                         "tmp/i03-var08-root-native-dispatch-20261008-01/receipt.json")
    assert pin(root_receipt_bytes)["sha256"] == ROOT_NATIVE_RECEIPT_SHA
    root_receipt = strict_json(root_receipt_bytes)
    assert type(root_receipt["actual_exit"]) is int and root_receipt["actual_exit"] == 0
    assert type(root_receipt["native_transport_attempts"]) is int
    assert root_receipt["native_transport_attempts"] == 1 and root_receipt["safe_native_boundary"] is True
    verdict = captured_verdict(context)
    authors = author_receipts()
    entry = strict_json((HERE / "publication-entry.json").read_bytes())
    assert entry["publication_id"] == PUBLICATION_ID
    assert type(entry["new_native_runs"]) is int and entry["new_native_runs"] == 1
    assert type(entry["accepted_parent_runs_repeated"]) is int and entry["accepted_parent_runs_repeated"] == 0
    design = strict_json((HERE / "contract.json").read_bytes())
    tree = git_tree(design["lineage"]["base_commit"])
    # The source gate always checks the archived 495-entry catalog, base Git
    # blob, typed live prefix, metadata and unique IDs. An authorized append
    # adds this exact entry, without changing the canonical index payload.
    live = parse((REPO / "cases/simlox-air-support/publication-index-v1.json").read_bytes())
    matches = [row for row in live["entries"] if row["publication_id"] == PUBLICATION_ID]
    assert (not matches and len(live["entries"]) == 495) or matches == [entry]
    sources = source_files(context)
    dual = design["lineage"]["accepted_81_local_and_base_git_refs"]
    assert len(dual) == 81 and len(tree) >= 81
    return {"schema": "i03-var08-bounded-original-evidence-index/v1",
            "publication_id": PUBLICATION_ID, "decision": "GO_BOUNDED_SEALED_ORIGINAL_NATIVE",
            "run_id": RUN_ID, "accepted_parent_runs_repeated": 0, "new_native_runs": 1,
            "source_count": len(sources), "source_files": sources,
            "raw_count": 147, "raw_files": raw["records"],
            "preflight_original_count": 15, "preflight_original_files": preflight["records"],
            "accepted_source_pairs": dual,
            "historical_catalog": {"prefix_entries": 495,
                                   "owned_archive_path": "preserved-context/context-17.bytes",
                                   "owned_archive": design["lineage"]["catalog_local_495"],
                                   "base_git_blob": design["lineage"]["catalog_git_495"],
                                   "always_check_live_prefix_metadata_unique_ids": True},
            "proof_custody": {"prelaunch_context_copies": 19,
                              "prelaunch_pure_proof_copies": 13,
                              "postrun_context_copies": context["records"]},
            "independent_verdict": verdict,
            "author_receipts": {"roundtrip": authors["roundtrip"],
                                "behavior_passed": authors["behavior"]["passed"],
                                "child_report_cells": authors["behavior"]["report_cell_checks"]},
            "limitations": ["One original fixed-source OUT child; accepted C08 parent not rerun.",
                            "Accepted/new/preflight original raw remains mandatory at sealed paths.",
                            "Presentation zeros/nulls are bounded native conventions.",
                            "No person identity, general MAXUT law, GUI, performance or cross-engine claim."],
            "postindex_review_excluded_prefixes": list(EXCLUDED_REVIEW_PREFIXES)}


def main() -> None:
    args = sys.argv[1:]
    assert args in ([], ["--dry"], ["--write"])
    document = build()
    data = body(document)
    if args == ["--write"]:
        assert not INDEX.exists()
        INDEX.write_bytes(data)
    elif args == []:
        assert INDEX.read_bytes() == data
    print(json.dumps({"schema": "i03-var08-evidence-index-check/v1",
                      "source_count": document["source_count"], "raw_count": 147,
                      "preflight_original_count": 15, "bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest(),
                      "written": args == ["--write"]}, sort_keys=True))


if __name__ == "__main__":
    main()

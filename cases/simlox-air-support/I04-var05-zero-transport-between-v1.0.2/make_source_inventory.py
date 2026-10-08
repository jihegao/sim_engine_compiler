"""Closed execution-source inventory with explicit future publication routing."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = "i04-var05-zero-between-owned-source-inventory/v102"
CORE = (
    ".gitattributes", ".gitignore", "README.md", "REPRODUCTION.md",
    "prospective-contract.json", "prospective-log-oracle.json", "prospective-report-oracle.json",
    "execution-contract.json", "native-input.json", "exact-diff.json",
    "child-report-oracle.json", "child-roundtrip-oracle.json", "model_common.py", "build.py",
    "check_roundtrip.py", "event_ledger.py", "report_oracle.py", "validate_native_cli.py",
    "self_check.py", "source_gate.py", "copy_context.py", "context-custody.json",
    "captured_process.ps1", "checker_receipt.ps1", "preflight_receipt.ps1",
    "run_native_ssh.ps1", "ssh_transport.py", "test_converter_gate.ps1",
    "pure_proof.py", "make_source_inventory.py", "make_prelaunch_manifest.py",
    "copy_pure_proof.py", "pure-proof-custody.json",
    "copy_extra_context.py", "extra-context-custody.json",
    "copy_v102_context.py", "v102-context-custody.json",
)
PRESERVED_DEVELOPMENT = (
    "build-before-contract-pin.py.bytes",
    "source_gate-before-contract-pin.py.bytes",
    "exact-diff-v100-template.json.bytes",
    "make-manifest-v100-path-assumption.py.bytes",
    "make-manifest-v100-context-assumption.py.bytes",
    "manifest-provisional-diagnostics.md",
    "exact-diff-v101-template.json.bytes",
    "build-v102-existing-diff-diagnostic.md",
)
DESCRIPTIVE_CONTEXT = (
    "catalog-local-497.json.bytes", "catalog-git-497.json.bytes",
    "selection.json.bytes",
)
EXTRA_CONTEXT = tuple(f"preserved-extra/extra-{n:03d}.bytes" for n in range(22))
REVIEW = (
    "review/independent_replay.py", "review/independent_self_check.py",
    "review/independent-method-static-go-2026-10-08.md",
    "review/preserved-independent-v1-v100-template.py.bytes",
    "review/preserved-independent-v2-before-recovery-custody.py.bytes",
    "review/preserved-independent-v3-before-manifest-counters.py.bytes",
    "review/preserved-self-check-v1-v100-template.py.bytes",
    "review/preserved-independent-v1-v101-template.py.bytes",
    "review/preserved-self-check-v1-v101-template.py.bytes",
)
FUTURE_AUTHOR = (
    "README-publication.md", "REPRODUCTION-postrun.md", "results-summary.json",
    "cli-scope-signoff-2026-10-08.md", "publication-entry.json",
    "make_evidence_index.py", "evidence-index.json", "copy_postrun_context.py",
    "postrun-context-originals.json", "postrun-context-custody.json",
    "make_raw_custody.py", "raw-custody-map.json",
    "make_preflight_custody.py", "preflight-custody-map.json",
)
FUTURE_GENERATED = (
    r"preserved-postrun/postrun-[0-9]{3}\.bytes",
    r"preserved-postrun-development/draft-[0-9]{3}\.bytes",
    r"preserved-raw/raw-[0-9]{3}\.bytes",
    r"preserved-preflight/preflight-[0-9]{3}\.bytes",
)
FUTURE_CUSTODY = (
    "preserved-postrun/custody.json", "preserved-postrun-development/custody.json",
    "preserved-raw/custody.json", "preserved-preflight/custody.json",
)
FUTURE_REVIEW_PREFIXES = (
    "review/independent-prelaunch-", "review/independent-postrun-",
    "review/independent-content-", "review/independent-staged-",
    "review/independent-remote-", "review/independent-pr-", "review/preflight-ssh0-",
)


def allowed_future(relative):
    if relative in FUTURE_AUTHOR or relative in FUTURE_CUSTODY:
        return True
    if any(re.fullmatch(pattern, relative) for pattern in FUTURE_GENERATED):
        return True
    for prefix in FUTURE_REVIEW_PREFIXES:
        if relative.startswith(prefix):
            suffix = relative[len(prefix):]
            return bool(suffix) and "/" not in suffix and "\\" not in suffix
    return False


def paths(provisional=False):
    names = [name for name in CORE if not (provisional and name == "pure-proof-custody.json")]
    names += ["preserved-development/" + name for name in PRESERVED_DEVELOPMENT]
    names += ["preserved-context/" + name for name in DESCRIPTIVE_CONTEXT]
    names += [f"preserved-context/context-{n:03d}.bytes" for n in range(78)]
    names += list(EXTRA_CONTEXT)
    names += [f"preserved-v102-context/context-{n:03d}.bytes" for n in range(20)]
    if not provisional:
        names += [f"preserved-pure-proof/pure-{n:02d}.bytes" for n in range(21)]
        names += list(REVIEW)
    assert len(names) == len(set(names))
    return names


def pin(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def candidate(provisional=False):
    contract = json.loads((HERE / "prospective-contract.json").read_bytes())
    assert tuple(contract["canonical_freeze_protocol"]["agreed_ordered_review_files"]) == REVIEW[:7]
    names = paths(provisional)
    records = []
    for relative in names:
        path = HERE / relative
        assert path.is_file(), relative
        records.append({"relative_path": relative, "path": str(path.resolve(strict=True)), **pin(path)})
    assert len({row["path"].lower() for row in records}) == len(records)
    known = set(names)
    for path in HERE.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(HERE).as_posix()
        if relative in known or relative in ("source-inventory.json", "prelaunch-manifest.json"):
            continue
        if relative.split("/", 1)[0] in ("runs", "test-output", "transport-evidence"):
            continue
        if "__pycache__" in path.relative_to(HERE).parts and relative.endswith(".pyc"):
            continue
        if allowed_future(relative):
            continue
        if provisional and (relative.startswith("review/") or relative == "pure-proof-custody.json" or
                            relative.startswith("preserved-pure-proof/")):
            continue
        raise AssertionError(f"unlisted publishable source: {relative}")
    return {"schema": SCHEMA, "source_count": len(records), "source_files": records,
            "provisional": provisional,
            "excluded_future": ["runs/", "test-output/", "transport-evidence/",
                                *FUTURE_AUTHOR, *FUTURE_GENERATED, *FUTURE_CUSTODY,
                                *FUTURE_REVIEW_PREFIXES]}


def body(document):
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def main():
    args = sys.argv[1:]
    external_candidate = len(args) == 2 and args[0] == "--candidate"
    assert external_candidate or args in ([], ["--dry"], ["--provisional"], ["--write"])
    provisional = args == ["--provisional"]
    data = body(candidate(provisional))
    target = HERE / "source-inventory.json"
    if external_candidate:
        external = Path(args[1]).absolute()
        assert external.parent.is_dir() and not external.exists()
        assert external.is_relative_to(HERE.parents[2] / "tmp")
        with external.open("xb") as stream:
            stream.write(data)
    elif args == ["--write"]:
        assert not target.exists()
        with target.open("xb") as stream:
            stream.write(data)
    elif not args:
        assert target.read_bytes() == data
    print(json.dumps({"schema": SCHEMA, "source_count": len(candidate(provisional)["source_files"]),
                      "sha256": hashlib.sha256(data).hexdigest(), "written": args == ["--write"],
                      "candidate_written": external_candidate,
                      "provisional": provisional}, sort_keys=True))


if __name__ == "__main__":
    main()

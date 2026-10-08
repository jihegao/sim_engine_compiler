"""Closed execution-source inventory with explicit postrun routing."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCHEMA = "i04-var10-horizon-transit-owned-source-inventory/v101"
CORE = (
    ".gitattributes", ".gitignore", "README.md", "REPRODUCTION.md",
    "prospective-contract.json", "prospective-contract.md", "prospective-log-oracle.json",
    "prospective-report-oracle.json", "prospective-source-delta.json", "execution-contract.json",
    "native-input.json", "exact-diff.json", "child-report-oracle.json",
    "child-roundtrip-oracle.json", "parent-source-pairs.json", "raw-custody-map.json",
    "preflight-custody-map.json", "prospective-proof-custody.json",
    "make_prospective_proof_custody.py", "model_common.py", "build.py", "make_parent_custody.py",
    "check_roundtrip.py", "event_ledger.py", "report_oracle.py", "validate_native_cli.py",
    "self_check.py", "source_gate.py", "copy_context.py", "context-custody.json",
    "captured_process.ps1", "checker_receipt.ps1", "preflight_receipt.ps1",
    "run_native_ssh.ps1", "ssh_transport.py", "test_converter_gate.ps1",
    "pure_proof.py", "copy_pure_proof.py", "pure-proof-custody.json",
    "make_source_inventory.py", "make_prelaunch_manifest.py",
)
PRESERVED_DEVELOPMENT = (
    "source-gate-v1-cwd-dependent-accepted-refs.py.bytes",
    "context-custody-v1-optional-originals.json.bytes",
    "copy-context-v2-mandatory-originals.py.bytes",
    "preflight-native-path-array-static-finding.md",
    "test-converter-v1-reparse-extraction-failure.ps1.bytes",
    "test-converter-v1-reparse-extraction-failure.md",
    "test-converter-v2-junction-removal-failure.ps1.bytes",
    "test-converter-v2-junction-removal-failure.md",
    "source-gate-v2-development-count-drift.py.bytes",
    "manifest-v1-development-count-drift.py.bytes",
    "manifest-v1-development-count-drift.md",
)
DESCRIPTIVE_CONTEXT = (
    "catalog-local-499.json.bytes", "catalog-git-499.json.bytes",
    "root-selection.json.bytes", "root-construction-boundary.json.bytes",
)
REVIEW = (
    "review/independent_replay.py", "review/independent_self_check.py",
    "review/preserved-independent-v1-v100-template.py.bytes",
    "review/preserved-self-check-v1-converter-line-ending-probe.md",
    "review/preserved-independent-v2-pure-fixture-native-report-mode.py.bytes",
    "review/preserved-independent-v2-pure-fixture-native-report-mode.md",
    "review/independent-method-static-go-2026-10-08.md",
)
FUTURE_AUTHOR = (
    "README-publication.md", "REPRODUCTION-postrun.md", "results-summary.json",
    "cli-scope-signoff-2026-10-08.md", "publication-entry.json", "make_evidence_index.py",
    "evidence-index.json", "copy_postrun_context.py", "postrun-context-custody.json",
    "postrun-context-originals.json", "make_raw_custody.py", "make_preflight_custody.py",
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


def ignored_generated(relative):
    parts = relative.split("/")
    if parts[0] in ("runs", "test-output", "transport-evidence") and len(parts) >= 2:
        return True
    return relative.endswith(".pyc") and (
        parts[:1] == ["__pycache__"] and len(parts) == 2 or
        parts[:2] == ["review", "__pycache__"] and len(parts) == 3)


def paths(provisional=False):
    names = [name for name in CORE if not (provisional and name == "pure-proof-custody.json")]
    names += ["preserved-development/" + name for name in PRESERVED_DEVELOPMENT]
    names += ["preserved-context/" + name for name in DESCRIPTIVE_CONTEXT]
    names += [f"preserved-context/context-{i:03d}.bytes" for i in range(30)]
    if not provisional:
        names += [f"preserved-pure-proof/pure-{i:02d}.bytes" for i in range(21)]
        names += list(REVIEW)
    assert len(names) == len(set(names))
    return names


def pin(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def candidate(provisional=False):
    names = paths(provisional)
    records = []
    for relative in names:
        path = HERE / relative
        assert path.is_file(), relative
        records.append({"relative_path": relative, "path": str(path.resolve(strict=True)), **pin(path)})
    assert len({row["path"].casefold() for row in records}) == len(records)
    known = set(names)
    for path in HERE.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(HERE).as_posix()
        if relative in known or relative in ("source-inventory.json", "prelaunch-manifest.json"):
            continue
        if ignored_generated(relative):
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
    external = len(args) == 2 and args[0] == "--candidate"
    assert external or args in ([], ["--dry"], ["--provisional"], ["--write"])
    provisional = args == ["--provisional"]
    data = body(candidate(provisional))
    target = HERE / "source-inventory.json"
    if external:
        output = Path(args[1]).absolute()
        assert output.parent.is_dir() and not output.exists() and output.is_relative_to(REPO / "tmp")
        with output.open("xb") as stream:
            stream.write(data)
    elif args == ["--write"]:
        assert not target.exists()
        with target.open("xb") as stream:
            stream.write(data)
    elif not args:
        assert target.read_bytes() == data
    print(json.dumps({"schema": SCHEMA, "source_count": len(candidate(provisional)["source_files"]),
                      "sha256": hashlib.sha256(data).hexdigest(), "written": args == ["--write"],
                      "candidate_written": external, "provisional": provisional}, sort_keys=True))


if __name__ == "__main__":
    main()

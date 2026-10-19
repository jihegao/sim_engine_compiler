"""Verify the fixed A01/STIM9 archives and optionally replay their frozen contents.

This entry never launches SIMLOX or executes preparation/native/PowerShell code.
Original Windows handle, readonly, queue and GUI evidence remains in the receipts.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent


def fingerprint(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-sha", required=True)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    raw_manifest = (ROOT / "archive-manifest.json").read_bytes()
    if hashlib.sha256(raw_manifest).hexdigest() != args.manifest_sha:
        raise ValueError("external archive manifest SHA differs")
    manifest = json.loads(raw_manifest)
    if manifest["schema"] != "issue18-A01-verified-directory-archive-delivery/v1":
        raise ValueError("unsupported archive delivery schema")
    if set(manifest["entry_files"]) != {"README.md", "verify_archives.py", ".gitattributes"}:
        raise ValueError("entry file set differs")
    for name, pin in manifest["entry_files"].items():
        if fingerprint((ROOT / name).read_bytes()) != pin:
            raise ValueError("entry file differs: " + name)
    expected = {"A01-case-local-native-and-guide-20261019-v1.zip",
                "A01-STIM9-directory-derivation-and-guide-20261019-v1.zip"}
    if {p["archive"] for p in manifest["archives"]} != expected or len(manifest["archives"]) != 2:
        raise ValueError("fixed archive set differs")
    results = []
    for package in manifest["archives"]:
        path = ROOT / package["archive"]
        if fingerprint(path.read_bytes()) != package["fingerprint"]:
            raise ValueError("archive bytes differ: " + path.name)
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("duplicate ZIP member")
            for info in archive.infolist():
                member = PurePosixPath(info.filename)
                if (member.is_absolute() or ".." in member.parts or
                        "\\" in info.filename or ":" in info.filename or
                        stat.S_ISLNK(info.external_attr >> 16)):
                    raise ValueError("unsupported archive path")
            raw_index = archive.read("delivery-index.json")
            if fingerprint(raw_index) != package["delivery_index"]:
                raise ValueError("inner index differs")
            index = json.loads(raw_index)
            if index["schema"] not in {"issue18-A01-case-local-directory-delivery/v1",
                                       "issue18-STIM9-case-local-directory-delivery/v1"}:
                raise ValueError("unsupported frozen inner index schema")
            files = {p["relative_path"]: {k: p[k] for k in ("bytes", "sha256")}
                     for p in index["files"]}
            if len(files) != len(index["files"]) or len(files) != package["indexed_files"]:
                raise ValueError("duplicate inner indexed path or count differs")
            if set(names) != set(files) | {"delivery-index.json"}:
                raise ValueError("inner file set differs")
            for name, pin in files.items():
                if fingerprint(archive.read(name)) != pin:
                    raise ValueError("inner file bytes differ: " + name)
            receipt = package["native_receipt"]
            raw = archive.read(receipt["member"])
            if fingerprint(raw) != receipt["fingerprint"]:
                raise ValueError("independent native receipt differs")
            terminal = json.loads(raw)
            if (terminal.get("decision") != receipt["decision"] or
                    terminal.get("run_id") != receipt["run_id"] or
                    not terminal.get("completed") or terminal.get("whole_scope_complete") is not False):
                raise ValueError("native receipt scope differs")
            if package.get("bundled_fixed_parent_archive_member"):
                if archive.read(package["bundled_fixed_parent_archive_member"]) != (
                        ROOT / "A01-case-local-native-and-guide-20261019-v1.zip").read_bytes():
                    raise ValueError("directory preparation parent archive differs")
            result = {"archive": path.name, "indexed_files": len(files),
                      "native_receipt_run_id": terminal["run_id"],
                      "archive_and_all_inner_bytes_verified": True}
            if args.replay:
                with tempfile.TemporaryDirectory(prefix="a01-archive-replay-") as temp:
                    archive.extractall(temp)
                    process = subprocess.run(
                        [sys.executable, "-I", "-X", "utf8", "-B",
                         str(Path(temp) / "replay.py"), temp],
                        cwd=temp, capture_output=True, timeout=60)
                    if process.returncode != 0 or process.stderr:
                        raise ValueError("frozen read-only replay failed: " + path.name + ": " +
                                         repr(process.stdout[-1500:]) + ": " + repr(process.stderr[-1500:]))
                    result["isolated_content_replay"] = json.loads(process.stdout)
            results.append(result)
    print(json.dumps({"schema": "issue18-A01-archive-delivery-verification/v1",
                      "decision": "ACCEPT_ARCHIVE_BYTES_AND_REQUESTED_CONTENT_REPLAYS",
                      "archives": results, "native_calls": 0,
                      "OS_custody_recreated": False, "new_semantic_case_claimed": False,
                      "new_agent_native_trial_verified": False,
                      "whole_K02_or_Issue18_complete": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

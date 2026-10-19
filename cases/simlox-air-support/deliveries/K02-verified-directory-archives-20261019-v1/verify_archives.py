"""Verify four frozen K02 directory archives; optional read-only content replay.

This entry has no model launch interface and never executes DLLs/PowerShell.
It does not reproduce native handle/readonly/queue or GUI protection evidence.
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


def fingerprint(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-sha", required=True)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    raw_manifest = (ROOT / "archive-manifest.json").read_bytes()
    if hashlib.sha256(raw_manifest).hexdigest() != args.manifest_sha:
        raise ValueError("external archive manifest SHA differs")
    manifest = json.loads(raw_manifest)
    if manifest["schema"] != "issue18-K02-verified-directory-archive-delivery/v1":
        raise ValueError("unsupported archive delivery schema")
    for name, pin in manifest["entry_files"].items():
        if name not in {"README.md", "verify_archives.py", ".gitattributes"}:
            raise ValueError("unexpected entry file")
        if fingerprint((ROOT / name).read_bytes()) != pin:
            raise ValueError("entry file differs: " + name)
    expected = {
        "K02-NOTE-and-guide-20261019-v2.zip",
        "K02-numeric-null-and-guide-20261019-v1.zip",
        "K02-active-QTY-null-default-and-guide-20261019-v1.zip",
        "K02-missing-BSID-and-guide-20261019-v1.zip",
    }
    if {p["archive"] for p in manifest["archives"]} != expected:
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
            if index["schema"] == "issue18-K02-directory-native-delivery/v1":
                files = index["files"]
            elif index["schema"] in {
                    "issue18-K02-numeric-null-delivery/v1",
                    "issue18-K02-active-QTY-default-delivery/v1",
                    "issue18-K02-active-missing-BSID-delivery/v1"}:
                files = {p["relative_path"]: {k: p[k] for k in ("bytes", "sha256")}
                         for p in index["files"]}
                if len(files) != len(index["files"]):
                    raise ValueError("duplicate inner indexed path")
            else:
                raise ValueError("unsupported frozen inner index schema")
            if set(names) != set(files) | {"delivery-index.json"}:
                raise ValueError("inner file set differs")
            for name, pin in files.items():
                if fingerprint(archive.read(name)) != pin:
                    raise ValueError("inner file bytes differ: " + name)
            for receipt in package["native_receipts"]:
                raw = archive.read(receipt["member"])
                if fingerprint(raw) != receipt["fingerprint"]:
                    raise ValueError("independent native receipt differs")
                value = json.loads(raw)
                if value.get("decision") != receipt["decision"]:
                    raise ValueError("native receipt decision differs")
            result = {"archive": path.name, "indexed_files": len(index["files"]),
                      "native_receipts": len(package["native_receipts"]),
                      "archive_and_all_inner_bytes_verified": True}
            if args.replay:
                with tempfile.TemporaryDirectory(prefix="k02-archive-replay-") as temp:
                    archive.extractall(temp)
                    replay_args = (["--index-sha", package["delivery_index"]["sha256"]]
                                   if index["schema"] ==
                                   "issue18-K02-directory-native-delivery/v1"
                                   else [temp])
                    process = subprocess.run(
                        [sys.executable, "-I", "-X", "utf8", "-B",
                         str(Path(temp) / "replay.py"), *replay_args],
                        cwd=temp, capture_output=True, timeout=60)
                    if process.returncode != 0 or process.stderr:
                        raise ValueError("frozen read-only replay failed: " +
                                         path.name + ": " +
                                         repr(process.stdout[-1500:]) + ": " +
                                         repr(process.stderr[-1500:]))
                    result["isolated_content_replay"] = json.loads(process.stdout)
            results.append(result)
    print(json.dumps({"schema": "issue18-K02-archive-delivery-verification/v1",
                      "decision": "ACCEPT_ARCHIVE_BYTES_AND_REQUESTED_CONTENT_REPLAYS",
                      "archives": results, "native_calls": 0,
                      "OS_custody_recreated": False,
                      "new_agent_native_trial_verified": False,
                      "whole_K02_or_Issue18_complete": False},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Archive exact non-run v100 source bytes; default mode only verifies custody."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OLD = HERE.parent / "I03-var06-out-ignored-duration-v1.0.0"
OLD_MANIFEST_SHA = "ce196b80f2365519885fb97b77eda0b04737736f239dfac46903df99edcf42a9"
ARCHIVE = HERE / "preserved-v100-source"
MAP = HERE / "v100-source-custody.json"

# Files created after the frozen prelaunch manifest; no directory glob widens this list.
EXTRA = (
    "prelaunch-manifest.json",
    "review/excluded-diagnostic-first-pass.stdout.json",
    "review/excluded-prelaunch-audit-draft-v1.py",
    "review/excluded-pure-preflight-audit-draft-v1.py",
    "review/independent-failed-run-diagnostic.py",
    "review/independent-failed-run-diagnostic.stderr.bin",
    "review/independent-failed-run-diagnostic.stdout.json",
    "review/independent-postrun-failed.stderr.bin",
    "review/independent-postrun-failed.stdout.bin",
    "review/independent-prelaunch-audit.py",
    "review/independent-prelaunch-go-2026-10-08.md",
    "review/independent-prelaunch-go.json",
    "review/independent-pure-preflight-audit.py",
    "review/independent-pure-preflight-go-2026-10-08.md",
    "review/independent-run-no-go-2026-10-08.md",
    "review/preflight-ssh0-20261007T181850319Z.json",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inert(rel: Path) -> Path:
    parts = ["__dot_gitattributes.bytes" if x == ".gitattributes" else
             "__dot_gitignore.bytes" if x == ".gitignore" else x for x in rel.parts]
    return Path(*parts)


def expected() -> list[dict]:
    raw = (OLD / "prelaunch-manifest.json").read_bytes()
    assert sha(raw) == OLD_MANIFEST_SHA
    manifest = json.loads(raw.decode("utf-8"))
    assert manifest["source_count"] == len(manifest["source_files"]) == 445
    records = {}
    for rec in manifest["source_files"]:
        path = Path(rec["path"])
        if not path.is_relative_to(OLD):
            continue
        rel = path.relative_to(OLD)
        assert "runs" not in rel.parts and "transport-evidence" not in rel.parts
        assert path.stat().st_size == rec["bytes"] and sha(path.read_bytes()) == rec["sha256"]
        records[rel.as_posix()] = (rec["bytes"], rec["sha256"])
    assert len(records) == 101
    for name in EXTRA:
        path = OLD / name
        data = path.read_bytes()
        assert name not in records
        records[name] = (len(data), sha(data))
    assert len(records) == 117
    return [dict(original=(OLD / name).relative_to(REPO).as_posix(),
                 owned_copy=(ARCHIVE / inert(Path(name))).relative_to(HERE).as_posix(),
                 bytes=size, sha256=digest, original_if_present_must_match=True)
            for name, (size, digest) in sorted(records.items())]


def check(records: list[dict]) -> None:
    for rec in records:
        owned = HERE / rec["owned_copy"]
        assert owned.is_file(), owned
        data = owned.read_bytes()
        assert len(data) == rec["bytes"] and sha(data) == rec["sha256"], owned
        original = REPO / rec["original"]
        if original.exists():
            assert original.stat().st_size == rec["bytes"] and sha(original.read_bytes()) == rec["sha256"], original


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="construct absent byte copies once")
    args = parser.parse_args()
    if args.write:
        records = expected()
        assert not MAP.exists() and not ARCHIVE.exists(), "refuse overwrite"
        for rec in records:
            original = REPO / rec["original"]
            target = HERE / rec["owned_copy"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
        MAP.write_text(json.dumps({"schema": "i03-var06-v101-v100-source-custody/v1",
                                   "record_count": len(records), "records": records},
                                  indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    saved = json.loads(MAP.read_text(encoding="utf-8"))
    assert saved["schema"] == "i03-var06-v101-v100-source-custody/v1"
    assert saved["record_count"] == len(saved["records"]) == 117
    records = saved["records"]
    assert len({r["original"] for r in records}) == 117
    assert len({r["owned_copy"] for r in records}) == 117
    assert all(r["owned_copy"].startswith("preserved-v100-source/") for r in records)
    manifest = next(r for r in records if r["original"].endswith("/prelaunch-manifest.json"))
    assert manifest["sha256"] == OLD_MANIFEST_SHA
    check(records)
    print(json.dumps({"passed": True, "records": len(records), "write": args.write}, sort_keys=True))


if __name__ == "__main__":
    main()

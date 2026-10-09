#!/usr/bin/env python3
"""Build a byte-bound local manifest for one I05.var05 native attempt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_ID = "i05-var05-item-replacement-v106-ssh-20261009-01"
NATIVE_RUN = r"C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\tmp\i05-var05-item-replacement-v106-20261009-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(key: str, path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"key": key, "path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "attributes": int(path.stat().st_file_attributes)}


def strict(path: Path) -> dict:
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError(f"duplicate JSON key: {key}")
            out[key] = value
        return out
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def main() -> None:
    source_files: list[dict[str, object]] = []
    owned = [
        "README.md", "contract.json", "build.py", "check_source_delta.py", "native-input.json",
        "source-freeze.json", "source-freeze-verification.json", "execution-contract.json",
        "check_roundtrip.py", "test_roundtrip_policy.py", "validate_native_cli.py", "run_native_ssh.ps1",
        "ssh_transport.py", "make_prelaunch_manifest.py", "make_source_freeze.py",
        "review/v104-roundtrip-v106-replay.json", "review/local-gates-receipt.json",
        "review/source-delta-checker-receipt.json",
        "review/independent-source-go-a09-v106-2026-10-09.md",
        "review/independent-source-go-a17-v106-2026-10-09.md",
    ]
    owned.extend(
        str(path.relative_to(HERE)).replace("\\", "/")
        for path in sorted((HERE / "preserved-history").rglob("*"))
        if path.is_file()
    )
    for name in owned:
        source_files.append(pin("owned:" + name.replace("\\", "/"), HERE / name))
    source_files.append(pin("live:catalog", HERE.parent / "catalog-v2.json"))
    parent_package = HERE.parent / "H02-var04-item-damage-replacement-fallback-v1.0.0"
    evidence_index = strict(parent_package / "evidence-index.json")
    signoff = parent_package / "cli-scope-signoff-2026-10-02.md"
    source_files.append(pin("parent:input", parent_package / "fallback-input.json"))
    source_files.append(pin("parent:evidence-index", parent_package / "evidence-index.json"))
    source_files.append(pin("parent:scope-signoff", signoff))
    run = evidence_index["accepted_runs"]["fallback"]
    run_dir = Path(run["local_path"])
    for name, expected in run["raw"].items():
        path = run_dir / name
        entry = pin("parent_raw:" + name, path)
        if entry["bytes"] != expected["bytes"] or entry["sha256"] != expected["sha256"]:
            raise SystemExit(f"accepted parent raw bytes/hash mismatch: {name}")
        if entry["attributes"] != 32:
            raise SystemExit(f"accepted parent raw Windows attributes changed: {name}")
        source_files.append(entry)
    if run["run_id"] != "h02-var04-item-fallback-v100-ssh-20261002-01" or sha(parent_package / "fallback-input.json") != run["input_sha256"]:
        raise SystemExit("accepted parent identity differs")
    if len(source_files) != len({item["key"] for item in source_files}):
        raise SystemExit("duplicate source role")
    manifest = {
        "schema": "i05-var05-prelaunch-manifest/v1",
        "run_id": RUN_ID,
        "native_run_directory": NATIVE_RUN,
        "base_commit": "fd2bbeece3daa1815dd1b9779f3134b18776aed4",
        "contract_sha256": sha(HERE / "contract.json"),
        "execution_contract_sha256": sha(HERE / "execution-contract.json"),
        "input_sha256": sha(HERE / "native-input.json"),
        "source_files": source_files,
        "source_count": len(source_files),
        "parent_raw_count": len(run["raw"]),
        "parent_run_id": run["run_id"],
        "live_catalog_prelaunch_pin": {"path": str(HERE.parent / "catalog-v2.json"),
                                        "bytes": (HERE.parent / "catalog-v2.json").stat().st_size,
                                        "sha256": sha(HERE.parent / "catalog-v2.json")},
        "native_stages": ["import", "export", "check_roundtrip", "calc", "jsonreport", "check_behavior"],
        "native_attempt_limit": 1,
        "native_actions_before_independent_prelaunch_go": 0,
        "publication_state": "not_published",
    }
    target = HERE / "prelaunch-manifest.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status":"PRELAUNCH_MANIFEST_CREATED","path":str(target),"bytes":target.stat().st_size,
                      "sha256":sha(target),"source_count":len(source_files),"parent_raw_count":len(run["raw"]),
                      "run_id":RUN_ID,"native_actions":0},sort_keys=True))


if __name__ == "__main__":
    main()

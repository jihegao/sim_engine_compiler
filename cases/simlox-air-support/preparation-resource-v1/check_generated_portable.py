"""Read-only check of frozen v1 generated files on Windows and POSIX hosts.

The original generator stores POSIX manifest paths. Its check constructs those
paths with ``str(Path(...))``, which uses backslashes on Windows. This checker
does not rewrite the frozen generator, manifest, or native model inputs.
"""
from __future__ import annotations

import json

import generate as frozen


def check() -> dict:
    failed_b02 = frozen.NATIVE / "B02--serial-10m-20m.json"
    frozen.require(
        failed_b02.is_file()
        and frozen.digest(failed_b02.read_bytes()) == frozen.FAILED_B02_SHA256,
        "immutable B02 v1.0.0 failed snapshot changed",
    )
    frozen.require_failed_resource_snapshots()
    for case_id in frozen.CASES:
        frozen.validate_contract_alignment(frozen.read(frozen.active_parameter_path(case_id)))

    checked = []
    for parameters, variant_id in frozen.all_candidates():
        case_id = parameters["case_id"]
        name = frozen.artifact_name(parameters, variant_id)
        native_path = frozen.NATIVE / name
        diff_path = frozen.PARENT_DIFFS / name
        expected_native = frozen.encoded(frozen.build(parameters, variant_id))
        expected_diff = frozen.encoded(frozen.parent_diff(parameters, variant_id))
        frozen.require(native_path.read_bytes() == expected_native, f"stale generated native file: {native_path}")
        frozen.require(diff_path.read_bytes() == expected_diff, f"stale generated parent diff: {diff_path}")
        checked.append({
            "case_id": case_id,
            "variant_id": variant_id,
            "candidate_revision": frozen.candidate_revision(parameters),
            "native_sha256": frozen.digest(expected_native),
            "native_verified": False,
        })

    expected_manifest = frozen.manifest(checked)
    for candidate in expected_manifest["candidates"]:
        candidate["parameter_path"] = candidate["parameter_path"].replace("\\", "/")
    frozen.require(
        (frozen.NATIVE / "manifest.json").read_bytes() == frozen.encoded(expected_manifest),
        "stale generated native manifest",
    )
    frozen.require(
        frozen.digest(frozen.writer.SCHEMA.read_bytes()) == frozen.writer.SCHEMA_SHA256,
        "frozen schema changed",
    )
    return {
        "status": "generated_static_validated_native_unverified",
        "candidate_count": len(checked),
        "platform_manifest_path_check": "posix_normalized",
    }


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, sort_keys=True))

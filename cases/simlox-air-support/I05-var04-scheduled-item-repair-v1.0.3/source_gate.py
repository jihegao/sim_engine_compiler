"""Read-only byte, Git-blob, attribute, and installed-source gate for I05.var04."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from model_common import HERE, REPO, NATIVE_DIR, INPUT_PIN, exact, strict_json, typed_equal, no_reparse_ancestry

SELECTED = HERE / "source-maps/root-selection-record.json"
SELECTED_PIN = {"bytes": 9645, "sha256": "57d53ce82f61d7408c33ab9380e6b5cf4921e93846bb470d7b3fd61b19004b25"}
ATTRIBUTES = HERE / "source-maps/current-parent-raw-attributes.json"
ATTRIBUTES_PIN = {"bytes": 5859, "sha256": "cda6ef9f55c42fe16d4ae4e40c84ff3925936a4769855b7d813a87d7bcc7d19c"}
CATALOG_LOCAL = HERE / "source-maps/catalog-local-504.json.bytes"
CATALOG_GIT = HERE / "source-maps/catalog-git-504.json.bytes"
CATALOG_LOCAL_PIN = {"bytes": 549384, "sha256": "65856647dd310207447c4621511b9f42da43a9f25e625560d1f56d06762c6985"}
CATALOG_GIT_PIN = {"bytes": 544581, "sha256": "0174772f37e670f1c8e99b65be5acca4870fc3e7dc7ffab24b1d3db73c4735d0"}
CATALOG_CURRENT = REPO / "cases/simlox-air-support/publication-index-v1.json"
INSTALLED = (
    (Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"), 18124110, "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"),
    (Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"), 78577, "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0"),
    (Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"), 33196032, "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"),
    (Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"), 106448, "10d845f50a2af64e3500bb2fcb348b5bc98a75d8ddada63e45ba1da6a1fc79d1"),
)
DESIGN = {
    "contract.json": (6921, "8bc2b9e7f579bfcfd75c025a9d7ac74ba385a09f70b744771d7937513d41eaf9"),
    "source-delta.json": (5997, "eb0148601892353a2ebfb1cf43a1a76fc3ac746f2f4ed20d5fb4266d9990bcd8"),
    "event-oracle.json": (6187, "5ad98484b1a926fd8f66d9d9e32e56c07bcaa6a98f3911a7d9ddfad66b064f9b"),
    "report-oracle.json": (6928, "b340d16af58c78f711d6f0e20d5158d77d206464d4d580e379447d462c2f6167"),
    "materialize_oracle.py": (15205, "6ac22c479e301b9fab0b088f429f5d29bfe3dc31d880685c951bebf3c7b65303"),
    "verify_oracle.py": (18576, "8b56ba476ad299e15db47d509c30137003e029e5000a951b41ae97f0d2943a04"),
    "README.md": (3366, "de52fbec0b06956df452666260d2caa3879b14937f71277adfd37d97262d82d0"),
    "pure-input-roster.json": (19947, "fc70a5fdb7fce16408a934148568adcae129c8f11a7b3c585d4487fb8ddcf1ac"),
    "preserved-verify-v101-integer-metadata.py.bytes": (17501, "63266c754ceecc612a0dcf73fcc18bab4cb1d458f935adbee8aaedcc67285c47"),
    "independent-construction-go.md": (4033, "676225ee9b51e8166c55b3ccd2dd28e278eec6467692adcee90ec5f19b2bcac4"),
}
ORACLE = {
    "candidate-input.json": (45095, "f4157f818f9f7c00a18b01074fcde9d52ed81baa8f4d92d8e3c323f2bf2545c2"),
    "log-patterns.json": (87444, "5cf823b0a1719a09e632fca16cbd6f1cc0798751dbe72e8ad29e25fb24cb7de3"),
    "report-predicates.json": (1380881, "84661b8f0675f91226d86623588d8c46011a7b81f05a8276666f2778b711436b"),
    "receipt.json": (2614, "68169667f7dd6b6e415ea2e847c3e525065ef0dc9116ffaf0d5824958b5b8dfa"),
}
ACCEPTED_PROOFS = (
    (REPO / "cases/simlox-air-support/E05-local-repair-reissue-v1.0.0/review/independent-native-review-2026-09-29.json", 1577, "ad7801108647a3cb0790a0d93abf85f45c5613377b0dcfb7e6f58d0c59026936"),
    (REPO / "cases/simlox-air-support/E05-local-repair-reissue-v1.0.0/runs/e05-v100-ssh-20260929-01/invocation.json", 6819, "a5e5b85421c0d25d1779fad20da0eb7acbb98ea03a347591436157930704bbac"),
    (REPO / "cases/simlox-air-support/E05-local-repair-reissue-v1.0.0/runs/e05-v100-ssh-20260929-01/closure.json", 5235, "e75836bcd99ba838d4ef247973794a2bf38fbddd4904d69337d631ba983d01ef"),
)
RECOVERY_BINDING_PIN = {"bytes": 2227, "sha256": "012f9873ec0c62ab55314641213ffa9283b7eb8237df9b0d9d65564bea11d8f3"}
EXPORT_SERIALIZATION_PIN = {"bytes": 1874, "sha256": "bab7315e63c301eccd7e004d9946d2b4db291279f3d65ec65a3c4cd4e3fca7b7"}
V100_FAILURE_PIN = {"bytes": 20760, "sha256": "294086eda9e993d173ab0c00bed4e2e1a45ccff67b3f0884ef8175e566cef0a4"}
V100_FAILURE_ORIGINAL = REPO / "tmp/i05-var04-source-preflight-failure-seal-v100-20261009.json"
V100_FAILURE_COPY = HERE / "source-maps/v100-failure-seal.json"
V100_OLD_CASE = REPO / "cases/simlox-air-support/I05-var04-scheduled-item-repair-v1.0.0"
V100_CAPTURE_METHOD = REPO / "tmp/i05-var04-root-command-capture-v100-20261009.py"
V100_AUDIT_SPEC = REPO / "tmp/i05-var04-manifest-audit-spec-v100-20261009.json"
V100_CAPTURE_PIN = {"bytes": 3610, "sha256": "09d86d3e88787bac53a2c10e89f9a60754bbff23253ecc9522f480cc215ea4a4"}
V100_SPEC_PIN = {"bytes": 640, "sha256": "31f76205366b2fdcdc9dc0b4c815b31f20e50e155bd7f86b79a213b170736a2f"}
V101_FAILURE_PIN = {"bytes": 77133, "sha256": "b9fe71bab3374d6de647cdf02c824d6275e3280cbfb5eff8c2c3ebe87ac10800"}
V101_FAILURE_ORIGINAL = REPO / "tmp/i05-var04-local-nogo-and-capacity-seal-v101-20261009.json"
V101_FAILURE_COPY = HERE / "source-maps/v101-failure-seal.json"
V101_OLD_CASE = REPO / "cases/simlox-air-support/I05-var04-scheduled-item-repair-v1.0.1"
V101_PROOF_LABELS = ("build", "independent-private", "inventory-audit", "inventory-generate",
                     "manifest-audit", "manifest-generate", "selfcheck", "source-gate", "source-promote")
V102_FAILURE_PIN = {"bytes": 119310, "sha256": "2c8effe52fe4e869d98fe3218cced949d81a09e59f8507b3d2de2de44c1fe454"}
V102_FAILURE_ORIGINAL = REPO / "tmp/i05-var04-excluded-native-failure-seal-v102-20261009.json"
V102_FAILURE_COPY = HERE / "source-maps/v102-failure-seal.json"

def _pair(size: int, sha: str) -> dict[str, object]:
    return {"bytes": size, "sha256": sha}

def accepted_powershell_receipt_bytes(raw: bytes) -> dict[str, object]:
    bom = b"\xef\xbb\xbf"
    assert raw.startswith(bom) and not raw[len(bom):].startswith(bom), "accepted receipt BOM cardinality"
    parsed = strict_json(raw[len(bom):])
    assert type(parsed) is dict
    return parsed

def accepted_powershell_receipt_json(path: Path, pin: dict[str, object]) -> dict[str, object]:
    assert path == ACCEPTED_PROOFS[1][0] or path == ACCEPTED_PROOFS[2][0]
    return accepted_powershell_receipt_bytes(exact(path, pin))

def v100_failure_sources() -> list[dict[str, object]]:
    original = exact(V100_FAILURE_ORIGINAL, V100_FAILURE_PIN)
    assert exact(V100_FAILURE_COPY, V100_FAILURE_PIN) == original
    assert V100_FAILURE_ORIGINAL.stat().st_file_attributes == 33
    assert V100_FAILURE_COPY.stat().st_file_attributes == 33
    doc = strict_json(original)
    assert type(doc) is dict and doc["schema"] == "i05-var04-source-preflight-failure/v100"
    assert doc["decision"] == "NO_GO_AS_FROZEN" and type(doc["actual_exit"]) is int and doc["actual_exit"] == 1
    assert doc["manifest_promoted"] is False and doc["ssh_preflight_calls"] == doc["native_calls"] == doc["accepted_checker_calls"] == 0
    assert doc["frozen_source_count"] == 54 and len(doc["frozen_sources"]) == 54
    assert len(doc["auxiliary"]) == 4
    rows = [{"key":"historical:failure-seal", "path":str(V100_FAILURE_ORIGINAL), **V100_FAILURE_PIN}]
    old_root = V100_OLD_CASE.resolve(strict=True)
    seen: set[str] = set()
    for i, item in enumerate(doc["frozen_sources"]):
        path = Path(item["path"])
        assert path.is_absolute() and path.resolve(strict=True).is_relative_to(old_root)
        assert str(path).casefold() not in seen and item["attributes"] == 33
        seen.add(str(path).casefold())
        exact(path, item)
        assert path.stat().st_file_attributes == 33
        rows.append({"key":f"historical:source:{i:02d}", "path":str(path), "bytes":item["bytes"], "sha256":item["sha256"]})
    assert len(seen) == 54
    for i, item in enumerate(doc["auxiliary"]):
        path = Path(item["path"])
        assert path.is_absolute() and path.is_relative_to(REPO / "tmp")
        exact(path, item)
        assert path.stat().st_file_attributes == 33
        rows.append({"key":f"historical:aux:{i:02d}", "path":str(path), "bytes":item["bytes"], "sha256":item["sha256"]})
    proof = doc["failed_proof"]
    receipt_path = Path(proof["path"])
    receipt_pin = _pair(proof["bytes"], proof["sha256"])
    receipt = strict_json(exact(receipt_path, receipt_pin))
    assert receipt_path.stat().st_file_attributes == 33
    assert receipt["schema"] == "i05-var04-root-command-proof/v100"
    assert receipt["native_dispatch"] is False and type(receipt["actual_exit"]) is int and receipt["actual_exit"] == 1
    assert receipt["method_before"] == receipt["method_after"]
    assert receipt["method_before"]["capture"] == V100_CAPTURE_PIN
    assert receipt["method_before"]["spec"] == V100_SPEC_PIN
    assert receipt["method_before"]["method"] == _pair(55854, "adc8f2843e94984c1ee38ccf7619f39048729d963324db241525304f325ed20c")
    assert receipt["argv"][4] == str(V100_OLD_CASE / "review/independent_reader.py")
    assert receipt["argv"][5] == "--manifest-candidate"
    rows.append({"key":"historical:proof:receipt", "path":str(receipt_path), **receipt_pin})
    for name in ("stdout.bin", "stderr.bin"):
        path = receipt_path.parent / name
        pin = receipt["streams"][name]
        assert pin == proof[name.removesuffix(".bin")]
        exact(path, pin)
        assert path.stat().st_file_attributes == 33
        rows.append({"key":"historical:proof:"+name.removesuffix(".bin"), "path":str(path), **pin})
    for name, path, pin in (("capture", V100_CAPTURE_METHOD, V100_CAPTURE_PIN),
                            ("spec", V100_AUDIT_SPEC, V100_SPEC_PIN)):
        exact(path, pin)
        assert path.stat().st_file_attributes == 33
        rows.append({"key":"historical:method:"+name, "path":str(path), **pin})
    assert len(rows) == 64
    return rows

def v101_failure_sources() -> list[dict[str, object]]:
    original = exact(V101_FAILURE_ORIGINAL, V101_FAILURE_PIN)
    assert exact(V101_FAILURE_COPY, V101_FAILURE_PIN) == original
    assert V101_FAILURE_ORIGINAL.stat().st_file_attributes == 33
    assert V101_FAILURE_COPY.stat().st_file_attributes == 33
    doc = strict_json(original)
    assert type(doc) is dict and doc["schema"] == "i05-var04-local-nogo-and-capacity/v101"
    assert doc["decision"] == "NO_GO_AS_FROZEN" and type(doc["actual_exit"]) is int and doc["actual_exit"] == 1
    assert doc["ssh_preflight_calls"] == doc["native_calls"] == doc["accepted_checker_calls"] == 0
    assert doc["frozen_source_count"] == len(doc["frozen_sources"]) == 57
    assert doc["manifest_role_count"] == 160
    assert len(doc["original_command_proofs"]) == len(V101_PROOF_LABELS) == 9
    assert len(doc["auxiliary"]) == 26
    rows = [{"key":"excluded-v101:seal", "path":str(V101_FAILURE_ORIGINAL), **V101_FAILURE_PIN}]
    old_root = V101_OLD_CASE.resolve(strict=True)
    for i, item in enumerate(doc["frozen_sources"]):
        path = Path(item["path"])
        no_reparse_ancestry(path)
        assert path.is_absolute() and path.resolve(strict=True).is_relative_to(old_root)
        assert item["attributes"] == 33 and path.stat().st_file_attributes == 33
        exact(path, item)
        rows.append({"key":f"excluded-v101:source:{i:02d}", "path":str(path),
                     "bytes":item["bytes"], "sha256":item["sha256"]})
    for label, proof in zip(V101_PROOF_LABELS, doc["original_command_proofs"], strict=True):
        assert proof["label"] == label
        receipt_item = proof["receipt"]
        receipt_path = Path(receipt_item["path"])
        no_reparse_ancestry(receipt_path)
        assert receipt_path.is_absolute() and receipt_path.is_relative_to(REPO / "tmp")
        receipt = strict_json(exact(receipt_path, receipt_item))
        assert receipt_path.stat().st_file_attributes == receipt_item["attributes"] == 33
        assert receipt["schema"] == "i05-var04-root-command-proof/v101"
        assert receipt["native_dispatch"] is False and receipt["method_before"] == receipt["method_after"]
        assert type(receipt["actual_exit"]) is int and receipt["actual_exit"] == proof["actual_exit"]
        assert receipt["actual_exit"] == (1 if label == "independent-private" else 0)
        rows.append({"key":f"excluded-v101:proof:{label}:receipt", "path":str(receipt_path),
                     "bytes":receipt_item["bytes"], "sha256":receipt_item["sha256"]})
        for name, stream in zip(("stdout", "stderr"), proof["streams"], strict=True):
            path = Path(stream["path"])
            no_reparse_ancestry(path)
            assert path == receipt_path.parent / (name + ".bin")
            assert stream["attributes"] == path.stat().st_file_attributes == 33
            assert receipt["streams"][name + ".bin"] == _pair(stream["bytes"], stream["sha256"])
            exact(path, stream)
            rows.append({"key":f"excluded-v101:proof:{label}:{name}", "path":str(path),
                         "bytes":stream["bytes"], "sha256":stream["sha256"]})
    for i, item in enumerate(doc["auxiliary"]):
        path = Path(item["path"])
        no_reparse_ancestry(path)
        assert path.is_absolute() and path.is_relative_to(REPO / "tmp")
        assert item["attributes"] == path.stat().st_file_attributes == 33
        exact(path, item)
        rows.append({"key":f"excluded-v101:aux:{i:02d}", "path":str(path),
                     "bytes":item["bytes"], "sha256":item["sha256"]})
    item = doc["method"]
    path = Path(item["path"])
    no_reparse_ancestry(path)
    assert path.is_absolute() and path.is_relative_to(REPO / "tmp")
    assert item["attributes"] == path.stat().st_file_attributes == 33
    exact(path, item)
    rows.append({"key":"excluded-v101:method:seal", "path":str(path),
                 "bytes":item["bytes"], "sha256":item["sha256"]})
    assert len(rows) == 112
    assert len({r["key"].casefold() for r in rows}) == 112
    return rows

def v102_failure_sources() -> list[dict[str, object]]:
    original = exact(V102_FAILURE_ORIGINAL, V102_FAILURE_PIN)
    assert exact(V102_FAILURE_COPY, V102_FAILURE_PIN) == original
    assert V102_FAILURE_ORIGINAL.stat().st_file_attributes == V102_FAILURE_COPY.stat().st_file_attributes == 33
    doc = strict_json(original)
    assert type(doc) is dict and doc["schema"] == "i05-var04-excluded-native-failure/v102"
    assert doc["decision"] == "NO_GO_AS_FROZEN" and doc["semantic_acceptance"] is False
    assert doc["failed_stage"] == "check_import_export" and doc["actual_exit"] == 1
    assert doc["formal_native_dispatches"] == 1 and doc["native_import_export_commands"] == 2
    assert doc["converter_calls"] == 0 and doc["publication_state"] == "excluded"
    assert doc["source_bytes_modes_attributes_stable"] is True
    assert doc["simulation_calls"] == doc["report_calls"] == doc["accepted_checker_calls"] == doc["native_retry_calls"] == 0
    assert doc["frozen_source_count"] == 59 and doc["canonical_file_count"] == 89
    assert doc["historical_file_count"] == 268 and doc["historical_role_count"] == 269
    history = doc["historical_files"]
    assert type(history) is list and len(history) == 268
    assert doc["failure_custody"] in history
    rows = [{"key":"excluded-v102:seal", "path":str(V102_FAILURE_ORIGINAL), **V102_FAILURE_PIN}]
    identities: set[str] = set()
    for i, item in enumerate(history):
        assert type(item) is dict and set(item) == {"path", "bytes", "sha256", "mode", "attributes"}
        path = Path(item["path"])
        no_reparse_ancestry(path)
        assert path.is_absolute() and (path.is_relative_to(REPO / "tmp") or
                                       path.is_relative_to(REPO / "cases/simlox-air-support/I05-var04-scheduled-item-repair-v1.0.2"))
        identity = str(path.resolve(strict=True)).casefold()
        assert identity not in identities
        identities.add(identity)
        exact(path, item)
        stat = path.stat()
        assert stat.st_mode == item["mode"] and stat.st_file_attributes == item["attributes"] == 33
        rows.append({"key":f"excluded-v102:history:{i:03d}", "path":str(path),
                     "bytes":item["bytes"], "sha256":item["sha256"]})
    assert len(rows) == 269
    return rows

def _git_pairs(rows: list[dict], base: str) -> None:
    names = [r["path"] for r in rows]
    assert len(names) == len(set(names)) == 21
    result = subprocess.run(["git", "ls-tree", "-r", "-z", base, "--", *names], cwd=REPO,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    assert result.stderr == b""
    tree: dict[str, str] = {}
    for rec in result.stdout.split(b"\0"):
        if not rec:
            continue
        head, path = rec.split(b"\t", 1)
        mode, kind, oid = head.decode("ascii").split(" ")
        name = path.decode("utf-8")
        assert kind == "blob" and name not in tree
        tree[name] = oid
    assert set(tree) == set(names)
    assert all(tree[r["path"]] == r["git_oid"] for r in rows)
    oids = list(dict.fromkeys(r["git_oid"] for r in rows))
    raw = subprocess.run(["git", "cat-file", "--batch"], cwd=REPO,
                         input=("\n".join(oids) + "\n").encode("ascii"),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    assert raw.stderr == b""
    offset = 0
    blobs: dict[str, bytes] = {}
    for oid in oids:
        end = raw.stdout.index(b"\n", offset)
        found, kind, length = raw.stdout[offset:end].decode("ascii").split(" ")
        assert found == oid and kind == "blob"
        start = end + 1; count = int(length)
        blobs[oid] = raw.stdout[start:start + count]
        assert len(blobs[oid]) == count and raw.stdout[start + count:start + count + 1] == b"\n"
        offset = start + count + 1
    assert offset == len(raw.stdout)
    for row in rows:
        body = blobs[row["git_oid"]]
        assert len(body) == row["bytes"] and hashlib.sha256(body).hexdigest() == row["sha256"]

def verify(require_absent_native: bool = False) -> dict[str, object]:
    selected = strict_json(exact(SELECTED, SELECTED_PIN))
    assert selected["decision"] == "PASS_CANDIDATE_DEPENDENCY_BYTES_ONLY"
    assert selected["merge"] == "7998e59944a8e061db2b48041349602039f4dc10"
    assert selected["catalog_count"] == 504 and selected["native_calls"] == selected["accepted_checker_calls"] == 0
    rows = selected["source_pairs"]
    assert type(rows) is list and len(rows) == 21
    for row in rows:
        rel = Path(row["path"])
        assert not rel.is_absolute() and ".." not in rel.parts
        no_reparse_ancestry(REPO / rel)
        path = (REPO / rel).resolve(strict=True)
        assert path.is_relative_to(REPO.resolve(strict=True))
        exact(path, row)
    _git_pairs(rows, selected["merge"])
    originals = selected["accepted_parent_raw_seals"]
    observation = strict_json(exact(ATTRIBUTES, ATTRIBUTES_PIN))
    observed = observation["rows"]
    assert type(originals) is type(observed) is list and len(originals) == len(observed) == 12
    for index, (original, current) in enumerate(zip(originals, observed, strict=True)):
        assert current["role"] == f"E05:raw:{index:02d}"
        assert all(current[k] == original[k] for k in ("path", "bytes", "sha256"))
        path = Path(original["path"])
        exact(path, original)
        stat = path.stat()
        assert stat.st_mode == current["mode"] and stat.st_file_attributes == current["file_attributes"]
    for path, size, sha in INSTALLED:
        exact(path, _pair(size, sha))
    verdict = strict_json(exact(ACCEPTED_PROOFS[0][0], _pair(*ACCEPTED_PROOFS[0][1:])))
    assert verdict["schema"] == "simlox-e05-independent-native-review/v1"
    assert verdict["run_id"] == "e05-v100-ssh-20260929-01"
    assert verdict["passed"] is True and verdict["differences"] == []
    assert verdict["raw_report_sha256"] == "fcf9a124546e77fb96871b5bf4b5e111774c00616bfed69c19ad7f1b6c08b4bf"
    invocation = accepted_powershell_receipt_json(ACCEPTED_PROOFS[1][0], _pair(*ACCEPTED_PROOFS[1][1:]))
    closure = accepted_powershell_receipt_json(ACCEPTED_PROOFS[2][0], _pair(*ACCEPTED_PROOFS[2][1:]))
    assert invocation["run_id"] == closure["run_id"] == verdict["run_id"]
    assert invocation["input_sha256"] == "ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca"
    assert closure["error"] is None
    assert closure["invocation_sha256"] == ACCEPTED_PROOFS[1][2]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    for path, _, _ in ACCEPTED_PROOFS:
        stat = path.stat()
        assert stat.st_mode == 33206 and stat.st_file_attributes == 32
    exact(HERE / "native-input.json", INPUT_PIN)
    for name, (size, sha) in DESIGN.items():
        exact(HERE / "preserved-design" / name, _pair(size, sha))
    recovery = strict_json(exact(HERE / "preserved-design/recovery-binding-v103.json", RECOVERY_BINDING_PIN))
    assert recovery["schema"] == "i05-var04-recovery-binding/v103"
    assert recovery["run_id"] == "i05-var04-item-repair-v103-ssh-20261009-01"
    assert recovery["native_run_directory"] == str(NATIVE_DIR)
    assert recovery["unchanged_business_contract_sha256"] == DESIGN["contract.json"][1]
    assert recovery["unchanged_candidate_input"] == INPUT_PIN
    assert recovery["unchanged_log_patterns"] == _pair(*ORACLE["log-patterns.json"])
    assert recovery["unchanged_report_predicates"] == _pair(*ORACLE["report-predicates.json"])
    assert recovery["excluded_v100_failure_seal"] == V100_FAILURE_PIN
    assert recovery["excluded_v101_failure_seal"] == V101_FAILURE_PIN
    assert recovery["excluded_v100_role_count"] == 64 and recovery["excluded_v101_role_count"] == 112
    assert recovery["excluded_v102_failure_seal"] == V102_FAILURE_PIN
    assert recovery["excluded_v102_role_count"] == 269 and recovery["excluded_v102_historical_file_count"] == 268
    assert recovery["authored_insertion_index"] == 12 and recovery["export_insertion_index"] == 17
    assert recovery["export_serialization"] == {"path":"preserved-design/export-serialization-v103.json", **EXPORT_SERIALIZATION_PIN}
    assert recovery["parent_control_duration_lines"] == [66,137,209]
    assert recovery["synthetic_child_restock_substitutions"] == 15
    assert recovery["synthetic_child_duration_substitutions"] == 3
    assert recovery["source_construction_only"] is True and recovery["native_calls_at_design"] == 0
    scope = recovery["construction_scope_note"]
    assert scope == {"path":"tmp/i05-var04-independent-v102-failure-scope-go-v103-construction-only-20261009.md",
                     "bytes":4231,"sha256":"5b8f8a722a7ebff9323d024e3d1d402a09993d40a3de35a2ed023ad514acc45c"}
    exact(REPO / scope["path"], scope)
    export = strict_json(exact(HERE / "preserved-design/export-serialization-v103.json", EXPORT_SERIALIZATION_PIN))
    assert export["schema"] == "i05-var04-export-serialization/v103"
    assert export["authored_insertion_index"] == 12 and export["export_insertion_index"] == 17
    assert export["observation_is_not_behavior_acceptance"] is True
    assert export["superseded_source_delta_field"]["path"] == "preserved-design/source-delta.json"
    assert export["superseded_source_delta_field"]["sha256"] == DESIGN["source-delta.json"][1]
    assert export["superseded_source_delta_field"]["field"] == "export_gate"
    historical = v100_failure_sources()
    excluded_v101 = v101_failure_sources()
    excluded_v102 = v102_failure_sources()
    for name, (size, sha) in ORACLE.items():
        exact(HERE / "preserved-oracle" / name, _pair(size, sha))
    local = strict_json(exact(CATALOG_LOCAL, CATALOG_LOCAL_PIN))
    git = strict_json(exact(CATALOG_GIT, CATALOG_GIT_PIN))
    assert typed_equal(local, git) and len(local["entries"]) == 504
    no_reparse_ancestry(CATALOG_CURRENT)
    current = strict_json(CATALOG_CURRENT.read_bytes())
    assert type(current) is dict and set(current) == set(local) and type(current["entries"]) is list
    assert len(current["entries"]) >= 504
    for key in local:
        if key not in ("entries", "as_of"):
            assert typed_equal(local[key], current[key]), key
    assert all(typed_equal(a, b) for a, b in zip(local["entries"], current["entries"][:504], strict=True))
    assert len({entry["publication_id"] for entry in current["entries"]}) == len(current["entries"])
    if require_absent_native:
        assert not NATIVE_DIR.exists(), "native run path already exists"
    return {"schema": "i05-var04-source-gate/v103", "passed": True,
            "accepted_disk_git_pairs": 21, "accepted_parent_raw_originals": 12,
            "accepted_parent_verdict_invocation_closure": 3,
            "excluded_v100_history_roles": len(historical),
            "excluded_v101_history_roles": len(excluded_v101),
            "excluded_v102_history_roles": len(excluded_v102),
            "raw_attribute_basis": "current_observation_only", "catalog_prefix_entries": 504,
            "native_calls": 0, "accepted_checker_calls": 0}

if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))

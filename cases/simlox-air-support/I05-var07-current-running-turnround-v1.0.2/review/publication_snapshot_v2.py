"""Captured publication bytes shared by parent and subordinate readonly replay."""
import hashlib
import json

from publication_target_v1 import derive_snapshot_reader, require


def parse_artifact(data):
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_BINDING_KEY", key)
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


def captured_binding(data, expected_sha256):
    require(hashlib.sha256(data).hexdigest() == expected_sha256,
            "CAPTURED_PUBLICATION_BINDING_MISMATCH", "subordinate requires captured immutable publication bytes")
    return parse_artifact(data)


def derive_captured_reader(original_text, binding_sha256):
    snapshot = derive_snapshot_reader(original_text)
    old = "publication_binding=json.loads((Path(__file__).parent/'publication-binding-v1.json').read_bytes())"
    new = ("import sys\nfrom publication_snapshot_v2 import captured_binding\n"
           "publication_binding=captured_binding(sys.stdin.buffer.read(), " + repr(binding_sha256) + ")")
    require(snapshot.count(old) == 1, "CAPTURED_DERIVATION_SOURCE_CHANGED", "expected one binding load site")
    return snapshot.replace(old, new)

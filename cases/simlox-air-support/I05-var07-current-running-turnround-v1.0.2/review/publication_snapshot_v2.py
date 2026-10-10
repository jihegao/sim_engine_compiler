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


BOOTSTRAP = '''import sys, json, hashlib, types, io
def unique(items):
 result={}
 for key,value in items:
  assert key not in result, 'DUPLICATE_EXECUTION_KEY'
  result[key]=value
 return result
payload=json.loads(sys.stdin.buffer.read(),object_pairs_hook=unique)
assert set(payload)=={'sources','binding'}, 'INVALID_EXECUTION_BUNDLE'
assert set(payload['sources'])==set(expected), 'MISSING_CAPTURED_CODE'
sources={name:bytes.fromhex(value) for name,value in payload['sources'].items()}
for name,data in sources.items():
 assert hashlib.sha256(data).hexdigest()==expected[name], 'CAPTURED_CODE_MISMATCH:'+name
binding=bytes.fromhex(payload['binding'])
assert hashlib.sha256(binding).hexdigest()==binding_sha, 'CAPTURED_PUBLICATION_BINDING_MISMATCH'
for name in ('publication_target_v1','publication_snapshot_v2'):
 module=types.ModuleType(name);module.__file__=paths[name];sys.modules[name]=module
 exec(compile(sources[name],paths[name],'exec'),module.__dict__)
sys.stdin=io.TextIOWrapper(io.BytesIO(binding),encoding='utf8')
exec(compile(sources['reader'],paths['reader'],'exec'),{'__name__':'__main__','__file__':paths['reader']})
'''


def captured_execution(binding_bytes, sources):
    """Trusted expected hashes stay in the command, separate from stdin payload."""
    require(set(sources) == {'publication_target_v1', 'publication_snapshot_v2', 'reader'},
            'CAPTURED_EXECUTION_SOURCES', 'exact two modules and reader required')
    expected = {name: hashlib.sha256(data).hexdigest() for name, (path, data) in sources.items()}
    paths = {name: str(path) for name, (path, data) in sources.items()}
    command = ('expected=' + repr(expected) + '\npaths=' + repr(paths)
               + '\nbinding_sha=' + repr(hashlib.sha256(binding_bytes).hexdigest()) + '\n' + BOOTSTRAP)
    payload = json.dumps({'sources': {name: data.hex() for name, (path, data) in sources.items()},
                          'binding': binding_bytes.hex()}).encode('ascii')
    return command, payload

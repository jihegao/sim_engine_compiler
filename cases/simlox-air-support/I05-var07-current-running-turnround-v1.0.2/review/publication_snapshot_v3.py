"""Captured publication bytes shared by parent and subordinate readonly replay."""
import hashlib
import json
import os
from pathlib import Path

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



_captured_paths = {}
def canonical_path(path):
    return os.path.normcase(os.path.abspath(os.fspath(path)))

def configure_captured_data(data, data_paths, code, code_paths):
    require(not _captured_paths, 'CAPTURED_DATA_ALREADY_CONFIGURED', 'one immutable child snapshot')
    require(set(data) == set(data_paths) == {'input','manifest'}, 'MISSING_CAPTURED_DATA', 'exact two anchors')
    require(set(code) == set(code_paths) == {'publication_target_v1','publication_snapshot_v3','reader'}, 'MISSING_CAPTURED_CODE', 'exact code paths')
    pending = {}
    for values, paths in ((data, data_paths), (code, code_paths)):
        for name, value in values.items():
            key = canonical_path(paths[name])
            require(key not in pending, 'DUPLICATE_CAPTURED_PATH', key)
            pending[key] = value
    _captured_paths.update(pending)

def captured_read_bytes(path):
    key = canonical_path(path)
    return _captured_paths[key] if key in _captured_paths else Path(path).read_bytes()

def captured_size(path):
    key = canonical_path(path)
    return len(_captured_paths[key]) if key in _captured_paths else Path(path).stat().st_size

def derive_captured_reader(original_text, binding_sha256):
    snapshot = derive_snapshot_reader(original_text)
    old = "publication_binding=json.loads((Path(__file__).parent/'publication-binding-v1.json').read_bytes())"
    new = ("import sys\nfrom publication_snapshot_v3 import captured_binding\n"
           "publication_binding=captured_binding(sys.stdin.buffer.read(), " + repr(binding_sha256) + ")")
    require(snapshot.count(old) == 1, "CAPTURED_DERIVATION_SOURCE_CHANGED", "expected one binding load site")
    snapshot = snapshot.replace(old, new)
    replacements = [
        ("def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()", "from publication_snapshot_v3 import captured_read_bytes,captured_size\ndef sha(p):return hashlib.sha256(captured_read_bytes(p)).hexdigest()"),
        ("s=Path(p).read_text(encoding='utf-8-sig')", "s=captured_read_bytes(p).decode('utf-8-sig')"),
        ("(C/'native-input.json').read_bytes()", "captured_read_bytes(C/'native-input.json')"),
        ("p.stat().st_size==e['bytes']", "captured_size(p)==e['bytes']"),
        ("print(json.dumps(out,indent=2))", "out['captured_source_sha256']={name:sha(W/publication_binding[name]['path']) for name in ('input','manifest')}\nprint(json.dumps(out,indent=2))")]
    for before, after in replacements:
        require(snapshot.count(before) == 1, 'CAPTURED_SOURCE_DERIVATION_CHANGED', before)
        snapshot = snapshot.replace(before, after)
    return snapshot


BOOTSTRAP = '''import sys, json, hashlib, types, io
def unique(items):
 result={}
 for key,value in items:
  assert key not in result, 'DUPLICATE_EXECUTION_KEY'
  result[key]=value
 return result
payload=json.loads(sys.stdin.buffer.read(),object_pairs_hook=unique)
assert set(payload)=={'sources','binding','data'}, 'INVALID_EXECUTION_BUNDLE'
assert set(payload['sources'])==set(expected), 'MISSING_CAPTURED_CODE'
sources={name:bytes.fromhex(value) for name,value in payload['sources'].items()}
for name,data in sources.items():
 assert hashlib.sha256(data).hexdigest()==expected[name], 'CAPTURED_CODE_MISMATCH:'+name
assert set(payload['data'])==set(data_expected)=={'input','manifest'}, 'MISSING_CAPTURED_DATA'
data={name:bytes.fromhex(value) for name,value in payload['data'].items()}
for name,value in data.items():
 assert hashlib.sha256(value).hexdigest()==data_expected[name], 'CAPTURED_DATA_MISMATCH:'+name
binding=bytes.fromhex(payload['binding'])
assert hashlib.sha256(binding).hexdigest()==binding_sha, 'CAPTURED_PUBLICATION_BINDING_MISMATCH'
for name in ('publication_target_v1','publication_snapshot_v3'):
 module=types.ModuleType(name);module.__file__=paths[name];sys.modules[name]=module
 exec(compile(sources[name],paths[name],'exec'),module.__dict__)
sys.modules['publication_snapshot_v3'].configure_captured_data(data,data_paths,sources,paths)
sys.stdin=io.TextIOWrapper(io.BytesIO(binding),encoding='utf8')
exec(compile(sources['reader'],paths['reader'],'exec'),{'__name__':'__main__','__file__':paths['reader']})
'''


def captured_execution(binding_bytes, sources, data):
    """Trusted expected hashes stay in the command, separate from stdin payload."""
    require(set(sources) == {'publication_target_v1', 'publication_snapshot_v3', 'reader'},
            'CAPTURED_EXECUTION_SOURCES', 'exact two modules and reader required')
    require(set(data) == {'input','manifest'}, 'CAPTURED_EXECUTION_DATA', 'exact two anchors required')
    expected = {name: hashlib.sha256(data).hexdigest() for name, (path, data) in sources.items()}
    data_expected = {name: hashlib.sha256(value).hexdigest() for name, (path, value) in data.items()}
    data_paths = {name: str(path) for name, (path, value) in data.items()}
    all_paths = [canonical_path(path) for path in list(data_paths.values()) + [str(path) for path, value in sources.values()]]
    require(len(set(all_paths)) == len(all_paths), 'DUPLICATE_CAPTURED_PATH', 'distinct data and code paths')
    paths = {name: str(path) for name, (path, data) in sources.items()}
    command = ('expected=' + repr(expected) + '\npaths=' + repr(paths)
               + '\nbinding_sha=' + repr(hashlib.sha256(binding_bytes).hexdigest())
               + '\ndata_expected=' + repr(data_expected) + '\ndata_paths=' + repr(data_paths) + '\n' + BOOTSTRAP)
    payload = json.dumps({'sources': {name: data.hex() for name, (path, data) in sources.items()},
                          'binding': binding_bytes.hex(), 'data': {name:value.hex() for name,(path,value) in data.items()}}).encode('ascii')
    return command, payload

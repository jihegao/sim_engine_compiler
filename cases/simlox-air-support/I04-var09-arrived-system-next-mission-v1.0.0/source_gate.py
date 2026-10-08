"""Independent-from-parent read-only byte custody gate for I04.var09 classification."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
import make_custody

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PARENT = REPO / 'cases/simlox-air-support/I04-var03-idle-system-between-v1.0.1'
VAR05 = REPO / 'cases/simlox-air-support/I04-var05-zero-transport-between-v1.0.2'
CATALOG = REPO / 'cases/simlox-air-support/publication-index-v1.json'
INDEX_PIN = (176439, '09e0fe50532797f97d13b3a17fdd886adfc9a18c925038b15058b3850b2273ff')
MANIFEST_PIN = (161922, 'd05541613248279a5620349ade72bcaf80b12f3be042b470694f45b6efa690f3')
SELECTION_PIN = (277670, 'e1476616e4694df1742d095f9976eb57a512953edf6222c9a6cdc74b74ea8cde')
ROOT_SELECTION_PIN = (9507, 'f198bdf3ef4e4778ac2dca5d87d185afb74b94f214aeebf5da4cef800a156192')
CURRENT_LOCAL = (536982, '0674cef00db66d7d907fa4c55cc1249e237c4c60b340740ab81f832405d2de5c')
CURRENT_GIT = (532311, '47a2615c633895de560db739e15e6fecc665786180cf8ef29f30443a2e666204')
CURRENT_GIT_OID = '8311413ebe7367ecf96fa69f0510cbecf3f07f6a'
OLD496_LOCAL = (532423, 'a247e221e524b319f45f62b32a1668366e3e2caf5f066ca79b58ca0838fe59d6')
OLD496_GIT = (527796, 'cecd78d6913a8e75638382f8b2a82c83c6f626394657f200150287df02e0851c')
OLD497_LOCAL = (534641, 'e4c3966bb85829ffafadf9331ef6a719431fbab58c8203bc017d188884cfc696')
OLD497_GIT = (529992, 'ab9bd439b967d15965a54482b783070408d92d9a17a4963b35447b9a3c631dd3')
EMPTY_SHA = hashlib.sha256(b'').hexdigest()


def pin(data: bytes) -> dict:
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def exact(data: bytes, expected) -> None:
    if isinstance(expected, dict):
        assert pin(data) == {k: expected[k] for k in ('bytes', 'sha256')}
    else:
        assert pin(data) == {'bytes': expected[0], 'sha256': expected[1]}


def pairs_hook(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('duplicate JSON key: ' + key)
        out[key] = value
    return out


def finite(value):
    if isinstance(value, float):
        assert math.isfinite(value)
    elif isinstance(value, list):
        for item in value: finite(item)
    elif isinstance(value, dict):
        for item in value.values(): finite(item)


def decode(data: bytes):
    result = json.loads(data.decode('utf-8-sig'), object_pairs_hook=pairs_hook,
                        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    finite(result)
    return result


def read(path: Path, expected=None):
    data = path.read_bytes()
    if expected is not None: exact(data, expected)
    return decode(data)


def typed_equal(a, b) -> bool:
    if type(a) is not type(b): return False
    if isinstance(a, dict):
        return set(a) == set(b) and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def abs_path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else REPO / p


def git_tree() -> dict[str, tuple[str, str, str]]:
    proc = subprocess.run(['git', '-c', 'core.longpaths=true', 'ls-tree', '-r', '-z', 'HEAD', '--', 'cases/simlox-air-support'],
                          cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    assert not proc.stderr
    out = {}
    for record in proc.stdout.split(b'\x00'):
        if not record: continue
        meta, path = record.split(b'\t', 1)
        mode, kind, oid = meta.decode('ascii').split(' ')
        key = path.decode('utf-8')
        assert key not in out
        out[key] = (mode, kind, oid)
    return out


def git_blobs(rows: list[dict], tree: dict) -> int:
    ids = []
    for row in rows:
        path = row['path'].replace('\\', '/')
        assert path in tree, path
        mode, kind, oid = tree[path]
        assert kind == 'blob' and oid == row['oid'] and mode in ('100644', '100755', '120000')
        ids.append(oid)
    proc = subprocess.run(['git', '-c', 'core.longpaths=true', 'cat-file', '--batch'], cwd=REPO,
                          input=(''.join(x + '\n' for x in ids)).encode('ascii'),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    assert not proc.stderr
    data = proc.stdout
    pos = 0
    for row, oid in zip(rows, ids):
        end = data.index(b'\n', pos)
        header = data[pos:end].decode('ascii').split(' ')
        assert len(header) == 3 and header[0] == oid and header[1] == 'blob'
        size = int(header[2])
        start = end + 1
        payload = data[start:start + size]
        assert len(payload) == size and data[start + size:start + size + 1] == b'\n'
        exact(payload, row['git'])
        pos = start + size + 1
    assert pos == len(data)
    return len(ids)


def verify(mode: str = 'sealed') -> dict:
    assert mode in ('live', 'sealed')
    contract = read(HERE / 'prospective-contract.json', (13997, 'ec2dbe37601d0045185109fe7856ea4656a0b2e01dfe35ac25809de17aa60307'))
    assert contract['schema'] == 'i04-var09-zero-new-native-classification-contract/v1'
    assert contract['native_execution']['new_native_runs'] == 0
    parent_index = read(PARENT / 'evidence-index.json', INDEX_PIN)
    assert parent_index['source_count'] == len(parent_index['source_files']) == 401
    seen = set()
    for row in parent_index['source_files']:
        assert set(row) == {'path', 'bytes', 'sha256'}
        key = row['path'].casefold()
        assert key not in seen
        seen.add(key)
        exact((PARENT / row['path']).read_bytes(), row)
    raw_map = read(HERE / 'raw-custody-map.json')
    pref_map = read(HERE / 'preflight-custody-map.json')
    for data, field, schema, count in (
        (raw_map, 'raw_files', 'i04-var09-parent-raw-custody/v1', 153),
        (pref_map, 'preflight_original_files', 'i04-var09-parent-preflight-custody/v1', 15),
    ):
        assert data['schema'] == schema and data['source_parent_index_sha256'] == INDEX_PIN[1]
        assert len(data['records']) == len(parent_index[field]) == count
        assert data['records'] == parent_index[field]
        paths = set()
        for row in data['records']:
            key = row['path'].casefold()
            assert key not in paths and row['original_mandatory'] is True and row['owned_copy'] is None
            paths.add(key)
            exact(abs_path(row['path']).read_bytes(), row)
    assert not {r['path'].casefold() for r in raw_map['records']} & {r['path'].casefold() for r in pref_map['records']}
    manifest = read(PARENT / 'prelaunch-manifest.json', MANIFEST_PIN)
    assert manifest['source_count'] == len(manifest['source_files']) == 456
    assert manifest['local_only_context_originals'] == 2
    keys, physical = set(), {}
    for row in manifest['source_files']:
        assert set(row) == {'key', 'path', 'bytes', 'sha256'}
        key = row['key'].casefold()
        assert key not in keys
        keys.add(key)
        path = abs_path(row['path'])
        resolved = str(path.resolve(strict=True)).casefold()
        observed = {'bytes': row['bytes'], 'sha256': row['sha256']}
        if resolved in physical: assert physical[resolved] == observed
        physical[resolved] = observed
        exact(path.read_bytes(), row)
    assert sum(row['key'].startswith('local_only_context_original:') for row in manifest['source_files']) == 2
    assert manifest['live_catalog_prelaunch_pin']['bytes'] == OLD496_LOCAL[0]
    assert manifest['live_catalog_prelaunch_pin']['sha256'] == OLD496_LOCAL[1]
    selected = read(VAR05 / 'preserved-context/selection.json.bytes', SELECTION_PIN)
    pairs = read(HERE / 'parent-source-pairs.json')
    assert pairs['schema'] == 'i04-var09-parent-disk-git-pairs/v1' and pairs['source_parent_sha256'] == SELECTION_PIN[1]
    expected = [{k: row[k] for k in ('path', 'bytes', 'sha256', 'git', 'oid')}
                for row in selected['parent_sources_and_catalog'][:-1]]
    assert len(pairs['records']) == len(expected) == 403 and pairs['records'] == expected
    parent_prefix = PARENT.relative_to(REPO).as_posix() + '/'
    indexed_paths = {parent_prefix + row['path'] for row in parent_index['source_files']}
    required_pair_paths = indexed_paths | {parent_prefix + 'evidence-index.json',
                                           parent_prefix + 'review/independent-content-go-2026-10-08.md'}
    assert len(indexed_paths) == 401 and len(required_pair_paths) == 403
    assert {row['path'].replace('\\', '/') for row in pairs['records']} == required_pair_paths
    tree = git_tree()
    paths = set()
    for row in pairs['records']:
        key = row['path'].casefold()
        assert key not in paths
        paths.add(key)
        exact(abs_path(row['path']).read_bytes(), row)
    git_blobs(pairs['records'], tree)
    accepted = parent_index['accepted_source_pairs']
    assert len(accepted) == 76
    for row in accepted:
        exact(abs_path(row['path']).read_bytes(), row['disk'])
    git_blobs(accepted, tree)
    context = read(HERE / 'context-custody.json')
    assert set(context) == {'schema', 'records', 'originals_optional_after_publication_when_owned_copy_exact', 'private_full_app_context_originals_are_not_copied'}
    assert context['schema'] == 'i04-var09-safe-context-custody/v1'
    assert context['originals_optional_after_publication_when_owned_copy_exact'] is True
    assert context['private_full_app_context_originals_are_not_copied'] is True
    expected_context = []
    for row, (relative, owned) in zip(context['records'], make_custody.CONTEXT, strict=True):
        size, sha = make_custody.PINS[relative]
        original = Path(row['original_path'])
        assert original.is_absolute()
        assert original.as_posix().casefold().endswith('/' + relative.casefold())
        expected_context.append({'original_path':row['original_path'], 'owned_copy':owned,
                                 'bytes':size, 'sha256':sha,
                                 'original_if_present_must_match':True})
    assert len(expected_context) == 8 and context['records'] == expected_context
    for row in context['records']:
        data = (HERE / row['owned_copy']).read_bytes()
        exact(data, row)
        original = Path(row['original_path'])
        if original.exists():
            assert original.read_bytes() == data
    root = read(HERE / 'preserved-context/root-selection.json.bytes', ROOT_SELECTION_PIN)
    assert root['decision'] == 'ELIGIBLE_FOR_PROSPECTIVE_CONTRACT_ONLY' and root['parent_sources_verified'] == 401
    assert root['parent_current_disk_pairs'] == 403 and root['parent_mandatory_raw'] == 168
    local496 = (PARENT / 'preserved-context/publication-index-local-496.json.bytes').read_bytes()
    git496 = (PARENT / 'preserved-context/publication-index-git-496.json.bytes').read_bytes()
    local497 = (VAR05 / 'preserved-context/catalog-local-497.json.bytes').read_bytes()
    git497 = (VAR05 / 'preserved-context/catalog-git-497.json.bytes').read_bytes()
    local498 = (HERE / 'preserved-context/owned-catalog-local-498.json.bytes').read_bytes()
    git498 = (HERE / 'preserved-context/owned-catalog-git-498.json.bytes').read_bytes()
    for data, expected in ((local496, OLD496_LOCAL), (git496, OLD496_GIT),
                           (local497, OLD497_LOCAL), (git497, OLD497_GIT),
                           (local498, CURRENT_LOCAL), (git498, CURRENT_GIT)):
        exact(data, expected)
    archived = [decode(x) for x in (local496, git496, local497, git497, local498, git498)]
    for n in (0, 2, 4):
        assert typed_equal(archived[n], archived[n+1])
    assert len(archived[0]['entries']) == 496 and len(archived[2]['entries']) == 497 and len(archived[4]['entries']) == 498
    live_bytes = CATALOG.read_bytes()
    live = decode(live_bytes)
    if mode == 'live':
        exact(live_bytes, CURRENT_LOCAL)
        proc = subprocess.run(['git', '-c', 'core.longpaths=true', 'rev-parse', 'HEAD:cases/simlox-air-support/publication-index-v1.json'],
                              cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        assert proc.stdout.decode('ascii').strip() == CURRENT_GIT_OID
    assert type(live['entries']) is list and len(live['entries']) >= 498
    baseline = archived[4]
    assert set(live) == set(baseline)
    assert all(typed_equal(live[key], baseline[key]) for key in live if key != 'entries')
    assert typed_equal(live['entries'][:498], baseline['entries'])
    assert typed_equal(archived[0]['entries'], archived[2]['entries'][:496])
    assert typed_equal(archived[2]['entries'], archived[4]['entries'][:497])
    ids = [row['publication_id'] for row in live['entries']]
    assert len(ids) == len(set(ids))
    return {'schema': 'i04-var09-source-gate/v1', 'mode': mode, 'parent_indexed_sources': 401,
            'parent_current_disk_git_pairs': 403, 'accepted_dependency_pairs': 76,
            'parent_manifest_roles': 456, 'mandatory_raw_originals': 153,
            'mandatory_preflight_originals': 15, 'private_local_only_originals': 2,
            'catalog_required_prefix': 498, 'native_calls': 0,
            'accepted_checker_reruns': 0}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('live', 'sealed'), default='sealed')
    args = ap.parse_args()
    print(json.dumps(verify(args.mode), sort_keys=True, separators=(',', ':')))

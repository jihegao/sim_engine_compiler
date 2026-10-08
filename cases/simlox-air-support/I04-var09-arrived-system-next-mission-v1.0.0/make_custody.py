"""Create once, then verify exact safe custody for the zero-native classification."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PARENT = REPO / 'cases/simlox-air-support/I04-var03-idle-system-between-v1.0.1'
SELECTED_PARENT = REPO / 'cases/simlox-air-support/I04-var05-zero-transport-between-v1.0.2/preserved-context/selection.json.bytes'
CONTRACT_DIR = REPO / 'tmp/i04-var09-prospective-v100-20261008-01'
CONTEXT = [
    ('tmp/i04-var09-prospective-v100-20261008-01/contract.json', 'prospective-contract.json'),
    ('tmp/i04-var09-prospective-v100-20261008-01/contract.md', 'prospective-contract.md'),
    ('tmp/i04-var09-root-selection-20261008/20261008T111751488105Z-e0b84a11/receipt.json', 'preserved-context/root-selection.json.bytes'),
    ('tmp/i04-var07-author-contract-readiness-no-go-20261008.md', 'preserved-context/var07-author-no-go.md.bytes'),
    ('tmp/i04-var07-independent-contract-readiness-no-go-20261008.md', 'preserved-context/var07-independent-no-go.md.bytes'),
    ('tmp/i04-var09-independent-reuse-feasibility-addendum-20261008.md', 'preserved-context/var09-independent-feasibility.md.bytes'),
    ('tmp/i04-var09-independent-contract-go-20261008.md', 'preserved-context/var09-independent-contract-go.md.bytes'),
    ('cases/simlox-air-support/I04-var03-idle-system-between-v1.0.1/review/independent-postrun-go-2026-10-08.md', 'preserved-context/parent-independent-postrun-go.md.bytes'),
]
PINS = {
    'tmp/i04-var09-prospective-v100-20261008-01/contract.json': (13997, 'ec2dbe37601d0045185109fe7856ea4656a0b2e01dfe35ac25809de17aa60307'),
    'tmp/i04-var09-prospective-v100-20261008-01/contract.md': (5689, '9d8a5047c8e8f090b090b0307553cead51a665813525a6d4f2ca2c053ba085de'),
    'tmp/i04-var09-root-selection-20261008/20261008T111751488105Z-e0b84a11/receipt.json': (9507, 'f198bdf3ef4e4778ac2dca5d87d185afb74b94f214aeebf5da4cef800a156192'),
    'tmp/i04-var07-author-contract-readiness-no-go-20261008.md': (2678, '6c593ef2661cdefa0d183ac91745838568d65dc3a97b7dda22115cb7a7fa0001'),
    'tmp/i04-var07-independent-contract-readiness-no-go-20261008.md': (4667, '62f3ab0e32deabce5a2f34da72adac5b9d0d7f44d4ea7106b99c15cc8ea9afc5'),
    'tmp/i04-var09-independent-reuse-feasibility-addendum-20261008.md': (1377, '51c80c60e26cbe16460a74ce062368f6f3554fc3837573d81101023d3ec9189c'),
    'tmp/i04-var09-independent-contract-go-20261008.md': (4074, '810bc2ea34d40df352368572ea6e51448ac3ddef59766bd2b55decdde0dd62ff'),
    'cases/simlox-air-support/I04-var03-idle-system-between-v1.0.1/review/independent-postrun-go-2026-10-08.md': (4369, 'd5b7ea964e65ddb57d248562dab82f53bce565f6d0ac7a161c4eccc5b8ebf7c7'),
}
PARENT_INDEX_PIN = (176439, '09e0fe50532797f97d13b3a17fdd886adfc9a18c925038b15058b3850b2273ff')
SELECTED_PARENT_PIN = (277670, 'e1476616e4694df1742d095f9976eb57a512953edf6222c9a6cdc74b74ea8cde')
CATALOG_LOCAL_PIN = (536982, '0674cef00db66d7d907fa4c55cc1249e237c4c60b340740ab81f832405d2de5c')
CATALOG_GIT_OID = '8311413ebe7367ecf96fa69f0510cbecf3f07f6a'
CATALOG_GIT_PIN = (532311, '47a2615c633895de560db739e15e6fecc665786180cf8ef29f30443a2e666204')


def pin(data: bytes) -> dict:
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def expect(data: bytes, expected: tuple[int, str]) -> None:
    assert pin(data) == {'bytes': expected[0], 'sha256': expected[1]}


def pairs_hook(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError('duplicate JSON key: ' + k)
        out[k] = v
    return out


def finite(value):
    if isinstance(value, float):
        assert math.isfinite(value)
    elif isinstance(value, list):
        for x in value: finite(x)
    elif isinstance(value, dict):
        for x in value.values(): finite(x)


def parse(data: bytes):
    obj = json.loads(data.decode('utf-8-sig'), object_pairs_hook=pairs_hook,
                     parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    finite(obj)
    return obj


def encode(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def git_blob(oid: str) -> bytes:
    proc = subprocess.run(['git', '-c', 'core.longpaths=true', 'cat-file', 'blob', oid],
                          cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    assert not proc.stderr
    return proc.stdout


def expected_files(write: bool) -> dict[str, bytes]:
    result = {}
    context_rows = []
    saved_rows = [] if write else parse((HERE / 'context-custody.json').read_bytes())['records']
    if not write: assert len(saved_rows) == len(CONTEXT)
    for index, (original, owned) in enumerate(CONTEXT):
        original_path = REPO / original if write else Path(saved_rows[index]['original_path'])
        assert original_path.is_absolute()
        assert original_path.as_posix().casefold().endswith('/' + original.casefold())
        owned_path = HERE / owned
        data = original_path.read_bytes() if write else owned_path.read_bytes()
        expect(data, PINS[original])
        if not write and original_path.exists():
            assert original_path.read_bytes() == data, original
        result[owned] = data
        context_rows.append({'original_path': str(original_path), 'owned_copy': owned,
                             **pin(data), 'original_if_present_must_match': True})
    result['context-custody.json'] = encode({
        'schema': 'i04-var09-safe-context-custody/v1', 'records': context_rows,
        'originals_optional_after_publication_when_owned_copy_exact': True,
        'private_full_app_context_originals_are_not_copied': True,
    })
    parent_index_data = (PARENT / 'evidence-index.json').read_bytes()
    expect(parent_index_data, PARENT_INDEX_PIN)
    parent_index = parse(parent_index_data)
    assert parent_index['source_count'] == len(parent_index['source_files']) == 401
    assert parent_index['raw_count'] == len(parent_index['raw_files']) == 153
    assert parent_index['preflight_original_count'] == len(parent_index['preflight_original_files']) == 15
    selected = SELECTED_PARENT.read_bytes()
    expect(selected, SELECTED_PARENT_PIN)
    selected_obj = parse(selected)
    raw_pairs = selected_obj['parent_sources_and_catalog']
    assert len(raw_pairs) == 404 and raw_pairs[-1]['path'].endswith('publication-index-v1.json')
    rows = []
    for row in raw_pairs[:-1]:
        assert set(row) == {'path', 'oid', 'bytes', 'sha256', 'git', 'byte_equal'}
        rows.append({k: row[k] for k in ('path', 'bytes', 'sha256', 'git', 'oid')})
    assert len(rows) == 403
    result['parent-source-pairs.json'] = encode({'schema': 'i04-var09-parent-disk-git-pairs/v1',
                                                  'records': rows, 'source_parent_sha256': SELECTED_PARENT_PIN[1]})
    for field, out, schema, expected in (
        ('raw_files', 'raw-custody-map.json', 'i04-var09-parent-raw-custody/v1', 153),
        ('preflight_original_files', 'preflight-custody-map.json', 'i04-var09-parent-preflight-custody/v1', 15),
    ):
        rr = []
        for row in parent_index[field]:
            assert row['original_mandatory'] is True
            assert set(row) == {'path', 'bytes', 'sha256', 'role', 'original_mandatory', 'owned_copy'}
            rr.append({'path': row['path'], 'bytes': row['bytes'], 'sha256': row['sha256'],
                       'role': row['role'], 'original_mandatory': True, 'owned_copy': None})
        assert len(rr) == expected
        result[out] = encode({'schema': schema, 'records': rr, 'source_parent_index_sha256': PARENT_INDEX_PIN[1]})
    local_cat = ((REPO / 'cases/simlox-air-support/publication-index-v1.json') if write else
                 (HERE / 'preserved-context/owned-catalog-local-498.json.bytes')).read_bytes()
    expect(local_cat, CATALOG_LOCAL_PIN)
    git_cat = git_blob(CATALOG_GIT_OID) if write else (HERE / 'preserved-context/owned-catalog-git-498.json.bytes').read_bytes()
    expect(git_cat, CATALOG_GIT_PIN)
    result['preserved-context/owned-catalog-local-498.json.bytes'] = local_cat
    result['preserved-context/owned-catalog-git-498.json.bytes'] = git_cat
    return result


def run(write: bool) -> dict:
    files = expected_files(write)
    for relative, data in files.items():
        path = HERE / relative
        if write:
            assert not path.exists(), f'owned target exists: {relative}'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        assert path.read_bytes() == data, relative
    return {'schema': 'i04-var09-safe-custody-check/v1', 'owned_files': len(files),
            'context_copies': len(CONTEXT), 'parent_pairs': 403,
            'mandatory_raw': 153, 'mandatory_preflight': 15,
            'current_catalog_local_sha256': CATALOG_LOCAL_PIN[1],
            'current_catalog_git_sha256': CATALOG_GIT_PIN[1], 'native_calls': 0}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    print(json.dumps(run(args.write), sort_keys=True, separators=(',', ':')))

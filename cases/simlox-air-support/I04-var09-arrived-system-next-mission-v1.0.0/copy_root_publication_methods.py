"""Pin safe, unexecuted root publisher methods and their static review history."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ROWS = [
    ('v100-stage', 'tmp/i04-var09-root-catalog-stage-v100-20261008.py', 5866, '8c88d7649c10d39780891c4d93953c50f3105203746a0a4796d2b642889ab239'),
    ('v100-audit', 'tmp/i04-var09-root-publication-byte-audit-v100-20261008.py', 8397, 'ee293d78d04a5dc32d695dcce6cf6a79713ce5c913770b381880c44427a638bb'),
    ('v100-capture', 'tmp/i04-var09-root-publication-capture-v100-20261008.py', 5144, '1dc7222ee6669df061f276cc222a80d08f75198957f6a9c7061055b32b7e0ad6'),
    ('v100-no-go', 'tmp/i04-var09-root-publication-wrappers-v100-static-no-go-20261008.md', 1730, '739a21fe15d550fabb01275b1ebdc141753db4f1b87c8a6caa0e4fc4de14c6dc'),
    ('v101-stage', 'tmp/i04-var09-root-catalog-stage-v101-20261008.py', 5950, '07da3cc62f3e6fe2193cd9e59559173b1aa4ba382cdafbf03d48f09a5a234deb'),
    ('v101-audit', 'tmp/i04-var09-root-publication-byte-audit-v101-20261008.py', 8907, 'd112f89fca82621b877d12ce3e0923046e0f7ad64de5562b1fe4721ffc621360'),
    ('v101-capture', 'tmp/i04-var09-root-publication-capture-v101-20261008.py', 5217, '751d8568bced43399deddefd981cfdb3e32c75e782795995d52d0ddae9077d0d'),
    ('v101-static-go', 'tmp/i04-var09-root-publication-wrappers-v101-static-go-20261008.md', 2060, '93b9f90e21e5a4ea0b289543519f3608eb7d1d01b27f90c8931346f7d4cad684'),
]
MAP = HERE / 'root-publication-method-custody.json'


def pin(data: bytes) -> dict:
    return {'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()}


def encode(value: dict) -> bytes:
    return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def candidate(write: bool = False) -> dict:
    saved = None if write else json.loads(MAP.read_bytes())
    if saved is not None:
        assert saved['schema'] == 'i04-var09-root-publication-method-custody/v1'
        assert len(saved['records']) == len(ROWS)
    records = []
    for index, (role, relative, size, sha) in enumerate(ROWS):
        owned = f'preserved-root-publication/method-{index:02d}.bytes'
        original = REPO / relative if write else Path(saved['records'][index]['original_path'])
        assert original.is_absolute() and original.as_posix().casefold().endswith('/'+relative.casefold())
        target = HERE / owned
        source = original.read_bytes() if write else target.read_bytes()
        assert pin(source) == {'bytes':size,'sha256':sha}
        if not write and original.exists(): assert original.read_bytes() == source
        if write:
            assert not target.exists(), owned
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(source)
        assert target.read_bytes() == source
        records.append({'role':role,'original_path':str(original),'owned_copy':owned,
                        'bytes':size,'sha256':sha,'original_if_present_must_match':True})
    result = {'schema':'i04-var09-root-publication-method-custody/v1','records':records,
              'originals_optional_after_publication_when_copies_exact':True,
              'v100_methods_not_executed':True,
              'v101_static_go_does_not_approve_catalog_or_git':True}
    body = encode(result)
    if write:
        assert not MAP.exists()
        MAP.write_bytes(body)
    assert MAP.read_bytes() == body
    return {'schema':result['schema'],'records':len(records),
            'map_sha256':pin(body)['sha256'],'native_calls':0,
            'catalog_mutations':0,'git_mutations':0}


if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    print(json.dumps(candidate(args.write),sort_keys=True,separators=(',',':')))

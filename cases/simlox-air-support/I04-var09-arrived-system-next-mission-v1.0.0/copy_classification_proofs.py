"""One-time owned copies of exact, small classification proof streams and method sources."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import source_gate

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
MAP=HERE/'classification-proof-custody.json'
PROCESSES=[
    ('publication-copy', 'tmp/i04-var09-copy-root-publication-20261008-01', 1153, '152d52b80d5c84ab6354f01918be46f90cdb37fa115d829e5ed8553302ee5963'),
    ('root-selection', 'tmp/i04-var05-root-review-proofs-v102-20261008/next-classification-selection-20261008T111751404786Z-36127a45', 1359, '760153013202432a8a38b3cbe3c9ae9ec0ad2b29174c3f2a8d43cb7ea83d2603'),
    ('independent-contract', 'tmp/i04-var09-root-review-proofs-v100-20261008/independent-contract-20261008T112723518374Z-4882b788', 1367, '0c52f59ddbdf78bc9b2c7c674f4457d183eeaa588f94bcb0bfc70096c0861ae7'),
    ('author-outer', 'tmp/i04-var09-root-review-proofs-v100-20261008/author-original-proof-20261008T115523506871Z-f2c853d5', 1366, '8d2cc79f8d9649b9239ddceb2ac72bdaa0071da997fe9eaaf7c1786ef4de5a24'),
    ('author-self-check', 'tmp/i04-var09-author-original-proof-v100-20261008-01/self-check', 2131, '995fb9cb0cb5d1cc5a2cfc2ad4ded22b73c914089e6f6382b0c2ed2d4627dba6'),
    ('author-classification', 'tmp/i04-var09-author-original-proof-v100-20261008-01/classification', 2162, '98755b9c1cb699af033da4fb074c17852cc3131a555a83418493f884b6efdb5e'),
    ('independent-pure', 'tmp/i04-var09-root-review-proofs-v100-20261008/independent-pure-20261008T115629196008Z-a7a75ef5', 1366, '0765c5d33cbf3abb1787d272767e1360eb86f230a096c84d994ca66c505291e6'),
    ('independent-preindex', 'tmp/i04-var09-root-review-proofs-v100-20261008/independent-preindex-20261008T115636473707Z-5279919d', 1370, '465399ebd19876d145e6c85a4abe79081bd035f11638bb8f8404b1be54d54e55'),
]
METHODS=[
    ('publication-copy-capture', 'tmp/i04-var09-copy-root-publication-capture-20261008.py', 1764, 'cd8fdc144cbda4e535fccb79d03130565a7e2169686775cab8326f3a3efe1b84'),
    ('selection-root-capture', 'tmp/i04-var05-root-review-capture-v102-20261008.py', 1952, '9a1c2b1ff71766b5f7c925604c6a144f13e7a699ae7e470bcbfbc4bd2cafb2c2'),
    ('selection-method', 'tmp/i04-var09-root-selection-boundary-20261008.py', 5558, '6bc691f9d443536d67ff8077b49a8a4850dd2489ff28e01da477d2bce2f44144'),
    ('classification-root-capture', 'tmp/i04-var09-root-review-capture-v100-20261008.py', 1952, '225340c804c8a123d7b40e7e6626535e4127ae714fccc82c437b165d5b7d049e'),
    ('contract-audit-method', 'tmp/i04-var09-independent-contract-audit-v100-20261008.py', 9794, '574d48c8e28573b1073220c46b0fb1f92cdf20d216a8b65327660eeb7aab8779'),
    ('unexecuted-author-dispatch-draft', 'tmp/i04-var09-root-author-proof-dispatch-20261008.py', 934, '3df5637f6d74cf0e97249232abf719a0d7df54f2d11291298345f77f5aa9ed65'),
    ('author-dispatch-v101', 'tmp/i04-var09-root-author-proof-dispatch-v101-20261008.py', 934, 'cae06f650ac2c09255cef315be821f46400c82e77163a14a5cb25f0a33c473de'),
    ('independent-pure-dispatch', 'tmp/i04-var09-independent-pure-dispatch-v100-20261008.py', 1196, '4e658e922d47f20dd9d89ca8b2215c735f49a4cf1b5b503a299839254102b74b'),
    ('independent-preindex-dispatch', 'tmp/i04-var09-independent-preindex-dispatch-v100-20261008.py', 1223, '43b8864f23e23c87737319bbae3f7eaae5bf1d4f47b567ff2c98b4c582ed6250'),
    ('author-proof-draft-before-ro', 'tmp/i04-var09-author-method-proof-v100-before-ro-finally-20261008.py', 3746, 'bc7d62451d93a2ee0a415166ac7c999b2bd4ae806257c9d2e1b6b1678c34ebe8'),
    ('author-proof-draft-before-topology', 'tmp/i04-var09-author-method-proof-v100-before-403-topology-20261008.py', 4351, '60b148ce31e63cd8b37e3e7ecc059c8b8569efd77510c8dfe4caa69c77ef1bf0'),
    ('author-proof-active', 'tmp/i04-var09-author-method-proof-v100-20261008.py', 4351, '5c568f40fcc26b63a4885e1708c894658d29d52cc1f0ddc0ec00ee69ef59a19b'),
]


def pin(data:bytes)->dict:
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def encode(value:dict)->bytes:
    return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def read_original(relative:str,index:int,write:bool,saved:dict|None)->tuple[str,bytes]:
    if write:
        original=REPO/relative
        data=original.read_bytes()
    else:
        row=saved['records'][index]
        original=Path(row['original_path'])
        data=(HERE/row['owned_copy']).read_bytes()
    assert original.is_absolute() and original.as_posix().casefold().endswith('/'+relative.casefold())
    if not write and original.exists(): assert original.read_bytes()==data
    return str(original),data


def candidate(write:bool=False)->dict:
    saved=None if write else source_gate.decode(MAP.read_bytes())
    assert write or (saved['schema']=='i04-var09-classification-proof-custody/v1' and len(saved['records'])==36)
    records=[]
    process_receipts=[]
    pending=[]
    for label,directory,size,sha in PROCESSES:
        triplet={}
        for name in ('receipt.json','stdout.bin','stderr.bin'):
            relative=directory+'/'+name
            index=len(records)
            original,data=read_original(relative,index,write,saved)
            owned=f'preserved-proof/proof-{index:02d}.bytes'
            if not write:
                assert saved['records'][index]['owned_copy']==owned
            records.append({'role':label+':'+name,'original_path':original,'owned_copy':owned,
                            **pin(data),'original_if_present_must_match':True})
            pending.append((owned,data))
            triplet[name]=data
        assert pin(triplet['receipt.json'])=={'bytes':size,'sha256':sha}
        receipt=source_gate.decode(triplet['receipt.json'])
        assert type(receipt['actual_exit']) is int and receipt['actual_exit']==0
        assert receipt['streams']['stdout.bin']==pin(triplet['stdout.bin'])
        assert receipt['streams']['stderr.bin']==pin(triplet['stderr.bin'])
        assert triplet['stderr.bin']==b''
        assert receipt['method_before']==receipt['method_after']
        if 'native_dispatch' in receipt: assert receipt['native_dispatch'] is False
        if label=='author-self-check':
            verdict=source_gate.decode(triplet['stdout.bin'])
            assert verdict['decision']=='PASS' and type(verdict['semantic_rejections']) is int and verdict['semantic_rejections']==30
        if label=='author-classification':
            verdict=source_gate.decode(triplet['stdout.bin'])
            assert verdict['decision']=='PROSPECTIVE_CLASSIFIER_PASS'
            assert verdict['ledger']['lines']==118 and verdict['ledger']['timed_records']==104
            assert verdict['report']['new_selected_behavior_cells']==10
        if label=='independent-preindex':
            verdict=source_gate.decode(triplet['stdout.bin'])
            assert verdict['decision']=='GO_BOUNDED_CLASSIFICATION' and verdict['mode']=='preindex'
            assert verdict['new_selected_behavior_cells']==10 and verdict['new_native_runs']==0
        process_receipts.append({'role':label,'receipt_sha256':sha,'actual_exit':0})
    for label,relative,size,sha in METHODS:
        index=len(records)
        original,data=read_original(relative,index,write,saved)
        owned=f'preserved-proof/proof-{index:02d}.bytes'
        if not write: assert saved['records'][index]['owned_copy']==owned
        assert pin(data)=={'bytes':size,'sha256':sha}
        records.append({'role':'method:'+label,'original_path':original,'owned_copy':owned,
                        'bytes':size,'sha256':sha,'original_if_present_must_match':True})
        pending.append((owned,data))
    assert len(records)==36 and len(process_receipts)==8
    result={'schema':'i04-var09-classification-proof-custody/v1','records':records,
            'process_receipts':process_receipts,'process_count':8,'method_source_count':12,
            'originals_optional_after_publication_when_copies_exact':True,
            'all_native_dispatches_false':True}
    body=encode(result)
    if write:
        assert not MAP.exists()
        assert all(not (HERE/owned).exists() for owned,_ in pending)
        (HERE/'preserved-proof').mkdir(exist_ok=True)
        for owned,data in pending: (HERE/owned).write_bytes(data)
        MAP.write_bytes(body)
    assert MAP.read_bytes()==body
    for owned,data in pending: assert (HERE/owned).read_bytes()==data
    return {'schema':result['schema'],'records':36,'process_count':8,'method_source_count':12,
            'map_sha256':pin(body)['sha256'],'native_calls':0,'accepted_checker_reruns':0}


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    print(json.dumps(candidate(args.write),sort_keys=True,separators=(',',':')))

"""Own byte-identical inert copies of the one captured local PURE proof."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ORIGINAL=HERE/"test-output"/"local-pure-20261008T031156407526Z-1303441c"
OWNED=HERE/"preserved-pure-proof"
MAP=HERE/"pure-proof-custody.json"
NAMES=("build-stdout.bin","build-stderr.bin","context-stdout.bin","context-stderr.bin",
       "source-stdout.bin","source-stderr.bin","selfcheck-stdout.bin","selfcheck-stderr.bin",
       "inventory-stdout.bin","inventory-stderr.bin","manifest-stdout.bin","manifest-stderr.bin",
       "receipt.json")

def pin(b):return {"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()}

def candidate(write=False):
    rows=[]
    for i,name in enumerate(NAMES):
        original=ORIGINAL/name
        copy=OWNED/f"pure-{i:02d}.bytes"
        assert original.is_file() or copy.is_file(),name
        data=copy.read_bytes() if copy.is_file() else original.read_bytes()
        if original.is_file():assert original.read_bytes()==data,name
        if copy.is_file():assert copy.read_bytes()==data,name
        elif write:
            OWNED.mkdir(exist_ok=True)
            with copy.open("xb") as f:f.write(data)
        rows.append({"original_path":str(original),"owned_copy":copy.relative_to(HERE).as_posix(),
                     **pin(data),"original_if_present_must_match":True})
    result={"schema":"i03-var08-local-pure-proof-custody/v1","records":rows,
            "original_receipt_sha256":"84148102ba9cd91eb3f50c667b5ca624c40b826f9741e68d2d4a3a2aff45b01e"}
    assert rows[-1]["sha256"]==result["original_receipt_sha256"]
    body=(json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    if MAP.exists():assert MAP.read_bytes()==body
    elif write:
        with MAP.open("xb") as f:f.write(body)
    return {"schema":result["schema"],"copies":len(rows),"map":pin(body),"exists":MAP.exists()}

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--write",action="store_true")
    print(json.dumps(candidate(ap.parse_args().write),sort_keys=True))

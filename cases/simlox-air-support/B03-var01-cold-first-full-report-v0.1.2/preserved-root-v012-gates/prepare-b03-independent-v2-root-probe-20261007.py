from pathlib import Path
r=Path(__file__).resolve().parents[1]
old=r/'tmp/probe-b03-v012-independent-root-20261007.py'
new=r/'tmp/probe-b03-v012-independent-v2-root-20261007.py';assert not new.exists()
s=old.read_text(encoding='utf-8')
s=s.replace("review/independent_replay.py","review/independent_replay_v2.py").replace('09beef94ea291807a9fdddb38864fe9bf16750d2e33cab094fbbfd812663b36c','e8141f93356fbe60c0be1b65146840b771330a9c2d13670f7d97c5b4db835c7b')
s=s.replace('b03-v012-independent-root','b03-v012-independent-v2-root')
marker="assert hashlib.sha256(method.read_bytes()).hexdigest()==h\nv="
extra="""original_parser=m.native_json_bytes
for level in ['database_version','instance_name','table_metadata','instance_metadata']:
    test=m.native_json_bytes((d/'roundtrip-raw.json').read_bytes())
    if level=='database_version':test['model']['database_version']='incorrect'
    elif level=='instance_name':test['model']['tables'][0]['instances'][0]['instance_name']='incorrect'
    elif level=='table_metadata':test['model']['tables'][0]['unexpected']='hours'
    else:test['model']['tables'][0]['instances'][0]['unexpected']='hours'
    try:
        m.native_json_bytes=lambda raw,test=test:test
        probe('roundtrip_'+level,lambda:m.roundtrip(src,d))
    finally:m.native_json_bytes=original_parser
"""
assert marker in s
s=s.replace(marker,extra+marker)
compile(s,str(new),'exec');new.write_text(s,encoding='utf-8');print(str(new))

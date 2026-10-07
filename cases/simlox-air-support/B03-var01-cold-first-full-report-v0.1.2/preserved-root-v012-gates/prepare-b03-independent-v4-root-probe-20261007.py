from pathlib import Path
r=Path(__file__).resolve().parents[1]
new=r/'tmp/probe-b03-v012-independent-v4-root-20261007.py';assert not new.exists()
s=(r/'tmp/probe-b03-v012-independent-v2-root-20261007.py').read_text(encoding='utf-8')
s=s.replace('review/independent_replay_v2.py','review/independent_replay_v4.py').replace('e8141f93356fbe60c0be1b65146840b771330a9c2d13670f7d97c5b4db835c7b','37d781293f2f6c9892598239296b18ac3c4d2e10473d042d74a2c3527fe3507f').replace('b03-v012-independent-v2-root','b03-v012-independent-v4-root')
s=s.replace("src=m.source_and_provenance(c);d=", "src,availability=m.source_and_provenance(c);d=")
marker="assert hashlib.sha256(method.read_bytes()).hexdigest()==h\nv="
extra="""duplicate=original_parser((d/'roundtrip-raw.json').read_bytes())
duplicate['model']['tables'].append(copy.deepcopy(duplicate['model']['tables'][0]))
probe('roundtrip_duplicate_table',lambda:m.roundtrip(src,d,duplicate))
missing=p/'review/__root_absent_archive_origin_probe__';assert not missing.exists()
assert m.archived_pin(c['excluded_v010']['files'][0],missing) is False
badpin=copy.deepcopy(c['excluded_v010']['files'][0]);badpin['sha256']='0'*64
probe('missing_original_still_requires_inert_copy_pin',lambda:m.archived_pin(badpin,missing))
"""
assert marker in s;s=s.replace(marker,extra+marker)
compile(s,str(new),'exec');new.write_text(s,encoding='utf-8');print(str(new))

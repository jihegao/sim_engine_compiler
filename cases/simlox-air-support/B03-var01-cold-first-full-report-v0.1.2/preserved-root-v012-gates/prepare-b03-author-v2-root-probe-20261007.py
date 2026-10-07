from pathlib import Path
r=Path(__file__).resolve().parents[1]
new=r/'tmp/probe-b03-v012-author-v2-root-20261007.py';assert not new.exists()
s=(r/'tmp/probe-b03-v012-author-root-20261007.py').read_text(encoding='utf-8')
for old,fresh in [('replay.py','replay_v2.py'),('self_check.py','self_check_v2.py'),('METHOD.md','METHOD-v2.md'),('8060423d1e2a3c70068fc4c2f976e73a71978ad4554d0cdd5f4717f4323e8a61','d6d1798c7cb2428a59a70cf3040cbbe39af11fc79dfef5ca8624cbbe2018bcb9'),('a4143b3c413cb948688158bdac45ffa978536821f8c5baea35c1dc0656865d72','1ac865b65ad83f009a3f3753db87368ed2364d5615abdbbb7b369b4d0d7e0bc7'),('9d00071b9fbe8017be7b5270822e5bafb5953024ccf4b611a3590a7cfe52026c','5fd93e80d75de41090d828f372d8b9e3d7d35b21b5f9f253174e7319c34a3a69'),('b03-v012-author-root','b03-v012-author-v2-root')]:s=s.replace(old,fresh)
compile(s,str(new),'exec');new.write_text(s,encoding='utf-8');print(str(new))

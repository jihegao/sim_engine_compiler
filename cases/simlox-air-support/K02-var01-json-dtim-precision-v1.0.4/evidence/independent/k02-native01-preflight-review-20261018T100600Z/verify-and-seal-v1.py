import json, hashlib, datetime, pathlib, subprocess
P=pathlib.Path('C:/Users/user/Documents/Codex/2026-10-10/issue18-cli-20261009T195400Z')
K=pathlib.Path('C:/Users/user/Documents/Codex/2026-10-09/i05-var08-pm-location/cases/simlox-air-support/K02-var01-json-dtim-precision-v1.0.4')
D=pathlib.Path(__file__).parent
MH='750bb491b1ec359a40b8d278facc4c7a5b380cc675b6f9bada9ac0c840189f42'
R='k02-json-dtim-v104-ssh-20261018-01'
pins={}
def pin(p):
 p=pathlib.Path(p); b=p.read_bytes(); return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def read(p):
 q=pin(p); pins[q['path']]=q; return json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))
def bound(q):
 assert pin(q['path'])=={k:q[k] for k in ('path','bytes','sha256')},q
 return read(q['path'])
def save(p,x):
 with pathlib.Path(p).open('x',encoding='utf-8',newline='\n') as f: json.dump(x,f,indent=2,ensure_ascii=False); f.write('\n')
 return pin(p)
utc=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
m=read(K/'selected-manifest-v12.json'); assert pin(K/'selected-manifest-v12.json')['sha256']==MH
s=read(K/'review/independent-preflight-go-v12.json'); assert pin(K/'review/independent-preflight-go-v12.json')['sha256']=='116a48d6752b26230612ff0e64ac6d2d058aac331665b225c76a90f9c341b2be'
b=bound(s['benign_acceptance']); assert b['decision']=='GO_SELECTED_REAL_BENIGN_ACCEPTED' and b['terminal'] and b['manifest_sha256']==MH
assert b['probe0_run_id']==m['targets']['probe0']['run_id'] and b['probe7_run_id']==m['targets']['probe7']['run_id']
pfp=K/'review/preflight-20261018T095951452Z.json'; pf=read(pfp)
assert pin(pfp)['sha256']=='21a38d0b8a6c7353cc4a82b81f18df0198c78933e54869dfa74fb50077a3b05f'
td=K/'review/transport-preflight-2589edd5186c43c6a6b247204a4b5dfa'; tr=read(td/'transport-receipt.json')
gp=K/'review/guardian-preflight-v12-20261018T100200Z.json'; g=read(gp)
assert pin(gp)['sha256']=='d8860628b9a5ad1a88550dd59d03cc0d4f65a164eed4c9972d1adee42102ed6c'
for x in (pf,tr,g): assert x['manifest_sha256']==MH and x['run_id']==R
assert pf['decision']=='GO_PRELAUNCH_CANDIDATE' and pf['ps_major']==5 and pf['session_id']==0 and pf['host']=='4700-3'
assert pf['native_process_started'] is False and pf['run_directory_absent'] is True
assert pf['native_queue_held'] is True and pf['native_queue_abandoned'] is False
assert pf['gui']==g['gui']==m['gui'] and pf['gui']['pid']==13340
assert any(x['name'].lower()=='sshd.exe' and x['session']==0 for x in pf['ssh_ancestors'])
assert pf['settings']['user_sid']==m['settings']['user_sid'] and pf['settings']['values']==m['settings']['values'] and pf['settings']['read_only']
assert pf['ssh_connection']==pf['transport_identity']['connection'] and pf['ssh_connection'].split()[::2]==['127.0.0.1','127.0.0.1']
assert pf['static_review_sha256']==tr['review_sha256']==pin(K/'review/independent-preflight-go-v12.json')['sha256']
assert pf['guardian_sha256']==tr['guardian_sha256']==pin(gp)['sha256']
assert tr['mode']=='preflight' and tr['exit_code']==0 and tr['error'] is None and tr['source_stability_error'] is None and tr['native_approved'] is False
assert g['mode']=='preflight' and g['decision']=='GO_STANDALONE_SAFETY_ONLY' and g['terminal'] and g['native_calls']==0 and g['guard_session']==0
assert all(g[k] is True for k in ('native_queue_free','executor_mutex_held','physical_absent','recovered_absent'))
assert any('user' in row and ' 1 ' in row and 'Active' in row for row in g['wts'])
expectedrefs=['5900513b3d3d9c581d50ff904dd460c984afbc96\trefs/heads/main','493f8a1639961d3af5da6dc79b03d6286342e476\trefs/heads/simlox/main']
assert len(pf['git_freshness'])==2
for row in pf['git_freshness']:
 assert row['exit_code']==0 and row['refs']==expectedrefs and row['configuration_edits']==0
 assert row['host']=='ssh.github.com' and row['port']==443 and row['strict_host_key_checking']=='yes' and row['update_host_keys']=='no'
 assert row['overall_git_deadline_proven'] is False and row['SSH_network_phase_deadline_seconds']==20
for name in ('stdout','stderr'):
 q=pin(td/(name+'.bin')); assert {k:q[k] for k in ('bytes','sha256')}==tr['streams'][name]; pins[q['path']]=q
assert (td/'stderr.bin').read_bytes()==b''
assert pathlib.Path((td/'stdout.bin').read_text(encoding='utf-8-sig').strip())==pfp
assert subprocess.list2cmdline(tr['command'])==pf['transport_identity']['client_command']
assert tr['command'][0]==m['ssh']['path'] and tr['command'][tr['command'].index('-Mode')+1]=='preflight'
assert m['native_steps']==['jimport_save','jexport'] and m['simulation_calls']==0 and m['parent_reruns']==0
assert m['targets']['native']['run_id']==R
for key in ('physical_directory','recovered_directory'): assert not pathlib.Path(m['targets']['native'][key]).exists()
for q in m['sources']:
 actual=pin(q['path']); assert actual=={k:q[k] for k in ('path','bytes','sha256')}; pins[actual['path']]=actual
# All tool records are byte-pinned even where they are not JSON.
for key in ('exe','git','ssh','powershell','python','compiler','probe_exe','runner_binary','independent_process_query','live_index','live_catalog'):
 q=m[key]; actual=pin(q['path']); assert actual=={k:q[k] for k in ('path','bytes','sha256')}; pins[actual['path']]=actual
entry=K/'run_selected_ssh_v12.ps1'; ep=pin(entry); assert pf['runner_sha256']==ep['sha256']=='76dac17da67524c201b094ee22fc48ce34fdd646bf1b863cf28710316bb947c7'
src=entry.read_text(encoding='utf-8-sig'); assert src.index("if($Mode -ceq 'preflight'){\n $mu=")<src.index('Add-Type -Path $m.runner_binary.path')<src.index('::Execute(')
assert "}finally{if($owned){$mu.ReleaseMutex()};$mu.Dispose()};Write-Output $receipt;exit 0" in src
authority=P/'human-owned-benign-preResume-recovery-20261018T091430Z.json'; read(authority)
accept=dict(schema='issue18-independent-actual-preflight-acceptance/v12',utc=utc(),terminal=True,completed=True,decision='GO_SELECTED_ACTUAL_PREFLIGHT_ACCEPTED',mode='preflight',run_id=R,manifest_sha256=MH,preflight=pin(pfp),preflight_transport=pin(td/'transport-receipt.json'),guardian=pin(gp),benign_acceptance=s['benign_acceptance'],actual_SSH0_PS5=True,actual_transport_terminal_exit_code=0,source_stability_error=None,native_process_started=False,native_target_still_absent=True,queue_qualification='Receipt records normal ownership before preflight return. Exact source finally releases that newly acquired mutex and disposes wrapper before exit0; natural terminal0 corroborates this control flow. No independent same-H kernel release instrumentation is fabricated.',network_qualification='Two exact-ref queries succeeded; bounded SSH-child phase only, no total Git/DNS harddeadline claim.',native_result_accepted=False,publication_GO=False)
ap=save(D/'actual-preflight-acceptance-v1.json',accept)
conditions=['Exactly one unused native01 attempt; fresh separately terminal native guardian plus actual SSH0 PS5, original GUI/WTS1 Active, exact current transport, pins/settings/refs and normal queue required.','Only jimport_save then jexport; simulation/calc and parent reruns are not authorized by this gate.','Use unchanged owner5/query lifetime protections; original H signal precedes writer closure, sealing, exact recovery and queue-last release. Unknown acquisition/query/Create/Resume/wait/close retains original handles, owner stack and queue; no kill, retry or manual release.','381 typed cells and exact prospective DTIM binary64 predicates remain unchanged. Native result acceptance and publication require separate actual raw review. No occupied prior run is replayed.']
gate=dict(schema='issue18-independent-selected-native-go/v12',utc=utc(),terminal=True,completed=True,decision='GO_PRELAUNCH',mode='native',run_id=R,manifest_sha256=MH,manifest=pin(K/'selected-manifest-v12.json'),preflight=pin(pfp),preflight_transport=pin(td/'transport-receipt.json'),benign_acceptance=s['benign_acceptance'],actual_preflight_acceptance=ap,accepted_static=s['accepted_static'],authority=pin(authority),authority_qualification='Existing direct-human instruction authorizes necessary safe repairs, actual probes and continued K02 execution after preserved gates; exact PID/run/step restrictions are implementation mapping, not fabricated literal human wording.',native_steps=m['native_steps'],attempt_limit=1,simulation_calls=0,parent_reruns=0,conditions=conditions,native_execution_permission=True,native_result_accepted=False,publication_GO=False,whole_issue_complete=False,denominator=None)
# Recheck all completed input bytes before creating the executable permission.
for q in pins.values(): assert pin(q['path'])==q
gatepin=save(K/'review/independent-native-go-v12.json',gate)
terminal=dict(schema='issue18-independent-preflight-native01-terminal/v1',utc=utc(),terminal=True,completed=True,decision='GO_ACTUAL_PREFLIGHT_ACCEPTED_EXACT_NATIVE01_PRELAUNCH',run_id=R,manifest_sha256=MH,actual_preflight_acceptance=ap,native_gate=gatepin,source_pins=list(pins.values()),independent_artifacts=[pin(__file__),ap,gatepin],review_tool_failures=[dict(phase='first artifact read',host_process_created=False,detail='exec_command CreateProcess rejected: helper_unknown_error: setup refresh had errors; retried same artifact-only reads under explicit escalation successfully; no candidate call or mutation')],no_execution=dict(native=0,model=0,SSH=0,Git=0,process_operations=0,mutex_operations=0,Goal=0),source_raw_oracle_unchanged=True,remaining_holds=['Actual native01 result and independent raw acceptance remain unperformed','Publication, complete new native reproduction/derivation and whole Issue remain separate/open','v103 sealed failure and all prior failed/occupied IDs retained','Crossengine UNVERIFIED_SEPARATE_STATUS_NOT_NATIVE_GATE; GUI OUT_NOT_PASS; CI waiver NOT_PASS'],conditions=conditions,whole_issue_complete=False,denominator=None)
tp=save(D/'terminal-receipt-v1.json',terminal)
for q in terminal['independent_artifacts']+terminal['source_pins']: assert pin(q['path'])==q
print(json.dumps(dict(terminal=tp,native_gate=gatepin,actual_preflight_acceptance=ap,pins_verified=len(pins)),indent=2))

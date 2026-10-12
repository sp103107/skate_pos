from __future__ import annotations
from copy import deepcopy
import hashlib,json,os,sqlite3,subprocess,sys,uuid,zipfile
from pathlib import Path
import pytest
from skate_inventory_core import CoreConfig,CoreLifecycleError,CoreRequestError,SkateInventoryCore
from skate_inventory_core import cli
from skate_inventory_core.facades import QUERY_PARAMS,RUNTIME_PARAMS,validate_params
from conftest import envelope
from test_core_composition import seed,register
from logical_state import logical_state


@pytest.fixture
def core(tmp_path):
    c=SkateInventoryCore(CoreConfig(tmp_path/'core.db')).initialize();seed(c);register(c)
    yield c
    c.shutdown()


def request_call(core,kind,name,params):
    return core.query(name,params) if kind=='query' else core.runtime_operation(name,params)


QUERIES=[('get_pair',{'pair_id':'SKT-0400'}),('list_inventory',{}),('find_asset',{'identifier':'SKT-0400-L'}),('asset_history',{'pair_id':'SKT-0400'}),('runtime_status',{'deep':True})]


@pytest.mark.parametrize('name,params',QUERIES)
def test_each_query_is_detached_json_and_no_logical_writes(core,name,params):
    before=logical_state(core.config.sqlite_path);original=deepcopy(params)
    out=core.query(name,params);json.dumps(out,allow_nan=False)
    expected=deepcopy(out)
    if isinstance(out,dict):out.clear()
    elif isinstance(out,list):out.clear()
    assert core.query(name,params)==expected and params==original
    assert logical_state(core.config.sqlite_path)==before
    if name=='get_pair':assert expected==core.get_pair('SKT-0400')
    elif name=='list_inventory':assert expected==core.list_inventory()
    elif name=='runtime_status':assert expected==core.health(deep=True)


def test_missing_and_exact_identifier_input(core):
    before=logical_state(core.config.sqlite_path)
    assert core.query('get_pair',{'pair_id':'missing'}) is None
    assert core.query('find_asset',{'identifier':'missing'}) is None
    assert core.query('find_asset',{'identifier':' SKT-0400 '}) is None
    assert core.query('asset_history',{'pair_id':'missing'})==[]
    assert core.query('find_asset',{'identifier':"' OR 1=1 --"}) is None
    assert logical_state(core.config.sqlite_path)==before


def test_identifier_precedence_inactive_alias_and_component(core):
    pair=core.query('find_asset',{'identifier':'SKT-0400'});assert pair['resolved_type']=='PAIR'
    cmd=envelope('replace_label',{'component_id':'SKT-0400-L','new_label_identifier':'SKT-0402-L'})
    assert core.execute(cmd)['status']=='ACCEPTED'
    before=logical_state(core.config.sqlite_path)
    old=core.query('find_asset',{'identifier':'SKT-0400-L'});new=core.query('find_asset',{'identifier':'SKT-0402-L'})
    assert old['resolved_type']=='COMPONENT_LABEL' and not old['active_label']
    assert old['alias']['retired_at'] and old['alias']['active']==0
    assert new['active_label'] and old['component']==new['component']
    assert logical_state(core.config.sqlite_path)==before
    # A component with a distinct physical label exercises the third precedence.
    p={'pair_id':'SKT-0401','owner_org_id':'ORG-OWNER','size_system':'US_MENS','size_value':'8','category':'HOCKEY','home_location_id':'LOC-RINK','current_location_id':'LOC-RINK','custodian_org_id':'ORG-OWNER'}
    assert core.execute(envelope('register_pair',{'pair':p}))['status']=='ACCEPTED'
    assert core.execute(envelope('register_component',{'component':{'component_id':'SKT-0401-L','pair_id':'SKT-0401','side':'L','label_identifier':'SKT-0500-L','current_location_id':'LOC-RINK'}}))['status']=='ACCEPTED'
    assert core.query('find_asset',{'identifier':'SKT-0401-L'})['resolved_type']=='COMPONENT'


def test_history_order_integrity_json_and_corrections(core):
    history=core.query('asset_history',{'pair_id':'SKT-0400'});target=history[0]['event_id']
    receipt=core.execute(envelope('record_correction',{'target_event_id':target,'correction_mode':'ANNOTATION','reason':'test historical annotation'}))
    assert receipt['status']=='ACCEPTED',receipt
    before=logical_state(core.config.sqlite_path);history=core.query('asset_history',{'pair_id':'SKT-0400'})
    assert history[-1]['event_type']=='CORRECTION_RECORDED' and history[-1]['payload']['target_event_id']==target
    assert history[-1]['event_id']==receipt['event_ids'][0]
    assert [e['ledger_sequence'] for e in history]==sorted(e['ledger_sequence'] for e in history)
    with core.db.connect() as conn:
        stored=conn.execute('SELECT event_id,event_hash,previous_event_hash FROM asset_events WHERE pair_id=? ORDER BY rowid',('SKT-0400',)).fetchall()
    assert [(e['event_id'],e['integrity']['event_hash'],e['integrity']['previous_event_hash']) for e in history]==[tuple(r) for r in stored]
    assert all(isinstance(e['payload'],dict) and isinstance(e['evidence_refs'],list) for e in history)
    assert logical_state(core.config.sqlite_path)==before


BAD=[('query','nope',{}),('runtime','nope',{}),('query','get_pair',{}),('query','get_pair',{'pair_id':1}),('query','get_pair',{'pair_id':' '}),('query','get_pair',{'pair_id':'x','sql':'drop'}),('query','list_inventory',{'extra':1}),('query','runtime_status',{'deep':1}),('runtime','health',{'deep':'yes'}),('runtime','checkpoint',{'metadata':[]}),('runtime','checkpoint',{'create_snapshot':1}),('runtime','rebuild_projections',{'require_clean_replay':None}),('runtime','add_evidence',{}),('runtime','add_evidence',{'file_path':Path('x')}),('runtime','export_recovery',{'out_path':''}),('runtime','restore_recovery',{'bundle_path':'x'}),('runtime','export_evidence',{'out_path':'x'}),('runtime','verify_ledger',None),('runtime','checkpoint',{'metadata':{'number':float('nan')}})]
@pytest.mark.parametrize('kind,name,params',BAD)
def test_strict_invalid_params_are_write_free(core,kind,name,params):
    before=logical_state(core.config.sqlite_path)
    with pytest.raises(CoreRequestError):request_call(core,kind,name,params)
    assert logical_state(core.config.sqlite_path)==before


@pytest.mark.parametrize('kind,name',[(k,n) for k,ns in [('query',QUERY_PARAMS),('runtime',RUNTIME_PARAMS)] for n in ns])
@pytest.mark.parametrize('state,code',[('NEW','CORE_NOT_INITIALIZED'),('SHUTDOWN','CORE_SHUTDOWN')])
def test_every_facade_lifecycle(kind,name,state,code,tmp_path):
    c=SkateInventoryCore(CoreConfig(tmp_path/'not-created.db'))
    if state=='SHUTDOWN':c.shutdown()
    with pytest.raises(CoreLifecycleError,match=code):request_call(c,kind,name,{})
    assert not c.config.sqlite_path.exists()


def test_health_verify_replay_no_logical_writes(core):
    before=logical_state(core.config.sqlite_path)
    assert core.runtime_operation('health',{'deep':True})==core.health(deep=True)
    assert core.runtime_operation('verify_ledger',{})=={'ok':True,'first_bad_event_id':None}
    replay=core.runtime_operation('replay_check',{});assert replay['ledger_ok'] and replay['semantic_match']
    assert logical_state(core.config.sqlite_path)==before


def test_checkpoint_and_rebuild_real_side_effects(core):
    before=logical_state(core.config.sqlite_path)
    checkpoint=core.runtime_operation('checkpoint',{'metadata':{'purpose':'facade'},'create_snapshot':False})
    after=logical_state(core.config.sqlite_path)
    assert checkpoint['snapshot_id'] is None and len(after['tables']['ledger_checkpoints'])==len(before['tables']['ledger_checkpoints'])+1
    assert after['tables']['asset_events']==before['tables']['asset_events'] and after['tables']['command_receipts']==before['tables']['command_receipts']
    with core.db.connect() as conn:conn.execute("UPDATE skate_pairs SET size_value='wrong' WHERE pair_id='SKT-0400'")
    assert not core.runtime_operation('replay_check',{})['semantic_match']
    rebuild=core.runtime_operation('rebuild_projections',{})
    assert rebuild['semantic_match'] and core.query('get_pair',{'pair_id':'SKT-0400'})['size_value']=='8'
    assert logical_state(core.config.sqlite_path)['tables']['asset_events']==before['tables']['asset_events']


def test_evidence_add_and_deterministic_metadata_export(core,tmp_path):
    file=tmp_path/'evidence.txt';file.write_text('test evidence')
    event=core.query('asset_history',{'pair_id':'SKT-0400'})[0]['event_id']
    result=core.runtime_operation('add_evidence',{'file_path':str(file),'related_event_id':event,'media_type':'text/plain','storage_ref':'external:evidence'})
    assert result['sha256']==hashlib.sha256(file.read_bytes()).hexdigest()
    before=logical_state(core.config.sqlite_path)
    a=core.runtime_operation('export_evidence',{});b=core.runtime_operation('export_evidence',{})
    assert json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True) and a['kind']=='EVIDENCE_METADATA_ONLY'
    assert a['attachments']==[result] and a['related_events'][0]['event_id']==event
    assert 'bytes' not in a and logical_state(core.config.sqlite_path)==before
    with pytest.raises(FileNotFoundError):core.runtime_operation('add_evidence',{'file_path':str(tmp_path/'absent')})
    assert logical_state(core.config.sqlite_path)==before


def test_recovery_facade_retry_conflict_and_source_unchanged(core,tmp_path):
    cmd=envelope('transfer_location',{'pair_id':'SKT-0400','to_location_id':'LOC-STORAGE'});receipt=core.execute(cmd);assert receipt['status']=='ACCEPTED'
    before=logical_state(core.config.sqlite_path);bundle=tmp_path/'bundle.zip'
    result=core.runtime_operation('export_recovery',{'out_path':str(bundle)})
    assert result['sha256']==hashlib.sha256(bundle.read_bytes()).hexdigest() and logical_state(core.config.sqlite_path)==before
    target=tmp_path/'restored.db';restored=core.runtime_operation('restore_recovery',{'bundle_path':str(bundle),'target_db_path':str(target)})
    assert Path(restored['db'])==target and logical_state(core.config.sqlite_path)==before
    c=SkateInventoryCore(CoreConfig(target)).initialize();snap=logical_state(target)
    retry=c.execute(cmd);assert retry['status']=='DUPLICATE' and retry['event_ids']==receipt['event_ids'] and retry['result']==receipt['result']
    assert logical_state(target)==snap
    changed=deepcopy(cmd);changed['command_id']=str(uuid.uuid4());changed['payload']['to_location_id']='LOC-RINK'
    assert c.execute(changed)['error']['code']=='IDEMPOTENCY_CONFLICT' and logical_state(target)==snap
    assert c.health(deep=True)['status']=='HEALTHY';c.shutdown()


@pytest.mark.parametrize('target_kind',['live','relative_live','symlink_live','hardlink_live','existing','existing_symlink'])
def test_restore_target_protection_before_bundle_read(core,target_kind,tmp_path):
    live=core.config.sqlite_path;target=live
    if target_kind=='relative_live':target=live.parent/'nested/../core.db'
    elif target_kind in ('symlink_live','hardlink_live'):
        target=tmp_path/'alias';target.symlink_to(live) if target_kind=='symlink_live' else os.link(live,target)
    elif target_kind=='existing':target=tmp_path/'existing';target.write_text('keep')
    elif target_kind=='existing_symlink':target=tmp_path/'dangling';target.symlink_to(tmp_path/'absent')
    before=logical_state(live);original=target.read_bytes() if target.exists() else None
    with pytest.raises(CoreRequestError):core.runtime_operation('restore_recovery',{'bundle_path':str(tmp_path/'notread.zip'),'target_db_path':str(target)})
    assert logical_state(live)==before
    if original is not None:assert target.read_bytes()==original


@pytest.mark.parametrize('kind',['malformed','legacy','tampered'])
def test_invalid_recovery_no_target_or_source_changes(core,kind,tmp_path):
    good=tmp_path/'good.zip';core.runtime_operation('export_recovery',{'out_path':str(good)})
    bad=tmp_path/'bad.zip'
    if kind=='malformed':bad.write_bytes(b'not zip')
    else:
        with zipfile.ZipFile(good) as z:data={n:z.read(n) for n in z.namelist()}
        meta=json.loads(data['bundle.json'])
        if kind=='legacy':meta['format_version']='0.2.0'
        else:meta['event_count']+=1
        data['bundle.json']=json.dumps(meta).encode()
        data['MANIFEST.sha256']=''.join(f'{hashlib.sha256(v).hexdigest()}  {n}\n' for n,v in sorted(data.items()) if n!='MANIFEST.sha256').encode()
        with zipfile.ZipFile(bad,'w') as z:
            for n,v in data.items():z.writestr(n,v)
    before=logical_state(core.config.sqlite_path);target=tmp_path/'new'/'target.db'
    with pytest.raises(Exception):core.runtime_operation('restore_recovery',{'bundle_path':str(bad),'target_db_path':str(target)})
    assert not target.exists() and logical_state(core.config.sqlite_path)==before


def invoke(kind,cwd,*args):
    console=os.environ.get('C03_CONSOLE')
    prefix=[console] if console else [sys.executable,'-c','from skate_inventory_core.cli import main; raise SystemExit(main())']
    if kind=='module':prefix=[sys.executable,'-m','skate_inventory_core']
    p=subprocess.run(prefix+list(args),cwd=cwd,text=True,capture_output=True,timeout=30)
    assert 'Traceback' not in p.stderr
    return p


@pytest.mark.parametrize('kind',['console','module'])
@pytest.mark.parametrize('command,name,params',[('query','get_pair',{'pair_id':'SKT-0400'}),('query','asset_history',{'pair_id':'SKT-0400'}),('runtime','verify_ledger',{}),('runtime','export_evidence',{})])
def test_cli_query_runtime_results_and_parity(kind,command,name,params,core,tmp_path):
    file=tmp_path/'request.json';file.write_text(json.dumps({'name':name,'params':params}));before=logical_state(core.config.sqlite_path)
    p=invoke(kind,tmp_path,'--db',str(core.config.sqlite_path),command,'--file',str(file))
    assert p.returncode==0 and p.stderr=='' and len(p.stdout.splitlines())==1
    d=json.loads(p.stdout);assert d['name']==name and d['command']==command and d['result']==request_call(core,command,name,params)
    assert logical_state(core.config.sqlite_path)==before


@pytest.mark.parametrize('req',[{'name':'unknown','params':{}},{'name':'list_inventory','params':{'extra':1}},{'name':'list_inventory'}, {'name':'list_inventory','params':{},'sql':'unsafe'}])
def test_cli_invalid_request_before_boot(req,tmp_path):
    file=tmp_path/'request.json';file.write_text(json.dumps(req))
    for kind in ('console','module'):
        p=invoke(kind,tmp_path,'--db','absent/nested.db','query','--file',str(file))
        assert p.returncode==2 and not p.stdout and json.loads(p.stderr)['error']['code'] in ('UNKNOWN_QUERY','INVALID_PARAMS','INVALID_REQUEST')
    assert not (tmp_path/'absent').exists()


@pytest.mark.parametrize('kind',['console','module'])
@pytest.mark.parametrize('command,name',[('query','runtime_status'),('runtime','health'),('runtime','replay_check')])
def test_cli_actual_mismatch_nonzero(kind,command,name,core,tmp_path):
    with core.db.connect() as conn:conn.execute("UPDATE skate_pairs SET size_value='wrong' WHERE pair_id='SKT-0400'")
    params={'deep':True} if name in ('runtime_status','health') else {}
    file=tmp_path/'request.json';file.write_text(json.dumps({'name':name,'params':params}));before=logical_state(core.config.sqlite_path)
    p=invoke(kind,tmp_path,'--db',str(core.config.sqlite_path),command,'--file',str(file))
    assert p.returncode==5 and p.stderr==''
    out=json.loads(p.stdout)['result'];assert out.get('status')=='DEGRADED' or out.get('semantic_match') is False
    assert logical_state(core.config.sqlite_path)==before


def test_cli_ledger_failure_truthful(core,tmp_path):
    # Controlled corrupt copy: restore the trigger after corruption, keeping schema compatible.
    with core.db.connect() as conn:
        sql=conn.execute("SELECT sql FROM sqlite_master WHERE name='asset_events_no_update'").fetchone()[0]
        conn.execute('DROP TRIGGER asset_events_no_update');conn.execute("UPDATE asset_events SET event_hash='bad' WHERE rowid=1");conn.execute(sql)
    before=logical_state(core.config.sqlite_path)
    assert core.runtime_operation('verify_ledger',{})['ok'] is False
    for name,code in [('verify_ledger',5),('replay_check',5),('checkpoint',7),('rebuild_projections',7)]:
        file=tmp_path/'r.json';file.write_text(json.dumps({'name':name,'params':{}}))
        p=invoke('module',tmp_path,'--db',str(core.config.sqlite_path),'runtime','--file',str(file));assert p.returncode==code
        if code==5:assert json.loads(p.stdout)['result'].get('ok',False) is False
        else:assert json.loads(p.stderr)['error']['code']=='LEDGER_INTEGRITY_ERROR'
    assert logical_state(core.config.sqlite_path)==before


@pytest.mark.parametrize('command',['query','runtime'])
def test_cli_shutdown_on_facade_failure(command,core,tmp_path,monkeypatch,capsys):
    seen=[]
    class Fault(SkateInventoryCore):
        def initialize(self):seen.append(self);return super().initialize()
        def query(self,*args):raise RuntimeError('private failure')
        def runtime_operation(self,*args):raise RuntimeError('private failure')
    monkeypatch.setattr(cli,'SkateInventoryCore',Fault)
    file=tmp_path/'r.json';file.write_text(json.dumps({'name':'list_inventory' if command=='query' else 'verify_ledger','params':{}}))
    assert cli.main(['--db',str(core.config.sqlite_path),command,'--file',str(file)])==7
    out=capsys.readouterr();assert not out.out and 'private' not in out.err and seen[0].state=='SHUTDOWN'


def test_degraded_foreign_key_findings_are_json_compatible(core):
    with core.db.connect() as conn:
        conn.execute('PRAGMA foreign_keys=OFF');conn.execute("UPDATE skate_pairs SET owner_org_id='absent' WHERE pair_id='SKT-0400'")
    before=logical_state(core.config.sqlite_path)
    for out in [core.query('runtime_status',{}),core.runtime_operation('health',{})]:
        assert out['status']=='DEGRADED' and out['foreign_key_findings'] and isinstance(out['foreign_key_findings'][0],list)
        json.dumps(out,allow_nan=False)
    assert logical_state(core.config.sqlite_path)==before


@pytest.mark.parametrize('kind',['query','runtime'])
def test_default_health_is_shallow_delegate(core,kind,monkeypatch):
    calls=[]
    def health(deep=False):calls.append(deep);return {'status':'HEALTHY','deep':deep}
    if kind=='query':monkeypatch.setattr(core,'health',health);name='runtime_status'
    else:monkeypatch.setattr(core.spine,'health_report',health);name='health'
    assert request_call(core,kind,name,{})['deep'] is False
    assert request_call(core,kind,name,{'deep':True})['deep'] is True
    assert calls==[False,True]


@pytest.mark.parametrize('name,params,target',[('checkpoint',{'metadata':{'custom':1},'create_snapshot':False},'create_checkpoint'),('rebuild_projections',{'require_clean_replay':False},'rebuild_projections'),('replay_check',{},'replay_check')])
def test_explicit_admin_parameter_delegation(core,name,params,target,monkeypatch):
    calls=[]
    def delegate(**kwargs):calls.append(kwargs);return {'actual':'native'}
    monkeypatch.setattr(core.spine,target,delegate)
    assert core.runtime_operation(name,params)=={'actual':'native'} and calls==[params]


@pytest.mark.parametrize('suffix',['','-wal','-shm','-journal'])
def test_recovery_export_never_targets_live_database(core,suffix):
    before=logical_state(core.config.sqlite_path)
    with pytest.raises(CoreRequestError,match='LIVE_DATABASE_TARGET'):core.runtime_operation('export_recovery',{'out_path':str(core.config.sqlite_path)+suffix})
    assert logical_state(core.config.sqlite_path)==before


def test_cli_recovery_export_restore_continuity(core,tmp_path):
    bundle=tmp_path/'cli.zip';target=tmp_path/'cli-restored.db'
    for kind,name,params in [('console','export_recovery',{'out_path':str(bundle)}),('module','restore_recovery',{'bundle_path':str(bundle),'target_db_path':str(target)})]:
        f=tmp_path/'r.json';f.write_text(json.dumps({'name':name,'params':params}))
        p=invoke(kind,tmp_path,'--db',str(core.config.sqlite_path),'runtime','--file',str(f));assert p.returncode==0 and not p.stderr
    c=SkateInventoryCore(CoreConfig(target)).initialize()
    assert c.query('list_inventory',{})==core.query('list_inventory',{}) and c.runtime_operation('replay_check',{})['semantic_match'];c.shutdown()


@pytest.mark.parametrize('command,name',[('query','list_inventory'),('runtime','verify_ledger')])
def test_new_cli_requires_existing_db(command,name,tmp_path):
    f=tmp_path/'r.json';f.write_text(json.dumps({'name':name,'params':{}}))
    p=invoke('module',tmp_path,'--db','new/absent.db',command,'--file',str(f))
    assert p.returncode==6 and json.loads(p.stderr)['error']['code']=='DATABASE_NOT_FOUND' and not (tmp_path/'new').exists()

from pathlib import Path
import importlib.util,json,os,sqlite3,subprocess,sys,uuid,zipfile,hashlib
from copy import deepcopy
import pytest
from skate_inventory_core import CoreConfig,SkateInventoryCore
from conftest import envelope
from logical_state import logical_state

ROOT=Path(__file__).resolve().parents[3]


@pytest.fixture
def core(tmp_path):
    c=SkateInventoryCore(CoreConfig(tmp_path/'core.db')).initialize()
    yield c
    c.shutdown()


@pytest.mark.parametrize('change',['schema','reference','receipt','idempotency'])
def test_logical_oracle_detects_changes(core,change):
    before=logical_state(core.config.sqlite_path)
    with core.db.connect() as conn:
        if change=='schema':conn.execute('CREATE TABLE negative_control(value TEXT)')
        elif change=='reference':conn.execute("INSERT INTO organizations VALUES ('ORG-TEST','Negative control','ASSET_OWNER',1,'2026-10-05T00:00:00Z')")
        elif change=='receipt':conn.execute("INSERT INTO command_receipts VALUES ('receipt','command','key','hash','scan_asset','ACCEPTED','time','{}')")
        else:conn.execute("INSERT INTO idempotency_records VALUES ('key','hash','command','{}','time')")
    after=logical_state(core.config.sqlite_path);assert after!=before
    assert ('schema' if change=='schema' else 'tables') in after
    if change=='schema':assert after['schema']!=before['schema']
    else:assert after['tables']!=before['tables']


def test_actual_metadata_wheel_and_stage_consistency():
    p=ROOT/'boot/validate_current_metadata.py';spec=importlib.util.spec_from_file_location('metadata_check',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=module.validate(ROOT);assert result['status']=='PASS' and result['resource_count']==25


def test_production_bytes_only_version_changed():
    # Prior source hashes materialized from the verified dev.6 provider ZIP.
    lock=json.loads((ROOT/'validation/evidence/C04/DEV6_PRODUCTION_LOCK.json').read_text())
    source=ROOT/'runtime/source/src'
    for rel,b in lock['files'].items():
        content=(source/rel).read_bytes()
        if rel=='skate_inventory_core/__init__.py':content=content.replace(b'0.3.1rc1',b'0.3.1.dev6')
        assert hashlib.sha256(content).hexdigest()==b


def test_one_canonical_C02_suite_without_duplicate_collection():
    assert not (ROOT/'runtime/source/tests/test_c02_semantic.py').exists()
    hist=ROOT/'validation/evidence/C04/historical/runtime/source/tests/test_core_cli.py';assert hist.is_file()
    bindings=json.loads((ROOT/'validation/evidence/C04/historical/HISTORICAL_BINDINGS.json').read_text())['bindings']
    b=next(x for x in bindings if x['input']=='runtime/source/tests/test_core_cli.py');assert hashlib.sha256(hist.read_bytes()).hexdigest()==b['sha256']
    canonical=(ROOT/'runtime/source/tests/test_core_cli.py').read_text()
    assert 'logical_state(db)' in canonical and 'db.read_bytes()' not in canonical
    # Malformed/empty source-file byte guards remain strong and active.
    assert "p.read_bytes()==b''" in canonical and "p.read_bytes()==b'not sqlite'" in canonical


def invoke(args,cwd,*,legacy=False,module=False):
    key='C04_LEGACY' if legacy else 'C04_CONSOLE'
    if os.environ.get(key):prefix=[os.environ[key]]
    else:prefix=[sys.executable,'-c','from '+('skate_registry' if legacy else 'skate_inventory_core')+'.cli import main; raise SystemExit(main())']
    if module:prefix=[sys.executable,'-m','skate_inventory_core']
    p=subprocess.run(prefix+list(args),cwd=cwd,capture_output=True,text=True,timeout=30)
    assert 'Traceback' not in p.stderr
    return p


def test_legacy_reference_administration_compatibility(core,tmp_path):
    before=logical_state(core.config.sqlite_path)
    p=invoke(['--db',str(core.config.sqlite_path),'add-org','ORG-COMPAT','Compatibility','ASSET_OWNER'],tmp_path,legacy=True)
    assert p.returncode==0 and json.loads(p.stdout)['org_id']=='ORG-COMPAT'
    after=logical_state(core.config.sqlite_path);assert after['tables']['organizations']!=before['tables']['organizations']
    assert after['tables']['asset_events']==before['tables']['asset_events'] and core.health(deep=True)['status']=='HEALTHY'


def test_complete_headless_workflow_and_recovery(tmp_path):
    db=tmp_path/'headless.db'
    assert invoke(['--db',str(db),'init'],tmp_path,module=True).returncode==0
    for args in [('add-org','ORG-OWNER','Owner','ASSET_OWNER'),('add-org','ORG-RINK','Rink','VENUE_OPERATOR'),('add-location','LOC-RINK','Rink','RINK'),('add-location','LOC-STORAGE','Storage','STORAGE'),('add-device','DEV-COUNTER','Counter','COUNTER_TABLET')]:
        assert invoke(['--db',str(db),*args],tmp_path,legacy=True).returncode==0
    c=SkateInventoryCore(CoreConfig(db)).initialize()
    def execute(name,payload,*,command=None,expected_code=0):
        cmd=command or envelope(name,payload);f=tmp_path/'command.json';f.write_text(json.dumps(cmd))
        out=invoke(['--db',str(db),'execute','--file',str(f)],tmp_path,module=(name=='scan_asset'))
        assert out.returncode==expected_code and not out.stderr
        return cmd,json.loads(out.stdout)['receipt']
    pair={'pair_id':'SKT-0900','owner_org_id':'ORG-OWNER','size_system':'US_MENS','size_value':'8','category':'HOCKEY','home_location_id':'LOC-RINK','current_location_id':'LOC-RINK','custodian_org_id':'ORG-OWNER'}
    execute('register_pair',{'pair':pair})
    for side in ['L','R']:execute('register_component',{'component':{'component_id':'SKT-0900-'+side,'pair_id':'SKT-0900','side':side,'label_identifier':'SKT-0900-'+side,'current_location_id':'LOC-RINK'}})
    execute('link_pair',{'pair_id':'SKT-0900','left_component_id':'SKT-0900-L','right_component_id':'SKT-0900-R'})
    execute('scan_asset',{'identifier':'SKT-0900-L'})
    execute('verify_inventory',{'pair_id':'SKT-0900','observed_component_ids':['SKT-0900-L','SKT-0900-R']})
    transfer,receipt=execute('transfer_location',{'pair_id':'SKT-0900','to_location_id':'LOC-STORAGE'})
    execute('replace_label',{'component_id':'SKT-0900-L','new_label_identifier':'SKT-0901-L'})
    execute('mark_component_missing',{'component_id':'SKT-0900-R'})
    attachment=tmp_path/'note.txt';attachment.write_text('local supporting evidence')
    evidence=c.runtime_operation('add_evidence',{'file_path':str(attachment),'related_event_id':receipt['event_ids'][0]})
    execute('record_correction',{'target_event_id':receipt['event_ids'][0],'correction_mode':'EVIDENCE_ADDENDUM','reason':'Record supporting note','evidence_refs':[evidence['attachment_id']]})
    before=logical_state(db)
    assert c.query('find_asset',{'identifier':'SKT-0900-L'})['active_label'] is False
    assert c.query('list_inventory',{})[0]['pair_id']=='SKT-0900'
    assert c.query('asset_history',{'pair_id':'SKT-0900'})[-1]['event_type']=='CORRECTION_RECORDED'
    assert c.query('runtime_status',{'deep':True})['status']=='HEALTHY'
    assert c.runtime_operation('verify_ledger',{})['ok'] and c.runtime_operation('replay_check',{})['semantic_match']
    assert c.runtime_operation('export_evidence',{})['attachments'][0]['attachment_id']==evidence['attachment_id']
    assert logical_state(db)==before
    c.runtime_operation('checkpoint',{'metadata':{'reason':'C04 end-to-end'}})
    assert c.runtime_operation('rebuild_projections',{})['semantic_match']
    bundle=tmp_path/'recovery.zip';target=tmp_path/'restored.db';c.runtime_operation('export_recovery',{'out_path':str(bundle)})
    c.runtime_operation('restore_recovery',{'bundle_path':str(bundle),'target_db_path':str(target)})
    restored=SkateInventoryCore(CoreConfig(target)).initialize();snap=logical_state(target)
    retry=restored.execute(transfer);assert retry['status']=='DUPLICATE' and retry['event_ids']==receipt['event_ids']
    changed=deepcopy(transfer);changed['command_id']=str(uuid.uuid4());changed['payload']['to_location_id']='LOC-RINK'
    assert restored.execute(changed)['error']['code']=='IDEMPOTENCY_CONFLICT' and logical_state(target)==snap
    assert restored.runtime_operation('health',{'deep':True})['status']=='HEALTHY'
    restored.shutdown();c.shutdown()

from __future__ import annotations

import json
import sqlite3

from conftest import envelope
from skate_registry.processor import CommandProcessor
from skate_registry.spine import RuntimeSpine


def register_complete_pair(db, pair_id='SKT-0300'):
    p=CommandProcessor(db)
    assert p.process(envelope('register_pair',{'pair':{'pair_id':pair_id,'owner_org_id':'ORG-OWNER','size_system':'US_MENS','size_value':'8','category':'HOCKEY','home_location_id':'LOC-RINK','current_location_id':'LOC-RINK','custodian_org_id':'ORG-OWNER'}}))['status']=='ACCEPTED'
    assert p.process(envelope('register_component',{'component':{'component_id':pair_id+'-L','pair_id':pair_id,'side':'L','label_identifier':pair_id+'-L','current_location_id':'LOC-RINK'}}))['status']=='ACCEPTED'
    assert p.process(envelope('register_component',{'component':{'component_id':pair_id+'-R','pair_id':pair_id,'side':'R','label_identifier':pair_id+'-R','current_location_id':'LOC-RINK'}}))['status']=='ACCEPTED'
    assert p.process(envelope('link_pair',{'pair_id':pair_id,'left_component_id':pair_id+'-L','right_component_id':pair_id+'-R'}))['status']=='ACCEPTED'
    return p


def test_replay_check_matches_live_projection(runtime):
    p=register_complete_pair(runtime)
    assert p.process(envelope('transfer_location',{'pair_id':'SKT-0300','to_location_id':'LOC-STORAGE'}))['status']=='ACCEPTED'
    assert p.process(envelope('transfer_custody',{'pair_id':'SKT-0300','to_custodian_org_id':'ORG-RINK'}))['status']=='ACCEPTED'
    report=RuntimeSpine(runtime).replay_check()
    assert report['ledger_ok'] is True
    assert report['semantic_match'] is True
    assert report['unsupported_event_types']==[]


def test_checkpoint_and_snapshot(runtime):
    register_complete_pair(runtime)
    spine=RuntimeSpine(runtime)
    cp=spine.create_checkpoint({'reason':'test'})
    assert cp['event_count']==4
    assert cp['last_event_hash']
    assert cp['snapshot_id']
    with runtime.connect() as conn:
        row=conn.execute('SELECT payload_sha256 FROM projection_snapshots WHERE snapshot_id=?',(cp['snapshot_id'],)).fetchone()
        assert row is not None and len(row['payload_sha256'])==64


def test_evidence_and_append_only_correction(runtime,tmp_path):
    p=register_complete_pair(runtime)
    with runtime.connect() as conn:
        target=conn.execute("SELECT event_id FROM asset_events WHERE event_type='PAIR_LINKED' LIMIT 1").fetchone()[0]
    f=tmp_path/'photo.txt'; f.write_text('evidence bytes',encoding='utf-8')
    att=RuntimeSpine(runtime).add_evidence(f,related_event_id=target,media_type='text/plain')
    r=p.process(envelope('record_correction',{'target_event_id':target,'correction_mode':'EVIDENCE_ADDENDUM','reason':'Attach corroborating evidence','evidence_refs':[att['attachment_id']]}))
    assert r['status']=='ACCEPTED'
    with runtime.connect() as conn:
        link=conn.execute('SELECT * FROM correction_links WHERE correction_event_id=?',(r['event_ids'][0],)).fetchone()
        assert link['target_event_id']==target
        original=conn.execute('SELECT payload_json FROM asset_events WHERE event_id=?',(target,)).fetchone()[0]
        assert json.loads(original)['availability_state']=='AVAILABLE'


def test_health_detects_bad_insert(runtime):
    register_complete_pair(runtime)
    with runtime.connect() as conn:
        last=conn.execute('SELECT * FROM asset_events ORDER BY rowid DESC LIMIT 1').fetchone()
        conn.execute("""INSERT INTO asset_events(event_id,schema_version,event_type,occurred_at,recorded_at,actor_id,actor_role,location_id,pair_id,component_id,rental_session_id,command_id,reason_code,notes,evidence_refs_json,device_id,offline_sequence,payload_json,event_hash,previous_event_hash)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     ('EVT-TAMPER','0.1.0','CORRECTION_RECORDED',last['occurred_at'],last['recorded_at'],'tester','OWNER_ADMIN','LOC-RINK','SKT-0300',None,None,None,None,None,'[]','DEV-COUNTER',0,'{}','0'*64,'f'*64))
    report=RuntimeSpine(runtime).health_report()
    assert report['status']=='DEGRADED'
    assert report['ledger']['ok'] is False


def test_rebuild_repairs_projection_drift(runtime):
    p=register_complete_pair(runtime)
    assert p.process(envelope('transfer_location',{'pair_id':'SKT-0300','to_location_id':'LOC-STORAGE'}))['status']=='ACCEPTED'
    with runtime.connect() as conn:
        conn.execute("UPDATE skate_pairs SET current_location_id='LOC-RINK' WHERE pair_id='SKT-0300'")
    before=RuntimeSpine(runtime).replay_check()
    assert before['semantic_match'] is False
    out=RuntimeSpine(runtime).rebuild_projections()
    assert out['semantic_match'] is True
    with runtime.connect() as conn:
        assert conn.execute("SELECT current_location_id FROM skate_pairs WHERE pair_id='SKT-0300'").fetchone()[0]=='LOC-STORAGE'


def test_recovery_bundle_roundtrip(runtime,tmp_path):
    p=register_complete_pair(runtime)
    assert p.process(envelope('transfer_custody',{'pair_id':'SKT-0300','to_custodian_org_id':'ORG-RINK'}))['status']=='ACCEPTED'
    spine=RuntimeSpine(runtime)
    bundle=tmp_path/'recovery.zip'
    exported=spine.export_recovery_bundle(bundle)
    assert exported['event_count']==5
    restored=tmp_path/'restored.sqlite3'
    out=RuntimeSpine.restore_recovery_bundle(bundle,restored)
    assert out['status']=='HEALTHY'
    from skate_registry.db import Database
    restored_spine=RuntimeSpine(Database(restored))
    assert restored_spine.replay_check()['semantic_match'] is True
    with sqlite3.connect(restored) as conn:
        assert conn.execute("SELECT custodian_org_id FROM skate_pairs WHERE pair_id='SKT-0300'").fetchone()[0]=='ORG-RINK'

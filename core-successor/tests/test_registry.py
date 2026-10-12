from __future__ import annotations

import sqlite3
from skate_registry.contracts import ContractStore
from skate_registry.events import EventLedger
from skate_registry.processor import CommandProcessor
from conftest import envelope


def register_complete_pair(db,pair_id='SKT-0001'):
    p=CommandProcessor(db)
    r=p.process(envelope('register_pair',{'pair':{'pair_id':pair_id,'owner_org_id':'ORG-OWNER','size_system':'US_MENS','size_value':'8','category':'HOCKEY','home_location_id':'LOC-RINK','current_location_id':'LOC-RINK','custodian_org_id':'ORG-OWNER'}})); assert r['status']=='ACCEPTED',r
    r=p.process(envelope('register_component',{'component':{'component_id':pair_id+'-L','pair_id':pair_id,'side':'L','label_identifier':pair_id+'-L','current_location_id':'LOC-RINK'}})); assert r['status']=='ACCEPTED',r
    r=p.process(envelope('register_component',{'component':{'component_id':pair_id+'-R','pair_id':pair_id,'side':'R','label_identifier':pair_id+'-R','current_location_id':'LOC-RINK'}})); assert r['status']=='ACCEPTED',r
    r=p.process(envelope('link_pair',{'pair_id':pair_id,'left_component_id':pair_id+'-L','right_component_id':pair_id+'-R'})); assert r['status']=='ACCEPTED',r
    return p


def test_pair_starts_incomplete_then_becomes_available(runtime):
    p=CommandProcessor(runtime)
    r=p.process(envelope('register_pair',{'pair':{'pair_id':'SKT-0001','owner_org_id':'ORG-OWNER','size_system':'US_MENS','size_value':'8','category':'HOCKEY','home_location_id':'LOC-RINK','current_location_id':'LOC-RINK','custodian_org_id':'ORG-OWNER'}}))
    assert r['status']=='ACCEPTED'; assert r['result']['pair']['availability_state']=='MISSING_COMPONENT'
    p.process(envelope('register_component',{'component':{'component_id':'SKT-0001-L','pair_id':'SKT-0001','side':'L','label_identifier':'SKT-0001-L','current_location_id':'LOC-RINK'}}))
    p.process(envelope('register_component',{'component':{'component_id':'SKT-0001-R','pair_id':'SKT-0001','side':'R','label_identifier':'SKT-0001-R','current_location_id':'LOC-RINK'}}))
    r=p.process(envelope('link_pair',{'pair_id':'SKT-0001','left_component_id':'SKT-0001-L','right_component_id':'SKT-0001-R'}))
    assert r['result']['pair']['availability_state']=='AVAILABLE'


def test_scan_pair_and_component(runtime):
    p=register_complete_pair(runtime)
    assert p.process(envelope('scan_asset',{'identifier':'SKT-0001'}))['result']['resolved_type']=='PAIR'
    out=p.process(envelope('scan_asset',{'identifier':'SKT-0001-L'}))
    assert out['result']['resolved_type']=='COMPONENT_LABEL'; assert out['result']['pair']['pair_id']=='SKT-0001'


def test_location_and_custody_do_not_change_owner(runtime):
    p=register_complete_pair(runtime)
    before=p.process(envelope('scan_asset',{'identifier':'SKT-0001'}))['result']['pair']
    p.process(envelope('transfer_location',{'pair_id':'SKT-0001','to_location_id':'LOC-STORAGE'}))
    p.process(envelope('transfer_custody',{'pair_id':'SKT-0001','to_custodian_org_id':'ORG-RINK'}))
    after=p.process(envelope('scan_asset',{'identifier':'SKT-0001'}))['result']['pair']
    assert before['owner_org_id']=='ORG-OWNER'==after['owner_org_id']
    assert after['current_location_id']=='LOC-STORAGE'; assert after['custodian_org_id']=='ORG-RINK'


def test_ownership_requires_owner_admin(runtime):
    p=register_complete_pair(runtime)
    r=p.process(envelope('transfer_ownership',{'pair_id':'SKT-0001','to_owner_org_id':'ORG-OTHER'},role='RINK_MANAGER'))
    assert r['status']=='REJECTED'; assert r['error']['code'] in {'ROLE_FORBIDDEN','OWNERSHIP_AUTH_REQUIRED'}
    r=p.process(envelope('transfer_ownership',{'pair_id':'SKT-0001','to_owner_org_id':'ORG-OTHER'},role='OWNER_ADMIN'))
    assert r['status']=='ACCEPTED'; assert r['result']['pair']['owner_org_id']=='ORG-OTHER'


def test_inventory_verification(runtime):
    p=register_complete_pair(runtime)
    r=p.process(envelope('verify_inventory',{'pair_id':'SKT-0001','observed_component_ids':['SKT-0001-L','SKT-0001-R']},role='RINK_MANAGER'))
    assert r['status']=='ACCEPTED'; assert r['result']['pair']['last_inventory_verified_at']


def test_idempotency_duplicate_and_conflict(runtime):
    p=CommandProcessor(runtime); key='same-key-123'
    payload={'pair':{'pair_id':'SKT-0001','owner_org_id':'ORG-OWNER','size_system':'US_MENS','size_value':'8','category':'HOCKEY','home_location_id':'LOC-RINK','current_location_id':'LOC-RINK','custodian_org_id':'ORG-OWNER'}}
    first=p.process(envelope('register_pair',payload,key=key)); assert first['status']=='ACCEPTED'
    second=p.process(envelope('register_pair',payload,key=key)); assert second['status']=='DUPLICATE'; assert second['event_ids']==first['event_ids']
    altered={'pair':{**payload['pair'],'size_value':'9'}}
    third=p.process(envelope('register_pair',altered,key=key)); assert third['status']=='CONFLICT'; assert third['error']['code']=='IDEMPOTENCY_CONFLICT'


def test_version_conflict(runtime):
    p=register_complete_pair(runtime)
    pair=p.process(envelope('scan_asset',{'identifier':'SKT-0001'}))['result']['pair']
    r=p.process(envelope('transfer_location',{'pair_id':'SKT-0001','to_location_id':'LOC-STORAGE'},expected=pair['version']-1))
    assert r['status']=='CONFLICT'; assert r['error']['code']=='VERSION_CONFLICT'


def test_label_replacement_preserves_old_resolution(runtime):
    p=register_complete_pair(runtime)
    r=p.process(envelope('replace_label',{'component_id':'SKT-0001-L','new_label_identifier':'SKT-000001-L'}))
    assert r['status']=='ACCEPTED'
    old=p.process(envelope('scan_asset',{'identifier':'SKT-0001-L'}))['result']; assert old['active_label'] is False
    new=p.process(envelope('scan_asset',{'identifier':'SKT-000001-L'}))['result']; assert new['active_label'] is True


def test_mark_component_missing_blocks_pair(runtime):
    p=register_complete_pair(runtime)
    r=p.process(envelope('mark_component_missing',{'component_id':'SKT-0001-R','reason_code':'NOT_FOUND'}))
    assert r['status']=='ACCEPTED'; assert r['result']['pair']['availability_state']=='MISSING_COMPONENT'


def test_event_chain_and_append_only(runtime):
    register_complete_pair(runtime)
    with runtime.connect() as conn:
        ok,bad=EventLedger(ContractStore()).verify_chain(conn); assert ok and bad is None
        event_id=conn.execute('SELECT event_id FROM asset_events LIMIT 1').fetchone()[0]
        try:
            conn.execute('DELETE FROM asset_events WHERE event_id=?',(event_id,))
        except sqlite3.DatabaseError:
            pass
        else:
            raise AssertionError('event ledger allowed deletion')


def test_same_command_id_replay_is_duplicate(runtime):
    p=CommandProcessor(runtime); cid='22222222-2222-4222-8222-222222222222'; key='replay-key-123'
    payload={'pair':{'pair_id':'SKT-0200','owner_org_id':'ORG-OWNER','size_system':'US_MENS','size_value':'10','category':'HOCKEY','home_location_id':'LOC-RINK','current_location_id':'LOC-RINK','custodian_org_id':'ORG-OWNER'}}
    first=p.process(envelope('register_pair',payload,key=key,command_id=cid)); assert first['status']=='ACCEPTED'
    second=p.process(envelope('register_pair',payload,key=key,command_id=cid)); assert second['status']=='DUPLICATE'; assert second['event_ids']==first['event_ids']

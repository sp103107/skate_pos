# Canonical C04 portable C02 acceptance; exact prior raw suite is historical evidence.
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from copy import deepcopy

import pytest
from logical_state import logical_state
from skate_inventory_core import CoreConfig, SkateInventoryCore
from skate_inventory_core import cli
from conftest import envelope
from test_core_composition import seed, register


def invoke(kind, cwd, *args):
    # Source run uses shared main directly; installed run uses actual console script.
    console = os.environ.get('C02_CONSOLE')
    prefix = [console] if console else [sys.executable, '-c', 'from skate_inventory_core.cli import main; raise SystemExit(main())']
    if kind == 'module': prefix = [sys.executable, '-m', 'skate_inventory_core']
    p = subprocess.run(prefix+list(args), cwd=cwd, capture_output=True, text=True, timeout=20)
    assert 'Traceback' not in p.stderr
    return p


def value(p, code=0):
    assert p.returncode == code, (p.stdout,p.stderr)
    assert p.stderr == ''
    lines = p.stdout.splitlines(); assert len(lines)==1
    return json.loads(lines[0])


def failure(p, code, reason):
    assert p.returncode==code and p.stdout==''
    d=json.loads(p.stderr); assert d['error']['code']==reason
    assert len(p.stderr.splitlines())==1
    return d


@pytest.fixture
def db(tmp_path):
    path=tmp_path/'core.db'; c=SkateInventoryCore(CoreConfig(path)).initialize(); seed(c); register(c); c.shutdown()
    return path


@pytest.mark.parametrize('kind',['console','module'])
@pytest.mark.parametrize('args',[[],['run'],['init']])
def test_default_boot_and_no_seed(kind,args,tmp_path):
    result=value(invoke(kind,tmp_path,*args))
    assert result['db_path']==str(tmp_path/'data/skate_inventory.db')
    assert result['report']['core_state']=='READY' and result['report']['shutdown']
    if result['command']=='run':
        assert result['report']['ready'] and result['report']['health']['status']=='HEALTHY'
        assert result['report']['components']['shared_database'] and result['report']['components']['shared_contracts']
    with sqlite3.connect(result['db_path']) as conn:
        for table in ['organizations','locations','devices','skate_pairs','asset_events']:
            assert conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]==0


@pytest.mark.parametrize('kind',['console','module'])
def test_repeat_init_reopen_and_real_health(kind,db,tmp_path):
    before=logical_state(db)
    for command in ['init','init','run','health']:
        d=value(invoke(kind,tmp_path,'--db',str(db),command))
        assert d['db_path']==str(db)
        if command=='health': assert d['report']['status']=='HEALTHY' and d['report']['ledger']['event_count']>0
    assert logical_state(db)==before


@pytest.mark.parametrize('kind',['console','module'])
@pytest.mark.parametrize('command',['health','execute'])
def test_missing_database_no_writes(kind,command,tmp_path):
    f=tmp_path/'cmd.json'; f.write_text('{}')
    args=['--db','missing/nested.db',command]+(['--file',str(f)] if command=='execute' else [])
    failure(invoke(kind,tmp_path,*args),6,'DATABASE_NOT_FOUND')
    assert not (tmp_path/'missing').exists()


@pytest.mark.parametrize('flag',['--help','--version'])
def test_help_version_parity_without_side_effects(flag,tmp_path):
    a=invoke('console',tmp_path,flag); b=invoke('module',tmp_path,flag)
    assert a.returncode==b.returncode==0 and a.stdout==b.stdout and a.stderr==b.stderr==''
    assert list(tmp_path.iterdir())==[]


@pytest.mark.parametrize('args',[['oops'],['execute'],['--db',':memory:','run'],['--db','file:x','run'],['--db','','run'],['--bogus'],['health','--db','x']])
def test_arguments_fail_before_boot(args,tmp_path):
    a=invoke('console',tmp_path,*args); b=invoke('module',tmp_path,*args)
    assert a.returncode==b.returncode==2 and a.stdout==b.stdout=='' and a.stderr==b.stderr
    assert list(tmp_path.iterdir())==[]


@pytest.mark.parametrize('content',['{','[]','{} {}','{"x":1,"x":2}','{"x":NaN}','{"x":1e400}','\udcff'])
def test_json_failure_preserves_database(content,db,tmp_path):
    f=tmp_path/'cmd.json'; f.write_bytes(content.encode('utf-8',errors='surrogateescape'))
    before=logical_state(db)
    for kind in ['console','module']:
        failure(invoke(kind,tmp_path,'--db',str(db),'execute','--file',str(f)),2,'INVALID_JSON_ENVELOPE')
    assert logical_state(db)==before


def test_missing_input_and_unusable_paths(db,tmp_path):
    before=logical_state(db)
    failure(invoke('module',tmp_path,'--db',str(db),'execute','--file','absent'),6,'IO_FAILURE')
    for bad in [str(tmp_path),str(db/'nested.db')]:
        failure(invoke('module',tmp_path,'--db',bad,'init'),2,'INVALID_DATABASE_PATH')
    assert logical_state(db)==before


def test_unsupported_database_never_repaired(tmp_path):
    p=tmp_path/'empty.db'; p.write_bytes(b'')
    for command in ['init','run','health','execute']:
        f=tmp_path/'cmd.json';f.write_text('{}')
        args=['--db',str(p),command]+(['--file',str(f)] if command=='execute' else [])
        failure(invoke('module',tmp_path,*args),7,'DATABASE_SCHEMA_UNSUPPORTED'); assert p.read_bytes()==b''
    p.write_bytes(b'not sqlite')
    failure(invoke('console',tmp_path,'--db',str(p),'health'),6,'IO_FAILURE');assert p.read_bytes()==b'not sqlite'


def test_health_console_module_exact_parity(db,tmp_path):
    a=invoke('console',tmp_path,'--db',str(db),'health'); b=invoke('module',tmp_path,'--db',str(db),'health')
    assert value(a)==value(b)


def test_execute_original_receipts_reject_duplicate_conflict(db,tmp_path):
    f=tmp_path/'cmd.json'
    cmd=envelope('transfer_location',{'pair_id':'SKT-0400','to_location_id':'LOC-STORAGE'})
    f.write_text(json.dumps(cmd)); accepted=value(invoke('console',tmp_path,'--db',str(db),'execute','--file',str(f)))['receipt']
    assert accepted['status']=='ACCEPTED'
    duplicate=value(invoke('module',tmp_path,'--db',str(db),'execute','--file',str(f)))['receipt']
    assert duplicate['status']=='DUPLICATE' and duplicate['event_ids']==accepted['event_ids'] and duplicate['result']==accepted['result']
    before=logical_state(db)
    changed=deepcopy(cmd);changed['payload']['to_location_id']='LOC-RINK';f.write_text(json.dumps(changed))
    assert value(invoke('module',tmp_path,'--db',str(db),'execute','--file',str(f)),4)['receipt']['error']['code']=='IDEMPOTENCY_CONFLICT'
    denied=envelope('transfer_location',{'pair_id':'SKT-0400','to_location_id':'LOC-RINK'},role='CUSTOMER');f.write_text(json.dumps(denied))
    assert value(invoke('console',tmp_path,'--db',str(db),'execute','--file',str(f)),3)['receipt']['error']['code']=='ROLE_FORBIDDEN'
    f.write_text('{}')
    assert value(invoke('module',tmp_path,'--db',str(db),'execute','--file',str(f)),3)['receipt']['status']=='REJECTED'
    assert logical_state(db)==before


@pytest.mark.parametrize('kind',['console','module'])
@pytest.mark.parametrize('command',['run','health'])
def test_real_degraded_health_nonzero(kind,command,db,tmp_path):
    with sqlite3.connect(db) as conn:conn.execute("UPDATE skate_pairs SET size_value='9' WHERE pair_id='SKT-0400'")
    before=logical_state(db);d=value(invoke(kind,tmp_path,'--db',str(db),command),5)
    health=d['report']['health'] if command=='run' else d['report']
    assert health['status']=='DEGRADED' and not health['replay']['semantic_match']
    if command=='run': assert not d['report']['ready'] and d['report']['shutdown']
    assert logical_state(db)==before


@pytest.mark.parametrize('stage',['initialize','health','execute'])
def test_shutdown_on_runtime_failure(stage,db,tmp_path,monkeypatch,capsys):
    seen=[]
    class Fault(SkateInventoryCore):
        def initialize(self):
            seen.append(self)
            if stage=='initialize':raise RuntimeError('sensitive details')
            return super().initialize()
        def health(self,deep=False):raise RuntimeError('sensitive details')
        def execute(self,envelope):raise RuntimeError('sensitive details')
    monkeypatch.setattr(cli,'SkateInventoryCore',Fault)
    f=tmp_path/'cmd.json';f.write_text('{}')
    args=['--db',str(db),'execute','--file',str(f)] if stage=='execute' else ['--db',str(db),'run']
    assert cli.main(args)==7
    out=capsys.readouterr();assert out.out=='' and 'sensitive' not in out.err
    assert json.loads(out.err)['error']['code']=='RUNTIME_FAILURE' and seen[0].state=='SHUTDOWN'


def test_execute_object_and_receipt_unchanged(db,tmp_path,monkeypatch,capsys):
    received=[]; original=SkateInventoryCore.execute
    def execute(self,obj):
        received.append(obj);r=original(self,obj);received.append(r);return r
    monkeypatch.setattr(SkateInventoryCore,'execute',execute)
    cmd=envelope('scan_asset',{'identifier':'SKT-0400-L'});f=tmp_path/'cmd.json';f.write_text(json.dumps(cmd))
    assert cli.main(['--db',str(db),'execute','--file',str(f)])==0
    assert received[0]==cmd and json.loads(capsys.readouterr().out)['receipt']==received[1]

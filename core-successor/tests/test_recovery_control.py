from __future__ import annotations

import copy
import hashlib
import json
import zipfile

import pytest

from conftest import envelope
from test_r02_spine import register_complete_pair
from skate_registry.db import Database
from skate_registry.errors import RegistryError
from skate_registry.processor import CommandProcessor
from skate_registry.spine import RuntimeSpine
from skate_registry.util import sha256_json


def controls(db):
    with db.connect() as c:
        return {t: [dict(r) for r in c.execute(f'SELECT * FROM {t} ORDER BY rowid')]
                for t in ('command_receipts', 'idempotency_records')}


def prepared(db):
    p = register_complete_pair(db)
    cmd = envelope('transfer_location', {'pair_id': 'SKT-0300', 'to_location_id': 'LOC-STORAGE'})
    accepted = p.process(cmd)
    assert accepted['status'] == 'ACCEPTED'
    # A second command ID for the same logical key must also survive recovery.
    alias = copy.deepcopy(cmd)
    alias['command_id'] = '8f74df66-8301-46b9-b676-067875b22344'
    assert p.process(alias)['status'] == 'DUPLICATE'
    # Include accepted no-event query commands in the recovery boundary.
    assert p.process(envelope('scan_asset', {'identifier': 'SKT-0300-L'}))['status'] == 'ACCEPTED'
    return p, cmd, alias, accepted


def test_retry_control_survives_restore(runtime, tmp_path):
    p, cmd, alias, accepted = prepared(runtime)
    before = controls(runtime)
    assert p.process(cmd)['status'] == 'DUPLICATE'
    bundle = tmp_path / 'recovery.zip'
    RuntimeSpine(runtime).export_recovery_bundle(bundle)
    target = tmp_path / 'restored.db'
    RuntimeSpine.restore_recovery_bundle(bundle, target)
    db = Database(target)
    spine = RuntimeSpine(db)
    state = spine.projection_snapshot()
    count = spine.health_report()['ledger']['event_count']
    for retry in (cmd, alias):
        got = CommandProcessor(db).process(retry)
        assert got['status'] == 'DUPLICATE'
        assert got['event_ids'] == accepted['event_ids']
        assert got['result'] == accepted['result']
    assert controls(db) == before
    assert spine.health_report()['ledger']['event_count'] == count
    assert spine.projection_snapshot() == state
    changed = copy.deepcopy(cmd)
    changed['command_id'] = '8f74df66-8301-46b9-b676-067875b22345'
    changed['payload']['to_location_id'] = 'LOC-RINK'
    assert p.process(changed)['error']['code'] == 'IDEMPOTENCY_CONFLICT'
    assert CommandProcessor(db).process(changed)['error']['code'] == 'IDEMPOTENCY_CONFLICT'
    assert spine.projection_snapshot() == state
    assert spine.replay_check()['semantic_match']


def rewrite_bundle(source, dest, mutate, rehash=True):
    with zipfile.ZipFile(source) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    mutate(entries)
    if rehash:
        entries['MANIFEST.sha256'] = ''.join(
            f'{hashlib.sha256(v).hexdigest()}  {n}\n'
            for n, v in sorted(entries.items()) if n != 'MANIFEST.sha256').encode()
    with zipfile.ZipFile(dest, 'w') as z:
        for n, v in entries.items():
            z.writestr(n, v)


@pytest.mark.parametrize('damage', [
    'legacy', 'missing_controls', 'bad_hash', 'duplicate_member', 'path_traversal',
    'bad_meta', 'bad_control_link', 'missing_receipt', 'bad_projection', 'bad_ledger',
    'malformed_json', 'missing_manifest_entry', 'unlinked_event', 'bad_receipt_metadata',
])
def test_reject_invalid_without_target_mutation(runtime, tmp_path, damage):
    prepared(runtime)
    bundle = tmp_path / 'good.zip'
    RuntimeSpine(runtime).export_recovery_bundle(bundle)
    bad = tmp_path / 'bad.zip'
    def mutate(entries):
        if damage == 'legacy':
            meta = json.loads(entries['bundle.json']); meta['format_version'] = '0.2.0'
            entries['bundle.json'] = json.dumps(meta).encode()
            entries.pop('controls.json', None)
        elif damage == 'missing_controls':
            entries.pop('controls.json')
        elif damage == 'bad_hash':
            entries['controls.json'] += b' '
        elif damage == 'path_traversal':
            entries['../escape'] = b'no'
        elif damage == 'bad_meta':
            meta = json.loads(entries['bundle.json']); meta['event_count'] += 1
            entries['bundle.json'] = json.dumps(meta).encode()
        elif damage in ('bad_control_link', 'missing_receipt', 'bad_receipt_metadata'):
            c = json.loads(entries['controls.json'])
            if damage == 'bad_control_link': c['idempotency_records'][0]['original_command_id'] = 'missing'
            elif damage == 'missing_receipt': c['command_receipts'] = c['command_receipts'][1:]
            else: c['command_receipts'][0]['command_name'] = 'unknown'
            entries['controls.json'] = json.dumps(c).encode()
        elif damage == 'bad_projection':
            p = json.loads(entries['projection.json']); p['pairs'][0]['current_location_id'] = 'LOC-RINK'
            entries['projection.json'] = json.dumps(p).encode()
        elif damage == 'bad_ledger':
            rows = entries['ledger.jsonl'].decode().splitlines(); e = json.loads(rows[0]); e['event_hash'] = '0' * 64
            rows[0] = json.dumps(e); entries['ledger.jsonl'] = ('\n'.join(rows)+'\n').encode()
        elif damage == 'unlinked_event':
            c = json.loads(entries['controls.json'])
            r = next(r for r in c['command_receipts'] if r['status'] == 'ACCEPTED')
            receipt = json.loads(r['receipt_json']); receipt['event_ids'] = []
            r['receipt_json'] = json.dumps(receipt)
            entries['controls.json'] = json.dumps(c).encode()
        elif damage == 'malformed_json': entries['controls.json'] = b'{broken'
        # Re-bind checksums/digests for structural attacks so restore must check semantics.
        if damage in ('bad_control_link', 'missing_receipt', 'unlinked_event', 'bad_receipt_metadata', 'bad_projection'):
            meta = json.loads(entries['bundle.json'])
            c = json.loads(entries['controls.json'])
            meta.update(control_digest=sha256_json(c), receipt_count=len(c['command_receipts']),
                        idempotency_count=len(c['idempotency_records']),
                        projection_digest=sha256_json(json.loads(entries['projection.json'])))
            entries['bundle.json'] = json.dumps(meta).encode()
    rewrite_bundle(bundle, bad, mutate, rehash=damage != 'bad_hash')
    if damage == 'duplicate_member':
        with zipfile.ZipFile(bad, 'a') as z: z.writestr('bundle.json', b'{}')
    if damage == 'missing_manifest_entry':
        rewrite_bundle(bad, tmp_path/'other.zip', lambda e: e.__setitem__('MANIFEST.sha256', b''), rehash=False)
        bad = tmp_path/'other.zip'
    target = tmp_path / 'new-dir' / 'target.db'
    with pytest.raises(RegistryError): RuntimeSpine.restore_recovery_bundle(bad, target)
    assert not target.exists()
    assert not target.parent.exists()
    assert not (tmp_path / 'escape').exists()


def test_export_boundary_and_rebuild(runtime, tmp_path):
    p, cmd, _, _ = prepared(runtime)
    spine = RuntimeSpine(runtime)
    old = spine.create_checkpoint({'reason': 'older'})
    assert p.process(envelope('transfer_custody', {'pair_id':'SKT-0300', 'to_custodian_org_id':'ORG-RINK'}))['status'] == 'ACCEPTED'
    before = controls(runtime)
    out = spine.export_recovery_bundle(tmp_path/'bundle.zip')
    assert out['event_count'] == old['event_count'] + 1
    target = tmp_path/'restored.db'
    RuntimeSpine.restore_recovery_bundle(tmp_path/'bundle.zip', target)
    restored = RuntimeSpine(Database(target))
    assert restored.replay_check()['semantic_match']
    assert restored.rebuild_projections()['semantic_match']
    assert controls(Database(target)) == before


def test_refuse_existing_target(runtime, tmp_path):
    prepared(runtime)
    RuntimeSpine(runtime).export_recovery_bundle(tmp_path/'bundle.zip')
    target = tmp_path/'exists.db'; target.write_bytes(b'keep')
    with pytest.raises(FileExistsError): RuntimeSpine.restore_recovery_bundle(tmp_path/'bundle.zip', target)
    assert target.read_bytes() == b'keep'


def test_checkpoint_binds_control_cutoff(runtime):
    prepared(runtime)
    cp = RuntimeSpine(runtime).create_checkpoint({'reason': 'control-cutoff'})
    assert cp['receipt_count'] == 7
    assert cp['idempotency_count'] == 6
    assert cp['control_digest'] == sha256_json(controls(runtime))
    with runtime.connect() as c:
        meta = json.loads(c.execute('SELECT metadata_json FROM ledger_checkpoints WHERE checkpoint_id=?',
                                   (cp['checkpoint_id'],)).fetchone()[0])
    assert meta['control_digest'] == cp['control_digest']


def test_export_is_one_locked_transaction(runtime, tmp_path, monkeypatch):
    import sqlite3
    prepared(runtime)
    spine = RuntimeSpine(runtime)
    original = spine.reference_snapshot
    def concurrent_attempt(conn=None):
        other = sqlite3.connect(runtime.path, timeout=0)
        try:
            with pytest.raises(sqlite3.OperationalError):
                other.execute("UPDATE locations SET name='concurrent' WHERE location_id='LOC-RINK'")
        finally:
            other.close()
        return original(conn)
    monkeypatch.setattr(spine, 'reference_snapshot', concurrent_attempt)
    spine.export_recovery_bundle(tmp_path/'bundle.zip')
    with runtime.connect() as c:
        assert c.execute("SELECT name FROM locations WHERE location_id='LOC-RINK'").fetchone()[0] == 'Rink'


def test_empty_cutoff_recovery(runtime, tmp_path):
    RuntimeSpine(runtime).export_recovery_bundle(tmp_path/'bundle.zip')
    out = RuntimeSpine.restore_recovery_bundle(tmp_path/'bundle.zip', tmp_path/'restored.db')
    assert out['event_count'] == 0
    assert controls(Database(tmp_path/'restored.db')) == {'command_receipts': [], 'idempotency_records': []}

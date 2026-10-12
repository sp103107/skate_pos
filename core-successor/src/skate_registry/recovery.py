"""Consistent full-cutoff recovery, including persisted command control state."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from .db import Database
from .errors import RegistryError
from .util import sha256_json, utc_now

FORMAT_VERSION = '0.2.1.dev3'
MEMBERS = {'bundle.json', 'references.json', 'projection.json', 'ledger.jsonl',
           'evidence.json', 'corrections.json', 'controls.json', 'MANIFEST.sha256'}


def invalid(message):
    raise RegistryError('LEDGER_INTEGRITY_ERROR', message)


def control_snapshot(conn):
    # Preserve insertion order as well as the original JSON bytes/linkage.
    return {table: [dict(row) for row in conn.execute(f'SELECT * FROM {table} ORDER BY rowid')]
            for table in ('command_receipts', 'idempotency_records')}


def validate_controls(conn, contracts):
    from .service import SUPPORTED_COMMANDS
    snap = control_snapshot(conn)
    receipts = {}
    by_key = {r['idempotency_key']: r for r in snap['idempotency_records']}
    events = {r['event_id']: dict(r) for r in conn.execute('SELECT * FROM asset_events ORDER BY rowid')}
    claimed = set()
    for row in snap['command_receipts']:
        receipt = json.loads(row['receipt_json'])
        contracts.validate('command_receipt.schema.json', receipt)
        if (receipt['receipt_id'] != row['receipt_id'] or receipt['command_id'] != row['command_id']
                or receipt['status'] != row['status'] or receipt['recorded_at'] != row['recorded_at']
                or row['command_name'] not in SUPPORTED_COMMANDS
                or row['status'] not in ('ACCEPTED', 'DUPLICATE')
                or len(row['logical_hash']) != 64
                or any(c not in '0123456789abcdef' for c in row['logical_hash'])):
            invalid('Receipt row metadata is inconsistent')
        if len(receipt['event_ids']) != len(set(receipt['event_ids'])):
            invalid('Receipt contains duplicate event links')
        for eid in receipt['event_ids']:
            if eid not in events:
                invalid('Receipt references an absent ledger event')
            if row['status'] == 'ACCEPTED':
                if events[eid]['command_id'] != row['command_id'] or eid in claimed:
                    invalid('Receipt ownership does not match ledger command')
                claimed.add(eid)
        receipts[row['command_id']] = (row, receipt)
    # Every ledger event must have an accepted command receipt at this cutoff.
    if claimed != set(events):
        invalid('Ledger events are missing accepted receipt linkage')
    for record in snap['idempotency_records']:
        original = receipts.get(record['original_command_id'])
        if original is None:
            invalid('Idempotency record has no original receipt')
        row, receipt = original
        if (row['status'] != 'ACCEPTED' or row['idempotency_key'] != record['idempotency_key']
                or row['logical_hash'] != record['logical_hash']
                or row['receipt_json'] != record['original_receipt_json']
                or row['recorded_at'] != record['created_at']):
            invalid('Idempotency original receipt binding is inconsistent')
    for row, receipt in receipts.values():
        record = by_key.get(row['idempotency_key'])
        if record is None or row['logical_hash'] != record['logical_hash']:
            invalid('Receipt has no consistent idempotency record')
        original = json.loads(record['original_receipt_json'])
        if row['status'] == 'DUPLICATE' and (
                receipt['event_ids'] != original['event_ids'] or receipt['result'] != original['result']):
            invalid('Duplicate receipt differs from original result')
        if row['status'] == 'ACCEPTED' and row['command_id'] != record['original_command_id']:
            invalid('Accepted receipt is not the original command for its key')
    return snap


def export_bundle(spine, out_path):
    from .spine import projection_digest
    out = Path(out_path)
    with spine.db.connect() as conn:
        # Reserve the writer before any read. All tables and cutoff share one transaction.
        conn.execute('BEGIN IMMEDIATE')
        ok, bad = spine.ledger.verify_chain(conn)
        if not ok:
            invalid(f'Cannot export corrupt ledger: {bad}')
        controls = validate_controls(conn, spine.contracts)
        refs = spine.reference_snapshot(conn)
        projection = spine.projection_snapshot(conn)
        events = [dict(r) for r in conn.execute('SELECT * FROM asset_events ORDER BY rowid')]
        evidence = [dict(r) for r in conn.execute('SELECT * FROM evidence_attachments ORDER BY attachment_id')]
        corrections = [dict(r) for r in conn.execute('SELECT * FROM correction_links ORDER BY correction_event_id')]
        meta = {
            'format': 'SKATE_R02_RECOVERY_BUNDLE', 'format_version': FORMAT_VERSION,
            'created_at': utc_now(), 'boundary': 'FULL_TRANSACTION_CUTOFF_NO_TAIL_REPLAY',
            'event_count': len(events), 'last_event_id': events[-1]['event_id'] if events else None,
            'last_event_hash': events[-1]['event_hash'] if events else None,
            'projection_version': 'r02-projection-1', 'projection_digest': projection_digest(conn),
            'reference_digest': sha256_json(refs), 'control_digest': sha256_json(controls),
            'receipt_count': len(controls['command_receipts']),
            'idempotency_count': len(controls['idempotency_records']),
        }
    entries = {}
    for name, obj in [('bundle.json', meta), ('references.json', refs), ('projection.json', projection),
                      ('evidence.json', evidence), ('corrections.json', corrections), ('controls.json', controls)]:
        entries[name] = (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)+'\n').encode()
    entries['ledger.jsonl'] = ''.join(json.dumps(e, sort_keys=True, ensure_ascii=False)+'\n' for e in events).encode()
    entries['MANIFEST.sha256'] = ''.join(f'{hashlib.sha256(v).hexdigest()}  {n}\n'
                                       for n, v in sorted(entries.items())).encode()
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, value in sorted(entries.items()): z.writestr(name, value)
    return {'path': str(out), 'sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
            'event_count': len(events), 'last_event_hash': meta['last_event_hash'],
            'control_digest': meta['control_digest'], 'format_version': FORMAT_VERSION}


def read_bundle(bundle_path):
    with zipfile.ZipFile(bundle_path) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            invalid('Duplicate recovery archive members')
        if 'bundle.json' not in names:
            invalid('Incomplete recovery bundle')
        meta = json.loads(z.read('bundle.json'))
        if meta.get('format_version') != FORMAT_VERSION:
            invalid('Unsupported recovery version; legacy recovery omits complete command control state')
        if set(names) != MEMBERS:
            invalid('Incomplete or unexpected recovery archive members')
        entries = {n: z.read(n) for n in names}
    expected = {}
    for line in entries['MANIFEST.sha256'].decode().splitlines():
        h, name = line.split('  ', 1)
        if name in expected or name not in MEMBERS - {'MANIFEST.sha256'}:
            invalid('Invalid recovery manifest member')
        expected[name] = h
    if set(expected) != MEMBERS - {'MANIFEST.sha256'}:
        invalid('Manifest does not cover the complete recovery boundary')
    for name, h in expected.items():
        if hashlib.sha256(entries[name]).hexdigest() != h:
            invalid(f'Recovery hash mismatch for {name}')
    data = {n[:-5]: json.loads(v) for n, v in entries.items() if n.endswith('.json')}
    data['events'] = [json.loads(line) for line in entries['ledger.jsonl'].decode().splitlines() if line.strip()]
    return data


def insert_rows(conn, table, rows):
    columns = [r[1] for r in conn.execute(f'PRAGMA table_info({table})')]
    for row in rows:
        if set(row) != set(columns): invalid(f'Invalid columns in {table}')
        conn.execute(f"INSERT INTO {table}({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                     tuple(row[c] for c in columns))


def restore_bundle(cls, bundle_path, target_db_path):
    from .spine import _insert_reference_snapshot, _insert_projection_snapshot, projection_digest
    target = Path(target_db_path).absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError(f'Refusing to overwrite existing database: {target}')
    try:
        data = read_bundle(bundle_path)
        meta, events, controls = data['bundle'], data['events'], data['controls']
        if (meta['format'] != 'SKATE_R02_RECOVERY_BUNDLE'
                or meta['boundary'] != 'FULL_TRANSACTION_CUTOFF_NO_TAIL_REPLAY'
                or meta['projection_version'] != 'r02-projection-1'
                or meta['event_count'] != len(events)
                or meta['last_event_id'] != (events[-1]['event_id'] if events else None)
                or meta['last_event_hash'] != (events[-1]['event_hash'] if events else None)
                or meta['receipt_count'] != len(controls['command_receipts'])
                or meta['idempotency_count'] != len(controls['idempotency_records'])
                or meta['control_digest'] != sha256_json(controls)
                or meta['reference_digest'] != sha256_json(data['references'])
                or meta['projection_digest'] != sha256_json(data['projection'])):
            invalid('Recovery metadata does not match its cutoff state')
        # Stage on the target filesystem, with no target/parent mutation during validation.
        ancestor = target.parent
        while not ancestor.exists(): ancestor = ancestor.parent
        with tempfile.TemporaryDirectory(prefix='.skate-recovery-', dir=ancestor) as td:
            stage = Path(td) / 'staged.sqlite3'
            db = Database(stage); db.initialize()
            raw = sqlite3.connect(stage)
            try:
                raw.execute('PRAGMA foreign_keys=OFF')
                raw.execute('BEGIN IMMEDIATE')
                _insert_reference_snapshot(raw, data['references'])
                _insert_projection_snapshot(raw, data['projection'])
                insert_rows(raw, 'asset_events', events)
                insert_rows(raw, 'command_receipts', controls['command_receipts'])
                insert_rows(raw, 'idempotency_records', controls['idempotency_records'])
                insert_rows(raw, 'evidence_attachments', data['evidence'])
                insert_rows(raw, 'correction_links', data['corrections'])
                if raw.execute('PRAGMA foreign_key_check').fetchall(): invalid('Recovery foreign key violation')
                raw.commit()
            finally:
                raw.close()
            spine = cls(db)
            with db.connect() as conn:
                validate_controls(conn, spine.contracts)
                if projection_digest(conn) != meta['projection_digest']: invalid('Restored projection differs')
                if sha256_json(spine.reference_snapshot(conn)) != meta['reference_digest']: invalid('Restored references differ')
            report = spine.health_report(deep=True)
            if report['status'] != 'HEALTHY': invalid('Staged recovery failed deep health/replay validation')
            spine.create_checkpoint({'reason': 'validated_recovery', 'recovery_control_digest': meta['control_digest']})
            # SQLite backup produces a self-contained rollback-journal DB, including WAL commits.
            publish = Path(td) / 'publish.sqlite3'
            source_conn = db.connect()
            publish_conn = sqlite3.connect(publish)
            try:
                source_conn.backup(publish_conn)
                publish_conn.execute('PRAGMA journal_mode=DELETE')
                publish_conn.commit()
            finally:
                publish_conn.close()
                source_conn.close()
            # Hard-link publication refuses a racing existing target atomically.
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(publish, target)
        return {'db': str(target_db_path), 'event_count': meta['event_count'],
                'last_event_hash': meta['last_event_hash'], 'status': 'HEALTHY',
                'control_digest': meta['control_digest'], 'format_version': FORMAT_VERSION}
    except (RegistryError, FileExistsError):
        raise
    except (ValueError, KeyError, TypeError, UnicodeError, sqlite3.DatabaseError, zipfile.BadZipFile) as ex:
        raise RegistryError('LEDGER_INTEGRITY_ERROR', f'Invalid or incomplete recovery bundle: {ex}') from ex

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sqlite3
import uuid

import pytest

from conftest import envelope
from skate_inventory_core import CoreConfig, CoreLifecycleError, SkateInventoryCore
from skate_registry.contracts import ContractStore
from skate_registry.reference_data import ReferenceDataService
from skate_registry.spine import RuntimeSpine


def seed(core):
    # Existing trusted-local reference administration, not a second registry.
    ref = ReferenceDataService(core.db)
    ref.add_organization({'org_id': 'ORG-OWNER', 'name': 'Owner', 'org_type': 'ASSET_OWNER'})
    ref.add_organization({'org_id': 'ORG-RINK', 'name': 'Rink', 'org_type': 'VENUE_OPERATOR'})
    ref.add_location({'location_id': 'LOC-RINK', 'name': 'Rink', 'location_type': 'RINK'})
    ref.add_location({'location_id': 'LOC-STORAGE', 'name': 'Storage', 'location_type': 'STORAGE'})
    ref.add_device({'device_id': 'DEV-COUNTER', 'name': 'Counter', 'device_type': 'COUNTER_TABLET'})


def register(core, pair_id='SKT-0400'):
    commands = [
        ('register_pair', {'pair': {'pair_id': pair_id, 'owner_org_id': 'ORG-OWNER',
          'size_system': 'US_MENS', 'size_value': '8', 'category': 'HOCKEY',
          'home_location_id': 'LOC-RINK', 'current_location_id': 'LOC-RINK', 'custodian_org_id': 'ORG-OWNER'}}),
        ('register_component', {'component': {'component_id': pair_id+'-L', 'pair_id': pair_id,
          'side': 'L', 'label_identifier': pair_id+'-L', 'current_location_id': 'LOC-RINK'}}),
        ('register_component', {'component': {'component_id': pair_id+'-R', 'pair_id': pair_id,
          'side': 'R', 'label_identifier': pair_id+'-R', 'current_location_id': 'LOC-RINK'}}),
        ('link_pair', {'pair_id': pair_id, 'left_component_id': pair_id+'-L', 'right_component_id': pair_id+'-R'}),
    ]
    for name, payload in commands:
        assert core.execute(envelope(name, payload))['status'] == 'ACCEPTED'


def snapshot(core):
    with core.db.connect() as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {t: [tuple(r) for r in conn.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables}


@pytest.fixture
def core(tmp_path):
    obj = SkateInventoryCore(CoreConfig(tmp_path/'core.sqlite3')).initialize()
    seed(obj)
    yield obj
    obj.shutdown()


def test_shared_database_and_contract_instance(tmp_path):
    contracts = ContractStore()
    core = SkateInventoryCore(CoreConfig(tmp_path/'one.sqlite3'), contracts=contracts).initialize()
    assert core.processor.db is core.db is core.spine.db
    assert core.processor.contracts is core.spine.contracts is core.contracts is contracts
    assert core.processor.service.contracts is contracts
    assert core.spine.projector.contracts is contracts
    assert Path(core.db.path) == core.config.sqlite_path
    core.shutdown()


def test_fresh_initialize_register_scan_transfer(core):
    assert core.list_inventory() == []
    register(core)
    scan = core.execute(envelope('scan_asset', {'identifier': 'SKT-0400-L'}))
    assert scan['status'] == 'ACCEPTED'
    assert scan['result']['pair']['pair_id'] == 'SKT-0400'
    moved = core.execute(envelope('transfer_location', {'pair_id': 'SKT-0400', 'to_location_id': 'LOC-STORAGE'}))
    assert moved['status'] == 'ACCEPTED'
    pair = core.get_pair('SKT-0400')
    assert pair['current_location_id'] == 'LOC-STORAGE'
    assert len(pair['components']) == 2
    assert all(c['current_location_id'] == 'LOC-STORAGE' for c in pair['components'])
    assert core.health(deep=True)['status'] == 'HEALTHY'


def test_public_reads_are_detached_and_write_free(core):
    register(core)
    before = snapshot(core)
    pair = core.get_pair('SKT-0400')
    inventory = core.list_inventory()
    pair['current_location_id'] = 'changed'
    pair['components'][0]['label_identifier'] = 'changed'
    pair['maintenance_flags'].append('changed')
    inventory.clear()
    assert core.get_pair('SKT-0400')['current_location_id'] == 'LOC-RINK'
    assert core.get_pair('SKT-0400')['components'][0]['label_identifier'] == 'SKT-0400-L'
    assert core.get_pair('SKT-0400')['maintenance_flags'] == []
    assert core.get_pair('SKT-DOES-NOT-EXIST') is None
    with pytest.raises(TypeError): core.get_pair(None)
    core.health(deep=True)
    assert snapshot(core) == before


OPERATIONS = ['execute', 'health', 'list_inventory', 'get_pair', 'db', 'contracts', 'processor', 'spine']


@pytest.mark.parametrize('operation', OPERATIONS)
@pytest.mark.parametrize('state,code', [('NEW', 'CORE_NOT_INITIALIZED'), ('SHUTDOWN', 'CORE_SHUTDOWN')])
def test_deterministic_lifecycle_errors(tmp_path, operation, state, code):
    path = tmp_path/'not-created.db'
    core = SkateInventoryCore(CoreConfig(path))
    if state == 'SHUTDOWN': core.shutdown()
    with pytest.raises(CoreLifecycleError) as ex:
        if operation == 'execute': core.execute({})
        elif operation == 'get_pair': core.get_pair('unknown')
        elif operation in ('health', 'list_inventory'): getattr(core, operation)()
        else: getattr(core, operation)
    assert ex.value.code == code
    assert str(ex.value) == code
    assert not path.exists()


def test_repeat_initialize_shutdown_and_reopen(core):
    register(core)
    before = snapshot(core)
    processor, spine, db = core.processor, core.spine, core.db
    assert core.initialize() is core
    assert (core.processor, core.spine, core.db) == (processor, spine, db)
    assert snapshot(core) == before
    config = core.config
    core.shutdown(); core.shutdown()
    with pytest.raises(CoreLifecycleError, match='CORE_SHUTDOWN'): core.initialize()
    reopened = SkateInventoryCore(config).initialize()
    assert snapshot(reopened) == before
    assert reopened.get_pair('SKT-0400') is not None
    assert reopened.health(deep=True)['status'] == 'HEALTHY'
    reopened.shutdown()


def test_two_configured_instances_are_isolated(tmp_path):
    a = SkateInventoryCore(CoreConfig(tmp_path/'a.db')).initialize()
    b = SkateInventoryCore(CoreConfig(tmp_path/'b.db')).initialize()
    seed(a); seed(b); register(a)
    assert a.db is not b.db and a.contracts is not b.contracts
    assert b.list_inventory() == []
    register(b, 'SKT-0401')
    assert a.get_pair('SKT-0401') is None
    assert b.get_pair('SKT-0400') is None
    a.shutdown()
    assert b.health(deep=True)['status'] == 'HEALTHY'
    b.shutdown()


def test_recovery_retry_conflict_through_core(core, tmp_path):
    register(core)
    cmd = envelope('transfer_location', {'pair_id':'SKT-0400', 'to_location_id':'LOC-STORAGE'})
    original = core.execute(cmd)
    assert original['status'] == 'ACCEPTED'
    bundle = tmp_path/'recovery.zip'
    core.spine.export_recovery_bundle(bundle)
    restored_path = tmp_path/'restored.db'
    RuntimeSpine.restore_recovery_bundle(bundle, restored_path)
    recovered = SkateInventoryCore(CoreConfig(restored_path)).initialize()
    before = snapshot(recovered)
    retry = recovered.execute(cmd)
    assert retry['status'] == 'DUPLICATE'
    assert retry['event_ids'] == original['event_ids']
    assert retry['result'] == original['result']
    assert snapshot(recovered) == before
    changed = deepcopy(cmd); changed['command_id'] = str(uuid.uuid4())
    changed['payload']['to_location_id'] = 'LOC-RINK'
    assert core.execute(changed)['error']['code'] == 'IDEMPOTENCY_CONFLICT'
    assert recovered.execute(changed)['error']['code'] == 'IDEMPOTENCY_CONFLICT'
    assert snapshot(recovered) == before
    assert recovered.health(deep=True)['status'] == 'HEALTHY'
    recovered.shutdown()


def test_execute_is_exact_legacy_processor_delegation(core, monkeypatch):
    cmd = envelope('scan_asset', {'identifier': 'missing'})
    result = {'delegated': True}
    def process(arg):
        assert arg is cmd
        return result
    monkeypatch.setattr(core.processor, 'process', process)
    assert core.execute(cmd) is result


def test_original_schema_role_and_command_names(core):
    register(core)
    denied = core.execute(envelope('transfer_location', {'pair_id':'SKT-0400', 'to_location_id':'LOC-STORAGE'}, role='CUSTOMER'))
    assert denied['error']['code'] == 'ROLE_FORBIDDEN'
    malformed = core.execute(envelope('transfer_location', {'pair_id':'SKT-0400'}))
    assert malformed['error']['code'] == 'VALIDATION_ERROR'
    alias = core.execute(envelope('register_asset', {}))
    assert alias['status'] == 'REJECTED'
    assert core.get_pair('SKT-0400')['current_location_id'] == 'LOC-RINK'


def test_failed_initialize_can_retry(tmp_path, monkeypatch):
    core = SkateInventoryCore(CoreConfig(tmp_path/'nested'/'core.db'))
    real_initialize = core._db.initialize
    monkeypatch.setattr(core._db, 'initialize', lambda: (_ for _ in ()).throw(sqlite3.OperationalError('test failure')))
    with pytest.raises(sqlite3.OperationalError): core.initialize()
    assert core.state == 'NEW'
    monkeypatch.setattr(core._db, 'initialize', real_initialize)
    assert core.initialize() is core
    assert core.list_inventory() == []
    core.shutdown()


@pytest.mark.parametrize('path', ['', ':memory:', 'file:mem?mode=memory'])
def test_explicit_file_path_required(path):
    with pytest.raises(ValueError): CoreConfig(path)


def test_config_validation(tmp_path):
    with pytest.raises(TypeError): CoreConfig(None)
    with pytest.raises(ValueError): CoreConfig(tmp_path)
    with pytest.raises(TypeError): SkateInventoryCore('not-a-config')
    with pytest.raises(TypeError): SkateInventoryCore(CoreConfig(tmp_path/'x.db'), contracts='not-a-store')

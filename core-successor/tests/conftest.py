from __future__ import annotations

import uuid
import pytest

from skate_registry.db import Database
from skate_registry.reference_data import ReferenceDataService
from skate_registry.util import utc_now


@pytest.fixture
def runtime(tmp_path):
    db=Database(tmp_path/'registry.sqlite3'); db.initialize(); ref=ReferenceDataService(db)
    ref.add_organization({'org_id':'ORG-OWNER','name':'Owner','org_type':'ASSET_OWNER'})
    ref.add_organization({'org_id':'ORG-RINK','name':'Rink','org_type':'VENUE_OPERATOR'})
    ref.add_organization({'org_id':'ORG-OTHER','name':'Other Owner','org_type':'ASSET_OWNER'})
    ref.add_location({'location_id':'LOC-RINK','name':'Rink','location_type':'RINK'})
    ref.add_location({'location_id':'LOC-STORAGE','name':'Storage','location_type':'STORAGE'})
    ref.add_device({'device_id':'DEV-COUNTER','name':'Counter','device_type':'COUNTER_TABLET'})
    return db


def envelope(name,payload,*,role='OWNER_ADMIN',key=None,expected=None,command_id=None):
    e={'command_id':command_id or str(uuid.uuid4()),'schema_version':'0.1.0','command_name':name,'requested_at':utc_now(),'actor_id':'tester','actor_role':role,'device_id':'DEV-COUNTER','location_id':'LOC-RINK','idempotency_key':key or f'test:{uuid.uuid4()}','payload':payload,'offline_created':False}
    if expected is not None: e['expected_pair_version']=expected
    return e

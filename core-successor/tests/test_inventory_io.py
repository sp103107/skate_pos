from skate_registry.inventory_io import import_inventory_csv, export_inventory


def test_import_export(runtime,tmp_path):
    csv=tmp_path/'inventory.csv'
    csv.write_text('pair_id,size_system,size_value,category,brand,model,owner_org_id,custodian_org_id,home_location_id,current_location_id,left_label,right_label,acquisition_date,acquisition_source,acquisition_cost_minor,ownership_evidence_ref\nSKT-0100,US_MENS,9,HOCKEY,Riedell,Rental,ORG-OWNER,ORG-OWNER,LOC-RINK,LOC-RINK,SKT-0100-L,SKT-0100-R,,,,\n',encoding='utf-8')
    out=import_inventory_csv(runtime,csv,actor_id='tester',actor_role='OWNER_ADMIN',device_id='DEV-COUNTER',location_id='LOC-RINK')
    assert out[0]['ok'] is True
    inv=export_inventory(runtime); assert len(inv)==1; assert inv[0]['pair_id']=='SKT-0100'; assert len(inv[0]['components'])==2

from pathlib import Path
import csv,json,hashlib,sys
from PIL import Image
root=Path(__file__).resolve().parents[1]
errors=[]
for p in root.rglob('*.json'):
    try: json.loads(p.read_text())
    except Exception as e: errors.append(f'JSON {p.relative_to(root)}: {e}')
with (root/'mapping/FE_BE_MAPPING_MATRIX.csv').open(newline='',encoding='utf-8') as f:
    rows=list(csv.DictReader(f))
req=['frontend_component','operator_intent','runtime_command_or_query','payload_contract','backend_service','event_types','projection_read_model','receipt_or_error','frontend_state_update','role_permission','offline_behavior','capability_state']
if not rows: errors.append('mapping matrix empty')
elif list(rows[0].keys())!=req: errors.append('mapping headers mismatch')
for r in rows:
    if r['capability_state'].startswith('DESIGN_GATED') and 'NOT IMPLEMENTED' not in r['backend_service']:
        errors.append('gated row missing NOT IMPLEMENTED backend: '+r['frontend_component'])
for p in root.glob('assets/**/*.png'):
    try:
        im=Image.open(p); im.verify()
    except Exception as e: errors.append(f'PNG {p.relative_to(root)}: {e}')
cap=json.loads((root/'UI00_CAPSULE.json').read_text())
for k in ['runtime_activation_authorized','frontend_runtime_activation_authorized','rental_activation_authorized','communications_activation_authorized']:
    if cap.get(k) is not False: errors.append(k+' must remain false')
if errors:
    print('FAIL')
    for e in errors: print('-',e)
    sys.exit(1)
print('PASS')
print('mapping_rows',len(rows))
print('png_assets',len(list(root.glob('assets/**/*.png'))))

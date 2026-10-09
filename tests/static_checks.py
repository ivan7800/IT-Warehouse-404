from pathlib import Path
import re, sys
root=Path(__file__).resolve().parents[1]
html=(root/'static/index.html').read_text(encoding='utf-8')
js=(root/'static/app.js').read_text(encoding='utf-8')
server=(root/'server.py').read_text(encoding='utf-8')
schema=(root/'schema_postgresql.sql').read_text(encoding='utf-8')
ids=re.findall(r'\bid=["\']([^"\']+)',html)
dups=sorted({x for x in ids if ids.count(x)>1})
refs=set(re.findall(r"\$\('#([^']+)'\)",js)) | set(re.findall(r'\$\("([^\"]+)"\)',js))
# only #id selectors count as direct DOM refs
refs={x[1:] for x in refs if x.startswith('#')}
missing=sorted(refs-set(ids))
checks={
 'duplicate_html_ids':dups,
 'missing_dom_refs':missing,
 'editable_operator_removed': 'name="operator"' not in html,
 'csrf_header_present': "X-CSRF-Token" in js,
 'role_ui_present': all(x in html for x in ('role-admin','role-manager','role-operator')),
 'mobile_scanner_present': 'BarcodeDetector' in js and 'getUserMedia' in js,
 'capacity_locked_on_create': "active=TRUE FOR UPDATE',(loc_id,)" in server,
 'capacity_locked_on_move': "active=TRUE FOR UPDATE',(lid,)" in server,
 'partial_transfer_lineage': 'origin_item_id' in server and 'destination_item_id' in server and 'idx_movements_destination' in schema,
 'last_admin_guard': 'Debe quedar al menos un administrador activo' in server,
 'audit_append_only_trigger': 'prevent_audit_mutation' in schema and 'trg_audit_no_delete' in schema and 'trg_audit_no_update' in schema,
 'server_side_roles': "require_user('admin'" in server and "ROLE_LEVEL[user['role']]" in server,
}
print(checks)
bools=[v for k,v in checks.items() if k not in ('duplicate_html_ids','missing_dom_refs')]
if dups or missing or not all(v is True for v in bools): sys.exit(1)

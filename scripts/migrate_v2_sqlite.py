#!/usr/bin/env python3
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import argparse
import secrets
import sqlite3
from db import transaction, one, execute
from security import hash_password

ap=argparse.ArgumentParser(description='Migra IT Warehouse 404 v2.x SQLite a v3 PostgreSQL')
ap.add_argument('sqlite_db', type=Path)
args=ap.parse_args()
if not args.sqlite_db.is_file(): raise SystemExit('No existe el SQLite indicado.')
src=sqlite3.connect(args.sqlite_db); src.row_factory=sqlite3.Row

with transaction() as dst:
    legacy=one(dst,"SELECT id FROM users WHERE username='legacy-import'")
    if legacy: legacy_id=legacy['id']
    else:
        ph=hash_password(secrets.token_urlsafe(24))
        legacy_id=execute(dst,"INSERT INTO users(username,display_name,password_hash,role,active) VALUES('legacy-import','Importación v2',%s,'viewer',FALSE) RETURNING id",(ph,))['id']
    loc_map={}
    for r in src.execute('SELECT * FROM locations ORDER BY id'):
        found=one(dst,'SELECT id FROM locations WHERE code=%s',(r['code'],))
        if found: nid=found['id']
        else:
            nid=execute(dst,"""INSERT INTO locations(code,zone,rack,shelf,position,capacity,notes,active,created_at,updated_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",(r['code'],r['zone'],r['rack'],r['shelf'],r['position'],r['capacity'],r['notes'],bool(r['active']),r['created_at'],r['updated_at']))['id']
        loc_map[r['id']]=nid
    item_map={}
    for r in src.execute('SELECT * FROM items ORDER BY id'):
        nid=execute(dst,"""INSERT INTO items(category,manufacturer,model,serial_number,asset_tag,tracking_mode,quantity,min_stock,status,location_id,notes,created_at,updated_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",(r['category'],r['manufacturer'],r['model'],r['serial_number'],r['asset_tag'],r['tracking_mode'],r['quantity'],r['min_stock'],r['status'],loc_map.get(r['location_id']),r['notes'],r['created_at'],r['updated_at']))['id']
        item_map[r['id']]=nid
    for r in src.execute('SELECT * FROM movements ORDER BY id'):
        execute(dst,"""INSERT INTO movements(item_id,action,quantity,from_status,to_status,from_location_id,to_location_id,person,ticket,operator_user_id,operator_name,notes,created_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",(item_map[r['item_id']],r['action'],r['quantity'],r['from_status'],r['to_status'],loc_map.get(r['from_location_id']),loc_map.get(r['to_location_id']),r['person'],r['ticket'],legacy_id,r['operator'] or 'Importación v2',r['notes'],r['created_at']))
    execute(dst,"""INSERT INTO audit_log(actor_user_id,actor_name,action,entity_type,summary,metadata)
        VALUES(%s,'Importación v2','migration.v2','system','Migración desde SQLite v2 completada',jsonb_build_object('source',%s,'locations',%s,'items',%s,'movements',%s))""",
        (legacy_id,str(args.sqlite_db),len(loc_map),len(item_map),src.execute('SELECT COUNT(*) FROM movements').fetchone()[0]))
print(f'Migración completada: {len(loc_map)} ubicaciones, {len(item_map)} registros de material.')

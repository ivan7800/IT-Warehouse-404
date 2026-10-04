#!/usr/bin/env python3
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from db import connect

schema = (Path(__file__).resolve().parents[1] / 'schema_postgresql.sql').read_text(encoding='utf-8')
conn = connect()
try:
    with conn.cursor() as cur:
        cur.execute(schema)
    conn.commit()
    print('Schema PostgreSQL aplicado correctamente.')
finally:
    conn.close()

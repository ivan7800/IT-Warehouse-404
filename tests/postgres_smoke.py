"""Smoke test no destructivo. Requiere PostgreSQL inicializado y WAREHOUSE_DATABASE_URL."""
from db import connect, one, all_rows

def main():
    c=connect()
    try:
        tables=one(c,"""SELECT COUNT(*) AS n FROM information_schema.tables
          WHERE table_schema='public' AND table_name IN ('users','sessions','items','locations','movements','audit_log')""")['n']
        assert tables==6, f'Faltan tablas: {tables}/6'
        checks=one(c,"""SELECT
          (SELECT COUNT(*) FROM users) AS users,
          (SELECT COUNT(*) FROM locations) AS locations,
          (SELECT COUNT(*) FROM items) AS items,
          (SELECT COUNT(*) FROM movements) AS movements,
          (SELECT COUNT(*) FROM audit_log) AS audit_rows""")
        constraints=one(c,"""SELECT COUNT(*) AS n FROM pg_constraint
          WHERE conrelid IN ('users'::regclass,'items'::regclass,'movements'::regclass)""")['n']
        triggers=all_rows(c,"""SELECT tgname FROM pg_trigger
          WHERE tgrelid='audit_log'::regclass AND NOT tgisinternal""")
        trigger_names={r['tgname'] for r in triggers}
        assert {'trg_audit_no_update','trg_audit_no_delete'} <= trigger_names, f'Triggers auditoría incompletos: {trigger_names}'
        indexes=one(c,"""SELECT COUNT(*) AS n FROM pg_indexes WHERE schemaname='public'
          AND indexname IN ('idx_items_serial_unique','idx_items_asset_unique','idx_movements_operator','idx_audit_actor')""")['n']
        assert indexes==4, f'Índices críticos incompletos: {indexes}/4'
        assert int(constraints) >= 8, f'Número inesperadamente bajo de constraints: {constraints}'
        c.rollback()
        print('PASS PostgreSQL schema/integrity:', checks)
        print('PASS audit append-only triggers:', sorted(trigger_names))
        print('PASS critical indexes:', indexes)
    finally:
        c.close()

if __name__=='__main__': main()

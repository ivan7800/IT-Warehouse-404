import os
from contextlib import contextmanager

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

DATABASE_URL = os.environ.get('WAREHOUSE_DATABASE_URL', 'postgresql://warehouse:warehouse@127.0.0.1:5432/warehouse404')


def require_driver():
    if psycopg is None:
        raise RuntimeError('Falta psycopg. Ejecuta: python -m pip install -r requirements.txt')


def connect():
    require_driver()
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


@contextmanager
def transaction():
    conn = connect()
    try:
        with conn.transaction():
            yield conn
    finally:
        conn.close()


def one(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def all_rows(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def execute(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        try:
            return cur.fetchone()
        except Exception:
            return None

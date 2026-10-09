#!/usr/bin/env python3
import csv
import io
import json
import mimetypes
import os
import re
import sys
import traceback
import base64
import ssl
import threading
import time
from datetime import datetime, timezone
from http import cookies
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from db import connect, transaction, one, all_rows, execute, require_driver
from security import verify_password, new_session_material, hash_session_token

try:
    import qrcode
except ImportError:
    qrcode = None

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / 'static'
HOST = os.environ.get('WAREHOUSE_HOST', '0.0.0.0')
PORT = int(os.environ.get('WAREHOUSE_PORT', '8765'))
VERSION = '3.1.0-rc2'
MAX_BODY_BYTES = 1024 * 1024
TLS_CERT = os.environ.get('WAREHOUSE_TLS_CERT', '').strip()
TLS_KEY = os.environ.get('WAREHOUSE_TLS_KEY', '').strip()
COOKIE_SECURE = os.environ.get('WAREHOUSE_COOKIE_SECURE', '1' if TLS_CERT and TLS_KEY else '0') == '1'
LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_FAILURES = 8
_LOGIN_FAILURES = {}
_LOGIN_LOCK = threading.Lock()
SESSION_COOKIE = 'warehouse_session'

ROLE_LEVEL = {'viewer': 10, 'operator': 20, 'manager': 30, 'admin': 40}


def json_default(obj):
    if isinstance(obj, (datetime,)):
        return obj.isoformat(timespec='seconds')
    raise TypeError(type(obj).__name__)


def safe_int(v, default=0, minimum=None, maximum=None):
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = default
    if minimum is not None:
        n = max(minimum, n)
    if maximum is not None:
        n = min(maximum, n)
    return n


def normalize_code(zone, rack, shelf, position):
    def clean(v):
        return '-'.join(str(v or '').strip().upper().replace('/', '-').split())
    return '-'.join(x for x in map(clean, (zone, rack, shelf, position)) if x)


def location_label(row):
    if not row:
        return ''
    parts = []
    if row.get('zone'):
        parts.append(f"Zona {row['zone']}")
    if row.get('rack'):
        parts.append(f"Est. {row['rack']}")
    if row.get('shelf'):
        parts.append(f"Balda {row['shelf']}")
    if row.get('position'):
        parts.append(f"Pos. {row['position']}")
    return ' / '.join(parts) or row.get('code', '')


def allowed_actions(item):
    mode, status = item['tracking_mode'], item['status']
    if mode == 'bulk':
        if status == 'baja':
            return []
        return (['entrada', 'salida', 'mover', 'ajuste'] if int(item['quantity']) > 0 else ['entrada', 'ajuste'])
    matrix = {
        'disponible': ['salida', 'mover', 'reparacion', 'baja'],
        'entregado': ['devolucion', 'reparacion', 'baja'],
        'reparacion': ['devolucion', 'baja'],
        'baja': [],
        'sin_stock': [],
    }
    return matrix.get(status, [])


def audit(conn, actor, request, action, entity_type, entity_id, summary, metadata=None):
    execute(conn, """INSERT INTO audit_log(actor_user_id,actor_name,action,entity_type,entity_id,summary,metadata,ip_address,user_agent)
                     VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (actor['id'] if actor else None, actor['display_name'] if actor else '', action, entity_type,
             str(entity_id or ''), summary, json.dumps(metadata or {}, ensure_ascii=False),
             request.client_address[0] if request else '', request.headers.get('User-Agent','')[:500] if request else ''))


def location_used_units(conn, location_id, exclude_item_id=None):
    sql = """SELECT COALESCE(SUM(CASE WHEN status='disponible' THEN CASE WHEN tracking_mode='bulk' THEN quantity ELSE 1 END ELSE 0 END),0) AS used
             FROM items WHERE location_id=%s"""
    params = [location_id]
    if exclude_item_id:
        sql += ' AND id<>%s'
        params.append(exclude_item_id)
    row = one(conn, sql, tuple(params))
    return int(row['used'] or 0)


def ensure_capacity(conn, loc, units, exclude_item_id=None):
    if not loc or int(loc['capacity'] or 0) <= 0:
        return None
    used = location_used_units(conn, loc['id'], exclude_item_id)
    total = used + int(units)
    if total > int(loc['capacity']):
        return f"Ubicación {loc['code']} sin capacidad suficiente: ocuparía {total}/{loc['capacity']} unidades"
    return None


class AppHandler(BaseHTTPRequestHandler):
    server_version = 'ITWarehouse404'
    sys_version = ''

    def log_message(self, fmt, *args):
        sys.stdout.write('[%s] %s\n' % (self.log_date_time_string(), fmt % args))

    def _headers(self, status=200, ctype='application/json; charset=utf-8', extra=None):
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Permissions-Policy', 'camera=(self), geolocation=(), microphone=()')
        self.send_header('Cache-Control', 'no-store' if ctype.startswith('application/json') else 'no-cache')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def _json(self, payload, status=200, extra=None):
        data = json.dumps(payload, ensure_ascii=False, default=json_default).encode('utf-8')
        self._headers(status, extra=extra)
        self.wfile.write(data)

    def _error(self, message, status=400):
        self._json({'ok': False, 'error': message}, status)

    def _body_json(self):
        length = safe_int(self.headers.get('Content-Length'), 0, 0, MAX_BODY_BYTES + 1)
        if length > MAX_BODY_BYTES:
            raise ValueError('Cuerpo JSON demasiado grande')
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            value = json.loads(raw.decode('utf-8'))
        except Exception:
            raise ValueError('JSON inválido')
        if not isinstance(value, dict):
            raise ValueError('El cuerpo debe ser un objeto JSON')
        return value

    def _cookies(self):
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get('Cookie', ''))
        except Exception:
            pass
        return jar

    def current_user(self):
        jar = self._cookies()
        morsel = jar.get(SESSION_COOKIE)
        if not morsel:
            return None
        token_hash = hash_session_token(morsel.value)
        try:
            conn = connect()
            try:
                user = one(conn, """SELECT u.id,u.username,u.display_name,u.role,u.active,s.id AS session_id,s.csrf_token,s.expires_at
                                  FROM sessions s JOIN users u ON u.id=s.user_id
                                  WHERE s.token_hash=%s AND s.expires_at>NOW() AND u.active=TRUE""", (token_hash,))
                if user:
                    execute(conn, 'UPDATE sessions SET last_seen_at=NOW() WHERE id=%s', (user['session_id'],))
                    conn.commit()
                return user
            finally:
                conn.close()
        except Exception:
            return None

    def require_user(self, min_role='viewer', csrf=False):
        user = self.current_user()
        if not user:
            self._error('Sesión no válida o expirada', 401)
            return None
        if ROLE_LEVEL[user['role']] < ROLE_LEVEL[min_role]:
            self._error('No tienes permisos para esta operación', 403)
            return None
        if csrf and self.headers.get('X-CSRF-Token', '') != user['csrf_token']:
            self._error('Token CSRF inválido', 403)
            return None
        return user

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path, qs = parsed.path, parse_qs(parsed.query)
            if path == '/api/health':
                return self.api_health()
            if path == '/api/me':
                user = self.require_user()
                if user: return self._json({'ok': True, 'user': {k:user[k] for k in ('id','username','display_name','role')}, 'csrf_token': user['csrf_token'], 'version': VERSION})
                return
            if path.startswith('/api/'):
                user = self.require_user()
                if not user: return
                if path == '/api/dashboard': return self.api_dashboard(user)
                if path == '/api/items': return self.api_items(user, qs)
                m = re.fullmatch(r'/api/items/(\d+)/history', path)
                if m: return self.api_item_history(user, int(m.group(1)))
                if path == '/api/movements': return self.api_movements(user, qs)
                if path == '/api/locations': return self.api_locations(user, qs)
                if path == '/api/warehouse-map': return self.api_warehouse_map(user)
                m = re.fullmatch(r'/api/locations/(\d+)/items', path)
                if m: return self.api_location_items(user, int(m.group(1)))
                m = re.fullmatch(r'/api/locations/(\d+)/qr.png', path)
                if m: return self.api_qr_location(user, int(m.group(1)))
                m = re.fullmatch(r'/api/items/(\d+)/qr.png', path)
                if m: return self.api_qr_item(user, int(m.group(1)))
                if path == '/api/audit':
                    if ROLE_LEVEL[user['role']] < ROLE_LEVEL['manager']: return self._error('Solo manager/admin', 403)
                    return self.api_audit(user, qs)
                if path == '/api/users':
                    if user['role'] != 'admin': return self._error('Solo admin', 403)
                    return self.api_users(user)
                if path == '/api/export/items.csv': return self.export_items(user)
                if path == '/api/export/movements.csv': return self.export_movements(user)
                if path == '/api/export/locations.csv': return self.export_locations(user)
                return self._error('Endpoint no encontrado', 404)
            return self.serve_static(path)
        except Exception as e:
            traceback.print_exc()
            return self._error('Error interno del servidor', 500)

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            payload = self._body_json()
            if path == '/api/auth/login': return self.api_login(payload)
            user = self.require_user('viewer', csrf=True)
            if not user: return
            if path == '/api/auth/logout': return self.api_logout(user)
            if path == '/api/items':
                if ROLE_LEVEL[user['role']] < ROLE_LEVEL['operator']: return self._error('Permiso insuficiente', 403)
                return self.api_create_item(user, payload)
            if path == '/api/movements':
                if ROLE_LEVEL[user['role']] < ROLE_LEVEL['operator']: return self._error('Permiso insuficiente', 403)
                return self.api_create_movement(user, payload)
            if path == '/api/locations':
                if ROLE_LEVEL[user['role']] < ROLE_LEVEL['manager']: return self._error('Solo manager/admin', 403)
                return self.api_create_location(user, payload)
            if path == '/api/users':
                if user['role'] != 'admin': return self._error('Solo admin', 403)
                return self.api_create_user(user, payload)
            return self._error('Endpoint no encontrado', 404)
        except ValueError as e:
            return self._error(str(e), 400)
        except Exception as e:
            traceback.print_exc()
            return self._error('Error interno del servidor', 500)

    def do_PATCH(self):
        try:
            path = urlparse(self.path).path
            user = self.require_user('admin', csrf=True)
            if not user: return
            payload = self._body_json()
            m = re.fullmatch(r'/api/users/(\d+)', path)
            if m: return self.api_update_user(user, int(m.group(1)), payload)
            return self._error('Endpoint no encontrado', 404)
        except ValueError as e:
            return self._error(str(e), 400)
        except Exception as e:
            traceback.print_exc(); return self._error('Error interno del servidor', 500)

    def serve_static(self, path):
        rel = 'index.html' if path in ('','/') else path.lstrip('/')
        target = (STATIC_DIR / rel).resolve()
        if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
            return self._error('Ruta inválida', 400)
        if not target.is_file():
            target = STATIC_DIR / 'index.html'
        ctype = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        self._headers(200, ctype)
        self.wfile.write(target.read_bytes())

    def api_health(self):
        try:
            conn = connect(); one(conn, 'SELECT 1 AS ok'); conn.close()
            return self._json({'ok': True, 'version': VERSION, 'database': 'postgresql'})
        except Exception as e:
            return self._json({'ok': False, 'version': VERSION, 'database': 'postgresql', 'error': 'PostgreSQL no disponible'}, 503)

    def api_login(self, p):
        username = str(p.get('username','')).strip().lower()
        password = str(p.get('password',''))
        if not username or not password: return self._error('Usuario y contraseña son obligatorios', 400)
        ip = self.client_address[0]
        now = time.time()
        with _LOGIN_LOCK:
            recent = [t for t in _LOGIN_FAILURES.get(ip, []) if now - t < LOGIN_WINDOW_SECONDS]
            _LOGIN_FAILURES[ip] = recent
            if len(recent) >= LOGIN_MAX_FAILURES:
                return self._error('Demasiados intentos. Espera unos minutos.', 429)
        with transaction() as conn:
            execute(conn, 'DELETE FROM sessions WHERE expires_at<=NOW()')
            user = one(conn, 'SELECT * FROM users WHERE username=%s AND active=TRUE', (username,))
            if not user or not verify_password(password, user['password_hash']):
                with _LOGIN_LOCK:
                    _LOGIN_FAILURES.setdefault(ip, []).append(now)
                audit(conn, None, self, 'auth.login_failed', 'user', username, 'Inicio de sesión fallido', {'username': username})
                return self._error('Credenciales incorrectas', 401)
            with _LOGIN_LOCK:
                _LOGIN_FAILURES.pop(ip, None)
            token, token_hash, csrf, expires = new_session_material()
            execute(conn, """INSERT INTO sessions(user_id,token_hash,csrf_token,expires_at,ip_address,user_agent)
                             VALUES(%s,%s,%s,%s,%s,%s)""",
                    (user['id'], token_hash, csrf, expires, self.client_address[0], self.headers.get('User-Agent','')[:500]))
            execute(conn, 'UPDATE users SET last_login_at=NOW(), updated_at=NOW() WHERE id=%s', (user['id'],))
            actor = {'id':user['id'],'display_name':user['display_name']}
            audit(conn, actor, self, 'auth.login', 'user', user['id'], 'Inicio de sesión correcto')
        flags = f'{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=43200'
        if COOKIE_SECURE: flags += '; Secure'
        return self._json({'ok': True, 'user': {'id':user['id'],'username':user['username'],'display_name':user['display_name'],'role':user['role']}, 'csrf_token': csrf}, extra={'Set-Cookie': flags})

    def api_logout(self, user):
        jar = self._cookies(); morsel = jar.get(SESSION_COOKIE)
        with transaction() as conn:
            if morsel: execute(conn, 'DELETE FROM sessions WHERE token_hash=%s', (hash_session_token(morsel.value),))
            audit(conn, user, self, 'auth.logout', 'user', user['id'], 'Cierre de sesión')
        flags = f'{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'
        if COOKIE_SECURE: flags += '; Secure'
        return self._json({'ok':True}, extra={'Set-Cookie': flags})

    def api_dashboard(self, user):
        conn = connect()
        try:
            stats = one(conn, """SELECT COUNT(*) AS records,
                COALESCE(SUM(CASE WHEN status='disponible' THEN CASE WHEN tracking_mode='bulk' THEN quantity ELSE 1 END ELSE 0 END),0) AS available_units,
                COUNT(*) FILTER (WHERE status='entregado') AS assigned,
                COUNT(*) FILTER (WHERE status='reparacion') AS repair,
                COUNT(*) FILTER (WHERE status='baja') AS retired FROM items""")
            cats = all_rows(conn, """SELECT category, COALESCE(SUM(CASE WHEN status='disponible' THEN CASE WHEN tracking_mode='bulk' THEN quantity ELSE 1 END ELSE 0 END),0) AS units FROM items GROUP BY category ORDER BY units DESC, category""")
            low = all_rows(conn, """SELECT i.*, l.code AS location_code FROM items i LEFT JOIN locations l ON l.id=i.location_id WHERE i.tracking_mode='bulk' AND i.quantity<=i.min_stock ORDER BY i.quantity ASC LIMIT 20""")
            recent = all_rows(conn, """SELECT m.*,i.manufacturer,i.model,i.category,fl.code AS from_location,tl.code AS to_location
                FROM movements m JOIN items i ON i.id=m.item_id LEFT JOIN locations fl ON fl.id=m.from_location_id LEFT JOIN locations tl ON tl.id=m.to_location_id ORDER BY m.id DESC LIMIT 12""")
            locs = one(conn, """SELECT COUNT(*) AS total_locations, COUNT(*) FILTER (WHERE capacity>0 AND used>=capacity) AS full_locations FROM (
                SELECT l.id,l.capacity,COALESCE(SUM(CASE WHEN i.status='disponible' THEN CASE WHEN i.tracking_mode='bulk' THEN i.quantity ELSE 1 END ELSE 0 END),0) AS used
                FROM locations l LEFT JOIN items i ON i.location_id=l.id WHERE l.active=TRUE GROUP BY l.id,l.capacity) x""")
            return self._json({'ok':True,'stats':stats,'categories':cats,'low_stock':low,'recent':recent,'location_stats':locs})
        finally: conn.close()

    def api_items(self, user, qs):
        q = (qs.get('q',[''])[0] or '').strip(); status=(qs.get('status',[''])[0] or '').strip(); limit=safe_int(qs.get('limit',['500'])[0],500,1,3000)
        sql = """SELECT i.*,l.code AS location_code,l.zone,l.rack,l.shelf,l.position,
                 TRIM(CONCAT_WS(' / ',NULLIF('Zona '||l.zone,'Zona '),NULLIF('Est. '||l.rack,'Est. '),NULLIF('Balda '||l.shelf,'Balda '),NULLIF('Pos. '||l.position,'Pos. '))) AS location
                 FROM items i LEFT JOIN locations l ON l.id=i.location_id WHERE 1=1"""
        params=[]
        if q:
            sql += " AND (i.category ILIKE %s OR i.manufacturer ILIKE %s OR i.model ILIKE %s OR i.serial_number ILIKE %s OR i.asset_tag ILIKE %s OR l.code ILIKE %s)"
            term=f'%{q}%'; params += [term]*6
        if status: sql += ' AND i.status=%s'; params.append(status)
        sql += ' ORDER BY i.updated_at DESC,i.id DESC LIMIT %s'; params.append(limit)
        conn=connect(); rows=all_rows(conn,sql,tuple(params)); conn.close()
        for r in rows: r['allowed_actions']=allowed_actions(r)
        return self._json({'ok':True,'items':rows})

    def api_item_history(self, user, item_id):
        conn=connect()
        item=one(conn,"""SELECT i.*,l.code AS location_code FROM items i LEFT JOIN locations l ON l.id=i.location_id WHERE i.id=%s""",(item_id,))
        if not item: conn.close(); return self._error('Material no encontrado',404)
        hist=all_rows(conn,"""SELECT m.*,fl.code AS from_location,tl.code AS to_location FROM movements m LEFT JOIN locations fl ON fl.id=m.from_location_id LEFT JOIN locations tl ON tl.id=m.to_location_id WHERE m.item_id=%s ORDER BY m.id DESC""",(item_id,)); conn.close()
        item['allowed_actions']=allowed_actions(item)
        return self._json({'ok':True,'item':item,'history':hist})

    def api_movements(self, user, qs):
        limit=safe_int(qs.get('limit',['500'])[0],500,1,3000)
        conn=connect(); rows=all_rows(conn,"""SELECT m.*,i.manufacturer,i.model,i.category,i.serial_number,i.asset_tag,fl.code AS from_location,tl.code AS to_location
            FROM movements m JOIN items i ON i.id=m.item_id LEFT JOIN locations fl ON fl.id=m.from_location_id LEFT JOIN locations tl ON tl.id=m.to_location_id ORDER BY m.id DESC LIMIT %s""",(limit,)); conn.close()
        return self._json({'ok':True,'movements':rows})

    def api_locations(self, user, qs):
        q=(qs.get('q',[''])[0] or '').strip(); conn=connect()
        sql="""SELECT l.*,COALESCE(SUM(CASE WHEN i.status='disponible' THEN CASE WHEN i.tracking_mode='bulk' THEN i.quantity ELSE 1 END ELSE 0 END),0) AS used_units
               FROM locations l LEFT JOIN items i ON i.location_id=l.id WHERE l.active=TRUE"""; params=[]
        if q:
            sql += ' AND (l.code ILIKE %s OR l.zone ILIKE %s OR l.rack ILIKE %s OR l.shelf ILIKE %s OR l.position ILIKE %s)'; term=f'%{q}%'; params=[term]*5
        sql += ' GROUP BY l.id ORDER BY l.zone,l.rack,l.shelf,l.position,l.code'
        rows=all_rows(conn,sql,tuple(params)); conn.close()
        for r in rows:
            r['free_units']=max(0,int(r['capacity'])-int(r['used_units'])) if int(r['capacity'])>0 else None
            r['label']=location_label(r)
        return self._json({'ok':True,'locations':rows})

    def api_warehouse_map(self, user):
        conn=connect(); rows=all_rows(conn,"""SELECT l.*,COALESCE(SUM(CASE WHEN i.status='disponible' THEN CASE WHEN i.tracking_mode='bulk' THEN i.quantity ELSE 1 END ELSE 0 END),0) AS used_units,
             STRING_AGG(DISTINCT NULLIF(TRIM(i.manufacturer||' '||i.model),''), ', ' ORDER BY NULLIF(TRIM(i.manufacturer||' '||i.model),'')) AS content
             FROM locations l LEFT JOIN items i ON i.location_id=l.id WHERE l.active=TRUE GROUP BY l.id ORDER BY l.zone,l.rack,l.shelf,l.position"""); conn.close()
        return self._json({'ok':True,'locations':rows})

    def api_location_items(self, user, location_id):
        conn=connect(); loc=one(conn,'SELECT * FROM locations WHERE id=%s AND active=TRUE',(location_id,))
        if not loc: conn.close(); return self._error('Ubicación no encontrada',404)
        rows=all_rows(conn,'SELECT * FROM items WHERE location_id=%s ORDER BY status,category,manufacturer,model',(location_id,)); conn.close(); loc['label']=location_label(loc)
        for r in rows: r['allowed_actions']=allowed_actions(r)
        return self._json({'ok':True,'location':loc,'items':rows})

    def _qr_png(self, value):
        if qrcode is None:
            return self._error('Falta qrcode. Ejecuta: python -m pip install -r requirements.txt', 503)
        img = qrcode.make(value)
        out = io.BytesIO(); img.save(out, format='PNG'); data = out.getvalue()
        self._headers(200, 'image/png', {'Cache-Control':'private, max-age=300'})
        self.wfile.write(data)

    def api_qr_location(self, user, location_id):
        conn=connect(); loc=one(conn,'SELECT code FROM locations WHERE id=%s AND active=TRUE',(location_id,)); conn.close()
        if not loc: return self._error('Ubicación no encontrada',404)
        return self._qr_png(loc['code'])

    def api_qr_item(self, user, item_id):
        conn=connect(); item=one(conn,'SELECT id,asset_tag,serial_number FROM items WHERE id=%s',(item_id,)); conn.close()
        if not item: return self._error('Material no encontrado',404)
        value=item['asset_tag'] or item['serial_number'] or f"ITEM:{item['id']}"
        return self._qr_png(value)

    def api_create_location(self, user, p):
        zone=str(p.get('zone','')).strip().upper(); rack=str(p.get('rack','')).strip().upper(); shelf=str(p.get('shelf','')).strip().upper(); position=str(p.get('position','')).strip().upper(); code=str(p.get('code','')).strip().upper() or normalize_code(zone,rack,shelf,position)
        if not zone or not rack or not shelf or not code: return self._error('Zona, estantería y balda son obligatorias')
        capacity=safe_int(p.get('capacity'),0,0,1000000); notes=str(p.get('notes','')).strip()[:2000]
        try:
            with transaction() as conn:
                row=execute(conn,"""INSERT INTO locations(code,zone,rack,shelf,position,capacity,notes) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *""",(code,zone,rack,shelf,position,capacity,notes))
                audit(conn,user,self,'location.create','location',row['id'],f'Ubicación {code} creada',{'capacity':capacity})
            row['label']=location_label(row); return self._json({'ok':True,'location':row},201)
        except Exception as e:
            if 'unique' in str(e).lower(): return self._error('Ya existe una ubicación con ese código',409)
            raise

    def api_create_item(self, user, p):
        mode=str(p.get('tracking_mode','serialized')).strip(); category=str(p.get('category','')).strip(); model=str(p.get('model','')).strip(); manufacturer=str(p.get('manufacturer','')).strip(); serial=str(p.get('serial_number','')).strip(); asset=str(p.get('asset_tag','')).strip(); notes=str(p.get('notes','')).strip()[:4000]; ticket=str(p.get('ticket','')).strip()[:200]; loc_id=safe_int(p.get('location_id'),0,0) or None
        if mode not in ('serialized','bulk') or not category or not model: return self._error('Modo, categoría y modelo son obligatorios')
        if mode=='serialized' and not (serial or asset): return self._error('Un equipo individualizado necesita serie o Asset Tag')
        quantity=1 if mode=='serialized' else safe_int(p.get('quantity'),0,0,1000000); min_stock=0 if mode=='serialized' else safe_int(p.get('min_stock'),0,0,1000000); status='disponible' if quantity>0 else 'sin_stock'
        if mode=='bulk' and quantity==0: return self._error('La entrada inicial requiere al menos una unidad',400)
        try:
            with transaction() as conn:
                loc=one(conn,'SELECT * FROM locations WHERE id=%s AND active=TRUE FOR UPDATE',(loc_id,)) if loc_id else None
                if loc_id and not loc: return self._error('Ubicación no válida',400)
                cap=ensure_capacity(conn,loc,quantity)
                if cap: return self._error(cap,409)
                item=execute(conn,"""INSERT INTO items(category,manufacturer,model,serial_number,asset_tag,tracking_mode,quantity,min_stock,status,location_id,notes)
                                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",(category,manufacturer,model,serial,asset,mode,quantity,min_stock,status,loc_id,notes))
                execute(conn,"""INSERT INTO movements(item_id,action,quantity,to_status,to_location_id,ticket,operator_user_id,operator_name,notes)
                                VALUES(%s,'entrada',%s,%s,%s,%s,%s,%s,%s)""",(item['id'],max(quantity,1),status,loc_id,ticket,user['id'],user['display_name'],'Alta de material'))
                audit(conn,user,self,'item.create','item',item['id'],f'Alta: {manufacturer} {model}'.strip(),{'tracking_mode':mode,'quantity':quantity,'location_id':loc_id,'ticket':ticket})
            return self._json({'ok':True,'item':item},201)
        except Exception as e:
            s=str(e).lower()
            if 'idx_items_serial_unique' in s or 'serial_number' in s and 'unique' in s: return self._error('El número de serie ya existe',409)
            if 'idx_items_asset_unique' in s or 'asset_tag' in s and 'unique' in s: return self._error('El Asset Tag ya existe',409)
            raise

    def api_create_movement(self, user, p):
        if 'quantity' in p and (isinstance(p['quantity'],bool) or not str(p['quantity']).isdigit() or not 1<=int(p['quantity'])<=1000000): return self._error('Cantidad inválida',400)
        if 'new_quantity' in p and (isinstance(p['new_quantity'],bool) or not str(p['new_quantity']).isdigit() or not 0<=int(p['new_quantity'])<=1000000): return self._error('Nuevo stock inválido',400)
        item_id=safe_int(p.get('item_id'),0,1); action=str(p.get('action','')).strip(); requested_qty=safe_int(p.get('quantity'),1,1,1000000); new_qty=safe_int(p.get('new_quantity'),-1,-1,1000000); to_loc_id=safe_int(p.get('to_location_id'),0,0) or None; person=str(p.get('person','')).strip()[:300]; ticket=str(p.get('ticket','')).strip()[:200]; notes=str(p.get('notes','')).strip()[:4000]
        with transaction() as conn:
            item=one(conn,'SELECT * FROM items WHERE id=%s FOR UPDATE',(item_id,))
            if not item: return self._error('Material no encontrado',404)
            if action not in allowed_actions(item): return self._error(f"Acción '{action}' no válida para el estado actual",409)
            from_status=item['status']; from_loc=item['location_id']; qty=1; to_status=from_status; final_loc=from_loc; final_qty=int(item['quantity'])
            if item['tracking_mode']=='bulk':
                available=int(item['quantity'])
                if action in ('salida','mover') and requested_qty>available:
                    return self._error('Cantidad superior al stock disponible',409)
                if action=='salida':
                    if not person: return self._error('Indica persona o departamento destinatario')
                    qty=requested_qty; final_qty=available-qty
                    to_status='disponible' if final_qty>0 else 'sin_stock'
                    final_loc=from_loc if final_qty>0 else None
                elif action=='entrada':
                    qty=requested_qty; final_qty=available+qty
                    to_status='disponible'
                    final_loc=from_loc or to_loc_id
                    if not final_loc: return self._error('Selecciona ubicación para recibir el stock')
                    if final_qty>1000000: return self._error('Stock máximo superado',409)
                elif action=='mover':
                    qty=requested_qty; final_loc=to_loc_id
                    if not final_loc: return self._error('Selecciona ubicación destino')
                    if final_loc==from_loc: return self._error('La ubicación destino es la actual',409)
                    if qty<available:
                        # El lote original permanece en origen; se crea otro lote en destino.
                        final_qty=available-qty
                        final_loc=from_loc
                elif action=='ajuste':
                    if new_qty<0: return self._error('Nuevo stock inválido')
                    qty=max(1,abs(new_qty-available)); final_qty=new_qty
                    to_status='disponible' if new_qty>0 else 'sin_stock'
                    final_loc=from_loc if new_qty>0 else None
                else: return self._error('Acción no válida para stock a granel',409)
            else:
                if action=='salida':
                    if not person: return self._error('Indica persona o destino')
                    to_status='entregado'; final_loc=None
                elif action=='devolucion':
                    to_status='disponible'; final_loc=to_loc_id
                    if not final_loc: return self._error('Selecciona ubicación de devolución')
                elif action=='mover':
                    final_loc=to_loc_id
                    if not final_loc: return self._error('Selecciona ubicación destino')
                    if final_loc==from_loc: return self._error('La ubicación destino es la actual',409)
                elif action=='reparacion': to_status='reparacion'; final_loc=None
                elif action=='baja': to_status='baja'; final_loc=None
            # Bloquear las ubicaciones implicadas en orden estable evita interbloqueos.
            location_ids=sorted({x for x in (from_loc, to_loc_id if action in ('mover','entrada') else None, final_loc) if x})
            locked={}
            for lid in location_ids:
                locked[lid]=one(conn,'SELECT * FROM locations WHERE id=%s AND active=TRUE FOR UPDATE',(lid,))
                if not locked[lid]: return self._error('Ubicación no válida',400)
            partial_move=(item['tracking_mode']=='bulk' and action=='mover' and qty<int(item['quantity']))
            target_loc=to_loc_id if partial_move else final_loc
            if target_loc:
                destination=locked[target_loc]
                extra=qty if partial_move else (final_qty if item['tracking_mode']=='bulk' else 1)
                excluding=item_id if target_loc==from_loc else None
                cap=ensure_capacity(conn,destination,extra,exclude_item_id=excluding)
                if cap: return self._error(cap,409)
            # La entrada en la misma ubicación cambia la cantidad total y debe validarse.
            if item['tracking_mode']=='bulk' and action=='entrada' and final_loc==from_loc and final_loc:
                cap=ensure_capacity(conn,locked[final_loc],final_qty,exclude_item_id=item_id)
                if cap: return self._error(cap,409)
            destination_item_id=None
            if partial_move:
                dest=execute(conn,"""INSERT INTO items(category,manufacturer,model,serial_number,asset_tag,tracking_mode,quantity,min_stock,status,location_id,notes,origin_item_id)
                    VALUES(%s,%s,%s,'','','bulk',%s,%s,'disponible',%s,%s,%s) RETURNING id""",
                    (item['category'],item['manufacturer'],item['model'],qty,item['min_stock'],to_loc_id,item['notes'],item_id))
                destination_item_id=dest['id']
            execute(conn,"""UPDATE items SET status=%s,location_id=%s,quantity=%s,updated_at=NOW(),version=version+1 WHERE id=%s""",(to_status,final_loc,final_qty,item_id))
            movement=execute(conn,"""INSERT INTO movements(item_id,action,quantity,from_status,to_status,from_location_id,to_location_id,person,ticket,operator_user_id,operator_name,notes,destination_item_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",(item_id,action,qty,from_status,to_status,from_loc,(to_loc_id if partial_move else final_loc),person,ticket,user['id'],user['display_name'],notes,destination_item_id))
            audit(conn,user,self,'movement.create','item',item_id,f'{action} sobre material {item_id}',{'movement_id':movement['id'],'quantity':qty,'from_status':from_status,'to_status':to_status,'from_location_id':from_loc,'to_location_id':(to_loc_id if partial_move else final_loc),'destination_item_id':destination_item_id,'ticket':ticket})
        return self._json({'ok':True,'movement':movement})

    def api_users(self, user):
        conn=connect(); rows=all_rows(conn,'SELECT id,username,display_name,role,active,created_at,updated_at,last_login_at FROM users ORDER BY display_name,username'); conn.close(); return self._json({'ok':True,'users':rows})

    def api_create_user(self, user, p):
        from security import hash_password
        username=str(p.get('username','')).strip().lower(); display=str(p.get('display_name','')).strip(); role=str(p.get('role','operator')).strip(); password=str(p.get('password',''))
        if not re.fullmatch(r'[a-z0-9._-]{3,64}',username): return self._error('Usuario inválido: 3-64 caracteres [a-z0-9._-]')
        if not display: return self._error('Nombre visible obligatorio')
        if role not in ROLE_LEVEL: return self._error('Rol inválido')
        try: ph=hash_password(password)
        except ValueError as e: return self._error(str(e))
        try:
            with transaction() as conn:
                row=execute(conn,'INSERT INTO users(username,display_name,password_hash,role) VALUES(%s,%s,%s,%s) RETURNING id,username,display_name,role,active,created_at',(username,display,ph,role))
                audit(conn,user,self,'user.create','user',row['id'],f'Usuario {username} creado',{'role':role})
            return self._json({'ok':True,'user':row},201)
        except Exception as e:
            if 'unique' in str(e).lower(): return self._error('El usuario ya existe',409)
            raise

    def api_update_user(self, user, target_id, p):
        role=p.get('role'); active=p.get('active'); password=p.get('password'); display=p.get('display_name')
        if target_id==user['id'] and active is False: return self._error('No puedes desactivar tu propia cuenta',409)
        from security import hash_password
        fields=[]; params=[]; changes={}
        if role is not None:
            if role not in ROLE_LEVEL: return self._error('Rol inválido')
            fields.append('role=%s'); params.append(role); changes['role']=role
        if active is not None:
            fields.append('active=%s'); params.append(bool(active)); changes['active']=bool(active)
        if display is not None:
            display=str(display).strip()
            if not display: return self._error('Nombre visible inválido')
            fields.append('display_name=%s'); params.append(display); changes['display_name']=display
        if password:
            try: ph=hash_password(str(password))
            except ValueError as e: return self._error(str(e))
            fields.append('password_hash=%s'); params.append(ph); changes['password']='changed'
        if not fields: return self._error('No hay cambios')
        fields.append('updated_at=NOW()'); params.append(target_id)
        with transaction() as conn:
            target=one(conn,'SELECT id,username,role,active FROM users WHERE id=%s FOR UPDATE',(target_id,))
            if not target: return self._error('Usuario no encontrado',404)
            removing_admin = target['role']=='admin' and target['active'] and ((role is not None and role!='admin') or active is False)
            if removing_admin:
                remaining=one(conn,"SELECT COUNT(*) AS n FROM users WHERE role='admin' AND active=TRUE AND id<>%s",(target_id,))
                if int(remaining['n']) < 1: return self._error('Debe quedar al menos un administrador activo',409)
            execute(conn,'UPDATE users SET '+','.join(fields)+' WHERE id=%s',tuple(params))
            if active is False or password: execute(conn,'DELETE FROM sessions WHERE user_id=%s',(target_id,))
            audit(conn,user,self,'user.update','user',target_id,f"Usuario {target['username']} actualizado",changes)
        return self._json({'ok':True})

    def api_audit(self, user, qs):
        limit=safe_int(qs.get('limit',['500'])[0],500,1,2000); actor=(qs.get('actor',[''])[0] or '').strip(); action=(qs.get('action',[''])[0] or '').strip(); sql='SELECT * FROM audit_log WHERE 1=1'; params=[]
        if actor: sql+=' AND actor_name ILIKE %s'; params.append(f'%{actor}%')
        if action: sql+=' AND action ILIKE %s'; params.append(f'%{action}%')
        sql+=' ORDER BY id DESC LIMIT %s'; params.append(limit)
        conn=connect(); rows=all_rows(conn,sql,tuple(params)); conn.close(); return self._json({'ok':True,'audit':rows})

    def _csv(self, filename, headers, rows):
        sio=io.StringIO(newline=''); writer=csv.writer(sio,delimiter=';'); writer.writerow(headers); writer.writerows(rows); data=('\ufeff'+sio.getvalue()).encode('utf-8'); self._headers(200,'text/csv; charset=utf-8',{'Content-Disposition':f'attachment; filename="{filename}"'}); self.wfile.write(data)

    def export_items(self,user):
        conn=connect(); rows=all_rows(conn,"""SELECT i.*,l.code AS location_code FROM items i LEFT JOIN locations l ON l.id=i.location_id ORDER BY i.id"""); conn.close(); return self._csv('inventario.csv',['ID','Categoría','Fabricante','Modelo','Serie','Asset','Modo','Cantidad','Estado','Ubicación','Notas'],[(r['id'],r['category'],r['manufacturer'],r['model'],r['serial_number'],r['asset_tag'],r['tracking_mode'],r['quantity'],r['status'],r['location_code'] or '',r['notes']) for r in rows])
    def export_movements(self,user):
        conn=connect(); rows=all_rows(conn,"""SELECT m.*,i.model,fl.code AS from_code,tl.code AS to_code FROM movements m JOIN items i ON i.id=m.item_id LEFT JOIN locations fl ON fl.id=m.from_location_id LEFT JOIN locations tl ON tl.id=m.to_location_id ORDER BY m.id DESC"""); conn.close(); return self._csv('movimientos.csv',['Fecha','Acción','Material','Cantidad','De','A','Persona','Ticket','Operador'],[(r['created_at'],r['action'],r['model'],r['quantity'],r['from_code'] or '',r['to_code'] or '',r['person'],r['ticket'],r['operator_name']) for r in rows])
    def export_locations(self,user):
        conn=connect(); rows=all_rows(conn,'SELECT * FROM locations WHERE active=TRUE ORDER BY code'); conn.close(); return self._csv('ubicaciones.csv',['Código','Zona','Estantería','Balda','Posición','Capacidad','Notas'],[(r['code'],r['zone'],r['rack'],r['shelf'],r['position'],r['capacity'],r['notes']) for r in rows])


def main():
    require_driver()
    print(f'IT Warehouse 404 v{VERSION}')
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    scheme = 'http'
    if TLS_CERT and TLS_KEY:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(TLS_CERT, TLS_KEY)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = 'https'
    print(f'Escuchando en {scheme}://{HOST}:{PORT}')
    if scheme == 'http' and HOST not in ('127.0.0.1','localhost'):
        print('AVISO: para cámara móvil usa HTTPS (WAREHOUSE_TLS_CERT/WAREHOUSE_TLS_KEY).')
    print('Ctrl+C para detener.')
    server.serve_forever()


if __name__ == '__main__':
    main()

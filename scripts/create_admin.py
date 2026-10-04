#!/usr/bin/env python3
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import getpass
import re
from db import transaction, one, execute
from security import hash_password

username = input('Usuario admin [admin]: ').strip().lower() or 'admin'
if not re.fullmatch(r'[a-z0-9._-]{3,64}', username):
    raise SystemExit('Usuario inválido.')
display = input('Nombre visible [Administrador]: ').strip() or 'Administrador'
p1 = getpass.getpass('Contraseña (mínimo 12 caracteres): ')
p2 = getpass.getpass('Repite contraseña: ')
if p1 != p2:
    raise SystemExit('Las contraseñas no coinciden.')
ph = hash_password(p1)
with transaction() as conn:
    existing = one(conn, 'SELECT id FROM users WHERE username=%s', (username,))
    if existing:
        execute(conn, 'UPDATE users SET display_name=%s,password_hash=%s,role=\'admin\',active=TRUE,updated_at=NOW() WHERE id=%s', (display,ph,existing['id']))
        execute(conn, 'DELETE FROM sessions WHERE user_id=%s', (existing['id'],))
        print('Administrador actualizado.')
    else:
        execute(conn, 'INSERT INTO users(username,display_name,password_hash,role) VALUES(%s,%s,%s,\'admin\')', (username,display,ph))
        print('Administrador creado.')

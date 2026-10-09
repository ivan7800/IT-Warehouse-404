"""Server-side access control checks with mocked authenticated sessions."""
import unittest
from server import AppHandler

class Probe(AppHandler):
    def __init__(self, role, csrf='secret'):
        self.role=role
        self.headers={'X-CSRF-Token':csrf}
        self.errors=[]
    def current_user(self):
        return None if self.role is None else {'role':self.role,'csrf_token':'secret'}
    def _error(self, message, status=400):
        self.errors.append(status)
        return {'ok':False,'error':message,'status':status}

class SecurityGuards(unittest.TestCase):
    def test_anonymous_denied(self):
        h=Probe(None)
        self.assertIsNone(h.require_user('viewer'))
        self.assertEqual(h.errors,[401])
    def test_viewer_cannot_write(self):
        h=Probe('viewer')
        self.assertIsNone(h.require_user('operator',csrf=True))
        self.assertEqual(h.errors,[403])
    def test_operator_cannot_manage_users(self):
        h=Probe('operator')
        self.assertIsNone(h.require_user('admin',csrf=True))
        self.assertEqual(h.errors,[403])
    def test_missing_csrf_denied(self):
        h=Probe('admin',csrf='')
        self.assertIsNone(h.require_user('operator',csrf=True))
        self.assertEqual(h.errors,[403])
    def test_wrong_csrf_denied(self):
        h=Probe('admin',csrf='incorrect')
        self.assertIsNone(h.require_user('operator',csrf=True))
        self.assertEqual(h.errors,[403])
    def test_valid_role_and_csrf(self):
        h=Probe('operator')
        self.assertIsNotNone(h.require_user('operator',csrf=True))
        self.assertEqual(h.errors,[])

if __name__=='__main__':unittest.main()

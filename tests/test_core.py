import unittest
from security import hash_password, verify_password, new_session_material, hash_session_token
from server import allowed_actions

class CoreTests(unittest.TestCase):
    def test_password_hash(self):
        h=hash_password('UnaClave-Muy-Segura-123')
        self.assertTrue(verify_password('UnaClave-Muy-Segura-123',h))
        self.assertFalse(verify_password('otra',h))
        self.assertNotIn('UnaClave-Muy-Segura-123',h)
    def test_session_material(self):
        token, token_hash, csrf, expires = new_session_material()
        self.assertEqual(hash_session_token(token), token_hash)
        self.assertGreater(len(token), 30); self.assertGreater(len(csrf), 20)
    def test_serialized_transitions(self):
        base={'tracking_mode':'serialized','quantity':1}
        self.assertEqual(set(allowed_actions({**base,'status':'disponible'})), {'salida','mover','reparacion','baja'})
        self.assertEqual(set(allowed_actions({**base,'status':'entregado'})), {'devolucion','reparacion','baja'})
        self.assertEqual(allowed_actions({**base,'status':'baja'}), [])
    def test_bulk_transitions(self):
        self.assertEqual(set(allowed_actions({'tracking_mode':'bulk','quantity':12,'status':'disponible'})), {'entrada','salida','mover','ajuste'})
        self.assertEqual(allowed_actions({'tracking_mode':'bulk','quantity':0,'status':'sin_stock'}), ['entrada','ajuste'])

if __name__=='__main__': unittest.main()

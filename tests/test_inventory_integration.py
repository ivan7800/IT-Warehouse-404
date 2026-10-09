"""Integration tests against a dedicated, disposable PostgreSQL database.
Never run against production: requires WAREHOUSE_TEST_DATABASE=1.
"""
import os
import threading
import unittest
from db import transaction, one, execute
from server import AppHandler
from security import hash_password

if os.environ.get('WAREHOUSE_TEST_DATABASE') != '1':
    raise SystemExit('Refusing to mutate database: set WAREHOUSE_TEST_DATABASE=1 on disposable DB only')

class Handler(AppHandler):
    def __init__(self): self.client_address=('127.0.0.1', 0); self.headers={'User-Agent':'integration-test'}
    def _error(self, message, status=400): return {'ok':False,'error':message,'status':status}
    def _json(self, payload, status=200, extra=None): return {**payload,'status_code':status}

class InventoryIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with transaction() as c:
            cls.uid=execute(c,"INSERT INTO users(username,display_name,password_hash,role) VALUES('ci_operator','CI operator',%s,'admin') RETURNING id",(hash_password('CI-integration-password-2026'),))['id']
            cls.a=execute(c,"INSERT INTO locations(code,zone,rack,shelf,capacity) VALUES('CI-A','CI','A','1',100) RETURNING id")['id']
            cls.b=execute(c,"INSERT INTO locations(code,zone,rack,shelf,capacity) VALUES('CI-B','CI','B','1',10) RETURNING id")['id']
        cls.actor={'id':cls.uid,'display_name':'CI operator','role':'admin'}
    @classmethod
    def tearDownClass(cls):
        with transaction() as c:
            execute(c,"DELETE FROM audit_log WHERE actor_user_id=%s",(cls.uid,)) if False else None
            # audit_log is append-only; intentionally retain it in the disposable test DB.
            execute(c,"DELETE FROM movements WHERE operator_user_id=%s",(cls.uid,))
            execute(c,"DELETE FROM items WHERE category='CI TEST' AND origin_item_id IS NOT NULL")
            execute(c,"DELETE FROM items WHERE category='CI TEST'")
            execute(c,"DELETE FROM locations WHERE id IN (%s,%s)",(cls.a,cls.b))
            execute(c,"DELETE FROM users WHERE id=%s",(cls.uid,))
    def create(self,qty=20):
        res=Handler().api_create_item(self.actor,{'tracking_mode':'bulk','category':'CI TEST','model':'Keyboard','quantity':qty,'location_id':self.a})
        self.assertTrue(res['ok'],res)
        return res['item']['id']
    def movement(self,item,action,quantity=1,**kwargs):
        return Handler().api_create_movement(self.actor,dict(item_id=item,action=action,quantity=quantity,**kwargs))
    def test_entries_issues_transfers_and_capacity(self):
        item=self.create()
        self.assertTrue(self.movement(item,'entrada',5)['ok'])
        self.assertTrue(self.movement(item,'salida',4,person='Department')['ok'])
        self.assertEqual(self.movement(item,'salida',100,person='Department')['status'],409)
        move=self.movement(item,'mover',6,to_location_id=self.b)
        self.assertTrue(move['ok'],move)
        with transaction() as c:
            origin=one(c,'SELECT quantity FROM items WHERE id=%s',(item,))
            dest=one(c,'SELECT quantity,origin_item_id FROM items WHERE origin_item_id=%s ORDER BY id DESC LIMIT 1',(item,))
            link=one(c,'SELECT destination_item_id FROM movements WHERE id=%s',(move['movement']['id'],))
            self.assertEqual(origin['quantity'],15)
            self.assertEqual(dest['quantity'],6)
            self.assertEqual(link['destination_item_id'],one(c,'SELECT id FROM items WHERE origin_item_id=%s ORDER BY id DESC LIMIT 1',(item,))['id'])
        self.assertEqual(self.movement(item,'mover',15,to_location_id=self.b)['status'],409)
    def test_concurrent_issues(self):
        item=self.create(1)
        gate=threading.Barrier(2)
        results=[]
        def worker():
            gate.wait()
            results.append(self.movement(item,'salida',1,person='CI'))
        threads=[threading.Thread(target=worker) for _ in range(2)]
        for t in threads:t.start()
        for t in threads:t.join(timeout=15)
        self.assertEqual(len(results),2)
        self.assertEqual(sum(bool(x.get('ok')) for x in results),1,results)
        with transaction() as c:
            self.assertEqual(one(c,'SELECT quantity FROM items WHERE id=%s',(item,))['quantity'],0)
    def test_zero_quantity_rejected(self):
        res=Handler().api_create_item(self.actor,{'tracking_mode':'bulk','category':'CI TEST','model':'Bad','quantity':0,'location_id':self.a})
        self.assertFalse(res['ok'])
        item=self.create(2)
        self.assertFalse(self.movement(item,'salida',0,person='CI')['ok'])

if __name__=='__main__':unittest.main()

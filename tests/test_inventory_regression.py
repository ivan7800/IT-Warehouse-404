"""Regression checks that do not require a database."""
import unittest
from pathlib import Path
from server import AppHandler

class Handler(AppHandler):
    def __init__(self):
        pass
    def _error(self, message, status=400):
        return {'ok': False, 'error': message, 'status': status}

class InventoryRegression(unittest.TestCase):
    def setUp(self):
        self.handler = Handler()
        self.user = {'id': 1, 'display_name': 'test'}

    def test_initial_zero_bulk_rejected(self):
        response = self.handler.api_create_item(self.user, {'tracking_mode':'bulk','category':'test','model':'test','quantity':0})
        self.assertEqual(response['status'],400)

    def test_invalid_quantities_rejected_before_db(self):
        for value in [0,-1,'texto',True,'1.5',1000001]:
            with self.subTest(value=value):
                response=self.handler.api_create_movement(self.user, {'item_id':1,'action':'salida','quantity':value})
                self.assertEqual(response['status'],400)

    def test_invalid_adjustment_rejected_before_db(self):
        for value in [-1, 'abc', False, 1000001]:
            with self.subTest(value=value):
                response=self.handler.api_create_movement(self.user, {'item_id':1,'action':'ajuste','new_quantity':value})
                self.assertEqual(response['status'],400)

    def test_lineage_schema_exists(self):
        schema=(Path(__file__).resolve().parents[1]/'schema_postgresql.sql').read_text()
        self.assertIn('origin_item_id',schema)
        self.assertIn('destination_item_id',schema)

if __name__ == '__main__': unittest.main()

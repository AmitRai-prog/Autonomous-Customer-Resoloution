"""
Unit tests for enterprise tools and state mutations using standard unittest.
"""

import unittest
from backend.database import seed_db, get_db
from backend.tools import (
    customer_db_lookup,
    order_api_lookup,
    inventory_api_check,
    refund_action,
    replace_action,
    cancel_action,
)


class TestEnterpriseTools(unittest.TestCase):
    def setUp(self):
        seed_db(force=True)

    def test_customer_lookup(self):
        res = customer_db_lookup("alice.morgan@example.com")
        self.assertTrue(res["found"])
        self.assertEqual(res["name"], "Alice Morgan")
        self.assertEqual(res["tier"], "regular")
        self.assertGreaterEqual(len(res["order_history"]), 1)

    def test_order_lookup(self):
        res = order_api_lookup("ord_101")
        self.assertTrue(res["found"])
        self.assertEqual(res["status"], "delivered")
        self.assertEqual(res["sku"], "SKU-HEADPHONES-BLK")

    def test_inventory_check(self):
        res_avail = inventory_api_check("SKU-HEADPHONES-BLK")
        self.assertTrue(res_avail["in_stock"])
        self.assertGreater(res_avail["quantity"], 0)

        res_zero = inventory_api_check("SKU-SPEAKER-PORT")
        self.assertFalse(res_zero["in_stock"])
        self.assertEqual(res_zero["quantity"], 0)

    def test_refund_action(self):
        res = refund_action("ord_101", reason="Customer requested return within window")
        self.assertTrue(res["success"])
        self.assertEqual(res["new_order_status"], "refund_processing")

        with get_db() as conn:
            status = conn.execute("SELECT status FROM orders WHERE order_id = 'ord_101'").fetchone()[0]
            self.assertEqual(status, "refund_processing")

    def test_replace_action_blocked_when_out_of_stock(self):
        res = replace_action("ord_104", "SKU-SPEAKER-PORT")
        self.assertFalse(res["success"])
        self.assertTrue(res["blocked"])
        self.assertIn("Out of stock", res["blocked_reason"])

    def test_replace_action_success_when_in_stock(self):
        initial_stock = inventory_api_check("SKU-EARBUDS-WHT")["quantity"]
        res = replace_action("ord_113", "SKU-EARBUDS-WHT")
        self.assertTrue(res["success"])
        self.assertFalse(res["blocked"])
        self.assertEqual(res["new_order_status"], "replacement_processing")
        self.assertEqual(res["new_inventory_level"], initial_stock - 1)

    def test_cancel_action(self):
        res = cancel_action("ord_105", reason="Customer changed mind before shipping")
        self.assertTrue(res["success"])
        self.assertEqual(res["new_order_status"], "cancelled")

        res_shipped = cancel_action("ord_111", reason="Customer wants to cancel shipped order")
        self.assertFalse(res_shipped["success"])
        self.assertTrue(res_shipped["blocked"])


if __name__ == "__main__":
    unittest.main()

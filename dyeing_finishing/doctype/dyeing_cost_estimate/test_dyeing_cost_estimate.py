import unittest

import frappe

from dyeing_finishing.dyeing_finishing.doctype.dyeing_cost_estimate.dyeing_cost_estimate import (
    _recipe_quantity_kg,
)


class TestDyeingCostEstimate(unittest.TestCase):
    def test_recipe_quantity_conversion(self):
        self.assertEqual(_recipe_quantity_kg(2, "%owf", 100), 2)
        self.assertEqual(_recipe_quantity_kg(5, "g/kg", 100), 0.5)
        self.assertEqual(_recipe_quantity_kg(1.5, "g/L", 100, "1:10"), 1.5)
        self.assertEqual(_recipe_quantity_kg(3, "kg", 100), 3)

    def test_g_per_l_requires_bath_ratio(self):
        self.assertRaises(frappe.ValidationError, _recipe_quantity_kg, 1.5, "g/L", 100, "")

    def test_cost_summary(self):
        doc = frappe.get_doc({
            "doctype": "Dyeing Cost Estimate",
            "estimate_qty": 100,
            "expected_yield_rate": 95,
            "target_gross_margin_rate": 20,
            "order_amount": 1000,
            "cost_items": [
                {"cost_category": "染料", "description": "染料", "quantity": 2, "unit_rate": 50, "amount": 100},
                {"cost_category": "蒸汽", "description": "蒸汽", "quantity": 1, "unit_rate": 200, "amount": 200},
                {"cost_category": "人工", "description": "人工", "quantity": 2, "unit_rate": 50, "amount": 100},
            ],
        })
        doc._calculate_totals()
        self.assertEqual(doc.total_cost, 400)
        self.assertEqual(doc.unit_cost, 4)
        self.assertEqual(doc.estimated_output_qty, 95)
        self.assertEqual(doc.gross_profit, 600)
        self.assertEqual(doc.gross_margin_rate, 60)
        self.assertEqual(doc.suggested_quote_rate, 5)

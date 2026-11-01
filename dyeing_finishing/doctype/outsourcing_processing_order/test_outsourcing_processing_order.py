import unittest

import frappe

from dyeing_finishing.dyeing_finishing.doctype.outsourcing_processing_order.outsourcing_processing_order import _pricing_quantity


class TestOutsourcingProcessingOrder(unittest.TestCase):
	def test_pricing_quantity(self):
		self.assertEqual(_pricing_quantity("按公斤", 10, 125.5, 600), 125.5)
		self.assertEqual(_pricing_quantity("按匹", 10, 125.5, 600), 10)
		self.assertEqual(_pricing_quantity("按码", 10, 125.5, 600), 600)

	def test_calculate_totals_by_weight(self):
		doc = frappe.get_doc({"doctype": "Outsourcing Processing Order", "pricing_basis": "按公斤", "unit_rate": 2.5,
			"items": [{"batch_no": "B1", "planned_roll_count": 3, "planned_weight": 40}, {"batch_no": "B2", "planned_roll_count": 2, "planned_weight": 25.5}]})
		doc._calculate_totals()
		self.assertEqual(doc.planned_roll_count, 5)
		self.assertEqual(doc.planned_weight, 65.5)
		self.assertEqual(doc.billing_qty, 65.5)
		self.assertEqual(doc.estimated_processing_fee, 163.75)

	def test_batch_pricing_defaults_to_one(self):
		doc = frappe.get_doc({"doctype": "Outsourcing Processing Order", "pricing_basis": "按批", "unit_rate": 300,
			"items": [{"batch_no": "B1", "planned_roll_count": 1, "planned_weight": 10}]})
		doc._calculate_totals()
		self.assertEqual(doc.billing_qty, 1)
		self.assertEqual(doc.estimated_processing_fee, 300)

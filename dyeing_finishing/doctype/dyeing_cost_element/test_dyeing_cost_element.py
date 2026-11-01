import frappe
from frappe.tests.utils import FrappeTestCase


class TestDyeingCostElement(FrappeTestCase):
	def test_code_is_normalized(self):
		company = frappe.db.get_single_value("Global Defaults", "default_company")
		if not company:
			self.skipTest("Default company is required")
		doc = frappe.get_doc({
			"doctype": "Dyeing Cost Element",
			"element_code": " ce-unit-check ",
			"element_name": "单元校验成本要素",
			"cost_category": "其他",
			"cost_nature": "直接成本",
			"cost_behavior": "变动成本",
			"default_calculation_basis": "按实际用量",
			"company": company,
		})
		doc.insert()
		self.assertEqual(doc.name, "CE-UNIT-CHECK")

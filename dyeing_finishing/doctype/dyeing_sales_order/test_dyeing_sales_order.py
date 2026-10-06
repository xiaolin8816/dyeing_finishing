import frappe
from frappe.tests.utils import FrappeTestCase

from dyeing_finishing.dyeing_finishing.doctype.dyeing_sales_order.dyeing_sales_order import DyeingSalesOrder


class TestDyeingSalesOrder(FrappeTestCase):
    def test_finished_specification(self):
        item = frappe._dict(finished_width="180cm", finished_gsm="200", finished_gsm_uom="g/㎡")
        self.assertEqual(DyeingSalesOrder._make_finished_specification(item), "180cm*200g/㎡")

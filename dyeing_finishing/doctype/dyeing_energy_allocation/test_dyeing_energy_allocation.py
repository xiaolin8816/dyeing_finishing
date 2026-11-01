import unittest
from decimal import Decimal
from types import SimpleNamespace

from frappe.utils import get_datetime

from dyeing_finishing.dyeing_finishing.doctype.dyeing_energy_allocation.dyeing_energy_allocation import (
	_actual_basis,
	_meter_scopes_overlap,
	split_amount,
)


class TestEnergyAllocationCalculation(unittest.TestCase):
	def test_quantity_remainder_is_exact(self):
		parts = split_amount("1.000001", [1, 1, 1])
		self.assertEqual(sum(parts), Decimal("1.000001"))
		self.assertEqual(parts, [Decimal("0.333334"), Decimal("0.333334"), Decimal("0.333333")])

	def test_small_amount_never_allocates_negative(self):
		parts = split_amount("0.000001", [1, 1, 1])
		self.assertEqual(sum(parts), Decimal("0.000001"))
		self.assertTrue(all(part >= 0 for part in parts))

	def test_partial_interval_uses_overlap(self):
		actual = SimpleNamespace(
			name="ACT-1", actual_start="2026-10-27 10:00:00",
			actual_end="2026-10-27 12:00:00", completed_qty=100, uom="Kg",
		)
		start, end = get_datetime("2026-10-27 11:00:00"), get_datetime("2026-10-27 13:00:00")
		self.assertEqual(_actual_basis(actual, start, end, "按实际工时"), Decimal(1))
		self.assertEqual(_actual_basis(actual, start, end, "按合格重量"), Decimal(50))

	def test_overlapping_meter_scope(self):
		center = SimpleNamespace(
			energy_type="电", scope_type="工段", work_center="WC-DYE", production_resource=None,
		)
		machine = SimpleNamespace(
			energy_type="电", scope_type="机台", work_center="WC-DYE", production_resource="RES-1",
		)
		self.assertTrue(_meter_scopes_overlap(center, machine))
		machine.energy_type = "水"
		self.assertFalse(_meter_scopes_overlap(center, machine))

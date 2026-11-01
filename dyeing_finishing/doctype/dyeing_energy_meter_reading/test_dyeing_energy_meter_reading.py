import unittest

import frappe

from dyeing_finishing.dyeing_finishing.doctype.dyeing_energy_meter_reading.dyeing_energy_meter_reading import (
	calculate_consumption,
)


class TestEnergyConsumption(unittest.TestCase):
	def test_normal_reading(self):
		self.assertEqual(calculate_consumption(100, 125, 2, "正常"), 50)

	def test_zero_consumption(self):
		self.assertEqual(calculate_consumption(100, 100, 1, "正常"), 0)

	def test_rollover(self):
		self.assertEqual(calculate_consumption(9990, 10, 1.5, "翻表", 10000), 30)

	def test_decreasing_reading_requires_rollover(self):
		with self.assertRaises(frappe.ValidationError):
			calculate_consumption(100, 90, 1, "正常")

	def test_rollover_requires_capacity(self):
		with self.assertRaises(frappe.ValidationError):
			calculate_consumption(100, 10, 1, "翻表")

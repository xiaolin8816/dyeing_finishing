import unittest

from dyeing_finishing.dyeing_finishing.doctype.dyeing_cost_estimate.dyeing_cost_estimate import (
	_rate_line_quantity,
)


class TestDyeingCostRateStandard(unittest.TestCase):
	def test_rate_line_quantity(self):
		self.assertEqual(_rate_line_quantity("每公斤", 0.1, 100, 2), 10)
		self.assertEqual(_rate_line_quantity("每批", 3, 100, 2), 3)
		self.assertEqual(_rate_line_quantity("每小时", 2, 100, 3), 6)
		self.assertEqual(_rate_line_quantity("固定金额", 8, 100, 3), 1)

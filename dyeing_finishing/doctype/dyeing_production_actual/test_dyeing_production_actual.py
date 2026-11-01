import unittest
from types import SimpleNamespace
from unittest.mock import patch

from dyeing_finishing.dyeing_finishing.doctype.dyeing_production_actual.dyeing_production_actual import (
	ensure_dyeing_production_actual,
)


class TestDyeingProductionActual(unittest.TestCase):
	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_production_actual.dyeing_production_actual.frappe")
	def test_existing_actual_is_reused(self, frappe_mock):
		report = SimpleNamespace(name="REPORT-1", docstatus=1, operation_name="染色")
		frappe_mock.get_all.return_value = [SimpleNamespace(name="ACTUAL-1")]
		self.assertEqual(ensure_dyeing_production_actual(report), "ACTUAL-1")
		frappe_mock.get_doc.assert_not_called()

	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_production_actual.dyeing_production_actual._", side_effect=lambda value: value)
	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_production_actual.dyeing_production_actual.frappe")
	def test_new_actual_is_created_as_draft(self, frappe_mock, _translate):
		report = SimpleNamespace(
			name="REPORT-1", docstatus=1, operation_name="染色", report_time="2026-10-30 08:00:00",
		)
		frappe_mock.get_all.return_value = []
		doc = SimpleNamespace(name="ACTUAL-1", insert=lambda **kwargs: None)
		frappe_mock.get_doc.return_value = doc
		self.assertEqual(ensure_dyeing_production_actual(report), "ACTUAL-1")
		values = frappe_mock.get_doc.call_args.args[0]
		self.assertEqual(values["production_operation_report"], "REPORT-1")
		self.assertEqual(values["process_type"], "正常")


if __name__ == "__main__":
	unittest.main()

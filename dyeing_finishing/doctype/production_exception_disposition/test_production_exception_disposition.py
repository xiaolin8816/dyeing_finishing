import unittest
from types import SimpleNamespace
from unittest.mock import patch

from frappe import _dict
from dyeing_finishing.dyeing_finishing.doctype.production_exception_disposition.production_exception_disposition import (
	ProductionExceptionDisposition, disposition_gaps, get_flow_card_batches,
)


MODULE = "dyeing_finishing.dyeing_finishing.doctype.production_exception_disposition.production_exception_disposition"


class TestProductionExceptionDisposition(unittest.TestCase):
	@patch(f"{MODULE}.frappe")
	def test_flow_card_batches_are_deduplicated_and_permission_checked(self, frappe_mock):
		card = SimpleNamespace(grey_fabric_issues=[_dict(batch_no="B-2"), _dict(batch_no="B-1"), _dict(batch_no="B-1")],
			check_permission=lambda permission: self.assertEqual(permission, "read"))
		frappe_mock.get_doc.return_value = card
		self.assertEqual(get_flow_card_batches("PFC-1"), ["B-1", "B-2"])
		frappe_mock.get_doc.assert_called_once_with("Production Flow Card", "PFC-1")

	@patch(f"{MODULE}.frappe")
	@patch(f"{MODULE}._", side_effect=lambda text: text)
	def test_one_batch_whole_card_is_auto_recorded(self, _translate, frappe_mock):
		card = _dict(grey_fabric_issues=[_dict(batch_no="B-1")])
		doc = _dict(impact_scope="整卡/整缸", batch_no=None, roll_no=None, affected_items=[])
		ProductionExceptionDisposition._validate_affected_scope(doc, card)
		self.assertEqual(doc.batch_no, "B-1")
		self.assertIn("B-1", doc.trace_summary)

	@patch(f"{MODULE}.frappe")
	@patch(f"{MODULE}._", side_effect=lambda text: text)
	def test_single_roll_requires_confirmed_roll_number(self, _translate, frappe_mock):
		frappe_mock.throw.side_effect = ValueError("missing roll")
		card = _dict(grey_fabric_issues=[_dict(batch_no="B-1")])
		doc = _dict(impact_scope="指定匹号", batch_no="B-1", roll_no="", affected_items=[])
		with self.assertRaisesRegex(ValueError, "missing roll"):
			ProductionExceptionDisposition._validate_affected_scope(doc, card)

	@patch(f"{MODULE}.frappe")
	@patch(f"{MODULE}._", side_effect=lambda text: text)
	def test_multi_batch_rejects_foreign_and_overlapping_rows(self, _translate, frappe_mock):
		frappe_mock.throw.side_effect = ValueError("invalid")
		card = _dict(grey_fabric_issues=[_dict(batch_no="B-1"), _dict(batch_no="B-2")])
		doc = _dict(impact_scope="多个批次/匹号", batch_no=None, roll_no=None,
			affected_items=[_dict(idx=1, batch_no="B-1", roll_no=""), _dict(idx=2, batch_no="B-3", roll_no="R-3")])
		with self.assertRaisesRegex(ValueError, "invalid"):
			ProductionExceptionDisposition._validate_affected_scope(doc, card)
		doc.affected_items[1].batch_no = "B-1"
		with self.assertRaisesRegex(ValueError, "invalid"):
			ProductionExceptionDisposition._validate_affected_scope(doc, card)
		doc.affected_items[0].roll_no = "R-1"
		ProductionExceptionDisposition._validate_affected_scope(doc, card)
		self.assertEqual(doc.trace_summary, "B-1/R-1、B-1/R-3")

	@patch(f"{MODULE}.frappe")
	@patch(f"{MODULE}._", side_effect=lambda text: text)
	def test_report_quantities_require_full_approved_coverage(self, _translate, frappe_mock):
		frappe_mock.get_all.side_effect = [
			[_dict(name="BG-1", loss_qty=2, defective_qty=1, rework_qty=0)],
			[],
		]
		frappe_mock.db.exists.return_value = None
		approved = [SimpleNamespace(production_operation_report="BG-1", exception_type="损耗", affected_qty=1,
			                         dyeing_production_actual=None)]
		gaps = disposition_gaps("PFC-1", approved)
		self.assertEqual(len(gaps), 2)
		self.assertTrue(any("损耗" in gap for gap in gaps))
		self.assertTrue(any("次品" in gap for gap in gaps))

	@patch(f"{MODULE}.frappe")
	@patch(f"{MODULE}._", side_effect=lambda text: text)
	def test_actual_with_text_needs_linked_approved_disposition(self, _translate, frappe_mock):
		frappe_mock.get_all.side_effect = [[], [SimpleNamespace(
			name="DYSJ-1", process_type="正常", exception_description="色差", additional_treatment="",
		)]]
		frappe_mock.db.exists.return_value = None
		self.assertEqual(len(disposition_gaps("PFC-1", [])), 1)

	@patch(f"{MODULE}.frappe")
	@patch(f"{MODULE}._", side_effect=lambda text: text)
	def test_report_and_linked_actual_are_not_double_counted(self, _translate, frappe_mock):
		frappe_mock.get_all.side_effect = [
			[_dict(name="BG-1", loss_qty=1, defective_qty=0, rework_qty=0)],
			[SimpleNamespace(name="DYSJ-1", process_type="追加处理", exception_description="", additional_treatment="复染")],
		]
		frappe_mock.db.exists.return_value = None
		approved = [SimpleNamespace(production_operation_report="BG-1", exception_type="损耗", affected_qty=1,
			                         dyeing_production_actual="DYSJ-1")]
		self.assertEqual(disposition_gaps("PFC-1", approved), [])

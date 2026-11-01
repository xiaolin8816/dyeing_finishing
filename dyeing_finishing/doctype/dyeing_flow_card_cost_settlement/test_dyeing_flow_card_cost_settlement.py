import unittest
from types import SimpleNamespace
from unittest.mock import patch

from dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement import (
	_apply_manual_prices,
	_classify_exception_cost,
	_finished_receipts,
	_production_rate_rows,
	_select_hourly_rate,
	DyeingFlowCardCostSettlement,
	can_generate_from_flow_card,
	sync_settlement_from_source,
)


class TestFlowCardCostSettlement(unittest.TestCase):
	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement.frappe")
	def test_exception_cost_is_classification_of_existing_rows(self, frappe_mock):
		frappe_mock.db.get_value.return_value = "SE-1"
		rows = [
			{"source_doctype": "Stock Entry", "source_name": "SE-1", "amount": 12},
			{"source_doctype": "Stock Entry", "source_name": "SE-2", "amount": 20},
			{"source_doctype": "Dyeing Energy Allocation", "source_name": "EA-1", "amount": 5},
			{"source_doctype": "Dyeing Production Actual", "source_name": "ACT-1", "amount": 8},
		]
		dispositions = [SimpleNamespace(
			name="CZ-1", material_issue="MI-1", energy_allocation="EA-1", dyeing_production_actual="ACT-1",
		)]
		_classify_exception_cost(rows, dispositions)
		self.assertEqual([row["cost_bucket"] for row in rows], ["异常", "正常", "异常", "异常"])
		self.assertEqual(sum(row["amount"] for row in rows), 45)
		self.assertEqual(sum(row["amount"] for row in rows if row["cost_bucket"] == "异常"), 25)

	def test_specific_machine_rate_preferred_over_general_rate(self):
		actual = SimpleNamespace(operation="OP-DYE", production_resource="RES-DYE-100")
		rates = [
			SimpleNamespace(idx=1, cost_category="机台", calculation_basis="每小时", production_operation=None,
				work_center=None, production_resource=None, unit_rate=50),
			SimpleNamespace(idx=2, cost_category="机台", calculation_basis="每小时", production_operation=None,
				work_center="WC-DYE", production_resource="RES-DYE-100", unit_rate=65),
		]
		self.assertEqual(_select_hourly_rate(rates, "机台", actual, "WC-DYE").unit_rate, 65)

	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement._applicable_rate_standard")
	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement._", side_effect=lambda value: value)
	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement.frappe")
	def test_packaging_and_overhead_rates_use_output_weight_and_batch(self, frappe_mock, _translate, standard_mock):
		standard_mock.return_value = SimpleNamespace(name="RATE-1")
		frappe_mock.db.get_value.return_value = "COMP-1"
		frappe_mock.get_all.return_value = [
			SimpleNamespace(idx=1, cost_element="CE-PACKAGING", cost_category="包装", cost_item="包装费",
				calculation_basis="每公斤", standard_consumption=1, uom="Kg", unit_rate=0.15,
				standard_cost=0.15, production_operation=None, work_center=None, production_resource=None),
			SimpleNamespace(idx=2, cost_element="CE-BATCH-OVERHEAD", cost_category="间接费用", cost_item="批次费用",
				calculation_basis="固定金额", standard_consumption=1, uom=None, unit_rate=50,
				standard_cost=50, production_operation=None, work_center=None, production_resource=None),
		]
		rows, missing = _production_rate_rows(SimpleNamespace(company="COMP-1"), 177, "2026-10-27")
		self.assertFalse(missing)
		self.assertEqual([row["amount"] for row in rows], [26.55, 50.0])

	def test_manual_price_only_fills_zero_valuation(self):
		rows = [{
			"source_doctype": "Stock Entry", "source_name": "SE-1", "source_detail": "SLE-1",
			"quantity": 0.024, "amount": 0, "pricing_status": "待计价", "remarks": "库存出库",
		}, {
			"source_doctype": "Stock Entry", "source_name": "SE-1", "source_detail": "SLE-2",
			"quantity": 1, "amount": 5, "pricing_status": "已计价", "remarks": "库存出库",
		}]
		with patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement._", side_effect=lambda value: value):
			_apply_manual_prices(rows, {("SE-1", "SLE-1"): (3, "用户确认"), ("SE-1", "SLE-2"): (4, "用户确认")})
		self.assertEqual(rows[0]["amount"], 0.07)
		self.assertEqual(rows[0]["pricing_status"], "人工补录")
		self.assertEqual(rows[1]["amount"], 5)
		self.assertEqual(rows[1]["pricing_status"], "已计价")

	def test_energy_price_only_fills_zero_rate_allocation(self):
		rows = [{
			"source_doctype": "Dyeing Energy Allocation", "source_name": "EA-1", "source_detail": "EAI-1",
			"quantity": 12.5, "amount": 0, "pricing_status": "待计价", "remarks": "能源分摊",
		}, {
			"source_doctype": "Dyeing Energy Allocation", "source_name": "EA-1", "source_detail": "EAI-2",
			"quantity": 10, "amount": 8, "pricing_status": "费率测算", "remarks": "能源分摊",
		}]
		with patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement._", side_effect=lambda value: value):
			_apply_manual_prices(rows, {("EA-1", "EAI-1"): (0.8, "能源账单"), ("EA-1", "EAI-2"): (2, "能源账单")})
		self.assertEqual(rows[0]["amount"], 10)
		self.assertEqual(rows[0]["pricing_status"], "人工补录")
		self.assertEqual(rows[1]["amount"], 8)
		self.assertEqual(rows[1]["pricing_status"], "费率测算")

	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement.frappe")
	def test_finished_receipt_requires_submitted_stock_entry(self, frappe_mock):
		frappe_mock.get_all.return_value = [
			type("Receipt", (), {"stock_entry": "SE-1", "total_weight": 77})(),
			type("Receipt", (), {"stock_entry": "SE-2", "total_weight": 50})(),
		]
		frappe_mock.db.get_value.side_effect = lambda doctype, name, field: {"SE-1": 1, "SE-2": 2}[name]
		self.assertEqual(len(_finished_receipts("PFC-1")), 1)
		frappe_mock.get_all.assert_called_once_with(
			"Finished Product Packing Receipt",
			filters={"production_flow_card": "PFC-1", "docstatus": 1, "packing_status": "已入库"},
			fields=["name", "packing_date", "stock_entry", "total_weight"],
		)

	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement._finished_receipts", return_value=[object()])
	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement.frappe")
	def test_generate_button_hidden_after_settlement_exists(self, frappe_mock, _receipts):
		frappe_mock.get_doc.return_value = SimpleNamespace(docstatus=1, check_permission=lambda action: None)
		frappe_mock.db.exists.return_value = "LZCB-1"
		self.assertFalse(can_generate_from_flow_card("PFC-1"))

	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement.sync_cost_settlement")
	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement._source_flow_cards", return_value={"PFC-1"})
	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement.frappe")
	def test_finished_receipt_submit_creates_settlement(self, frappe_mock, _flow_cards, sync_mock):
		frappe_mock.generate_hash.return_value = "savepoint"
		doc = SimpleNamespace(doctype="Finished Product Packing Receipt")
		sync_settlement_from_source(doc, method="on_submit")
		sync_mock.assert_called_once_with("PFC-1", create=True)

	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement.sync_cost_settlement")
	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement._source_flow_cards", return_value={"PFC-1"})
	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement.frappe")
	def test_other_sources_only_refresh_existing_settlement(self, frappe_mock, _flow_cards, sync_mock):
		frappe_mock.generate_hash.return_value = "savepoint"
		doc = SimpleNamespace(doctype="Dyeing Energy Allocation")
		sync_settlement_from_source(doc, method="on_submit")
		sync_mock.assert_called_once_with("PFC-1", create=False)

	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement._", side_effect=lambda value: value)
	@patch("dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement.frappe")
	def test_save_rejects_second_active_settlement(self, frappe_mock, _translate):
		frappe_mock.db.exists.return_value = "LZCB-1"
		frappe_mock.throw.side_effect = ValueError("duplicate")
		doc = SimpleNamespace(name="LZCB-2", production_flow_card="PFC-1", is_new=lambda: True)
		with self.assertRaisesRegex(ValueError, "duplicate"):
			DyeingFlowCardCostSettlement.validate(doc)
		frappe_mock.db.sql.assert_called_once_with(
			"SELECT name FROM `tabProduction Flow Card` WHERE name = %s FOR UPDATE", "PFC-1"
		)

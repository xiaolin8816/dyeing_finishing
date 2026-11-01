from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from dyeing_finishing.dyeing_finishing.doctype.grey_fabric_issue import grey_fabric_issue
from dyeing_finishing.dyeing_finishing.doctype.production_flow_card import production_flow_card


class TestGreyFabricReservation(TestCase):
    @patch.object(production_flow_card, "frappe")
    def test_rework_card_uses_original_cards_company(self, mocked_frappe):
        mocked_frappe.db.get_value.return_value = "Company-1"
        card = SimpleNamespace(sales_order=None, original_flow_card="CARD-1", company=None)

        production_flow_card.ProductionFlowCard._set_company(card)

        self.assertEqual(card.company, "Company-1")
        mocked_frappe.db.get_value.assert_called_once_with("Production Flow Card", "CARD-1", "company")

    @patch.object(production_flow_card, "get_grey_fabric_reservations")
    def test_available_stock_subtracts_unissued_reservations(self, reservations):
        reservations.return_value = {("B-1", "W-1"): frappe._dict(rolls=3, qty=60)}
        rows = [frappe._dict(batch_no="B-1", location="W-1", stock_roll_count=10, stock_qty=200)]

        production_flow_card.add_grey_fabric_availability(rows)

        self.assertEqual((rows[0].available_roll_count, rows[0].available_qty), (7, 140))

    @patch.object(production_flow_card, "get_grey_fabric_reservations")
    def test_issue_reduces_stock_and_remaining_reservation_once(self, reservations):
        reservations.return_value = {("B-1", "W-1"): frappe._dict(rolls=2, qty=40)}
        rows = [frappe._dict(batch_no="B-1", location="W-1", stock_roll_count=6, stock_qty=120)]

        production_flow_card.add_grey_fabric_availability(rows)

        self.assertEqual((rows[0].available_roll_count, rows[0].available_qty), (4, 80))

    def test_duplicate_plan_rows_cannot_exceed_available_stock(self):
        rows = [
            frappe._dict(batch_no="B-1", location="W-1", planned_roll_count=3, planned_qty=50,
                available_roll_count=5, available_qty=100),
            frappe._dict(batch_no="B-1", location="W-1", planned_roll_count=3, planned_qty=50,
                available_roll_count=5, available_qty=100),
        ]
        card = SimpleNamespace(get=lambda field: rows)

        with patch.object(production_flow_card, "_", lambda message: message), patch.object(
            frappe, "throw", side_effect=frappe.ValidationError
        ), self.assertRaises(frappe.ValidationError):
            production_flow_card.ProductionFlowCard._validate_grey_fabric_reservation(card)

    @patch.object(grey_fabric_issue, "lock_grey_fabric_batches")
    @patch.object(grey_fabric_issue, "get_batch_stock_details")
    def test_issue_cannot_use_another_cards_reservation(self, stock, lock):
        stock.return_value = frappe._dict(available_roll_count=2, available_qty=40)
        issue = SimpleNamespace(
            customer="Customer", _validate_items=lambda: None,
            items=[frappe._dict(batch_no="B-1", location="W-1", issue_roll_count=3, issue_qty=50)],
        )

        with patch.object(grey_fabric_issue, "_", lambda message: message), patch.object(
            frappe, "throw", side_effect=frappe.ValidationError
        ), self.assertRaises(frappe.ValidationError):
            grey_fabric_issue.GreyFabricIssue._validate_available_after_issue(issue)
        lock.assert_called_once()

    @patch.object(production_flow_card, "frappe")
    @patch.object(production_flow_card, "get_batch_stock_details")
    def test_reopening_fully_issued_card_needs_no_stock(self, stock, mocked_frappe):
        mocked_frappe.db.sql.return_value = [frappe._dict(rolls=5, qty=100)]
        row = frappe._dict(name="PLAN-1", batch_no="B-1", location="W-1", planned_roll_count=5, planned_qty=100)
        card = SimpleNamespace(name="CARD-1", get=lambda field: [row])

        production_flow_card.validate_reopened_card_reservations(card)

        stock.assert_not_called()

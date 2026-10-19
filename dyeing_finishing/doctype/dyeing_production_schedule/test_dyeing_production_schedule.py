import unittest
from datetime import datetime
from unittest.mock import patch

import frappe

from dyeing_finishing.dyeing_finishing.doctype.dyeing_production_schedule import dyeing_production_schedule as schedule


class TestBoardRules(unittest.TestCase):
	def test_sequential_slot_skips_overlapping_blocks(self):
		at = lambda hour: datetime(2030, 12, 1, hour)
		self.assertEqual(schedule._next_free_slot(at(8), 2, at(20), [
			(at(9), at(11)), (at(10), at(12)), (at(15), at(16)),
		]), (at(12), at(14)))

	def test_slot_allows_adjacent_tasks_but_rejects_insufficient_time(self):
		at = lambda hour: datetime(2030, 12, 1, hour)
		self.assertEqual(schedule._next_free_slot(at(8), 1, at(10),
			[(at(9), at(10))]), (at(8), at(9)))
		self.assertIsNone(schedule._next_free_slot(at(8), 2, at(10),
			[(at(9), at(10))]))
		self.assertIsNone(schedule._next_free_slot(at(8), 0, at(10), []))

	def test_optional_requirements_do_not_block(self):
		result = schedule._readiness("CARD", "", {}, {
			"grey": {"CARD"}, "recipe": set(), "material": set(),
		})
		self.assertEqual(result["readiness_status"], "可以排产")
		self.assertEqual(result["readiness_missing"], [])

	def test_required_recipe_needs_nonblank_color(self):
		result = schedule._readiness("CARD", "", {"requires_recipe": 1}, {
			"grey": {"CARD"}, "recipe": {""}, "material": set(),
		})
		self.assertEqual(result["readiness_missing"], ["配方未确认"])

	def test_required_material_is_checked(self):
		result = schedule._readiness("CARD", "C001", {"requires_material_ready": 1}, {
			"grey": {"CARD"}, "recipe": set(), "material": set(),
		})
		self.assertEqual(result["readiness_missing"], ["染料未齐套"])

	def test_duration_includes_setup_and_cleaning(self):
		self.assertEqual(schedule._suggested_hours(100, {
			"time_calculation_method": "按生产数量", "minutes_per_kg": 2,
			"setup_minutes": 20, "cleaning_minutes": 20,
		}), 4)
		self.assertEqual(schedule._suggested_hours(100, {"fixed_batch_minutes": 90}), 1.5)
		self.assertEqual(schedule._suggested_hours(100, {}), 1)

	def test_draft_card_is_rejected(self):
		card = frappe._dict(docstatus=0, production_status="进行中",
			check_permission=lambda permission: None)
		with patch.object(schedule.frappe, "get_doc", return_value=card):
			with self.assertRaises(frappe.ValidationError):
				schedule.get_task_details("CARD", "OP")

	def test_repeated_operation_requires_row_identity(self):
		card = frappe._dict(docstatus=1, production_status="进行中",
			check_permission=lambda permission: None,
			operations=[frappe._dict(name=name, operation="OP", operation_status="未开始")
				for name in ("ROW1", "ROW2")])
		with patch.object(schedule.frappe, "get_doc", return_value=card):
			with self.assertRaises(frappe.ValidationError):
				schedule.get_task_details("CARD", "OP")

	def test_publish_requires_submit_permission(self):
		with patch.object(schedule.frappe, "has_permission",
			side_effect=[True, frappe.PermissionError]) as permission:
			with self.assertRaises(frappe.PermissionError):
				schedule.create_schedule_from_task("CARD", "OP", "RESOURCE",
					"2026-12-01 08:00:00", "2026-12-01 09:00:00")
			self.assertEqual(permission.call_args.args[1], "submit")

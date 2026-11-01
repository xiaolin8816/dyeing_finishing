import re

import frappe
from frappe import _
from frappe.model.document import Document


class DyeingCostElement(Document):
	def validate(self):
		self.element_code = _normalize_code(self.element_code)
		self.element_name = (self.element_name or "").strip()
		self.company = self.company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
			"Global Defaults", "default_company"
		)
		if not self.company:
			frappe.throw(_("请先设置默认公司"))
		if not self.element_name:
			frappe.throw(_("请填写成本要素名称"))
		self._validate_expense_account()

	def _validate_expense_account(self):
		if not self.expense_account:
			return
		account = frappe.db.get_value(
			"Account", self.expense_account, ["company", "is_group", "root_type"], as_dict=True
		)
		if not account or account.company != self.company:
			frappe.throw(_("对应费用科目必须属于当前公司"))
		if account.is_group:
			frappe.throw(_("对应费用科目不能选择汇总科目"))
		if account.root_type != "Expense":
			frappe.throw(_("对应费用科目必须是费用类科目"))


def _normalize_code(value):
	value = re.sub(r"\s+", "-", (value or "").strip().upper())
	if not value:
		frappe.throw(_("请填写要素编码"))
	if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]*", value):
		frappe.throw(_("要素编码只能使用英文字母、数字、下划线和短横线"))
	return value

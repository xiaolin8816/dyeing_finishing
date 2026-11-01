import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ProcessingContractor(Document):
	def before_insert(self):
		self.contractor_code = self.name

	def validate(self):
		self.contractor_name = (self.contractor_name or "").strip()
		self.company = self.company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
			"Global Defaults", "default_company"
		)
		if not self.company:
			frappe.throw(_("请先设置默认公司"))
		self.currency = self.currency or frappe.db.get_value("Company", self.company, "default_currency")
		if not self.contractor_name:
			frappe.throw(_("请填写加工商名称"))
		if flt(self.allowed_loss_rate) > 100:
			frappe.throw(_("默认允许损耗率不能大于 100%"))
		self._validate_supplier()

	def _validate_supplier(self):
		if not self.supplier:
			return
		supplier = frappe.db.get_value("Supplier", self.supplier, ["supplier_name", "disabled"], as_dict=True)
		if not supplier:
			frappe.throw(_("关联结算供应商不存在"))
		if supplier.disabled:
			frappe.throw(_("关联结算供应商 {0} 已停用").format(self.supplier))
		self.supplier_name = supplier.supplier_name


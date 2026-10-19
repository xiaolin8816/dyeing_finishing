import frappe
from frappe import _
from frappe.model.document import Document


class EmployeeOperationPermission(Document):
	def validate(self):
		if frappe.db.exists("Employee Operation Permission", {
			"employee": self.employee,
			"name": ["!=", self.name],
		}):
			frappe.throw(_("员工 {0} 已有工序设置，请在原设置单中维护").format(
				self.employee_name or self.employee
			))
		if not self.operations:
			frappe.throw(_("请至少设置一个可操作工序"))
		seen = set()
		for row in self.operations:
			if row.operation in seen:
				frappe.throw(_("可操作工序不能重复：{0}").format(row.operation_name or row.operation))
			seen.add(row.operation)


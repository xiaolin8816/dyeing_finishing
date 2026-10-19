import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime


class MachineProductionCalendar(Document):
	def before_insert(self):
		self.maintenance_no = self.name

	def validate(self):
		self.maintenance_no = self.name
		if get_datetime(self.end_datetime) <= get_datetime(self.start_datetime):
			frappe.throw(_("预计恢复时间必须晚于停机开始时间。"))
		conflict = frappe.db.sql("""SELECT name FROM `tabMachine Production Calendar`
			WHERE name != %(name)s AND docstatus < 2 AND production_resource=%(resource)s
			AND start_datetime < %(end)s AND end_datetime > %(start)s LIMIT 1""",
			{"name":self.name or "", "resource":self.production_resource, "start":self.start_datetime, "end":self.end_datetime})
		if conflict:
			frappe.throw(_("该设备或班组的停机时间与记录 {0} 重叠。").format(conflict[0][0]))

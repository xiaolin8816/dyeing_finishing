import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class DyeingEnergyMeter(Document):
	def validate(self):
		self.company = self.company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
			"Global Defaults", "default_company"
		)
		if not self.company:
			frappe.throw(_("请先设置默认公司"))
		if self.scope_type == "机台":
			if not self.production_resource:
				frappe.throw(_("机台表计必须选择生产机台"))
			self.work_center = frappe.db.get_value("Production Resource", self.production_resource, "work_center")
		elif self.scope_type == "工段":
			if not self.work_center:
				frappe.throw(_("工段表计必须选择生产工段"))
			self.production_resource = None
		elif self.scope_type == "总表":
			self.work_center = None
			self.production_resource = None
		else:
			frappe.throw(_("请选择表计范围"))
		if flt(self.multiplier) <= 0:
			frappe.throw(_("表计倍率必须大于零"))
		if flt(self.opening_reading) < 0:
			frappe.throw(_("启用读数不能小于零"))
		if self.rollover_capacity and flt(self.rollover_capacity) <= flt(self.opening_reading):
			frappe.throw(_("翻表容量必须大于启用读数"))
		if not self.opening_time:
			frappe.throw(_("请填写表计启用时间"))
		self._protect_reading_history()

	def _protect_reading_history(self):
		previous = self.get_doc_before_save()
		if not previous:
			return
		frappe.db.sql("SELECT name FROM `tabDyeing Energy Meter` WHERE name = %s FOR UPDATE", self.name)
		has_readings = frappe.db.sql("""
			SELECT 1 FROM `tabDyeing Energy Meter Reading Item` item
			JOIN `tabDyeing Energy Meter Reading` parent ON parent.name = item.parent
			WHERE item.meter = %s AND parent.docstatus = 1 LIMIT 1 FOR UPDATE
		""", self.name)
		if not has_readings:
			return
		locked = (
			"company", "energy_type", "scope_type", "work_center", "production_resource",
			"uom", "multiplier", "opening_time", "opening_reading", "rollover_capacity",
		)
		if any(previous.get(field) != self.get(field) for field in locked):
			frappe.throw(_("已有已提交抄表记录，不能修改表计口径；请新建表计档案"))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_energy_meters(doctype, txt, searchfield, start, page_len, filters, **kwargs):
	frappe.has_permission("Dyeing Energy Meter", ptype="read", throw=True)
	company = (filters or {}).get("company")
	if not company:
		return []
	search_text = f"%{txt}%" if txt else None
	meters = frappe.get_list(
		"Dyeing Energy Meter",
		filters={"company": company, "is_active": 1},
		or_filters={
			"meter_code": ["like", search_text],
			"meter_name": ["like", search_text],
			"energy_type": ["like", search_text],
			"scope_type": ["like", search_text],
		} if search_text else None,
		fields=["name", "meter_code", "meter_name", "energy_type", "scope_type", "uom"],
		order_by="meter_code asc",
		limit_start=start,
		limit_page_length=page_len,
	)
	return [{
		"name": meter.name,
		"表计编码": meter.meter_code,
		"表计名称": meter.meter_name,
		"能源类型": meter.energy_type,
		"计量范围": meter.scope_type,
		"单位": meter.uom,
	} for meter in meters]

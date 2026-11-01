import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, now_datetime


def calculate_consumption(previous, current, multiplier, method, capacity=None):
	previous, current, multiplier, capacity = map(flt, (previous, current, multiplier, capacity))
	if current < 0 or previous < 0 or multiplier <= 0:
		frappe.throw(_("表计读数和倍率无效"))
	if capacity and (previous >= capacity or current >= capacity):
		frappe.throw(_("表计读数不能达到或超过翻表容量"))
	if method == "正常":
		if current < previous:
			frappe.throw(_("本次读数小于上次读数，请核对或选择翻表"))
		difference = current - previous
	elif method == "翻表":
		if not capacity or current >= previous:
			frappe.throw(_("翻表必须设置翻表容量，且本次读数小于上次读数"))
		difference = capacity - previous + current
	else:
		frappe.throw(_("抄表方式无效"))
	return flt(difference * multiplier, 6)


def _latest_reading(meter, exclude=None, for_update=False):
	query = """
		SELECT item.current_reading, parent.reading_time, parent.name AS source
		FROM `tabDyeing Energy Meter Reading Item` item
		JOIN `tabDyeing Energy Meter Reading` parent ON parent.name = item.parent
		WHERE item.meter = %s AND parent.docstatus = 1 AND parent.name != %s
		ORDER BY parent.reading_time DESC, parent.creation DESC LIMIT 1
	"""
	return frappe.db.sql(query + (" FOR UPDATE" if for_update else ""), (meter, exclude or ""), as_dict=True)


class DyeingEnergyMeterReading(Document):
	def before_insert(self):
		self.reading_no = self.name
		self.reading_status = "草稿"

	def validate(self):
		self.reading_no = self.name
		self.reading_time = self.reading_time or now_datetime()
		self.company = self.company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
			"Global Defaults", "default_company"
		)
		if not self.company:
			frappe.throw(_("请先设置默认公司"))
		self._recalculate_items(require_current=False)
		self.meter_count = len(self.items)
		if self.docstatus == 0:
			self.reading_status = "草稿"

	def before_submit(self):
		if not self.items:
			frappe.throw(_("请至少选择一只能源表计"))
		for meter in sorted(row.meter for row in self.items):
			frappe.db.sql("SELECT name FROM `tabDyeing Energy Meter` WHERE name = %s FOR UPDATE", meter)
		self._recalculate_items(require_current=True)
		self.reading_status = "已提交"

	def before_cancel(self):
		frappe.db.sql(
			"SELECT name FROM `tabDyeing Energy Meter Reading` WHERE name = %s FOR UPDATE", self.name
		)
		if frappe.db.exists("DocType", "Dyeing Energy Allocation") and frappe.db.exists(
			"Dyeing Energy Allocation", {"source_reading": self.name, "docstatus": 1}
		):
			frappe.throw(_("此抄表单已有已提交的生产能源分摊单，请先取消分摊单"))
		for meter in sorted(row.meter for row in self.items):
			frappe.db.sql("SELECT name FROM `tabDyeing Energy Meter` WHERE name = %s FOR UPDATE", meter)
		for row in self.items:
			later = frappe.db.sql("""
				SELECT parent.name FROM `tabDyeing Energy Meter Reading Item` item
				JOIN `tabDyeing Energy Meter Reading` parent ON parent.name = item.parent
				WHERE item.meter = %s AND parent.docstatus = 1
				AND parent.name != %s AND parent.reading_time > %s LIMIT 1 FOR UPDATE
			""", (row.meter, self.name, self.reading_time))
			if later:
				frappe.throw(_("表计 {0} 已有后续抄表单 {1}，请先取消后续单据").format(row.meter, later[0][0]))

	def on_cancel(self):
		self.db_set("reading_status", "已取消", update_modified=False)

	def _recalculate_items(self, require_current):
		seen = set()
		for row in self.items:
			if not row.meter or row.meter in seen:
				frappe.throw(_("第 {0} 行表计为空或重复").format(row.idx))
			seen.add(row.meter)
			meter = frappe.get_doc("Dyeing Energy Meter", row.meter)
			if not meter.is_active or meter.company != self.company:
				frappe.throw(_("第 {0} 行表计已停用或所属公司不一致").format(row.idx))
			row.meter_name = meter.meter_name
			row.energy_type = meter.energy_type
			row.scope_type = meter.scope_type
			row.work_center = meter.work_center
			row.production_resource = meter.production_resource
			row.uom = meter.uom
			row.multiplier = meter.multiplier
			row.rollover_capacity = meter.rollover_capacity
			latest = _latest_reading(meter.name, self.name, for_update=require_current)
			if latest:
				latest = latest[0]
				if get_datetime(self.reading_time) <= get_datetime(latest.reading_time):
					frappe.throw(_("表计 {0} 的抄表时间必须晚于已提交单据 {1}").format(meter.name, latest.source))
				row.previous_reading = latest.current_reading
				row.previous_source = latest.source
			else:
				if get_datetime(self.reading_time) <= get_datetime(meter.opening_time):
					frappe.throw(_("表计 {0} 的抄表时间必须晚于启用时间").format(meter.name))
				row.previous_reading = meter.opening_reading
				row.previous_source = None
			if row.current_reading in (None, ""):
				row.consumption = 0
				if require_current:
					frappe.throw(_("第 {0} 行请填写本次读数").format(row.idx))
				continue
			row.reading_method = row.reading_method or "正常"
			if row.reading_method == "翻表" and not (row.remarks or "").strip():
				frappe.throw(_("第 {0} 行翻表请填写原因").format(row.idx))
			row.consumption = calculate_consumption(
				row.previous_reading, row.current_reading, row.multiplier,
				row.reading_method or "正常", row.rollover_capacity,
			)


@frappe.whitelist()
def get_meter_contexts(meters, reading_time, company=None):
	frappe.has_permission("Dyeing Energy Meter Reading", ptype="create", throw=True)
	if not reading_time:
		frappe.throw(_("请先填写抄表时间"))
	company = company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	meters = frappe.parse_json(meters) or []
	if not isinstance(meters, list) or len(meters) > 500:
		frappe.throw(_("请选择不超过 500 只表计"))
	result = []
	for name in dict.fromkeys(meters):
		meter = frappe.get_doc("Dyeing Energy Meter", name)
		meter.check_permission("read")
		if meter.company != company or not meter.is_active:
			frappe.throw(_("表计 {0} 已停用或所属公司不一致").format(name))
		latest = _latest_reading(name)
		if latest:
			latest = latest[0]
			if get_datetime(reading_time) <= get_datetime(latest.reading_time):
				frappe.throw(_("表计 {0} 的抄表时间必须晚于已提交单据 {1}").format(name, latest.source))
		else:
			if get_datetime(reading_time) <= get_datetime(meter.opening_time):
				frappe.throw(_("表计 {0} 的抄表时间必须晚于启用时间").format(name))
		result.append({
			"meter": meter.name,
			"meter_name": meter.meter_name,
			"energy_type": meter.energy_type,
			"scope_type": meter.scope_type,
			"work_center": meter.work_center,
			"production_resource": meter.production_resource,
			"uom": meter.uom,
			"multiplier": meter.multiplier,
			"rollover_capacity": meter.rollover_capacity,
			"previous_reading": latest.current_reading if latest else meter.opening_reading,
			"previous_source": latest.source if latest else None,
		})
	return result

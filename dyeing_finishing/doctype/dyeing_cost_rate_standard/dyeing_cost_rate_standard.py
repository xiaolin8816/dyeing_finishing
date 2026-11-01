import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate


RATE_CALCULATION_BASES = {"每公斤", "每批", "每小时", "固定金额"}


class DyeingCostRateStandard(Document):
	def before_insert(self):
		self.standard_no = self.name
		self.standard_date = self.standard_date or getdate(nowdate())
		self.standard_status = "草稿"
		self._set_company_defaults()
		self.standard_version = self.standard_version or _next_version(self.company)

	def validate(self):
		self.standard_no = self.name
		self.standard_date = self.standard_date or getdate(nowdate())
		self._set_company_defaults()
		self._validate_dates()
		self._validate_source_standard()
		self._validate_rate_items()
		self.rate_item_count = len(self.rate_items)

	def before_submit(self):
		if not self.rate_items:
			frappe.throw(_("请至少填写一条成本费率明细"))
		self.standard_status = "已提交"

	def on_cancel(self):
		self.db_set("standard_status", "已取消", update_modified=False)

	def _set_company_defaults(self):
		self.company = self.company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
			"Global Defaults", "default_company"
		)
		if not self.company:
			frappe.throw(_("请先设置默认公司"))
		self.currency = frappe.db.get_value("Company", self.company, "default_currency")

	def _validate_dates(self):
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("失效日期不能早于生效日期"))

	def _validate_source_standard(self):
		if not self.source_standard:
			return
		if self.source_standard == self.name:
			frappe.throw(_("来源费率标准不能是当前单据"))
		source = frappe.db.get_value(
			"Dyeing Cost Rate Standard",
			self.source_standard,
			["company", "docstatus"],
			as_dict=True,
		)
		if not source or source.docstatus != 1:
			frappe.throw(_("来源费率标准必须是已提交单据"))
		if source.company != self.company:
			frappe.throw(_("来源费率标准所属公司与当前单据不一致"))

	def _validate_rate_items(self):
		seen = set()
		for row in self.rate_items:
			if not row.cost_element:
				frappe.throw(_("第 {0} 行请选择成本要素").format(row.idx))
			element = frappe.get_cached_doc("Dyeing Cost Element", row.cost_element)
			if not element.is_active:
				frappe.throw(_("第 {0} 行成本要素 {1} 已停用").format(row.idx, element.element_name))
			if not element.enable_estimate:
				frappe.throw(_("第 {0} 行成本要素 {1} 未启用预计成本").format(row.idx, element.element_name))
			if element.company != self.company:
				frappe.throw(_("第 {0} 行成本要素所属公司与费率标准不一致").format(row.idx))
			row.cost_category = element.cost_category
			row.cost_item = row.cost_item or element.element_name
			row.uom = row.uom or element.default_uom
			if not row.calculation_basis and element.default_calculation_basis in RATE_CALCULATION_BASES:
				row.calculation_basis = element.default_calculation_basis
			if row.calculation_basis not in RATE_CALCULATION_BASES:
				frappe.throw(_("第 {0} 行计费方式无效").format(row.idx))
			if flt(row.standard_consumption) <= 0:
				frappe.throw(_("第 {0} 行标准用量必须大于零").format(row.idx))
			if flt(row.unit_rate) < 0:
				frappe.throw(_("第 {0} 行费用单价不能小于零").format(row.idx))
			row.standard_cost = flt(row.standard_consumption) * flt(row.unit_rate)
			key = (
				row.cost_element,
				row.calculation_basis,
				row.production_operation or "",
				row.work_center or "",
				row.production_resource or "",
			)
			if key in seen:
				frappe.throw(_("第 {0} 行存在重复的成本项目和适用范围").format(row.idx))
			seen.add(key)


@frappe.whitelist()
def get_rate_cost_elements(company=None, cost_elements=None):
	frappe.has_permission("Dyeing Cost Rate Standard", ptype="create", throw=True)
	company = company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	if not company:
		frappe.throw(_("请先设置默认公司"))
	filters = {
		"company": company,
		"is_active": 1,
		"enable_estimate": 1,
	}
	cost_elements = frappe.parse_json(cost_elements) if cost_elements else []
	if cost_elements:
		filters["name"] = ["in", cost_elements]
		selected = frappe.get_list(
			"Dyeing Cost Element",
			filters={"name": ["in", cost_elements]},
			fields=["name", "element_name", "company", "is_active", "enable_estimate"],
			limit_page_length=len(set(cost_elements)),
		)
		if len(selected) != len(set(cost_elements)):
			frappe.throw(_("所选成本要素不存在或无权读取，请刷新后重试"))
		for element in selected:
			if element.company != company:
				frappe.throw(_("成本要素 {0} 不属于当前公司").format(element.element_name))
			if not element.is_active:
				frappe.throw(_("成本要素 {0} 已停用").format(element.element_name))
			if not element.enable_estimate:
				frappe.throw(_("成本要素 {0} 未启用预计成本").format(element.element_name))

	elements = frappe.get_list(
		"Dyeing Cost Element",
		filters=filters,
		fields=[
			"name", "element_name", "cost_category", "default_uom", "default_calculation_basis"
		],
		order_by="cost_category asc, element_code asc",
		limit_page_length=len(set(cost_elements)) if cost_elements else 1000,
	)
	return [
		{
			"cost_element": element.name,
			"cost_category": element.cost_category,
			"cost_item": element.element_name,
			"calculation_basis": (
				element.default_calculation_basis
				if element.default_calculation_basis in RATE_CALCULATION_BASES else ""
			),
			"standard_consumption": 1,
			"uom": element.default_uom,
			"unit_rate": 0,
			"standard_cost": 0,
		}
		for element in elements
	]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_rate_cost_elements(doctype, txt, searchfield, start, page_len, filters, **kwargs):
	frappe.has_permission("Dyeing Cost Element", ptype="read", throw=True)
	search_text = f"%{txt}%" if txt else None
	elements = frappe.get_list(
		"Dyeing Cost Element",
		or_filters={
			"element_code": ["like", search_text],
			"element_name": ["like", search_text],
			"cost_category": ["like", search_text],
		} if search_text else None,
		fields=["name", "element_code", "element_name", "cost_category", "default_calculation_basis"],
		order_by="element_code asc",
		limit_start=start,
		limit_page_length=page_len,
	)
	return [
		{
			"name": element.name,
			"要素编码": element.element_code,
			"成本要素名称": element.element_name,
			"成本类别": element.cost_category,
			"默认计费方式": element.default_calculation_basis,
		}
		for element in elements
	]


@frappe.whitelist()
def make_new_version(source_name):
	frappe.has_permission("Dyeing Cost Rate Standard", ptype="create", throw=True)
	source = frappe.get_doc("Dyeing Cost Rate Standard", source_name)
	source.check_permission("read")
	if source.docstatus != 1:
		frappe.throw(_("只能从已提交的费率标准创建新版本"))

	new_doc = frappe.new_doc("Dyeing Cost Rate Standard")
	new_doc.update({
		"standard_date": getdate(nowdate()),
		"standard_status": "草稿",
		"effective_from": getdate(nowdate()),
		"applicable_order_type": source.applicable_order_type,
		"currency": source.currency,
		"company": source.company,
		"source_standard": source.name,
		"remarks": _("基于费率标准 {0} 创建，请复核用量和单价后提交。").format(source.name),
	})
	for row in source.rate_items:
		new_doc.append("rate_items", {
			"cost_element": row.cost_element,
			"cost_category": row.cost_category,
			"cost_item": row.cost_item,
			"calculation_basis": row.calculation_basis,
			"standard_consumption": row.standard_consumption,
			"uom": row.uom,
			"unit_rate": row.unit_rate,
			"standard_cost": row.standard_cost,
			"production_operation": row.production_operation,
			"work_center": row.work_center,
			"production_resource": row.production_resource,
			"remarks": row.remarks,
		})
	new_doc.rate_item_count = len(new_doc.rate_items)
	return new_doc


def _next_version(company):
	versions = frappe.get_all(
		"Dyeing Cost Rate Standard",
		filters={"company": company} if company else {},
		pluck="standard_version",
	)
	numbers = []
	for version in versions:
		match = re.fullmatch(r"V(\d+)", version or "")
		if match:
			numbers.append(int(match.group(1)))
	return f"V{max(numbers, default=0) + 1}"

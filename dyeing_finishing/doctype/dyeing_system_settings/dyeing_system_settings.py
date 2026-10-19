import frappe
from frappe import _
from frappe.model.document import Document


class DyeingSystemSettings(Document):
	def validate(self):
		warehouse_fields = (
			"production_transit_warehouse",
			"dye_material_warehouse",
			"finished_product_warehouse",
			"finished_product_return_warehouse",
			"return_rework_warehouse",
		)
		warehouse_companies = set()
		for fieldname in warehouse_fields:
			warehouse = self.get(fieldname)
			if not warehouse:
				frappe.throw(_("请填写 {0}").format(self.meta.get_label(fieldname)))
			row = frappe.db.get_value("Warehouse", warehouse, ["is_group", "disabled", "company"], as_dict=True)
			if not row or row.is_group or row.disabled:
				frappe.throw(_("{0} 必须是已启用的非分组仓库").format(self.meta.get_label(fieldname)))
			if row.company:
				warehouse_companies.add(row.company)
		if len(warehouse_companies) > 1:
			frappe.throw(_("印染系统设置中的默认仓库必须属于同一家公司"))
		default_company = frappe.defaults.get_global_default("company")
		if default_company and warehouse_companies and default_company not in warehouse_companies:
			frappe.throw(_("默认仓库必须属于当前默认公司 {0}").format(default_company))
		if self.dye_item_group == self.auxiliary_item_group:
			frappe.throw(_("染料物料组和助剂物料组不能相同"))
		if self.packing_weight_tolerance_percent < 0:
			frappe.throw(_("包装重量差异预警范围不能小于 0"))
		if not 1 <= self.license_reminder_days <= 180:
			frappe.throw(_("授权到期提醒天数应在 1 至 180 天之间"))

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import cint, getdate, now_datetime, nowdate


class FinishedProductBlankLabel(Document):
	def autoname(self):
		date = getdate(self.print_date or nowdate())
		prefix = f"BQ{date:%y%m%d}"
		self.name = f"{prefix}{getseries(prefix, 3)}"

	def before_insert(self):
		self.label_print_no = self.name
		self.print_date = self.print_date or getdate(nowdate())
		self.print_status = "保存"
		self._set_company()

	def validate(self):
		self.label_print_no = self.name
		self.print_date = self.print_date or getdate(nowdate())
		self._set_company()
		if cint(self.print_quantity) <= 0:
			frappe.throw(_("本次打印数量必须大于 0"))
		if cint(self.print_quantity) > 1000:
			frappe.throw(_("本次打印数量不能超过 1000 张"))
		if self.print_status == "已作废" and not self.is_new():
			frappe.throw(_("已作废的空白标签打印单不能修改"))
		self._set_flow_card_details()

	def _set_company(self):
		if self.production_flow_card:
			self.company = frappe.db.get_value("Production Flow Card", self.production_flow_card, "company") or self.company
		self.company = self.company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
			"Global Defaults", "default_company"
		)

	def _set_flow_card_details(self):
		if not self.production_flow_card:
			return
		values = get_blank_label_flow_card_details(self.production_flow_card)
		for fieldname, value in values.items():
			if fieldname == "composition" and self.composition:
				continue
			self.set(fieldname, value)


@frappe.whitelist()
def get_blank_label_flow_card_details(flow_card):
	if not flow_card or not frappe.db.exists("Production Flow Card", flow_card):
		frappe.throw(_("找不到生产流转卡 {0}").format(flow_card or ""))
	card = frappe.get_doc("Production Flow Card", flow_card)
	if card.docstatus != 1:
		frappe.throw(_("生产流转卡 {0} 尚未提交").format(flow_card))
	if card.production_status == "已关闭":
		frappe.throw(_("生产流转卡 {0} 已关闭，不能打印空白标签").format(flow_card))
	return {
		"company": card.company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company"),
		"flow_card_no": card.flow_card_no or card.name,
		"customer": card.customer,
		"customer_name": frappe.db.get_value("Customer", card.customer, "customer_name") or card.customer,
		"color_no": card.color_no,
		"color": card.color,
		"finished_product_name": card.finished_product_name,
		"finished_specification": card.finished_specification,
		"composition": "",
	}


@frappe.whitelist()
def create_from_packing_receipt(packing_receipt):
	"""从成品包装入库单生成或复用可用的空白标签打印记录。"""
	if not packing_receipt or not frappe.db.exists("Finished Product Packing Receipt", packing_receipt):
		frappe.throw(_("找不到成品包装入库单 {0}").format(packing_receipt or ""))
	receipt = frappe.get_doc("Finished Product Packing Receipt", packing_receipt)
	receipt.check_permission("read")
	if receipt.docstatus == 2 or receipt.packing_status == "已取消":
		frappe.throw(_("已取消的成品包装入库单不能打印标签"))
	if not receipt.production_flow_card:
		frappe.throw(_("成品包装入库单未关联生产流转卡"))

	existing = frappe.db.get_value(
		"Finished Product Blank Label",
		{"source_packing_receipt": receipt.name, "print_status": ["!=", "已作废"]},
		"name",
		order_by="creation desc",
	)
	quantity = len(receipt.items or []) or cint(receipt.total_roll_count) or 1
	if existing:
		label = frappe.get_doc("Finished Product Blank Label", existing)
		label.check_permission("write")
		label.print_quantity = quantity
		label.save()
	else:
		label = frappe.new_doc("Finished Product Blank Label")
		label.source_packing_receipt = receipt.name
		label.production_flow_card = receipt.production_flow_card
		label.print_date = receipt.packing_date or nowdate()
		label.print_quantity = quantity
		label.insert()

	return {"name": label.name, "print_quantity": quantity, "source_packing_receipt": receipt.name}


@frappe.whitelist()
def record_blank_label_print(name, print_quantity):
	doc = frappe.get_doc("Finished Product Blank Label", name)
	doc.check_permission("write")
	if doc.print_status == "已作废":
		frappe.throw(_("已作废的空白标签打印单不能打印"))
	quantity = cint(print_quantity)
	if quantity <= 0 or quantity > 1000:
		frappe.throw(_("本次打印数量应在 1 至 1000 张之间"))
	now = now_datetime()
	doc.db_set({
		"print_quantity": quantity,
		"print_status": "已打印",
		"print_count": cint(doc.print_count) + 1,
		"cumulative_print_quantity": cint(doc.cumulative_print_quantity) + quantity,
		"last_print_time": now,
		"last_printed_by": frappe.session.user,
	})
	doc.add_comment("Info", _("打印空白标签 {0} 张").format(quantity))
	return {"print_quantity": quantity, "print_status": "已打印"}


@frappe.whitelist()
def void_blank_label_print(name):
	doc = frappe.get_doc("Finished Product Blank Label", name)
	doc.check_permission("write")
	if doc.print_status == "已作废":
		return
	doc.db_set("print_status", "已作废")
	doc.add_comment("Info", _("空白标签打印单已作废"))

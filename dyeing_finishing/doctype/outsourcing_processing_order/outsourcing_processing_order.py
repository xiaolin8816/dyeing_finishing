import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate


OUTSOURCING_WAREHOUSE_NAME = "委外加工仓"


class OutsourcingProcessingOrder(Document):
	def before_insert(self):
		self.outsourcing_order_no = self.name

	def validate(self):
		self._set_source_details()
		self._set_processing_contractor_details()
		self._validate_operation()
		self._populate_items_if_empty()
		self._validate_items()
		self._calculate_totals()
		self._validate_dates()
		self._validate_duplicate()
		if self.docstatus == 0:
			self.outsourcing_status = "草稿"

	def before_submit(self):
		self.outsourcing_status = "待外发"

	def before_cancel(self):
		if self.purchase_order and frappe.db.get_value("Purchase Order", self.purchase_order, "docstatus") == 1:
			frappe.throw(_("采购订单 {0} 已提交，请先取消采购订单").format(self.purchase_order))
		self.outsourcing_status = "已取消"

	def _set_source_details(self):
		if not self.production_flow_card:
			return
		card = frappe.get_doc("Production Flow Card", self.production_flow_card)
		if self.is_new() and card.production_status in ("已关闭", "已完成"):
			frappe.throw(_("生产流转卡 {0} 已{1}，不能新建委外加工单").format(card.name, card.production_status[1:]))
		self.sales_order = card.sales_order
		self.customer = card.customer
		self.customer_name = frappe.db.get_value("Customer", card.customer, "customer_name") if card.customer else None
		self.customer_order_no = card.customer_order_no
		self.finished_product_name = card.finished_product_name
		self.color = card.color
		self.order_type = card.order_type
		self.company = card.company or _default_company()
		if self.company:
			self.currency = frappe.db.get_value("Company", self.company, "default_currency")

	def _set_processing_contractor_details(self):
		self.supplier_warehouse = get_outsourcing_warehouse(self.company)
		if not self.processing_contractor:
			self.supplier = None
			self.supplier_name = None
			return
		contractor = frappe.db.get_value(
			"Processing Contractor",
			self.processing_contractor,
			[
				"contractor_name", "status", "supplier", "supplier_name", "contact_person", "contact_phone",
				"currency", "default_pricing_basis", "allowed_loss_rate",
				"default_unit_rate", "service_item", "company",
			],
			as_dict=True,
		)
		if not contractor:
			frappe.throw(_("加工商 {0} 不存在").format(self.processing_contractor))
		if contractor.status != "启用":
			frappe.throw(_("加工商 {0} 已停用").format(contractor.contractor_name))
		if self.company and contractor.company != self.company:
			frappe.throw(_("加工商 {0} 不属于当前公司").format(contractor.contractor_name))
		if not contractor.supplier:
			frappe.throw(_("加工商 {0} 未关联结算供应商").format(contractor.contractor_name))
		self.processing_contractor_name = contractor.contractor_name
		self.supplier = contractor.supplier
		self.supplier_name = contractor.supplier_name or frappe.db.get_value(
			"Supplier", contractor.supplier, "supplier_name"
		)
		self.supplier_contact = self.supplier_contact or contractor.contact_person
		self.supplier_phone = self.supplier_phone or contractor.contact_phone
		self.currency = contractor.currency or self.currency
		self.pricing_basis = self.pricing_basis or contractor.default_pricing_basis
		self.allowed_loss_rate = self.allowed_loss_rate or contractor.allowed_loss_rate
		self.unit_rate = self.unit_rate or contractor.default_unit_rate
		self.service_item = self.service_item or contractor.service_item

	def _validate_operation(self):
		if not self.production_flow_card or not self.production_operation:
			return
		card = frappe.get_doc("Production Flow Card", self.production_flow_card)
		operation_row = next((row for row in card.operations if row.operation == self.production_operation), None)
		if not operation_row:
			frappe.throw(_("工序 {0} 不属于生产流转卡 {1}").format(self.production_operation, self.production_flow_card))
		self.operation_name = operation_row.operation_name or frappe.db.get_value(
			"Production Operation", self.production_operation, "production_operation_name"
		)
		self.operation_sequence = cint(operation_row.sequence_no)

	def _populate_items_if_empty(self):
		if self.items or not self.production_flow_card:
			return
		for item in _get_flow_card_payload(self.production_flow_card).get("items", []):
			self.append("items", item)

	def _validate_items(self):
		if not self.items:
			frappe.throw(_("请至少添加一条委外加工明细"))
		card_batches = set()
		if self.production_flow_card:
			card_batches = {
				row.batch_no for row in frappe.get_doc("Production Flow Card", self.production_flow_card).grey_fabric_issues
				if row.batch_no
			}
		seen = set()
		for row in self.items:
			if row.batch_no in seen:
				frappe.throw(_("第 {0} 行：胚布批次 {1} 重复").format(row.idx, row.batch_no))
			seen.add(row.batch_no)
			if card_batches and row.batch_no not in card_batches:
				frappe.throw(_("第 {0} 行：胚布批次 {1} 不属于所选生产流转卡").format(row.idx, row.batch_no))
			if flt(row.planned_roll_count) < 0 or flt(row.planned_weight) < 0 or flt(row.planned_yard_qty) < 0:
				frappe.throw(_("第 {0} 行：计划数量不能小于 0").format(row.idx))
			if not any((flt(row.planned_roll_count), flt(row.planned_weight), flt(row.planned_yard_qty))):
				frappe.throw(_("第 {0} 行：计划匹数、重量和码数不能全部为 0").format(row.idx))

	def _calculate_totals(self):
		self.planned_roll_count = sum(cint(row.planned_roll_count) for row in self.items)
		self.planned_weight = flt(sum(flt(row.planned_weight) for row in self.items), 3)
		self.planned_yard_qty = flt(sum(flt(row.planned_yard_qty) for row in self.items), 3)
		calculated_qty = _pricing_quantity(
			self.pricing_basis, self.planned_roll_count, self.planned_weight, self.planned_yard_qty
		)
		if self.pricing_basis in ("按公斤", "按匹", "按码"):
			self.billing_qty = calculated_qty
		elif self.pricing_basis == "按批" and not flt(self.billing_qty):
			self.billing_qty = 1
		if self.pricing_basis in ("按缸", "按批") and flt(self.billing_qty) <= 0:
			frappe.throw(_("按缸或按批计价时，计价数量必须大于 0"))
		self.estimated_processing_fee = flt(self.billing_qty) * flt(self.unit_rate)

	def _validate_dates(self):
		if self.planned_completion_date and self.order_date:
			if getdate(self.planned_completion_date) < getdate(self.order_date):
				frappe.throw(_("预计交期不能早于单据日期"))

	def _validate_duplicate(self):
		if not self.production_flow_card or not self.production_operation:
			return
		filters = {
			"production_flow_card": self.production_flow_card,
			"production_operation": self.production_operation,
			"docstatus": ["<", 2],
		}
		if self.name:
			filters["name"] = ["!=", self.name]
		duplicate = frappe.db.exists("Outsourcing Processing Order", filters)
		if duplicate:
			frappe.throw(_("生产流转卡 {0} 的工序 {1} 已存在委外加工单 {2}").format(
				self.production_flow_card, self.operation_name or self.production_operation, duplicate
			))


def _default_company():
	return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")


def get_outsourcing_warehouse(company, create=True):
	if not company:
		frappe.throw(_("请先确定委外加工单所属公司"))
	warehouse = frappe.db.get_value(
		"Warehouse", {"warehouse_name": OUTSOURCING_WAREHOUSE_NAME, "company": company},
		["name", "is_group", "disabled"], as_dict=True,
	)
	if warehouse:
		if warehouse.is_group:
			frappe.throw(_("仓库 {0} 必须是末级仓库").format(warehouse.name))
		if warehouse.disabled and create:
			frappe.db.set_value("Warehouse", warehouse.name, "disabled", 0)
		return warehouse.name
	if not create:
		return None
	warehouse_doc = frappe.get_doc({
		"doctype": "Warehouse",
		"warehouse_name": OUTSOURCING_WAREHOUSE_NAME,
		"company": company,
		"is_group": 0,
	})
	warehouse_doc.insert(ignore_permissions=True)
	return warehouse_doc.name


def _pricing_quantity(pricing_basis, roll_count, weight, yard_qty):
	return {"按公斤": flt(weight), "按匹": cint(roll_count), "按码": flt(yard_qty)}.get(pricing_basis, 0)


def _get_flow_card_payload(flow_card):
	card = frappe.get_doc("Production Flow Card", flow_card)
	operations = []
	for row in card.operations:
		operations.append({
			"name": row.operation,
			"operation_name": row.operation_name,
			"sequence_no": cint(row.sequence_no),
			"operation_status": row.operation_status,
			"scheduling_mode": frappe.db.get_value("Production Operation", row.operation, "scheduling_mode"),
		})
	items = []
	for row in card.grey_fabric_issues:
		if not row.batch_no:
			continue
		item_code = frappe.db.get_value("Batch", row.batch_no, "item")
		items.append({
			"batch_no": row.batch_no,
			"item_code": item_code,
			"grey_fabric_name": row.grey_fabric_name or (frappe.db.get_value("Item", item_code, "item_name") if item_code else None),
			"color": row.color,
			"source_warehouse": row.warehouse or row.location,
			"planned_roll_count": cint(row.planned_roll_count),
			"planned_weight": flt(row.planned_qty, 3),
			"planned_yard_qty": 0,
		})
	warehouses = {item["source_warehouse"] for item in items if item.get("source_warehouse")}
	return frappe._dict({
		"sales_order": card.sales_order,
		"customer": card.customer,
		"customer_name": frappe.db.get_value("Customer", card.customer, "customer_name") if card.customer else None,
		"customer_order_no": card.customer_order_no,
		"finished_product_name": card.finished_product_name,
		"color": card.color,
		"order_type": card.order_type,
		"company": card.company or _default_company(),
		"source_warehouse": next(iter(warehouses)) if len(warehouses) == 1 else None,
		"operations": operations,
		"items": items,
	})


@frappe.whitelist()
def get_flow_card_details(flow_card):
	if not flow_card or not frappe.db.exists("Production Flow Card", flow_card):
		frappe.throw(_("生产流转卡不存在"))
	return _get_flow_card_payload(flow_card)

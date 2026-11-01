import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime, nowdate


CHEMICAL_CATEGORIES = {"染料", "助剂"}
ENERGY_CATEGORIES = {"水", "电", "蒸汽", "天然气", "污水处理"}
DEFAULT_COST_ELEMENTS = {
    "胚布": "CE-GREY-FABRIC",
    "染料": "CE-DYE",
    "助剂": "CE-AUXILIARY",
    "水": "CE-WATER",
    "电": "CE-ELECTRICITY",
    "蒸汽": "CE-STEAM",
    "天然气": "CE-NATURAL-GAS",
    "污水处理": "CE-WASTEWATER",
    "人工": "CE-LABOR",
    "机台": "CE-MACHINE",
    "包装": "CE-PACKAGING",
    "委外": "CE-SUBCONTRACT",
    "间接费用": "CE-BATCH-OVERHEAD",
    "其他": "CE-OTHER",
}


class DyeingCostEstimate(Document):
    def before_insert(self):
        self.estimate_no = self.name
        self.estimate_date = self.estimate_date or getdate(nowdate())
        self.estimate_status = "草稿"
        self.estimate_version = self.estimate_version or _next_version(self.sales_order_item)

    def validate(self):
        self.estimate_no = self.name
        self.estimate_date = self.estimate_date or getdate(nowdate())
        self._set_order_details()
        self._validate_estimate_basis()
        self._validate_recipe()
        self._validate_rate_standard()
        self._validate_cost_items()
        self._calculate_totals()

    def before_submit(self):
        if not self.cost_items:
            frappe.throw(_("请至少填写一条成本明细"))
        self.estimate_status = "已确认"
        self.confirmed_by = frappe.session.user
        self.confirmed_on = now_datetime()

    def on_cancel(self):
        self.db_set("estimate_status", "已取消", update_modified=False)

    def _set_order_details(self):
        if not self.sales_order or not self.sales_order_item:
            frappe.throw(_("请选择染整销售订单和订单明细"))
        order, item = _get_order_item(self.sales_order, self.sales_order_item)
        self.company = order.company
        self.currency = order.currency or frappe.db.get_value("Company", order.company, "default_currency")
        self.customer_name = order.customer_name or frappe.db.get_value("Customer", order.customer, "customer_name") or order.customer
        self.order_type = order.order_type
        self.finished_product_name = item.finished_product_name or item.item_name
        self.color_no = item.color_no
        self.color = item.color
        self.grey_fabric_batch = item.grey_fabric_batch
        self.estimate_qty = flt(self.estimate_qty or item.qty, 6)
        self.uom = item.uom
        self.order_rate = flt(item.rate, 6)
        self.order_amount = flt(self.estimate_qty * self.order_rate, 6)
        self.expected_revenue = self.order_amount

    def _validate_estimate_basis(self):
        if flt(self.estimate_qty) <= 0:
            frappe.throw(_("测算数量必须大于零"))
        if flt(self.expected_yield_rate) <= 0:
            frappe.throw(_("预计成品率必须大于零"))
        if not 0 <= flt(self.target_gross_margin_rate) < 100:
            frappe.throw(_("目标毛利率必须大于等于零且小于 100%"))

    def _validate_recipe(self):
        if not self.laboratory_recipe:
            self.recipe_version = None
            return
        recipe = frappe.get_doc("Laboratory Recipe", self.laboratory_recipe)
        if recipe.recipe_status != "已确认":
            frappe.throw(_("只能使用已确认的化验室配方"))
        if self.color_no and recipe.color_no != self.color_no:
            frappe.throw(_("化验室配方的色号与订单明细不一致"))
        self.recipe_version = recipe.recipe_version

    def _validate_rate_standard(self):
        if not self.cost_rate_standard:
            self.rate_standard_version = None
            return
        standard = _get_applicable_rate_standard(
            self.company,
            self.order_type,
            self.estimate_date,
            self.cost_rate_standard,
        )
        self.rate_standard_version = standard.standard_version

    def _validate_cost_items(self):
        for row in self.cost_items:
            if row.cost_element:
                element = frappe.get_cached_doc("Dyeing Cost Element", row.cost_element)
                if element.company != self.company:
                    frappe.throw(_("第 {0} 行成本要素所属公司与测算单不一致").format(row.idx))
                row.cost_category = element.cost_category
                row.description = row.description or element.element_name
                row.uom = row.uom or element.default_uom
            if flt(row.quantity) < 0 or flt(row.unit_rate) < 0:
                frappe.throw(_("第 {0} 行预计用量和预计单价不能小于零").format(row.idx))
            if self.order_type == "来料加工" and row.cost_category == "胚布":
                row.unit_rate = 0
                row.amount = 0
                row.remarks = row.remarks or _("客户来料不计胚布成本")
            else:
                row.amount = flt(row.quantity) * flt(row.unit_rate)

    def _calculate_totals(self):
        buckets = {
            "grey_fabric_cost": 0,
            "chemical_cost": 0,
            "energy_cost": 0,
            "labor_cost": 0,
            "machine_cost": 0,
            "packaging_cost": 0,
            "subcontract_cost": 0,
            "other_cost": 0,
        }
        for row in self.cost_items:
            amount = flt(row.amount)
            if row.cost_category == "胚布":
                buckets["grey_fabric_cost"] += amount
            elif row.cost_category in CHEMICAL_CATEGORIES:
                buckets["chemical_cost"] += amount
            elif row.cost_category in ENERGY_CATEGORIES:
                buckets["energy_cost"] += amount
            elif row.cost_category == "人工":
                buckets["labor_cost"] += amount
            elif row.cost_category == "机台":
                buckets["machine_cost"] += amount
            elif row.cost_category == "包装":
                buckets["packaging_cost"] += amount
            elif row.cost_category == "委外":
                buckets["subcontract_cost"] += amount
            else:
                buckets["other_cost"] += amount

        for fieldname, amount in buckets.items():
            self.set(fieldname, flt(amount, 6))
        self.total_cost = flt(sum(buckets.values()), 6)
        self.unit_cost = flt(self.total_cost / self.estimate_qty, 6) if flt(self.estimate_qty) else 0
        self.estimated_output_qty = flt(self.estimate_qty * flt(self.expected_yield_rate) / 100, 6)
        self.expected_revenue = flt(self.order_amount, 6)
        self.gross_profit = flt(self.expected_revenue - self.total_cost, 6)
        self.gross_margin_rate = flt(self.gross_profit / self.expected_revenue * 100, 6) if self.expected_revenue else 0
        target_rate = flt(self.target_gross_margin_rate)
        self.suggested_quote_rate = (
            flt(self.unit_cost / (1 - target_rate / 100), 6)
            if self.estimate_qty and 0 <= target_rate < 100
            else 0
        )


def _next_version(sales_order_item):
    if not sales_order_item:
        return "V1"
    versions = frappe.get_all(
        "Dyeing Cost Estimate",
        filters={"sales_order_item": sales_order_item},
        pluck="estimate_version",
    )
    numbers = []
    for version in versions:
        match = re.fullmatch(r"V(\d+)", version or "")
        if match:
            numbers.append(int(match.group(1)))
    return f"V{max(numbers, default=0) + 1}"


def _get_order_item(sales_order, sales_order_item):
    order = frappe.get_doc("Dyeing Sales Order", sales_order)
    order.check_permission("read")
    if order.docstatus == 2:
        frappe.throw(_("不能引用已取消的染整销售订单"))
    item = next((row for row in order.items if row.name == sales_order_item), None)
    if not item:
        frappe.throw(_("染整销售订单明细不属于当前订单"))
    return order, item


def _item_estimate_rate(item_code, company):
    if not item_code:
        return 0
    rate = frappe.db.sql(
        """
        SELECT SUM(bin.actual_qty * bin.valuation_rate) / NULLIF(SUM(bin.actual_qty), 0)
        FROM `tabBin` bin
        INNER JOIN `tabWarehouse` warehouse ON warehouse.name = bin.warehouse
        WHERE bin.item_code = %s AND warehouse.company = %s AND bin.actual_qty > 0
        """,
        (item_code, company),
    )[0][0]
    if rate:
        return flt(rate, 6)
    fallback = frappe.db.get_value("Item", item_code, ["valuation_rate", "last_purchase_rate"], as_dict=True)
    return flt((fallback or {}).get("valuation_rate") or (fallback or {}).get("last_purchase_rate"), 6)


def _bath_ratio_value(value):
    match = re.search(r"(?:1\s*[:：]\s*)?(\d+(?:\.\d+)?)", value or "")
    return flt(match.group(1)) if match else 0


def _recipe_quantity_kg(formula_qty, dosage_basis, estimate_qty, bath_ratio=None):
    formula_qty = flt(formula_qty)
    estimate_qty = flt(estimate_qty)
    if dosage_basis == "%owf":
        return flt(formula_qty * estimate_qty / 100, 6)
    if dosage_basis == "g/kg":
        return flt(formula_qty * estimate_qty / 1000, 6)
    if dosage_basis == "g/L":
        ratio = _bath_ratio_value(bath_ratio)
        if not ratio:
            frappe.throw(_("配方使用 g/L 用量基准时必须填写有效浴比，例如 1:10"))
        return flt(formula_qty * estimate_qty * ratio / 1000, 6)
    if dosage_basis == "kg":
        return flt(formula_qty, 6)
    return 0


def _recipe_cost_lines(recipe, estimate_qty, company):
    lines = []
    for row in recipe.recipe_items:
        item = frappe.get_cached_doc("Item", row.item_code)
        quantity = _recipe_quantity_kg(row.formula_qty, row.dosage_basis, estimate_qty, recipe.bath_ratio)
        category = row.material_category if row.material_category in CHEMICAL_CATEGORIES else "其他"
        lines.append({
            "cost_element": DEFAULT_COST_ELEMENTS.get(category, "CE-OTHER"),
            "cost_category": category,
            "item_code": row.item_code,
            "description": row.item_name or item.item_name or row.item_code,
            "calculation_basis": "配方用量",
            "quantity": quantity,
            "uom": item.stock_uom,
            "unit_rate": _item_estimate_rate(row.item_code, company),
            "source_type": "化验室配方",
            "source_reference": recipe.name,
            "remarks": _("配方基准：{0} {1}").format(row.formula_qty, row.dosage_basis),
        })
    return lines


def _get_applicable_rate_standard(company, order_type, estimate_date, selected=None):
    if selected:
        standard = frappe.get_doc("Dyeing Cost Rate Standard", selected)
        standard.check_permission("read")
        if standard.docstatus != 1:
            frappe.throw(_("只能使用已提交的染整成本费率标准"))
        if standard.company != company:
            frappe.throw(_("成本费率标准所属公司与订单公司不一致"))
        if standard.applicable_order_type not in ("全部", order_type):
            frappe.throw(_("成本费率标准不适用于当前订单类型"))
        if getdate(standard.effective_from) > getdate(estimate_date):
            frappe.throw(_("成本费率标准尚未生效"))
        if standard.effective_to and getdate(standard.effective_to) < getdate(estimate_date):
            frappe.throw(_("成本费率标准已失效"))
        return standard

    names = frappe.db.sql(
        """
        SELECT name
        FROM `tabDyeing Cost Rate Standard`
        WHERE docstatus = 1
          AND company = %(company)s
          AND effective_from <= %(estimate_date)s
          AND (effective_to IS NULL OR effective_to = '' OR effective_to >= %(estimate_date)s)
          AND applicable_order_type IN ('全部', %(order_type)s)
        ORDER BY (applicable_order_type = %(order_type)s) DESC, effective_from DESC, creation DESC
        LIMIT 1
        """,
        {"company": company, "order_type": order_type, "estimate_date": getdate(estimate_date)},
    )
    return frappe.get_doc("Dyeing Cost Rate Standard", names[0][0]) if names else None


def _rate_line_quantity(calculation_basis, standard_consumption, estimate_qty, estimated_hours):
    standard_consumption = flt(standard_consumption)
    if calculation_basis == "每公斤":
        return flt(standard_consumption * flt(estimate_qty), 6)
    if calculation_basis == "每批":
        return flt(standard_consumption, 6)
    if calculation_basis == "每小时":
        return flt(standard_consumption * flt(estimated_hours), 6)
    if calculation_basis == "固定金额":
        return 1
    return 0


def _rate_cost_lines(standard, estimate_qty, estimated_hours, production_resource=None):
    if not standard:
        return []
    lines = []
    for row in standard.rate_items:
        if row.production_resource and row.production_resource != production_resource:
            continue
        quantity = _rate_line_quantity(
            row.calculation_basis,
            row.standard_consumption,
            estimate_qty,
            estimated_hours,
        )
        unit_rate = flt(row.standard_cost) if row.calculation_basis == "固定金额" else flt(row.unit_rate)
        scope = [row.production_operation, row.work_center, row.production_resource]
        scope_text = " / ".join(value for value in scope if value)
        lines.append({
            "cost_element": row.cost_element,
            "cost_category": row.cost_category,
            "description": row.cost_item,
            "calculation_basis": row.calculation_basis,
            "quantity": quantity,
            "uom": row.uom,
            "unit_rate": unit_rate,
            "source_type": "成本费率标准",
            "source_reference": standard.name,
            "remarks": _("费率版本：{0}{1}").format(
                standard.standard_version,
                _("；适用范围：{0}").format(scope_text) if scope_text else "",
            ),
        })
    return lines


@frappe.whitelist()
def get_order_items_for_estimate(sales_order):
    order = frappe.get_doc("Dyeing Sales Order", sales_order)
    order.check_permission("read")
    if order.docstatus == 2:
        return []
    return [{
        "name": row.name,
        "item_name": row.finished_product_name or row.item_name,
        "color": row.color,
        "qty": row.qty,
        "uom": row.uom,
    } for row in order.items]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_sales_order_items(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
    filters = frappe.parse_json(filters) or {}
    rows = frappe.db.sql(
        """
        SELECT item.name, item.finished_product_name, item.color, item.qty, item.uom
        FROM `tabDyeing Sales Order Item` item
        INNER JOIN `tabDyeing Sales Order` parent ON parent.name = item.parent
        WHERE parent.name = %(sales_order)s AND parent.docstatus < 2
          AND (item.name LIKE %(txt)s OR COALESCE(item.finished_product_name, '') LIKE %(txt)s
               OR COALESCE(item.color, '') LIKE %(txt)s)
        ORDER BY item.idx
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "sales_order": filters.get("sales_order") or "",
            "txt": f"%{txt}%",
            "start": int(start),
            "page_len": int(page_len),
        },
    )
    return rows


@frappe.whitelist()
def get_estimate_source(
    sales_order,
    sales_order_item,
    laboratory_recipe=None,
    cost_rate_standard=None,
    estimate_date=None,
    production_resource=None,
    estimated_production_hours=0,
):
    order, item = _get_order_item(sales_order, sales_order_item)
    estimate_date = getdate(estimate_date or nowdate())
    recipe_name = laboratory_recipe or frappe.db.get_value(
        "Laboratory Recipe",
        {"color_no": item.color_no, "recipe_status": "已确认"},
        "name",
        order_by="modified desc",
    )
    recipe = frappe.get_doc("Laboratory Recipe", recipe_name) if recipe_name else None
    if recipe and recipe.color_no != item.color_no:
        frappe.throw(_("所选化验室配方与订单色号不一致"))
    standard = _get_applicable_rate_standard(
        order.company,
        order.order_type,
        estimate_date,
        cost_rate_standard,
    )

    values = {
        "company": order.company,
        "currency": order.currency or frappe.db.get_value("Company", order.company, "default_currency"),
        "customer_name": order.customer_name or order.customer,
        "order_type": order.order_type,
        "finished_product_name": item.finished_product_name or item.item_name,
        "color_no": item.color_no,
        "color": item.color,
        "grey_fabric_batch": item.grey_fabric_batch,
        "estimate_qty": item.qty,
        "uom": item.uom,
        "order_rate": item.rate,
        "order_amount": flt(item.qty) * flt(item.rate),
        "laboratory_recipe": recipe.name if recipe else "",
        "recipe_version": recipe.recipe_version if recipe else "",
        "cost_rate_standard": standard.name if standard else "",
        "rate_standard_version": standard.standard_version if standard else "",
        "production_resource": production_resource or "",
        "estimated_production_hours": flt(estimated_production_hours),
    }
    lines = []
    if order.order_type == "全代料" and item.item_code:
        item_doc = frappe.get_cached_doc("Item", item.item_code)
        lines.append({
            "cost_element": DEFAULT_COST_ELEMENTS["胚布"],
            "cost_category": "胚布",
            "item_code": item.item_code,
            "description": item.item_name or item_doc.item_name or item.item_code,
            "calculation_basis": "库存估值",
            "quantity": item.qty,
            "uom": item.uom or item_doc.stock_uom,
            "unit_rate": _item_estimate_rate(item.item_code, order.company),
            "source_type": "库存估值",
            "source_reference": item.grey_fabric_batch or item.item_code,
        })
    if recipe:
        lines.extend(_recipe_cost_lines(recipe, item.qty, order.company))
    lines.extend(_rate_cost_lines(
        standard,
        item.qty,
        estimated_production_hours,
        production_resource,
    ))
    return {"values": values, "cost_items": lines}

import frappe
from frappe import _
from frappe.model.naming import make_autoname
from frappe.utils import cint
from dyeing_finishing.dyeing_finishing.settings import get_dye_material_groups, get_setting


def autoname(doc, method=None):
	"""成品物料使用独立的 CP 五位流水号，不影响其他物料。"""
	if cint(doc.get("custom_is_finished_product")):
		doc.name = make_autoname("CP.#####")
		doc.item_code = doc.name


def _normalized_identity_part(value):
	return " ".join(str(value or "").strip().split()).casefold()


def _validate_finished_product(doc):
	if not cint(doc.get("custom_is_finished_product")):
		return

	if doc.get("item_group") != get_setting("finished_product_item_group"):
		frappe.throw(_("成品物料的物料组只能选择成品。"))
	if not doc.get("custom_finished_color_no"):
		frappe.throw(_("请选择色号。"))
	if not doc.get("item_name"):
		frappe.throw(_("请填写成品名称。"))
	if not doc.get("custom_finished_width"):
		frappe.throw(_("请填写成品门幅。"))
	if not doc.get("custom_finished_gsm"):
		frappe.throw(_("请填写成品克重。"))

	color = frappe.db.get_value(
		"Color Master",
		doc.custom_finished_color_no,
		["color_name", "customer_name", "status"],
		as_dict=True,
	)
	if not color or color.status != "启用":
		frappe.throw(_("只能选择状态为启用的色号。"))

	doc.custom_finished_color = color.color_name
	doc.custom_finished_customer = color.customer_name
	doc.custom_finished_gsm_uom = doc.get("custom_finished_gsm_uom") or "g/㎡"
	doc.custom_finished_specification = " × ".join(
		filter(None, (str(doc.custom_finished_width).strip(), f"{doc.custom_finished_gsm}{doc.custom_finished_gsm_uom}"))
	)
	doc.custom_finished_identity_key = "|".join(
		_normalized_identity_part(value)
		for value in (doc.custom_finished_color_no, doc.item_name, doc.custom_finished_color)
	)
	doc.stock_uom = get_setting("weight_uom")
	doc.is_stock_item = 1
	doc.has_batch_no = 1

	duplicate = frappe.db.get_value(
		"Item",
		{
			"custom_finished_identity_key": doc.custom_finished_identity_key,
			"name": ["!=", doc.name or ""],
		},
		"name",
	)
	if duplicate:
		frappe.throw(_("相同色号、成品名称和颜色的成品物料已存在：{0}").format(duplicate))


def get_or_create_finished_item(color_no, product_name, width=None, gsm=None, gsm_uom="g/㎡"):
	color_name = frappe.db.get_value("Color Master", color_no, "color_name") or ""
	identity_key = "|".join(
		_normalized_identity_part(value) for value in (color_no, product_name, color_name)
	)
	item_code = frappe.db.get_value("Item", {"custom_finished_identity_key": identity_key}, "name")
	if item_code:
		return item_code

	item = frappe.get_doc(
		{
			"doctype": "Item",
			"custom_is_finished_product": 1,
			"item_name": product_name,
			"item_group": get_setting("finished_product_item_group"),
			"stock_uom": get_setting("weight_uom"),
			"is_stock_item": 1,
			"has_batch_no": 1,
			"custom_finished_color_no": color_no,
			"custom_finished_width": width,
			"custom_finished_gsm": gsm,
			"custom_finished_gsm_uom": gsm_uom or "g/㎡",
		}
	)
	item.insert(ignore_permissions=True)
	return item.name


def validate(doc, method=None):
	"""染化料入口创建的物料只能归入染料或助剂。"""
	_validate_finished_product(doc)
	if not cint(doc.get("custom_is_dyeing_material")):
		return

	if doc.get("item_group") not in set(get_dye_material_groups()):
		frappe.throw("染化料物料的物料组只能选择染料或助剂。")

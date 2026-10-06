import frappe
from frappe.utils import cint


ALLOWED_DYEING_ITEM_GROUPS = {"染料", "助剂"}


def validate(doc, method=None):
	"""染化料入口创建的物料只能归入染料或助剂。"""
	if not cint(doc.get("custom_is_dyeing_material")):
		return

	if doc.get("item_group") not in ALLOWED_DYEING_ITEM_GROUPS:
		frappe.throw("染化料物料的物料组只能选择染料或助剂。")

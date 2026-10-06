import frappe
from frappe import _
from frappe.model.document import Document


ALLOWED_ITEM_GROUPS = ("染料", "助剂")


class LaboratoryRecipeItem(Document):
    def validate(self):
        if not self.item_code:
            return

        item = frappe.db.get_value(
            "Item", self.item_code, ["item_group", "disabled"], as_dict=True
        )
        if not item or item.disabled:
            frappe.throw(_("只能选择启用的染料或助剂物料"))
        if item.item_group not in ALLOWED_ITEM_GROUPS:
            frappe.throw(_("配方明细只能选择物料组为“染料”或“助剂”的物料"))

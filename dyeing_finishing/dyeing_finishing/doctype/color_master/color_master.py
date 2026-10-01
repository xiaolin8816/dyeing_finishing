import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class ColorMaster(Document):
    def validate(self):
        self._set_grey_fabric_details()

    def _set_grey_fabric_details(self):
        if not self.grey_fabric_batch:
            self.grey_fabric = None
            self.grey_fabric_code = None
            self.grey_fabric_name = None
            return

        batch = frappe.get_doc("Batch", self.grey_fabric_batch)
        item = frappe.get_doc("Item", batch.item)
        if cint(batch.disabled) or cint(item.disabled) or item.item_group != "胚布":
            frappe.throw(_("只能选择启用的胚布库存批次"))

        self.grey_fabric_code = item.name
        self.grey_fabric_name = item.item_name
        self.grey_fabric = frappe.db.get_value("Grey Fabric Master", {"item_code": item.name})


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_grey_fabric_batches(doctype, txt, searchfield, start, page_len, filters):
    like_txt = f"%{txt}%"
    return frappe.db.sql(
        """
        SELECT batch.name, batch.item, item.item_name
        FROM tabBatch AS batch
        INNER JOIN tabItem AS item ON item.name = batch.item
        WHERE batch.disabled = 0
          AND item.disabled = 0
          AND item.item_group = '胚布'
          AND (batch.name LIKE %(txt)s OR batch.item LIKE %(txt)s OR item.item_name LIKE %(txt)s)
        ORDER BY batch.modified DESC
        LIMIT %(start)s, %(page_len)s
        """,
        {"txt": like_txt, "start": cint(start), "page_len": cint(page_len)},
    )


@frappe.whitelist()
def get_grey_fabric_batch_details(batch_no):
    batch = frappe.get_doc("Batch", batch_no)
    item = frappe.get_doc("Item", batch.item)
    if cint(batch.disabled) or cint(item.disabled) or item.item_group != "胚布":
        frappe.throw(_("只能选择启用的胚布库存批次"))

    return {
        "batch_no": batch.name,
        "grey_fabric": frappe.db.get_value("Grey Fabric Master", {"item_code": item.name}) or "",
        "grey_fabric_code": item.name,
        "grey_fabric_name": item.item_name,
    }

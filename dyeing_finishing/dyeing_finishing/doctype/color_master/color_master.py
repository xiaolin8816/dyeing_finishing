import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

RECEIPT_TABLE = chr(96) + "tabCustomer Grey Fabric Receipt" + chr(96)
RECEIPT_ITEM_TABLE = chr(96) + "tabCustomer Grey Fabric Receipt Item" + chr(96)
BATCH_TABLE = chr(96) + "tabBatch" + chr(96)
ITEM_TABLE = chr(96) + "tabItem" + chr(96)


class ColorMaster(Document):
    def validate(self):
        self._set_grey_fabric_details()

    def _set_grey_fabric_details(self):
        if not self.grey_fabric_batch:
            self.grey_fabric = None
            self.grey_fabric_code = None
            self.grey_fabric_name = None
            return

        detail = get_grey_fabric_batch_details(
            self.grey_fabric_batch, customer=self.customer_name
        )
        self.grey_fabric = detail.grey_fabric
        self.grey_fabric_code = detail.grey_fabric_code
        self.grey_fabric_name = detail.grey_fabric_name


def _validate_customer_batch(batch_no, customer):
    if not customer:
        frappe.throw(_("请选择客户后再选择胚布批次"))

    owner = frappe.db.sql(
        f"""
        SELECT receipt.customer
        FROM {RECEIPT_TABLE} AS receipt
        INNER JOIN {RECEIPT_ITEM_TABLE} AS item
            ON item.parent = receipt.name
        WHERE receipt.docstatus = 1
          AND receipt.customer = %(customer)s
          AND item.batch_no = %(batch_no)s
        LIMIT 1
        """,
        {"customer": customer, "batch_no": batch_no},
        as_dict=True,
    )
    if not owner:
        frappe.throw(_("所选胚布批次不属于当前客户"))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_grey_fabric_batches(doctype, txt, searchfield, start, page_len, filters):
    filters = filters or {}
    customer = filters.get("customer")
    if not customer:
        return []

    like_txt = f"%{txt}%"
    return frappe.db.sql(
        f"""
        SELECT DISTINCT batch.name, batch.item, item.item_name, receipt.customer_name
        FROM {RECEIPT_TABLE} AS receipt
        INNER JOIN {RECEIPT_ITEM_TABLE} AS receipt_item
            ON receipt_item.parent = receipt.name
        INNER JOIN {BATCH_TABLE} AS batch ON batch.name = receipt_item.batch_no
        INNER JOIN {ITEM_TABLE} AS item ON item.name = batch.item
        WHERE receipt.docstatus = 1
          AND receipt.customer = %(customer)s
          AND batch.disabled = 0
          AND item.disabled = 0
          AND item.item_group = '胚布'
          AND (
              batch.name LIKE %(txt)s
              OR batch.item LIKE %(txt)s
              OR item.item_name LIKE %(txt)s
              OR receipt.customer_name LIKE %(txt)s
          )
        ORDER BY batch.modified DESC
        LIMIT %(start)s, %(page_len)s
        """,
        {"customer": customer, "txt": like_txt, "start": cint(start), "page_len": cint(page_len)},
    )


@frappe.whitelist()
def get_grey_fabric_batch_details(batch_no, customer=None):
    _validate_customer_batch(batch_no, customer)

    batch = frappe.get_doc("Batch", batch_no)
    item = frappe.get_doc("Item", batch.item)
    if cint(batch.disabled) or cint(item.disabled) or item.item_group != "胚布":
        frappe.throw(_("只能选择启用的胚布库存批次"))

    return frappe._dict({
        "batch_no": batch.name,
        "grey_fabric": frappe.db.get_value("Grey Fabric Master", {"item_code": item.name}) or "",
        "grey_fabric_code": item.name,
        "grey_fabric_name": item.item_name,
    })

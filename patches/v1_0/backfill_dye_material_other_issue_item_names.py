import frappe


def execute():
    for row in frappe.get_all("Dye Material Other Issue", pluck="name"):
        item_names = []
        for item in frappe.get_all(
            "Dye Material Other Issue Item",
            filters={"parent": row},
            fields=["item_name", "item_code"],
            order_by="idx",
        ):
            name = (item.item_name or item.item_code or "").strip()
            if name and name not in item_names:
                item_names.append(name)
        frappe.db.set_value("Dye Material Other Issue", row, "item_names", "、".join(item_names), update_modified=False)

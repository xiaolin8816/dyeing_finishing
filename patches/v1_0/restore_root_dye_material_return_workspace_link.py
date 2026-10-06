import frappe


def execute():
    if not frappe.db.exists("Workspace", "印染整理"):
        return
    workspace = frappe.get_doc("Workspace", "印染整理")
    card = next((row for row in workspace.links or [] if row.type == "Card Break" and row.label == "染料管理"), None)
    if card:
        card.link_count = 5
    link = next((row for row in workspace.links or [] if row.type == "Link" and row.link_to == "Dye Material Return"), None)
    if not link:
        link = workspace.append("links", {"type": "Link", "label": "染料退货单"})
    link.label = "染料退货单"
    link.link_type = "DocType"
    link.link_to = "Dye Material Return"
    link.is_query_report = 0
    link.hidden = 0
    workspace.save(ignore_permissions=True)
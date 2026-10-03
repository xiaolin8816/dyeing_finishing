import frappe

def execute():
    if not frappe.db.exists("Workspace", "印染整理"):
        return
    workspace = frappe.get_doc("Workspace", "印染整理")
    card = next((row for row in workspace.links or [] if row.type == "Card Break" and row.label == "染料管理"), None)
    if card:
        card.link_count = 3
    link = next((row for row in workspace.links or [] if row.type == "Link" and row.link_to == "Site Dyeing Material Issue"), None)
    if not link:
        link = workspace.append("links", {"type": "Link", "label": "现场染色领料单"})
    link.label = "现场染色领料单"
    link.link_type = "DocType"
    link.link_to = "Site Dyeing Material Issue"
    link.is_query_report = 0
    workspace.save(ignore_permissions=True)

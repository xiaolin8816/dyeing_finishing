import frappe


def execute():
    if not frappe.db.exists("Workspace", "印染整理"):
        return
    workspace = frappe.get_doc("Workspace", "印染整理")
    original_count = len(workspace.links or [])
    workspace.links = [
        row for row in workspace.links or []
        if not (row.type == "Link" and row.link_to == "Dye Material Return")
    ]
    changed = len(workspace.links) != original_count
    card = next((row for row in workspace.links or [] if row.type == "Card Break" and row.label == "染料管理"), None)
    if card and card.link_count != 4:
        card.link_count = 4
        changed = True
    if changed:
        workspace.save(ignore_permissions=True)
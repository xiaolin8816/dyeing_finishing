import frappe


WORKSPACE = "印染整理"
CARD_LABEL = "染料管理"
LINK_LABEL = "染料库存"
REPORT_NAME = "Dye Material Stock"


def execute():
    if not frappe.db.exists("Workspace", WORKSPACE):
        return

    workspace = frappe.get_doc("Workspace", WORKSPACE)
    card = next(
        (row for row in workspace.links or [] if row.type == "Card Break" and row.label == CARD_LABEL),
        None,
    )
    if card:
        card.link_type = "Report"
        card.is_query_report = 1
        card.link_count = 2

    link = next(
        (row for row in workspace.links or [] if row.type == "Link" and row.label == LINK_LABEL),
        None,
    )
    if not link:
        link = workspace.append("links", {"type": "Link", "label": LINK_LABEL})
    link.link_type = "Report"
    link.link_to = REPORT_NAME
    link.is_query_report = 1
    workspace.save(ignore_permissions=True)

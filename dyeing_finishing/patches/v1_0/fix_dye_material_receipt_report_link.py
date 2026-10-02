import frappe


WORKSPACE = "印染整理"
CARD_LABEL = "染料管理"
LINK_LABEL = "染料入库单"
REPORT_NAME = "Dye Material Receipt Register"


def execute():
    if not frappe.db.exists("Workspace", WORKSPACE):
        return

    workspace = frappe.get_doc("Workspace", WORKSPACE)
    changed = False

    for row in workspace.links or []:
        if row.type == "Card Break" and row.label == CARD_LABEL:
            row.link_type = "Report"
            row.is_query_report = 1
            row.link_count = 1
            changed = True
        elif row.type == "Link" and row.label == LINK_LABEL:
            row.link_type = "Report"
            row.link_to = REPORT_NAME
            row.is_query_report = 1
            changed = True

    if changed:
        workspace.save(ignore_permissions=True)

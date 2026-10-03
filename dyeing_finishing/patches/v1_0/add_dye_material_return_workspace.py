import frappe


WORKSPACES = ("染料管理",)


def execute():
    for workspace_name in WORKSPACES:
        if not frappe.db.exists("Workspace", workspace_name):
            continue
        workspace = frappe.get_doc("Workspace", workspace_name)
        card = next(
            (row for row in workspace.links or [] if row.type == "Card Break" and row.label == "染料管理"),
            None,
        )
        if not card:
            card = next(
                (row for row in workspace.links or [] if row.type == "Card Break" and row.label == "染料收发与库存"),
                None,
            )
        if card:
            card.link_count = 5

        link = next(
            (row for row in workspace.links or [] if row.type == "Link" and row.link_to == "Dye Material Return"),
            None,
        )
        if not link:
            link = workspace.append("links", {"type": "Link", "label": "染料退货单"})
        link.label = "染料退货单"
        link.link_type = "DocType"
        link.link_to = "Dye Material Return"
        link.is_query_report = 0
        link.hidden = 0
        workspace.save(ignore_permissions=True)
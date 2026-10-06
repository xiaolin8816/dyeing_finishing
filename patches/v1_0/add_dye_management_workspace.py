import frappe


WORKSPACE = "印染整理"
CARD_LABEL = "染料管理"
LINK_LABEL = "染料入库单"
REPORT_NAME = "Dye Material Receipt Register"
STOCK_LINK_LABEL = "染料库存"
STOCK_REPORT_NAME = "Dye Material Stock"


def execute():
    if not frappe.db.exists("Workspace", WORKSPACE):
        return

    workspace = frappe.get_doc("Workspace", WORKSPACE)
    content = frappe.parse_json(workspace.content or "[]")

    content = [
        block
        for block in content
        if block.get("id") not in {"dye-management-header", "dye-material-receipt-shortcut", "dye-management-card"}
    ]
    content.extend(
        [
            {
                "id": "dye-management-header",
                "type": "header",
                "data": {"text": '<span class="h4"><b>染料管理</b></span>', "col": 12},
            },
            {
                "id": "dye-management-card",
                "type": "card",
                "data": {"card_name": CARD_LABEL, "col": 4},
            },
        ]
    )
    workspace.content = frappe.as_json(content)

    workspace.set(
        "shortcuts",
        [row for row in (workspace.shortcuts or []) if row.label != LINK_LABEL],
    )

    card = next(
        (row for row in workspace.links or [] if row.type == "Card Break" and row.label == CARD_LABEL),
        None,
    )
    if not card:
        card = workspace.append("links", {"type": "Card Break", "label": CARD_LABEL})
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

    stock_link = next(
        (row for row in workspace.links or [] if row.type == "Link" and row.label == STOCK_LINK_LABEL),
        None,
    )
    if not stock_link:
        stock_link = workspace.append("links", {"type": "Link", "label": STOCK_LINK_LABEL})
    stock_link.link_type = "Report"
    stock_link.link_to = STOCK_REPORT_NAME
    stock_link.is_query_report = 1

    workspace.save(ignore_permissions=True)

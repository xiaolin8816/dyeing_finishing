import frappe


WORKSPACE = "印染整理"
CARD_LABEL = "染料管理"
LINK_LABEL = "染料入库单"


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

    has_card = any(row.type == "Card Break" and row.label == CARD_LABEL for row in workspace.links or [])
    if not has_card:
        workspace.append("links", {"type": "Card Break", "label": CARD_LABEL})

    has_link = any(
        row.type == "Link" and row.label == LINK_LABEL and row.link_to == "dye-material-receipt"
        for row in workspace.links or []
    )
    if not has_link:
        workspace.append(
            "links",
            {
                "type": "Link",
                "link_type": "Page",
                "link_to": "dye-material-receipt",
                "label": LINK_LABEL,
            },
        )

    workspace.save(ignore_permissions=True)

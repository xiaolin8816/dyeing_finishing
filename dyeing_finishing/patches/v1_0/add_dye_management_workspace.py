import frappe


WORKSPACE = "印染整理"
SHORTCUT_LABEL = "染料入库单"


def execute():
    if not frappe.db.exists("Workspace", WORKSPACE):
        return

    workspace = frappe.get_doc("Workspace", WORKSPACE)
    content = frappe.parse_json(workspace.content or "[]")
    if not any(block.get("id") == "dye-management-header" for block in content):
        content.extend([
            {
                "id": "dye-management-header",
                "type": "header",
                "data": {"text": '<span class="h4"><b>染料管理</b></span>', "col": 12},
            },
            {
                "id": "dye-material-receipt-shortcut",
                "type": "shortcut",
                "data": {"shortcut_name": SHORTCUT_LABEL, "col": 4},
            },
        ])
        workspace.content = frappe.as_json(content)

    if not any(row.label == SHORTCUT_LABEL for row in workspace.shortcuts or []):
        workspace.append(
            "shortcuts",
            {
                "type": "Page",
                "link_to": "dye-material-receipt",
                "label": SHORTCUT_LABEL,
                "icon": "receipt",
            },
        )
    workspace.save(ignore_permissions=True)

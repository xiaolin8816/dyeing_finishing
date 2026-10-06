import json
from pathlib import Path

import frappe


def execute():
    """将生产管理入口从 ERPNext 原生销售订单切换为染整销售订单。"""
    workspace_name = "生产管理"
    workspace_file = Path(
        frappe.get_app_path(
            "dyeing_finishing", "dyeing_finishing", "workspace",
            workspace_name, f"{workspace_name}.json",
        )
    )
    source = json.loads(workspace_file.read_text(encoding="utf-8"))
    workspace = frappe.get_doc("Workspace", workspace_name)
    workspace.content = source["content"]
    workspace.set("links", source.get("links", []))
    workspace.set("shortcuts", source.get("shortcuts", []))
    workspace.save(ignore_permissions=True)
    frappe.clear_cache()

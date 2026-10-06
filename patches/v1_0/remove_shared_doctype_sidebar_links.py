import frappe

from dyeing_finishing.patches.v1_0.consolidate_dyeing_workspace_sidebar import (
	execute as sync_sidebar,
)


def execute():
	"""从可见侧栏移除共享的 ERPNext 标准档案入口。

	这些页面的工作区归属由前端根据进入来源处理，避免将它们常驻在侧栏中。
	"""
	sync_sidebar()
	frappe.cache.delete_key("bootinfo")

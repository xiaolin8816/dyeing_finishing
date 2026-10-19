import json

import frappe


def execute():
	"""移除染整销售订单明细的旧个人列设置。

	旧设置会优先于 DocField 元数据，导致新增的“胚布批次”和新字段顺序
	在已使用过子表列设置的账号上不生效。
	"""
	rows = frappe.db.sql(
		"SELECT user, data FROM `__UserSettings` WHERE doctype=%s",
		"Dyeing Sales Order",
		as_dict=True,
	)
	for row in rows:
		try:
			settings = json.loads(row.data or "{}")
		except (TypeError, ValueError):
			continue
		grid_view = settings.get("GridView") or {}
		if "Dyeing Sales Order Item" not in grid_view:
			continue
		grid_view.pop("Dyeing Sales Order Item", None)
		if grid_view:
			settings["GridView"] = grid_view
		else:
			settings.pop("GridView", None)
		frappe.db.sql(
			"UPDATE `__UserSettings` SET data=%s WHERE user=%s AND doctype=%s",
			(json.dumps(settings, ensure_ascii=False), row.user, "Dyeing Sales Order"),
		)
	frappe.cache.delete_key("_user_settings")

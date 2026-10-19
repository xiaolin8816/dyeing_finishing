from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, get_datetime, getdate, time_diff_in_hours


class DyeingProductionSchedule(Document):
	def before_insert(self):
		self.schedule_no = self.name
		self.planner = frappe.session.user

	def validate(self):
		self.schedule_no = self.name
		if get_datetime(self.to_datetime) <= get_datetime(self.from_datetime):
			frappe.throw(_("排程结束时间必须晚于开始时间。"))
		if not self.items:
			frappe.throw(_("请至少添加一项排程任务。"))
		self._validate_items()
		self.task_count = len(self.items)
		self.total_hours = sum(flt(row.estimated_hours) for row in self.items)

	def on_submit(self):
		for row in self.items:
			resource = frappe.db.get_value("Production Resource", row.production_resource,
				["resource_name"], as_dict=True) or {}
			values = {
				"production_resource": row.production_resource, "resource_name": resource.get("resource_name"),
				"planned_start": row.planned_start,
				"planned_end": row.planned_end, "estimated_hours": row.estimated_hours,
				"production_shift": self.production_shift, "schedule_status": row.schedule_status,
				"production_schedule": self.name,
			}
			for operation_row in _get_dyeing_group_rows(row.production_flow_card, row.operation_row):
				frappe.db.set_value("Production Flow Card Operation", operation_row, values, update_modified=False)
		frappe.db.set_value("Dyeing Production Schedule", self.name, "schedule_status", "已发布", update_modified=False)

	def before_cancel(self):
		started = [row for row in self.items if row.schedule_status != "已排程"]
		if started:
			frappe.throw(_("已开始或已完成的染色任务不能直接取消排程。"))

	def on_cancel(self):
		for row in self.items:
			for operation_row in _get_dyeing_group_rows(row.production_flow_card, row.operation_row):
				if frappe.db.get_value("Production Flow Card Operation", operation_row, "production_schedule") != self.name:
					continue
				frappe.db.set_value("Production Flow Card Operation", operation_row, {
					"production_resource": None, "resource_name": None,
					"planned_start": None, "planned_end": None,
					"estimated_hours": 0, "production_shift": None,
					"schedule_status": "未排程", "production_schedule": None,
				}, update_modified=False)
		frappe.db.set_value("Dyeing Production Schedule", self.name, "schedule_status", "已取消", update_modified=False)

	def _validate_items(self):
		seen = set()
		resource_ranges = {}
		# Serialize publication on each resource before checking overlapping schedules.
		for resource in sorted({row.production_resource for row in self.items if row.production_resource}):
			frappe.db.get_value("Production Resource", resource, "name", for_update=True)
		task_details = [
			get_task_details(row.production_flow_card, row.operation, row.operation_row)
			for row in self.items
		]
		# All drafts and publications lock the same operation identities in the same order.
		for key in sorted({details["operation_row"] for details in task_details}):
			frappe.db.get_value("Production Flow Card Operation", key, "name", for_update=True)
		for row, details in zip(self.items, task_details):
			key = details["operation_row"]
			if key in seen:
				frappe.throw(_("流转卡 {0} 的工序 {1} 重复排程。").format(row.production_flow_card, row.operation))
			seen.add(key)
			existing_schedule = frappe.db.get_value(
				"Production Flow Card Operation", key, "production_schedule", for_update=True
			)
			if existing_schedule and existing_schedule != self.name:
				frappe.throw(_("该工序已经安排在排程 {0} 中，请刷新看板。").format(existing_schedule))
			_assert_task_available(row.production_flow_card, row.operation, key, self.name, for_update=True)
			for field in ("operation_row", "operation_name", "scheduling_mode", "work_center", "resource_type", "customer_name", "finished_product_name", "color", "production_priority", "production_qty", "delivery_date", "readiness_status"):
				row.set(field, details.get(field))
			if row.scheduling_mode == "仅记录进度":
				frappe.throw(_("工序 {0} 设置为仅记录进度，不需要进入生产排程。").format(row.operation_name))
			if not row.production_resource:
				frappe.throw(_("请为工序 {0} 选择生产资源。").format(row.operation_name))
			start, end = get_datetime(row.planned_start), get_datetime(row.planned_end)
			if end <= start:
				frappe.throw(_("流转卡 {0} 的计划结束时间必须晚于开始时间。").format(row.production_flow_card))
			if start < get_datetime(self.from_datetime) or end > get_datetime(self.to_datetime):
				frappe.throw(_("流转卡 {0} 超出本排程计划的时间范围。").format(row.production_flow_card))
			row.estimated_hours = time_diff_in_hours(end, start)
			resource = frappe.db.get_value("Production Resource", row.production_resource,
				["resource_name", "status", "work_center", "resource_type", "minimum_capacity", "maximum_capacity", "rated_capacity"], as_dict=True)
			if not resource or resource.status not in ("启用", "空闲", "生产中"):
				frappe.throw(_("生产资源 {0} 当前不可排产。").format(row.production_resource))
			if row.work_center and resource.work_center != row.work_center:
				frappe.throw(_("工序 {0} 只能安排到生产工段 {1}。").format(row.operation_name, row.work_center))
			if row.resource_type and resource.resource_type != row.resource_type:
				frappe.throw(_("工序 {0} 要求资源类型为 {1}。").format(row.operation_name, row.resource_type))
			row.resource_name = resource.resource_name
			maximum = flt(resource.maximum_capacity or resource.rated_capacity)
			minimum = flt(resource.minimum_capacity)
			if maximum and flt(row.production_qty) > maximum + 0.000001:
				frappe.throw(_("流转卡 {0} 数量超过生产资源 {1} 最大容量。").format(row.production_flow_card, resource.resource_name))
			if minimum and flt(row.production_qty) < minimum - 0.000001:
				frappe.throw(_("流转卡 {0} 数量低于生产资源 {1} 最小装载量。").format(row.production_flow_card, resource.resource_name))
			row.load_rate = flt(row.production_qty) / maximum * 100 if maximum else 0
			for other_start, other_end, other_card in resource_ranges.setdefault(row.production_resource, []):
				if start < other_end and end > other_start:
					frappe.throw(_("生产资源 {0} 的流转卡 {1} 与 {2} 时间重叠。").format(resource.resource_name, row.production_flow_card, other_card))
			resource_ranges[row.production_resource].append((start, end, row.production_flow_card))
			self._validate_external_conflicts(row, start, end)

	def _validate_external_conflicts(self, row, start, end):
		conflict = frappe.db.sql("""SELECT item.parent, item.production_flow_card
			FROM `tabDyeing Production Schedule Item` item
			INNER JOIN `tabDyeing Production Schedule` plan ON plan.name=item.parent
			WHERE item.parent != %(parent)s AND plan.docstatus < 2 AND item.production_resource=%(resource)s
			AND item.planned_start < %(end)s AND item.planned_end > %(start)s LIMIT 1 FOR UPDATE""",
			{"parent":self.name or "", "resource":row.production_resource, "start":start, "end":end}, as_dict=True)
		if conflict:
			frappe.throw(_("生产资源 {0} 与已有排程 {1}（含草稿，流转卡 {2}）时间冲突。").format(row.production_resource, conflict[0].parent, conflict[0].production_flow_card))
		blocked = frappe.db.sql("""SELECT name, calendar_type FROM `tabMachine Production Calendar`
			WHERE docstatus < 2 AND production_resource=%(resource)s
			AND start_datetime < %(end)s AND end_datetime > %(start)s LIMIT 1""",
			{"resource":row.production_resource, "start":start, "end":end}, as_dict=True)
		if blocked:
			frappe.throw(_("生产资源 {0} 在该时间段处于{1}（{2}）。").format(row.production_resource, blocked[0].calendar_type, blocked[0].name))


def _get_dyeing_group_rows(production_flow_card, fallback_row=None):
	rows = frappe.db.sql("""
		SELECT flow_operation.name
		FROM `tabProduction Flow Card Operation` flow_operation
		INNER JOIN `tabProduction Operation` operation_master
			ON operation_master.name=flow_operation.operation
		WHERE flow_operation.parent=%s
		AND flow_operation.operation_status!='已完成'
		AND operation_master.scheduling_mode='设备排程'
		AND operation_master.default_work_center='WC-DYE'
		ORDER BY flow_operation.idx
	""", production_flow_card, pluck=True)
	return rows or ([fallback_row] if fallback_row else [])


@frappe.whitelist()
def get_task_details(production_flow_card, operation, operation_row=None):
	card = frappe.get_doc("Production Flow Card", production_flow_card)
	card.check_permission("read")
	if card.docstatus != 1 or card.production_status != "进行中":
		frappe.throw(_("生产流转卡不可排程。"))
	matching_rows = [
		row for row in card.operations
		if row.operation == operation and row.operation_status != "已完成"
		and (not operation_row or row.name == operation_row)
	]
	if not matching_rows:
		frappe.throw(_("流转卡中未找到可排程的工序 {0}。").format(operation))
	if len(matching_rows) > 1:
		frappe.throw(_("该工序在流转卡中出现多次，请从看板选择具体工序任务。"))
	task = matching_rows[0]
	operation_name = task.operation_name or frappe.db.get_value("Production Operation", operation, "production_operation_name") or operation
	operation_rule = frappe.db.get_value("Production Operation", operation,
		["scheduling_mode", "default_work_center", "resource_type", "requires_recipe",
		 "requires_material_ready", "time_calculation_method", "fixed_batch_minutes",
		 "minutes_per_kg", "setup_minutes", "cleaning_minutes"], as_dict=True) or {}
	operation_rule["work_center"] = operation_rule.get("default_work_center")
	customer_name = frappe.db.get_value("Customer", card.customer, "customer_name") or card.customer
	card_values = {field: card.get(field) for field in (
		"customer", "finished_product_name", "color", "color_no", "production_priority",
		"production_qty", "delivery_date", "production_status",
	)}
	prepared = _get_prepared_tasks([frappe._dict(
		production_flow_card=card.name, color_no=card.color_no
	)])
	return {
		**card_values, **operation_rule, **_readiness(card.name, card.color_no, operation_rule, prepared),
		"customer_name": customer_name, "operation_row": task.name, "operation_name": operation_name,
		"suggested_hours": _suggested_hours(card.production_qty, operation_rule),
		"default_shift": frappe.db.get_value("Production Work Center", operation_rule["work_center"], "default_shift")
			if operation_rule["work_center"] else None,
	}


def _get_prepared_tasks(tasks):
	cards = sorted({row.production_flow_card for row in tasks})
	colors = sorted({row.color_no for row in tasks if row.color_no})
	if not cards:
		return {"grey": set(), "recipe": set(), "material": set()}
	return {
		"grey": set(frappe.get_all("Grey Fabric Issue",
			filters={"flow_card": ["in", cards], "docstatus": 1}, pluck="flow_card")),
		"recipe": set(frappe.get_all("Laboratory Recipe",
			filters={"color_no": ["in", colors], "recipe_status": "已确认"}, pluck="color_no")) if colors else set(),
		"material": set(frappe.get_all("Site Dyeing Material Sheet",
			filters={"production_flow_card": ["in", cards], "docstatus": ["!=", 2],
				"material_sheet_status": ["not in", ["保存", "已取消"]]}, pluck="production_flow_card")),
	}


def _readiness(card_name, color_no, rule, prepared):
	checks = [("胚布未领用", card_name in prepared["grey"])]
	if cint(rule.get("requires_recipe")):
		checks.append(("配方未确认", bool(color_no) and color_no in prepared["recipe"]))
	if cint(rule.get("requires_material_ready")):
		checks.append(("染料未齐套", card_name in prepared["material"]))
	missing = [label for label, ready in checks if not ready]
	status = "可以排产" if not missing else ("部分准备" if any(ready for _, ready in checks) else "未准备")
	return {"readiness_status": status, "readiness_missing": missing}


def _suggested_hours(quantity, rule):
	if rule.get("time_calculation_method") == "按生产数量":
		minutes = flt(quantity) * flt(rule.get("minutes_per_kg"))
	else:
		minutes = flt(rule.get("fixed_batch_minutes"))
	minutes += flt(rule.get("setup_minutes")) + flt(rule.get("cleaning_minutes"))
	return flt(minutes / 60, 2) if minutes > 0 else 1


def _assert_task_available(card, operation, operation_row, current_schedule=None, for_update=False):
	reserved = frappe.db.sql("""
		SELECT item.parent FROM `tabDyeing Production Schedule Item` item
		INNER JOIN `tabDyeing Production Schedule` plan ON plan.name=item.parent
		WHERE plan.docstatus < 2 AND item.parent != %(current)s
		AND (item.operation_row=%(row)s OR (
			COALESCE(item.operation_row,'')='' AND item.production_flow_card=%(card)s
			AND item.operation=%(operation)s))
		LIMIT 1""" + (" FOR UPDATE" if for_update else ""),
		{"current": current_schedule or "", "row": operation_row, "card": card, "operation": operation})
	if reserved:
		frappe.throw(_("该工序已被其他排程占用（含草稿），请刷新待排任务。"))


@frappe.whitelist()
def get_board_data(from_date=None, to_date=None, work_center=None, production_resource=None):
	frappe.has_permission("Dyeing Production Schedule", "read", throw=True)
	from_date = from_date or frappe.utils.nowdate()
	to_date = to_date or from_date
	if getdate(to_date) < getdate(from_date):
		frappe.throw(_("结束日期不能早于开始日期。"))
	params = {"from_date": from_date, "to_date": to_date, "work_center": work_center,
		"production_resource": production_resource}
	pending_conditions = ""
	if work_center:
		pending_conditions += " AND operation_master.default_work_center=%(work_center)s"
	if production_resource:
		selected_resource = frappe.get_doc("Production Resource", production_resource)
		selected_resource.check_permission("read")
		params.update(selected_center=selected_resource.work_center, selected_type=selected_resource.resource_type)
		pending_conditions += """
			AND (COALESCE(operation_master.default_work_center,'')='' OR operation_master.default_work_center=%(selected_center)s)
			AND (COALESCE(operation_master.resource_type,'')='' OR operation_master.resource_type=%(selected_type)s)"""
	terminal_progress = {"成品全部入库", "成品全部出库", "成品全部转客户"}
	active_cards = frappe.get_list(
		"Production Flow Card",
		filters={"docstatus": 1, "production_status": "进行中"},
		fields=["name", "current_progress_status"],
		limit_page_length=0,
	)
	cards = [row.name for row in active_cards if row.current_progress_status not in terminal_progress]
	params["cards"] = cards
	unscheduled = frappe.db.sql(f"""SELECT op.name operation_row, op.idx operation_idx,
		op.parent production_flow_card, op.operation,
		COALESCE(NULLIF(op.operation_name,''), operation_master.production_operation_name, op.operation) operation_name,
		card.customer, customer.customer_name, card.finished_product_name, card.color, card.color_no, card.production_qty,
		card.delivery_date, COALESCE(card.production_priority,'普通') production_priority, op.operation_status,
		operation_master.scheduling_mode, operation_master.default_work_center work_center, operation_master.resource_type,
		operation_master.requires_recipe, operation_master.requires_material_ready,
		operation_master.time_calculation_method, operation_master.fixed_batch_minutes,
		operation_master.minutes_per_kg, operation_master.setup_minutes, operation_master.cleaning_minutes
		FROM `tabProduction Flow Card Operation` op
		INNER JOIN `tabProduction Flow Card` card ON card.name=op.parent AND card.docstatus=1
		LEFT JOIN `tabCustomer` customer ON customer.name=card.customer
		LEFT JOIN `tabProduction Operation` operation_master ON operation_master.name=op.operation
		WHERE card.name IN %(cards)s AND op.operation_status != '已完成'
		AND COALESCE(op.production_schedule,'')='' AND operation_master.scheduling_mode='设备排程'
		AND operation_master.default_work_center='WC-DYE'
		AND NOT EXISTS (
			SELECT 1 FROM `tabDyeing Production Schedule Item` reserved
			INNER JOIN `tabDyeing Production Schedule` plan ON plan.name=reserved.parent
			WHERE plan.docstatus < 2 AND reserved.production_flow_card=op.parent)
		{pending_conditions}
		ORDER BY FIELD(COALESCE(card.production_priority,'普通'),'特急','加急','普通'), card.delivery_date, card.name,
			CASE WHEN TRIM(COALESCE(op.operation_name,''))='染色' THEN 0 ELSE 1 END, op.idx""",
		params, as_dict=True) if cards else []
	# One flow card occupies one dyeing-machine slot.  Prefer its explicit
	# "染色" operation as the representative; otherwise use the first dye-vat step.
	grouped = {}
	for row in unscheduled:
		grouped.setdefault(row.production_flow_card, row)
	unscheduled = list(grouped.values())
	prepared = _get_prepared_tasks(unscheduled)
	for row in unscheduled:
		row.update(_readiness(row.production_flow_card, row.color_no, row, prepared))
		row.suggested_hours = _suggested_hours(row.production_qty, row)
		row.board_task_name = "染色任务"
	conditions = ""
	if work_center:
		conditions += " AND resource.work_center=%(work_center)s"
	if production_resource:
		conditions += " AND item.production_resource=%(production_resource)s"
	params["schedules"] = frappe.get_list("Dyeing Production Schedule", filters={"docstatus": 1},
		pluck="name", limit_page_length=0)
	scheduled = frappe.db.sql(f"""SELECT item.*, schedule.name production_schedule, schedule.production_shift,
		COALESCE(NULLIF(item.operation_name,''), operation_master.production_operation_name, item.operation) operation_display_name,
		resource.resource_name, resource.work_center, work_center_master.work_center_name
		FROM `tabDyeing Production Schedule Item` item
		INNER JOIN `tabDyeing Production Schedule` schedule ON schedule.name=item.parent AND schedule.docstatus=1
		LEFT JOIN `tabProduction Operation` operation_master ON operation_master.name=item.operation
		LEFT JOIN `tabProduction Resource` resource ON resource.name=item.production_resource
		LEFT JOIN `tabProduction Work Center` work_center_master ON work_center_master.name=resource.work_center
		WHERE item.planned_start < DATE_ADD(%(to_date)s, INTERVAL 1 DAY)
		AND item.planned_end > %(from_date)s AND schedule.name IN %(schedules)s {conditions}
		ORDER BY resource.work_center,item.production_resource,item.planned_start""",
		params, as_dict=True) if params["schedules"] else []
	phase_rows = frappe.db.sql("""SELECT flow_operation.parent production_flow_card,
		flow_operation.production_schedule, flow_operation.name operation_row,
		flow_operation.operation,
		COALESCE(NULLIF(flow_operation.operation_name,''), operation_master.production_operation_name,
			flow_operation.operation) operation_name,
		flow_operation.operation_status, flow_operation.schedule_status,
		flow_operation.actual_start, flow_operation.actual_end
		FROM `tabProduction Flow Card Operation` flow_operation
		LEFT JOIN `tabProduction Operation` operation_master
			ON operation_master.name=flow_operation.operation
		WHERE COALESCE(flow_operation.production_schedule,'')!=''
		AND operation_master.default_work_center='WC-DYE'
		ORDER BY flow_operation.parent, flow_operation.idx""", as_dict=True)
	phases_by_task = {}
	for phase in phase_rows:
		phases_by_task.setdefault((phase.production_schedule, phase.production_flow_card), []).append(phase)
	for task in scheduled:
		task.phases = phases_by_task.get((task.production_schedule, task.production_flow_card), [])
		task.current_phase = next((phase for phase in task.phases
			if phase.operation_status in ("生产中", "暂停")), None)
		if not task.current_phase:
			task.current_phase = next((phase for phase in task.phases
				if phase.operation_status != "已完成"), None)
		task.is_last_phase = bool(
			task.phases and (
				all(phase.operation_status == "已完成" for phase in task.phases)
				or (task.current_phase and all(
					phase.operation_status == "已完成"
					or phase.operation_row == task.current_phase.operation_row
					for phase in task.phases
				))
			)
		)
	operation_snapshots = _actual_operation_snapshots(list({
		row.production_flow_card for row in [*unscheduled, *scheduled]
	}))
	for task in [*unscheduled, *scheduled]:
		snapshot = operation_snapshots.get(task.production_flow_card) or {}
		actual = snapshot.get("actual_operation")
		next_operation = snapshot.get("next_operation")
		task.actual_operation_name = actual.operation_name if actual else ""
		task.next_operation_name = next_operation.operation_name if next_operation else (
			"已进入成品环节" if snapshot.get("has_downstream") else "待包装"
		)
		task.missing_operations = [{"name": row.name, "operation_name": row.operation_name}
			for row in snapshot.get("missing_operations", [])]
		task.missing_operation_count = len(task.missing_operations)
	resources = frappe.get_list("Production Resource", filters={"status":["!=","停用"],
		**({"work_center":work_center} if work_center else {}),
		**({"name":production_resource} if production_resource else {})},
		fields=["name","resource_name","resource_type","resource_mode","status","work_center","minimum_capacity","maximum_capacity","rated_capacity","capacity_uom"], order_by="work_center,resource_code", limit_page_length=0)
	center_names = {
		row.name: row.work_center_name for row in frappe.get_all("Production Work Center", fields=["name", "work_center_name"])
	}
	for resource in resources:
		resource.work_center_name = center_names.get(resource.work_center, resource.work_center)
	return {"unscheduled":unscheduled,"scheduled":scheduled,"resources":resources,
		"can_schedule": bool(frappe.has_permission("Dyeing Production Schedule", "create")
			and frappe.has_permission("Dyeing Production Schedule", "submit")),
		"can_execute": bool(frappe.has_permission("Dyeing Production Schedule", "write"))}


def _display_stage(card, current_operation, current_operation_status, has_schedule, paused):
	"""Return the single production stage used by both the TV screen and operation desk."""
	progress = card.current_progress_status or ""
	if card.production_status == "进行中" and progress in ("成品全部出库", "成品全部转客户"):
		progress = ""
	if card.production_status == "进行中" and flt(card.packing_qty) > 0:
		return "包装中"
	if card.production_status == "进行中" and flt(card.warehoused_qty) > 0:
		return "部分入库"
	if "全部入库" in progress:
		return "全部入库"
	if "部分入库" in progress:
		return "部分入库"
	if "包装" in progress:
		return "包装中"
	if any(word in progress for word in ("检验", "质量", "待检")):
		return "质量检验"
	if card.operation_total and card.operation_completed >= card.operation_total:
		return "待包装"
	if paused:
		return "生产暂停"
	if not has_schedule and not card.operation_completed:
		return "待排产"
	operation_name = (current_operation or "").strip()
	if operation_name:
		is_dyeing = any(word in operation_name for word in ("染", "前处理", "后处理"))
		if current_operation_status == "已完成":
			return "染色已完成" if is_dyeing else "后整理已完成"
		return "染色中" if is_dyeing else "后整理中"
	return "已排产" if has_schedule else "待排产"


def _actual_operation_snapshots(flow_cards):
	"""Resolve the furthest reached operation and audit gaps before it.

	A late backfill of an earlier operation must never move actual production progress
	backwards. Sequence is therefore authoritative; timestamps only break ties.
	"""
	if not flow_cards:
		return {}
	rows = frappe.db.sql("""SELECT op.name, op.parent, op.idx, op.operation,
		COALESCE(NULLIF(op.operation_name,''), master.production_operation_name, op.operation) operation_name,
		op.operation_status, op.schedule_status, op.actual_start, op.actual_end
		FROM `tabProduction Flow Card Operation` op
		LEFT JOIN `tabProduction Operation` master ON master.name=op.operation
		WHERE op.parent IN %(flow_cards)s ORDER BY op.parent, op.idx""",
		{"flow_cards": flow_cards}, as_dict=True)
	grouped = {}
	for row in rows:
		grouped.setdefault(row.parent, []).append(row)
	downstream_cards = set(frappe.get_all(
		"Production Flow Card Progress",
		filters={
			"parent": ["in", flow_cards],
			"source_doctype": ["in", [
				"Finished Product Packing Receipt", "Finished Product Delivery",
				"Finished Product Customer Transfer", "Finished Product Return",
				"Finished Product Return to Grey Fabric", "Finished Product to Grey Fabric",
			]],
		},
		pluck="parent",
	))
	result = {}
	for flow_card, operations in grouped.items():
		reached = [row for row in operations if row.operation_status != "待生产"
			or row.actual_start or row.actual_end]
		actual = max(reached, key=lambda row: (
			row.idx,
			row.actual_end or row.actual_start or frappe.utils.get_datetime("1900-01-01"),
		)) if reached else None
		first_pending = next((row for row in operations if row.operation_status != "已完成"), None)
		display = actual or first_pending
		missing = []
		if flow_card in downstream_cards:
			missing = [row for row in operations if row.operation_status == "待生产"
				and not row.actual_start and not row.actual_end]
		elif actual:
			missing = [row for row in operations
				if row.idx < actual.idx and row.operation_status == "待生产"
				and not row.actual_start and not row.actual_end]
		next_operation = None if flow_card in downstream_cards else next((row for row in operations
			if (not actual or row.idx > actual.idx) and row.operation_status != "已完成"), None)
		result[flow_card] = frappe._dict(
			display_operation=display,
			actual_operation=actual,
			next_operation=next_operation,
			has_downstream=flow_card in downstream_cards,
			missing_operations=missing,
		)
	return result


@frappe.whitelist()
def get_production_progress_screen_data():
	"""Read-only, flow-card-level production picture for the workshop TV screen."""
	frappe.has_permission("Production Flow Card", "read", throw=True)
	rows = frappe.db.sql("""
		SELECT card.name production_flow_card, card.flow_card_no, card.flow_card_type,
			card.customer, COALESCE(customer.customer_name, card.customer) customer_name,
			card.finished_product_name, card.color_no, card.color,
			COALESCE(card.production_qty, 0) production_qty,
			COALESCE(card.production_priority, '普通') production_priority,
			card.delivery_date, card.planned_completion_date, card.production_status,
			card.current_progress_status, card.latest_progress_time,
			COALESCE(card.packed_weight, 0) warehoused_qty,
			COALESCE(card.packing_in_progress_weight, 0) packing_qty,
			COALESCE(card.packing_remaining_qty, 0) remaining_qty,
			COALESCE(card.packing_completion_rate, 0) completion_rate,
			COALESCE(operation_summary.operation_total, 0) operation_total,
			COALESCE(operation_summary.operation_completed, 0) operation_completed,
			operation_summary.current_operation, operation_summary.operation_status,
			operation_summary.schedule_status,
			latest_schedule.production_resource, latest_schedule.resource_name,
			latest_schedule.production_shift, latest_schedule.planned_start,
			latest_schedule.planned_end
		FROM `tabProduction Flow Card` card
		LEFT JOIN `tabCustomer` customer ON customer.name=card.customer
		LEFT JOIN (
			SELECT op.parent,
				COUNT(*) operation_total,
				SUM(CASE WHEN op.operation_status='已完成' THEN 1 ELSE 0 END) operation_completed,
				SUBSTRING_INDEX(GROUP_CONCAT(
					CASE WHEN op.operation_status!='已完成'
					THEN COALESCE(NULLIF(op.operation_name,''), master.production_operation_name, op.operation) END
					ORDER BY CASE WHEN op.operation_status IN ('生产中','暂停') THEN 0 ELSE 1 END, op.idx SEPARATOR '||'
				), '||', 1) current_operation,
				SUBSTRING_INDEX(GROUP_CONCAT(
					CASE WHEN op.operation_status!='已完成' THEN op.operation_status END
					ORDER BY CASE WHEN op.operation_status IN ('生产中','暂停') THEN 0 ELSE 1 END, op.idx SEPARATOR '||'
				), '||', 1) operation_status,
				SUBSTRING_INDEX(GROUP_CONCAT(
					CASE WHEN op.operation_status!='已完成' THEN op.schedule_status END
					ORDER BY CASE WHEN op.operation_status IN ('生产中','暂停') THEN 0 ELSE 1 END, op.idx SEPARATOR '||'
				), '||', 1) schedule_status
			FROM `tabProduction Flow Card Operation` op
			LEFT JOIN `tabProduction Operation` master ON master.name=op.operation
			GROUP BY op.parent
		) operation_summary ON operation_summary.parent=card.name
		LEFT JOIN (
			SELECT scheduled.production_flow_card,
				SUBSTRING_INDEX(GROUP_CONCAT(scheduled.production_resource ORDER BY scheduled.planned_start DESC SEPARATOR '||'), '||', 1) production_resource,
				SUBSTRING_INDEX(GROUP_CONCAT(resource.resource_name ORDER BY scheduled.planned_start DESC SEPARATOR '||'), '||', 1) resource_name,
				SUBSTRING_INDEX(GROUP_CONCAT(plan.production_shift ORDER BY scheduled.planned_start DESC SEPARATOR '||'), '||', 1) production_shift,
				MAX(scheduled.planned_start) planned_start, MAX(scheduled.planned_end) planned_end
			FROM `tabDyeing Production Schedule Item` scheduled
			INNER JOIN `tabDyeing Production Schedule` plan ON plan.name=scheduled.parent AND plan.docstatus=1
			LEFT JOIN `tabProduction Resource` resource ON resource.name=scheduled.production_resource
			GROUP BY scheduled.production_flow_card
		) latest_schedule ON latest_schedule.production_flow_card=card.name
		WHERE card.docstatus=1 AND card.production_status!='已关闭'
		AND NOT (card.production_status='已完成'
			AND COALESCE(card.current_progress_status,'') IN ('成品全部出库', '成品全部转客户'))
		AND (card.production_status='进行中'
			OR DATE(COALESCE(card.latest_progress_time, card.modified))=CURDATE())
	""", as_dict=True)

	today = getdate()
	snapshots = _actual_operation_snapshots([card.production_flow_card for card in rows])
	stage_order = {"生产暂停": 0, "待排产": 1, "已排产": 2, "染色中": 3, "染色已完成": 4,
		"后整理中": 5, "后整理已完成": 6, "质量检验": 7, "待包装": 8, "包装中": 9,
		"部分入库": 8, "全部入库": 9}
	priority_order = {"特急": 0, "加急": 1, "普通": 2}
	alerts_by_card = {}
	def add_alert(card, level, message):
		entry = alerts_by_card.setdefault(card.production_flow_card, {
			"level": level, "flow_card": card.flow_card_no or card.production_flow_card, "messages": [],
		})
		if level == "danger":
			entry["level"] = "danger"
		entry["messages"].append(message)

	for card in rows:
		snapshot = snapshots.get(card.production_flow_card) or {}
		display = snapshot.get("display_operation")
		if display:
			card.current_operation = display.operation_name
			card.operation_status = display.operation_status
			card.actual_progress_time = display.actual_end or display.actual_start
		card.missing_operations = [{"name": row.name, "operation_name": row.operation_name}
			for row in snapshot.get("missing_operations", [])]
		card.missing_operation_count = len(card.missing_operations)
		paused = card.operation_status == "暂停" or card.schedule_status == "暂停"
		card.stage = _display_stage(card, card.current_operation, card.operation_status,
			bool(card.production_resource), paused)
		next_operation = snapshot.get("next_operation")
		if card.stage == "包装中":
			card.next_operation = "待成品入库"
		elif card.stage == "部分入库":
			card.next_operation = "继续成品入库"
		elif card.stage == "全部入库":
			card.next_operation = "生产完成"
		elif next_operation:
			card.next_operation = next_operation.operation_name
		else:
			card.next_operation = "待包装"
		deadline = card.planned_completion_date or card.delivery_date
		card.is_overdue = bool(deadline and getdate(deadline) < today and card.stage != "全部入库")
		card.progress_percent = flt(card.operation_completed / card.operation_total * 65, 1) if card.operation_total else 0
		if card.stage in ("待包装", "包装中"):
			card.progress_percent = max(card.progress_percent, 75)
		elif card.stage == "部分入库":
			card.progress_percent = max(card.progress_percent, min(95, 80 + flt(card.completion_rate) * 0.15))
		elif card.stage == "全部入库":
			card.progress_percent = 100
		card.packed_qty = flt(card.warehoused_qty) + flt(card.packing_qty)
		if paused:
			add_alert(card, "danger", f"{card.current_operation or '当前工序'}已暂停")
		if card.is_overdue:
			add_alert(card, "danger", f"已超过计划完成日期 {deadline}")
		if card.missing_operation_count:
			names = "、".join(row["operation_name"] for row in card.missing_operations)
			add_alert(card, "warning", f"实际进度已到{card.stage}，{names}未登记，等待补录")

	rows.sort(key=lambda card: (
		0 if card.is_overdue or card.stage == "生产暂停" else 1,
		priority_order.get(card.production_priority, 9),
		card.delivery_date or "9999-12-31",
		stage_order.get(card.stage, 99), card.production_flow_card,
	))
	summary = {
		"total": len(rows),
		"in_production": sum(card.stage in ("已排产", "染色中", "染色已完成", "后整理中",
			"后整理已完成", "质量检验", "生产暂停") for card in rows),
		"waiting_packing": sum(card.stage in ("待包装", "包装中") for card in rows),
		"partial_receipt": sum(card.stage == "部分入库" for card in rows),
		"exceptions": sum(bool(card.is_overdue or card.stage == "生产暂停" or card.missing_operation_count) for card in rows),
		"completed_today": sum(card.stage == "全部入库" for card in rows),
	}
	alerts = [{
		"level": entry["level"],
		"flow_card": entry["flow_card"],
		"message": f"{entry['flow_card']}：{' · '.join(entry['messages'])}",
	} for entry in alerts_by_card.values()]
	alerts.sort(key=lambda row: (0 if row["level"] == "danger" else 1, row["flow_card"]))
	return {"summary": summary, "cards": rows, "alerts": alerts[:20], "refreshed_at": frappe.utils.now_datetime()}


@frappe.whitelist()
def get_batch_tasks(work_center=None, production_resource=None, customer=None, delivery_before=None):
	tasks = get_board_data(work_center=work_center, production_resource=production_resource)["unscheduled"]
	return [task for task in tasks
		if (not customer or task.customer == customer)
		and (not delivery_before or (task.delivery_date and getdate(task.delivery_date) <= getdate(delivery_before)))]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_available_operations(doctype, txt, searchfield, start, page_len, filters):
	card = (filters or {}).get("production_flow_card")
	if not card:
		return []
	tasks = get_batch_tasks()
	options = {}
	for task in tasks:
		if task.production_flow_card == card and txt.lower() in (
			f"{task.operation} {task.operation_name}".lower()
		):
			options[task.operation] = task.operation_name
	return list(options.items())[cint(start):cint(start) + cint(page_len)]


def _next_free_slot(start, hours, end, busy):
	duration = timedelta(hours=flt(hours))
	if duration.total_seconds() <= 0:
		return None
	for blocked_start, blocked_end in sorted(busy):
		if blocked_end <= start:
			continue
		if start + duration <= blocked_start:
			break
		start = max(start, blocked_end)
	return (start, start + duration) if start + duration <= end else None


@frappe.whitelist()
def generate_batch_schedule(operation_rows, production_resource, planned_start, planned_end,
	current_schedule=None, current_items=None):
	"""Preview one-resource sequential scheduling; saving the document reserves the tasks."""
	frappe.has_permission("Dyeing Production Schedule", "create" if not current_schedule else "write", throw=True)
	if current_schedule:
		doc = frappe.get_doc("Dyeing Production Schedule", current_schedule)
		doc.check_permission("write")
		if doc.docstatus != 0:
			frappe.throw(_("只能向草稿排程添加任务。"))
	if not planned_start or not planned_end:
		frappe.throw(_("请填写排程开始和结束时间。"))
	start, end = get_datetime(planned_start), get_datetime(planned_end)
	if end <= start:
		frappe.throw(_("排程结束时间必须晚于开始时间。"))
	rows = frappe.parse_json(operation_rows)
	existing = frappe.parse_json(current_items) if current_items else []
	if not isinstance(rows, list) or not rows or len(rows) > 200:
		frappe.throw(_("请选择 1 至 200 项工序任务。"))
	if not isinstance(existing, list) or any(not isinstance(row, dict) for row in existing):
		frappe.throw(_("排程明细格式不正确。"))
	resource = frappe.get_doc("Production Resource", production_resource)
	resource.check_permission("read")
	if resource.status not in ("启用", "空闲", "生产中"):
		frappe.throw(_("该生产资源当前不可排产。"))
	candidates = {task.operation_row: task for task in get_batch_tasks(production_resource=resource.name)}
	busy = [(get_datetime(row[0]), get_datetime(row[1])) for row in frappe.db.sql("""
		SELECT item.planned_start, item.planned_end FROM `tabDyeing Production Schedule Item` item
		INNER JOIN `tabDyeing Production Schedule` plan ON plan.name=item.parent
		WHERE plan.docstatus < 2 AND item.parent != %(current)s AND item.production_resource=%(resource)s
		AND item.planned_start < %(end)s AND item.planned_end > %(start)s
		UNION ALL
		SELECT start_datetime, end_datetime FROM `tabMachine Production Calendar`
		WHERE docstatus < 2 AND production_resource=%(resource)s
		AND start_datetime < %(end)s AND end_datetime > %(start)s
		""", {"resource": resource.name, "current": current_schedule or "", "start": start, "end": end})]
	existing_keys = {row.get("operation_row") for row in existing}
	for row in existing:
		if row.get("production_resource") == resource.name and row.get("planned_start") and row.get("planned_end"):
			busy.append((get_datetime(row["planned_start"]), get_datetime(row["planned_end"])))
	items, skipped, seen = [], [], set()
	cursor = start
	for key in rows:
		if not isinstance(key, str):
			frappe.throw(_("工序任务格式不正确。"))
		if key in seen:
			continue
		seen.add(key)
		task = candidates.get(key)
		reason = None
		if key in existing_keys:
			reason = "已在当前明细中"
		elif not task:
			reason = "任务已被占用、不可排程或与所选资源不匹配"
		else:
			maximum = flt(resource.maximum_capacity or resource.rated_capacity)
			if maximum and flt(task.production_qty) > maximum + 0.000001:
				reason = "生产数量超过资源容量"
			elif flt(task.production_qty) < flt(resource.minimum_capacity) - 0.000001:
				reason = "生产数量低于最小装载量"
		slot = _next_free_slot(cursor, task.suggested_hours, end, busy) if not reason else None
		if not reason and not slot:
			reason = "排程范围内没有足够的连续空闲时间"
		if reason:
			skipped.append({"operation_row": key,
				"task": f"{task.production_flow_card} · {task.operation_name}" if task else key, "reason": reason})
			continue
		item = {field: task.get(field) for field in (
			"production_flow_card", "operation", "operation_row", "operation_name", "scheduling_mode",
			"work_center", "resource_type", "customer_name", "finished_product_name", "color",
			"production_priority", "production_qty", "delivery_date", "readiness_status")}
		item.update(production_resource=resource.name, resource_name=resource.resource_name,
			planned_start=slot[0], planned_end=slot[1], estimated_hours=task.suggested_hours,
			load_rate=flt(task.production_qty) / maximum * 100 if maximum else 0, schedule_status="已排程")
		items.append(item)
		busy.append(slot)
		cursor = slot[1]
	return {"items": items, "skipped": skipped}


@frappe.whitelist()
def create_schedule_from_task(production_flow_card, operation, production_resource, planned_start, planned_end,
	production_shift=None, operation_row=None, remarks=None):
	"""Create and publish one schedule directly from the production board."""
	frappe.has_permission("Dyeing Production Schedule", "create", throw=True)
	frappe.has_permission("Dyeing Production Schedule", "submit", throw=True)
	frappe.get_doc("Production Resource", production_resource).check_permission("read")
	details = get_task_details(production_flow_card, operation, operation_row)
	if details.get("scheduling_mode") == "仅记录进度":
		frappe.throw(_("该工序只需要登记进度，不需要排程。"))
	if frappe.db.get_value("Production Flow Card Operation", details["operation_row"], "production_schedule"):
		frappe.throw(_("该工序已经排程，请刷新看板。"))

	if not planned_start or not planned_end:
		frappe.throw(_("请填写计划开始和结束时间。"))
	start = get_datetime(planned_start)
	end = get_datetime(planned_end)
	if end <= start:
		frappe.throw(_("计划结束时间必须晚于开始时间。"))

	doc = frappe.get_doc({
		"doctype": "Dyeing Production Schedule",
		"schedule_date": start.date(),
		"from_datetime": start,
		"to_datetime": end,
		"production_shift": production_shift or details.get("default_shift"),
		"remarks": remarks,
		"items": [{
			"production_flow_card": production_flow_card,
			"operation": operation,
			"operation_row": details["operation_row"],
			"production_resource": production_resource,
			"planned_start": start,
			"planned_end": end,
			"schedule_status": "已排程",
			"remarks": remarks,
		}],
	})
	doc.insert()
	doc.submit()
	return doc.name


def _get_execution_item(schedule_name, schedule_item):
	doc = frappe.get_doc("Dyeing Production Schedule", schedule_name)
	doc.check_permission("write")
	if doc.docstatus != 1:
		frappe.throw(_("只能操作已发布的染色排程。"))
	item = next((row for row in doc.items if row.name == schedule_item), None)
	if not item:
		frappe.throw(_("排程中找不到该染色任务。"))
	frappe.db.get_value("Dyeing Production Schedule Item", item.name, "name", for_update=True)
	frappe.db.get_value("Production Resource", item.production_resource, "name", for_update=True)
	item.schedule_status = frappe.db.get_value(
		"Dyeing Production Schedule Item", item.name, "schedule_status"
	)
	return doc, item


def _get_execution_phases(item):
	rows = frappe.db.sql("""SELECT flow_operation.name, flow_operation.operation,
		COALESCE(NULLIF(flow_operation.operation_name,''), operation_master.production_operation_name,
			flow_operation.operation) operation_name,
		flow_operation.operation_status, flow_operation.schedule_status,
		flow_operation.actual_start, flow_operation.actual_end
		FROM `tabProduction Flow Card Operation` flow_operation
		INNER JOIN `tabProduction Operation` operation_master
			ON operation_master.name=flow_operation.operation
		WHERE flow_operation.parent=%(flow_card)s
		AND flow_operation.production_schedule=%(schedule)s
		AND operation_master.default_work_center='WC-DYE'
		ORDER BY flow_operation.idx FOR UPDATE""", {
			"flow_card": item.production_flow_card, "schedule": item.parent,
		}, as_dict=True)
	if not rows:
		frappe.throw(_("该排程没有可执行的染色工序。"))
	return rows


def _current_execution_phase(phases):
	return next((row for row in phases if row.operation_status in ("生产中", "暂停")), None)


def _refresh_flow_card_operation_summary(flow_card):
	pending = frappe.db.sql("""
		SELECT operation FROM `tabProduction Flow Card Operation`
		WHERE parent=%s AND operation_status!='已完成'
		ORDER BY idx LIMIT 1
	""", flow_card)
	frappe.db.set_value("Production Flow Card", flow_card, {
		"current_operation": pending[0][0] if pending else None,
		"is_completed": 0 if pending else 1,
	}, update_modified=False)


def _add_execution_progress(item, status, description, quantity=0, operation=None):
	from dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card import (
		record_production_progress,
	)

	record_production_progress(
		item.production_flow_card,
		operation or item.operation,
		status,
		"Dyeing Production Schedule",
		item.parent,
		quantity=quantity,
		uom=frappe.db.get_value("Production Resource", item.production_resource, "capacity_uom") or "Kg",
		production_resource=item.production_resource,
		description=description,
	)


@frappe.whitelist()
def start_dyeing(schedule_name, schedule_item):
	_, item = _get_execution_item(schedule_name, schedule_item)
	if item.schedule_status != "已排程":
		frappe.throw(_("只有已排程的任务才能开始染色。"))
	resource_status = frappe.db.get_value("Production Resource", item.production_resource, "status")
	if resource_status in ("停用", "清洗", "维修", "停机"):
		frappe.throw(_("生产机台当前不可开始染色。"))
	now = frappe.utils.now_datetime()
	phases = _get_execution_phases(item)
	phase = next((row for row in phases if row.operation_status != "已完成"), None)
	if not phase:
		frappe.throw(_("染色任务的工序已全部完成。"))
	frappe.db.set_value("Dyeing Production Schedule Item", item.name, {
		"schedule_status": "生产中", "actual_start": now, "operator": frappe.session.user,
	}, update_modified=False)
	frappe.db.set_value("Production Flow Card Operation", phase.name, {
		"operation_status": "生产中", "schedule_status": "生产中", "actual_start": now,
	}, update_modified=False)
	frappe.db.set_value("Production Resource", item.production_resource, "status", "生产中", update_modified=False)
	_add_execution_progress(item, f"{phase.operation_name}生产中",
		f"已在生产排程看板开始{phase.operation_name}。", operation=phase.operation)
	return {"status": "生产中", "actual_start": now, "current_phase": phase.operation_name}


@frappe.whitelist()
def toggle_dyeing_pause(schedule_name, schedule_item):
	_, item = _get_execution_item(schedule_name, schedule_item)
	if item.schedule_status not in ("生产中", "暂停"):
		frappe.throw(_("只有生产中或暂停的任务才能执行该操作。"))
	paused = item.schedule_status == "生产中"
	new_status = "暂停" if paused else "生产中"
	phases = _get_execution_phases(item)
	phase = _current_execution_phase(phases)
	if not phase:
		frappe.throw(_("找不到生产中的染色工序。"))
	frappe.db.set_value(
		"Dyeing Production Schedule Item", item.name, "schedule_status", new_status, update_modified=False
	)
	frappe.db.set_value("Production Flow Card Operation", phase.name, {
		"operation_status": new_status, "schedule_status": new_status,
	}, update_modified=False)
	_add_execution_progress(
		item,
		f"{phase.operation_name}{'暂停' if paused else '恢复'}",
		f"{phase.operation_name}已{'暂停' if paused else '恢复生产'}。",
		operation=phase.operation,
	)
	return {"status": new_status, "current_phase": phase.operation_name}


@frappe.whitelist()
def complete_dyeing(schedule_name, schedule_item, actual_qty=0, execution_remarks=None):
	_, item = _get_execution_item(schedule_name, schedule_item)
	if item.schedule_status not in ("生产中", "暂停"):
		frappe.throw(_("请先开始染色，再完成任务。"))
	phases = _get_execution_phases(item)
	phase = _current_execution_phase(phases)
	if not phase:
		frappe.throw(_("找不到生产中的染色工序。"))
	remaining = [row for row in phases if row.name != phase.name and row.operation_status != "已完成"]
	is_final = not remaining
	actual_qty = flt(actual_qty)
	if is_final and actual_qty <= 0:
		frappe.throw(_("最后一道染色工序完成时，实际染色数量必须大于0。"))
	now = frappe.utils.now_datetime()
	frappe.db.set_value("Production Flow Card Operation", phase.name, {
		"operation_status": "已完成", "schedule_status": "已完成", "actual_end": now,
	}, update_modified=False)
	if not is_final:
		next_phase = remaining[0]
		frappe.db.set_value("Production Flow Card Operation", next_phase.name, {
			"operation_status": "生产中", "schedule_status": "生产中", "actual_start": now,
		}, update_modified=False)
		frappe.db.set_value("Dyeing Production Schedule Item", item.name, {
			"schedule_status": "生产中", "operator": frappe.session.user,
		}, update_modified=False)
		_refresh_flow_card_operation_summary(item.production_flow_card)
		_add_execution_progress(item, f"{phase.operation_name}已完成",
			f"{phase.operation_name}已完成，自动进入{next_phase.operation_name}。", operation=phase.operation)
		return {"status": "生产中", "completed_phase": phase.operation_name,
			"current_phase": next_phase.operation_name, "task_completed": False}
	frappe.db.set_value("Dyeing Production Schedule Item", item.name, {
		"schedule_status": "已完成", "actual_end": now, "actual_qty": actual_qty,
		"operator": frappe.session.user, "execution_remarks": execution_remarks,
	}, update_modified=False)
	_refresh_flow_card_operation_summary(item.production_flow_card)
	other_active = frappe.db.exists("Dyeing Production Schedule Item", {
		"production_resource": item.production_resource,
		"name": ["!=", item.name],
		"schedule_status": ["in", ["生产中", "暂停"]],
	})
	if not other_active:
		frappe.db.set_value("Production Resource", item.production_resource, "status", "空闲", update_modified=False)
	_add_execution_progress(
		item,
		f"{phase.operation_name}已完成",
		execution_remarks or f"{phase.operation_name}已完成，染色任务全部完成。",
		quantity=actual_qty,
		operation=phase.operation,
	)
	return {"status": "已完成", "actual_end": now, "actual_qty": actual_qty,
		"completed_phase": phase.operation_name, "task_completed": True}


@frappe.whitelist()
def backfill_skipped_operations(production_flow_card, operation_rows, completed_at, reason):
	"""Complete missing earlier operations with an explicit audited backfill record."""
	card = frappe.get_doc("Production Flow Card", production_flow_card)
	card.check_permission("write")
	if card.docstatus != 1 or card.production_status == "已关闭":
		frappe.throw(_("只能补录已提交且未关闭的生产流转卡。"))
	selected = frappe.parse_json(operation_rows)
	if not isinstance(selected, list) or not selected or len(selected) > 50:
		frappe.throw(_("请选择需要补录的前序工序。"))
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("请填写补录原因。"))
	completed_at = get_datetime(completed_at)
	if completed_at > frappe.utils.now_datetime():
		frappe.throw(_("补录完成时间不能晚于当前时间。"))
	snapshot = _actual_operation_snapshots([card.name]).get(card.name) or {}
	allowed = {row.name: row for row in snapshot.get("missing_operations", [])}
	invalid = [name for name in selected if name not in allowed]
	if invalid:
		frappe.throw(_("前序工序状态已变化，请刷新操作台后重试。"))
	actual = snapshot.get("actual_operation")
	actual_time = actual and (actual.actual_start or actual.actual_end)
	if actual_time and completed_at > get_datetime(actual_time):
		frappe.throw(_("补录时间不能晚于后续工序的实际时间 {0}。").format(actual_time))

	from dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card import (
		record_production_progress,
	)
	for name in selected:
		row = allowed[name]
		frappe.db.set_value("Production Flow Card Operation", name, {
			"operation_status": "已完成", "actual_start": completed_at, "actual_end": completed_at,
		}, update_modified=False)
		record_production_progress(
			card.name, row.operation, f"{row.operation_name}已补录",
			"Production Flow Card", card.name,
			description=f"由 {frappe.session.user} 补录前序工序。原因：{reason}",
		)
	_refresh_flow_card_operation_summary(card.name)
	return {"completed": len(selected), "operations": [allowed[name].operation_name for name in selected]}

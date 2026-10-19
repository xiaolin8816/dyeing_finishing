frappe.pages["production-schedule-board"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: "生产排程操作台", single_column: true });
	const api = "dyeing_finishing.dyeing_finishing.doctype.dyeing_production_schedule.dyeing_production_schedule.";
	let ready = false, request = 0, data = {};
	page.add_inner_button("刷新", () => load());
	if (frappe.user.has_role(["System Manager", "Manufacturing Manager"])) {
		page.add_menu_item("排程记录", () => frappe.set_route("List", "Dyeing Production Schedule"));
		page.add_menu_item("设备停机记录", () => frappe.set_route("List", "Machine Production Calendar"));
	}
	const today = frappe.datetime.get_today();
	const from = page.add_field({ label: "开始日期", fieldname: "from_date", fieldtype: "Date", default: today, change: () => load() });
	const to = page.add_field({ label: "结束日期", fieldname: "to_date", fieldtype: "Date", default: today, change: () => load() });
	const center = page.add_field({
		label: "生产工段", fieldname: "work_center", fieldtype: "Link", options: "Production Work Center",
		change: () => { if (ready) { resource.set_value(""); load(); } },
	});
	const resource = page.add_field({
		label: "生产机台", fieldname: "production_resource", fieldtype: "Link", options: "Production Resource",
		get_query: () => ({ filters: {
			status: ["in", ["启用", "空闲", "生产中"]],
			...(center.get_value() ? { work_center: center.get_value() } : {}),
		} }), change: () => load(),
	});
	const root = $("<div class='production-schedule-board'></div>").appendTo(page.main);
	$(`<style>
	.production-schedule-board .psb-grid{display:grid;grid-template-columns:minmax(300px,35%) minmax(0,1fr);gap:24px;margin-top:16px}
	.production-schedule-board h4{font-size:16px;margin:0 0 12px}
	.production-schedule-board .psb-task{border:1px solid var(--border-color);border-left:3px solid var(--blue-500);border-radius:6px;padding:12px;margin-bottom:10px;overflow-wrap:anywhere}
	.production-schedule-board .psb-head{display:flex;justify-content:space-between;align-items:center;gap:8px}
	.production-schedule-board .psb-line{margin-top:6px;font-size:13px}
	.production-schedule-board .psb-missing{color:var(--text-muted);font-size:12px;margin-top:6px}
	.production-schedule-board .psb-resource{border-bottom:1px solid var(--border-color);padding:12px 0}
	.production-schedule-board .psb-slots{display:flex;gap:10px;overflow-x:auto;margin-top:8px}
	.production-schedule-board .psb-slot{flex:0 0 250px;border:1px solid var(--border-color);border-radius:6px;padding:10px;overflow-wrap:anywhere}
	.production-schedule-board .psb-slot small{display:block;margin-top:5px}
	.production-schedule-board .psb-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
	.production-schedule-board .psb-phases{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
	.production-schedule-board .psb-phase{border:1px solid var(--border-color);border-radius:12px;padding:2px 8px;font-size:12px}
	.production-schedule-board .psb-phase.done{background:var(--green-100);color:var(--green-700)}
	.production-schedule-board .psb-phase.active{background:var(--blue-100);color:var(--blue-700)}
	.production-schedule-board .psb-phase.paused{background:var(--orange-100);color:var(--orange-700)}
	@media(max-width:900px){.production-schedule-board .psb-grid{grid-template-columns:minmax(0,1fr)}}
	</style>`).appendTo(page.main);
	const esc = (value) => frappe.utils.escape_html(String(value == null ? "" : value));
	const badge = (value) => `<span class="indicator-pill ${value === "可以排产" ? "green" : value === "部分准备" ? "orange" : "red"}">${esc(value)}</span>`;
	root.on("click", "[data-task]", function () { arrange(data.unscheduled[Number($(this).attr("data-task"))]); });
	root.on("click", "[data-card]", function (event) {
		event.preventDefault();
		frappe.set_route("Form", "Production Flow Card", $(this).attr("data-card"));
	});
	root.on("click", "[data-schedule]", function (event) {
		event.preventDefault();
		frappe.set_route("Form", "Dyeing Production Schedule", $(this).attr("data-schedule"));
	});
	root.on("click", "[data-exec]", async function (event) {
		event.preventDefault();
		event.stopPropagation();
		const action = $(this).attr("data-exec");
		const task = (data.scheduled || []).find((row) => row.name === $(this).attr("data-item"));
		if (!task) return;
		if (action === "backfill") return backfillMissingOperations(task);
		if (action === "complete") return completeTask(task);
		const label = action === "start" ? "开始染色" : task.schedule_status === "暂停" ? "恢复染色" : "暂停染色";
		frappe.confirm(`确认${label}？`, async () => {
			await frappe.call({
				method: api + (action === "start" ? "start_dyeing" : "toggle_dyeing_pause"),
				args: { schedule_name: task.production_schedule, schedule_item: task.name },
				freeze: true, freeze_message: `正在${label}…`,
			});
			frappe.show_alert({ message: `已${label}`, indicator: "green" });
			load();
		});
	});
	async function load() {
		if (!ready) return;
		const current = ++request;
		if (!from.get_value() || !to.get_value()) return;
		if (moment(to.get_value()).isBefore(moment(from.get_value()))) {
			root.html('<div class="text-muted p-4">结束日期不能早于开始日期</div>');
			return;
		}
		root.html('<div class="text-muted p-4">正在读取排程…</div>');
		try {
			const response = await frappe.call({ method: api + "get_board_data", args: {
				from_date: from.get_value(), to_date: to.get_value(),
				work_center: center.get_value(), production_resource: resource.get_value(),
			} });
			if (current !== request) return;
			data = response.message || {};
			render();
		} catch (error) {
			if (current === request) root.html('<div class="text-muted p-4">读取失败，请刷新重试</div>');
		}
	}
	function render() {
		const taskActions = (task) => {
			if (!data.can_execute) return "";
			const backfill = task.missing_operation_count
				? `<button class="btn btn-warning btn-xs" data-exec="backfill" data-item="${esc(task.name)}">补录前序工序</button>` : "";
			if (task.schedule_status === "已排程") return `${backfill}<button class="btn btn-primary btn-xs" data-exec="start" data-item="${esc(task.name)}">开始染色</button>`;
			const completeLabel = task.is_last_phase ? "完成染色" : "完成当前工序";
			if (task.schedule_status === "生产中") return `${backfill}<button class="btn btn-default btn-xs" data-exec="pause" data-item="${esc(task.name)}">暂停</button><button class="btn btn-primary btn-xs" data-exec="complete" data-item="${esc(task.name)}">${completeLabel}</button>`;
			if (task.schedule_status === "暂停") return `${backfill}<button class="btn btn-default btn-xs" data-exec="pause" data-item="${esc(task.name)}">恢复</button><button class="btn btn-primary btn-xs" data-exec="complete" data-item="${esc(task.name)}">${completeLabel}</button>`;
			return backfill;
		};
		const phaseSteps = (task) => (task.phases || []).map((phase) => {
			const cls = phase.operation_status === "已完成" ? "done" : phase.operation_status === "暂停" ? "paused" : phase.operation_status === "生产中" ? "active" : "";
			return `<span class="psb-phase ${cls}">${esc(phase.operation_name)} · ${esc(phase.operation_status)}</span>`;
		}).join("");
		const pending = (data.unscheduled || []).map((task, index) => `
			<div class="psb-task">
				<div class="psb-head"><a href="#" data-card="${esc(task.production_flow_card)}">${esc(task.production_flow_card)}</a>
				${data.can_schedule ? `<button class="btn btn-default btn-xs" data-task="${index}">安排</button>` : ""}</div>
				<div class="psb-line"><b>${esc(task.board_task_name || task.operation_name || task.operation)}</b> · ${esc(task.production_qty)} · ${esc(task.production_priority)}</div>
				<div class="psb-line">${esc(task.customer_name)} · ${esc(task.finished_product_name)} · ${esc(task.color)}</div>
				<div class="psb-line">实际进度 ${esc(task.actual_operation_name || "未开始")} · 下一道 ${esc(task.next_operation_name)}</div>
				<div class="psb-line">交期 ${esc(task.delivery_date || "未设置")} · ${badge(task.readiness_status)}</div>
				${(task.readiness_missing || []).length ? `<div class="psb-missing">${task.readiness_missing.map(esc).join("、")}</div>` : ""}
			</div>`).join("") || '<div class="text-muted">没有待排任务</div>';
		const byResource = {};
		(data.scheduled || []).forEach((task) => { (byResource[task.production_resource] ||= []).push(task); });
		const rows = (data.resources || []).map((item) => `
			<div class="psb-resource"><b>${esc(item.resource_name || item.name)}</b>
				<div class="psb-missing">${esc(item.work_center_name || item.work_center)} · ${esc(item.resource_type)} · ${esc(item.status)}
				${item.maximum_capacity || item.rated_capacity ? ` · 容量 ${esc(item.maximum_capacity || item.rated_capacity)} ${esc(item.capacity_uom)}` : ""}</div>
				<div class="psb-slots">${(byResource[item.name] || []).map((task) => `
					<div class="psb-slot"><a href="#" data-schedule="${esc(task.production_schedule)}">${esc(task.production_flow_card)}</a>
					<div class="psb-line"><b>染色任务</b> · ${esc(task.color)} · ${esc(task.schedule_status)}</div>
					<div class="psb-line">实际进度 ${esc(task.actual_operation_name || "未开始")} · 下一道 ${esc(task.next_operation_name)}</div>
					<div class="psb-phases">${phaseSteps(task)}</div>
					${task.missing_operation_count ? `<div class="psb-missing" style="color:var(--orange-600)">待补录：${task.missing_operations.map((row) => esc(row.operation_name)).join("、")}</div>` : ""}
					<small>${esc(task.planned_start)} → ${esc(task.planned_end)}</small>
					<small>数量 ${esc(task.production_qty)}${task.load_rate ? ` · 装载 ${esc(task.load_rate)}%` : ""}</small>
					${task.actual_start ? `<small>实际开始 ${esc(task.actual_start)}</small>` : ""}
					${task.actual_end ? `<small>实际完成 ${esc(task.actual_end)}</small>` : ""}
					<div class="psb-actions">${taskActions(task)}</div></div>
				`).join("") || '<span class="text-muted">暂无排程</span>'}</div>
			</div>`).join("") || '<div class="text-muted">没有匹配的生产资源</div>';
		root.html(`<div class="psb-grid"><section><h4>待排任务（${(data.unscheduled || []).length}）</h4>${pending}</section>
			<section><h4>资源排程</h4>${rows}</section></div>`);
	}
	function backfillMissingOperations(task) {
		const missing = task.missing_operations || [];
		if (!missing.length) {
			frappe.show_alert({ message: "当前没有需要补录的前序工序", indicator: "blue" });
			return;
		}
		const referenceTime = task.current_phase?.actual_start || task.actual_start || frappe.datetime.now_datetime();
		const dialog = new frappe.ui.Dialog({
			title: `补录前序工序 · ${esc(task.production_flow_card)}`,
			fields: [
				{ fieldname: "operation_notice", fieldtype: "HTML", options:
					`<div class="alert alert-warning">后续工序已开始或完成，以下前序工序未登记：<br><b>${missing.map((row) => esc(row.operation_name)).join("、")}</b><br><small>补录会保留操作人、时间和原因，不会改变当前实际工序。</small></div>` },
				{ fieldname: "completed_at", label: "实际完成时间", fieldtype: "Datetime", reqd: 1, default: referenceTime },
				{ fieldname: "reason", label: "补录原因", fieldtype: "Small Text", reqd: 1 },
			],
			primary_action_label: "确认补录",
			async primary_action(values) {
				dialog.disable_primary_action();
				try {
					await frappe.call({ method: api + "backfill_skipped_operations", args: {
						production_flow_card: task.production_flow_card,
						operation_rows: missing.map((row) => row.name),
						completed_at: values.completed_at, reason: values.reason,
					}, freeze: true, freeze_message: "正在补录前序工序…" });
					dialog.hide();
					frappe.show_alert({ message: `已补录 ${missing.length} 道前序工序`, indicator: "green" });
					load();
				} finally { dialog.enable_primary_action(); }
			},
		});
		dialog.show();
	}
	function completeTask(task) {
		if (!task.is_last_phase) {
			const phaseName = task.current_phase?.operation_name || "当前工序";
			frappe.confirm(`确认完成${esc(phaseName)}，并自动进入下一道染色工序？`, async () => {
				const response = await frappe.call({ method: api + "complete_dyeing", args: {
					schedule_name: task.production_schedule, schedule_item: task.name, actual_qty: 0,
				}, freeze: true, freeze_message: "正在完成当前工序…" });
				const next = response.message?.current_phase;
				frappe.show_alert({ message: next ? `已进入${next}` : "当前工序已完成", indicator: "green" });
				load();
			});
			return;
		}
		const dialog = new frappe.ui.Dialog({
			title: `完成染色 · ${esc(task.production_flow_card)}`,
			fields: [
				{ fieldname: "actual_qty", label: "实际染色数量", fieldtype: "Float", reqd: 1, default: task.production_qty },
				{ fieldname: "execution_remarks", label: "生产说明", fieldtype: "Small Text" },
			],
			primary_action_label: "确认完成",
			async primary_action(values) {
				dialog.disable_primary_action();
				try {
					await frappe.call({ method: api + "complete_dyeing", args: {
						schedule_name: task.production_schedule, schedule_item: task.name,
						actual_qty: values.actual_qty, execution_remarks: values.execution_remarks,
					}, freeze: true, freeze_message: "正在完成染色…" });
					dialog.hide();
					frappe.show_alert({ message: "染色任务已完成", indicator: "green" });
					load();
				} finally { dialog.enable_primary_action(); }
			},
		});
		dialog.show();
	}
	async function arrange(task) {
		if (!task) return;
		const response = await frappe.call({ method: api + "get_task_details", args: {
			production_flow_card: task.production_flow_card, operation: task.operation, operation_row: task.operation_row,
		} });
		const details = response.message;
		const filters = {
			status: ["in", ["启用", "空闲", "生产中"]],
			...(details.work_center ? { work_center: details.work_center } : {}),
			...(details.resource_type ? { resource_type: details.resource_type } : {}),
		};
		const candidates = (data.resources || []).filter((item) =>
			["启用", "空闲", "生产中"].includes(item.status) &&
			(!details.work_center || item.work_center === details.work_center) &&
			(!details.resource_type || item.resource_type === details.resource_type));
		let dialog, submitting = false;
		const updateEnd = () => {
			if (!dialog) return;
			const start = dialog.get_value("planned_start"), hours = Number(dialog.get_value("estimated_hours"));
			if (start && hours > 0) dialog.set_value("planned_end", moment(start).add(hours, "hours").format("YYYY-MM-DD HH:mm:ss"));
		};
		dialog = new frappe.ui.Dialog({
			title: `安排 · ${esc(task.production_flow_card)} · ${esc(task.board_task_name || task.operation_name)}`,
			fields: [
				{ fieldname: "readiness", fieldtype: "HTML",
					options: `${badge(details.readiness_status)} <span class="text-muted">${(details.readiness_missing || []).map(esc).join("、")}</span>` },
				{ fieldname: "production_resource", label: "生产机台", fieldtype: "Link", options: "Production Resource",
					reqd: 1, get_query: () => ({ filters }), default: candidates.length === 1 ? candidates[0].name : undefined },
				{ fieldname: "planned_start", label: "开始时间", fieldtype: "Datetime", reqd: 1,
					default: from.get_value() === frappe.datetime.get_today() ? frappe.datetime.now_datetime() : `${from.get_value()} 08:00:00`, change: updateEnd },
				{ fieldname: "estimated_hours", label: "预计工时（小时）", fieldtype: "Float",
					default: details.suggested_hours, reqd: 1, change: updateEnd },
				{ fieldname: "planned_end", label: "结束时间", fieldtype: "Datetime", reqd: 1, read_only: 1 },
				{ fieldname: "production_shift", label: "班次", fieldtype: "Link", options: "Production Shift", default: details.default_shift },
				{ fieldname: "remarks", label: "排程备注", fieldtype: "Small Text" },
			],
			primary_action_label: "确认安排",
			async primary_action(values) {
				if (submitting) return;
				if (!moment(values.planned_end).isAfter(moment(values.planned_start))) {
					frappe.msgprint("结束时间必须晚于开始时间"); return;
				}
				submitting = true;
				dialog.disable_primary_action();
				try {
					await frappe.call({ method: api + "create_schedule_from_task", args: {
						production_flow_card: task.production_flow_card, operation: task.operation, operation_row: task.operation_row,
						production_resource: values.production_resource, planned_start: values.planned_start,
						planned_end: values.planned_end, production_shift: values.production_shift, remarks: values.remarks,
					} });
					dialog.hide();
					frappe.show_alert({ message: "已安排生产", indicator: "green" });
					load();
				} catch (error) {
					// Frappe displays the server validation message and keeps the dialog open.
				} finally { submitting = false; dialog.enable_primary_action(); }
			},
		});
		dialog.show();
		updateEnd();
	}
	ready = true;
	load();
};

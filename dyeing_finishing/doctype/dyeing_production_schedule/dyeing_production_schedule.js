const METHOD = "dyeing_finishing.dyeing_finishing.doctype.dyeing_production_schedule.dyeing_production_schedule";

async function load_task(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.production_flow_card || !row.operation) return;
	const card = row.production_flow_card, operation = row.operation;
	const response = await frappe.call({ method: `${METHOD}.get_task_details`, args: {
		production_flow_card: card, operation, operation_row: row.operation_row,
	} });
	if (row.production_flow_card !== card || row.operation !== operation) return;
	for (const [field, value] of Object.entries(response.message || {})) {
		if (frappe.meta.get_docfield(cdt, field, cdn)) {
			await frappe.model.set_value(cdt, cdn, field, value == null ? "" : value);
		}
	}
}

function recalc(frm) {
	frm.set_value("task_count", (frm.doc.items || []).length);
	frm.set_value("total_hours", (frm.doc.items || []).reduce((sum, row) => sum + flt(row.estimated_hours), 0));
}

function update_hours(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (row.planned_start && row.planned_end) {
		frappe.model.set_value(cdt, cdn, "estimated_hours",
			moment(row.planned_end).diff(moment(row.planned_start), "minutes") / 60);
	}
	recalc(frm);
}

function batch_schedule(frm) {
	const esc = (value) => frappe.utils.escape_html(String(value == null ? "" : value));
	let dialog, tasks = [], request = 0, loaded = null, generating = false;
	const filters = () => ({
		work_center: dialog.get_value("work_center") || "",
		production_resource: dialog.get_value("production_resource") || "",
		customer: dialog.get_value("customer") || "",
		delivery_before: dialog.get_value("delivery_before") || "",
	});
	const fingerprint = () => JSON.stringify(filters());
	const wrapper = () => dialog.fields_dict.tasks.$wrapper;
	const currentItems = () => (frm.doc.items || []).filter((row) =>
		row.production_flow_card || row.operation || row.production_resource || row.planned_start || row.planned_end);
	async function load() {
		if (!dialog) return;
		const current = ++request, signature = fingerprint();
		loaded = null;
		wrapper().html('<div class="text-muted p-3">正在读取待排任务…</div>');
		try {
			const response = await frappe.call({ method: `${METHOD}.get_batch_tasks`, args: filters() });
			if (current !== request) return;
			const existing = currentItems();
			tasks = (response.message || []).filter((task) => !existing.some((row) =>
				row.operation_row === task.operation_row ||
				(!row.operation_row && row.production_flow_card === task.production_flow_card && row.operation === task.operation)));
			loaded = signature;
			if (!tasks.length) {
				wrapper().html('<div class="text-muted p-3">没有可选的待排任务</div>');
				return;
			}
			wrapper().html(`<div style="max-height:360px;overflow:auto">
				<table class="table table-bordered table-condensed" style="margin-bottom:0">
				<thead><tr><th><input type="checkbox" data-select-all aria-label="全选待排任务"></th>
				<th>流转卡 / 工序</th><th>客户 / 颜色</th><th>数量</th><th>交期 / 优先级</th><th>准备状态</th></tr></thead>
				<tbody>${tasks.map((task, index) => `<tr>
					<td><input type="checkbox" data-task="${index}" aria-label="${esc(task.production_flow_card + ' ' + task.operation_name)}"></td>
					<td>${esc(task.production_flow_card)}<br>${esc(task.operation_name)}</td>
					<td>${esc(task.customer_name)}<br>${esc(task.color)}</td>
					<td>${esc(task.production_qty)}</td><td>${esc(task.delivery_date)}<br>${esc(task.production_priority)}</td>
					<td>${esc(task.readiness_status)}${(task.readiness_missing || []).length ?
						`<br><small class="text-muted">${task.readiness_missing.map(esc).join("、")}</small>` : ""}</td>
				</tr>`).join("")}</tbody></table></div>`);
			wrapper().find("[data-select-all]").on("change", function () {
				wrapper().find("[data-task]").prop("checked", this.checked);
			});
		} catch (error) {
			if (current === request) wrapper().html('<div class="text-muted p-3">读取失败，请重新查询</div>');
		}
	}
	dialog = new frappe.ui.Dialog({
		title: "批量选择待排任务", size: "extra-large",
		fields: [
			{ fieldname: "work_center", label: "生产工段", fieldtype: "Link", options: "Production Work Center",
				change: () => { if (dialog) { dialog.set_value("production_resource", ""); load(); } } },
			{ fieldname: "production_resource", label: "生产机台", fieldtype: "Link", options: "Production Resource", reqd: 1,
				get_query: () => ({ filters: { status: ["in", ["启用", "空闲", "生产中"]],
					...(dialog.get_value("work_center") ? { work_center: dialog.get_value("work_center") } : {}) } }), change: load },
			{ fieldtype: "Column Break" },
			{ fieldname: "customer", label: "客户", fieldtype: "Link", options: "Customer", change: load },
			{ fieldname: "delivery_before", label: "交期截至", fieldtype: "Date", change: load },
			{ fieldtype: "Section Break" },
			{ fieldname: "planned_start", label: "开始时间", fieldtype: "Datetime", reqd: 1,
				default: frm.doc.from_datetime || `${frm.doc.schedule_date || frappe.datetime.get_today()} 08:00:00` },
			{ fieldtype: "Column Break" },
			{ fieldname: "planned_end", label: "结束时间", fieldtype: "Datetime", reqd: 1,
				default: frm.doc.to_datetime || `${frm.doc.schedule_date || frappe.datetime.get_today()} 20:00:00` },
			{ fieldtype: "Section Break" },
			{ fieldname: "reload_tasks", label: "查询待排任务", fieldtype: "Button", click: load },
			{ fieldname: "tasks", fieldtype: "HTML" },
		],
		primary_action_label: "生成草稿明细",
		async primary_action(values) {
			if (generating) return;
			if (!loaded || loaded !== fingerprint()) {
				frappe.msgprint("待排任务正在更新，请稍后再选择"); return;
			}
			const selected = wrapper().find("[data-task]:checked").map(function () {
				return tasks[Number($(this).attr("data-task"))].operation_row;
			}).get();
			if (!selected.length) { frappe.msgprint("请勾选待排任务"); return; }
			if (!moment(values.planned_end).isAfter(moment(values.planned_start))) {
				frappe.msgprint("结束时间必须晚于开始时间"); return;
			}
			generating = true;
			dialog.disable_primary_action();
			try {
				const response = await frappe.call({ method: `${METHOD}.generate_batch_schedule`, args: {
					operation_rows: selected, production_resource: values.production_resource,
					planned_start: values.planned_start, planned_end: values.planned_end,
					current_schedule: frm.is_new() ? null : frm.doc.name,
					current_items: currentItems(),
				} });
				const result = response.message;
				if (result.items.length) {
					if (!frm.doc.from_datetime || moment(values.planned_start).isBefore(moment(frm.doc.from_datetime))) {
						await frm.set_value("from_datetime", values.planned_start);
					}
					if (!frm.doc.to_datetime || moment(values.planned_end).isAfter(moment(frm.doc.to_datetime))) {
						await frm.set_value("to_datetime", values.planned_end);
					}
					frm.doc.items = (frm.doc.items || []).filter((row) =>
						row.production_flow_card || row.operation || row.production_resource || row.planned_start || row.planned_end);
					for (const item of result.items) frm.add_child("items", item);
					frm.refresh_field("items");
					frm.dirty();
					recalc(frm);
					dialog.hide();
					frappe.show_alert({ message: `已生成 ${result.items.length} 项明细，尚未保存`, indicator: "green" });
				}
				if (result.skipped.length) {
					frappe.msgprint({ title: "未安排任务", message: result.skipped.map((row) =>
						`${esc(row.task)}：${esc(row.reason)}`).join("<br>") });
					if (!result.items.length) load();
				}
			} catch (error) {
				// Keep the selection open while Frappe displays the validation message.
			} finally {
				generating = false;
				dialog.enable_primary_action();
			}
		},
	});
	dialog.show();
	load();
}

frappe.ui.form.on("Dyeing Production Schedule", {
	setup(frm) {
		frm.set_query("production_shift", () => ({ filters: { enabled: 1 } }));
		frm.set_query("operation", "items", (doc, cdt, cdn) => ({
			query: `${METHOD}.get_available_operations`,
			filters: { production_flow_card: locals[cdt][cdn].production_flow_card || "" },
		}));
		frm.set_query("production_resource", "items", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn], filters = { status: ["in", ["启用", "空闲", "生产中"]] };
			if (row.work_center) filters.work_center = row.work_center;
			if (row.resource_type) filters.resource_type = row.resource_type;
			return { filters };
		});
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.perm.some((permission) => frm.is_new() ? permission.create : permission.write)) {
			frm.add_custom_button("批量选择待排任务", () => batch_schedule(frm));
		}
	},
});

frappe.ui.form.on("Dyeing Production Schedule Item", {
	async production_flow_card(frm, cdt, cdn) {
		await frappe.model.set_value(cdt, cdn, { operation: "", operation_row: "", operation_name: "",
			production_resource: "", resource_name: "", work_center: "", resource_type: "" });
	},
	async operation(frm, cdt, cdn) {
		await frappe.model.set_value(cdt, cdn, { production_resource: "", operation_row: "" });
		await load_task(frm, cdt, cdn);
	},
	async production_resource(frm, cdt, cdn) {
		const row = locals[cdt][cdn], resource = row.production_resource;
		if (!resource) return frappe.model.set_value(cdt, cdn, "resource_name", "");
		const response = await frappe.db.get_value("Production Resource", resource, "resource_name");
		if (row.production_resource === resource) frappe.model.set_value(cdt, cdn, "resource_name", response.message?.resource_name || "");
	},
	planned_start: update_hours, planned_end: update_hours, items_remove: recalc, items_add: recalc,
});

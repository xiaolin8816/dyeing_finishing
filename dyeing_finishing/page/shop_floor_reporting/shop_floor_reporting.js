frappe.pages["shop-floor-reporting"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: "生产工序扫码报工", single_column: true });
	const api = "dyeing_finishing.dyeing_finishing.doctype.production_operation_report.production_operation_report.";
	const root = $("<div class='shop-floor-reporting'></div>").appendTo(page.main);
	let state = emptyState();

	page.add_inner_button("重新开始", reset);
	page.add_menu_item("报工记录", () => frappe.set_route("List", "Production Operation Report"));
	page.add_menu_item("员工工序设置", () => frappe.set_route("List", "Employee Operation Permission"));
	$(`<style>
	.shop-floor-reporting{--sfr-panel:var(--card-bg);--sfr-border:var(--border-color);--sfr-muted:var(--text-muted);--sfr-bg:var(--subtle-fg);max-width:1280px;margin:14px auto;background:var(--sfr-bg);border:1px solid var(--sfr-border);border-radius:14px;overflow:hidden}
	.shop-floor-reporting .sfr-head{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;padding:15px 20px;background:var(--sfr-panel);border-bottom:1px solid var(--sfr-border);gap:16px}.shop-floor-reporting .sfr-title-wrap{text-align:center}.shop-floor-reporting .sfr-title{font-size:22px;font-weight:600}.shop-floor-reporting .sfr-head-note,.shop-floor-reporting .sfr-clock{color:var(--sfr-muted)}.shop-floor-reporting .sfr-clock{font-size:15px;font-variant-numeric:tabular-nums}.shop-floor-reporting .sfr-head-actions{justify-self:end}.shop-floor-reporting .sfr-body{padding:18px;display:grid;gap:13px}
	.shop-floor-reporting *{box-sizing:border-box}.shop-floor-reporting .sfr-grid{display:grid;gap:14px}.shop-floor-reporting .sfr-scans{display:grid;grid-template-columns:1fr 1fr;gap:14px}.shop-floor-reporting .sfr-scan{background:var(--sfr-panel);border:2px solid var(--blue-500);border-radius:10px;padding:14px;display:grid;grid-template-columns:auto 1fr;align-items:center;gap:12px}.shop-floor-reporting .sfr-step{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:var(--blue-500);color:white;font-weight:600}.shop-floor-reporting .sfr-scan input{border:0;background:transparent;width:100%;outline:0;font-size:18px;color:var(--text-color)}
	.shop-floor-reporting .sfr-panel{background:var(--sfr-panel);border:1px solid var(--sfr-border);border-radius:11px;padding:15px}.shop-floor-reporting .sfr-product{display:grid;grid-template-columns:1.35fr 1fr 1fr 1fr;gap:14px}.shop-floor-reporting .sfr-label{display:block;color:var(--sfr-muted);font-size:12px;margin-bottom:4px}.shop-floor-reporting .sfr-value{font-size:16px;font-weight:600}.shop-floor-reporting .sfr-main{display:grid;grid-template-columns:1.15fr .85fr;gap:14px}.shop-floor-reporting .sfr-operation{display:flex;justify-content:space-between;gap:15px}.shop-floor-reporting .sfr-operation-name{font-size:30px;color:var(--blue-600);font-weight:600;margin:3px 0}.shop-floor-reporting .sfr-decision{color:var(--green-600);font-weight:500}.shop-floor-reporting .sfr-operation-buttons{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}.shop-floor-reporting .sfr-operation-buttons button{min-height:50px;min-width:150px;font-size:17px}.shop-floor-reporting .sfr-requirement{border-top:1px solid var(--sfr-border);margin-top:12px;padding-top:10px}.shop-floor-reporting .sfr-qty{display:grid;grid-template-columns:1fr 1fr;gap:10px}.shop-floor-reporting .sfr-number{background:var(--sfr-bg);border-radius:8px;padding:11px}.shop-floor-reporting .sfr-number.edit{border:2px solid var(--blue-500)}.shop-floor-reporting .sfr-number strong{font-size:25px}.shop-floor-reporting .sfr-number input{width:100%;border:0;background:transparent;outline:0;font-size:25px;font-weight:600;color:var(--text-color)}
	.shop-floor-reporting .sfr-workers{background:var(--sfr-panel);border:1px solid var(--sfr-border);border-radius:11px;padding:15px}.shop-floor-reporting .sfr-worker-list{display:flex;flex-wrap:wrap;gap:10px;margin-top:10px}.shop-floor-reporting .sfr-worker{display:flex;align-items:center;gap:9px;background:var(--sfr-bg);border-radius:9px;padding:9px 12px;min-width:138px}.shop-floor-reporting .sfr-avatar{width:34px;height:34px;display:grid;place-items:center;border-radius:50%;background:var(--blue-500);color:white;font-size:17px}.shop-floor-reporting .sfr-worker small{display:block;color:var(--sfr-muted)}.shop-floor-reporting .sfr-ready{margin-top:12px;color:var(--green-600);font-size:15px}.shop-floor-reporting .sfr-ready.waiting{color:var(--orange-700)}.shop-floor-reporting .sfr-warning{background:var(--orange-50);color:var(--orange-700);border:1px solid var(--orange-300);border-radius:9px;padding:12px 14px}.shop-floor-reporting .sfr-actions{display:grid;grid-template-columns:.75fr 1.5fr;gap:12px}.shop-floor-reporting .sfr-actions button{min-height:56px;font-size:17px;border-radius:10px}.shop-floor-reporting .sfr-actions .btn-primary{background:var(--green-600);border-color:var(--green-600)}.shop-floor-reporting .sfr-empty{padding:42px 20px;text-align:center;color:var(--sfr-muted)}.shop-floor-reporting .sfr-foot{text-align:center;color:var(--sfr-muted);font-size:12px;padding:0 10px 16px}
	@media(max-width:800px){.shop-floor-reporting .sfr-head{grid-template-columns:1fr auto}.shop-floor-reporting .sfr-title-wrap{grid-column:1/-1;grid-row:1;text-align:left}.shop-floor-reporting .sfr-clock{grid-column:1;grid-row:2}.shop-floor-reporting .sfr-head-actions{grid-column:2;grid-row:2}.shop-floor-reporting .sfr-scans,.shop-floor-reporting .sfr-main{grid-template-columns:1fr}.shop-floor-reporting .sfr-product{grid-template-columns:1fr 1fr}.shop-floor-reporting .sfr-actions{grid-template-columns:1fr}.shop-floor-reporting .sfr-operation{display:block}}
	</style>`).appendTo(page.main);

	root.on("keydown", "[data-active-scan]", (event) => {
		if (event.key !== "Enter") return;
		if (state.card) scanEmployee(event.currentTarget.value); else scanFlowCard(event.currentTarget.value);
	});
	root.on("click", "[data-rescan]", reset);
	root.on("click", "[data-fullscreen]", toggleFullscreen);
	root.on("click", "[data-operation]", function () { selectOperation($(this).attr("data-operation")); });
	root.on("input", "[data-completed-qty]", function () { state.completedQty = Number($(this).val() || 0); updateReadyState(); });
	root.on("click", "[data-difference]", showDifferenceDialog);
	root.on("click", "[data-submit]", submitReport);
	root.on("click", "[data-remove-worker]", function (event) {
		event.preventDefault();
		const employee = $(this).attr("data-remove-worker");
		if (state.workers[0]?.employee === employee) return frappe.msgprint("主操作员不能移除，请重新开始后扫描其他员工。");
		state.workers = state.workers.filter((row) => row.employee !== employee); render(); focusEmployee();
	});

	function emptyState() { return { card: null, primary: null, workers: [], candidates: [], operation: null, completedQty: 0, difference: {} }; }
	function esc(value) { return frappe.utils.escape_html(String(value == null || value === "" ? "-" : value)); }
	function initial(value) { return esc(Array.from(String(value || "员"))[0] || "员"); }
	function qty(value) { return `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 3 }).format(Number(value || 0))}${esc(state.card?.uom || "Kg")}`; }
	function readyStatus() {
		if (!state.primary) return { ready: false, text: "请扫描主操作员" };
		if (!state.operation) return { ready: false, text: "请选择本次实际生产工序" };
		const total = Number(state.completedQty || 0) + Number(state.difference.loss_qty || 0) + Number(state.difference.defective_qty || 0) + Number(state.difference.rework_qty || 0);
		if (total <= 0) return { ready: false, text: "请输入本次报工数量" };
		if (total > Number(state.operation.available_qty || 0)) return { ready: false, text: "报工数量超过本次可报工数量" };
		return { ready: true, text: "人员与数量校验通过，可以完成报工" };
	}
	function updateReadyState() {
		const status = readyStatus();
		root.find("[data-ready-status]").toggleClass("waiting", !status.ready).html(`${status.ready ? "✓" : "!"} ${esc(status.text)}`);
		root.find("[data-submit]").prop("disabled", !status.ready);
	}
	function updateClock() {
		const now = new Date();
		const value = new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", weekday: "short", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(now);
		root.find("[data-clock]").text(value);
	}
	function reset() { state = emptyState(); render(); focusScanner(); }
	function focusScanner() { window.setTimeout(() => root.find("[data-active-scan]").val("").trigger("focus"), 50); }
	async function toggleFullscreen() {
		if (document.fullscreenElement) await document.exitFullscreen();
		else await root[0].requestFullscreen();
		render(); focusScanner();
	}
	async function scanFlowCard(value) {
		if (!String(value || "").trim()) return;
		try {
			const { message } = await frappe.call({ method: api + "get_flow_card_context", args: { flow_card_scan: value }, freeze: true, freeze_message: "正在读取流转卡…" });
			state = emptyState(); state.card = message; render(); focusEmployee();
		} catch (error) { focusScanner(); }
	}
	async function scanEmployee(value) {
		if (!state.card || !String(value || "").trim()) return;
		try {
			if (!state.primary) {
				const { message } = await frappe.call({ method: api + "resolve_employee_operation", args: { flow_card: state.card.production_flow_card, employee_scan: value } });
				state.primary = message; state.workers = [{ employee: message.employee, employee_name: message.employee_name }]; state.candidates = message.candidates || [];
				if (message.selected) setOperation(message.selected); else render();
			} else {
				const { message } = await frappe.call({ method: api + "validate_assistant", args: { employee_scan: value } });
				if (state.workers.some((row) => row.employee === message.employee)) {
					frappe.msgprint("该员工已经加入本次报工。");
					return focusEmployee();
				}
				state.workers.push(message); render();
			}
			focusEmployee();
		} catch (error) { focusEmployee(); }
	}
	function selectOperation(rowName) { const operation = state.candidates.find((row) => row.operation_row === rowName); if (operation) setOperation(operation); }
	function setOperation(operation) { state.operation = operation; state.completedQty = Number(operation.available_qty || 0); state.difference = {}; render(); focusEmployee(); }
	function focusEmployee() { focusScanner(); }
	function showDifferenceDialog() {
		if (!state.operation) return;
		const dialog = new frappe.ui.Dialog({ title: "登记数量差异", fields: [
			{ fieldname: "completed_qty", label: "本次合格数量", fieldtype: "Float", default: state.completedQty, reqd: 1 },
			{ fieldname: "loss_qty", label: "损耗数量", fieldtype: "Float", default: state.difference.loss_qty || 0 },
			{ fieldname: "defective_qty", label: "次品数量", fieldtype: "Float", default: state.difference.defective_qty || 0 },
			{ fieldname: "rework_qty", label: "返修数量", fieldtype: "Float", default: state.difference.rework_qty || 0 },
			{ fieldname: "remarks", label: "差异原因", fieldtype: "Small Text", default: state.difference.remarks || "" },
		], primary_action_label: "确定", primary_action(values) { state.completedQty = Number(values.completed_qty || 0); state.difference = values; dialog.hide(); render(); focusEmployee(); } });
		dialog.show();
	}
	async function submitReport() {
		if (!state.card || !state.operation || !state.workers.length) return frappe.msgprint("请先扫描流转卡和主操作员工卡，并确认生产工序。");
		if (!state.completedQty && !state.difference.loss_qty && !state.difference.defective_qty && !state.difference.rework_qty) return frappe.msgprint("本次报工数量必须大于零。");
		if (state.operation.missing_previous_operations?.length) {
			const confirmed = await new Promise((resolve) => frappe.confirm(
				`前道工序 ${state.operation.missing_previous_operations.map(esc).join("、")} 尚未报工。确认只报当前工序，并登记前道待补录？`,
				() => resolve(true), () => resolve(false)
			));
			if (!confirmed) return;
		}
		const response = await frappe.call({ method: api + "submit_workbench_report", args: {
			flow_card: state.card.production_flow_card, operation_row: state.operation.operation_row,
			employees: state.workers, completed_qty: state.completedQty,
			production_resource: state.operation.production_resource,
			loss_qty: state.difference.loss_qty || 0, defective_qty: state.difference.defective_qty || 0,
			rework_qty: state.difference.rework_qty || 0, remarks: state.difference.remarks || "",
		}, freeze: true, freeze_message: "正在提交报工…" });
		frappe.show_alert({ message: `报工 ${response.message.name} 已完成`, indicator: "green" }, 5); reset();
	}
	function render() {
		const card = state.card;
		const operation = state.operation;
		const fullscreenLabel = document.fullscreenElement ? "退出全屏" : "全屏显示";
		const shellHead = `<div class="sfr-head"><div class="sfr-clock" data-clock></div><div class="sfr-title-wrap"><div class="sfr-title">车间扫码报工</div><div class="sfr-head-note">生产工序完工确认</div></div><div class="sfr-head-actions"><button class="btn btn-default" data-fullscreen>${fullscreenLabel}</button></div></div>`;
		const scanTitle = !card ? "请扫描生产流转卡" : !state.primary ? "流转卡已识别，请扫描主操作员" : "继续扫描可加入协作人员";
		const scanSummary = card ? `${esc(card.flow_card_no)} · ${esc(card.finished_product_name)} · ${esc(card.color)}` : "支持流转卡、员工二维码或条码";
		const scanFields = `<div class="sfr-scan"><div><strong class="sfr-value">${scanTitle}</strong><span class="sfr-label">${scanSummary}</span><input data-active-scan autocomplete="off" placeholder="扫码后按回车" autofocus></div>${card ? '<button class="btn btn-default" data-rescan>重新扫描</button>' : '<span class="sfr-step">1</span>'}</div>`;
		if (!card) { root.html(`${shellHead}<div class="sfr-body">${scanFields}<div class="sfr-panel sfr-empty"><b>等待扫描生产流转卡</b><br>扫描后自动读取成品、规格、批次、数量和未完成工序。</div></div><div class="sfr-foot">一次报工：扫流转卡 → 扫员工卡 → 确认完成；下一道工序不会自动开工</div>`); updateClock(); return; }
		const product = `<div class="sfr-panel"><div class="sfr-value" style="margin-bottom:12px">生产任务核对</div><div class="sfr-product"><div><span class="sfr-label">客户名称</span><span class="sfr-value">${esc(card.customer_name)}</span></div><div><span class="sfr-label">成品名称</span><span class="sfr-value">${esc(card.finished_product_name)}</span></div><div><span class="sfr-label">成品规格</span><span class="sfr-value">${esc(card.finished_specification)}</span></div><div><span class="sfr-label">胚布批次</span><span class="sfr-value">${esc(card.grey_fabric_batches)}</span></div><div><span class="sfr-label">色号 / 颜色</span><span class="sfr-value">${esc(card.color_no)} / ${esc(card.color)}</span></div><div><span class="sfr-label">生产数量</span><span class="sfr-value">${qty(card.production_qty)}</span></div><div><span class="sfr-label">交货日期</span><span class="sfr-value">${esc(card.delivery_date)}</span></div><div><span class="sfr-label">当前进度</span><span class="sfr-value">${esc(card.current_progress_status || "进行中")}</span></div></div></div>`;
		let operationHtml = "";
		if (!state.primary) operationHtml = '<div class="sfr-panel sfr-empty">扫描主操作员工卡后，系统根据员工可操作工序自动判断。</div>';
		else if (!operation) operationHtml = `<div class="sfr-panel"><span class="sfr-label">该员工可操作多个当前工序，请选择实际工序</span><div class="sfr-operation-buttons">${state.candidates.map((row) => `<button class="btn btn-primary" data-operation="${esc(row.operation_row)}">${esc(row.operation_name)}</button>`).join("")}</div></div>`;
		else operationHtml = `<div class="sfr-main"><div class="sfr-panel"><div class="sfr-operation"><div><span class="sfr-label">当前工序</span><div class="sfr-operation-name">${esc(operation.operation_name)}</div><div class="sfr-decision">员工工序权限匹配 · 第 ${operation.sequence_no}/${card.operation_total} 道</div></div><div class="text-right"><span class="sfr-label">生产机台</span><div class="sfr-value">${esc(operation.resource_name || "未安排")}</div><span class="sfr-label">前道状态</span><div>${operation.missing_previous_operations?.length ? "待补录" : "正常"}</div></div></div></div><div class="sfr-panel"><div class="sfr-value" style="margin-bottom:10px">本次报工数量</div><div class="sfr-qty"><div class="sfr-number"><span class="sfr-label">可报工</span><strong>${qty(operation.available_qty)}</strong></div><div class="sfr-number edit"><span class="sfr-label">本次合格数量</span><input data-completed-qty type="number" min="0" step="0.001" value="${esc(state.completedQty)}"></div><div class="sfr-number"><span class="sfr-label">损耗</span><strong>${qty(state.difference.loss_qty || 0)}</strong></div><div class="sfr-number"><span class="sfr-label">预计剩余</span><strong>${qty(Math.max(Number(operation.available_qty || 0) - Number(state.completedQty || 0) - Number(state.difference.loss_qty || 0) - Number(state.difference.defective_qty || 0) - Number(state.difference.rework_qty || 0), 0))}</strong></div></div></div></div>`;
		const warning = operation?.missing_previous_operations?.length ? `<div class="sfr-warning"><b>前道待补录：</b>${operation.missing_previous_operations.map(esc).join("、")}。本次只记录当前实际工序，不会代报前道。</div>` : "";
		const status = readyStatus();
		const workers = `<div class="sfr-workers"><div class="sfr-value">参与员工 · 扫描员工二维码加入</div>${state.workers.length ? `<div class="sfr-worker-list">${state.workers.map((row, index) => `<div class="sfr-worker"><span class="sfr-avatar">${initial(row.employee_name)}</span><span><b>${esc(row.employee_name)}</b><small>${index ? `协作人员 · <a href="#" data-remove-worker="${esc(row.employee)}">移除</a>` : "主操作员"}</small></span></div>`).join("")}</div>` : '<div class="text-muted" style="margin-top:8px">尚未扫描员工</div>'}<div class="sfr-ready ${status.ready ? "" : "waiting"}" data-ready-status>${status.ready ? "✓" : "!"} ${esc(status.text)}</div></div>`;
		const actions = operation ? `<div class="sfr-actions"><button class="btn btn-default" data-difference>暂停 / 数量异常</button><button class="btn btn-primary" data-submit ${status.ready ? "" : "disabled"}>完成报工并准备下一道工序</button></div>` : "";
		root.html(`${shellHead}<div class="sfr-body">${scanFields}${warning}${product}${operationHtml}${workers}${actions}</div><div class="sfr-foot">一次报工：扫流转卡 → 扫员工卡 → 确认完成；下一道工序不会自动开工</div>`);
		updateClock();
	}
	reset();
	window.setInterval(updateClock, 1000);
};

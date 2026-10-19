frappe.pages["production-progress-screen"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: "生产进度大屏", single_column: true });
	const method = "dyeing_finishing.dyeing_finishing.doctype.dyeing_production_schedule.dyeing_production_schedule.get_production_progress_screen_data";
	const root = $("<div class='production-progress-screen'></div>").appendTo(page.main);
	const settingsKey = "dyeing_finishing.production_progress_screen.settings";
	const defaults = { displayMode: "自动适应", rowsPerPage: 10, rotateSeconds: 15 };
	let settings = readSettings();
	let payload = { summary: {}, cards: [], alerts: [] };
	let pageIndex = 0;
	let alertIndex = 0;
	let refreshTimer;
	let rotateTimer;
	let alertTimer;
	let clockTimer;

	page.add_inner_button("刷新", () => load());
	page.add_inner_button("全屏显示", () => toggleFullscreen());
	page.add_menu_item("显示设置", () => showDisplaySettings());
	$(`<style>
	.production-progress-screen{--screen-bg:#07111f;--panel:#102239;--line:#29405d;--muted:#9fb3c8;--white:#f5f9ff;background:var(--screen-bg);color:var(--white);min-height:calc(100vh - 120px);padding:clamp(12px,1vw,22px);border-radius:10px;font-size:clamp(14px,calc(.48vw + 8px),18px)}
	.production-progress-screen .pps-top{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:12px}
	.production-progress-screen .pps-kpi{background:linear-gradient(145deg,#102844,#0d1d31);border:1px solid #284565;border-radius:10px;padding:clamp(9px,.8vw,16px);min-height:clamp(72px,7vh,100px)}
	.production-progress-screen .pps-kpi span{display:block;color:var(--muted);font-size:clamp(13px,calc(.28vw + 9px),17px)}.production-progress-screen .pps-kpi b{display:block;font-size:clamp(25px,2.05vw,42px);line-height:1.2;margin-top:4px}
	.production-progress-screen .pps-kpi.danger b{color:#ff6b6b}.production-progress-screen .pps-kpi.success b{color:#43d17a}
	.production-progress-screen .pps-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:clamp(12px,1.3vw,20px) 2px 10px}.production-progress-screen .pps-title{font-size:clamp(18px,1.35vw,26px);font-weight:700}.production-progress-screen .pps-meta{color:var(--muted);font-size:clamp(12px,.78vw,16px);text-align:right}
	.production-progress-screen .pps-table{border:1px solid var(--line);border-radius:10px;overflow-x:auto;overflow-y:hidden}.production-progress-screen .pps-row{display:grid;grid-template-columns:minmax(64px,.55fr) minmax(112px,1fr) minmax(180px,1.65fr) minmax(82px,.72fr) minmax(185px,1.45fr) minmax(155px,1.3fr) minmax(140px,1.15fr) minmax(105px,.9fr);align-items:center;min-height:clamp(58px,5.8vh,72px);border-bottom:1px solid var(--line)}
	.production-progress-screen.pps-sparse .pps-row{min-height:clamp(72px,8vh,104px);font-size:1.08em}.production-progress-screen.pps-compact .pps-row{min-height:54px;font-size:.94em}
	.production-progress-screen .pps-row:last-child{border-bottom:0}.production-progress-screen .pps-row>div{padding:clamp(7px,.6vw,12px);min-width:0}.production-progress-screen .pps-header{min-height:clamp(42px,4.5vh,54px)!important;background:#163452;color:#cfe5fb;font-weight:700;white-space:nowrap}.production-progress-screen .pps-card:nth-child(odd){background:#0c1a2c}.production-progress-screen .pps-card:nth-child(even){background:#0e2035}
	.production-progress-screen .pps-priority{font-weight:700;white-space:nowrap}.production-progress-screen .pps-priority.urgent{color:#ff6b6b}.production-progress-screen .pps-priority.high{color:#ffbf5b}.production-progress-screen a{color:#79c4ff;font-weight:700}.production-progress-screen .pps-sub{display:block;color:var(--muted);font-size:.82em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:3px}.production-progress-screen .pps-wrap{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;line-clamp:2;overflow:hidden;overflow-wrap:anywhere;line-height:1.28}.production-progress-screen .pps-nowrap{white-space:nowrap}.production-progress-screen .pps-quantity{white-space:nowrap;font-size:clamp(13px,1vw,19px);font-variant-numeric:tabular-nums}.production-progress-screen .pps-stock-progress{display:flex;align-items:center;gap:clamp(6px,.65vw,12px);white-space:nowrap;font-size:clamp(12px,.9vw,18px)}.production-progress-screen .pps-stock-progress span{white-space:nowrap}.production-progress-screen .pps-stock-progress b{color:var(--muted);font-weight:400}
	.production-progress-screen .pps-stage{font-weight:700;margin-bottom:6px}.production-progress-screen .pps-progress{height:7px;background:#27394d;border-radius:8px;overflow:hidden}.production-progress-screen .pps-progress i{display:block;height:100%;background:linear-gradient(90deg,#2596ff,#3ddc97)}
	.production-progress-screen .pps-status{display:inline-block;border-radius:12px;padding:3px 9px;font-size:.78em;background:#23476b}.production-progress-screen .pps-status.overdue,.production-progress-screen .pps-status.paused{background:#7a2831;color:#ffd8dc}.production-progress-screen .pps-status.complete{background:#155c3d;color:#c8ffe4}
	.production-progress-screen .pps-card.exception{box-shadow:inset 5px 0 0 #ff5964;background:#241923}.production-progress-screen .pps-next{color:#79c4ff}
	.production-progress-screen .pps-alerts{display:flex;align-items:center;gap:12px;margin-top:14px;padding:clamp(8px,.7vw,13px) 14px;background:#311c23;border:1px solid #74313d;border-radius:8px;min-height:44px}.production-progress-screen .pps-alert-label{color:#ff858f;font-weight:700;white-space:nowrap}.production-progress-screen .pps-alert-message{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.production-progress-screen .pps-empty{height:360px;display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:clamp(18px,1.5vw,28px)}
	.production-progress-screen.pps-mode-large{font-size:clamp(17px,calc(.62vw + 9px),22px)}.production-progress-screen.pps-mode-large .pps-row{grid-template-columns:minmax(70px,.55fr) minmax(126px,1fr) minmax(200px,1.7fr) minmax(90px,.72fr) minmax(210px,1.5fr) minmax(175px,1.35fr) minmax(155px,1.2fr) minmax(112px,.9fr)}
	body.pps-fullscreen .navbar,body.pps-fullscreen .page-head,body.pps-fullscreen .desk-sidebar{display:none!important}body.pps-fullscreen .layout-main-section-wrapper,body.pps-fullscreen .layout-main-section{margin:0!important;padding:0!important;max-width:none!important}.production-progress-screen:fullscreen{width:100vw;height:100vh;min-height:100vh;overflow:auto;border-radius:0;padding:22px}.production-progress-screen:fullscreen .pps-table{max-height:calc(100vh - 260px)}
	.production-progress-screen .pps-alert-window{position:relative;overflow:hidden;min-width:0;flex:1;height:24px}.production-progress-screen .pps-alert-message{position:absolute;inset:0;display:flex;align-items:center;transition:transform .35s ease,opacity .35s ease}.production-progress-screen .pps-alert-count{color:#ffb1b7;white-space:nowrap;font-variant-numeric:tabular-nums}
	@media(max-width:1300px){.production-progress-screen .pps-row{min-width:1080px}.production-progress-screen .pps-top{grid-template-columns:repeat(3,minmax(130px,1fr))}.production-progress-screen .pps-head{align-items:flex-start;flex-direction:column}.production-progress-screen .pps-meta{text-align:left}}
	</style>`).appendTo(page.main);

	const esc = (value) => frappe.utils.escape_html(String(value == null || value === "" ? "-" : value));
	const quantity = (value, uom = "KG") => `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(Number(value || 0))}${uom}`;
	const dateText = (value) => value ? frappe.datetime.str_to_user(value) : "-";
	function readSettings() {
		try {
			const saved = { ...defaults, ...JSON.parse(window.localStorage.getItem(settingsKey) || "{}") };
			if (saved.displayMode === "auto") saved.displayMode = "自动适应";
			if (saved.displayMode === "large") saved.displayMode = "大字显示";
			return saved;
		} catch (error) { return { ...defaults }; }
	}
	root.on("click", "[data-flow-card]", function (event) {
		event.preventDefault();
		frappe.set_route("Form", "Production Flow Card", $(this).attr("data-flow-card"));
	});

	async function load() {
		try {
			const response = await frappe.call({ method });
			payload = response.message || { summary: {}, cards: [], alerts: [] };
			alertIndex = Math.min(alertIndex, Math.max(0, (payload.alerts || []).length - 1));
			const maxPage = Math.max(0, Math.ceil((payload.cards || []).length / settings.rowsPerPage) - 1);
			pageIndex = Math.min(pageIndex, maxPage);
			render();
		} catch (error) {
			root.html('<div class="pps-empty">大屏数据读取失败，系统将自动重试</div>');
		}
	}

	function render() {
		const summary = payload.summary || {};
		const cards = payload.cards || [];
		const pages = Math.max(1, Math.ceil(cards.length / settings.rowsPerPage));
		const visible = cards.slice(pageIndex * settings.rowsPerPage, (pageIndex + 1) * settings.rowsPerPage);
		const density = visible.length <= 6 ? "pps-sparse" : visible.length >= 9 ? "pps-compact" : "pps-standard";
		root.removeClass("pps-sparse pps-standard pps-compact pps-mode-large")
			.addClass(density).toggleClass("pps-mode-large", settings.displayMode === "大字显示");
		const body = visible.map((card) => {
			const priorityClass = card.production_priority === "特急" ? "urgent" : card.production_priority === "加急" ? "high" : "";
			const statusClass = card.is_overdue ? "overdue" : card.stage === "生产暂停" ? "paused" : card.stage === "全部入库" ? "complete" : "";
			const statusText = card.is_overdue ? "已逾期" : card.missing_operation_count ? `待补录${card.missing_operation_count}道`
				: card.flow_card_type === "回修" ? "回修" : "正常";
			return `<div class="pps-row pps-card ${card.missing_operation_count ? "exception" : ""}">
				<div class="pps-priority ${priorityClass}">${esc(card.production_priority)}</div>
				<div class="pps-nowrap"><a href="#" data-flow-card="${esc(card.production_flow_card)}">${esc(card.flow_card_no || card.production_flow_card)}</a><span class="pps-sub" title="${esc(`${card.color_no || ""} ${card.color || ""}`)}">${esc(card.color_no)} ${esc(card.color)}</span></div>
				<div><span class="pps-wrap" title="${esc(card.customer_name)}">${esc(card.customer_name)}</span><span class="pps-sub" title="${esc(card.finished_product_name)}">${esc(card.finished_product_name)}</span></div>
				<div class="pps-quantity">${quantity(card.production_qty)}</div>
				<div><div class="pps-stage">${esc(card.stage)}</div><div class="pps-progress"><i style="width:${Math.min(100, Number(card.progress_percent || 0))}%"></i></div></div>
				<div><span class="pps-wrap" title="${esc(card.current_operation || card.stage)}">${esc(card.current_operation || card.stage)}</span><span class="pps-sub" title="${esc(card.resource_name || "未安排机台")}">${esc(card.operation_status)} · ${esc(card.resource_name || "未安排机台")}${card.production_shift ? ` · ${esc(card.production_shift)}` : ""}</span><span class="pps-sub pps-next">下一道：${esc(card.next_operation)}</span></div>
				<div class="pps-stock-progress"><span>包装 ${quantity(card.packed_qty)}</span><b>·</b><span>入库 ${quantity(card.warehoused_qty)}</span></div>
				<div class="pps-nowrap">${dateText(card.planned_completion_date || card.delivery_date)}<span class="pps-sub"><span class="pps-status ${statusClass}">${statusText}</span></span></div>
			</div>`;
		}).join("") || '<div class="pps-empty">当前没有进行中的生产流转卡</div>';
		const alerts = payload.alerts || [];
		const alert = alerts[alertIndex];
		root.html(`<div class="pps-top">
			${kpi("生产任务", summary.total)}${kpi("生产中", summary.in_production)}${kpi("待包装", summary.waiting_packing)}
			${kpi("部分入库", summary.partial_receipt)}${kpi("异常/逾期", summary.exceptions, "danger")}${kpi("今日已入库", summary.completed_today, "success")}
		</div><div class="pps-head"><div class="pps-title">生产任务实时进度</div><div class="pps-meta">第 ${pageIndex + 1}/${pages} 页 · <span data-clock></span> · 30秒刷新 · ${settings.rotateSeconds}秒翻页</div></div>
		<div class="pps-table"><div class="pps-row pps-header"><div>优先级</div><div>流转卡</div><div>客户 / 成品</div><div>数量</div><div>当前进度</div><div>当前 / 下一道</div><div>包装 / 入库</div><div>计划完成</div></div>${body}</div>
		<div class="pps-alerts"><span class="pps-alert-label">${alerts.length ? "异常提醒" : "生产正常"}</span><span class="pps-alert-count">${alerts.length ? `${alertIndex + 1}/${alerts.length}` : ""}</span><span class="pps-alert-window"><span class="pps-alert-message" data-alert-message>${esc(alert?.message || "当前没有生产异常")}</span></span></div>`);
		updateClock();
	}

	function rotateAlert() {
		const alerts = payload.alerts || [];
		if (alerts.length <= 1) return;
		const message = root.find("[data-alert-message]");
		message.css({ transform: "translateY(-100%)", opacity: 0 });
		window.setTimeout(() => {
			alertIndex = (alertIndex + 1) % alerts.length;
			const alert = alerts[alertIndex];
			root.find(".pps-alert-count").text(`${alertIndex + 1}/${alerts.length}`);
			message.text(alert.message).css({ transform: "translateY(100%)", opacity: 0 });
			window.requestAnimationFrame(() => message.css({ transform: "translateY(0)", opacity: 1 }));
		}, 350);
	}

	function kpi(label, value, className = "") {
		return `<div class="pps-kpi ${className}"><span>${label}</span><b>${Number(value || 0)}</b></div>`;
	}

	function rotate() {
		const pages = Math.ceil((payload.cards || []).length / settings.rowsPerPage);
		if (pages > 1) {
			pageIndex = (pageIndex + 1) % pages;
			render();
		}
	}

	function resetRotateTimer() {
		window.clearInterval(rotateTimer);
		rotateTimer = window.setInterval(rotate, Number(settings.rotateSeconds) * 1000);
	}

	function showDisplaySettings() {
		const dialog = new frappe.ui.Dialog({
			title: "生产大屏显示设置",
			fields: [
				{ fieldname: "displayMode", label: "显示模式", fieldtype: "Select", options: "自动适应\n大字显示",
					default: settings.displayMode, description: "自动适应；电视观看距离较远时可选大字显示。" },
				{ fieldname: "rowsPerPage", label: "每页任务数", fieldtype: "Select", options: "6\n8\n10", default: String(settings.rowsPerPage), reqd: 1 },
				{ fieldname: "rotateSeconds", label: "自动翻页间隔", fieldtype: "Select", options: "10\n15\n30", default: String(settings.rotateSeconds), reqd: 1 },
			],
			primary_action_label: "保存并应用",
			primary_action(values) {
				settings = { displayMode: values.displayMode || "自动适应", rowsPerPage: Number(values.rowsPerPage), rotateSeconds: Number(values.rotateSeconds) };
				window.localStorage.setItem(settingsKey, JSON.stringify(settings));
				pageIndex = 0;
				resetRotateTimer();
				render();
				dialog.hide();
				frappe.show_alert({ message: "大屏显示设置已保存在当前设备", indicator: "green" });
			},
		});
		dialog.show();
		dialog.set_value("displayMode", settings.displayMode);
	}

	function updateClock() {
		root.find("[data-clock]").text(moment().format("YYYY-MM-DD HH:mm:ss"));
	}

	function toggleFullscreen() {
		if (!document.fullscreenElement && root[0].requestFullscreen) root[0].requestFullscreen().catch(() => {});
		else if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen().catch(() => {});
	}
	function syncFullscreenState() { $(document.body).toggleClass("pps-fullscreen", document.fullscreenElement === root[0]); }

	refreshTimer = window.setInterval(load, 30000);
	resetRotateTimer();
	alertTimer = window.setInterval(rotateAlert, 5000);
	clockTimer = window.setInterval(updateClock, 1000);
	document.addEventListener("fullscreenchange", syncFullscreenState);
	$(wrapper).on("remove", () => {
		window.clearInterval(refreshTimer);
		window.clearInterval(rotateTimer);
		window.clearInterval(alertTimer);
		window.clearInterval(clockTimer);
		document.removeEventListener("fullscreenchange", syncFullscreenState);
		$(document.body).removeClass("pps-fullscreen");
	});
	load();
};

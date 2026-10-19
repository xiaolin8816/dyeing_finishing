frappe.pages["dyeing-print-template-manager"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({parent: wrapper, title: "报表设计中心", single_column: true});
	page.set_primary_action("新建报表", openNewTemplateDialog, "add");
	page.set_secondary_action("刷新", loadTemplates, "refresh");
	page.add_menu_item("纸张规格", () => frappe.set_route("List", "Dyeing Paper Format"));
	page.add_menu_item("报表引擎诊断", () => frappe.set_route("dyeing-report-engine-diagnostics"));
	const search = page.add_field({label: "搜索", fieldname: "search_text", fieldtype: "Data", placeholder: "模板名称或业务表单", change: render});
	const category = page.add_field({label: "类型", fieldname: "category", fieldtype: "Select", options: "\n标签\n单据", change: render});
	const root = $("<div class='dyeing-report-design-center'></div>").appendTo(page.main);
	let templates = [];

	$("<style>").text(`
		.dyeing-report-design-center{margin-top:16px}.drdc-hero{display:flex;justify-content:space-between;gap:16px;padding:18px 20px;border:1px solid #bfdbfe;border-radius:10px;background:linear-gradient(135deg,#eff6ff,#f8fafc);margin-bottom:14px}.drdc-title{font-size:18px;font-weight:700;color:#1e3a5f}.drdc-help{color:var(--text-muted);margin-top:5px}.drdc-note{white-space:nowrap;align-self:center;color:#166534;background:#dcfce7;padding:5px 10px;border-radius:12px;font-size:12px}.drdc-stats{display:grid;grid-template-columns:repeat(3,minmax(120px,1fr));gap:10px;margin-bottom:14px}.drdc-stat{padding:13px 15px;border:1px solid var(--border-color);border-radius:8px;background:var(--card-bg)}.drdc-number{font-size:22px;font-weight:700}.drdc-label,.drdc-meta{font-size:12px;color:var(--text-muted)}
		.drdc-table{border:1px solid var(--border-color);border-radius:8px;overflow:hidden;background:var(--card-bg)}.drdc-row{display:grid;grid-template-columns:minmax(190px,1.5fr) minmax(170px,1.2fr) 80px 110px 110px minmax(210px,1.4fr);align-items:center;gap:12px;padding:11px 14px;border-bottom:1px solid var(--border-color)}.drdc-row:last-child{border-bottom:0}.drdc-head{font-weight:600;background:var(--subtle-fg)}.drdc-name{font-weight:600}.drdc-actions{display:flex;gap:5px;flex-wrap:wrap}.drdc-badge{display:inline-block;padding:2px 7px;border:0;border-radius:10px;font-size:12px}.drdc-ok{background:#dcfce7;color:#166534}.drdc-warning{background:#fef3c7;color:#92400e}.drdc-error{background:#fee2e2;color:#991b1b}.drdc-empty{padding:38px;text-align:center;color:var(--text-muted)}.drdc-backup{margin-top:14px;padding:12px 15px;border:1px dashed var(--border-color);border-radius:8px;color:var(--text-muted)}
		@media(max-width:1000px){.drdc-stats{grid-template-columns:1fr}.drdc-head{display:none}.drdc-row{grid-template-columns:1fr}.drdc-note{display:none}}
	`).appendTo(page.main);

	const escape = (value) => frappe.utils.escape_html(String(value == null ? "" : value));
	root.on("click", "[data-action]", function () {
		const row = templates.find((item) => item.name === $(this).attr("data-name"));
		if (!row) return;
		const action = $(this).attr("data-action");
		if (action === "design") frappe.set_route("dyeing-visual-report-designer", row.name);
		if (action === "preview") preview(row);
		if (action === "copy") copyTemplate(row);
		if (action === "check") showChecks(row);
	});

	async function loadTemplates() {
		root.html('<div class="drdc-empty">正在读取 Crispy Print 报表模板…</div>');
		const response = await frappe.call({method: "dyeing_finishing.dyeing_finishing.page.dyeing_print_template_manager.dyeing_print_template_manager.get_crispy_templates"});
		templates = response.message || [];
		render();
	}

	function render() {
		const keyword = String(search.get_value() || "").trim().toLowerCase();
		const rows = templates.filter((row) => (!keyword || `${row.name} ${row.doc_type_label} ${row.doc_type}`.toLowerCase().includes(keyword)) && (!category.get_value() || row.category === category.get_value()));
		const body = rows.map((row) => {
			const status = row.health === "error" ? ["有错误", "drdc-error"] : row.health === "warning" ? ["待完善", "drdc-warning"] : ["可使用", "drdc-ok"];
			return `<div class="drdc-row"><div><div class="drdc-name">${escape(row.name)}</div><div class="drdc-meta">Crispy Print 可视模板${row.is_default ? " · 默认" : ""}</div></div><div>${escape(__(row.doc_type))}<div class="drdc-meta">${escape(row.doc_type)}</div></div><div>${escape(row.category)}</div><div>${escape(row.page_size)}</div><div><button class="drdc-badge ${status[1]}" data-action="check" data-name="${escape(row.name)}">${status[0]}</button><div class="drdc-meta">${row.binding_count} 个字段</div></div><div class="drdc-actions"><button class="btn btn-primary btn-sm" data-action="design" data-name="${escape(row.name)}">设计</button><button class="btn btn-default btn-sm" data-action="preview" data-name="${escape(row.name)}">预览</button><button class="btn btn-default btn-sm" data-action="copy" data-name="${escape(row.name)}">复制</button></div></div>`;
		}).join("");
		const ok = templates.filter((x) => x.health === "ok").length;
		root.html(`<div class="drdc-hero"><div><div class="drdc-title">报表设计中心</div><div class="drdc-help">统一使用 Crispy Print 管理、保存和预览可视化报表。</div></div><span class="drdc-note">Crispy Print + Typst</span></div><div class="drdc-stats"><div class="drdc-stat"><div class="drdc-number">${templates.length}</div><div class="drdc-label">可视报表模板</div></div><div class="drdc-stat"><div class="drdc-number text-success">${ok}</div><div class="drdc-label">可直接使用</div></div><div class="drdc-stat"><div class="drdc-number">${templates.filter(x => x.category === "标签").length}</div><div class="drdc-label">标签模板</div></div></div><div class="drdc-table"><div class="drdc-row drdc-head"><div>模板名称</div><div>业务表单</div><div>类型</div><div>纸张</div><div>状态</div><div>操作</div></div>${body || '<div class="drdc-empty">没有符合条件的模板</div>'}</div>`);
	}

	async function openNewTemplateDialog() {
		const [doctypeResponse, paperResponse] = await Promise.all([
			frappe.call({method: "dyeing_finishing.dyeing_finishing.page.dyeing_print_template_manager.dyeing_print_template_manager.get_printable_doctypes"}),
			frappe.call({method: "dyeing_finishing.dyeing_finishing.page.dyeing_print_template_manager.dyeing_print_template_manager.get_paper_formats"}),
		]);
		const rows = doctypeResponse.message || [], papers = paperResponse.message || [];
		const dialog = new frappe.ui.Dialog({title: "新建报表模板", fields: [
			{label: "模板名称", fieldname: "template_name", fieldtype: "Data", reqd: 1},
			{label: "绑定业务表单", fieldname: "doc_type", fieldtype: "Autocomplete", reqd: 1, options: rows.map((row) => ({label: `${__(row.value)} (${row.value})`, value: row.value}))},
			{label: "模板类型", fieldname: "template_type", fieldtype: "Select", reqd: 1, options: "业务单据\n标签", default: "业务单据"},
			{label: "纸张规格", fieldname: "paper_format", fieldtype: "Select", reqd: 1,
				options: [...papers.map((row) => row.paper_name), "自定义"].join("\n"), default: papers.find((row) => row.paper_name === "A4纵向")?.paper_name || papers[0]?.paper_name},
			{fieldname: "page_size", fieldtype: "Data", hidden: 1, default: "自定义"},
			{fieldtype: "Section Break", label: "自定义纸张尺寸（mm）", depends_on: "eval:doc.paper_format=='自定义'"},
			{label: "纸张格式名称", fieldname: "paper_name", fieldtype: "Data", description: "例如：中一刀、60×80mm标签纸",
				depends_on: "eval:doc.paper_format=='自定义'", mandatory_depends_on: "eval:doc.paper_format=='自定义'"},
			{label: "宽度", fieldname: "width", fieldtype: "Float", default: 210,
				depends_on: "eval:doc.paper_format=='自定义'", mandatory_depends_on: "eval:doc.paper_format=='自定义'"},
			{fieldtype: "Column Break"}, {label: "高度", fieldname: "height", fieldtype: "Float", default: 297,
				depends_on: "eval:doc.paper_format=='自定义'", mandatory_depends_on: "eval:doc.paper_format=='自定义'"},
		], primary_action_label: "创建并进入设计", primary_action: async (values) => {
			const created = await frappe.call({method: "dyeing_finishing.dyeing_finishing.page.dyeing_print_template_manager.dyeing_print_template_manager.create_crispy_template", args: values, freeze: true, freeze_message: "正在创建 Crispy Print 模板…"});
			dialog.hide(); await loadTemplates(); frappe.set_route("dyeing-visual-report-designer", created.message.name);
		}});
		dialog.show();
		dialog.fields_dict.template_type.$input.on("change.dyeingCustomPaper", () => {
			if (dialog.get_value("template_type") === "标签") {
				dialog.set_value("paper_format", "60×80mm标签纸");
			}
		});
		dialog.fields_dict.paper_format.$input.on("change.dyeingCustomPaper", () => {
			if (dialog.get_value("paper_format") === "自定义") {
				if (!dialog.get_value("width")) dialog.set_value("width", 210);
				if (!dialog.get_value("height")) dialog.set_value("height", 297);
			}
		});
	}

	async function preview(row) {
		if (!row.preview_doc) return frappe.msgprint(`暂无 ${__(row.doc_type)} 数据，请先新建一张测试单据。`);
		await frappe.call({method: "dyeing_finishing.dyeing_finishing.page.dyeing_print_template_manager.dyeing_print_template_manager.ensure_active_print_template", args: {crispy_format: row.name}, freeze: true, freeze_message: "正在准备打印预览…"});
		frappe.route_options = {format: row.name};
		frappe.set_route("crispy-print-preview", row.doc_type, row.preview_doc);
	}

	function showChecks(row) {
		const items = row.checks.length ? row.checks.map((x) => `<li class="${x.level === "error" ? "text-danger" : "text-warning"}">${escape(x.message)}</li>`).join("") : '<li class="text-success">布局、页面设置和字段绑定已就绪。</li>';
		frappe.msgprint({title: `${row.name}：模板检查`, message: `<ul style="margin-bottom:0">${items}</ul>`, indicator: row.health === "error" ? "red" : row.health === "warning" ? "orange" : "green"});
	}

	function copyTemplate(row) {
		frappe.prompt([{label: "新模板名称", fieldname: "new_name", fieldtype: "Data", reqd: 1, default: `${row.name}-副本`}], async (values) => {
			const response = await frappe.call({method: "dyeing_finishing.dyeing_finishing.page.dyeing_print_template_manager.dyeing_print_template_manager.duplicate_crispy_template", args: {source_name: row.name, new_name: values.new_name}, freeze: true, freeze_message: "正在复制模板…"});
			await loadTemplates(); frappe.set_route("dyeing-visual-report-designer", response.message.name);
		}, `复制模板：${row.name}`, "复制并设计");
	}

	loadTemplates();
};

frappe.pages["dyeing-visual-report-designer"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({parent: wrapper, title: "可视化报表设计器", single_column: true});
	const root = $("<div class='dvrd'></div>").appendTo(page.main);
	const route = frappe.get_route();
	const formatName = route.slice(1).join("/");
	let data, visual, selected = null, zoom = 1, history = [], historyIndex = -1, dirty = false, canvasFrame = null;
	const clone = (obj) => JSON.parse(JSON.stringify(obj));
	const esc = (v) => frappe.utils.escape_html(String(v == null ? "" : v));

	$("<style>").text(`
		.page-container[data-page-route^="dyeing-visual-report-designer"] .container{max-width:none!important;padding:0!important}.page-container[data-page-route^="dyeing-visual-report-designer"] .layout-main-section{padding:0!important}.dvrd{height:calc(100vh - 118px);min-height:650px;display:grid;grid-template-rows:48px 1fr;background:#eef1f5;color:#1f2937}.dvrd-toolbar{display:flex;align-items:center;gap:6px;padding:7px 12px;background:#fff;border-bottom:1px solid #d8dee8}.dvrd-toolbar .spacer{flex:1}.dvrd-workspace{display:grid;grid-template-columns:285px minmax(480px,1fr) 300px;min-height:0}.dvrd-left,.dvrd-right{background:#fff;overflow:auto}.dvrd-left{border-right:1px solid #d8dee8}.dvrd-right{border-left:1px solid #d8dee8}.dvrd-tabs{display:flex;border-bottom:1px solid #e5e7eb;position:sticky;top:0;background:#fff;z-index:3}.dvrd-tab{flex:1;padding:11px 4px;text-align:center;cursor:pointer}.dvrd-tab.active{color:#2563eb;border-bottom:2px solid #2563eb;font-weight:600}.dvrd-panel{padding:12px}.dvrd-search{margin-bottom:10px}.dvrd-group-title{font-weight:650;margin:12px 0 6px}.dvrd-field,.dvrd-component,.dvrd-layer{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 9px;border:1px solid #e5e7eb;border-radius:6px;margin:5px 0;background:#fff;cursor:pointer}.dvrd-field:hover,.dvrd-component:hover,.dvrd-layer:hover{border-color:#93c5fd;background:#eff6ff}.dvrd-field small{color:#6b7280}.dvrd-center{overflow:auto;padding:28px;position:relative}.dvrd-stage{min-width:max-content;min-height:max-content;margin:auto}.dvrd-paper{position:relative;background:#fff;box-shadow:0 4px 18px #64748b55;transform-origin:top left;background-image:linear-gradient(to right,#dbeafe66 1px,transparent 1px),linear-gradient(to bottom,#dbeafe66 1px,transparent 1px)}.dvrd-element{position:absolute;box-sizing:border-box;overflow:hidden;white-space:nowrap;cursor:move;user-select:none;padding:2px 3px}.dvrd-element.selected{outline:2px solid #2563eb;z-index:999!important}.dvrd-element .resize{display:none;position:absolute;width:10px;height:10px;right:-1px;bottom:-1px;background:#2563eb;border:1px solid #fff;cursor:nwse-resize}.dvrd-element.selected .resize{display:block}.dvrd-table-preview{width:100%;border-collapse:collapse;font-size:inherit}.dvrd-table-preview th,.dvrd-table-preview td{border:1px solid #64748b;padding:2px}.dvrd-properties h4{font-size:14px;font-weight:700;margin:4px 0 12px}.dvrd-prop{margin-bottom:10px}.dvrd-prop label{display:block;font-size:12px;color:#64748b;margin-bottom:4px}.dvrd-grid2{display:grid;grid-template-columns:1fr 1fr;gap:8px}.dvrd-empty{padding:35px 12px;text-align:center;color:#64748b}.dvrd-status{font-size:12px;color:#64748b}.dvrd-status.dirty{color:#d97706}.dvrd-size{width:72px}.dvrd-menu-note{font-size:12px;color:#64748b;padding:8px;background:#f8fafc;border-radius:6px;margin-bottom:9px}@media(max-width:1100px){.dvrd-workspace{grid-template-columns:230px minmax(400px,1fr) 250px}}
		.dvrd{position:fixed!important;inset:0!important;z-index:1040!important;height:100vh!important;min-height:520px!important}.dvrd-toolbar{box-shadow:0 1px 4px #64748b22}.dvrd-toolbar-title{font-weight:700;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-right:8px}.dvrd.left-collapsed .dvrd-workspace{grid-template-columns:0 minmax(480px,1fr) 300px}.dvrd.left-collapsed .dvrd-left{display:none}
		.dvrd-table-preview th,.dvrd-table-preview td{border-color:#000!important}
		.dvrd-element.dvrd-line{padding:0;overflow:visible;background:transparent}.dvrd-element.dvrd-line:before{content:"";position:absolute}.dvrd-element.dvrd-line-horizontal:before{left:0;right:0;top:-4px;height:9px}.dvrd-element.dvrd-line-vertical:before{top:0;bottom:0;left:-4px;width:9px}.dvrd-element.dvrd-line.selected{outline:none}.dvrd-element.dvrd-line.selected:after{content:"";position:absolute;pointer-events:none;border:1px dashed #2563eb}.dvrd-element.dvrd-line-horizontal.selected:after{left:0;right:0;top:-4px;bottom:-4px}.dvrd-element.dvrd-line-vertical.selected:after{top:0;bottom:0;left:-4px;right:-4px}.dvrd-element.dvrd-line .resize{width:8px;height:8px;border-radius:50%;right:-4px;bottom:-4px}
	`).appendTo(page.main);

	if (!formatName) {
		root.html('<div class="dvrd-empty">请从“报表设计中心”选择一个模板进入设计。</div>');
		return;
	}

	function toolbar() {
		return `<div class="dvrd-toolbar"><button class="btn btn-sm btn-primary" data-cmd="save">保存</button><button class="btn btn-sm btn-default" data-cmd="preview">预览</button><button class="btn btn-sm btn-default" data-cmd="page-settings">页面设置</button><span class="border-start mx-1"></span><button class="btn btn-sm btn-default" data-cmd="undo">撤销</button><button class="btn btn-sm btn-default" data-cmd="redo">重做</button><button class="btn btn-sm btn-default" data-cmd="duplicate">复制</button><button class="btn btn-sm btn-default" data-cmd="delete">删除</button><span class="border-start mx-1"></span><button class="btn btn-sm btn-default" data-cmd="front">置顶</button><button class="btn btn-sm btn-default" data-cmd="back">置底</button><div class="spacer"></div><span class="dvrd-status ${dirty ? "dirty" : ""}">${dirty ? "未保存" : "已保存"}</span><select class="form-control dvrd-size" data-cmd="zoom"><option value="0.5">50%</option><option value="0.75">75%</option><option value="1">100%</option><option value="1.25">125%</option><option value="1.5">150%</option></select><button class="btn btn-sm btn-default" data-cmd="exit">退出</button></div>`;
	}

	async function load() {
		root.html('<div class="dvrd-empty">正在加载报表字段和画布…</div>');
		const response = await frappe.call({method: "dyeing_finishing.dyeing_finishing.page.dyeing_print_template_manager.dyeing_print_template_manager.get_visual_designer_data", args: {crispy_format: formatName}});
		data = response.message; visual = clone(data.visual); visual.page = visual.page || {};
		(visual.elements || []).forEach((item) => { if (["line", "vline", "grid"].includes(item.type) && (!item.line_color || item.line_color === "#334155")) item.line_color = "#000000"; });
		const baseMargin = Number(visual.page.margin_mm || 0);
		["margin_top_mm","margin_bottom_mm","margin_left_mm","margin_right_mm"].forEach(key => { if (visual.page[key] == null) visual.page[key] = baseMargin; });
		if (visual.page.label_gap_mm == null) visual.page.label_gap_mm = 0;
		commit(true); renderShell();
		page.set_title(`${data.name} · 可视化设计`);
	}

	function renderShell() {
		root.html(`${toolbar()}<div class="dvrd-workspace"><aside class="dvrd-left"><div class="dvrd-tabs"><div class="dvrd-tab active" data-tab="fields">字段</div><div class="dvrd-tab" data-tab="components">组件</div><div class="dvrd-tab" data-tab="layers">图层</div></div><div class="dvrd-panel" data-panel></div></aside><main class="dvrd-center"><div class="dvrd-stage"><div class="dvrd-paper"></div></div></main><aside class="dvrd-right"><div class="dvrd-panel dvrd-properties"></div></aside></div>`);
		root.find(".dvrd-toolbar").prepend(`<div class="dvrd-toolbar-title">${esc(data.name)}</div><button class="btn btn-sm btn-default" data-cmd="toggle-left">隐藏字段面板</button>`);
		root.find('[data-cmd="zoom"]').val(String(zoom)); renderLeft("fields"); renderCanvas(); renderProperties(); bindCommands();
	}

	function renderLeft(tab) {
		root.find(".dvrd-tab").removeClass("active").filter(`[data-tab="${tab}"]`).addClass("active");
		const panel = root.find("[data-panel]");
		if (tab === "fields") {
			panel.html(`<input class="form-control dvrd-search" placeholder="搜索中文名称或字段名"><div class="dvrd-menu-note">点击字段即可加入画布，加入后可自由拖动和缩放。</div>` + data.groups.map((group) => `<div class="dvrd-field-group"><div class="dvrd-group-title">${esc(group.label)}</div>${group.fields.map((field) => `<div class="dvrd-field" data-field="${esc(field.fieldname)}" data-label="${esc(field.label)}" data-type="${esc(field.fieldtype)}" data-table="${esc(group.table_field || "")}"><span>${esc(field.label)}</span><small>${esc(field.fieldname)}</small></div>`).join("")}</div>`).join(""));
		} else if (tab === "components") {
			panel.html('<div class="dvrd-menu-note">线条用于自由划线；静态表格可快速生成等宽、等高的空白格。</div>' + [["text","文本"],["rect","矩形/边框"],["line","水平线"],["vline","垂直线"],["grid","静态表格/分格"],["barcode","条码"],["table","数据明细表"]].map(x => `<div class="dvrd-component" data-component="${x[0]}">${x[1]}<span>+</span></div>`).join(""));
		} else {
			panel.html((visual.elements || []).slice().reverse().map((item, i) => `<div class="dvrd-layer ${item.id === selected ? "selected" : ""}" data-select="${item.id}"><span>${esc(elementName(item))}</span><small>${visual.elements.length - i}</small></div>`).join("") || '<div class="dvrd-empty">暂无组件</div>');
		}
	}

	function renderCanvas() {
		if (canvasFrame) { cancelAnimationFrame(canvasFrame); canvasFrame = null; }
		const px = 3.2 * zoom, page = visual.page, paper = root.find(".dvrd-paper");
		paper.css({width: page.width_mm * px, height: page.height_mm * px, backgroundSize: `${(page.grid_mm || 5) * px}px ${(page.grid_mm || 5) * px}px`, backgroundImage: visual.show_grid ? "" : "none"});
		const mt=Number(page.margin_top_mm||0), mb=Number(page.margin_bottom_mm||0), ml=Number(page.margin_left_mm||0), mr=Number(page.margin_right_mm||0);
		const safe=`<div style="position:absolute;pointer-events:none;border:1px dashed #f59e0b;left:${ml*px}px;top:${mt*px}px;width:${Math.max(0,page.width_mm-ml-mr)*px}px;height:${Math.max(0,page.height_mm-mt-mb)*px}px;box-sizing:border-box;z-index:998"></div>`;
		paper.html(safe + (visual.elements || []).map((item, index) => elementHtml(item, index, px)).join(""));
		bindCanvas(px);
	}

	function scheduleCanvasRender() {
		if (canvasFrame) return;
		canvasFrame = requestAnimationFrame(() => { canvasFrame = null; renderCanvas(); });
	}

	function elementHtml(item, index, px) {
		const sample = data.sample || {}; let content = "";
		if (item.type === "text") content = esc(item.text || "文本");
		else if (item.type === "rect") content = "";
		else if (item.type === "line") content = "";
		else if (item.type === "vline") content = "";
		else if (item.type === "grid") content = "";
		else if (item.type === "barcode") content = `<div style="font-family:monospace;letter-spacing:2px">||| ${esc(sample[item.fieldname] || item.fieldname || "BARCODE")} |||</div>`;
		else if (item.type === "table") {
			const cols = item.columns || [], rows = sample[item.fieldname] || [{}];
			const groups = Math.max(1, Number(item.repeat_columns) || 1), perGroup = Math.max(1, Number(item.rows_per_group) || 8);
			const headers = Array.from({length:groups}, () => cols).flat().map(c => `<th>${esc(c.label || c.fieldname)}</th>`).join("");
			const bodyRows = Array.from({length:Math.min(perGroup, 8)}, (_, rowIndex) => `<tr>${Array.from({length:groups}, (_, groupIndex) => {
				const row = rows[groupIndex * perGroup + rowIndex] || {};
				return cols.map(c => `<td>${esc(row[c.fieldname] || "")}</td>`).join("");
			}).join("")}</tr>`).join("");
			content = `<table class="dvrd-table-preview" style="${item.fill_height !== 0 ? "height:100%;table-layout:fixed" : ""}"><thead><tr>${headers}</tr></thead><tbody>${bodyRows}</tbody></table>`;
		} else { let value = sample[item.fieldname] || `{{ ${item.fieldname || "字段"} }}`; if (item.format === "date_dot") value = String(value).replaceAll("-", "."); content = `${item.show_label === 0 ? "" : `<b>${esc(item.label || item.fieldname)} </b>`}${esc(value)}`; }
		const lineWidth = Math.max(Number(item.line_width) || .5, .1), lineColor = /^#[0-9a-f]{6}$/i.test(item.line_color || "") ? item.line_color : "#000000";
		if (item.type === "grid") {
			const rows = Math.max(1, Math.floor(Number(item.rows) || 2)), cols = Math.max(1, Math.floor(Number(item.cols) || 2));
			content = `<table class="dvrd-table-preview" style="width:100%;height:100%;border-collapse:collapse">${Array.from({length:rows}, () => `<tr>${Array.from({length:cols}, () => `<td style="border:${lineWidth}px solid ${lineColor}"></td>`).join("")}</tr>`).join("")}</table>`;
		}
		const isHorizontalLine = item.type === "line", isVerticalLine = item.type === "vline";
		const lineClass = isHorizontalLine ? "dvrd-line dvrd-line-horizontal" : isVerticalLine ? "dvrd-line dvrd-line-vertical" : "";
		const edgeStyle = isHorizontalLine ? `border-top:${lineWidth}px solid ${lineColor};` : isVerticalLine ? `border-left:${lineWidth}px solid ${lineColor};` : item.type === "grid" ? "border:none;" : item.border ? "border:1px solid #000000;" : "border:none;";
		return `<div class="dvrd-element ${lineClass} ${item.id === selected ? "selected" : ""}" data-id="${item.id}" style="left:${item.x*px}px;top:${item.y*px}px;width:${item.w*px}px;height:${item.h*px}px;font-size:${(item.font_size||9)*zoom}px;font-weight:${item.bold ? 700 : 400};text-align:${item.align||"left"};${edgeStyle}z-index:${item.z == null ? index : item.z}">${content}<span class="resize"></span></div>`;
	}

	function bindCanvas(px) {
		root.find(".dvrd-element").off(".dvrdCanvas").on("mousedown.dvrdCanvas", function (event) {
			event.preventDefault(); selected = $(this).data("id"); renderProperties(); root.find(".dvrd-element").removeClass("selected"); $(this).addClass("selected");
			const node=$(this),item=current(),resizing=$(event.target).hasClass("resize"),start={x:event.clientX,y:event.clientY,ix:item.x,iy:item.y,iw:item.w,ih:item.h};
			$(document).off(".dvrdDrag").on("mousemove.dvrdDrag",(e)=>{const dx=(e.clientX-start.x)/px,dy=(e.clientY-start.y)/px,grid=visual.snap?(visual.page.grid_mm||1):.1,snap=v=>Math.round(v/grid)*grid;if(resizing){item.w=Math.max(grid,snap(start.iw+dx));item.h=Math.max(grid,snap(start.ih+dy));node.css({width:item.w*px,height:item.h*px});}else{item.x=Math.max(0,snap(start.ix+dx));item.y=Math.max(0,snap(start.iy+dy));node.css({left:item.x*px,top:item.y*px});}}).one("mouseup.dvrdDrag",()=>{$(document).off(".dvrdDrag");commit();renderCanvas();renderProperties();});
		}).on("click.dvrdCanvas", function (e) {e.stopPropagation(); selected=$(this).data("id"); renderCanvas(); renderProperties();});
		root.find(".dvrd-paper").off("click.dvrdCanvas").on("click.dvrdCanvas", () => {selected=null;renderCanvas();renderProperties();});
	}

	function renderProperties() {
		const panel = root.find(".dvrd-properties"), item = current();
		if (!item) {
			const p=visual.page;
			const margin = p.margin_mm || 0;
			panel.html(`<h4>页面与标签设置</h4><div class="dvrd-menu-note">纸张尺寸为单张标签大小；标签间隔用于连续标签纸走纸。</div><div class="dvrd-grid2"><div class="dvrd-prop"><label>纸张宽度 mm</label><input class="form-control" data-page="width_mm" type="number" step="0.1" value="${p.width_mm}"></div><div class="dvrd-prop"><label>纸张高度 mm</label><input class="form-control" data-page="height_mm" type="number" step="0.1" value="${p.height_mm}"></div><div class="dvrd-prop"><label>上边距 mm</label><input class="form-control" data-page="margin_top_mm" type="number" step="0.1" value="${p.margin_top_mm ?? margin}"></div><div class="dvrd-prop"><label>下边距 mm</label><input class="form-control" data-page="margin_bottom_mm" type="number" step="0.1" value="${p.margin_bottom_mm ?? margin}"></div><div class="dvrd-prop"><label>左边距 mm</label><input class="form-control" data-page="margin_left_mm" type="number" step="0.1" value="${p.margin_left_mm ?? margin}"></div><div class="dvrd-prop"><label>右边距 mm</label><input class="form-control" data-page="margin_right_mm" type="number" step="0.1" value="${p.margin_right_mm ?? margin}"></div><div class="dvrd-prop"><label>标签纵向间隔 mm</label><input class="form-control" data-page="label_gap_mm" type="number" min="0" step="0.1" value="${p.label_gap_mm || 0}"></div><div class="dvrd-prop"><label>网格 mm</label><input class="form-control" data-page="grid_mm" type="number" min="0.1" step="0.1" value="${p.grid_mm||1}"></div></div><div class="checkbox"><label><input type="checkbox" data-flag="show_grid" ${visual.show_grid ? "checked":""}> 显示网格</label></div><div class="checkbox"><label><input type="checkbox" data-flag="snap" ${visual.snap ? "checked":""}> 对齐网格</label></div>`);
		} else {
			const binding = ["field","barcode","table"].includes(item.type) ? `<div class="dvrd-menu-note"><b>当前绑定：${esc(item.label || item.fieldname)}</b><br><small>${esc(item.fieldname || "")}</small><br><button class="btn btn-xs btn-default mt-2" data-action="replace-field">更换字段</button></div>` : "";
			const isRule = ["line","vline","grid"].includes(item.type);
			const textControls = isRule || item.type === "rect" ? "" : `<div class="dvrd-group-title">文字格式</div><div class="dvrd-grid2">${fontSizeProp(item.font_size||9)}<div class="dvrd-prop"><label>水平对齐</label><select class="form-control" data-prop="align"><option value="left">靠左</option><option value="center">居中</option><option value="right">靠右</option></select></div></div><div class="checkbox"><label><input type="checkbox" data-check="bold" ${item.bold ? "checked":""}> 粗体</label></div>`;
			const ruleControls = isRule ? `<div class="dvrd-group-title">线条设置</div><div class="dvrd-grid2">${prop("线宽 (pt)","line_width",item.line_width||.5,"number")}${prop("线条颜色","line_color",item.line_color||"#000000","color")}${item.type === "grid" ? prop("行数","rows",item.rows||2,"number") + prop("列数","cols",item.cols||2,"number") : ""}</div>` : "";
			const tableControls = item.type === "table" ? `<div class="dvrd-group-title">明细分栏</div><div class="dvrd-grid2">${prop("横向分组数","repeat_columns",item.repeat_columns||1,"number")}${prop("每组行数","rows_per_group",item.rows_per_group||8,"number")}</div><div class="checkbox"><label><input type="checkbox" data-check="fill_height" ${item.fill_height !== 0 ? "checked":""}> 空白行自动填满明细区高度</label></div>` : "";
			panel.html(`<h4>组件属性 · ${esc(elementName(item))}</h4>${binding}${item.type === "text" ? prop("文本","text",item.text) : ""}${["field","barcode","table"].includes(item.type) ? prop("显示名称","label",item.label) : ""}${textControls}${ruleControls}${tableControls}<div class="dvrd-group-title">位置与尺寸</div><div class="dvrd-grid2">${prop("X (mm)","x",item.x,"number")}${prop("Y (mm)","y",item.y,"number")}${prop("宽 (mm)","w",item.w,"number")}${prop("高 (mm)","h",item.h,"number")}</div>${isRule ? "" : `<div class="checkbox"><label><input type="checkbox" data-check="border" ${item.border ? "checked":""}> 边框</label></div>`}${item.type === "field" ? `<div class="checkbox"><label><input type="checkbox" data-check="show_label" ${item.show_label !== 0 ? "checked":""}> 显示字段名称</label></div>`:""}`);
			panel.find('[data-prop="align"]').val(item.align||"left");
		}
		if (item) panel.prepend('<div class="dvrd-menu-note">选中后可用方向键移动；Alt + 方向键精确移动 0.1 mm；Shift + 方向键加速移动。</div>');
		if (!item) panel.prepend(`<div class="dvrd-prop"><label>应用已保存纸张规格</label><select class="form-control" data-paper-preset><option value="">请选择</option>${(data.paper_formats||[]).map(row=>`<option value="${esc(row.name)}">${esc(row.paper_name)}（${row.width_mm}×${row.height_mm} mm）</option>`).join("")}</select></div><div class="dvrd-prop"><label>纸张格式名称</label><input class="form-control" data-page="paper_name" type="text" value="${esc(visual.page.paper_name || "")}" placeholder="例如：中一刀"></div><button class="btn btn-sm btn-default w-100 mb-3" data-action="save-paper-format">将当前页面另存为纸张规格</button>`);
		panel.find("[data-prop]").on("change input", function(){const it=current();if(!it)return;const key=$(this).data("prop"),value=$(this).val();it[key]=["x","y","w","h","font_size","line_width","rows","cols","repeat_columns","rows_per_group"].includes(key)?Number(value):value;mark();scheduleCanvasRender();});
		panel.find("[data-check]").on("change", function(){current()[$(this).data("check")] = this.checked ? 1 : 0;mark();renderCanvas();});
		panel.find("[data-page]").on("change", function(){const key=$(this).data("page");visual.page[key]=key === "paper_name" ? String($(this).val()).trim() : Number($(this).val());commit();renderCanvas();});
		panel.find("[data-flag]").on("change", function(){visual[$(this).data("flag")]=this.checked?1:0;commit();renderCanvas();});
		panel.find('[data-action="replace-field"]').on("click", replaceCurrentField);
		panel.find("[data-paper-preset]").on("change", function(){applyPaperFormat($(this).val());});
		panel.find('[data-action="save-paper-format"]').on("click", saveCurrentPaperFormat);
	}

	function applyPaperFormat(name) {
		const row=(data.paper_formats||[]).find(item=>item.name===name); if(!row)return;
		Object.assign(visual.page,{paper_name:row.paper_name,width_mm:row.width_mm,height_mm:row.height_mm,
			orientation:row.orientation==="横向"?"landscape":"portrait",grid_mm:row.grid_mm,label_gap_mm:row.label_gap_mm,
			margin_top_mm:row.margin_top_mm,margin_bottom_mm:row.margin_bottom_mm,
			margin_left_mm:row.margin_left_mm,margin_right_mm:row.margin_right_mm});
		commit();renderCanvas();renderProperties();
	}

	async function saveCurrentPaperFormat() {
		const p=visual.page,name=String(p.paper_name||"").trim();
		if(!name){frappe.msgprint("请先填写纸张格式名称。");return;}
		const response=await frappe.call({method:"dyeing_finishing.dyeing_finishing.page.dyeing_print_template_manager.dyeing_print_template_manager.save_paper_format",args:{paper_name:name,width_mm:p.width_mm,height_mm:p.height_mm,margin_top_mm:p.margin_top_mm,margin_bottom_mm:p.margin_bottom_mm,margin_left_mm:p.margin_left_mm,margin_right_mm:p.margin_right_mm,grid_mm:p.grid_mm,label_gap_mm:p.label_gap_mm},freeze:true,freeze_message:"正在保存纸张规格…"});
		const row=response.message;if(!(data.paper_formats||[]).some(item=>item.name===row.name))data.paper_formats.push(row);
		frappe.show_alert({message:"纸张规格已保存",indicator:"green"});renderProperties();
	}

	async function replaceCurrentField() {
		const item = current(); if (!item) return;
		const fields = item.type === "table" ? data.groups.filter(g => g.table_field).map(g => ({fieldname:g.table_field,label:g.label,group:g})) : data.groups.flatMap(g => g.table_field ? [] : g.fields);
		const value = await chooseField(item.type, fields); if (!value) return;
		item.fieldname = value.fieldname; item.label = value.label || value.fieldname;
		if (item.type === "table") item.columns = (value.group?.fields || []).slice(0, 6).map(f => ({fieldname:f.fieldname,label:f.label}));
		commit(); renderCanvas(); renderProperties();
	}

	function prop(label,key,value,type="text") {return `<div class="dvrd-prop"><label>${label}</label><input class="form-control" data-prop="${key}" type="${type}" value="${esc(value)}"></div>`;}
	function fontSizeProp(value) {
		const sizes = [6, 7, 8, 9, 10, 10.5, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 72];
		if (!sizes.includes(Number(value))) sizes.push(Number(value));
		sizes.sort((a, b) => a - b);
		return `<div class="dvrd-prop"><label>字体大小 (pt)</label><select class="form-control" data-prop="font_size">${sizes.map(size => `<option value="${size}" ${Number(value) === size ? "selected" : ""}>${size} pt</option>`).join("")}</select></div>`;
	}
	function current(){return (visual.elements||[]).find(x=>x.id===selected);}
	function elementName(item){return item.type === "text" ? (item.text||"文本") : item.label || item.fieldname || ({rect:"矩形",line:"水平线",vline:"垂直线",grid:"静态表格",barcode:"条码",table:"数据明细表"}[item.type]||item.type);}
	function makeId(){return `el-${Date.now()}-${Math.random().toString(36).slice(2,7)}`;}
	function add(item){const margin=visual.page.margin_mm||2;item={id:makeId(),x:margin,y:margin+12,w:60,h:8,font_size:9,align:"left",border:0,bold:0,z:visual.elements.length,...item};visual.elements.push(item);selected=item.id;commit();renderCanvas();renderProperties();}
	function mark(){dirty=true;root.find(".dvrd-status").text("未保存").addClass("dirty");}
	function commit(initial=false){const snapshot=JSON.stringify(visual);if(history[historyIndex]===snapshot)return;history=history.slice(0,historyIndex+1);history.push(snapshot);historyIndex=history.length-1;if(!initial)mark();}
	function restore(index){if(index<0||index>=history.length)return;historyIndex=index;visual=JSON.parse(history[index]);selected=null;mark();renderCanvas();renderProperties();}
	function isEditingControl(target){return $(target).is("input, textarea, select, [contenteditable=true]");}
	function moveSelectedWithKeyboard(key, event){
		const item=current(); if(!item)return false;
		const grid=Math.max(Number(visual.page.grid_mm)||1,.1);
		const step=event.altKey ? 0.1 : event.shiftKey ? grid*5 : grid;
		let dx=0,dy=0;
		if(key==="ArrowLeft")dx=-step;else if(key==="ArrowRight")dx=step;else if(key==="ArrowUp")dy=-step;else if(key==="ArrowDown")dy=step;else return false;
		const maxX=Math.max(0,Number(visual.page.width_mm||0)-Number(item.w||0));
		const maxY=Math.max(0,Number(visual.page.height_mm||0)-Number(item.h||0));
		item.x=Math.round(Math.min(maxX,Math.max(0,Number(item.x||0)+dx))*1000)/1000;
		item.y=Math.round(Math.min(maxY,Math.max(0,Number(item.y||0)+dy))*1000)/1000;
		commit();renderCanvas();renderProperties();return true;
	}

	function bindCommands() {
		root.find(".dvrd-tab").on("click",function(){renderLeft($(this).data("tab"));});
		root.find('[data-cmd="toggle-left"]').on("click", function(){root.toggleClass("left-collapsed");$(this).text(root.hasClass("left-collapsed") ? "显示字段面板" : "隐藏字段面板");});
		root.on("input", ".dvrd-search", function(){const q=String($(this).val()).toLowerCase();root.find(".dvrd-field").each(function(){$(this).toggle($(this).text().toLowerCase().includes(q));});});
		root.on("click", ".dvrd-field", function(){add({type:"field",fieldname:$(this).data("field"),label:$(this).data("label"),show_label:1,w:visual.page.width_mm<100?visual.page.width_mm-2*(visual.page.margin_mm||2):85,border:visual.page.width_mm<100?1:0});});
		root.on("click", ".dvrd-component", async function(){const type=$(this).data("component");if(type==="text")add({type,text:"新文本",w:50});else if(type==="rect")add({type,w:50,h:25,border:1});else if(type==="line")add({type,w:50,h:1,line_width:.5,line_color:"#000000"});else if(type==="vline")add({type,w:1,h:50,line_width:.5,line_color:"#000000"});else if(type==="grid")add({type,w:60,h:30,rows:3,cols:3,line_width:.5,line_color:"#000000"});else{const fields=data.groups[0].fields;const value=await chooseField(type,fields);if(!value)return;if(type==="table"){const tableGroup=data.groups.find(g=>g.table_field===value.fieldname);add({type,fieldname:value.fieldname,label:value.label,w:visual.page.width_mm-2*(visual.page.margin_mm||2),h:40,border:1,columns:(tableGroup?.fields||[]).slice(0,6).map(f=>({fieldname:f.fieldname,label:f.label}))});}else add({type,fieldname:value.fieldname,label:value.label,w:55,h:10});}});
		root.on("click", "[data-select]", function(){selected=$(this).data("select");renderCanvas();renderProperties();});
		root.find("[data-cmd]").on("click change", async function(e){const cmd=$(this).data("cmd");if(cmd==="zoom"){zoom=Number($(this).val());renderCanvas();return;}if(e.type!=="click")return;if(cmd==="page-settings"){selected=null;renderCanvas();renderProperties();return;}if(cmd==="save")await save();if(cmd==="preview"){await save();await ensurePublished();frappe.route_options={format:data.name};frappe.set_route("crispy-print-preview",data.doctype,data.preview_doc);}if(cmd==="undo")restore(historyIndex-1);if(cmd==="redo")restore(historyIndex+1);if(cmd==="delete"&&selected){visual.elements=visual.elements.filter(x=>x.id!==selected);selected=null;commit();renderCanvas();renderProperties();}if(cmd==="duplicate"&&current()){const copy=clone(current());copy.id=makeId();copy.x+=visual.page.grid_mm||2;copy.y+=visual.page.grid_mm||2;visual.elements.push(copy);selected=copy.id;commit();renderCanvas();renderProperties();}if(cmd==="front"&&current()){current().z=Math.max(...visual.elements.map(x=>Number(x.z)||0))+1;commit();renderCanvas();}if(cmd==="back"&&current()){current().z=Math.min(...visual.elements.map(x=>Number(x.z)||0))-1;commit();renderCanvas();}if(cmd==="exit")frappe.set_route("dyeing-print-template-manager");});
	}

	async function chooseField(type, fields) {
		if(type==="table" && !fields.some(field => field.group)){const tables=data.groups.filter(g=>g.table_field).map(g=>({label:g.label,fieldname:g.table_field,group:g}));if(!tables.length){frappe.msgprint("当前表单没有可用明细表。");return null;}fields=tables;}
		return new Promise(resolve=>{const d=new frappe.ui.Dialog({title:type==="table"?"选择明细表":"选择或更换字段",fields:[{label:"字段",fieldname:"fieldname",fieldtype:"Autocomplete",options:fields.map(f=>({label:`${f.label || f.fieldname} (${f.fieldname})`,value:f.fieldname})),reqd:1}],primary_action_label:"确定",primary_action(v){d.hide();resolve(fields.find(f=>f.fieldname===v.fieldname));}});d.$wrapper.on("hidden.bs.modal",()=>resolve(null));d.show();});
	}

	async function save(){commit();await frappe.call({method:"dyeing_finishing.dyeing_finishing.page.dyeing_print_template_manager.dyeing_print_template_manager.save_visual_designer",args:{crispy_format:data.name,visual:JSON.stringify(visual)},freeze:true,freeze_message:"正在保存并生成打印模板…"});dirty=false;root.find(".dvrd-status").text("已保存").removeClass("dirty");frappe.show_alert({message:"报表已保存",indicator:"green"});}
	async function ensurePublished(){return frappe.call({method:"dyeing_finishing.dyeing_finishing.page.dyeing_print_template_manager.dyeing_print_template_manager.ensure_active_print_template",args:{crispy_format:data.name},freeze:true,freeze_message:"正在准备打印预览…"});}

	$(document).off("keydown.dvrd").on("keydown.dvrd",function(e){if(!root.is(":visible"))return;if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="s"){e.preventDefault();save();}else if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="z"){e.preventDefault();restore(e.shiftKey?historyIndex+1:historyIndex-1);}else if(!isEditingControl(e.target)&&moveSelectedWithKeyboard(e.key,e)){e.preventDefault();}else if(!isEditingControl(e.target)&&e.key==="Delete"&&selected){e.preventDefault();root.find('[data-cmd="delete"]').trigger("click");}});
	load();
};

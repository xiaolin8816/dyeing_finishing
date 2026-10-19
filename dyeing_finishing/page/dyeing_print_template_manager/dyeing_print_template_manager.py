import json
import re
import shutil
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cint



def _ensure_visual_cjk_font():
	"""Make a Simplified Chinese font available to Crispy's isolated Typst compiler."""
	target_dir = Path(frappe.get_site_path("private", "files", "crispy_print", "fonts"))
	target = target_dir / "WenQuanYiZenHei.ttc"
	if not target.exists():
		source = next((path for path in (
			Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
			Path("/usr/share/fonts/opentype/unifont/unifont.otf"),
		) if path.exists()), None)
		if not source:
			frappe.throw(_("服务器缺少可用于中文报表的字体，请安装文泉驿正黑或 Unifont"))
		target_dir.mkdir(parents=True, exist_ok=True)
		shutil.copy2(source, target)
	return "WenQuanYi Zen Hei"

_CRISPY_PILOTS = {
	"生产流转卡 A4": {
		"doc_type": "Production Flow Card",
		"category": "单据",
		"page_size": "A4",
		"typst_preamble": "#set text(font: (\"Noto Sans CJK SC\", \"Microsoft YaHei\", \"Inter\"), size: 9pt)",
		"layout": {
			"schema_version": 4,
			"sections": [
				{"id": "flow-main", "label": "生产流转卡", "columns": [
					{"id": "flow-left", "width": 1, "fields": [
						{"fieldname": "flow_card_no", "label": "流转卡号", "fieldtype": "Data", "align": "auto"},
						{"fieldname": "customer", "label": "客户名称", "fieldtype": "Link", "align": "auto"},
						{"fieldname": "finished_product_name", "label": "成品名称", "fieldtype": "Data", "align": "auto"},
						{"fieldname": "finished_specification", "label": "成品规格", "fieldtype": "Data", "align": "auto"},
					]},
					{"id": "flow-right", "width": 1, "fields": [
						{"fieldname": "color_no", "label": "色号", "fieldtype": "Link", "align": "auto"},
						{"fieldname": "color", "label": "颜色", "fieldtype": "Data", "align": "auto"},
						{"fieldname": "production_qty", "label": "流转卡数量", "fieldtype": "Float", "align": "end"},
						{"fieldname": "finished_uom", "label": "成品单位", "fieldtype": "Link", "align": "auto"},
					]},
				]},
				{"id": "flow-operations", "label": "生产工序", "columns": [{"id": "flow-operations-table", "width": 1, "fields": [
					{"fieldname": "operations", "label": "生产工序", "fieldtype": "Table", "orderMode": "logical", "columns": [
						{"fieldname": "sequence_no", "label": "顺序号", "align": "end"},
						{"fieldname": "operation_name", "label": "工序名称", "align": "start"},
						{"fieldname": "operation_status", "label": "工序状态", "align": "start"},
						{"fieldname": "resource_name", "label": "生产机台", "align": "start"},
						{"fieldname": "completed_qty", "label": "完成数量", "align": "end"},
						{"fieldname": "pending_qty", "label": "剩余数量", "align": "end"},
					]
				}]}]},
			],
		},
	},
	"成品空白标签 60×80mm": {
		"doc_type": "Finished Product Blank Label",
		"category": "标签",
		"page_size": "60×80 mm",
		"layout": {"schema_version": 4, "sections": [
			{"id": "label-main", "label": "成品标签", "columns": [{"id": "label-fields", "width": 1, "fields": [
				{"fieldname": "customer", "label": "客户", "fieldtype": "Link", "align": "auto"},
				{"fieldname": "print_date", "label": "日期", "fieldtype": "Date", "align": "auto"},
				{"fieldname": "color_no", "label": "色号", "fieldtype": "Link", "align": "auto"},
				{"fieldname": "flow_card_no", "label": "缸号", "fieldtype": "Data", "align": "auto"},
				{"fieldname": "composition", "label": "成份", "fieldtype": "Data", "align": "auto"},
				{"fieldname": "finished_product_name", "label": "品名", "fieldtype": "Data", "align": "auto"},
				{"fieldname": "finished_specification", "label": "规格", "fieldtype": "Data", "align": "auto"},
				{"fieldname": "color", "label": "颜色", "fieldtype": "Data", "align": "auto"},
				{"fieldname": "label_remarks", "label": "备注", "fieldtype": "Small Text", "align": "auto"},
			]}]},
		]},
		"typst_preamble": "#set page(width: 60mm, height: 80mm, margin: 2mm)\n#set text(font: (\"Noto Sans CJK SC\", \"Microsoft YaHei\"), size: 8pt)\n#set table(stroke: 0.5pt, inset: 2pt)",
		"raw_typst": 1,
		"typst_code": """#set page(width: 60mm, height: 80mm, margin: 2mm)\n#set text(font: (\"Noto Sans CJK SC\", \"Microsoft YaHei\", \"Inter\"), size: 8pt)\n#set table(stroke: 0.5pt, inset: 2pt)\n#align(center)[#text(size: 11pt, weight: \"bold\")[成品标签]]\n#v(2mm)\n#table(\n  columns: (13mm, 1fr),\n  [客户], [#doc.customer_name],\n  [日期], [#doc.print_date],\n  [色号], [#doc.color_no],\n  [缸号], [#doc.flow_card_no],\n  [成份], [#doc.composition],\n  [品名], [#doc.finished_product_name],\n  [规格], [#doc.finished_specification],\n  [颜色], [#doc.color],\n  [备注], [#doc.label_remarks],\n)""",
	},
	"成品包装入库单": {
		"doc_type": "Finished Product Packing Receipt", "category": "单据", "page_size": "A4",
		"layout": {"schema_version": 4, "sections": [
			{"id": "packing-main", "label": "成品包装入库单", "columns": [
				{"id": "packing-left", "width": 1, "fields": [
					{"fieldname": "packing_receipt_no", "label": "入库单号", "fieldtype": "Data"},
					{"fieldname": "packing_date", "label": "入库日期", "fieldtype": "Date"},
					{"fieldname": "customer_name", "label": "客户名称", "fieldtype": "Data"},
					{"fieldname": "production_flow_card", "label": "生产流转卡", "fieldtype": "Link"}]},
				{"id": "packing-right", "width": 1, "fields": [
					{"fieldname": "finished_product_name", "label": "成品名称", "fieldtype": "Data"},
					{"fieldname": "finished_specification", "label": "成品规格", "fieldtype": "Data"},
					{"fieldname": "color_no", "label": "色号", "fieldtype": "Link"},
					{"fieldname": "color", "label": "颜色", "fieldtype": "Data"}]}
			]},
			{"id": "packing-items", "label": "包装明细", "columns": [{"id": "packing-table", "width": 1,
				"fields": [{"fieldname": "items", "label": "包装明细", "fieldtype": "Table", "columns": [
					{"fieldname": "piece_no", "label": "匹号"}, {"fieldname": "weight", "label": "成品重量"},
					{"fieldname": "yard_qty", "label": "码数"}, {"fieldname": "finished_grade", "label": "成品等级"},
					{"fieldname": "package_no", "label": "包号/托盘号"}, {"fieldname": "barcode", "label": "条码/二维码"}
				]}]}]}
		]},
	},
}


def _crispy_presentation(page_size="A4"):
	return {
		"source": "dyeing_finishing",
		"page": {"size": page_size, "orientation": "portrait", "margins": {"top": 10, "bottom": 10, "left": 10, "right": 10}},
		"branding": {"profile": "", "company": "", "mode": "none", "letterhead": "", "letterhead_image": "", "logo": {"company": "", "image": "", "size": 25, "dx": 0, "dy": 0, "anchor": "left"}},
		"language": "zh",
		"qr": {"dx": 0, "dy": 0, "size": 15, "anchor": "left", "fields": [], "enabled": False, "sourceMode": "", "symbology": "QR Code", "errorCorrection": "Medium", "quietZone": 1, "moduleSize": 3},
	}


def _ensure_crispy_pilots():
	if not frappe.db.exists("DocType", "Crispy Format"):
		frappe.throw(_("未安装 Crispy Print，无法打开新报表设计中心"))
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
	created = []
	for name, spec in _CRISPY_PILOTS.items():
		if frappe.db.exists("Crispy Format", name):
			continue
		doc = frappe.get_doc({
			"doctype": "Crispy Format", "name": name, "crispy_format_type": "DocType",
			"doc_type": spec["doc_type"], "company": company, "module": "dyeing_finishing",
			"is_default": 0, "default_print_language": "zh", "pdf_standard": "PDF 1.7",
			"layout_json": json.dumps(spec["layout"], ensure_ascii=False),
			"presentation_settings": json.dumps(_crispy_presentation("A4" if spec["page_size"] == "A4" else "A5"), ensure_ascii=False),
		})
		if spec.get("typst_preamble"):
			doc.typst_preamble = spec["typst_preamble"]
		if spec.get("raw_typst"):
			doc.raw_typst = 1
			doc.typst_code = spec["typst_code"]
		doc.insert(ignore_permissions=True)
		created.append(name)
	return created


@frappe.whitelist()
def get_crispy_templates():
	frappe.only_for("System Manager")
	_ensure_crispy_pilots()
	modules = dict(frappe.get_all("DocType", fields=["name", "module"], as_list=True))
	rows = frappe.get_all("Crispy Format", fields=["name", "doc_type", "company", "module", "is_default", "modified", "modified_by", "layout_json", "presentation_settings"], order_by="modified desc")
	result = []
	for row in rows:
		if row.module != "dyeing_finishing" and modules.get(row.doc_type) != "dyeing_finishing":
			continue
		layout = _json(row.layout_json, {})
		bindings = sorted({field.get("fieldname") for section in layout.get("sections", []) for column in section.get("columns", []) for field in column.get("fields", []) if field.get("fieldname")})
		missing = [name for name in bindings
			if name != "name" and not name.startswith("__") and not frappe.get_meta(row.doc_type).get_field(name)]
		pilot = _CRISPY_PILOTS.get(row.name, {})
		settings = _json(row.presentation_settings, {})
		visual_page = (layout.get("dyeing_visual") or {}).get("page") or {}
		custom_size = (f'{float(visual_page["width_mm"]):g}×{float(visual_page["height_mm"]):g} mm'
			if visual_page.get("width_mm") and visual_page.get("height_mm") else None) or (settings.get("page") or {}).get("size") or "A4"
		paper_name = visual_page.get("paper_name") or (settings.get("page") or {}).get("custom_name") or ""
		page_size = pilot.get("page_size") or (f"{paper_name} ({custom_size})" if paper_name and custom_size else custom_size)
		checks = []
		if not row.layout_json: checks.append({"level": "error", "message": "尚未建立可视布局"})
		if not row.presentation_settings: checks.append({"level": "warning", "message": "尚未保存页面设置"})
		for fieldname in missing: checks.append({"level": "error", "message": _('字段不存在：{0}').format(fieldname)})
		result.append({"name": row.name, "doc_type": row.doc_type, "doc_type_label": _(row.doc_type), "company": row.company or "", "category": pilot.get("category") or layout.get("dyeing_template_type") or ("标签" if "label" in row.name.lower() else "单据"), "page_size": page_size, "is_default": cint(row.is_default), "modified": row.modified, "modified_by": row.modified_by, "binding_count": len(bindings), "bindings": bindings, "checks": checks, "health": "error" if any(x["level"] == "error" for x in checks) else "warning" if checks else "ok", "preview_doc": _latest_document(row.doc_type)})
	return result


@frappe.whitelist()
def create_crispy_template(template_name, doc_type, template_type="业务单据", page_size="A4", width=None, height=None, paper_name=None, paper_format=None):
	frappe.only_for("System Manager")
	name = (template_name or "").strip()
	if not name: frappe.throw(_("模板名称不能为空"))
	if frappe.db.exists("Crispy Format", name): frappe.throw(_("模板名称已存在"))
	meta = frappe.get_meta(doc_type)
	fields = []
	for field in meta.fields:
		if field.fieldname and field.fieldtype not in {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Table", "Table MultiSelect"} and not field.hidden:
			fields.append({"fieldname": field.fieldname, "label": _(field.label or field.fieldname), "fieldtype": field.fieldtype, "align": "end" if field.fieldtype in {"Int", "Float", "Currency", "Percent"} else "auto"})
		if len(fields) >= 8: break
	category = "标签" if template_type == "标签" else "单据"
	layout = {"schema_version": 4, "dyeing_template_type": category,
		"sections": [{"id": "main", "label": name, "columns": [{"id": "main-fields", "width": 1, "fields": fields}]}]}
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
	preset = frappe.get_doc("Dyeing Paper Format", paper_format) if paper_format and paper_format != "自定义" else None
	is_custom = bool(preset) or template_type == "标签" or page_size == "自定义"
	if is_custom:
		paper_name = preset.paper_name if preset else str(paper_name or "").strip()
		if not paper_name:
			frappe.throw(_("自定义纸张格式名称不能为空"))
		custom_width, custom_height = ((float(preset.width_mm), float(preset.height_mm)) if preset else
			_requested_page_size(category, "自定义", width, height))
		presentation = _crispy_presentation("CUSTOM")
		presentation["page"].update({"width_mm": custom_width, "height_mm": custom_height,
			"custom_name": paper_name, "orientation": "landscape" if custom_width > custom_height else "portrait"})
		if preset:
			presentation["page"]["margins"] = {"top": float(preset.margin_top_mm or 0),
				"bottom": float(preset.margin_bottom_mm or 0), "left": float(preset.margin_left_mm or 0),
				"right": float(preset.margin_right_mm or 0)}
	else:
		custom_width = custom_height = None
		presentation = _crispy_presentation(page_size if page_size in {"A3", "A4", "A5", "Letter", "Legal", "Tabloid", "Executive"} else "A4")
	doc = frappe.get_doc({"doctype": "Crispy Format", "name": name, "crispy_format_type": "DocType", "doc_type": doc_type,
		"company": company, "module": "dyeing_finishing", "pdf_standard": "PDF 1.7",
		"layout_json": json.dumps(layout, ensure_ascii=False), "presentation_settings": json.dumps(presentation, ensure_ascii=False)})
	if is_custom:
		doc.typst_preamble = f'#set page(width: {custom_width:g}mm, height: {custom_height:g}mm, margin: 2mm)\n#set text(font: ("Noto Sans CJK SC", "Microsoft YaHei"), size: 8pt)'
	doc.insert()
	visual = _visual_from_crispy_layout(doc, layout)
	if is_custom:
		visual["page"]["paper_name"] = paper_name
	if preset:
		visual["page"].update({"grid_mm": float(preset.grid_mm or 1), "label_gap_mm": float(preset.label_gap_mm or 0),
			"margin_top_mm": float(preset.margin_top_mm or 0), "margin_bottom_mm": float(preset.margin_bottom_mm or 0),
			"margin_left_mm": float(preset.margin_left_mm or 0), "margin_right_mm": float(preset.margin_right_mm or 0)})
	layout["dyeing_visual"] = visual
	doc.db_set("layout_json", json.dumps(layout, ensure_ascii=False))
	return {"name": doc.name, "width_mm": visual["page"]["width_mm"], "height_mm": visual["page"]["height_mm"]}


@frappe.whitelist()
def duplicate_crispy_template(source_name, new_name):
	frappe.only_for("System Manager")
	name = (new_name or "").strip()
	if not name or frappe.db.exists("Crispy Format", name): frappe.throw(_("新模板名称为空或已存在"))
	source = frappe.get_doc("Crispy Format", source_name)
	doc = frappe.copy_doc(source)
	doc.name = name
	doc.is_default = 0
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist()
def get_printable_doctypes():
	frappe.only_for("System Manager")
	rows = frappe.get_all("DocType", filters={"istable": 0, "issingle": 0}, fields=["name", "module"], order_by="name")
	return [{"value": row.name, "label": _(row.name), "module": _(row.module)} for row in rows
		if row.module == "dyeing_finishing" or row.module in {"Selling", "Buying", "Stock", "Accounts", "CRM"}]


def _paper_format_dict(doc):
	return {"name": doc.name, "paper_name": doc.paper_name, "width_mm": float(doc.width_mm),
		"height_mm": float(doc.height_mm), "orientation": doc.orientation,
		"grid_mm": float(doc.grid_mm or 1), "label_gap_mm": float(doc.label_gap_mm or 0),
		"margin_top_mm": float(doc.margin_top_mm or 0), "margin_bottom_mm": float(doc.margin_bottom_mm or 0),
		"margin_left_mm": float(doc.margin_left_mm or 0), "margin_right_mm": float(doc.margin_right_mm or 0),
		"system_standard": cint(doc.system_standard)}


@frappe.whitelist()
def get_paper_formats():
	frappe.only_for("System Manager")
	from dyeing_finishing.dyeing_finishing.report_engine import ensure_standard_paper_formats
	ensure_standard_paper_formats()
	return [_paper_format_dict(frappe.get_doc("Dyeing Paper Format", name)) for name in
		frappe.get_all("Dyeing Paper Format", filters={"enabled": 1}, pluck="name", order_by="system_standard desc, paper_name asc")]


@frappe.whitelist()
def save_paper_format(paper_name, width_mm, height_mm, margin_top_mm=0, margin_bottom_mm=0,
		margin_left_mm=0, margin_right_mm=0, grid_mm=1, label_gap_mm=0):
	frappe.only_for("System Manager")
	name = str(paper_name or "").strip()
	if not name:
		frappe.throw(_("纸张格式名称不能为空"))
	if frappe.db.exists("Dyeing Paper Format", name):
		doc = frappe.get_doc("Dyeing Paper Format", name)
		if doc.system_standard:
			frappe.throw(_("系统预设纸张不能覆盖，请另存为新名称"))
	else:
		doc = frappe.new_doc("Dyeing Paper Format")
		doc.paper_name = name
	for key, value in {"width_mm": width_mm, "height_mm": height_mm, "margin_top_mm": margin_top_mm,
		"margin_bottom_mm": margin_bottom_mm, "margin_left_mm": margin_left_mm, "margin_right_mm": margin_right_mm,
		"grid_mm": grid_mm, "label_gap_mm": label_gap_mm}.items():
		doc.set(key, float(value or 0))
	doc.enabled = 1
	doc.save()
	return _paper_format_dict(doc)


@frappe.whitelist()
def get_visual_designer_data(crispy_format):
	frappe.only_for("System Manager")
	doc = frappe.get_doc("Crispy Format", crispy_format)
	meta = frappe.get_meta(doc.doc_type)
	layout = _json(doc.layout_json, {})
	visual = layout.get("dyeing_visual") or _visual_from_crispy_layout(doc, layout)
	_normalize_visual_layout(visual)
	groups = [{"key": "main", "label": "主表字段", "fields": _visual_fields(meta)}]
	for field in meta.fields:
		if field.fieldtype == "Table" and field.options:
			groups.append({"key": field.fieldname, "label": _(field.label or field.fieldname), "table_field": field.fieldname,
				"fields": _visual_fields(frappe.get_meta(field.options))})
	groups.append({"key": "system", "label": "打印信息", "fields": [
		{"fieldname": "__page", "label": "当前页", "fieldtype": "Data"},
		{"fieldname": "__pages", "label": "总页数", "fieldtype": "Data"},
		{"fieldname": "__print_date", "label": "打印日期", "fieldtype": "Date"},
	]})
	groups.append({"key": "company", "label": "公司资料", "fields": [
		{"fieldname": "__company_name", "label": "公司全称", "fieldtype": "Data"},
		{"fieldname": "__company_abbr", "label": "公司简称", "fieldtype": "Data"},
		{"fieldname": "__company_phone", "label": "公司电话", "fieldtype": "Data"},
	]})
	preview_doc = _latest_document(doc.doc_type)
	sample = frappe.get_doc(doc.doc_type, preview_doc).as_dict() if preview_doc else {}
	company_name = doc.company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
	if company_name:
		company = frappe.get_cached_doc("Company", company_name)
		sample.update({"__company_name": company.company_name or company.name, "__company_abbr": company.abbr or "",
			"__company_phone": company.get("phone_no") or ""})
	return {"name": doc.name, "doctype": doc.doc_type, "doctype_label": _(doc.doc_type), "visual": visual,
		"groups": groups, "preview_doc": preview_doc, "sample": sample, "paper_formats": get_paper_formats()}


@frappe.whitelist()
def save_visual_designer(crispy_format, visual):
	frappe.only_for("System Manager")
	doc = frappe.get_doc("Crispy Format", crispy_format)
	data = _json(visual, None)
	_normalize_visual_layout(data)
	_validate_visual_layout(doc.doc_type, data)
	layout = _json(doc.layout_json, {})
	layout.update({"schema_version": 4, "dyeing_visual": data})
	# Keep a simple reconstructable section for Crispy metadata and field discovery.
	layout["sections"] = _visual_crispy_sections(data)
	doc.layout_json = json.dumps(layout, ensure_ascii=False)
	doc.raw_typst = 1
	_ensure_visual_cjk_font()
	doc.typst_code = _visual_to_typst(data)
	presentation = _crispy_presentation("CUSTOM")
	presentation["page"].update({"width_mm": float(data["page"]["width_mm"]),
		"height_mm": float(data["page"]["height_mm"]), "orientation": data["page"].get("orientation") or "portrait",
		"custom_name": str(data["page"].get("paper_name") or "").strip(),
		"margins": {"top": float(data["page"].get("margin_top_mm") or 0),
			"bottom": float(data["page"].get("margin_bottom_mm") or 0),
			"left": float(data["page"].get("margin_left_mm") or 0),
			"right": float(data["page"].get("margin_right_mm") or 0)}})
	doc.presentation_settings = json.dumps(presentation, ensure_ascii=False)
	doc.save()
	from crispy_print.crispy_print.doctype.crispy_template.crispy_template import publish_crispy_template
	published = publish_crispy_template(source_crispy_format=doc.name, version_bump="minor",
		make_active=True, company=doc.company, notes="由可视化报表设计器保存并自动发布")
	return {"name": doc.name, "modified": doc.modified, "element_count": len(data.get("elements") or []),
		"published_template": published.get("name")}


@frappe.whitelist()
def initialize_visual_designer(crispy_format):
	"""Persist a legacy/Crispy layout in the visual schema without changing its visible field set."""
	frappe.only_for("System Manager")
	doc = frappe.get_doc("Crispy Format", crispy_format)
	layout = _json(doc.layout_json, {})
	visual = layout.get("dyeing_visual") or _visual_from_crispy_layout(doc, layout)
	return save_visual_designer(crispy_format, json.dumps(visual, ensure_ascii=False))


@frappe.whitelist()
def apply_blank_label_standard():
	"""Apply the approved 60x80 finished-product blank label grid."""
	frappe.only_for("System Manager")
	name = "成品空白标签 60×80mm"
	if not frappe.db.exists("Crispy Format", name):
		_ensure_crispy_pilots()
	# 80mm page minus 1.5mm top/bottom margins leaves 77mm; ten equal rows are 7.7mm each.
	x0, y0, row_h = 1.5, 1.5, 7.7
	label_w, value_w, right_label_w, right_value_w = 9.5, 19.0, 9.5, 19.0
	elements = []

	def cell(row, column_x, width, text=None, fieldname=None, bold=0, align="left", format_=None):
		item = {"id": frappe.generate_hash(length=10), "type": "field" if fieldname else "text",
			"x": column_x, "y": y0 + row * row_h, "w": width, "h": row_h, "font_size": 9,
			"bold": bold, "align": align, "border": 1, "show_label": 0}
		if fieldname: item.update({"fieldname": fieldname, "label": text or fieldname})
		else: item["text"] = text or ""
		if format_: item["format"] = format_
		elements.append(item)

	# 客户行：客户 | 客户编号（加宽） | 打印日期
	cell(0, x0, label_w, "客户", bold=1)
	cell(0, x0 + label_w, value_w + right_label_w, "客户编号", "customer")
	cell(0, x0 + label_w + value_w + right_label_w, right_value_w, "打印日期", "print_date", align="center", format_="date_dot")
	# 标准双列行
	for row, label, fieldname in (
		(1, "色号", "color_no"), (2, "缸号", "flow_card_no"), (3, "成份", "composition"),
		(4, "品名", "finished_product_name"), (5, "规格", "finished_specification"), (6, "颜色", "color"),
	):
		cell(row, x0, label_w, label, bold=1)
		cell(row, x0 + label_w, value_w + right_label_w + right_value_w, label, fieldname)
	# 匹号/净重与码数/毛重为留空手写格
	for row, left_label, right_label in ((7, "匹号", "净重"), (8, "码数", "毛重")):
		cell(row, x0, label_w, left_label, bold=1)
		cell(row, x0 + label_w, value_w, "")
		cell(row, x0 + label_w + value_w, right_label_w, right_label, bold=1)
		cell(row, x0 + label_w + value_w + right_label_w, right_value_w, "")
	cell(9, x0, label_w, "备注", bold=1)
	cell(9, x0 + label_w, value_w + right_label_w + right_value_w, "备注", "label_remarks")
	visual = {"version": 1, "copies_field": "print_quantity", "page": {"paper_name": "60×80mm标签纸", "width_mm": 60, "height_mm": 80, "margin_mm": 1.5,
		"margin_top_mm": 1.5, "margin_bottom_mm": 1.5, "margin_left_mm": 1.5, "margin_right_mm": 1.5,
		"label_gap_mm": 0, "grid_mm": 0.5, "orientation": "portrait"}, "snap": 1, "show_grid": 1, "elements": elements}
	frappe.db.set_value("Crispy Format", {"doc_type": "Finished Product Blank Label", "name": ["!=", name]}, "is_default", 0)
	frappe.db.set_value("Crispy Format", name, "is_default", 1)
	return save_visual_designer(name, json.dumps(visual, ensure_ascii=False))


@frappe.whitelist()
def apply_finished_delivery_standard():
	"""Create the editable 215 x 140 mm middle-cut finished delivery template."""
	frappe.only_for("System Manager")
	name = "成品出货单 215×140mm"
	company_name = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
	if not frappe.db.exists("Crispy Format", name):
		frappe.get_doc({"doctype": "Crispy Format", "name": name, "crispy_format_type": "DocType",
			"doc_type": "Finished Product Delivery", "company": company_name, "module": "dyeing_finishing",
			"is_default": 1, "default_print_language": "zh", "pdf_standard": "PDF 1.7",
			"layout_json": json.dumps({"schema_version": 4, "sections": []}, ensure_ascii=False),
			"presentation_settings": json.dumps(_crispy_presentation("CUSTOM"), ensure_ascii=False)}).insert(ignore_permissions=True)

	elements = []

	def text(value, x, y, w, h, size=9, bold=0, align="left", border=0):
		elements.append({"id": frappe.generate_hash(length=10), "type": "text", "text": value,
			"x": x, "y": y, "w": w, "h": h, "font_size": size, "bold": bold, "align": align,
			"border": border, "show_label": 0})

	def field(fieldname, label, x, y, w, h, size=8, align="left", border=0, format_=None):
		item = {"id": frappe.generate_hash(length=10), "type": "field", "fieldname": fieldname,
			"label": label, "x": x, "y": y, "w": w, "h": h, "font_size": size, "bold": 0,
			"align": align, "border": border, "show_label": 0}
		if format_:
			item["format"] = format_
		elements.append(item)

	# Company heading and document identity.
	field("__company_name", "公司名称", 5, 2, 205, 8, 15, "center")
	text("成品发货明细表", 65, 12, 85, 8, 13, 1, "center")
	text("单号：", 150, 13, 17, 6, 8, 1, "right")
	field("delivery_no", "出库单号", 167, 13, 43, 6, 8)
	text("出货日期：", 150, 20, 17, 6, 8, 1, "right")
	field("delivery_date", "出库日期", 167, 20, 43, 6, 8, "left", 0, "date_dot")

	# Two compact information rows.
	for value, x, w in (("客户名称：", 5, 23), ("品名：", 83, 16), ("规格：", 136, 16), ("布号：", 181, 16)):
		text(value, x, 28, w, 8, 8, 1, "left", 1)
	field("customer_name", "客户名称", 28, 28, 55, 8, 8, border=1)
	field("finished_product_name", "成品名称", 99, 28, 37, 8, 8, border=1)
	field("finished_specification", "成品规格", 152, 28, 29, 8, 8, border=1)
	field("finished_batch_no", "成品批次", 197, 28, 13, 8, 7, border=1)
	for value, x, w in (("缸号：", 5, 18), ("色号：", 63, 18), ("颜色：", 111, 18), ("加工项目：", 151, 25)):
		text(value, x, 36, w, 8, 8, 1, "left", 1)
	field("production_flow_card", "生产流转卡", 23, 36, 40, 8, 8, border=1)
	field("color_no", "色号", 81, 36, 30, 8, 8, border=1)
	field("color", "颜色", 129, 36, 22, 8, 8, border=1)
	field("remarks", "加工项目", 176, 36, 34, 8, 8, border=1)

	# 32 pieces: four horizontal groups, eight rows per group.
	elements.append({"id": frappe.generate_hash(length=10), "type": "table", "fieldname": "items",
		"label": "成品出库明细", "x": 5, "y": 44, "w": 205, "h": 59, "font_size": 7.5,
		"bold": 0, "align": "center", "border": 0, "show_label": 0, "repeat_columns": 4,
		"rows_per_group": 8, "fill_height": 1, "columns": [
			{"fieldname": "piece_no", "label": "匹号"}, {"fieldname": "weight", "label": "重量"},
			{"fieldname": "yard_qty", "label": "码数"},
		]})

	text("总计：", 5, 103, 20, 8, 9, 1, "center", 1)
	field("total_roll_count", "总匹数", 25, 103, 28, 8, 9, "center", 1)
	text("匹", 53, 103, 10, 8, 8, 0, "center", 1)
	field("total_weight", "总重量", 63, 103, 35, 8, 9, "right", 1)
	text("Kg", 98, 103, 12, 8, 8, 0, "center", 1)
	field("total_yard_qty", "总码数", 110, 103, 35, 8, 9, "right", 1)
	text("码", 145, 103, 10, 8, 8, 0, "center", 1)
	text("签收人：", 155, 103, 25, 8, 9, 1, "left", 1)
	field("receiver", "收货人", 180, 103, 30, 8, 9, border=1)

	for label, fieldname, x, y, w in (
		("送货人：", "last_printed_by", 5, 111, 60), ("联系电话：", "contact_phone", 65, 111, 45),
		("车牌号：", "vehicle_no", 5, 119, 60), ("送货地址：", "delivery_address", 65, 119, 45),
	):
		text(label, x, y, 22, 8, 8, 1, "left", 1)
		if fieldname == "last_printed_by":
			text("", x + 22, y, w - 22, 8, 8, 0, "left", 1)
		else:
			field(fieldname, label, x + 22, y, w - 22, 8, 8, border=1)
	text("备注：", 110, 111, 18, 16, 8, 1, "left", 1)
	field("remarks", "出库备注", 128, 111, 82, 16, 8, border=1)
	text("注意：请收货时核对匹数、重量和码数，如有异议请及时联系。", 5, 129, 170, 7, 7, 0, "left")
	field("__page", "当前页", 175, 129, 10, 7, 7, "right")
	text("页 / 共", 185, 129, 12, 7, 7, 0, "center")
	field("__pages", "总页数", 197, 129, 8, 7, 7, "center")
	text("页", 205, 129, 5, 7, 7)

	visual = {"version": 1, "page": {"paper_name": "中一刀", "width_mm": 215, "height_mm": 140, "margin_mm": 5,
		"margin_top_mm": 2, "margin_bottom_mm": 2, "margin_left_mm": 5, "margin_right_mm": 5,
		"label_gap_mm": 0, "grid_mm": 1, "orientation": "landscape"},
		"snap": 1, "show_grid": 1, "elements": elements}
	frappe.db.set_value("Crispy Format", {"doc_type": "Finished Product Delivery", "name": ["!=", name]}, "is_default", 0)
	frappe.db.set_value("Crispy Format", name, "is_default", 1)
	return save_visual_designer(name, json.dumps(visual, ensure_ascii=False))


@frappe.whitelist()
def ensure_active_print_template(crispy_format):
	"""Publish the latest visual format snapshot when preview has no current active template."""
	frappe.only_for("System Manager")
	format_doc = frappe.get_doc("Crispy Format", crispy_format)
	active = frappe.get_all("Crispy Template", filters={"source_crispy_format": format_doc.name,
		"is_active": 1, "status": "Approved"}, fields=["name", "creation", "modified"], order_by="creation desc", limit=1)
	if active and max(active[0].creation, active[0].modified) >= format_doc.modified:
		return {"name": active[0].name, "published": False}
	from crispy_print.crispy_print.doctype.crispy_template.crispy_template import publish_crispy_template
	result = publish_crispy_template(source_crispy_format=format_doc.name, version_bump="minor",
		make_active=True, company=format_doc.company, notes="由报表设计中心自动发布")
	result["published"] = True
	return result


@frappe.whitelist()
def backfill_print_company_context():
	"""Keep existing pilot documents compatible with company-scoped Crispy templates."""
	frappe.only_for("System Manager")
	default_company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	flow_cards = frappe.get_all("Production Flow Card", filters=[["company", "is", "not set"]], fields=["name", "sales_order"])
	for row in flow_cards:
		company = frappe.db.get_value("Dyeing Sales Order", row.sales_order, "company") if row.sales_order else None
		frappe.db.set_value("Production Flow Card", row.name, "company", company or default_company, update_modified=False)
	labels = frappe.get_all("Finished Product Blank Label", filters=[["company", "is", "not set"]], fields=["name", "production_flow_card"])
	for row in labels:
		company = frappe.db.get_value("Production Flow Card", row.production_flow_card, "company") if row.production_flow_card else None
		frappe.db.set_value("Finished Product Blank Label", row.name, "company", company or default_company, update_modified=False)
	return {"flow_cards": len(flow_cards), "labels": len(labels), "company": default_company}


def _visual_fields(meta):
	return [{"fieldname": f.fieldname, "label": _(f.label or f.fieldname), "fieldtype": f.fieldtype,
		"options": f.options or ""} for f in meta.fields if f.fieldname and f.fieldtype not in
		{"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Table", "Table MultiSelect"} and not f.hidden]


def _default_visual_source_layout(doctype, title):
	"""Build an editable starting layout for a Crispy format with no saved layout.

	Older/externally-created Crispy formats may contain only Typst code or even an
	empty layout.  Returning a title-only canvas made those formats appear to be
	non-editable in our visual designer.  Use the DocType metadata as a safe,
	reconstructable starting point and include the first child table as well.
	"""
	meta = frappe.get_meta(doctype)
	fields = []
	for field in meta.fields:
		if not field.fieldname or field.hidden or field.print_hide:
			continue
		if field.fieldtype in {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Table MultiSelect"}:
			continue
		if field.fieldtype == "Table":
			continue
		fields.append({"fieldname": field.fieldname, "label": _(field.label or field.fieldname),
			"fieldtype": field.fieldtype, "align": "end" if field.fieldtype in {"Int", "Float", "Currency", "Percent"} else "auto"})
		if len([field for field in fields if field.get("fieldtype") != "Table"]) >= 12:
			break
	for field in meta.fields:
		if field.fieldtype != "Table" or not field.fieldname or not field.options or field.hidden or field.print_hide:
			continue
		child_fields = _visual_fields(frappe.get_meta(field.options))[:8]
		fields.append({"fieldname": field.fieldname, "label": _(field.label or field.fieldname),
			"fieldtype": "Table", "columns": [{"fieldname": child["fieldname"], "label": child["label"]}
				for child in child_fields]})
		break
	return {"schema_version": 4, "sections": [{"id": "visual-default", "label": title,
		"columns": [{"id": "visual-default-fields", "width": 1, "fields": fields}]}]}


def _visual_from_crispy_layout(doc, layout):
	if not layout.get("sections"):
		layout = _default_visual_source_layout(doc.doc_type, doc.name)
	presentation = _json(doc.presentation_settings, {})
	page_settings = presentation.get("page") or {}
	page_sizes = {"A3": (297, 420), "A4": (210, 297), "A5": (148, 210), "Letter": (215.9, 279.4),
		"Legal": (215.9, 355.6), "Tabloid": (279.4, 431.8), "Executive": (184.15, 266.7)}
	width, height = page_sizes.get(page_settings.get("size"), (210, 297))
	# Raw Typst formats often carry the authoritative custom label size.
	page_source = "\n".join(filter(None, (doc.typst_preamble, doc.typst_code)))
	custom_size = re.search(r"#set\s+page\s*\([^)]*?width\s*:\s*([0-9.]+)mm\s*,\s*height\s*:\s*([0-9.]+)mm", page_source, re.S)
	if custom_size:
		width, height = float(custom_size.group(1)), float(custom_size.group(2))
	if page_settings.get("orientation") == "landscape":
		width, height = max(width, height), min(width, height)
	margins = page_settings.get("margins") or {}
	margin = float(margins.get("left", 2 if max(width, height) <= 120 else 10) or 0)
	is_label = max(width, height) <= 120 or "标签" in doc.name
	page = {"paper_name": page_settings.get("custom_name") or "", "width_mm": width, "height_mm": height, "margin_mm": margin,
		"margin_top_mm": float(margins.get("top", margin) or 0),
		"margin_bottom_mm": float(margins.get("bottom", margin) or 0),
		"margin_left_mm": margin, "margin_right_mm": float(margins.get("right", margin) or 0),
		"label_gap_mm": 0, "grid_mm": 2 if is_label else 5,
		"orientation": "landscape" if width > height else "portrait"}
	elements, y = [], page["margin_mm"] + (8 if is_label else 12)
	elements.append({"id": frappe.generate_hash(length=10), "type": "text", "x": page["margin_mm"], "y": page["margin_mm"],
		"w": page["width_mm"] - 2 * page["margin_mm"], "h": 8, "text": doc.name,
		"font_size": 14 if is_label else 18, "bold": 1, "align": "center", "border": 0})
	for section in layout.get("sections") or []:
		for column in section.get("columns") or []:
			for field in column.get("fields") or []:
				if field.get("fieldtype") == "Table":
					elements.append({"id": frappe.generate_hash(length=10), "type": "table", "x": page["margin_mm"], "y": y,
						"w": page["width_mm"] - 2 * page["margin_mm"], "h": 42, "fieldname": field.get("fieldname"),
						"label": field.get("label") or field.get("fieldname"), "columns": field.get("columns") or [], "font_size": 8, "border": 1})
					y += 45
					continue
				width = page["width_mm"] - 2 * page["margin_mm"] if is_label else 90
				elements.append({"id": frappe.generate_hash(length=10), "type": "field", "x": page["margin_mm"], "y": y,
					"w": width, "h": 7, "fieldname": field.get("fieldname"), "label": field.get("label") or field.get("fieldname"),
					"font_size": 8 if is_label else 10, "bold": 0, "align": "left", "border": 1 if is_label else 0, "show_label": 1})
				y += 7 if is_label else 9
	return {"version": 1, "page": page, "snap": 1, "show_grid": 1, "elements": elements}


def _validate_visual_layout(doctype, data):
	if not isinstance(data, dict) or not isinstance(data.get("page"), dict) or not isinstance(data.get("elements"), list):
		frappe.throw(_("设计数据结构无效"))
	page = data["page"]
	for key in ("width_mm", "height_mm"):
		value = float(page.get(key) or 0)
		if value < 20 or value > 1000: frappe.throw(_("纸张尺寸无效：{0}").format(key))
	for key in ("margin_top_mm", "margin_bottom_mm", "margin_left_mm", "margin_right_mm", "label_gap_mm"):
		value = float(page.get(key) or 0)
		if value < 0 or value > 100: frappe.throw(_("页面设置无效：{0}").format(key))
	if float(page.get("margin_left_mm") or 0) + float(page.get("margin_right_mm") or 0) >= float(page.get("width_mm") or 0):
		frappe.throw(_("左右边距不能大于纸张宽度"))
	if float(page.get("margin_top_mm") or 0) + float(page.get("margin_bottom_mm") or 0) >= float(page.get("height_mm") or 0):
		frappe.throw(_("上下边距不能大于纸张高度"))
	meta = frappe.get_meta(doctype)
	for index, item in enumerate(data["elements"], 1):
		if item.get("type") not in {"text", "field", "rect", "line", "vline", "grid", "barcode", "qrcode", "calculated", "table"}:
			frappe.throw(_("第 {0} 个组件类型无效").format(index))
		for key in ("x", "y", "w", "h"):
			try: float(item.get(key) or 0)
			except (TypeError, ValueError): frappe.throw(_("第 {0} 个组件的 {1} 无效").format(index, key))
		if item.get("type") in {"field", "barcode", "qrcode", "table", "calculated"} and not str(item.get("fieldname") or "").startswith("__") and not meta.get_field(item.get("fieldname")):
			frappe.throw(_("第 {0} 个组件引用了不存在的字段：{1}").format(index, item.get("fieldname")))
		if item.get("type") == "qrcode":
			if item.get("error_correction", "m") not in {"l", "m", "q", "h"}:
				frappe.throw(_("第 {0} 个二维码的纠错等级无效").format(index))
			if not 0 <= cint(item.get("quiet_zone", 4)) <= 16:
				frappe.throw(_("第 {0} 个二维码的留白应在 0 至 16 之间").format(index))
		if item.get("type") == "barcode":
			if item.get("barcode_type", "code128") != "code128":
				frappe.throw(_("第 {0} 个条码类型暂不支持").format(index))
			if not 0 <= cint(item.get("quiet_zone", 10)) <= 50:
				frappe.throw(_("第 {0} 个条码的留白应在 0 至 50 之间").format(index))
		if item.get("type") == "calculated":
			calc_type = item.get("calc_type") or "rmb_upper"
			if calc_type not in {"rmb_upper", "table_sum", "table_avg", "table_count", "table_min", "table_max"}:
				frappe.throw(_("第 {0} 个计算字段的计算方式无效").format(index))
			if calc_type.startswith("table_"):
				table_field = meta.get_field(item.get("fieldname"))
				child_meta = frappe.get_meta(table_field.options) if table_field and table_field.fieldtype == "Table" and table_field.options else None
				if not child_meta or (calc_type != "table_count" and not child_meta.get_field(item.get("column_field"))):
					frappe.throw(_("第 {0} 个计算字段的明细数据源无效").format(index))
		if item.get("type") in {"line", "vline", "grid"}:
			line_width = float(item.get("line_width") or .5)
			if line_width < .1 or line_width > 10:
				frappe.throw(_("第 {0} 个组件的线宽应在 0.1 至 10 pt 之间").format(index))
			if not re.fullmatch(r"#[0-9A-Fa-f]{6}", item.get("line_color") or "#000000"):
				frappe.throw(_("第 {0} 个组件的线条颜色无效").format(index))
		if item.get("type") == "grid":
			rows, cols = cint(item.get("rows")), cint(item.get("cols"))
			if not 1 <= rows <= 100 or not 1 <= cols <= 50:
				frappe.throw(_("第 {0} 个静态表格的行列数无效").format(index))
		if item.get("type") == "table" and item.get("repeat_columns"):
			groups, rows = cint(item.get("repeat_columns")), cint(item.get("rows_per_group"))
			if not 1 <= groups <= 8 or not 1 <= rows <= 100:
				frappe.throw(_("第 {0} 个明细表的分组数或每组行数无效").format(index))
		if item.get("type") == "table":
			if item.get("row_height_mode", "fill") not in {"auto", "fixed", "fill"}:
				frappe.throw(_("第 {0} 个明细表的行高模式无效").format(index))
			for height_key, height_label in (("header_row_height_mm", "表头行高"), ("detail_row_height_mm", "明细行高"), ("summary_row_height_mm", "汇总行高")):
				height_value = float(item.get(height_key) or 0)
				if height_value < 2 or height_value > 100:
					frappe.throw(_("第 {0} 个明细表的{1}应在 2 至 100 mm 之间").format(index, height_label))
			if not 1 <= cint(item.get("rows_per_page") or item.get("rows_per_group") or 8) <= 500:
				frappe.throw(_("第 {0} 个明细表的每页行数应在 1 至 500 之间").format(index))
			if item.get("overflow", "shrink") not in {"wrap", "clip", "shrink"}:
				frappe.throw(_("第 {0} 个明细表的内容超出处理无效").format(index))
			table_field = meta.get_field(item.get("fieldname"))
			child_meta = frappe.get_meta(table_field.options) if table_field and table_field.fieldtype == "Table" and table_field.options else None
			if not child_meta:
				frappe.throw(_("第 {0} 个明细表数据源无效：{1}").format(index, item.get("fieldname")))
			if not item.get("columns"):
				frappe.throw(_("第 {0} 个明细表至少需要一个显示列").format(index))
			for column_index, column in enumerate(item.get("columns") or [], 1):
				if not child_meta.get_field(column.get("fieldname")):
					frappe.throw(_("第 {0} 个明细表的第 {1} 列引用了不存在的字段：{2}").format(index, column_index, column.get("fieldname")))
				width = float(column.get("width_mm") or 0)
				if width < 0 or width > float(item.get("w") or 0):
					frappe.throw(_("第 {0} 个明细表的第 {1} 列宽度无效").format(index, column_index))
				if column.get("align", "center") not in {"left", "center", "right"}:
					frappe.throw(_("第 {0} 个明细表的第 {1} 列对齐方式无效").format(index, column_index))
				if column.get("aggregate", "none") not in {"none", "sum", "count", "avg"}:
					frappe.throw(_("第 {0} 个明细表的第 {1} 列汇总方式无效").format(index, column_index))


def _normalize_visual_layout(data):
	"""Upgrade legacy visual values in memory before validation and publishing."""
	if not isinstance(data, dict):
		return data
	alignments = {"start": "left", "end": "right", "auto": "left"}
	for item in data.get("elements") or []:
		if item.get("align") in alignments:
			item["align"] = alignments[item["align"]]
		if item.get("type") == "qrcode":
			item.setdefault("error_correction", "m")
			item.setdefault("quiet_zone", 4)
		if item.get("type") == "barcode":
			item.setdefault("barcode_type", "code128")
			item.setdefault("show_barcode_text", 1)
			item.setdefault("quiet_zone", 10)
		if item.get("type") != "table":
			continue
		item.setdefault("row_height_mode", "fill" if cint(item.get("fill_height", 1)) else "auto")
		item.setdefault("header_row_height_mm", 7)
		item.setdefault("detail_row_height_mm", 7)
		item.setdefault("summary_row_height_mm", 7)
		item.setdefault("rows_per_page", cint(item.get("rows_per_group") or 8))
		item.setdefault("repeat_header", 1)
		item.setdefault("fill_blank_rows", cint(item.get("fill_height", 1)))
		item.setdefault("overflow", "shrink")
		for column in item.get("columns") or []:
			column["align"] = alignments.get(column.get("align"), column.get("align") or "center")
			column.setdefault("width_mm", 0)
			column.setdefault("aggregate", "none")
	return data


def _visual_crispy_sections(data):
	fields = []
	for item in data.get("elements") or []:
		if item.get("type") in {"field", "barcode", "qrcode", "table", "calculated"} and item.get("fieldname"):
			field = {"fieldname": item["fieldname"], "label": item.get("label") or item["fieldname"], "fieldtype": "Table" if item["type"] == "table" else "Data", "align": "auto"}
			if item["type"] == "table": field["columns"] = item.get("columns") or []
			fields.append(field)
	return [{"id": "visual-fields", "label": "可视化设计", "columns": [{"id": "visual-fields-main", "width": 1, "fields": fields}]}]


def _typst_text(value):
	return str(value or "").replace("\\", "\\\\").replace('"', '\\"').replace("#", "\\#").replace("[", "\\[").replace("]", "\\]")


def _visual_to_typst(data):
	page = data["page"]
	# Crispy Print deliberately requests only fields it can detect in raw Typst.
	# Our generated templates access values through val()/doc.at(), which its
	# extractor cannot infer.  Keep an explicit hint in the generated source so
	# preview and print receive the real document values instead of only the
	# mandatory name/doctype fields.
	required_fields = set()
	for item in data.get("elements") or []:
		fieldname = str(item.get("fieldname") or "").strip()
		if not fieldname or fieldname.startswith("__"):
			continue
		required_fields.add(fieldname)
		if item.get("type") == "table":
			for column in item.get("columns") or []:
				column_field = str(column.get("fieldname") or "").strip()
				if column_field:
					required_fields.add(f"{fieldname}.{column_field}")
		if item.get("type") == "calculated" and str(item.get("calc_type") or "").startswith("table_"):
			column_field = str(item.get("column_field") or "").strip()
			if column_field:
				required_fields.add(f"{fieldname}.{column_field}")
	copies_field = str(data.get("copies_field") or "").strip()
	if copies_field:
		required_fields.add(copies_field)
	field_hint = "// fields: " + ", ".join(sorted(required_fields))
	lines = [field_hint,
		f'#set page(width: {float(page["width_mm"]):g}mm, height: {float(page["height_mm"]):g}mm, margin: 0mm)',
		'#set text(font: ("WenQuanYi Zen Hei", "Unifont"), size: 9pt)',
		'#import "@local/crispy-print:0.1.0": crispy-qrcode',
		'#let val(key) = doc.at(key, default: "")',
		'''#let rmb-group(number) = {
  let digits = ("零", "壹", "贰", "叁", "肆", "伍", "陆", "柒", "捌", "玖")
  let units = ("仟", "佰", "拾", "")
  let divisors = (1000, 100, 10, 1)
  let result = ""
  let pending-zero = false
  for index in range(4) {
    let digit = calc.rem(calc.floor(number / divisors.at(index)), 10)
    if digit == 0 {
      if result != "" { pending-zero = true }
    } else {
      if pending-zero { result += "零"; pending-zero = false }
      result += digits.at(digit) + units.at(index)
    }
  }
  result
}''',
		'''#let rmb-upper(value, prefix: true, empty-as-zero: false) = {
  if value == none or str(value).trim() == "" {
    if empty-as-zero { "人民币零元整" } else { "" }
  } else {
    let amount = float(str(value))
    let cents = int(calc.round(calc.abs(amount) * 100))
    let integer = calc.floor(cents / 100)
    let fraction = calc.rem(cents, 100)
    let groups = (
      calc.rem(integer, 10000),
      calc.rem(calc.floor(integer / 10000), 10000),
      calc.rem(calc.floor(integer / 100000000), 10000),
      calc.rem(calc.floor(integer / 1000000000000), 10000),
    )
    let group-units = ("", "万", "亿", "万亿")
    let result = ""
    let pending-zero = false
    for index in (3, 2, 1, 0) {
      let group = groups.at(index)
      if group == 0 {
        if result != "" { pending-zero = true }
      } else {
        if result != "" and (pending-zero or group < 1000) { result += "零" }
        result += rmb-group(group) + group-units.at(index)
        pending-zero = false
      }
    }
    if result == "" { result = "零" }
    result += "元"
    let jiao = calc.floor(fraction / 10)
    let fen = calc.rem(fraction, 10)
    let digits = ("零", "壹", "贰", "叁", "肆", "伍", "陆", "柒", "捌", "玖")
    if jiao == 0 and fen == 0 { result += "整" }
    else {
      if jiao > 0 { result += digits.at(jiao) + "角" }
      else if integer > 0 and fen > 0 { result += "零" }
      if fen > 0 { result += digits.at(fen) + "分" }
    }
    (if amount < 0 { "负" } else { "" }) + (if prefix { "人民币" } else { "" }) + result
  }
}''',
		'''#let code128(data, width: 50mm, height: 10mm, quiet-zone: 10, show-text: true) = {
  let patterns = (
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213", "221312", "231212",
    "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132", "221231", "213212", "223112", "312131",
    "311222", "321122", "321221", "312212", "322112", "322211", "212123", "212321", "232121", "111323", "131123", "131321",
    "112313", "132113", "132311", "211313", "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121",
    "313121", "211331", "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214", "112412", "122114",
    "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111", "111242", "121142", "121241", "114212",
    "124112", "124211", "411212", "421112", "421211", "212141", "214121", "412121", "111143", "111341", "131141", "114113",
    "114311", "411113", "411311", "113141", "114131", "311141", "411131", "211412", "211214", "211232", "2331112",
  )
  let charset = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
  let values = str(data).clusters().map(character => {
    let position = charset.clusters().position(item => item == character)
    if position == none { 31 } else { position }
  })
  let checksum = 104
  for pair in values.enumerate() { checksum += pair.at(1) * (pair.at(0) + 1) }
  let codes = (104,) + values + (calc.rem(checksum, 103), 106)
  let total-units = quiet-zone * 2
  for code in codes { for digit in patterns.at(code).clusters() { total-units += int(digit) } }
  let module = width / total-units
  let widths = (quiet-zone * module,)
  let cells = ([],)
  for code in codes {
    for pair in patterns.at(code).clusters().enumerate() {
      widths.push(int(pair.at(1)) * module)
      cells.push(if calc.rem(pair.at(0), 2) == 0 { rect(width: 100%, height: 100%, fill: black, stroke: none) } else { [] })
    }
  }
  widths.push(quiet-zone * module); cells.push([])
  stack(dir: ttb, spacing: 1pt,
    grid(columns: widths, rows: (height,), gutter: 0pt, ..cells),
    if show-text { align(center, text(size: 7pt, str(data))) } else { [] },
  )
}''']
	for item in sorted(data.get("elements") or [], key=lambda row: (int(row.get("z") or 0), row.get("id") or "")):
		type_ = item.get("type"); x = float(item.get("x") or 0); y = float(item.get("y") or 0)
		w = max(float(item.get("w") or 1), .5); h = max(float(item.get("h") or 1), .5)
		font = max(float(item.get("font_size") or 9), 4); align = {"left": "left", "center": "center", "right": "right"}.get(item.get("align"), "left")
		line_width = min(max(float(item.get("line_width") or .5), .1), 10)
		line_color = item.get("line_color") if re.fullmatch(r"#[0-9A-Fa-f]{6}", item.get("line_color") or "") else "#000000"
		line_stroke = f'(paint: rgb("{line_color}"), thickness: {line_width:g}pt)'
		stroke = "0.5pt" if cint(item.get("border")) else "none"
		if type_ == "rect": content = ""
		elif type_ == "line":
			lines.append(f'#place(dx: {x:g}mm, dy: {y:g}mm, line(length: {w:g}mm, stroke: {line_stroke}))'); continue
		elif type_ == "vline":
			lines.append(f'#place(dx: {x:g}mm, dy: {y:g}mm, line(end: (0mm, {h:g}mm), stroke: {line_stroke}))'); continue
		elif type_ == "grid":
			rows, cols = max(cint(item.get("rows")), 1), max(cint(item.get("cols")), 1)
			col_size, row_size = w / cols, h / rows
			columns = ", ".join([f"{col_size:g}mm"] * cols)
			row_sizes = ", ".join([f"{row_size:g}mm"] * rows)
			lines.append(f'#place(dx: {x:g}mm, dy: {y:g}mm, grid(columns: ({columns}), rows: ({row_sizes}), stroke: {line_stroke}, ..range({rows * cols}).map(_ => [])))'); continue
		elif type_ == "text": content = _typst_text(item.get("text"))
		elif type_ == "barcode": content = f'#text(font: "Libre Barcode 39", size: {font:g}pt)[#val("{_typst_text(item.get("fieldname"))}")]'
		elif type_ == "table":
			cols = item.get("columns") or []
			if not cols: content = _typst_text(item.get("label") or "明细表")
			elif cint(item.get("repeat_columns")) > 1:
				groups = min(max(cint(item.get("repeat_columns")), 1), 8)
				rows_per_group = min(max(cint(item.get("rows_per_group")), 1), 100)
				fill_height = cint(item.get("fill_height", 1))
				fieldname = _typst_text(item.get("fieldname"))
				column_widths = []
				for _group in range(groups):
					column_widths.extend([f'{float(col.get("width_mm")):g}mm' if float(col.get("width_mm") or 0) > 0 else "1fr" for col in cols])
				head = ", ".join(f'[#align({col.get("align") if col.get("align") in {"left", "center", "right"} else "center"})[{_typst_text(col.get("label") or col.get("fieldname"))}]]'
					for _group in range(groups) for col in cols)
				cells = ", ".join(
					f'[#align({col.get("align") if col.get("align") in {"left", "center", "right"} else "center"})['
					f'#if group * {rows_per_group} + row-index < val("{fieldname}").len() '
					f'{{ val("{fieldname}").at(group * {rows_per_group} + row-index).at("{_typst_text(col.get("fieldname"))}", default: "") }}]]'
					for col in cols
				)
				available_height = max(h - 2, 1)
				row_height = available_height / (rows_per_group + 1)
				row_sizes = f', rows: ({", ".join([f"{row_height:g}mm"] * (rows_per_group + 1))})' if fill_height else ""
				content = (f'#table(columns: ({", ".join(column_widths)}){row_sizes}, stroke: 0.5pt, inset: 2pt, '
					f'table.header({head}), ..range({rows_per_group}).map(row-index => '
					f'range({groups}).map(group => ({cells})).flatten()).flatten())')
			else:
				column_widths = [f'{float(col.get("width_mm")):g}mm' if float(col.get("width_mm") or 0) > 0 else "1fr" for col in cols]
				head = ", ".join(f'[#align({col.get("align") if col.get("align") in {"left", "center", "right"} else "center"})[{_typst_text(col.get("label") or col.get("fieldname"))}]]' for col in cols)
				cells = ", ".join(f'[#align({col.get("align") if col.get("align") in {"left", "center", "right"} else "center"})[#row.at("{_typst_text(col.get("fieldname"))}", default: "")]]' for col in cols)
				footer_cells = []
				for col in cols:
					mode = col.get("aggregate") or "none"
					field = _typst_text(col.get("fieldname"))
					if mode == "count": aggregate = f'计数：#val("{_typst_text(item.get("fieldname"))}").len()'
					elif mode in {"sum", "avg"}:
						values = f'val("{_typst_text(item.get("fieldname"))}").map(row => row.at("{field}", default: 0))'
						aggregate = f'{"平均" if mode == "avg" else "合计"}：#{values}.sum()'
						if mode == "avg": aggregate = f'平均：#if {values}.len() > 0 {{ {values}.sum() / {values}.len() }} else {{ 0 }}'
					else: aggregate = ""
					footer_cells.append(f'[#align({col.get("align") if col.get("align") in {"left", "center", "right"} else "center"})[#text(weight: "bold")[{aggregate}]]]')
				footer = f', table.footer({", ".join(footer_cells)})' if any((col.get("aggregate") or "none") != "none" for col in cols) else ""
				content = f'#table(columns: ({", ".join(column_widths)}), table.header({head}), ..val("{_typst_text(item.get("fieldname"))}").map(row => ({cells})).flatten(){footer})'
		else:
			label = _typst_text(item.get("label") or item.get("fieldname"))
			fieldname = item.get("fieldname") or ""
			if fieldname == "__page": value = '#context counter(page).get().first()'
			elif fieldname == "__pages": value = '#context counter(page).final().first()'
			elif fieldname == "__print_date": value = '#datetime.today().display("[year]-[month]-[day]")'
			elif fieldname.startswith("__company_"):
				company_name = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
				company = frappe.get_cached_doc("Company", company_name) if company_name else frappe._dict()
				company_values = {"__company_name": company.get("company_name") or company_name or "", "__company_abbr": company.get("abbr") or "", "__company_phone": company.get("phone_no") or ""}
				value = _typst_text(company_values.get(fieldname))
			elif item.get("format") == "date_dot": value = f'#str(val("{_typst_text(fieldname)}")).replace("-", ".")'
			else: value = f'#val("{_typst_text(fieldname)}")'
			content = (f'#text(weight: "bold")[{label}]  ' if cint(item.get("show_label", 1)) else "") + value
		weight = 'weight: "bold", ' if cint(item.get("bold")) else ""
		lines.append(f'#place(dx: {x:g}mm, dy: {y:g}mm, box(width: {w:g}mm, height: {h:g}mm, stroke: {stroke}, inset: 1mm)[#align({align})[#text({weight}size: {font:g}pt)[{content}]]])')
	if copies_field:
		body = lines[4:]
		lines = lines[:4] + [
			f'#let copies = calc.max(1, int(str(doc.at("{_typst_text(copies_field)}", default: 1))))',
			'#let render-copy() = [', *body, ']',
			'#for copy-number in range(copies) [',
			'  #render-copy()',
			'  #if copy-number < copies - 1 [#pagebreak()]',
			']',
		]
	return "\n".join(lines)



def _json(value, default):
	try:
		return json.loads(value or json.dumps(default))
	except (TypeError, ValueError):
		return default


def _latest_document(doctype):
	try:
		rows = frappe.get_all(doctype, fields=["name"], order_by="modified desc", limit=1)
		return rows[0].name if rows else ""
	except Exception:
		return ""


def _requested_page_size(template_type, page_size, width, height):
	if template_type == "标签" or page_size == "自定义":
		width, height = float(width or 60), float(height or 80)
		if width <= 0 or height <= 0 or width > 1000 or height > 1000:
			frappe.throw(_("纸张宽度和高度必须在 0–1000 mm 之间"))
		return width, height
	return {"A5": (148, 210), "A4横向": (297, 210)}.get(page_size, (210, 297))


import traceback

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


IMPACT_DOCTYPES = (
	("Warehouse", "仓库"), ("Account", "会计科目"), ("Cost Center", "成本中心"),
	("Sales Order", "销售订单"), ("Purchase Order", "采购订单"),
	("Sales Invoice", "销售发票"), ("Purchase Invoice", "采购发票"),
	("Stock Entry", "库存凭证"), ("Payment Entry", "付款凭证"),
	("Journal Entry", "日记账凭证"), ("Work Order", "工作单"), ("BOM", "BOM"),
)
ABBR_RENAME_DOCTYPES = (("Warehouse", "仓库"), ("Account", "会计科目"), ("Cost Center", "成本中心"))


class CompanyNameChange(Document):
	def validate(self):
		frappe.only_for("System Manager")
		self.new_company_name = (self.new_company_name or "").strip()
		self.new_company_abbr = (self.new_company_abbr or "").strip()
		previous = None if self.is_new() else self.get_doc_before_save()
		protected = ("old_company", "new_company_name", "abbr_handling", "new_company_abbr", "change_reason", "confirm_backup")
		if previous and previous.status not in ("草稿", "失败") and any(self.has_value_changed(fieldname) for fieldname in protected):
			frappe.throw(_("已进入执行流程的公司变更记录不允许修改"))
		if previous and any(self.has_value_changed(fieldname) for fieldname in ("old_company", "new_company_name", "abbr_handling", "new_company_abbr")):
			self.previewed_on = self.preview_company = self.preview_new_company_name = self.preview_new_company_abbr = None
		if self.old_company and not self.old_company_name_snapshot:
			self.old_company_name_snapshot = self.old_company
		if self.old_company:
			current_abbr = frappe.db.get_value("Company", self.old_company, "abbr")
			self.company_abbr = current_abbr
			self.old_company_abbr_snapshot = self.old_company_abbr_snapshot or current_abbr
		_validate_request(self)

	def on_trash(self):
		if self.status != "草稿":
			frappe.throw(_("已进入执行流程的公司变更记录不允许删除"))


def _validate_request(doc):
	if not doc.old_company or not frappe.db.exists("Company", doc.old_company):
		frappe.throw(_("请选择有效的当前公司"))
	if not doc.new_company_name:
		frappe.throw(_("请填写新公司名称"))
	if doc.old_company == doc.new_company_name:
		frappe.throw(_("新公司名称不能与当前公司相同"))
	if frappe.db.exists("Company", doc.new_company_name):
		frappe.throw(_("公司 {0} 已存在，不能重复命名").format(doc.new_company_name))
	if doc.abbr_handling == "同步修改简称":
		if not doc.new_company_abbr:
			frappe.throw(_("请填写新公司简称"))
		if doc.new_company_abbr == doc.company_abbr:
			frappe.throw(_("新公司简称不能与原简称相同"))
		if len(doc.new_company_abbr) > 10 or " - " in doc.new_company_abbr:
			frappe.throw(_("公司简称最长 10 个字符，且不能包含后缀分隔符“ - ”"))
		if frappe.db.exists("Company", {"abbr": doc.new_company_abbr, "name": ["!=", doc.old_company]}):
			frappe.throw(_("公司简称 {0} 已被其他公司使用").format(doc.new_company_abbr))


def _impact_rows(company):
	rows = []
	for doctype, label in IMPACT_DOCTYPES:
		if frappe.db.exists("DocType", doctype) and frappe.get_meta(doctype).has_field("company"):
			rows.append({"doctype": doctype, "label": label, "count": frappe.db.count(doctype, {"company": company})})
	return rows


def _abbr_rename_rows(company, old_abbr, new_abbr, new_company_name=None):
	rows, collisions = [], []
	old_suffix = f" - {old_abbr}"
	for doctype, label in ABBR_RENAME_DOCTYPES:
		for name in frappe.get_all(doctype, {"company": company, "name": ["like", f"%{old_suffix}"]}, pluck="name"):
			if not name.endswith(old_suffix):
				continue
			base_name = name[:-len(old_suffix)]
			if doctype == "Cost Center" and base_name == company and new_company_name:
				base_name = new_company_name
			target = f"{base_name} - {new_abbr}"
			row = {"doctype": doctype, "label": label, "old_name": name, "new_name": target}
			rows.append(row)
			if frappe.db.exists(doctype, target):
				collisions.append(row)
	return rows, collisions


@frappe.whitelist()
def preview_company_name_change(name):
	frappe.only_for("System Manager")
	doc = frappe.get_doc("Company Name Change", name)
	doc.check_permission("write")
	if doc.status not in ("草稿", "失败"):
		frappe.throw(_("只能预览草稿或失败状态的变更记录"))
	_validate_request(doc)
	rows = _impact_rows(doc.old_company)
	rename_rows, collisions = ([], [])
	if doc.abbr_handling == "同步修改简称":
		rename_rows, collisions = _abbr_rename_rows(doc.old_company, doc.company_abbr, doc.new_company_abbr, doc.new_company_name)
	frappe.db.set_value(doc.doctype, doc.name, {
		"previewed_on": now_datetime(), "preview_company": doc.old_company,
		"preview_new_company_name": doc.new_company_name,
		"preview_new_company_abbr": doc.new_company_abbr if doc.abbr_handling == "同步修改简称" else "",
	}, update_modified=False)
	return {"old_company": doc.old_company, "new_company_name": doc.new_company_name,
		"old_abbr": doc.company_abbr, "new_abbr": doc.new_company_abbr, "abbr_handling": doc.abbr_handling,
		"rows": rows, "rename_rows": rename_rows, "collisions": collisions}


@frappe.whitelist()
def execute_company_name_change(name):
	frappe.only_for("System Manager")
	doc = frappe.get_doc("Company Name Change", name)
	doc.check_permission("write")
	if doc.status not in ("草稿", "失败"):
		frappe.throw(_("该变更记录已进入执行流程，不能重复处理"))
	if not doc.confirm_backup:
		frappe.throw(_("请先确认已有可用的系统备份"))
	if not doc.previewed_on:
		frappe.throw(_("请先预览变更影响范围"))
	expected_abbr = doc.new_company_abbr if doc.abbr_handling == "同步修改简称" else ""
	if (doc.preview_company, doc.preview_new_company_name, doc.preview_new_company_abbr or "") != (doc.old_company, doc.new_company_name, expected_abbr):
		frappe.throw(_("公司名称或简称已变更，请重新预览"))
	_validate_request(doc)
	_, collisions = _abbr_rename_rows(doc.old_company, doc.company_abbr, doc.new_company_abbr, doc.new_company_name) if expected_abbr else ([], [])
	if collisions:
		frappe.throw(_("存在 {0} 个新简称名称冲突，请更换简称后重新预览").format(len(collisions)))
	frappe.db.set_value(doc.doctype, doc.name, {
		"status": "等待执行", "execution_error": "", "renamed_by": frappe.session.user,
	})
	frappe.enqueue(
		"dyeing_finishing.dyeing_finishing.doctype.company_name_change.company_name_change.run_company_name_change",
		queue="long", enqueue_after_commit=True, job_name=f"公司名称变更 {doc.name}", name=doc.name,
	)
	return {"queued": True, "name": doc.name}


def run_company_name_change(name):
	try:
		doc = frappe.get_doc("Company Name Change", name)
		if doc.status != "等待执行":
			return
		frappe.db.set_value(doc.doctype, doc.name, "status", "处理中")
		frappe.db.commit()
		old_company, new_company = doc.old_company, doc.new_company_name
		old_abbr = frappe.db.get_value("Company", old_company, "abbr")
		rename_rows = []
		if doc.abbr_handling == "同步修改简称":
			rename_rows, collisions = _abbr_rename_rows(old_company, old_abbr, doc.new_company_abbr, new_company)
			if collisions:
				frappe.throw(_("执行前检测到新简称名称冲突"))
		frappe.rename_doc("Company", old_company, new_company, force=True, merge=False)
		for row in rename_rows:
			frappe.rename_doc(row["doctype"], row["old_name"], row["new_name"], force=True, merge=False)
		if doc.abbr_handling == "同步修改简称":
			company = frappe.get_doc("Company", new_company)
			company.abbr = doc.new_company_abbr
			company.save(ignore_permissions=True)
		frappe.db.set_value(doc.doctype, doc.name, {
			"old_company_name_snapshot": old_company, "old_company_abbr_snapshot": old_abbr,
			"old_company": new_company, "company_abbr": doc.new_company_abbr or old_abbr,
			"status": "已完成", "renamed_by": doc.renamed_by, "renamed_on": now_datetime(), "execution_error": "",
		}, update_modified=True)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		error = traceback.format_exc()
		frappe.log_error(error, f"公司名称变更失败 {name}")
		frappe.db.set_value("Company Name Change", name, {"status": "失败", "execution_error": error[-4000:]})
		frappe.db.commit()
		raise

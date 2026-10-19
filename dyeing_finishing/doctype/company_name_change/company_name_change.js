/* eslint-disable */
frappe.ui.form.on("Company Name Change", {
  refresh(frm) {
    frm.set_intro("公司更名会更新 ERPNext 关联资料；同步修改简称时，还会重命名仓库、会计科目和成本中心后缀。执行前必须预览并确认备份。", "orange");
    if (["等待执行", "处理中"].includes(frm.doc.status)) {
      frm.dashboard.set_headline_alert("公司资料正在后台更新，期间请暂停库存和会计操作。", "orange");
      window.setTimeout(() => frm.reload_doc(), 4000);
      return;
    }
    if (frm.is_new() || frm.doc.status === "已完成") return;
    frm.add_custom_button("预览影响", () => preview_change(frm), "操作");
    frm.add_custom_button(frm.doc.status === "失败" ? "重新执行变更" : "确认变更公司资料", () => confirm_change(frm), "操作");
  },
  old_company(frm) {
    if (!frm.doc.old_company) return;
    frappe.db.get_value("Company", frm.doc.old_company, "abbr").then(({ message }) => {
      frm.set_value("company_abbr", message?.abbr || "");
      frm.set_value("old_company_name_snapshot", frm.doc.old_company);
      frm.set_value("old_company_abbr_snapshot", message?.abbr || "");
      clear_preview(frm);
    });
  },
  new_company_name: clear_preview,
  abbr_handling(frm) {
    if (frm.doc.abbr_handling === "保持原简称") frm.set_value("new_company_abbr", "");
    clear_preview(frm);
  },
  new_company_abbr: clear_preview,
});

function clear_preview(frm) {
  if (!frm.is_new()) frm.set_value("previewed_on", "");
}

function preview_change(frm) {
  if (frm.is_dirty()) { frappe.msgprint("请先保存当前内容，再预览影响范围。"); return; }
  frappe.call({
    method: "dyeing_finishing.dyeing_finishing.doctype.company_name_change.company_name_change.preview_company_name_change",
    args: { name: frm.doc.name }, freeze: true, freeze_message: "正在统计公司更名影响范围…",
  }).then(({ message }) => {
    const impactRows = (message.rows || []).filter(row => row.count).map(row => `<tr><td>${frappe.utils.escape_html(row.label)}</td><td class="text-right">${row.count}</td></tr>`).join("");
    const renameCounts = {};
    (message.rename_rows || []).forEach(row => { renameCounts[row.label] = (renameCounts[row.label] || 0) + 1; });
    const renameRows = Object.entries(renameCounts).map(([label, count]) => `<tr><td>${frappe.utils.escape_html(label)}后缀改名</td><td class="text-right">${count}</td></tr>`).join("");
    const abbreviation = message.abbr_handling === "同步修改简称"
      ? `<b>${frappe.utils.escape_html(message.old_abbr || "")}</b> → <b>${frappe.utils.escape_html(message.new_abbr || "")}</b>`
      : `<b>${frappe.utils.escape_html(message.old_abbr || "")}</b>（保持不变）`;
    const collision = (message.collisions || []).length
      ? `<div class="alert alert-danger">发现 ${message.collisions.length} 个新名称冲突，当前不能执行。请更换新简称后重新预览。</div>` : "";
    frappe.msgprint({ title: "公司资料变更预览", indicator: (message.collisions || []).length ? "red" : "orange", message: `
      ${collision}<p>公司：<b>${frappe.utils.escape_html(message.old_company)}</b> → <b>${frappe.utils.escape_html(message.new_company_name)}</b></p>
      <p>简称：${abbreviation}</p>
      <table class="table table-bordered"><thead><tr><th>影响资料</th><th class="text-right">记录数</th></tr></thead><tbody>${impactRows}${renameRows || ""}${impactRows || renameRows ? "" : "<tr><td colspan='2'>未找到已使用记录</td></tr>"}</tbody></table>` });
    frm.reload_doc();
  });
}

function confirm_change(frm) {
  if (frm.is_dirty()) { frappe.msgprint("当前内容尚未保存，请保存后重新预览。"); return; }
  if (!frm.doc.confirm_backup) { frappe.msgprint("请先勾选“已确认存在可用的系统备份”并保存。"); return; }
  if (!frm.doc.previewed_on) { frappe.msgprint("请先点击“预览影响”。"); return; }
  const label = frm.doc.abbr_handling === "同步修改简称"
    ? `请输入“${frm.doc.new_company_name} / ${frm.doc.new_company_abbr}”进行确认`
    : `请输入新公司名称“${frm.doc.new_company_name}”进行确认`;
  const expected = frm.doc.abbr_handling === "同步修改简称" ? `${frm.doc.new_company_name} / ${frm.doc.new_company_abbr}` : frm.doc.new_company_name;
  frappe.prompt([{ label, fieldname: "confirmation", fieldtype: "Data", reqd: 1 }], (values) => {
    if (values.confirmation.trim() !== expected.trim()) { frappe.msgprint("确认内容不一致，未执行变更。"); return; }
    frappe.call({ method: "dyeing_finishing.dyeing_finishing.doctype.company_name_change.company_name_change.execute_company_name_change", args: { name: frm.doc.name }, freeze: true, freeze_message: "正在提交后台变更任务…" }).then(() => {
      frappe.show_alert({ message: "变更任务已提交，请暂停相关库存和会计操作", indicator: "orange" }, 10);
      frm.reload_doc();
    });
  }, "最终确认", "提交后台变更");
}

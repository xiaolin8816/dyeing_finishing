const blankLabelMethod = "dyeing_finishing.dyeing_finishing.doctype.finished_product_blank_label.finished_product_blank_label";

frappe.ui.form.on("Finished Product Blank Label", {
 setup(frm) {
  frm.set_query("production_flow_card", () => ({filters: {docstatus: 1, production_status: ["!=", "已关闭"]}}));
 },
 refresh(frm) {
  if (frappe.user_roles.includes("System Manager")) {
   frm.add_custom_button("设计标签", () => {
    window.open(`/desk/dyeing-visual-report-designer/${encodeURIComponent("成品空白标签 60×80mm")}`, "_blank");
   }, "操作");
  }
  if (!frm.is_new() && frm.doc.print_status !== "已作废") {
   frm.add_custom_button("作废", () => frappe.confirm("确认作废这张空白标签打印单？", () => {
    frappe.call({method: `${blankLabelMethod}.void_blank_label_print`, args: {name: frm.doc.name}, freeze: true}).then(() => frm.reload_doc());
   }), "操作");
  }
 },
 production_flow_card(frm) {
  if (!frm.doc.production_flow_card) return;
  frappe.call({
   method: `${blankLabelMethod}.get_blank_label_flow_card_details`,
   args: {flow_card: frm.doc.production_flow_card},
   freeze: true,
   freeze_message: "正在带出生产流转卡资料…",
  }).then(({message}) => {
   if (!message) return;
   Object.entries(message).forEach(([fieldname, value]) => frm.set_value(fieldname, value || ""));
  });
 },
});

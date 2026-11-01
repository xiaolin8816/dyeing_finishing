const blankLabelMethod = "dyeing_finishing.dyeing_finishing.doctype.finished_product_blank_label.finished_product_blank_label";

frappe.ui.form.on("Finished Product Blank Label", {
 setup(frm) {
  frm.set_query("production_flow_card", () => ({filters: {docstatus: 1, production_status: ["!=", "已关闭"]}}));
 },
 refresh(frm) {
  if (frappe.user_roles.includes("System Manager")) {
   frm.page.add_action_item("设计标签", () => {
    window.open("/app/visual-print-template-manager", "_blank");
   });
  }
  if (!frm.is_new() && frm.doc.print_status !== "已作废") {
   frm.page.add_action_item("作废", () => frappe.confirm("确认作废这张空白标签打印单？", () => {
    frappe.call({method: `${blankLabelMethod}.void_blank_label_print`, args: {name: frm.doc.name}, freeze: true}).then(() => frm.reload_doc());
   }));
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

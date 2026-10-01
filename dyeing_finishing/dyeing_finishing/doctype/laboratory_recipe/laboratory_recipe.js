frappe.ui.form.on("Laboratory Recipe", {
 setup(frm) {
  frm.set_query("color_no", () => ({filters:{status:"启用"}}));
  frm.set_query("operation", "process_parameters", () => ({filters:{disabled:0}}));
 },
 color_no(frm) {
  if (!frm.doc.color_no) return;
  frappe.db.get_doc("Color Master", frm.doc.color_no).then(color => {
   frm.set_value("color", color.color_name || "");
   frm.set_value("customer", color.customer_name || "");
   frm.set_value("finished_product_name", color.product_name || "");
   if (!frm.doc.grey_fabric) frm.set_value("grey_fabric", color.grey_fabric || "");
  });
 }
});

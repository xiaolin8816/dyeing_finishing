frappe.ui.form.on("Laboratory Recipe", {
 setup(frm) {
  frm.set_query("color_no", () => ({filters:{status:"启用"}}));
  frm.set_query("process_parameter_template", () => ({
   filters: {
    status: "启用",
    ...(frm.doc.process_type ? {process_type: frm.doc.process_type} : {})
   }
  }));
 },
 color_no(frm) {
  if (!frm.doc.color_no) return;
  frappe.db.get_doc("Color Master", frm.doc.color_no).then(color => {
   frm.set_value("color", color.color_name || "");
   frm.set_value("customer", color.customer_name || "");
   frm.set_value("finished_product_name", color.product_name || "");
   if (!frm.doc.grey_fabric) frm.set_value("grey_fabric", color.grey_fabric || "");
  });
 },
 process_type(frm) {
  if (frm._setting_process_type_from_template) return;
  if (frm.doc.process_parameter_template) {
   frm.set_value("process_parameter_template", "");
   frm.clear_table("process_parameters");
   frm.refresh_field("process_parameters");
  }
 },
 process_parameter_template(frm) {
  if (!frm.doc.process_parameter_template) return;
  frappe.call({
   method: "dyeing_finishing.dyeing_finishing.doctype.process_parameter_template.process_parameter_template.get_process_parameter_template_items",
   args: {
    template_name: frm.doc.process_parameter_template,
    process_type: frm.doc.process_type || null
   },
   freeze: true,
   freeze_message: "正在带入工艺参数项目…",
   callback: ({message}) => {
    if (!message) return;
    const set_items = () => {
     frm.clear_table("process_parameters");
     (message.items || []).forEach(data => {
      const row = frm.add_child("process_parameters");
      Object.keys(data).forEach(key => frappe.model.set_value(row.doctype, row.name, key, data[key] || ""));
     });
     frm.refresh_field("process_parameters");
    };
    if (!frm.doc.process_type) {
     frm._setting_process_type_from_template = true;
     frm.set_value("process_type", message.process_type).then(() => {
      frm._setting_process_type_from_template = false;
      set_items();
     });
     return;
    }
    set_items();
   }
  });
 }
});

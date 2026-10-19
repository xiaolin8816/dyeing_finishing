frappe.ui.form.on("Dyeing System Settings", {
  refresh(frm) {
    frm.set_intro("这些设置将作为印染整理新单据的默认值，不会自动改写已有单据。", "blue");
  },
});

frappe.ui.form.on("Dyeing Finishing License", {
  refresh(frm) {
    frappe.call("dyeing_finishing.license.get_license_status").then((response) => {
      const status = response.message || {};
      frm.set_intro(status.message || "", status.indicator || "blue");
      frm.dashboard.set_headline(`<span class="indicator-pill ${status.indicator || "gray"}">${frappe.utils.escape_html(status.status || "未配置")}</span>`);
    });
  },
});

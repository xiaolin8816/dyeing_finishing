/* eslint-disable */
(() => {
  function check_license() {
    if (window.__dyeing_finishing_license_checked || frappe.session.user === "Guest") return;
    window.__dyeing_finishing_license_checked = true;
    frappe.call("dyeing_finishing.license.get_license_status").then((response) => {
      const status = response.message || {};
      const warn = ["过渡期", "宽限期", "已到期", "无效", "时间异常", "未生效"].includes(status.status)
        || (status.status === "有效" && Number(status.remaining_days) <= Number(status.reminder_days || 30));
      if (!warn) return;
      frappe.show_alert({message: status.message, indicator: status.indicator || "orange"}, 12);
    });
  }
  $(check_license);
})();

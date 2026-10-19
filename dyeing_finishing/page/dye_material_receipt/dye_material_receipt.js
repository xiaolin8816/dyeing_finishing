frappe.pages["dye-material-receipt"].on_page_load = function () {
    window.sessionStorage.setItem("dyeing_finishing.shared_route_owner", "purchase receipt");
    frappe.set_route("List", "Purchase Receipt");
};

frappe.pages["production-flow-card-rework"].on_page_show = function () {
    const filter = encodeURIComponent(JSON.stringify(["=", "回修"]));
    window.location.replace(`/desk/production-flow-card?mode=rework&flow_card_type=${filter}`);
};

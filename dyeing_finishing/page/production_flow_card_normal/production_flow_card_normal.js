frappe.pages["production-flow-card-normal"].on_page_show = function () {
    const filter = encodeURIComponent(JSON.stringify(["!=", "回修"]));
    window.location.replace(`/desk/production-flow-card?mode=normal&flow_card_type=${filter}`);
};

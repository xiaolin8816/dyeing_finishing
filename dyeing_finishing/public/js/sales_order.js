function make_finished_specification(row) {
    const width = String(row.custom_finished_width || "").trim();
    const gsm = String(row.custom_finished_gsm || "").trim();
    const gsm_uom = String(row.custom_finished_gsm_uom || "").trim();
    const gsm_value = gsm ? `${gsm}${gsm_uom}` : "";
    return [width, gsm_value].filter(Boolean).join("*");
}

function update_finished_specification(cdt, cdn) {
    const row = locals[cdt][cdn];
    frappe.model.set_value(cdt, cdn, "custom_finished_specification", make_finished_specification(row));
}

function set_requirement_tab(frm, active) {
    frm._dyeing_requirement_tab = active;
    const groups = {
        process: ["custom_process_requirements_tab", "custom_process_requirements"],
        packaging: ["custom_packaging_requirements_tab", "custom_packaging_requirements"],
    };

    Object.entries(groups).forEach(([tab, fieldnames]) => {
        fieldnames.forEach((fieldname) => {
            const field = frm.fields_dict[fieldname];
            if (field && field.$wrapper) field.$wrapper.toggle(tab === active);
        });
    });

    const field = frm.get_field("custom_requirement_tabs_html");
    if (!field || !field.$wrapper) return;

    field.$wrapper.html(`
        <div class="dyeing-requirement-tabs">
            <button type="button" class="btn btn-sm ${active === "process" ? "btn-primary" : "btn-default"}"
                data-dyeing-requirement-tab="process">加工要求</button>
            <button type="button" class="btn btn-sm ${active === "packaging" ? "btn-primary" : "btn-default"}"
                data-dyeing-requirement-tab="packaging">包装要求</button>
        </div>
    `);

    field.$wrapper.off("click.dyeingRequirementTabs").on(
        "click.dyeingRequirementTabs",
        "[data-dyeing-requirement-tab]",
        function () {
            set_requirement_tab(frm, $(this).data("dyeing-requirement-tab"));
        }
    );
}

function bind_single_item_add_button(frm) {
    const grid = frm.fields_dict.items?.grid;
    const button = grid?.wrapper?.find(".grid-add-row");
    if (!button?.length) return;

    button.off("click").on("click.dyeingSingleItemAdd", function (event) {
        event.preventDefault();
        event.stopImmediatePropagation();
        grid.add_new_row(null, null, false, null, true);
        return false;
    });
}

function bind_single_row_insert_buttons(row) {
    const form = row?.grid_form?.wrapper;
    if (!form?.length) return;

    const bind_insert = (selector, insert_below) => {
        form.find(selector).off("click").on("click.dyeingSingleRowInsert", function (event) {
            event.preventDefault();
            event.stopImmediatePropagation();
            row.insert(true, insert_below);
            return false;
        });
    };

    bind_insert(".grid-insert-row", false);
    bind_insert(".grid-insert-row-below", true);
}

frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        if (!frm.doc.custom_customer_order_no && frm.doc.po_no) {
            frm.set_value("custom_customer_order_no", frm.doc.po_no);
        }
        set_requirement_tab(frm, frm._dyeing_requirement_tab || "process");
        bind_single_item_add_button(frm);
    },
    custom_customer_order_no(frm) {
        if (frm.doc.po_no !== frm.doc.custom_customer_order_no) {
            frm.set_value("po_no", frm.doc.custom_customer_order_no);
        }
    },
    po_no(frm) {
        if (frm.doc.custom_customer_order_no !== frm.doc.po_no) {
            frm.set_value("custom_customer_order_no", frm.doc.po_no);
        }
    },
    items_on_form_rendered(frm) {
        const row = frm.cur_grid;
        const button = row?.grid_form?.wrapper?.find(".grid-collapse-row");
        if (!button?.length) return;

        button
            .attr("title", "返回物料列表")
            .attr("aria-label", "返回物料列表")
            .text("返回物料")
            .off("click.dyeingReturn")
            .on("click.dyeingReturn", function (event) {
                event.preventDefault();
                event.stopImmediatePropagation();
                row.toggle_view();
                return false;
            });

        bind_single_row_insert_buttons(row);
    },
});

frappe.ui.form.on("Sales Order Item", {
    custom_finished_width(frm, cdt, cdn) {
        update_finished_specification(cdt, cdn);
    },
    custom_finished_gsm(frm, cdt, cdn) {
        update_finished_specification(cdt, cdn);
    },
    custom_finished_gsm_uom(frm, cdt, cdn) {
        update_finished_specification(cdt, cdn);
    },
});
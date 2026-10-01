(() => {
    const VERSION_WIDTH = 72;

    function apply_recipe_version_width(listview) {
        const width = `${VERSION_WIDTH}px`;
        listview.$result.find('[data-fieldname="recipe_version"]').css({
            width,
            minWidth: width,
            maxWidth: width,
            flex: `0 0 ${width}`,
        });
    }

    frappe.listview_settings["Laboratory Recipe"] = {
        refresh(listview) {
            window.setTimeout(() => apply_recipe_version_width(listview), 0);
        },
    };
})();

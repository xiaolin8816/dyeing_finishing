from frappe.custom.doctype.custom_field.custom_field import delete_custom_fields


def execute():
    delete_custom_fields(
        {
            "Item": [
                "custom_dyeing_color_tone",
                "custom_dyeing_standard_concentration",
                "custom_dyeing_material_column",
            ]
        }
    )

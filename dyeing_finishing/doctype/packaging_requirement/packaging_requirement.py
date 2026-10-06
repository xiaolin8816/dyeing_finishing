# Copyright (c) 2026, Xiaolin Hang and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.model.naming import getseries


class PackagingRequirement(Document):
    def autoname(self):
        if not self.packaging_requirement_code:
            generated_name = getseries("Packaging Requirement-", 4)
            self.packaging_requirement_code = generated_name.removeprefix("Packaging Requirement-")
        self.name = self.packaging_requirement_code

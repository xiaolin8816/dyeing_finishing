# Copyright (c) 2026, Xiaolin Hang and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.model.naming import getseries


class ProcessRequirement(Document):
    def autoname(self):
        if not self.process_requirement_code:
            self.process_requirement_code = getseries("Process Requirement-", 4)
        self.name = self.process_requirement_code

from frappe.model.document import Document

class SiteSubscription(Document):
    def validate(self):
        if not self.creation_date:
            self.creation_date = frappe.utils.now()
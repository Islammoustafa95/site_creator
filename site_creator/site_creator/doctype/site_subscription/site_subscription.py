from frappe.model.document import Document

class SiteSubscription(Document):
    def validate(self):
        if not self.creation_date:
            self.creation_date = frappe.utils.today()
        if not self.expiry_date:
            self.expiry_date = frappe.utils.add_days(self.creation_date, 30)
        if not self.status:
            self.status = 'Pending'

    def before_submit(self):
        self.status = 'Pending'
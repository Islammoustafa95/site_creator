import frappe

def get_context(context):
    context.sites = frappe.get_all(
        "Site Subscription",
        fields=["subdomain", "plan", "creation_date", "expiry_date", "status"]
    )
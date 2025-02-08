import frappe

def get_context(context):
    context.plans = frappe.get_all(
        "Subscription Plan",
        fields=["name", "plan_name", "price"]
    )
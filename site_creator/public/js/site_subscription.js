frappe.ui.form.on('Site Subscription', {
    refresh: function(frm) {
        frm.add_custom_button(__('Create Site'), function() {
            frappe.call({
                method: 'site_creator.api.create_site',
                args: {
                    subdomain: frm.doc.subdomain,
                    plan: frm.doc.plan,
                    email: frm.doc.email
                },
                callback: function(r) {
                    if (r.message && r.message.status === "success") {
                        frappe.msgprint("Site creation started successfully");
                    } else {
                        frappe.msgprint(r.message.message || "Error creating site");
                    }
                }
            });
        });
    }
});
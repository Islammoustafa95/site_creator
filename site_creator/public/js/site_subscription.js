frappe.ui.form.on('Site Subscription', {
    refresh: function(frm) {
        if(!frm.doc.__islocal) {
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
                            frappe.show_alert({
                                message: __("Site creation started. You can monitor the progress here."),
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        } else {
                            frappe.show_alert({
                                message: __(r.message.message || "Error creating site"),
                                indicator: 'red'
                            });
                        }
                    }
                });
            });
        }
    }
});
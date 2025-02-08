frappe.ui.form.on('Site Subscription', {
    refresh: function(frm) {
        if(frm.doc.__islocal) {
            frm.add_custom_button(__('Create Site'), function() {
                if (!frm.doc.subdomain || !frm.doc.plan || !frm.doc.email) {
                    frappe.msgprint(__('Please fill in all required fields'));
                    return;
                }

                frappe.call({
                    method: 'site_creator.api.create_site',
                    args: {
                        subdomain: frm.doc.subdomain,
                        plan: frm.doc.plan,
                        email: frm.doc.email
                    },
                    freeze: true,
                    freeze_message: __('Creating site...'),
                    callback: function(r) {
                        if (r.message && r.message.status === "success") {
                            frappe.show_alert({
                                message: __("Site creation initiated. You will receive an email shortly."),
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
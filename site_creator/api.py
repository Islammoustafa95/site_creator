import frappe
import os
import subprocess
import requests
from datetime import datetime
import random
import string
from frappe.utils import get_site_name

def create_cloudflare_record(subdomain):
    try:
        api_token = frappe.conf.get("cloudflare_api_token")
        zone_id = frappe.conf.get("cloudflare_zone_id")
        server_ip = frappe.conf.get("server_ip")

        if not all([api_token, zone_id, server_ip]):
            raise Exception("Cloudflare configuration missing in common_site_config.json")

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

        data = {
            "type": "A",
            "name": subdomain,
            "content": server_ip,
            "proxied": True
        }

        response = requests.post(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
            headers=headers,
            json=data
        )

        if not response.ok:
            raise Exception(f"Cloudflare API error: {response.text}")

        return True

    except Exception as e:
        raise Exception(f"Failed to create Cloudflare DNS record: {str(e)}")

@frappe.whitelist()
def create_site(subdomain, plan, email):
    subscription = None
    try:
        site_name = f"{subdomain}.ventotech.co"

        # Check if subdomain exists in Site Subscription
        if frappe.db.exists("Site Subscription", {"subdomain": subdomain}):
            raise Exception("Subdomain already exists")

        # Create Cloudflare DNS record first
        create_cloudflare_record(subdomain)

        # Create subscription record
        subscription = frappe.get_doc({
            "doctype": "Site Subscription",
            "subdomain": subdomain,
            "plan": plan,
            "email": email,
            "creation_date": datetime.now(),
            "status": "In Progress",
            "site_creation_log": "DNS Record created successfully. Starting site creation..."
        })
        subscription.insert(ignore_permissions=True)

        # Generate random admin password
        admin_password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

        # Get MySQL password
        mysql_password = frappe.conf.get('mysql_root_password')
        if not mysql_password:
            raise Exception("MySQL root password not configured in common_site_config.json")

        # Determine which script to run
        script_path = "/home/frappe/plan1.sh" if plan == "Plan 1" else "/home/frappe/plan2.sh"

        # Run the script
        process = subprocess.Popen(
            [script_path, site_name, admin_password, mysql_password, email],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        def update_log():
            try:
                log_file = f"/home/frappe/site_creation_logs/{site_name}_creation.log"
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        current_log = f.read()
                        subscription.site_creation_log = current_log

                        if "SUCCESS" in current_log:
                            subscription.status = "Completed"
                            # Send success email
                            send_completion_email(email, site_name, admin_password)
                        elif "FAILED" in current_log:
                            subscription.status = "Failed"
                            # Send failure email
                            send_failure_email(email, site_name)

                        subscription.save()
            except Exception as e:
                frappe.log_error(f"Log update error: {str(e)}", "Site Creation Log Update Error")

        # Schedule log updates
        frappe.enqueue(
            update_log,
            queue='long',
            timeout=3600
        )

        return {
            "status": "success",
            "message": "Site creation initiated",
            "subscription_name": subscription.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Site Creation Error")
        if subscription:
            subscription.status = "Failed"
            subscription.site_creation_log += f"\nError: {str(e)}"
            subscription.save()
        return {"status": "error", "message": str(e)}

def send_completion_email(email, site_name, admin_password):
    try:
        frappe.sendmail(
            recipients=[email],
            subject=f"Your site {site_name} is ready!",
            message=f"""
            Hello,

            Your new site has been created successfully!

            Site URL: https://{site_name}
            Username: administrator
            Password: {admin_password}

            Please change your password after first login.

            Best regards,
            Your Site Creation Team
            """
        )
    except Exception as e:
        frappe.log_error(f"Email sending error: {str(e)}", "Site Creation Email Error")

def send_failure_email(email, site_name):
    try:
        frappe.sendmail(
            recipients=[email],
            subject=f"Site creation failed for {site_name}",
            message=f"""
            Hello,

            Unfortunately, we encountered an error while creating your site {site_name}.
            Our team has been notified and will investigate the issue.

            We will contact you once we have more information.

            Best regards,
            Your Site Creation Team
            """
        )
    except Exception as e:
        frappe.log_error(f"Email sending error: {str(e)}", "Site Creation Email Error")
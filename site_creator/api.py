# site_creator/site_creator/api.py
import frappe
import os
import requests
import subprocess
from datetime import datetime, timedelta
from frappe.utils import random_string

@frappe.whitelist(allow_guest=True)
def create_site(subdomain, plan, email):
    try:
        # Validate subdomain
        if frappe.db.exists("Site Subscription", {"subdomain": subdomain}):
            frappe.throw("Subdomain already exists")

        # Create site subscription
        site = frappe.get_doc({
            "doctype": "Site Subscription",
            "subdomain": subdomain,
            "plan": plan,
            "email": email,
            "creation_date": datetime.now().date(),
            "expiry_date": (datetime.now() + timedelta(days=30)).date(),
            "status": "Pending"
        })
        site.insert()

        # Send initial email
        send_creation_started_email(email, subdomain)

        # Create site
        admin_password = random_string(16)
        site_name = f"{subdomain}.ventotech.co"

        # Create DNS record
        create_cloudflare_record(subdomain)

        # Get MySQL root password from common_site_config.json
        mysql_password = frappe.conf.get('mysql_root_password')
        if not mysql_password:
            frappe.throw("MySQL root password not configured")

        # Get apps from plan
        plan_doc = frappe.get_doc("Subscription Plan", plan)
        apps_to_install = [app.app_name for app in plan_doc.apps]

        # Construct the installation command chain
        installation_command = f"bench new-site {site_name} --admin-password {admin_password} --mariadb-root-password {mysql_password}"

        # Add each app installation and migration to the command chain
        for app in apps_to_install:
            installation_command += f" && bench --site {site_name} install-app {app}"
            installation_command += f" && bench --site {site_name} migrate"

        # Execute the complete installation command
        process = subprocess.Popen(
            installation_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        output, error = process.communicate()

        if process.returncode != 0:
            error_msg = error.decode('utf-8') if error else "Unknown error"
            frappe.log_error(f"Installation failed: {error_msg}", "Site Creation Error")
            raise Exception(f"Site creation failed: {error_msg}")

        # Configure domain and nginx
        os.system(f"bench setup add-domain {site_name}")
        os.system("bench setup nginx --yes")
        os.system("bench setup reload-nginx")

        # Update status
        site.status = "Active"
        site.save()

        # Send completion email
        send_creation_complete_email(email, subdomain, admin_password)

        return {"status": "success", "message": "Site created successfully"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Site Creation Error")
        site.status = "Failed"
        site.save()
        return {"status": "error", "message": str(e)}

def create_cloudflare_record(subdomain):
    api_token = frappe.conf.get("cloudflare_api_token")
    zone_id = frappe.conf.get("cloudflare_zone_id")

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    data = {
        "type": "A",
        "name": subdomain,
        "content": frappe.conf.get("server_ip"),
        "proxied": True
    }

    response = requests.post(
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
        headers=headers,
        json=data
    )

    if not response.ok:
        frappe.throw("Failed to create DNS record")

def send_creation_started_email(email, subdomain):
    frappe.sendmail(
        recipients=[email],
        subject="Site Creation Started",
        message=f"Your site {subdomain}.ventotech.co is being created. We'll notify you once it's ready."
    )

def send_creation_complete_email(email, subdomain, password):
    frappe.sendmail(
        recipients=[email],
        subject="Site Creation Complete",
        message=f"""
        Your site has been created successfully!

        URL: https://{subdomain}.ventotech.co
        Username: administrator
        Password: {password}

        Please change your password after first login.
        """
    )
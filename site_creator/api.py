# site_creator/site_creator/api.py
import frappe
import os
import requests
import subprocess
import time
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

        # Create bench site with MySQL password
        run_command(f"bench new-site {site_name} --admin-password {admin_password} --mariadb-root-password {mysql_password}")

        # Install apps based on plan
        plan_doc = frappe.get_doc("Subscription Plan", plan)

        for app in plan_doc.apps:
            frappe.log_error(f"Starting installation of {app.app_name}", "App Installation Status")

            # Check if app is already installed
            installed_apps = get_installed_apps(site_name)
            if app.app_name in installed_apps:
                frappe.log_error(f"{app.app_name} is already installed", "App Installation Status")
                continue

            # Install app with retries
            retries = 3
            success = False

            for attempt in range(retries):
                # Install the app
                returncode, output, error = run_command(f"bench --site {site_name} install-app {app.app_name}")

                if returncode == 0:
                    # Verify installation
                    installed_apps = get_installed_apps(site_name)
                    if app.app_name in installed_apps:
                        success = True
                        frappe.log_error(f"Successfully installed {app.app_name}", "App Installation Status")
                        break
                    else:
                        frappe.log_error(f"App {app.app_name} installation completed but not found in installed apps",
                                       "App Installation Error")
                else:
                    error_msg = error.decode('utf-8') if error else "Unknown error"
                    frappe.log_error(f"Attempt {attempt + 1}: Failed to install {app.app_name}: {error_msg}",
                                   "App Installation Error")

                # Wait before retry
                time.sleep(30)

            if not success:
                raise Exception(f"Failed to install {app.app_name} after {retries} attempts")

            # Run migrations for the site
            returncode, output, error = run_command(f"bench --site {site_name} migrate")
            if returncode != 0:
                error_msg = error.decode('utf-8') if error else "Unknown error"
                raise Exception(f"Migration failed for {app.app_name}: {error_msg}")

            # Clear cache
            run_command(f"bench --site {site_name} clear-cache")

            # Wait before next app
            time.sleep(60)

        # Verify all required apps are installed
        final_installed_apps = get_installed_apps(site_name)
        missing_apps = [app.app_name for app in plan_doc.apps if app.app_name not in final_installed_apps]

        if missing_apps:
            raise Exception(f"Some apps failed to install: {', '.join(missing_apps)}")

        # Configure domain and nginx
        run_command(f"bench setup add-domain {site_name}")
        run_command("bench setup nginx --yes")
        run_command("bench setup reload-nginx")

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

def run_command(command):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True
    )
    output, error = process.communicate()
    return process.returncode, output, error

def get_installed_apps(site_name):
    returncode, output, error = run_command(f"bench --site {site_name} list-apps")
    if returncode == 0:
        # Convert bytes to string and split into lines
        apps_output = output.decode('utf-8').strip().split('\n')
        # Remove empty strings and whitespace
        installed_apps = [app.strip() for app in apps_output if app.strip()]
        return installed_apps
    return []

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
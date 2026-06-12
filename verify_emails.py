import os
import csv
import json
import re
import time
import urllib.request
import urllib.parse
import subprocess
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_FILE = 'token.json'
CONFIG_FILE = 'config.json'
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/gmail.modify'
]

CITY_CSV = 'city_employees_outreach.csv'
VENDOR_CSV = 'vendor_employees_outreach.csv'

# Load config
SENDER_EMAIL = ""
SPREADSHEET_ID = ""
ABSTRACT_API_KEY = ""

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as cf:
            config_data = json.load(cf)
            SENDER_EMAIL = config_data.get('sender_email', SENDER_EMAIL)
            SPREADSHEET_ID = config_data.get('spreadsheet_id', SPREADSHEET_ID)
            ABSTRACT_API_KEY = config_data.get('abstract_api_key', ABSTRACT_API_KEY)
    except Exception as e:
        print(f"Warning: Could not parse config.json: {e}")

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

def get_creds():
    """Gets cached credentials."""
    if not os.path.exists(TOKEN_FILE):
        print(f"Error: Token file not found at {TOKEN_FILE}. Run run_outreach.py first.")
        return None
    return Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)


def check_syntax(email):
    """Validates email format using regex."""
    return bool(re.match(EMAIL_REGEX, email))


def check_domain_mx_local(email):
    """Checks if the email domain has valid MX records using nslookup."""
    parts = email.split('@')
    if len(parts) != 2:
        return False
    domain = parts[1].strip()
    
    try:
        # Run nslookup MX query
        out = subprocess.run(['nslookup', '-type=mx', domain], capture_output=True, text=True, timeout=5)
        stdout = out.stdout.lower()
        
        # Check if output contains MX records or "mail exchanger"
        if "mail exchanger" in stdout or "mx preference" in stdout or "mail exchanger =" in stdout:
            return True
            
        # Fallback: check if the domain resolves to an IP address (A record)
        out_a = subprocess.run(['nslookup', domain], capture_output=True, text=True, timeout=5)
        stdout_a = out_a.stdout.lower()
        if "addresses:" in stdout_a or "address:" in stdout_a:
            return True
            
        return False
    except Exception as e:
        # If nslookup fails or times out, return True to be safe
        print(f"  [!] Local DNS check failed for {domain}: {e}")
        return True


def verify_email_via_api(email, api_key):
    """Verifies email via Abstract API Email Validation API."""
    params = urllib.parse.urlencode({
        'api_key': api_key,
        'email': email
    })
    url = f"https://emailreputation.abstractapi.com/v1/?{params}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            deliverability_data = data.get('email_deliverability', {})
            status = deliverability_data.get('status', '').lower()
            if not status:
                status = data.get('deliverability', '').lower()
                
            is_format_valid = deliverability_data.get('is_format_valid', True)
            if isinstance(is_format_valid, dict):
                is_format_valid = is_format_valid.get('value', True)
            elif 'is_format_valid' in data:
                is_format_valid = data.get('is_format_valid', True)
                if isinstance(is_format_valid, dict):
                    is_format_valid = is_format_valid.get('value', True)
                    
            is_mx_valid = deliverability_data.get('is_mx_valid', True)
            if isinstance(is_mx_valid, dict):
                is_mx_valid = is_mx_valid.get('value', True)
            elif 'is_mx_valid' in data:
                is_mx_valid = data.get('is_mx_valid', True)
                if isinstance(is_mx_valid, dict):
                    is_mx_valid = is_mx_valid.get('value', True)

            is_smtp_valid = deliverability_data.get('is_smtp_valid', True)
            if isinstance(is_smtp_valid, dict):
                is_smtp_valid = is_smtp_valid.get('value', True)
            elif 'is_smtp_valid' in data:
                is_smtp_valid = data.get('is_smtp_valid', True)
                if isinstance(is_smtp_valid, dict):
                    is_smtp_valid = is_smtp_valid.get('value', True)

            # Mark as invalid if format is invalid, MX is invalid, or status is explicitly undeliverable
            if status == 'undeliverable' or not is_format_valid or not is_mx_valid:
                return 'Invalid', f"Undeliverable (Format: {is_format_valid}, MX: {is_mx_valid}, SMTP: {is_smtp_valid})"
                
            # If SMTP is invalid and format is valid, it is likely invalid (no mailbox exists)
            if not is_smtp_valid:
                return 'Invalid', "Invalid mailbox (SMTP failed)"
                
            return 'Verified', "Deliverable"
    except Exception as e:
        print(f"  [!] Abstract API failed for {email}: {e}")
        return 'Error', str(e)


def delete_draft_for_email(gmail_service, email):
    """Searches for any drafts sent to the given email address and deletes them."""
    try:
        results = gmail_service.users().drafts().list(userId='me').execute()
        drafts = results.get('drafts', [])
        
        while 'nextPageToken' in results:
            page_token = results['nextPageToken']
            results = gmail_service.users().drafts().list(userId='me', pageToken=page_token).execute()
            drafts.extend(results.get('drafts', []))
            
        deleted_count = 0
        for d in drafts:
            draft_id = d['id']
            draft_detail = gmail_service.users().drafts().get(userId='me', id=draft_id, format='full').execute()
            msg = draft_detail.get('message', {})
            payload = msg.get('payload', {})
            headers = payload.get('headers', [])
            
            to_val = ""
            for h in headers:
                if h['name'].lower() == 'to':
                    to_val = h['value'].strip().lower()
                    break
                    
            if email.strip().lower() in to_val:
                gmail_service.users().drafts().delete(userId='me', id=draft_id).execute()
                print(f"  [+] Trashed Gmail draft ID {draft_id} for invalid contact: {email}")
                deleted_count += 1
                
        return deleted_count
    except Exception as e:
        print(f"  [-] Error checking/deleting draft for {email}: {e}")
        return 0


def get_emails_to_check(limit=100):
    """Retrieves up to limit emails that haven't been verified or marked as bounced/invalid."""
    emails_to_check = []
    
    for csv_path in [CITY_CSV, VENDOR_CSV]:
        if os.path.exists(csv_path):
            with open(csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = row.get('Email', '').strip().lower()
                    status = row.get('Delivery Status', '').strip()
                    
                    if email and status not in ['Verified', 'Invalid', 'Bounced']:
                        emails_to_check.append((email, csv_path))
                        if len(emails_to_check) >= limit:
                            return emails_to_check
                            
    return emails_to_check


def update_contact_status_in_csv(csv_path, email_statuses):
    """Updates CSV status for email addresses. email_statuses is a dict: email -> status."""
    if not os.path.exists(csv_path):
        return 0
        
    updated_rows = []
    matches_found = 0
    
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames)
        
        if 'Delivery Status' not in fields:
            fields.append('Delivery Status')
            
        for row in reader:
            email = row['Email'].strip().lower()
            if email in email_statuses:
                row['Delivery Status'] = email_statuses[email]
                matches_found += 1
            updated_rows.append(row)
            
    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(updated_rows)
        
    return matches_found


def update_contact_status_in_sheets(sheets_service, sheet_id, sheet_name, email_statuses):
    """Updates status in Google Sheets tab."""
    try:
        range_name = f"'{sheet_name}'!A1:Z500"
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        
        rows = result.get('values', [])
        if not rows:
            return 0
            
        header = rows[0]
        
        if 'Email' not in header:
            print(f"[-] 'Email' column not found in Google Sheets tab '{sheet_name}'.")
            return 0
        email_idx = header.index('Email')
        
        if 'Delivery Status' not in header:
            header.append('Delivery Status')
            status_idx = len(header) - 1
            sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"'{sheet_name}'!A1",
                valueInputOption='RAW',
                body={'values': [header]}
            ).execute()
        else:
            status_idx = header.index('Delivery Status')
            
        updates = 0
        for i in range(1, len(rows)):
            row = rows[i]
            while len(row) < len(header):
                row.append("")
                
            email = row[email_idx].strip().lower()
            if email in email_statuses:
                new_status = email_statuses[email]
                row[status_idx] = new_status
                col_letter = chr(65 + status_idx)
                cell_range = f"'{sheet_name}'!{col_letter}{i+1}"
                sheets_service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range=cell_range,
                    valueInputOption='RAW',
                    body={'values': [[new_status]]}
                ).execute()
                updates += 1
                
        return updates
    except Exception as e:
        print(f"[-] Error updating Google Sheet tab '{sheet_name}': {e}")
        return 0


def run_verification():
    print("====================================================")
    print("        MyCity Email Verification Tool              ")
    print("====================================================")
    
    creds = get_creds()
    if not creds:
        return
        
    gmail_service = build('gmail', 'v1', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    
    # Get up to 100 emails that need verification
    emails_to_check = get_emails_to_check(limit=100)
    print(f"[+] Found {len(emails_to_check)} emails to check in this batch.")
    
    if not emails_to_check:
        print("[+] All emails have already been verified or flagged. Exiting.")
        return
        
    if not ABSTRACT_API_KEY:
        print("[!] Warning: 'abstract_api_key' not found in config.json.")
        print("    Please sign up at abstractapi.com and add your key to config.json.")
        print("    Running in LOCAL-ONLY mode (Syntax + DNS MX checks)...")
        
    email_statuses = {}
    invalid_emails = []
    
    for idx, (email, csv_path) in enumerate(emails_to_check):
        print(f"[{idx+1}/{len(emails_to_check)}] Verifying {email}...")
        
        # 1. Syntax check
        if not check_syntax(email):
            print(f"  [-] Syntax invalid for {email}")
            email_statuses[email] = 'Invalid'
            invalid_emails.append(email)
            continue
            
        # 2. Local DNS MX check
        if not check_domain_mx_local(email):
            print(f"  [-] Domain MX/DNS check failed for {email}")
            email_statuses[email] = 'Invalid'
            invalid_emails.append(email)
            continue
            
        # 3. API check if key available
        if ABSTRACT_API_KEY:
            status, detail = verify_email_via_api(email, ABSTRACT_API_KEY)
            print(f"  [-] Abstract API Result: {status} ({detail})")
            
            if status == 'Invalid':
                email_statuses[email] = 'Invalid'
                invalid_emails.append(email)
            elif status == 'Verified':
                email_statuses[email] = 'Verified'
            else:
                # API error, do not mark as invalid to prevent false positives. Leave status unchecked.
                print(f"  [!] Skipping classification due to API error: {detail}")
                
            # Respect rate limit
            time.sleep(0.5)
        else:
            # Local-only checks passed. Do not write 'Verified' yet, so they remain eligible for future API checks.
            print(f"  [+] Local checks passed. (Skipping database update to allow future API check)")

            
    # Update local CSVs
    print("\n--- Task 1: Updating Local CSV Databases ---")
    city_updates = update_contact_status_in_csv(CITY_CSV, email_statuses)
    vendor_updates = update_contact_status_in_csv(VENDOR_CSV, email_statuses)
    print(f"[+] Marked {city_updates} contacts in {CITY_CSV}")
    print(f"[+] Marked {vendor_updates} contacts in {VENDOR_CSV}")
    
    # Update Google Sheets
    if SPREADSHEET_ID:
        print(f"\n--- Task 2: Updating Google Sheets ({SPREADSHEET_ID}) ---")
        city_sheet_updates = update_contact_status_in_sheets(sheets_service, SPREADSHEET_ID, 'City Employees', email_statuses)
        vendor_sheet_updates = update_contact_status_in_sheets(sheets_service, SPREADSHEET_ID, 'Vendor Employees', email_statuses)
        print(f"[+] Flagged {city_sheet_updates} rows in Google Sheets 'City Employees'")
        print(f"[+] Flagged {vendor_sheet_updates} rows in Google Sheets 'Vendor Employees'")
    else:
        print("\n[-] Google Sheets update skipped: 'spreadsheet_id' not found in config.json.")
        
    # Trash Gmail Drafts for invalid contacts
    if invalid_emails:
        print("\n--- Task 3: Trashing Drafts for Invalid Emails ---")
        deleted_drafts = 0
        for email in invalid_emails:
            deleted_drafts += delete_draft_for_email(gmail_service, email)
        print(f"[+] Trashed {deleted_drafts} drafts associated with invalid emails.")
        
    print("\n[+] Done! Email verification batch complete.")


if __name__ == '__main__':
    run_verification()

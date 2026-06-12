import os
import csv
import json
import time
import sys
import datetime
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

# Send Limits Configuration
DAILY_SEND_LIMIT = 30
ORG_DAILY_LIMIT = 2

# Load config
SENDER_EMAIL = ""
SPREADSHEET_ID = ""

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as cf:
            config_data = json.load(cf)
            SENDER_EMAIL = config_data.get('sender_email', SENDER_EMAIL)
            SPREADSHEET_ID = config_data.get('spreadsheet_id', SPREADSHEET_ID)
    except Exception as e:
        print(f"Warning: Could not parse config.json: {e}")


def get_creds():
    """Gets cached credentials."""
    if not os.path.exists(TOKEN_FILE):
        print(f"Error: Token file not found at {TOKEN_FILE}. Run run_outreach.py first.")
        return None
    return Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)


def is_working_hours():
    """Checks if current time is US Working Hours (9:00 AM - 5:00 PM EST, Mon-Fri)."""
    # Using local system time (since metadata indicates user is in Eastern Time timezone -04:00)
    now = datetime.datetime.now()
    hour = now.hour
    weekday = now.weekday()  # Monday is 0, Sunday is 6
    
    # 0-4 is Monday-Friday, hour must be between 9 and 16 inclusive (9:00 AM to 4:59 PM)
    if weekday < 5 and (9 <= hour < 17):
        return True
    return False


def load_verified_and_sent_counts(today_str):
    """Loads verified contacts and counts how many have already been sent today per organization."""
    verified_contacts = []
    sent_today_count = 0
    org_sent_today = {}
    
    for csv_path in [CITY_CSV, VENDOR_CSV]:
        if os.path.exists(csv_path):
            with open(csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = row.get('Email', '').strip().lower()
                    org = row.get('Organization', '').strip()
                    status = row.get('Delivery Status', '').strip()
                    
                    # Track total sent today
                    if status == f"Sent ({today_str})":
                        sent_today_count += 1
                        org_sent_today[org] = org_sent_today.get(org, 0) + 1
                    
                    # Collect verified contacts
                    if email and status == 'Verified':
                        verified_contacts.append({
                            'email': email,
                            'name': row.get('Full Name', '').strip(),
                            'org': org,
                            'csv': csv_path
                        })
                        
    return verified_contacts, sent_today_count, org_sent_today


def update_contact_status_in_csv(csv_path, email, status):
    """Updates the status of a specific email in a CSV file."""
    if not os.path.exists(csv_path):
        return False
        
    updated_rows = []
    success = False
    
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames)
        
        if 'Delivery Status' not in fields:
            fields.append('Delivery Status')
            
        for row in reader:
            row_email = row['Email'].strip().lower()
            if row_email == email.strip().lower():
                row['Delivery Status'] = status
                success = True
            updated_rows.append(row)
            
    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(updated_rows)
        
    return success


def update_contact_status_in_sheets(sheets_service, sheet_id, sheet_name, email, status):
    """Updates the status of a specific email in Google Sheets."""
    try:
        range_name = f"'{sheet_name}'!A1:Z500"
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        
        rows = result.get('values', [])
        if not rows:
            return False
            
        header = rows[0]
        if 'Email' not in header:
            return False
        email_idx = header.index('Email')
        
        if 'Delivery Status' not in header:
            header.append('Delivery Status')
            status_idx = len(header) - 1
            # Update header row
            sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"'{sheet_name}'!A1",
                valueInputOption='RAW',
                body={'values': [header]}
            ).execute()
        else:
            status_idx = header.index('Delivery Status')
            
        for i in range(1, len(rows)):
            row = rows[i]
            while len(row) < len(header):
                row.append("")
                
            row_email = row[email_idx].strip().lower()
            if row_email == email.strip().lower():
                row[status_idx] = status
                col_letter = chr(65 + status_idx)
                cell_range = f"'{sheet_name}'!{col_letter}{i+1}"
                sheets_service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range=cell_range,
                    valueInputOption='RAW',
                    body={'values': [[status]]}
                ).execute()
                return True
        return False
    except Exception as e:
        print(f"  [-] Google Sheets update failed for {email}: {e}")
        return False


def find_and_send_draft(gmail_service, email):
    """Searches for a draft to the target email and sends it."""
    try:
        # Query drafts for target email address
        results = gmail_service.users().drafts().list(userId='me', q=f"to:{email}").execute()
        drafts = results.get('drafts', [])
        
        if not drafts:
            return False, "No draft found"
            
        # Get the first matching draft ID
        draft_id = drafts[0]['id']
        
        # Send the draft
        gmail_service.users().drafts().send(userId='me', body={'id': draft_id}).execute()
        return True, draft_id
    except Exception as e:
        return False, str(e)


def run_sender():
    print("====================================================")
    print("        MyCity Outreach Email Sending Tool          ")
    print("====================================================")
    
    dry_run = '--dry-run' in sys.argv
    force = '--force' in sys.argv
    
    if dry_run:
        print("[!] RUNNING IN DRY-RUN MODE (No actual emails will be sent)\n")
        
    # 1. Time Gate Check
    if not is_working_hours() and not force:
        print("[-] Outside US Working Hours (9:00 AM - 5:00 PM EST, Mon-Fri).")
        print("    No emails will be sent. Exiting.")
        return
        
    creds = get_creds()
    if not creds:
        return
        
    gmail_service = build('gmail', 'v1', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    
    # 2. Load verified contacts & today's counts
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    verified_contacts, sent_today_count, org_sent_today = load_verified_and_sent_counts(today_str)
    
    print(f"[+] Date: {today_str}")
    print(f"[+] Verified contacts pending: {len(verified_contacts)}")
    print(f"[+] Total emails already sent today: {sent_today_count} (Daily limit: {DAILY_SEND_LIMIT})")
    
    if sent_today_count >= DAILY_SEND_LIMIT:
        print("[+] Daily sending limit of 30 emails has already been reached. Exiting.")
        return
        
    if not verified_contacts:
        print("[+] No verified contacts pending outreach. Exiting.")
        return
        
    emails_sent = 0
    remaining_quota = DAILY_SEND_LIMIT - sent_today_count
    
    for contact in verified_contacts:
        if emails_sent >= remaining_quota:
            print(f"[+] Reached daily limit of {DAILY_SEND_LIMIT} sends in this run. Stopping.")
            break
            
        email = contact['email']
        name = contact['name']
        org = contact['org']
        csv_path = contact['csv']
        
        # Check organization limits
        org_sent = org_sent_today.get(org, 0)
        if org_sent >= ORG_DAILY_LIMIT:
            print(f"  [-] Skipping {name} ({email}) - Organization limit of {ORG_DAILY_LIMIT} reached today for '{org}'.")
            continue
            
        print(f"\nProcessing outreach to: {name} ({email}) at {org}...")
        
        if dry_run:
            print(f"  [DRY-RUN] Would send draft to {email}...")
            emails_sent += 1
            org_sent_today[org] = org_sent + 1
        else:
            success, result = find_and_send_draft(gmail_service, email)
            if success:
                print(f"  [+] Successfully sent draft (Draft ID: {result})!")
                
                # Update CSV
                update_contact_status_in_csv(csv_path, email, f"Sent ({today_str})")
                
                # Update Sheets
                if SPREADSHEET_ID:
                    sheet_name = 'City Employees' if csv_path == CITY_CSV else 'Vendor Employees'
                    update_contact_status_in_sheets(sheets_service, SPREADSHEET_ID, sheet_name, email, f"Sent ({today_str})")
                
                emails_sent += 1
                org_sent_today[org] = org_sent + 1
                
                # Throttle slightly between sends (2 seconds)
                time.sleep(2)
            else:
                print(f"  [-] Failed to send email to {email}: {result}")
                
    print(f"\n[+] Outreach run complete. Sent {emails_sent} emails in this batch.")


if __name__ == '__main__':
    run_sender()

import os
import csv
import json
import re
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


TOKEN_FILE = 'token.json'
CONFIG_FILE = 'config.json'
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/gmail.modify' # Requires modify scope to trash parsed bounce messages
]

CITY_CSV = 'city_employees_outreach.csv'
VENDOR_CSV = 'vendor_employees_outreach.csv'

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


def search_bounce_emails(gmail_service):
    """Searches for bounce email messages in Inbox, Junk/Spam, and Archive."""
    query = 'from:mailer-daemon OR subject:"delivery status notification" OR subject:"undelivered mail"'
    try:
        # Search all mail, including Spam and Trash
        results = gmail_service.users().messages().list(userId='me', q=query, includeSpamTrash=True).execute()
        messages = results.get('messages', [])
        
        while 'nextPageToken' in results:
            page_token = results['nextPageToken']
            results = gmail_service.users().messages().list(userId='me', q=query, includeSpamTrash=True, pageToken=page_token).execute()
            messages.extend(results.get('messages', []))
            
        return messages
    except HttpError as error:
        print(f"[-] Error searching Gmail: {error}")
        return []


def load_target_emails():
    """Loads all target email addresses from the two CSV files."""
    emails = set()
    for csv_path in [CITY_CSV, VENDOR_CSV]:
        if os.path.exists(csv_path):
            try:
                with open(csv_path, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        email = row.get('Email')
                        if email:
                            emails.add(email.strip().lower())
            except Exception as e:
                print(f"[-] Error reading {csv_path}: {e}")
    return emails


def find_matched_bounces(gmail_service, message_info, target_emails):
    """Retrieves message content and checks if any target email is present in headers, subject, snippet, or body."""
    msg_id = message_info['id']
    try:
        msg = gmail_service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        
        # Check snippet
        snippet = msg.get('snippet', '').lower()
        
        # Check headers (Subject, X-Failed-Recipients, etc.)
        payload = msg.get('payload', {})
        headers = payload.get('headers', [])
        header_text = ""
        for h in headers:
            header_text += f" {h['name']}: {h['value']}"
        header_text = header_text.lower()
        
        # Check body
        body_text = ""
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    body_text += base64_decode(part.get('body', {}).get('data', ''))
        else:
            body_text += base64_decode(payload.get('body', {}).get('data', ''))
        body_text = body_text.lower()
        
        # Combine all text
        full_content = f"{snippet} {header_text} {body_text}"
        
        # Look for target emails in the content
        matched = []
        for email in target_emails:
            if email in full_content:
                matched.append(email)
                
        return matched
    except Exception as e:
        print(f"[-] Error parsing message {msg_id}: {e}")
        return []


def base64_decode(data):
    """Safely decodes base64url data."""
    if not data:
        return ""
    try:
        decoded_bytes = base64.urlsafe_b64decode(data + '=' * (4 - len(data) % 4))
        return decoded_bytes.decode('utf-8', errors='ignore')
    except Exception:
        return ""


def flag_bounced_in_csv(csv_path, bounced_emails):
    """Updates local CSV to add a 'Delivery Status' column and mark matches as 'Bounced'."""
    if not os.path.exists(csv_path):
        return 0
        
    updated_rows = []
    matches_found = 0
    
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        
        # Add 'Delivery Status' to fieldnames if not present
        if 'Delivery Status' not in fields:
            fields.append('Delivery Status')
            
        for row in reader:
            email = row['Email'].strip().lower()
            if email in bounced_emails:
                row['Delivery Status'] = 'Bounced'
                matches_found += 1
            elif not row.get('Delivery Status'):
                row['Delivery Status'] = 'Sent'
            updated_rows.append(row)
            
    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(updated_rows)
        
    return matches_found


def flag_bounced_in_sheets(sheets_service, sheet_id, sheet_name, bounced_emails):
    """Updates Google Sheets worksheet to flag matching emails as 'Bounced' in a 'Delivery Status' column."""
    try:
        # 1. Read sheet values
        range_name = f"'{sheet_name}'!A1:Z500"
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        
        rows = result.get('values', [])
        if not rows:
            return 0
            
        header = rows[0]
        
        # Find Email column index
        if 'Email' not in header:
            print(f"[-] 'Email' column not found in Google Sheets tab '{sheet_name}'.")
            return 0
        email_idx = header.index('Email')
        
        # Find or create 'Delivery Status' column index
        if 'Delivery Status' not in header:
            header.append('Delivery Status')
            status_idx = len(header) - 1
            # Write new header back
            sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"'{sheet_name}'!A1",
                valueInputOption='RAW',
                body={'values': [header]}
            ).execute()
        else:
            status_idx = header.index('Delivery Status')
            
        # Track rows to update
        updates = 0
        for i in range(1, len(rows)):
            row = rows[i]
            # Ensure row length matches header
            while len(row) < len(header):
                row.append("")
                
            email = row[email_idx].strip().lower()
            if email in bounced_emails:
                row[status_idx] = 'Bounced'
                # Update this specific cell
                # Column letter calculation
                col_letter = chr(65 + status_idx)
                cell_range = f"'{sheet_name}'!{col_letter}{i+1}"
                sheets_service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range=cell_range,
                    valueInputOption='RAW',
                    body={'values': [['Bounced']]}
                ).execute()
                updates += 1
                
        return updates
    except Exception as e:
        print(f"[-] Error updating Google Sheet tab '{sheet_name}': {e}")
        return 0


def trash_message(gmail_service, msg_id):
    """Trashes the processed bounce message so it is not processed on subsequent runs."""
    try:
        gmail_service.users().messages().trash(userId='me', id=msg_id).execute()
        return True
    except Exception as e:
        print(f"[-] Error trashing message {msg_id}: {e}")
        return False


def run_purger():
    print("====================================================")
    print("        MyCity Bounce Mail Purging Tool              ")
    print("====================================================")
    
    creds = get_creds()
    if not creds:
        return
        
    gmail_service = build('gmail', 'v1', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    
    print("[+] Searching for bounce emails...")
    messages = search_bounce_emails(gmail_service)
    print(f"[+] Found {len(messages)} potential bounce email notifications.")
    
    if not messages:
        print("[+] No bounce notifications found. Your lists are clean.")
        return
        
    target_emails = load_target_emails()
    print(f"[+] Loaded {len(target_emails)} target outreach emails to check for bounces.")
    
    all_bounced_emails = []
    messages_to_trash = []
    
    for m in messages:
        bounces = find_matched_bounces(gmail_service, m, target_emails)
        if bounces:
            print(f"  Processed bounce email {m['id']}: matched target recipient(s) {bounces}")
            all_bounced_emails.extend(bounces)
            messages_to_trash.append(m['id'])
            
    all_bounced_emails = list(set(all_bounced_emails))
    print(f"\n[+] Total unique target bounced recipients matched: {len(all_bounced_emails)}")
    if not all_bounced_emails:
        print("[+] No matching outreach bounces found in these notifications.")
        return
        
    print("\n--- Task 1: Updating Local CSV Databases ---")
    city_csv_updates = flag_bounced_in_csv(CITY_CSV, all_bounced_emails)
    vendor_csv_updates = flag_bounced_in_csv(VENDOR_CSV, all_bounced_emails)
    print(f"[+] Marked {city_csv_updates} bounced contacts in {CITY_CSV}")
    print(f"[+] Marked {vendor_csv_updates} bounced contacts in {VENDOR_CSV}")
    
    # Check Sheets
    if SPREADSHEET_ID:
        print(f"\n--- Task 2: Updating Google Sheets ({SPREADSHEET_ID}) ---")
        city_sheet_updates = flag_bounced_in_sheets(sheets_service, SPREADSHEET_ID, 'City Employees', all_bounced_emails)
        vendor_sheet_updates = flag_bounced_in_sheets(sheets_service, SPREADSHEET_ID, 'Vendor Employees', all_bounced_emails)
        print(f"[+] Flagged {city_sheet_updates} bounced rows in Google Sheets 'City Employees'")
        print(f"[+] Flagged {vendor_sheet_updates} bounced rows in Google Sheets 'Vendor Employees'")
    else:
        print("\n[-] Google Sheets update skipped: 'spreadsheet_id' not found in config.json.")
        
    print("\n--- Task 3: Trashing Processed Bounce Notifications ---")
    trashed_count = 0
    for msg_id in messages_to_trash:
        if trash_message(gmail_service, msg_id):
            trashed_count += 1
    print(f"[+] Trashed {trashed_count} bounce notifications in Gmail.")
    
    print("\n[+] Done! Bounce status sync completed successfully.")


if __name__ == '__main__':
    run_purger()

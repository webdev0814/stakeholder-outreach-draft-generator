import os
import csv
import json
import base64
import html
from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Scopes required: Google Sheets write/read and Gmail Compose (creates drafts but cannot send)
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/gmail.compose'
]

# File paths
CITY_CSV = 'city_employees_outreach.csv'
VENDOR_CSV = 'vendor_employees_outreach.csv'
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
CONFIG_FILE = 'config.json'

# Default placeholders (loaded from config.json if available)
SENDER_NAME = "[Your Name]"
SENDER_EMAIL = "[Your Email]"
SENDER_LINKEDIN = "linkedin.com/in/jasonsantpmp"
SENDER_WEBSITE = "https://jasonsant.dev"
SENDER_SIGNATURE = (
    "[Your Name] - Public Sector Specialist\n"
    "PMP | CSM | CBAP | SAFe\n\n"
    "Project Leadership \u2022 Data-Driven Strategy \u2022 Process Improvement\n\n"
    "Linkedin: linkedin.com/in/jasonsantpmp\n"
    "Website:  https://jasonsant.dev"
)

# Load config if exists
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as cf:
            config_data = json.load(cf)
            SENDER_NAME = config_data.get('sender_name', SENDER_NAME)
            SENDER_EMAIL = config_data.get('sender_email', SENDER_EMAIL)
            SENDER_LINKEDIN = config_data.get('sender_linkedin', SENDER_LINKEDIN)
            SENDER_WEBSITE = config_data.get('sender_website', SENDER_WEBSITE)
            SENDER_SIGNATURE = config_data.get('sender_signature', SENDER_SIGNATURE)
    except Exception as e:
        print(f"Warning: Could not parse config.json: {e}")

# --- EMAIL TEMPLATES MAP ---
TEMPLATES = {
    'ACS': {
        'subject': "Reconnecting / MyCity Child Care contract opportunities",
        'body': (
            "Hi {first_name},\n\n"
            "I hope you're doing well.\n\n"
            "My contract as the BA Lead Engineer & SAFe Release Train Engineer for the MyCity platform recently ended due to the city budget cuts.\n\n"
            "I really enjoyed working with the ACS team on the Child Care site. As I look for my next contract engagement, do you know of any open BA, PM, or RTE opportunities within ACS or other city orgs?\n\n"
            "I have excellent letters of recommendation from my OTI supervisors that I can share. Any leads or connections would be greatly appreciated.\n\n"
            "Best regards,\n\n"
            "{sender_signature}"
        )
    },
    'SBS': {
        'subject': "City Contract Opportunities – BA/RTE",
        'body': (
            "Hi {first_name},\n\n"
            "I hope you're doing well.\n\n"
            "My contract as the BA Lead Engineer & SAFe Release Train Engineer on the MyCity platform recently ended due to the city budget cuts.\n\n"
            "As I explore my next contract opportunity, I wanted to ask if SBS has any open contracts or upcoming initiatives that need a Senior BA, PM, or RTE? I would appreciate any advice or connections you might be able to share.\n\n"
            "I have strong letters of recommendation from my OTI supervisors. Thanks for your time!\n\n"
            "Best regards,\n\n"
            "{sender_signature}"
        )
    },
    'City Hall': {
        'subject': "MyCity Platform – Next Contract Opportunities",
        'body': (
            "Hi {first_name},\n\n"
            "I hope you're doing well.\n\n"
            "My contract as the BA Lead/SAFe Release Train Engineer for the MyCity platform recently wrapped up due to budget cuts.\n\n"
            "I enjoyed supporting the platform's delivery and creating leadership dashboards. I'm now looking for my next contract role. Given your vantage point at City Hall, do you know of any project management, business analysis, or agile delivery contracts open across the city?\n\n"
            "I have strong recommendation letters from my OTI managers that I can share. Thanks so much for your time.\n\n"
            "Best regards,\n\n"
            "{sender_signature}"
        )
    },
    'Generic_City': {
        'subject': "Reconnecting from MyCity / Contract Opportunities",
        'body': (
            "Hi {first_name},\n\n"
            "I hope you're doing well.\n\n"
            "My contract as the BA Lead/SAFe Release Train Engineer for the MyCity platform was recently cut short due to city budget constraints.\n\n"
            "I really valued working on the platform's agency integrations. I'm now looking for my next contract role. Do you happen to know if {org_name} has any active or upcoming contracts for a Senior BA, Agile PM, or RTE?\n\n"
            "I have excellent references from my supervisors at OTI. Thanks for your time and support!\n\n"
            "Best regards,\n\n"
            "{sender_signature}"
        )
    },
    'MTX': {
        'subject': "OTI Project Reconnect – MTX Opportunities",
        'body': (
            "Hi {first_name},\n\n"
            "I hope things are going well.\n\n"
            "My contract as the BA Lead Engineer and Release Train Engineer on the MyCity platform recently ended due to budget cuts. Since we both worked on the OTI project for NYC, I wanted to reach out.\n\n"
            "I am looking for my next role and know MTX is heavily involved in public sector contracts. Do you know if MTX has any current openings for Senior BAs, PMs, or Scrum Masters that I could be referred to?\n\n"
            "I have strong letters of recommendation from my OTI supervisors that I can share. Thanks for your time and help!\n\n"
            "Best,\n\n"
            "{sender_signature}"
        )
    },
    'EY': {
        'subject': "OTI Project Reconnect / EY Opportunities",
        'body': (
            "Hi {first_name},\n\n"
            "I hope you're doing well.\n\n"
            "My contract as the BA Lead Engineer & SAFe Release Train Engineer on the MyCity platform recently ended due to budget cuts. Since we both worked on the OTI project for NYC, I wanted to reach out.\n\n"
            "I am actively searching for my next opportunity. Do you know if EY has any open project/program management, business analyst, or agile delivery roles in your practice? If so, I would be very grateful for a referral or introduction.\n\n"
            "I have letters of recommendation from my former managers at OTI. Thanks for your time!\n\n"
            "Best,\n\n"
            "{sender_signature}"
        )
    },
    'Deloitte': {
        'subject': "OTI Project Reconnect – Deloitte Opportunities",
        'body': (
            "Hi {first_name},\n\n"
            "I hope all is well.\n\n"
            "My contract as the BA Lead Engineer & SAFe Release Train Engineer on the MyCity platform recently ended due to budget cuts. Since we both worked on the OTI project for NYC, I wanted to reach out.\n\n"
            "I am exploring my next role and wanted to see if Deloitte has any open contracts or permanent roles for Senior BAs, PMs, or Agile coaches. If so, I would appreciate a referral or connection. I have strong letters of recommendation from my former supervisors at OTI.\n\n"
            "Thanks so much for your time.\n\n"
            "Best,\n\n"
            "{sender_signature}"
        )
    },
    'Maureen Data Systems': {
        'subject': "OTI Project Reconnect – MDS Opportunities",
        'body': (
            "Hi {first_name},\n\n"
            "I hope you're doing well.\n\n"
            "My contract as the BA Lead Engineer & Release Train Engineer on the MyCity platform recently ended due to budget cuts. Since we both worked on the OTI project for NYC, I wanted to reach out.\n\n"
            "I am seeking my next opportunity. Do you know if MDS has any project management, business analysis, or service delivery positions open where a referral from you might help?\n\n"
            "I have letters of recommendation from my former managers at OTI. Thanks for your time!\n\n"
            "Best,\n\n"
            "{sender_signature}"
        )
    },
    'Generic_Vendor': {
        'subject': "OTI Project Reconnect / Job Opportunities",
        'body': (
            "Hi {first_name},\n\n"
            "I hope you're doing well.\n\n"
            "My contract as the BA Lead Engineer & Release Train Engineer on the MyCity platform recently ended due to budget cuts. Since we both worked on the OTI project for NYC, I wanted to reach out.\n\n"
            "I am looking for my next role. Does your organization have any open contracts or full-time roles in project management, agile delivery, or business analysis that might be a fit? I'd be very grateful for a referral or any advice.\n\n"
            "I have letters of recommendation from my former supervisors at OTI. Thanks for your time!\n\n"
            "Best,\n\n"
            "{sender_signature}"
        )
    }
}


def get_gmail_creds():
    """Handles OAuth2 authentication and returns credentials."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"Error: '{CREDENTIALS_FILE}' is missing.")
                print("Please follow the instructions in agent_workflow_contract.md to create it.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save credentials for next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return creds


def text_to_html(text_body):
    """Converts plain text to HTML, dynamically hyperlinking LinkedIn and Website fields."""
    # Escape HTML special characters
    html_content = html.escape(text_body)
    
    # Hyperlink the LinkedIn URL dynamically
    if SENDER_LINKEDIN and SENDER_LINKEDIN != "[Your LinkedIn]":
        linkedin_url = SENDER_LINKEDIN if SENDER_LINKEDIN.startswith("http") else f"https://{SENDER_LINKEDIN}"
        # We search for the escaped plain text and replace it with a clickable link
        escaped_linkedin = html.escape(SENDER_LINKEDIN)
        html_content = html_content.replace(
            escaped_linkedin, 
            f'<a href="{linkedin_url}">{escaped_linkedin}</a>'
        )
        
    # Hyperlink the Website URL dynamically
    if SENDER_WEBSITE and SENDER_WEBSITE != "[Your Website]":
        website_url = SENDER_WEBSITE if SENDER_WEBSITE.startswith("http") else f"https://{SENDER_WEBSITE}"
        escaped_website = html.escape(SENDER_WEBSITE)
        html_content = html_content.replace(
            escaped_website, 
            f'<a href="{website_url}">{escaped_website}</a>'
        )
        
    # Replace plain text newlines with HTML line breaks
    html_content = html_content.replace('\n', '<br>')
    return html_content


def create_draft(service, to_email, subject, plain_body):
    """Creates a draft email (Multipart Plain/HTML) in the Gmail drafts folder."""
    try:
        message = EmailMessage()
        message['To'] = to_email
        message['Subject'] = subject
        
        # Set the plain text alternative
        message.set_content(plain_body)
        
        # Convert plain text to HTML and add as HTML alternative
        html_body = text_to_html(plain_body)
        message.add_alternative(html_body, subtype='html')
        
        # Raw email string needs to be base64url encoded
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        draft = {
            'message': {
                'raw': raw_message
            }
        }
        
        service.users().drafts().create(userId="me", body=draft).execute()
        return True
    except HttpError as error:
        print(f"An error occurred: {error}")
        return False


def get_template_and_details(contact, is_city=True):
    """Selects and formats the template for a contact."""
    org = contact['Organization']
    first_name = contact['First Name']
    
    if is_city:
        if org in TEMPLATES:
            subject = TEMPLATES[org]['subject']
            body = TEMPLATES[org]['body'].format(
                first_name=first_name,
                sender_signature=SENDER_SIGNATURE
            )
        else:
            subject = TEMPLATES['Generic_City']['subject']
            body = TEMPLATES['Generic_City']['body'].format(
                first_name=first_name,
                org_name=org,
                sender_signature=SENDER_SIGNATURE
            )
    else:
        # Check if the specific vendor organization template exists
        if org in TEMPLATES:
            subject = TEMPLATES[org]['subject']
            body = TEMPLATES[org]['body'].format(
                first_name=first_name,
                sender_signature=SENDER_SIGNATURE
            )
        else:
            subject = TEMPLATES['Generic_Vendor']['subject']
            body = TEMPLATES['Generic_Vendor']['body'].format(
                first_name=first_name,
                org_name=org,
                sender_signature=SENDER_SIGNATURE
            )
            
    return subject, body


def upload_to_google_sheets(creds):
    """Creates a Google Sheet and uploads both lists as separate worksheets."""
    try:
        sheets_service = build('sheets', 'v4', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)
        
        # 1. Create a new Spreadsheet
        spreadsheet_body = {
            'properties': {
                'title': 'MyCity Outreach Directory'
            }
        }
        spreadsheet = sheets_service.spreadsheets().create(
            body=spreadsheet_body,
            fields='spreadsheetId,spreadsheetUrl'
        ).execute()
        
        spreadsheet_id = spreadsheet.get('spreadsheetId')
        spreadsheet_url = spreadsheet.get('spreadsheetUrl')
        print(f"\n[+] Created Google Sheet: {spreadsheet_url}")
        
        # 2. Add worksheets for City and Vendor lists
        # By default, a spreadsheet has one sheet ("Sheet1"). Let's rename it to "City Employees Outreach".
        # And add another sheet called "Vendor Employees Outreach".
        
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                'requests': [
                    {
                        'updateSheetProperties': {
                            'properties': {
                                'sheetId': 0,
                                'title': 'City Employees'
                            },
                            'fields': 'title'
                        }
                    },
                    {
                        'addSheet': {
                            'properties': {
                                'title': 'Vendor Employees'
                            }
                        }
                    }
                ]
            }
        ).execute()
        
        # 3. Read CSVs and write them to Google Sheets
        for csv_file, sheet_name in [(CITY_CSV, 'City Employees'), (VENDOR_CSV, 'Vendor Employees')]:
            if not os.path.exists(csv_file):
                print(f"[-] CSV file {csv_file} not found. Skipping...")
                continue
                
            with open(csv_file, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                data = list(reader)
                
            range_name = f"'{sheet_name}'!A1"
            body = {
                'values': data
            }
            sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            print(f"[+] Loaded {len(data) - 1} contacts into '{sheet_name}' sheet.")
            
        return spreadsheet_url
    except Exception as e:
        print(f"[-] Error uploading to Google Sheets: {e}")
        return None


def run_outreach(test_mode=True):
    print("====================================================")
    print("        MyCity Outreach Automation Tool             ")
    print("====================================================")
    
    print(f"Using Signature:\n{SENDER_SIGNATURE}\n")
    
    creds = get_gmail_creds()
    if not creds:
        return
        
    print("\n[+] Authentication Successful.")
    
    # Task 1: Upload to Google Sheets
    print("\n--- Task 1: Uploading Contacts to Google Sheets ---")
    sheet_url = upload_to_google_sheets(creds)
    
    # Task 2: Create Gmail Drafts
    print("\n--- Task 2: Generating Gmail Drafts ---")
    gmail_service = build('gmail', 'v1', credentials=creds)
    
    # Read City contacts
    city_contacts = []
    if os.path.exists(CITY_CSV):
        with open(CITY_CSV, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            city_contacts = list(reader)
            
    # Read Vendor contacts
    vendor_contacts = []
    if os.path.exists(VENDOR_CSV):
        with open(VENDOR_CSV, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            vendor_contacts = list(reader)
            
    total_contacts = len(city_contacts) + len(vendor_contacts)
    print(f"Total contacts loaded: {total_contacts} ({len(city_contacts)} City, {len(vendor_contacts)} Vendors)")
    
    if test_mode:
        print("\n[!] RUNNING IN TEST MODE (Creating drafts for first 2 City and 2 Vendor contacts only)...")
        target_city = city_contacts[:2]
        target_vendor = vendor_contacts[:2]
    else:
        print("\n[!] WARNING: Running in FULL MODE. This will create drafts for all contacts.")
        confirm = input("Are you sure you want to proceed? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Aborted.")
            return
        target_city = city_contacts
        target_vendor = vendor_contacts
        
    # Create Drafts
    drafts_created = 0
    
    print("\nCreating City outreach drafts:")
    for contact in target_city:
        subject, body = get_template_and_details(contact, is_city=True)
        to_email = contact['Email']
        full_name = contact['Full Name']
        org = contact['Organization']
        
        print(f"  Drafting email for {full_name} ({org}) -> {to_email}...")
        if create_draft(gmail_service, to_email, subject, body):
            drafts_created += 1
            
    print("\nCreating Vendor outreach drafts:")
    for contact in target_vendor:
        subject, body = get_template_and_details(contact, is_city=False)
        to_email = contact['Email']
        full_name = contact['Full Name']
        org = contact['Organization']
        
        print(f"  Drafting email for {full_name} ({org}) -> {to_email}...")
        if create_draft(gmail_service, to_email, subject, body):
            drafts_created += 1
            
    print(f"\n[+] Done! Created {drafts_created} drafts in your Drafts folder.")
    print("Please review and send them manually from your Gmail account.")


if __name__ == '__main__':
    # Defaulting to Test Mode for safety.
    # To run full mode, change to False or pass it via argument.
    import sys
    test = True
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'full':
        test = False
    run_outreach(test_mode=test)

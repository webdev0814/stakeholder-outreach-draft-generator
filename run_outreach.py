import os
import csv
import json
import base64
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
SENDER_LINKEDIN = "[Your LinkedIn]"

# Load config if exists
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as cf:
            config_data = json.load(cf)
            SENDER_NAME = config_data.get('sender_name', SENDER_NAME)
            SENDER_EMAIL = config_data.get('sender_email', SENDER_EMAIL)
            SENDER_LINKEDIN = config_data.get('sender_linkedin', SENDER_LINKEDIN)
    except Exception as e:
        print(f"Warning: Could not parse config.json: {e}")

# --- EMAIL TEMPLATES MAP ---
TEMPLATES = {
    'ACS': {
        'subject': "Reconnecting / MyCity Child Care & BA/RTE Contracts",
        'body': (
            "Hi {first_name},\n\n"
            "I hope you're doing well!\n\n"
            "I'm reaching out because my contract as the BA Lead Engineer and SAFe Release Train Engineer for the MyCity platform recently ended due to the city-wide budget cuts.\n\n"
            "It was a privilege collaborating with ACS on the MyCity Child Care initiative. During my time on the project, I focused on leading our SAFe Agile delivery, driving agentic workflow adoption, and building the reporting dashboards that leadership used to track our progress.\n\n"
            "I am actively looking for my next contract role. Since you are close to the work at ACS, I wanted to ask if you know of any open contract opportunities for a Senior Business Analyst or Release Train Engineer within ACS, or if there is a project lead you think I should connect with?\n\n"
            "For reference, I have excellent letters of recommendation from both of my former supervisors at OTI, which I'd be happy to share.\n\n"
            "Thanks so much for your time and for all your collaboration during the MyCity project.\n\n"
            "Best regards,\n\n"
            "{sender_name}\n"
            "{sender_linkedin}\n"
            "{sender_email}"
        )
    },
    'SBS': {
        'subject': "City Contract Opportunities – Business Analyst & RTE Lead",
        'body': (
            "Hi {first_name},\n\n"
            "I hope you're doing well!\n\n"
            "I recently finished my contract as the BA Lead Engineer and SAFe Release Train Engineer on the MyCity platform due to the budget cuts.\n\n"
            "I really enjoyed our cross-agency collaboration and the work we did to align stakeholders around the MyCity Business portal. Over the past two years, I led SAFe Agile coordination across our teams, defined business requirements, and created dashboard insights for leadership.\n\n"
            "I'm currently exploring my next contract role and wanted to see if SBS has any open contracts or upcoming initiatives that need a Senior BA, Project Manager, or RTE. I would appreciate any advice or connections you might be able to share.\n\n"
            "I have strong letters of recommendation from my OTI supervisors, which I'm glad to forward.\n\n"
            "Thanks for your time, and I hope we can stay in touch!\n\n"
            "Best regards,\n\n"
            "{sender_name}\n"
            "{sender_linkedin}\n"
            "{sender_email}"
        )
    },
    'City Hall': {
        'subject': "Reconnecting – MyCity Platform Delivery & Dashboards",
        'body': (
            "Hi {first_name},\n\n"
            "I hope you are having a productive week!\n\n"
            "I wanted to reach out and let you know that my contract as the BA Lead Engineer and SAFe Release Train Engineer for the MyCity platform recently wrapped up due to budget cuts.\n\n"
            "I valued our collaboration during my time on the project. I spent nearly two years driving Agile delivery across the product teams, coordinating stakeholders, and building the dashboard reporting that kept leadership and executive stakeholders updated on our releases.\n\n"
            "I am currently looking for my next contract engagement. Given your vantage point at City Hall, I wanted to see if you are aware of any open project management, business analysis, or digital transformation contracts across the city agencies?\n\n"
            "I have strong recommendation letters from both of my OTI managers that I can share. Any leads or introductions would be incredibly helpful.\n\n"
            "Thank you for your time, and thank you for your support of the MyCity platform.\n\n"
            "Best regards,\n\n"
            "{sender_name}\n"
            "{sender_linkedin}\n"
            "{sender_email}"
        )
    },
    'Generic_City': {
        'subject': "Reconnecting from MyCity / Senior BA & RTE Opportunities",
        'body': (
            "Hi {first_name},\n\n"
            "I hope you're doing well!\n\n"
            "I wanted to reach out because my contract as the BA Lead Engineer and Release Train Engineer for the MyCity platform was recently cut short due to city budget constraints.\n\n"
            "I really valued the opportunity to coordinate with your agency during our integrations on the platform. Over my two years on MyCity, I led the SAFe release coordination, gathered requirements as the BA Lead, and designed the data dashboards for project metrics.\n\n"
            "I'm now looking for my next contract engagement. Do you happen to know if {org_name} has any active or upcoming contracts for a Senior Business Analyst, Agile Project Manager, or Release Train Engineer? I would be very grateful for any leads or introductions.\n\n"
            "I have excellent references from both of my supervisors at OTI, which I'm happy to provide.\n\n"
            "Thank you for your support, and I hope to hear from you soon!\n\n"
            "Best regards,\n\n"
            "{sender_name}\n"
            "{sender_linkedin}\n"
            "{sender_email}"
        )
    },
    'MTX': {
        'subject': "Project Reconnect – MyCity Collaboration & MTX Roles",
        'body': (
            "Hi {first_name},\n\n"
            "I hope things are going well at MTX!\n\n"
            "I wanted to reach out directly—as you might know, my contract as the BA Lead Engineer and Release Train Engineer on the MyCity platform recently ended due to the budget cuts. It was an excellent run, and I thoroughly enjoyed collaborating with the MTX team on the implementation.\n\n"
            "During my time on MyCity, I worked closely with our vendor partners to lead Release Train Engineering, manage stakeholders, and design dashboard tracking for leadership.\n\n"
            "I’m looking for my next contract or permanent role. I know MTX is heavily involved in public sector and digital transformation contracts. Do you know if MTX currently has any openings for Senior Business Analysts, PMs, or Scrum Masters that I could be referred to?\n\n"
            "I have letters of recommendation from my OTI supervisors and would love to share my resume if there is an active opening.\n\n"
            "Thank you for a great partnership on MyCity, and I hope our paths cross again soon!\n\n"
            "Best,\n\n"
            "{sender_name}\n"
            "{sender_linkedin}\n"
            "{sender_email}"
        )
    },
    'EY': {
        'subject': "Reconnecting / MyCity Platform Delivery & Opportunities",
        'body': (
            "Hi {first_name},\n\n"
            "I hope you're doing well!\n\n"
            "I wanted to send a quick note to reconnect. My contract as the BA Lead Engineer and SAFe Release Train Engineer on the MyCity platform recently concluded due to the project's budget cuts. I really valued working alongside the EY/Nuvalence team to build the platform.\n\n"
            "Over the past two years, I focused on leading agile delivery, training cross-functional teams on agentic tools, and ensuring smooth stakeholder coordination.\n\n"
            "I am actively searching for my next opportunity and wanted to see if EY has any open project management, business analyst, or agile delivery roles in your practice. If so, I would be very grateful for a referral or an introduction to the hiring team.\n\n"
            "I have excellent written recommendations from both of my supervisors at OTI that I'd be happy to share.\n\n"
            "Thank you again for your collaboration, and I'd love to stay connected!\n\n"
            "Best,\n\n"
            "{sender_name}\n"
            "{sender_linkedin}\n"
            "{sender_email}"
        )
    },
    'Deloitte': {
        'subject': "Staying Connected – MyCity & Deloitte Opportunities",
        'body': (
            "Hi {first_name},\n\n"
            "I hope all is well!\n\n"
            "I wanted to reach out as my contract as the BA Lead Engineer and SAFe Release Train Engineer on the MyCity platform recently ended due to budget constraints. I really appreciated our collaboration during the Deloitte phase of the platform's delivery.\n\n"
            "During my time on the project, I led agile processes, managed business analysis requirements, and built leadership dashboards. I'm now exploring my next role and wanted to see if Deloitte has any open contracts or permanent roles for Senior BAs, PMs, or Agile coaches.\n\n"
            "If there are any relevant openings, I would be very grateful if you could refer me or connect me with the right team lead. I have strong letters of recommendation from my former managers at OTI.\n\n"
            "Thanks for the great partnership, and let's keep in touch!\n\n"
            "Best,\n\n"
            "{sender_name}\n"
            "{sender_linkedin}\n"
            "{sender_email}"
        )
    },
    'Maureen Data Systems': {
        'subject': "Project Reconnect – MyCity Common Services & MDS Roles",
        'body': (
            "Hi {first_name},\n\n"
            "I hope you're doing well!\n\n"
            "I wanted to reach out and let you know that my contract as the BA Lead Engineer and Release Train Engineer on the MyCity platform recently ended due to budget cuts. It was a pleasure collaborating with the MDS team on the Common Services support side.\n\n"
            "I am looking for my next role and wanted to see if MDS has any project management, business analysis, or service delivery positions open. If you know of any active roles, I'd appreciate a referral or if you could point me to the recruiter.\n\n"
            "I have strong letters of recommendation from my OTI supervisors, which I'm happy to send over along with my resume.\n\n"
            "Thank you for your support, and I hope we can work together again in the future!\n\n"
            "Best,\n\n"
            "{sender_name}\n"
            "{sender_linkedin}\n"
            "{sender_email}"
        )
    },
    'Generic_Vendor': {
        'subject': "Reconnecting from MyCity / Job Opportunities",
        'body': (
            "Hi {first_name},\n\n"
            "I hope you're doing well!\n\n"
            "I wanted to reach out because my contract as the BA Lead Engineer and SAFe Release Train Engineer on the MyCity platform recently concluded due to project budget cuts. I really enjoyed working alongside {org_name} on this project.\n\n"
            "I'm now seeking my next opportunity. Over the last two years, I focused on leading agile delivery, dashboard analytics for leadership, and cross-functional team alignment.\n\n"
            "Does {org_name} have any open contracts or full-time roles in project/program management, agile coaching, or business analysis that might be a good fit? I would be very grateful for a referral or any advice.\n\n"
            "I have strong written recommendations from my former supervisors at OTI.\n\n"
            "Thank you, and I hope we can stay in touch!\n\n"
            "Best,\n\n"
            "{sender_name}\n"
            "{sender_linkedin}\n"
            "{sender_email}"
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


def create_draft(service, to_email, subject, body):
    """Creates a draft email in the Gmail drafts folder."""
    try:
        message = EmailMessage()
        message.set_content(body)
        message['To'] = to_email
        message['Subject'] = subject
        
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
                sender_name=SENDER_NAME,
                sender_linkedin=SENDER_LINKEDIN,
                sender_email=SENDER_EMAIL
            )
        else:
            subject = TEMPLATES['Generic_City']['subject']
            body = TEMPLATES['Generic_City']['body'].format(
                first_name=first_name,
                org_name=org,
                sender_name=SENDER_NAME,
                sender_linkedin=SENDER_LINKEDIN,
                sender_email=SENDER_EMAIL
            )
    else:
        # Check if the specific vendor organization template exists
        if org in TEMPLATES:
            subject = TEMPLATES[org]['subject']
            body = TEMPLATES[org]['body'].format(
                first_name=first_name,
                sender_name=SENDER_NAME,
                sender_linkedin=SENDER_LINKEDIN,
                sender_email=SENDER_EMAIL
            )
        else:
            subject = TEMPLATES['Generic_Vendor']['subject']
            body = TEMPLATES['Generic_Vendor']['body'].format(
                first_name=first_name,
                org_name=org,
                sender_name=SENDER_NAME,
                sender_linkedin=SENDER_LINKEDIN,
                sender_email=SENDER_EMAIL
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
    
    print(f"Using Sender Details:\n  Name: {SENDER_NAME}\n  Email: {SENDER_EMAIL}\n  LinkedIn: {SENDER_LINKEDIN}")
    
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

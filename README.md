# MyCity Outreach Agent

An agentic automation workflow tool to segment stakeholder directories, upload them to Google Sheets, and generate customized, context-aware Gmail drafts for job outreach or relationship management.

Designed to help contractors or employees transition into new roles after project wind-downs or budget cuts, particularly within the public sector (NYC) and public-sector vendor networks (MTX, EY, Deloitte, MDS, etc.).

---

## ✨ Features
1. **Directory Segmentation & Cleaning (`process_contacts.py`)**:
   * Parses raw stakeholder CSV directories.
   * Capitalizes and cleans names dynamically.
   * Resolves empty first/last names from full name strings.
   * Identifies best contact email addresses (prefers company native emails for vendors; agency/project emails for city employees).
   * Segments contacts into separate **City** and **Vendor** lists.
   * Filters out specific domains/orgs (e.g. OTI or Microsoft) as configured.
2. **Dynamic Templating (`email_templates.md`)**:
   * Context-aware, personalized email bodies tailored to specific agencies (e.g., SBS, ACS, City Hall) or vendor firms (e.g., EY, Deloitte, MTX, Maureen Data Systems).
   * Generic fallbacks for other organizations.
3. **Google Sheets & Gmail Integration (`run_outreach.py`)**:
   * Uses OAuth2 Desktop App authentication to connect with Sheets and Gmail APIs.
   * Creates a structured Google Sheet with separate worksheets for the segmented contact directories.
   * Generates draft emails in the user's Gmail **Drafts** folder. **Strictly safe: no emails are sent directly.**

---

## 🛠️ Quick Start

### 1. Configure Local Settings
Create a `config.json` file in the root directory to store your personal details (this file is gitignored and will not be pushed to GitHub):
```json
{
  "sender_name": "Your Name, PMP",
  "sender_email": "yourname@gmail.com",
  "sender_linkedin": "linkedin.com/in/yourprofile",
  "master_csv_path": "path/to/your/stakeholder_directory.csv"
}
```

### 2. Configure Google API Credentials
Set up your Google Cloud Project and obtain client credentials. Save the credential file as `credentials.json` in the root folder.
* Detailed API and credential configuration steps can be found in [agent_workflow_contract.md](agent_workflow_contract.md).

### 3. Run the Process
First, install dependencies:
```bash
pip install google-auth-oauthlib google-api-python-client google-auth-httplib2
```

To clean the directory and split the lists:
```bash
python process_contacts.py
```

To run a test dry-run (creates 4 drafts in Gmail to verify):
```bash
python run_outreach.py
```

To run the full outreach generation (creates drafts for all segmented contacts):
```bash
python run_outreach.py full
```

---

## ⚠️ Security & Privacy
* **Gitignored Secrets**: All API tokens (`token.json`), client secrets (`credentials.json`), personal configuration details (`config.json`), and raw CSV data files (`*.csv`) are included in `.gitignore` to prevent leakage.
* **Compose-Only Scope**: The script requests the `gmail.compose` scope, meaning it is programmatically impossible for the tool to send emails. It can only write draft emails to your folder for your manual review and approval.

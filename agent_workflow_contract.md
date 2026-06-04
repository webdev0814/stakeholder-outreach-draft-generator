# Agent Workflow Contract: Google Sheets & Gmail Draft Outreach

This document serves as the **Prompt Contract** and **Instructions** for the AI Agent (Codex or Claude Code) executing the outreach automation in the local workspace.

---

## 🎯 Goal
1. **Upload Target Lists**: Load the filtered contacts (`city_employees_outreach.csv` and `vendor_employees_outreach.csv`) into a new Google Sheet named **"MyCity Outreach Directory"** under `[Your Email]`.
2. **Generate Gmail Drafts**: For each contact, select the appropriate customized agency or vendor email template and create a draft email in the Gmail drafts folder of `[Your Email]`. **No emails must be sent directly.**

---

## 🛠️ Prerequisites & Setup (To be completed by the User or Agent)

To run the automation script successfully, the following credentials and packages are required:

### 1. Enable Google APIs & Get Credentials
The script uses standard OAuth 2.0 Desktop Application flow to authenticate securely directly from the machine.
1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., "MyCity Outreach").
3. Go to **APIs & Services > Library** and enable:
   * **Google Sheets API**
   * **Gmail API**
4. Go to **APIs & Services > OAuth consent screen**:
   * Set User Type to **External**.
   * Fill out the app name and user support email.
   * Under **Test Users**, add `[Your Email]`.
5. Go to **APIs & Services > Credentials**:
   * Click **Create Credentials** > **OAuth client ID**.
   * Select application type: **Desktop App** and name it "Outreach Desktop App".
   * Click **Create**, then click the **Download JSON** icon on the credential list.
   * Save this file in the `shared-workspace/` directory as **`credentials.json`**.

### 2. Install Required Python Libraries
Run this command in the workspace terminal to install the necessary Google SDK libraries:
```bash
pip install google-auth-oauthlib google-api-python-client google-auth-httplib2
```

---

## 🚀 Execution Instructions for Codex / Claude Code

Once `credentials.json` is in the workspace directory:

### Step 1: Run Test Mode (Dry Run)
First, verify that the Sheets upload and Gmail draft creation works by running in Test Mode. This will only create **2 drafts** for city contacts and **2 drafts** for vendor contacts:
```bash
py run_outreach.py
```
* **Expected Behavior**: A browser tab will open asking you to authenticate with `[Your Email]`. Log in and grant permissions. A `token.json` file will be saved locally. The script will create the Google Sheet and 4 draft emails.

### Step 2: Review Drafts in Gmail
Open [mail.google.com](https://mail.google.com/) under `[Your Email]` and go to the **Drafts** folder. Confirm that the templates are formatted correctly and have the correct names and organizations.

### Step 3: Run Full Mode
Once satisfied with the test drafts, run the script with the `full` argument to process all 40 city employees and 262 vendor employees:
```bash
py run_outreach.py full
```
* **Expected Behavior**: The script will read all contacts from both CSVs, create the worksheets, and create drafts in Gmail.

---

## ⚠️ Safety & Constraints
* **Drafts Only**: Under no circumstances should the script attempt to send emails. The scope of authentication is limited to `gmail.compose` which allows creating drafts but enforces manual review before sending.
* **Rate Limits**: If Gmail rate limits are hit during full generation, the script will output a progress log. Simply run the script again to resume from the last contact (token cache is preserved).

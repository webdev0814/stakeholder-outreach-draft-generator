# Stakeholder Outreach Draft Generator

A human-in-the-loop workflow for cleaning stakeholder directories, segmenting contacts, synchronizing structured data with Google Sheets, and generating context-aware Gmail drafts for manual review.

## Product Context

This project demonstrates how an AI-enabled workflow can improve operational throughput without removing human accountability. The core workflow prepares drafts; the user reviews and decides whether anything is sent.

Maintained by [Jason Agentic](https://x.com/Jason_Agentic).

## Capabilities

1. **Directory preparation (`process_contacts.py`)**
   - Parses stakeholder CSV directories.
   - Normalizes names and resolves incomplete name fields.
   - Selects the best available contact address using configurable rules.
   - Segments contacts into configurable groups.
2. **Context-aware templates (`email_templates.md`)**
   - Supports organization- and relationship-specific draft language.
   - Provides a generic fallback for unmatched contacts.
3. **Sheets and Gmail integration (`run_outreach.py`)**
   - Uses OAuth 2.0 desktop authentication.
   - Creates structured worksheets for segmented contacts.
   - Creates Gmail drafts for review.

## Governance Model

```text
Source directory
      ↓
Normalize and segment
      ↓
Generate context-aware draft
      ↓
Human review
      ↓
User-controlled disposition
```

Keep production sending, scheduling, or inbox-cleanup utilities separate from the portfolio demonstration and review their configuration before use.

## Quick Start

### 1. Configure local settings

Create a gitignored `config.json`:

```json
{
  "sender_name": "Your display name",
  "sender_email": "you@example.com",
  "sender_profile": "https://example.com/profile",
  "master_csv_path": "path/to/stakeholder-directory.csv"
}
```

### 2. Configure Google APIs

Create a Google Cloud OAuth desktop client and save its downloaded credentials locally as `credentials.json`. Do not commit credentials, tokens, configuration, or contact data.

### 3. Install and run

```bash
pip install google-auth-oauthlib google-api-python-client google-auth-httplib2
python process_contacts.py
python run_outreach.py
```

Use `python run_outreach.py full` only after reviewing the segmented data and draft templates.

## Security and Privacy

- `token.json`, `credentials.json`, `config.json`, and CSV data are gitignored.
- The portfolio workflow is designed around draft generation and human review.
- Never publish contact directories, generated messages, OAuth files, logs, or organization-specific configuration.
- Validate Google scopes and local configuration before every operational use.

## License

MIT

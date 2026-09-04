# Agent Briefing: stakeholder-outreach-draft-generator

## 1. Repository Overview & Purpose
- **Repository Name**: `stakeholder-outreach-draft-generator`
- **Visibility**: `Public`
- **Default Branch**: `main`
- **Last Updated / Pushed**: 2026-09-03
- **Description**: Automated directory cleaning, DNS MX checking, sheets syncing, and throttled outreach draft generation in Gmail.
- **Context from README**: A human-in-the-loop workflow for cleaning stakeholder directories, segmenting contacts, synchronizing structured data with Google Sheets, and generating context-aware Gmail drafts for manual review. This project demonstrates how an AI-enabled workflow can improve operational throughput without remov...
- **Topics/Tags**: automation, dns, email-verification, gmail-api

---

## 2. Tech Stack & Architecture
- **Primary Language / Ecosystem**: Python
- **Key Directories**: Single root directory structure.
- **Notable Top-Level Files**: `.gitignore`, `LICENSE`, `README.md`, `SECURITY.md`, `agent_workflow_contract.md`, `email_templates.md`, `process_contacts.py`, `purge_bounces.py`, `run_outreach.py`, `run_purge_bounces.bat`, `run_send_emails.bat`, `run_verify_emails.bat`

---

## 3. Setup & Execution Commands
### Environment Setup & Installation
```bash
# Review repository files and install dependencies corresponding to the language/runtime.
```

### Running / Starting
```bash
python <entrypoint>.py
```

### Testing / Verification
```bash
# Run relevant unit/integration tests (e.g. pytest or npm test)
```

---

## 4. Recent Commit Activity (Where We Left Off)
The most recent commits show the latest development trajectory:
- `[0c5f988]` (2026-09-03) Add security reporting and repository hygiene policy
- `[851df06]` (2026-09-03) Sanitize and reposition portfolio documentation
- `[3f3c2fc]` (2026-06-12) Remove PII and add MIT license
- `[8b71200]` (2026-06-12) Implement automated outreach email sender with throttling, limits, and Task Scheduler configurator
- `[307fc59]` (2026-06-12) Optimize Google Sheets write logic using batchUpdate and add --sync support
- `[185cbdd]` (2026-06-12) Implement email verification tool (verify_emails.py) with Abstract API integration and local DNS MX checks
- `[2f6dcc8]` (2026-06-04) Implement automated email bounce purger with unified OAuth scopes and robust matching
- `[f8cc50b]` (2026-06-04) Support --yes argument to bypass confirmation prompt when running in non-interactive environments
- `[103e50a]` (2026-06-04) Add 0.5s throttling delay to run_outreach.py to ensure Google API rate limits are not exceeded
- `[2cfd48e]` (2026-06-04) Update generic vendor template phrasing and format signature links as HTML hyperlinks in drafts

---

## 5. Current State & Immediate Next Steps
- **Current State**: Project is active under branch `main`.
- **When picking up this repo**:
  1. Inspect the top-level files and recent commits to understand the active feature or bugfix context.
  2. Verify all required credentials and environment variables before running integration scripts.
  3. Ensure all tests and linting pass after making modifications.
  4. Follow the repository conventions and preserve existing architecture patterns.

---

## 6. Agent Working Guidelines & Gotchas
- **Cross-Platform Compatibility**: Code may run across Windows, macOS, or Linux agent environments. Ensure path manipulations use OS-agnostic methods (e.g. `pathlib.Path` or `path.join`).
- **Secret Hygiene**: NEVER commit plain-text API keys, tokens, or credentials into repository files.
- **Git Commit Etiquette**: Use concise, conventional commit messages (e.g., `feat:`, `fix:`, `docs:`, `refactor:`).
- **Tooling Compatibility**: This briefing is kept aligned for Antigravity (`GEMINI.md`), Claude Code / Codex (`CLAUDE.md`), and general autonomous agents (`AGENTS.md`).

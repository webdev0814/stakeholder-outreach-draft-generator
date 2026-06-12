@echo off
cd /d "%~dp0"
echo Running MyCity Outreach Email Sender...
python send_verified_emails.py
pause

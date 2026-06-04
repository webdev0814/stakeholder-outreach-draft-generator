@echo off
cd /d "%~dp0"
echo Running MyCity Outreach Bounce Purger...
python purge_bounces.py
pause

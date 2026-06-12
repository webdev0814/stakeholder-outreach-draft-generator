@echo off
echo ====================================================
echo        MyCity Task Scheduler Configurator            
echo ====================================================
echo.

echo [+] Registering Email Verification Task...
echo     Runs daily at 9:00 AM to verify the next 100 emails.
schtasks /create /tn "MyCity_Verify_Emails" /tr "py C:\Users\jason\.gemini\antigravity\scratch\shared-workspace\verify_emails.py" /sc daily /st 09:00 /f

echo.
echo [+] Registering Email Sending Task...
echo     Runs every 2 hours starting at 9:00 AM.
echo     (Internally restricts sends to 9:00 AM - 5:00 PM EST, Mon-Fri).
schtasks /create /tn "MyCity_Send_Emails" /tr "py C:\Users\jason\.gemini\antigravity\scratch\shared-workspace\send_verified_emails.py" /sc hourly /mo 2 /st 09:00 /f

echo.
echo ====================================================
echo [+] Done! Tasks registered in Windows Task Scheduler.
echo     You can view them by running 'taskschd.msc'.
echo ====================================================
pause

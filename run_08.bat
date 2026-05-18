@echo off
cd /d D:\ClaudeCode工作區\stock-tracker
set PYTHONUTF8=1

:: 從 User 環境變數讀取 Telegram 憑證
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable('TELEGRAM_BOT_TOKEN','User')"`) do set TELEGRAM_BOT_TOKEN=%%A
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable('TELEGRAM_CHAT_ID','User')"`) do set TELEGRAM_CHAT_ID=%%A

C:\Users\nicks\AppData\Local\Programs\Python\Python314\python.exe scripts\fetch_asia.py >> logs\run_08.log 2>&1
C:\Users\nicks\AppData\Local\Programs\Python\Python314\python.exe scripts\notify_line.py >> logs\run_08.log 2>&1

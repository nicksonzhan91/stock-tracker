@echo off
cd /d D:\ClaudeCode工作區\stock-tracker
set PYTHONUTF8=1
C:\Users\nicks\AppData\Local\Programs\Python\Python314\python.exe scripts\fetch_options.py >> logs\run_monthly.log 2>&1

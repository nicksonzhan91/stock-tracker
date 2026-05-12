@echo off
cd /d D:\ClaudeCode工作區\stock-tracker
set PYTHONUTF8=1
C:\Users\nicks\AppData\Local\Programs\Python\Python314\python.exe scripts\fetch_institutional.py >> logs\run_18.log 2>&1
C:\Users\nicks\AppData\Local\Programs\Python\Python314\python.exe scripts\calc_indicators.py >> logs\run_18.log 2>&1
call D:\ClaudeCode工作區\stock-tracker\push_github.bat >> logs\run_18.log 2>&1

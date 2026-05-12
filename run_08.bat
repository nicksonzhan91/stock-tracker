@echo off
cd /d D:\ClaudeCode工作區\stock-tracker
set PYTHONUTF8=1
C:\Users\nicks\AppData\Local\Programs\Python\Python314\python.exe scripts\fetch_asia.py >> logs\run_08.log 2>&1
C:\Users\nicks\AppData\Local\Programs\Python\Python314\python.exe scripts\notify_line.py >> logs\run_08.log 2>&1

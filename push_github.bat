@echo off
cd /d D:\ClaudeCode工作區\stock-tracker
git add data/latest.json
git diff --cached --quiet && (echo [GitHub] latest.json 無變動，略過 push) || (
    git commit -m "data: update latest.json %date% %time%"
    git push origin main
    echo [GitHub] Push 完成
)

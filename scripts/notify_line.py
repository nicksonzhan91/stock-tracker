"""
notify_line.py — 發送通知（08:00 執行）
支援：Telegram Bot（主要）
環境變數：
  TELEGRAM_BOT_TOKEN  — Telegram Bot Token
  TELEGRAM_CHAT_ID    — Telegram Chat ID
  DASHBOARD_URL       — Dashboard 網址（選填）
"""

import os
import sys
import json
from datetime import datetime
import requests

sys.stdout.reconfigure(encoding="utf-8")

DATA_FILE     = os.path.join(os.path.dirname(__file__), "..", "data", "latest.json")
DASHBOARD_URL = os.environ.get(
    "DASHBOARD_URL",
    "file:///D:/ClaudeCode%E5%B7%A5%E4%BD%9C%E5%8D%80/stock-tracker/web/index.html"
)


def send_telegram(message: str, token: str, chat_id: str):
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
    if resp.status_code == 200:
        print("Telegram 通知發送成功")
    else:
        print(f"[錯誤] Telegram 發送失敗: {resp.status_code} {resp.text}")


def build_message(data: dict, date_str: str) -> str:
    """組合完整的每日摘要訊息"""
    lines = [f"📊 {date_str} 台股市場摘要"]
    lines.append("")

    # 美股
    us = data.get("us_indices", {})
    if us:
        lines.append("🇺🇸 美股")
        for sym, v in us.items():
            sign = "+" if v["change"] >= 0 else ""
            lines.append(f"  {v['name']}: {v['close']:,.0f}  {sign}{v['change_pct']:.2f}%")

    # 亞股
    asia = data.get("asia_indices", {})
    if asia:
        lines.append("")
        lines.append("🌏 亞股")
        for sym, v in asia.items():
            sign = "+" if v["change"] >= 0 else ""
            lines.append(f"  {v['name']}: {v['close']:,.0f}  {sign}{v['change_pct']:.2f}%")

    lines.append("")
    lines.append(f"🔗 詳細資料 → {DASHBOARD_URL}")
    return "\n".join(lines)


def main():
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("[錯誤] 未設定環境變數 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
        print("請執行以下指令設定（在 PowerShell）：")
        print('  [System.Environment]::SetEnvironmentVariable("TELEGRAM_BOT_TOKEN", "你的Token", "User")')
        print('  [System.Environment]::SetEnvironmentVariable("TELEGRAM_CHAT_ID", "你的ChatID", "User")')
        return

    # 讀取最新資料
    date_str = datetime.now().strftime("%Y-%m-%d")
    data = {}
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 2:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        date_str = data.get("date", date_str)

    message = build_message(data, date_str)
    print(f"發送訊息:\n{message}\n")
    send_telegram(message, token, chat_id)


if __name__ == "__main__":
    main()

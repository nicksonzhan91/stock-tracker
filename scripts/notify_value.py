"""
notify_value.py — 價值低估區 Telegram 通知
每日 18:xx 由 run_18.bat 呼叫，於 export_value_excel.py 之後執行。

讀取 data/value_zone.json，與上次結果比對，發送：
  - 新進入低估區的股票（★新進入）
  - 離開低估區的股票
"""

import os
import sys
import json
import shutil
import requests

sys.stdout.reconfigure(encoding="utf-8")

ZONE_FILE      = os.path.join(os.path.dirname(__file__), "..", "data", "value_zone.json")
ZONE_PREV_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "value_zone_prev.json")
DASHBOARD_URL  = os.environ.get(
    "DASHBOARD_URL",
    "https://nicksonzhan91.github.io/stock-tracker/web/index.html"
)


def send_telegram(message: str, token: str, chat_id: str):
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": message,
                                    "parse_mode": "HTML"}, timeout=10)
    if resp.status_code == 200:
        print("Telegram 價值通知發送成功")
    else:
        print(f"[錯誤] Telegram 發送失敗: {resp.status_code} {resp.text}")


def build_message(current: dict, prev: dict | None) -> str:
    date_str     = current["date"]
    zone_stocks  = current["stocks"]
    total_stocks = current["total"]

    cur_ids  = {s["stock_id"] for s in zone_stocks}
    prev_ids = {s["stock_id"] for s in prev["stocks"]} if prev else set()

    new_entries = cur_ids - prev_ids
    exits       = prev_ids - cur_ids

    lines = [f"📈 <b>{date_str} 價值低估區報告</b>"]
    lines.append(f"監控 {total_stocks} 支 → 低估區 <b>{len(zone_stocks)}</b> 支")
    lines.append("")

    # 新進入提示
    if new_entries:
        lines.append(f"🆕 <b>新進入低估區（{len(new_entries)} 支）</b>")
        for s in zone_stocks:
            if s["stock_id"] in new_entries:
                lines.append(
                    f"  ★ {s['stock_id']} {s['name']}　"
                    f"現價 {s['price']:.1f} / 合理買入 {s['buy_target']:.1f}　"
                    f"潛在+{s['ratio']:.1f}%"
                )
        lines.append("")

    # 離開提示
    if exits and prev:
        prev_map = {s["stock_id"]: s for s in prev["stocks"]}
        lines.append(f"📤 <b>離開低估區（{len(exits)} 支）</b>")
        for sid in exits:
            s = prev_map[sid]
            lines.append(f"  {s['stock_id']} {s['name']}")
        lines.append("")

    lines.append("")
    lines.append(f"🔗 {DASHBOARD_URL}")
    return "\n".join(lines)


def main():
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("[錯誤] 未設定環境變數 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
        return

    if not os.path.exists(ZONE_FILE):
        print(f"[錯誤] 找不到 {ZONE_FILE}，請先執行 export_value_excel.py")
        return

    with open(ZONE_FILE, "r", encoding="utf-8-sig") as f:
        current = json.load(f)

    prev = None
    if os.path.exists(ZONE_PREV_FILE):
        with open(ZONE_PREV_FILE, "r", encoding="utf-8-sig") as f:
            prev = json.load(f)

    message = build_message(current, prev)
    print(f"發送訊息:\n{message}\n")
    send_telegram(message, token, chat_id)

    # 更新 prev 檔（本次結果存為下次比對基準）
    shutil.copy2(ZONE_FILE, ZONE_PREV_FILE)
    print(f"已更新基準檔 → {os.path.basename(ZONE_PREV_FILE)}")


if __name__ == "__main__":
    main()

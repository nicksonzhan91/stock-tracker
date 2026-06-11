"""
fetch_asia.py — 抓取日韓即時指數（08:00 執行）
來源：Yahoo Finance (yfinance)
標的：^N225, ^KS11
"""

import json
import math
import os
import sys
from datetime import datetime
import yfinance as yf

sys.stdout.reconfigure(encoding="utf-8")

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "latest.json")

TICKERS = {
    "^N225": "日經 225",
    "^KS11": "韓國綜合",
}


def fetch_asia_indices():
    result = {}
    for symbol, name in TICKERS.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if len(hist) < 2:
                print(f"[警告] {symbol} 資料不足")
                continue

            close = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2])
            if math.isnan(close) or math.isnan(prev_close):
                print(f"[警告] {symbol} 收到 NaN，略過")
                continue
            change = close - prev_close
            change_pct = change / prev_close * 100

            result[symbol] = {
                "name":       name,
                "close":      round(close, 2),
                "change":     round(change, 2),
                "change_pct": round(change_pct, 2),
            }
            print(f"{name}({symbol}): {close:.2f}  {change:+.2f}  {change_pct:+.2f}%")
        except Exception as e:
            print(f"[錯誤] {symbol}: {e}")

    return result


def main():
    asia_data = fetch_asia_indices()

    data = {}
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 2:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    data["asia_indices"] = asia_data
    data["asia_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n已寫入 {DATA_FILE}")


if __name__ == "__main__":
    main()

"""
fetch_options.py — 抓取台指選擇權壓力/支撐履約價（每月第三週四 20:00 執行）
來源：TAIFEX optDailyMarketReport
方法：各近月合約（非週選擇權）的成交量，取 Call 最大履約價 → 壓力，Put 最大 → 支撐
注意：TAIFEX 每日行情表不提供各履約價 OI，改以成交量作為市場關注度指標
"""

import json
import os
import sys
from datetime import datetime, timedelta
import requests
import urllib3
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "latest.json")

TAIFEX_OPT_MKT = "https://www.taifex.com.tw/cht/3/optDailyMarketReport"
TWSE_FMTQIK    = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?response=json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def _last_trading_date() -> str:
    """從 TWSE 取最近一個交易日（格式 YYYY/MM/DD）"""
    try:
        resp = requests.get(TWSE_FMTQIK, headers=HEADERS, timeout=15, verify=False)
        rows = resp.json().get("data", [])
        if rows:
            roc   = rows[-1][0]   # e.g. "115/05/08"
            parts = roc.split("/")
            year  = int(parts[0]) + 1911
            return f"{year}/{parts[1]}/{parts[2]}"
    except Exception:
        pass
    return datetime.now().strftime("%Y/%m/%d")


def fetch_strike_volumes(session: requests.Session, query_date: str) -> tuple:
    """
    從 TAIFEX optDailyMarketReport 取各履約價成交量
    只取近月（非週選擇權，不含 'W'）
    回傳 (resistance: int, support: int)
    """
    resistance = None
    support    = None

    try:
        resp = session.post(TAIFEX_OPT_MKT, data={
            "queryStartDate": query_date,
            "queryEndDate":   query_date,
            "commodityId":    "TXO",
        }, timeout=30)
        soup = BeautifulSoup(resp.text, "html.parser")

        call_vol = {}
        put_vol  = {}

        for tbl in soup.find_all("table"):
            rows = tbl.find_all("tr")
            if len(rows) < 10:
                continue

            header = [td.get_text(strip=True) for td in rows[0].find_all(["td", "th"])]
            if "履約價" not in header:
                continue

            for tr in rows[1:]:
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if len(cells) < 13:
                    continue

                expiry = cells[1]
                if "W" in expiry or "F" in expiry:  # 跳過週選擇權
                    continue
                if not expiry[:4].isdigit():
                    continue

                strike_str = cells[3]
                cp         = cells[4]
                vol_str    = cells[12].replace(",", "").replace("-", "0")

                try:
                    strike = int(strike_str)
                    vol    = int(vol_str)
                except ValueError:
                    continue

                if vol <= 0:
                    continue

                if cp == "Call":
                    call_vol[strike] = call_vol.get(strike, 0) + vol
                elif cp == "Put":
                    put_vol[strike] = put_vol.get(strike, 0) + vol

            break  # 只處理第一個符合的表格

        if call_vol:
            resistance = max(call_vol, key=call_vol.get)
            print(f"壓力（Call 成交量最大履約價）: {resistance}  "
                  f"（成交量 {call_vol[resistance]:,} 口）")

        if put_vol:
            support = max(put_vol, key=put_vol.get)
            print(f"支撐（Put  成交量最大履約價）: {support}  "
                  f"（成交量 {put_vol[support]:,} 口）")

        # 印 Top3 供參考
        if call_vol:
            top3c = sorted(call_vol.items(), key=lambda x: x[1], reverse=True)[:3]
            print(f"Call Top3: {top3c}")
        if put_vol:
            top3p = sorted(put_vol.items(), key=lambda x: x[1], reverse=True)[:3]
            print(f"Put  Top3: {top3p}")

    except Exception as e:
        print(f"[錯誤] 履約價成交量: {e}")

    return resistance, support


def main():
    print("=== 抓取選擇權壓力/支撐（每月第三週四）===")

    session = requests.Session()
    session.verify = False
    session.headers.update(HEADERS)
    session.get(TAIFEX_OPT_MKT, timeout=15)

    query_date = _last_trading_date()
    print(f"查詢日期: {query_date}")

    resistance, support = fetch_strike_volumes(session, query_date)

    data = {}
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 2:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    data["options_strikes"] = {
        "resistance": resistance,
        "support":    support,
        "month":      datetime.now().strftime("%Y-%m"),
        "updated":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note":       "以近月合約成交量最大履約價代替 OI",
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n已寫入 {DATA_FILE}")


if __name__ == "__main__":
    main()

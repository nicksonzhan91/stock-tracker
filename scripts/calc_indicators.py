"""
calc_indicators.py — 計算均線（EMA11, EMA24, SMA60）與 P/C 比均線（3MA, 10MA）
資料來源：
  - 加權指數收盤 & 台股成交量：TWSE FMTQIK
  - 歷史回補：yfinance ^TWII
  - 大台成交量：TAIFEX futDailyMarketReport
  - P/C 比：TAIFEX pcRatio（HTML）
"""

import json
import os
import sys
from datetime import datetime, timedelta
import requests
import urllib3
import yfinance as yf
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATA_FILE       = os.path.join(os.path.dirname(__file__), "..", "data", "latest.json")
HISTORY_DIR     = os.path.join(os.path.dirname(__file__), "..", "data", "history")
HISTORY_TAIEX   = os.path.join(HISTORY_DIR, "taiex_close.json")
HISTORY_PC      = os.path.join(HISTORY_DIR, "pc_ratio.json")

TWSE_FMTQIK  = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?response=json"
TAIFEX_PC    = "https://www.taifex.com.tw/cht/3/pcRatio"
TAIFEX_VOL   = "https://www.taifex.com.tw/cht/3/futDailyMarketReport"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


# ── 工具函式 ──────────────────────────────────────────────

def _num(s: str) -> float:
    s = str(s).strip().replace(",", "").replace("%", "").replace(" ", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_history(path: str) -> list:
    os.makedirs(HISTORY_DIR, exist_ok=True)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(path: str, data: list):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def calc_ema(prices: list, period: int) -> int | None:
    if len(prices) < period:
        return None
    k = 2 / (period + 1)
    ema = prices[0]
    for p in prices[1:]:
        ema = p * k + ema * (1 - k)
    return round(ema)


def calc_sma(prices: list, period: int) -> int | None:
    if len(prices) < period:
        return None
    return round(sum(prices[-period:]) / period)


def calc_ma(values: list, period: int) -> float | None:
    if len(values) < period:
        return None
    return round(sum(values[-period:]) / period, 2)


# ── 加權指數收盤 & 台股成交量（TWSE FMTQIK） ────────────────

def fetch_taiex_from_twse() -> tuple:
    """回傳 (close: float, volume_yi: float)"""
    try:
        resp = requests.get(TWSE_FMTQIK, headers=HEADERS, timeout=15, verify=False)
        resp.raise_for_status()
        rows = resp.json().get("data", [])
        if not rows:
            return None, None
        last = rows[-1]
        close     = _num(last[4])                     # 發行量加權股價指數
        vol_yi    = round(_num(last[2]) / 1e8, 0)     # 成交金額（元）→ 億元
        return close, vol_yi
    except Exception as e:
        print(f"[錯誤] 加權指數/台股成交量: {e}")
        return None, None


# ── 歷史資料回補（yfinance ^TWII） ──────────────────────────

def backfill_taiex_history(existing: list) -> list:
    """若歷史資料不足 60 筆，用 yfinance 補齊最近 120 個交易日"""
    if len(existing) >= 60:
        return existing

    print("歷史資料不足 60 筆，從 yfinance 回補...")
    try:
        twii = yf.Ticker("^TWII")
        df   = twii.history(period="150d")
        new_hist = []
        for dt_idx, row in df.iterrows():
            date_str = dt_idx.strftime("%Y-%m-%d")
            new_hist.append({"date": date_str, "close": round(float(row["Close"]), 2)})

        # 合併：以 yfinance 為基底，覆蓋或補充既有資料
        existing_dates = {r["date"] for r in existing}
        for r in existing:
            if r["date"] not in {nr["date"] for nr in new_hist}:
                new_hist.append(r)

        new_hist.sort(key=lambda r: r["date"])
        print(f"回補完成，共 {len(new_hist)} 筆")
        return new_hist
    except Exception as e:
        print(f"[錯誤] yfinance 回補: {e}")
        return existing


# ── 大台成交量（TAIFEX futDailyMarketReport） ────────────────

def fetch_txf_volume(session: requests.Session, query_date: str) -> float | None:
    """大台（TXF/TX）所有月份成交量合計（萬口）"""
    try:
        resp = session.post(TAIFEX_VOL, data={
            "queryStartDate": query_date,
            "queryEndDate":   query_date,
            "commodityId":    "TXF",
        }, timeout=15)
        soup  = BeautifulSoup(resp.text, "html.parser")
        total = 0
        found = False
        for tbl in soup.find_all("table"):
            rows = tbl.find_all("tr")
            if len(rows) < 3:
                continue
            for tr in rows:
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells and cells[0] in ("TX", "TXF"):
                    vol = _num(cells[8]) if len(cells) > 8 else 0  # *成交量欄位
                    total += vol
                    found = True
        if found:
            return round(total / 10000, 2)  # 口 → 萬口
    except Exception as e:
        print(f"[錯誤] 大台成交量: {e}")
    return None


# ── P/C 比（TAIFEX pcRatio HTML） ────────────────────────────

def fetch_pc_ratio_history(session: requests.Session, query_date: str) -> list:
    """
    抓取最近 20 筆 P/C 未平倉量比率（%），回傳 [{'date': 'YYYY-MM-DD', 'pc': float}, ...]
    日期最新的排最前，已按日期排序後回傳
    """
    records = []
    try:
        session.get(TAIFEX_PC, timeout=15)
        resp = session.post(TAIFEX_PC, data={"queryDate": query_date}, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tbl in soup.find_all("table"):
            rows = tbl.find_all("tr")
            if len(rows) < 2:
                continue
            header = [td.get_text(strip=True) for td in rows[0].find_all(["td", "th"])]
            if "買賣權未平倉量比率%" not in header:
                continue
            for tr in rows[1:]:
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if len(cells) < 7 or not cells[0].strip():
                    continue
                # 日期格式 2026/5/8 → 2026-05-08
                parts = cells[0].split("/")
                if len(parts) == 3:
                    date_str = f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
                    records.append({"date": date_str, "pc": _num(cells[6])})
            break
    except Exception as e:
        print(f"[錯誤] P/C 比: {e}")

    records.sort(key=lambda r: r["date"])
    return records


def _last_trading_date_str() -> str:
    """找最近有 TWSE 資料的交易日，回傳 YYYY/MM/DD 格式"""
    try:
        resp = requests.get(TWSE_FMTQIK, headers=HEADERS, timeout=15, verify=False)
        rows = resp.json().get("data", [])
        if rows:
            # 日期格式為民國 115/05/08，轉西元
            roc = rows[-1][0]   # e.g. "115/05/08"
            parts = roc.split("/")
            year = int(parts[0]) + 1911
            return f"{year}/{parts[1]}/{parts[2]}"
    except Exception:
        pass
    return datetime.now().strftime("%Y/%m/%d")


# ── 主流程 ────────────────────────────────────────────────

def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    print("=== 計算均線與 P/C 比指標 ===")

    # 建立 TAIFEX session
    session = requests.Session()
    session.verify = False
    session.headers.update(HEADERS)

    # 找最近交易日
    query_date = _last_trading_date_str()
    print(f"查詢日期: {query_date}")

    # 1. 加權指數收盤 & 台股成交量
    taiex_close, taiex_vol = fetch_taiex_from_twse()
    print(f"加權指數收盤: {taiex_close}  台股成交量: {taiex_vol} 億")

    # 2. 大台成交量
    txf_vol = fetch_txf_volume(session, query_date)
    print(f"大台成交量: {txf_vol} 萬口")

    # 3. 更新加權指數歷史 & 計算均線
    taiex_hist = load_history(HISTORY_TAIEX)
    taiex_hist = backfill_taiex_history(taiex_hist)  # 不足60筆時回補

    if taiex_close:
        # 當日資料：若已有當日則更新，否則新增
        yd = query_date.replace("/", "-")  # 轉 YYYY-MM-DD
        if taiex_hist and taiex_hist[-1]["date"] == yd:
            taiex_hist[-1]["close"] = taiex_close
        else:
            taiex_hist.append({"date": yd, "close": taiex_close})

    if len(taiex_hist) > 120:
        taiex_hist = taiex_hist[-120:]
    save_history(HISTORY_TAIEX, taiex_hist)

    closes = [r["close"] for r in taiex_hist]
    ema11  = calc_ema(closes, 11)
    ema24  = calc_ema(closes, 24)
    sma60  = calc_sma(closes, 60)
    print(f"EMA11={ema11}  EMA24={ema24}  SMA60={sma60}")

    # 4. P/C 比 & 歷史均線
    new_pc_records = fetch_pc_ratio_history(session, query_date)
    pc_today = new_pc_records[-1]["pc"] if new_pc_records else None
    print(f"P/C 比: {pc_today}%  (本次取得 {len(new_pc_records)} 筆歷史資料)")

    pc_hist = load_history(HISTORY_PC)
    # 合併歷史：以日期為 key，新資料覆蓋舊資料
    pc_dict = {r["date"]: r["pc"] for r in pc_hist}
    for r in new_pc_records:
        pc_dict[r["date"]] = r["pc"]
    pc_hist = [{"date": d, "pc": v} for d, v in sorted(pc_dict.items())]

    if len(pc_hist) > 120:
        pc_hist = pc_hist[-120:]
    save_history(HISTORY_PC, pc_hist)

    pc_vals = [r["pc"] for r in pc_hist]
    pc_3ma  = calc_ma(pc_vals, 3)
    pc_10ma = calc_ma(pc_vals, 10)
    print(f"P/C 3MA={pc_3ma}  P/C 10MA={pc_10ma}")

    # 5. 寫回 latest.json
    data = {}
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 2:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    data["taiex"] = {
        "close":       taiex_close,
        "volume_yi":   int(taiex_vol) if taiex_vol else None,
        "txf_vol_wan": txf_vol,
        "ema11":       ema11,
        "ema24":       ema24,
        "sma60":       sma60,
    }
    data["pc_ratio"] = {
        "current": pc_today,
        "ma3":     pc_3ma,
        "ma10":    pc_10ma,
    }
    data["indicators_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n已寫入 {DATA_FILE}")


if __name__ == "__main__":
    main()

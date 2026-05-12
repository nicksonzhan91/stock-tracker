"""
fetch_institutional.py — 抓取法人動態（18:00 執行）
來源：
  - 現股買賣差額：TWSE BFI82U（三大法人買賣金額統計表）
  - 大台期貨：TAIFEX futContractsDate（HTML 解析）
  - 選擇權多空：TAIFEX callsAndPutsDate（HTML 解析）
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

TWSE_BFI82U   = "https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json&dayDate=&type=day"
TAIFEX_FUT    = "https://www.taifex.com.tw/cht/3/futContractsDate"
TAIFEX_OPT    = "https://www.taifex.com.tw/cht/3/callsAndPutsDate"


def _num(s: str) -> float:
    s = str(s).strip().replace(",", "").replace(" ", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return 0.0


def _last_trading_date(session: requests.Session, url: str, extra_params: dict = None) -> str:
    """往回找最近有資料的交易日（最多找10天）"""
    base = {"queryDate": "", "commodityId": "TXF"}
    if extra_params:
        base.update(extra_params)
    d = datetime.now()
    for _ in range(10):
        date_str = d.strftime("%Y/%m/%d")
        base["queryDate"] = date_str
        try:
            resp = session.post(url, data=base, timeout=15)
            if "查無資料" not in resp.text and len(resp.text) > 10000:
                return date_str
        except Exception:
            pass
        d -= timedelta(days=1)
    return datetime.now().strftime("%Y/%m/%d")


# ── 現股買賣差額（TWSE BFI82U） ──────────────────────────

def fetch_stock_net() -> dict:
    result = {"foreign": None, "trust": None}
    try:
        resp = requests.get(TWSE_BFI82U, headers=HEADERS, timeout=15, verify=False)
        resp.raise_for_status()
        data = resp.json()
        for row in data.get("data", []):
            name     = row[0].strip()
            diff_yi  = round(_num(row[3]) / 1e8, 1)  # 元 → 億元
            if "外資及陸資" in name:
                # 累加「不含外資自營商」與「外資自營商」兩列
                result["foreign"] = round((result["foreign"] or 0) + diff_yi, 1)
            elif name == "投信":
                result["trust"] = diff_yi
        print(f"現股買賣差額 — 外資: {result['foreign']} 億  投信: {result['trust']} 億")
    except Exception as e:
        print(f"[錯誤] 現股買賣超: {e}")
    return result


# ── 大台期貨三大法人（TAIFEX） ────────────────────────────

def fetch_futures_positions(session: requests.Session, query_date: str) -> dict:
    result = {
        "foreign": {"net": None, "oi": None},
        "trust":   {"net": None, "oi": None},
    }
    try:
        resp = session.post(TAIFEX_FUT, data={
            "queryDate": query_date, "commodityId": "TXF"
        }, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        # 找有資料的表格（列數 > 5）
        target = None
        for tbl in soup.find_all("table"):
            if len(tbl.find_all("tr")) > 5:
                target = tbl
                break
        if not target:
            print("[警告] 找不到期貨資料表格")
            return result

        rows = [[td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                for tr in target.find_all("tr")]
        rows = [r for r in rows if any(r)]

        # 解析規則：
        # 開頭是數字的列（序號列）: [序號, 商品, 買權/賣權, 身份別, ..., 交易淨額口, 交易淨額金, ...]
        #   身份別=index[3], 交易淨額口=[8], 未平倉淨額口=[14]
        # 其他列: 身份別=index[0], 交易淨額口=[5], 未平倉淨額口=[11]

        for row in rows:
            if not row:
                continue
            if row[0].isdigit():  # 序號列
                identity = row[3] if len(row) > 3 else ""
                trade_net = int(_num(row[8]))  if len(row) > 8  else None
                oi_net    = int(_num(row[14])) if len(row) > 14 else None
            else:
                identity  = row[0]
                trade_net = int(_num(row[5]))  if len(row) > 5  else None
                oi_net    = int(_num(row[11])) if len(row) > 11 else None

            if "外資" in identity and "合計" not in identity:
                result["foreign"]["net"] = trade_net
                result["foreign"]["oi"]  = oi_net
            elif identity.strip() == "投信":
                result["trust"]["net"] = trade_net
                result["trust"]["oi"]  = oi_net

        print(f"大台期貨({query_date}) 外資淨額: {result['foreign']['net']}口  外資未平倉: {result['foreign']['oi']}口")
        print(f"大台期貨({query_date}) 投信淨額: {result['trust']['net']}口  投信未平倉: {result['trust']['oi']}口")
    except Exception as e:
        print(f"[錯誤] 大台期貨部位: {e}")
    return result


# ── 選擇權多空契約金額（TAIFEX） ──────────────────────────

def fetch_options_net_value(session: requests.Session, query_date: str) -> dict:
    """
    判斷外資/投信選擇權的多空偏向
    = sign( Call未平倉差額契約金額 − Put未平倉差額契約金額 )
    Call 淨買 > Put 淨買 → 偏多 (positive)
    Put  淨買 > Call 淨買 → 偏空 (negative)
    """
    result = {"foreign": None, "trust": None}
    try:
        resp = session.post(TAIFEX_OPT, data={
            "queryType": "", "goDay": "", "doQuery": "1",
            "dateaddcnt": "", "queryDate": query_date,
            "commodityId": "TXO", "button": "送出查詢",
        }, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        target = None
        for tbl in soup.find_all("table"):
            if len(tbl.find_all("tr")) > 5:
                target = tbl
                break
        if not target:
            print("[警告] 找不到選擇權資料表格")
            return result

        rows = [[td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                for tr in target.find_all("tr")]
        rows = [r for r in rows if any(r)]

        # 紀錄 Call/Put 各身份別的 未平倉差額契約金額
        # 欄位解析（以 '買權'/'賣權' 判斷目前區段）
        # 開頭是數字的列: [序號, 商品, 買|賣, 身份別, ...], 未平倉差額金額 = index[15]
        # '買權'/'賣權'開頭的列: [買|賣, 身份別, ...], 未平倉差額金額 = index[13]
        # 其他（續行）: [身份別, ...], 未平倉差額金額 = index[12]

        call_vals = {}  # {身份別: 未平倉差額契約金額}
        put_vals  = {}
        current_section = None  # 'call' or 'put'

        for row in rows:
            if not row or len(row) < 3:
                continue

            if row[0].isdigit():
                cp_type  = row[2]
                identity = row[3] if len(row) > 3 else ""
                val      = _num(row[15]) if len(row) > 15 else 0
                current_section = "call" if "買" in cp_type else "put"
            elif row[0] in ("買權", "賣權"):
                cp_type  = row[0]
                identity = row[1] if len(row) > 1 else ""
                val      = _num(row[13]) if len(row) > 13 else 0
                current_section = "call" if "買" in cp_type else "put"
            else:
                identity = row[0]
                val      = _num(row[12]) if len(row) > 12 else 0

            if current_section == "call":
                call_vals[identity] = val
            elif current_section == "put":
                put_vals[identity] = val

        def sign(identity_key):
            call_v = call_vals.get(identity_key, 0)
            put_v  = put_vals.get(identity_key, 0)
            net    = call_v - put_v
            return "positive" if net > 0 else "negative"

        # 找外資鍵值（可能是「外資」或「外資及陸資」）
        foreign_key = next((k for k in call_vals if "外資" in k), None)
        if foreign_key:
            result["foreign"] = sign(foreign_key)
        if "投信" in call_vals:
            result["trust"] = sign("投信")

        print(f"選擇權多空 — 外資: {result['foreign']}  投信: {result['trust']}")
        print(f"  Call外資={call_vals.get(foreign_key)}  Put外資={put_vals.get(foreign_key)}")
        print(f"  Call投信={call_vals.get('投信')}  Put投信={put_vals.get('投信')}")
    except Exception as e:
        print(f"[錯誤] 選擇權多空契約金額: {e}")
    return result


# ── 主流程 ────────────────────────────────────────────────

def main():
    print("=== 抓取法人動態 ===")

    session = requests.Session()
    session.verify = False
    session.headers.update(HEADERS)
    # 先訪問首頁建立 session
    session.get(TAIFEX_FUT, timeout=15)

    # 找最近有資料的交易日
    query_date = _last_trading_date(session, TAIFEX_FUT)
    print(f"查詢日期: {query_date}")

    stock_net    = fetch_stock_net()
    futures_pos  = fetch_futures_positions(session, query_date)
    options_sign = fetch_options_net_value(session, query_date)

    institutional = {
        "foreign": {
            "stock_net_yi":    stock_net["foreign"],
            "futures_net_lot": futures_pos["foreign"]["net"],
            "futures_oi_lot":  futures_pos["foreign"]["oi"],
            "options_sign":    options_sign["foreign"],
        },
        "trust": {
            "stock_net_yi":    stock_net["trust"],
            "futures_net_lot": futures_pos["trust"]["net"],
            "futures_oi_lot":  futures_pos["trust"]["oi"],
            "options_sign":    options_sign["trust"],
        },
    }

    data = {}
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 2:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    data["institutional"]         = institutional
    data["institutional_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n已寫入 {DATA_FILE}")


if __name__ == "__main__":
    main()

"""
update_value_zone_price.py — 每日刷新「超跌好公司」現價與低估名單
────────────────────────────────────────────────────────────
背景：
  ・合理價值（buy_target / value）由 export_value_excel.py 季更新一次（財報才會變），
    結果存於 data/value_targets.json。
  ・但「現價」與「是否超跌」每天都在變，不應跟著季更新被凍結。

本腳本：
  1. 讀 data/value_targets.json（季更新的合理價值基準）
  2. 只抓這批好公司的最新「前日收盤」（永豐金 zca），約 45 支、數十秒
  3. 重算低估名單（price <= buy_target）後，以今天日期覆寫 data/value_zone.json

用法：
  python update_value_zone_price.py
────────────────────────────────────────────────────────────
"""

import os, sys, json, time, datetime

sys.stdout.reconfigure(encoding="utf-8")

# 重用 export_value_excel.py 內已驗證的價格抓取邏輯
sys.path.insert(0, os.path.dirname(__file__))
from export_value_excel import fetch_zca_data, SLEEP

DATA_DIR     = os.path.join(os.path.dirname(__file__), "..", "data")
TARGETS_FILE = os.path.join(DATA_DIR, "value_targets.json")
ZONE_FILE    = os.path.join(DATA_DIR, "value_zone.json")


def main():
    if not os.path.exists(TARGETS_FILE):
        print(f"[錯誤] 找不到 {TARGETS_FILE}；請先跑一次 export_value_excel.py（季更新）產生合理價值基準")
        sys.exit(1)

    with open(TARGETS_FILE, "r", encoding="utf-8") as f:
        targets = json.load(f)

    stocks = targets["stocks"]
    print(f"合理價值基準日 {targets.get('valuation_date', '?')}，共 {len(stocks)} 支好公司，開始抓最新收盤…")

    zone_stocks = []
    miss = 0
    for i, t in enumerate(stocks, 1):
        sid        = t["stock_id"]
        name       = t["name"]
        value      = t.get("value")
        buy_target = t.get("buy_target")

        zca   = fetch_zca_data(sid)
        price = zca.get("price")
        time.sleep(SLEEP)

        if price is None:
            miss += 1
            print(f"  [{i:>2}/{len(stocks)}] {sid} {name}  收盤=取得失敗")
            continue

        flag = ""
        if value is not None and buy_target is not None and price <= buy_target:
            zone_stocks.append({
                "stock_id":   sid,
                "name":       name,
                "price":      price,
                "buy_target": buy_target,
                "value":      value,
                "ratio":      round((value - price) / price * 100, 2),
                "avg_roe":    t.get("avg_roe"),
            })
            flag = "★低估"
        print(f"  [{i:>2}/{len(stocks)}] {sid} {name}  收盤={price}  合理買入={buy_target}  {flag}")

    zone_stocks.sort(key=lambda x: x["ratio"], reverse=True)
    price_date = datetime.date.today().strftime("%Y-%m-%d")

    with open(ZONE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "date":   price_date,
            "total":  len(stocks),
            "stocks": zone_stocks,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已更新 → {ZONE_FILE}（報價日 {price_date}，低估 {len(zone_stocks)} 支，"
          f"取價失敗 {miss} 支）")


if __name__ == "__main__":
    main()

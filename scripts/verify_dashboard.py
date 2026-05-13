"""
verify_dashboard.py — 核對網頁儀表板數值
模擬 index.html 的 JS 渲染邏輯，對照 latest.json 逐欄輸出預期顯示值
"""
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "latest.json")

with open(DATA_FILE, encoding="utf-8") as f:
    d = json.load(f)

def fmt(v, dec=2):
    if v is None: return "—"
    return f"{v:,.{dec}f}"

PASS = "✅"
WARN = "⚠️ "

print("=" * 52)
print("  儀表板數值核對報告")
print("=" * 52)

errors = []

# ── 法人動態 ─────────────────────────────────────
print("\n【法人動態】")
inst = d.get("institutional", {})
fo   = inst.get("foreign", {})
tr_  = inst.get("trust", {})

rows = [
    ("現股買賣差額（億）", fo.get("stock_net_yi"),    tr_.get("stock_net_yi")),
    ("大台多空淨額（口）", fo.get("futures_net_lot"), tr_.get("futures_net_lot")),
    ("大台未平倉（口）",   fo.get("futures_oi_lot"),  tr_.get("futures_oi_lot")),
    ("選擇權多空契約金額", fo.get("options_sign"),     tr_.get("options_sign")),
]

print(f"  {'項目':<16} {'外資及陸資':>12} {'投信':>10}")
print(f"  {'-'*40}")
for label, fv, tv in rows:
    if label == "選擇權多空契約金額":
        fv2 = {"positive":"多","negative":"空"}.get(fv, "—") if fv else "—"
        tv2 = {"positive":"多","negative":"空"}.get(tv, "—") if tv else "—"
    else:
        fv2 = (("+" if fv > 0 else "") + fmt(fv, 1)) if fv is not None else "—"
        tv2 = (("+" if tv > 0 else "") + fmt(tv, 1)) if tv is not None else "—"
    ok = PASS if fv is not None and tv is not None else WARN
    if fv is None or tv is None:
        errors.append(f"法人動態 [{label}] 有欄位為 None")
    print(f"{ok} {label:<16} {fv2:>12} {tv2:>10}")

print(f"  更新：{d.get('institutional_updated','—')}")

# ── 台股區間 ─────────────────────────────────────
print("\n【台股區間】")
tx = d.get("taiex", {})
st = d.get("options_strikes", {})

vol_yi   = tx.get("volume_yi")
txf_wan  = tx.get("txf_vol_wan")
ok1 = PASS if vol_yi  is not None else WARN
ok2 = PASS if txf_wan is not None else WARN
if vol_yi  is None: errors.append("台股成交量（億）為 None")
if txf_wan is None: errors.append("大台成交量（萬口）為 None")
print(f"{ok1} 台股成交量（億）　　{fmt(vol_yi,0):>10}")
print(f"{ok2} 大台成交量（萬口）　{fmt(txf_wan,2):>10}")

items = [
    ("壓力",   st.get("resistance"), 0),
    ("現值",   tx.get("close"),      2),
    ("支撐",   st.get("support"),    0),
    ("攻擊線", tx.get("ema11"),      0),
    ("生命線", tx.get("ema24"),      0),
    ("季線",   tx.get("sma60"),      0),
]
items_sorted = sorted(items, key=lambda x: (x[1] is None, -(x[1] or 0)))

print(f"\n  → 依數值高至低排序後：")
prev_val = None
order_ok = True
for label, val, dec in items_sorted:
    ok = PASS if val is not None else WARN
    if val is None:
        errors.append(f"台股區間 [{label}] 為 None")
    if prev_val is not None and val is not None and val > prev_val:
        order_ok = False
        errors.append(f"台股區間排序異常：{label}({val}) > 前項({prev_val})")
    prev_val = val
    print(f"  {ok} {label:<8} {fmt(val, dec):>12}")

if order_ok:
    print(f"  {PASS} 排列順序正確（高→低）")

print(f"  更新：{d.get('indicators_updated','—')}")

# ── P/C 比 ────────────────────────────────────────
print("\n【動能指標 P/C 比】")
pc   = d.get("pc_ratio", {})
cur  = pc.get("current")
ma3  = pc.get("ma3")
ma10 = pc.get("ma10")
chart = pc.get("chart", [])

ok = PASS if None not in (cur, ma3, ma10) else WARN
if None in (cur, ma3, ma10):
    errors.append("P/C 比數值有 None")

if cur is not None and ma3 is not None and ma10 is not None:
    if cur > ma3 > ma10:   trend = "多頭排列"
    elif cur < ma3 < ma10: trend = "空頭排列"
    else:                  trend = "排列不整"
else:
    trend = "—"

print(f"{ok} 現值={cur}　3MA={ma3}　10MA={ma10}　→ {trend}")
ok_chart = PASS if len(chart) >= 10 else WARN
if len(chart) < 10:
    errors.append(f"P/C 比圖表資料僅 {len(chart)} 筆（建議 ≥ 10）")
print(f"{ok_chart} 圖表資料：{len(chart)} 筆（最新日期：{chart[-1]['date'] if chart else '—'}）")

# ── 美日韓指數 ────────────────────────────────────
print("\n【美日韓指數】")
all_idx = {**d.get("us_indices", {}), **d.get("asia_indices", {})}
order = ["^DJI","^GSPC","^IXIC","^SOX","^N225","^KS11"]
names = {"^DJI":"道瓊工業","^GSPC":"S&P 500","^IXIC":"那斯達克","^SOX":"費城半導體","^N225":"日經225","^KS11":"韓國綜合"}

for sym in order:
    v = all_idx.get(sym)
    ok = PASS if v else WARN
    if not v:
        errors.append(f"指數 {sym} 缺資料")
        print(f"{ok} {names[sym]}({sym})：缺資料")
        continue
    chg = v["change"]; pct = v["change_pct"]
    s = "+" if chg >= 0 else ""
    print(f"{ok} {v['name']}({sym})：{fmt(v['close'],2)}　{s+fmt(chg,2)}　{s+fmt(pct,2)}%")

print(f"  美股更新：{d.get('us_updated','—')}")
print(f"  亞股更新：{d.get('asia_updated','—')}")

# ── 總結 ──────────────────────────────────────────
print("\n" + "=" * 52)
if errors:
    print(f"  {WARN} 發現 {len(errors)} 個問題：")
    for e in errors:
        print(f"    • {e}")
else:
    print(f"  {PASS} 全部欄位數值正常，無異常！")
print("=" * 52)

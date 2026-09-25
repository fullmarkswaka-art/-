# -*- coding: utf-8 -*-
"""週次の広告成果レポート（Meta + Google）をPDF生成する。

使い方:
  python scripts/weekly_report.py [--out reports/週次レポート.pdf]

構成:
  1. サマリー … 今週の費用/売上/ROAS/購入件数（前週比）、今週のポイント、月間ペース
  2. 何が売れたか … ブランド別・枠別の成果、Googleショッピングで売れた商品、
                    Metaカタログ広告（ブランド/シリーズ別）
  3. キャンペーン別 … Google / Meta それぞれ前週比付き
  4. 日別推移 … Google + Meta 合算
  5. 監査 … リンク切れ、他口座の消化、アウトレット品の表示
今週 = 昨日までの7日間、前週 = その前の7日間。売上は各媒体計測のCV金額（税込）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from ads_manager.audit import check_url, meta_audit
from ads_manager.config import load_google_config, load_meta_config
from ads_manager.meta_ads import MetaAdsClient

_IPA = Path("/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf")
if _IPA.exists():  # プロポーショナル日本語フォント（Ø や _ の字間が崩れない）
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("IPAPGothic", str(_IPA)))
    FONT = "IPAPGothic"
else:
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    FONT = "HeiseiKakuGo-W5"
NAVY = colors.HexColor("#1a3c6e"); GREY = colors.HexColor("#555555")
LIGHT = colors.HexColor("#f0f4fa"); LINE = colors.HexColor("#c8d2e0")
GOOD = colors.HexColor("#1b7f3b"); BAD = colors.HexColor("#b3261e")

S = {
    "title": ParagraphStyle("t", fontName=FONT, fontSize=17, leading=22, spaceAfter=1 * mm),
    "sub": ParagraphStyle("s", fontName=FONT, fontSize=9, leading=12, textColor=GREY),
    "h1": ParagraphStyle("h1", fontName=FONT, fontSize=14, leading=18, spaceBefore=7 * mm,
                         spaceAfter=3 * mm, textColor=NAVY),
    "h2": ParagraphStyle("h2", fontName=FONT, fontSize=11, leading=15, spaceBefore=5 * mm,
                         spaceAfter=2 * mm, textColor=NAVY),
    "body": ParagraphStyle("b", fontName=FONT, fontSize=9, leading=14),
    "bullet": ParagraphStyle("bl", fontName=FONT, fontSize=9, leading=14, leftIndent=5 * mm,
                             bulletIndent=1 * mm),
    "sub_bullet": ParagraphStyle("sbl", fontName=FONT, fontSize=8.5, leading=13, leftIndent=11 * mm,
                                 bulletIndent=6 * mm, textColor=BAD),
    "cell": ParagraphStyle("c", fontName=FONT, fontSize=8, leading=10),
    "tile_label": ParagraphStyle("tl", fontName=FONT, fontSize=8, leading=10, textColor=GREY,
                                 alignment=1),
    "tile_value": ParagraphStyle("tv", fontName=FONT, fontSize=15, leading=18, alignment=1),
    "tile_delta": ParagraphStyle("td", fontName=FONT, fontSize=8, leading=10, alignment=1),
    "note": ParagraphStyle("n", fontName=FONT, fontSize=7.5, leading=10, textColor=GREY),
}

BRANDS = [("HOUDINI", ["フーディ", "houdini"]), ("NORRØNA", ["ノローナ", "norrona", "norrøna"]),
          ("POC", ["ポック", "poc"]), ("ACLIMA", ["アクリマ", "aclima"]),
          ("HESTRA", ["ヘストラ", "hestra"]), ("SAIL RACING", ["セイル", "sail"]),
          ("PLUS ONE WORKS", ["plus one", "pu store"]), ("KANG", ["kang"]), ("POW", ["pow"])]


def brand_of(name: str) -> str:
    n = (name or "").lower()
    for b, keys in BRANDS:
        if any(k in n for k in keys):
            return b
    if "フルマークス" in n and ("指名" in n or "sk_" in n):
        return "店舗指名（フルマークス）"
    return "全ブランド（旧・全商品カタログ等）"


def disp(name: str) -> str:
    """キャンペーン名の表示用: 運用プレフィックス（UC_SK_1_ など）を落とす。"""
    n = re.sub(r"^UC_[A-Z]{2}_\d+_", "", name or "")
    return n.replace("NORRONA", "NORRØNA").replace("_", " ")


def frame_of(name: str) -> str:
    n = (name or "").upper()
    if "UC_SK" in n or "指名" in n:
        return "指名検索"
    if "UC_PL" in n or "PLA" in n or "ショッピング" in n:
        return "ショッピング"
    if "CVS" in n or "カタログ" in n or "DPA" in n:
        return "カタログ"
    if "RTG" in n:
        return "リターゲティング（静止画）"
    if "CLK" in n:
        return "新規向け（静止画）"
    return "その他"


# ---------------- 書式 ----------------

def yen(v):
    return f"¥{v:,.0f}"


def pct(cur, prev):
    if not prev:
        return "—" if not cur else "新規"
    return f"{(cur - prev) / prev * 100:+.0f}%"


def roas(m):
    return m["rev"] / m["spend"] if m["spend"] else 0.0


def table(data, widths, align_right_from=1, font_size=8, zebra=True, header=True):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("FONT", (0, 0), (-1, -1), FONT, font_size),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("ALIGN", (align_right_from, 1 if header else 0), (-1, -1), "RIGHT"),
          ("GRID", (0, 0), (-1, -1), 0.4, LINE),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
               ("ALIGN", (0, 0), (-1, 0), "CENTER")]
    if zebra:
        st.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]))
    t.setStyle(TableStyle(st))
    return t


def kpi_tiles(cur, prev):
    """費用 / 売上 / ROAS / 購入件数 の4タイル（前週比付き）。"""
    items = [("広告費", yen(cur["spend"]), pct(cur["spend"], prev["spend"]), None),
             ("売上（広告経由）", yen(cur["rev"]), pct(cur["rev"], prev["rev"]), True),
             ("ROAS", f"{roas(cur):.1f}", f"{roas(cur) - roas(prev):+.1f}（前週 {roas(prev):.1f}）", True),
             ("購入件数", f"{cur['cv']:.0f}件", pct(cur["cv"], prev["cv"]), True)]
    row_label, row_value, row_delta = [], [], []
    for label, value, delta, good_up in items:
        row_label.append(Paragraph(label, S["tile_label"]))
        row_value.append(Paragraph(value, S["tile_value"]))
        color = GREY
        if good_up is not None and delta not in ("—", "新規"):
            color = GOOD if delta.startswith("+") else BAD
        row_delta.append(Paragraph(f'<font color="{color.hexval()}">前週比 {delta}</font>', S["tile_delta"]))
    t = Table([row_label, row_value, row_delta], colWidths=[44 * mm] * 4)
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE),
                           ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
                           ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                           ("LINEBELOW", (0, 0), (-1, 0), 0, LIGHT), ("LINEBELOW", (0, 1), (-1, 1), 0, LIGHT),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return t


# ---------------- データ取得 ----------------

def _meta_actions(row, key, values=False):
    for a in row.get("action_values" if values else "actions") or []:
        if a["action_type"] == key:
            return float(a["value"])
    return 0.0


def _mm(row):
    return {"spend": float(row.get("spend") or 0), "imp": int(row.get("impressions") or 0),
            "clicks": int(row.get("clicks") or 0), "cv": _meta_actions(row, "omni_purchase"),
            "rev": _meta_actions(row, "omni_purchase", values=True)}


def meta_data(client, since, until):
    acct = client.config.ad_account_id
    tr = json.dumps({"since": str(since), "until": str(until)})
    f = "campaign_id,campaign_name,ad_id,ad_name,impressions,clicks,spend,actions,action_values"
    camps = [{"id": r["campaign_id"], "name": r["campaign_name"], **_mm(r)}
             for r in client.get_all(f"{acct}/insights", level="campaign", time_range=tr, fields=f, limit=200)]
    ads = [{"id": r["ad_id"], "name": r["ad_name"], "campaign": r["campaign_name"], **_mm(r)}
           for r in client.get_all(f"{acct}/insights", level="ad", time_range=tr, fields=f, limit=500)]
    daily = {r["date_start"]: _mm(r) for r in client.get_all(
        f"{acct}/insights", level="account", time_range=tr, time_increment=1, fields=f, limit=100)}
    return camps, ads, daily


def _gm(m):
    return {"spend": m.cost_micros / 1e6, "imp": m.impressions, "clicks": m.clicks,
            "cv": m.conversions, "rev": m.conversions_value}


def google_data(client, since, until):
    where = f"segments.date BETWEEN '{since}' AND '{until}'"
    f = "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value"
    camps = []
    for r in client.search(f"SELECT campaign.id, campaign.name, {f} FROM campaign WHERE {where}"):
        m = _gm(r.metrics)
        if m["imp"] or m["spend"]:
            camps.append({"id": str(r.campaign.id), "name": r.campaign.name, **m})
    daily = {}
    for r in client.search(f"SELECT segments.date, {f} FROM customer WHERE {where}"):
        daily[r.segments.date] = _gm(r.metrics)
    shop_brand = defaultdict(lambda: {"spend": 0.0, "imp": 0, "clicks": 0, "cv": 0.0, "rev": 0.0})
    products = defaultdict(lambda: {"title": "", "brand": "", "spend": 0.0, "clicks": 0, "cv": 0.0, "rev": 0.0})
    labels = defaultdict(lambda: defaultdict(int))  # label -> campaign -> imp
    for r in client.search(
            "SELECT campaign.id, campaign.name, segments.product_item_id, segments.product_title, "
            "segments.product_brand, segments.product_custom_attribute0, "
            f"{f} FROM shopping_performance_view WHERE {where}"):
        m = _gm(r.metrics)
        b = (r.segments.product_brand or "").upper().replace("NORRONA", "NORRØNA") or "ショッピング（ブランド属性なし）"
        for k in ("spend", "imp", "clicks", "cv", "rev"):
            shop_brand[b][k] += m[k]
        p = products[r.segments.product_item_id]
        p["title"] = r.segments.product_title; p["brand"] = b
        p["spend"] += m["spend"]; p["clicks"] += m["clicks"]; p["cv"] += m["cv"]; p["rev"] += m["rev"]
        labels[r.segments.product_custom_attribute0 or "（ラベルなし）"][r.campaign.name] += m["imp"]
    return camps, daily, shop_brand, products, labels


def total_of(rows):
    t = {"spend": 0.0, "imp": 0, "clicks": 0, "cv": 0.0, "rev": 0.0}
    for r in rows:
        for k in t:
            t[k] += r[k]
    return t


# ---------------- 集計 ----------------

def by_brand(g_camps, g_shop_brand, m_ads):
    """ブランド別（広告経由）。指名検索/静止画はキャンペーン名、ショッピングは商品ブランド、
    カタログは広告名（fullmarks-dpa-<BRAND>）から判定する。"""
    agg = defaultdict(lambda: {"spend": 0.0, "cv": 0.0, "rev": 0.0})
    for c in g_camps:
        if frame_of(c["name"]) == "ショッピング":
            continue  # 商品ブランド別で計上
        b = brand_of(c["name"])
        for k in ("spend", "cv", "rev"):
            agg[b][k] += c[k]
    for b, m in g_shop_brand.items():
        for k in ("spend", "cv", "rev"):
            agg[b][k] += m[k]
    for a in m_ads:
        b = brand_of(a["name"]) if frame_of(a["campaign"]) == "カタログ" else brand_of(a["campaign"])
        for k in ("spend", "cv", "rev"):
            agg[b][k] += a[k]
    return agg


def by_frame(g_camps, m_camps):
    agg = defaultdict(lambda: {"spend": 0.0, "cv": 0.0, "rev": 0.0})
    for c in g_camps + m_camps:
        fr = frame_of(c["name"])
        for k in ("spend", "cv", "rev"):
            agg[fr][k] += c[k]
    return agg


def highlights(brand_cur, brand_prev, frame_cur, camps_cur, camps_prev):
    """今週のポイント（自動生成）。"""
    lines = []
    top = sorted(brand_cur.items(), key=lambda kv: -kv[1]["rev"])[:3]
    if top and top[0][1]["rev"]:
        lines.append("売上が大きかったブランド: " + "、".join(
            f"{b} {yen(m['rev'])}（{m['cv']:.0f}件、ROAS {roas(m):.1f}）" for b, m in top if m["rev"]))
    fr = sorted(frame_cur.items(), key=lambda kv: -kv[1]["rev"])
    if fr:
        lines.append("枠別: " + "、".join(f"{f} ROAS {roas(m):.1f}" for f, m in fr if m["spend"]))
    weak = [(c, roas(c)) for c in camps_cur if c["spend"] >= 5000 and roas(c) < 2]
    if weak:
        lines.append("要改善（週5,000円以上でROAS 2未満）: " + "／".join(
            f"{disp(c['name'])} 費用{yen(c['spend'])}・売上{yen(c['rev'])}・ROAS {r:.1f}"
            for c, r in sorted(weak, key=lambda x: -x[0]['spend'])))
    prev_by = {c["id"]: c for c in camps_prev}
    moves = []
    for c in camps_cur:
        p = prev_by.get(c["id"])
        if p and p["spend"] >= 3000 and c["spend"] >= 3000:
            d = roas(c) - roas(p)
            if abs(d) >= 3:
                moves.append(f"{disp(c['name'])} ROAS {roas(p):.1f}→{roas(c):.1f}")
    if moves:
        lines.append("前週から大きく変わった: " + "／".join(moves))
    return lines


# ---------------- セクション ----------------

def sec_brand(brand_cur, brand_prev):
    data = [["ブランド", "広告費", "購入", "売上", "ROAS", "前週売上", "前週比"]]
    for b, m in sorted(brand_cur.items(), key=lambda kv: -kv[1]["rev"]):
        p = brand_prev.get(b, {"spend": 0, "cv": 0, "rev": 0})
        data.append([b, yen(m["spend"]), f"{m['cv']:.0f}", yen(m["rev"]) if m["rev"] else "—",
                     f"{roas(m):.1f}" if m["rev"] else "—", yen(p["rev"]) if p["rev"] else "—",
                     pct(m["rev"], p["rev"])])
    t = total_of([dict(imp=0, clicks=0, **m) for m in brand_cur.values()])
    data.append(["合計", yen(t["spend"]), f"{t['cv']:.0f}", yen(t["rev"]), f"{roas(t):.1f}", "", ""])
    tb = table(data, [42 * mm, 24 * mm, 14 * mm, 26 * mm, 16 * mm, 26 * mm, 18 * mm])
    tb.setStyle(TableStyle([("FONT", (0, len(data) - 1), (-1, len(data) - 1), FONT, 8),
                            ("BACKGROUND", (0, len(data) - 1), (-1, len(data) - 1), colors.HexColor("#dfe7f3"))]))
    return tb


def sec_frame(frame_cur, frame_prev):
    data = [["枠", "広告費", "購入", "売上", "ROAS", "前週ROAS"]]
    for f, m in sorted(frame_cur.items(), key=lambda kv: -kv[1]["spend"]):
        p = frame_prev.get(f, {"spend": 0, "cv": 0, "rev": 0})
        data.append([f, yen(m["spend"]), f"{m['cv']:.0f}", yen(m["rev"]) if m["rev"] else "—",
                     f"{roas(m):.1f}" if m["rev"] else "—", f"{roas(p):.1f}" if p["rev"] else "—"])
    return table(data, [46 * mm, 26 * mm, 14 * mm, 28 * mm, 18 * mm, 20 * mm])


def sec_products(products):
    sold = [p for p in products.values() if p["cv"] >= 1]
    if not sold:
        return Paragraph("今週、Googleショッピング広告からの購入はありませんでした。", S["body"])
    data = [["商品", "ブランド", "クリック", "広告費", "購入", "売上"]]
    for p in sorted(sold, key=lambda p: -p["rev"])[:15]:
        data.append([Paragraph(p["title"][:40], S["cell"]), p["brand"], f"{p['clicks']}", yen(p["spend"]),
                     f"{p['cv']:.0f}", yen(p["rev"])])
    return table(data, [66 * mm, 26 * mm, 16 * mm, 20 * mm, 12 * mm, 26 * mm])


def sec_catalog_ads(m_ads, m_ads_prev):
    rows = [a for a in m_ads if frame_of(a["campaign"]) == "カタログ" and a["spend"] > 0]
    if not rows:
        return Paragraph("今週、Metaカタログ広告の配信はありませんでした。", S["body"])
    prev = {a["id"]: a for a in m_ads_prev}
    data = [["広告（ブランド／シリーズ）", "広告費", "表示", "購入", "売上", "ROAS", "前週売上"]]
    for a in sorted(rows, key=lambda a: -a["spend"]):
        label = re.sub(r"^fullmarks-dpa-", "", a["name"]).replace("NORRONA_", "NORRØNA ")
        p = prev.get(a["id"], {"rev": 0})
        data.append([label, yen(a["spend"]), f"{a['imp']:,}", f"{a['cv']:.0f}",
                     yen(a["rev"]) if a["rev"] else "—", f"{roas(a):.1f}" if a["rev"] else "—",
                     yen(p["rev"]) if p["rev"] else "—"])
    return table(data, [46 * mm, 22 * mm, 18 * mm, 12 * mm, 24 * mm, 14 * mm, 24 * mm])


def _event_ids():
    p = Path(__file__).resolve().parent.parent / "targets.json"
    try:
        return set(json.loads(p.read_text(encoding="utf-8")).get("event_campaign_ids", []))
    except Exception:
        return set()


EVENT_IDS = _event_ids()


def sec_campaigns(cur, prev_rows):
    prev = {c["id"]: c for c in prev_rows}
    data = [["キャンペーン", "広告費", "前週比", "購入", "売上", "ROAS", "前週ROAS"]]
    for c in sorted(cur, key=lambda c: -c["spend"]):
        if c["spend"] <= 0:
            continue
        p = prev.get(c["id"], {"spend": 0, "cv": 0, "rev": 0})
        label = disp(c["name"]) + ("【イベント枠】" if c["id"] in EVENT_IDS else "")
        data.append([Paragraph(label, S["cell"]), yen(c["spend"]), pct(c["spend"], p["spend"]),
                     f"{c['cv']:.0f}", yen(c["rev"]) if c["rev"] else "—",
                     f"{roas(c):.1f}" if c["rev"] else "—", f"{roas(p):.1f}" if p["rev"] else "—"])
    cur_ids = {c["id"] for c in cur if c["spend"] > 0}
    for p in sorted(prev_rows, key=lambda r: -r["spend"]):
        if p["id"] not in cur_ids and p["spend"] > 0:
            data.append([Paragraph(disp(p["name"]) + "（今週配信なし）", S["cell"]), "¥0", pct(0, p["spend"]),
                         "0", "—", "—", f"{roas(p):.1f}" if p["rev"] else "—"])
    return table(data, [62 * mm, 22 * mm, 16 * mm, 12 * mm, 24 * mm, 14 * mm, 18 * mm])


def sec_daily(g_daily, m_daily, since, until):
    data = [["日付", "曜", "Google 費用", "Google 売上", "Meta 費用", "Meta 売上", "合計費用", "合計売上", "ROAS"]]
    d = since
    tot = defaultdict(float)
    while d <= until:
        k = d.isoformat(); g = g_daily.get(k, {"spend": 0, "rev": 0}); m = m_daily.get(k, {"spend": 0, "rev": 0})
        sp, rv = g["spend"] + m["spend"], g["rev"] + m["rev"]
        tot["gs"] += g["spend"]; tot["gr"] += g["rev"]; tot["ms"] += m["spend"]; tot["mr"] += m["rev"]
        data.append([k, "月火水木金土日"[d.weekday()], yen(g["spend"]), yen(g["rev"]), yen(m["spend"]), yen(m["rev"]),
                     yen(sp), yen(rv), f"{rv / sp:.1f}" if sp else "—"])
        d += timedelta(days=1)
    sp, rv = tot["gs"] + tot["ms"], tot["gr"] + tot["mr"]
    data.append(["合計", "", yen(tot["gs"]), yen(tot["gr"]), yen(tot["ms"]), yen(tot["mr"]), yen(sp), yen(rv),
                 f"{rv / sp:.1f}" if sp else "—"])
    tb = table(data, [22 * mm, 8 * mm, 20 * mm, 22 * mm, 20 * mm, 22 * mm, 20 * mm, 22 * mm, 12 * mm], align_right_from=2)
    tb.setStyle(TableStyle([("BACKGROUND", (0, len(data) - 1), (-1, len(data) - 1), colors.HexColor("#dfe7f3"))]))
    return tb


def sec_pacing(meta_client, google_client, today):
    p = Path(__file__).resolve().parent.parent / "targets.json"
    if not p.exists():
        return None
    t = json.loads(p.read_text(encoding="utf-8"))
    ms = today.replace(day=1); until = today - timedelta(days=1)
    if until < ms:
        return None
    ev_ids = set(t.get("event_campaign_ids", []))
    m_c, _, _ = meta_data(meta_client, ms, until)
    camps = list(m_c)
    if google_client:
        g_c, _, _, _, _ = google_data(google_client, ms, until)
        camps += g_c
    normal = total_of([c for c in camps if c["id"] not in ev_ids])
    event = total_of([c for c in camps if c["id"] in ev_ids])
    reserve = t.get("event_reserve", 0)
    budget = t.get("normal_budget_ex_tax", t["monthly_budget_ex_tax"] - reserve)
    dim = (ms.replace(month=ms.month % 12 + 1, day=1) - timedelta(days=1)).day
    el = (until - ms).days + 1
    pace = budget * el / dim
    proj = normal["spend"] / el * dim
    data = [["項目", "実績", "目安", "評価"],
            [f"通常運用の広告費（{ms.month}/1〜{until.month}/{until.day}）", yen(normal["spend"]),
             f"{yen(pace)}（{el}/{dim}日）", "順調" if normal["spend"] >= pace * 0.9 else "未消化ペース"],
            ["通常運用の月末着地見込み", yen(proj), f"{yen(budget)}（通常運用）", f"{proj / budget:.0%}"],
            ["通常運用のROAS", f"{roas(normal):.1f}", f"{t.get('min_roas', 0):.0f} 以上",
             "達成" if roas(normal) >= t.get("min_roas", 0) else "未達"]]
    if ev_ids:
        label = "、".join(e.get("label", "") for e in t.get("events", [])) or "企画"
        data.append([f"イベント枠の広告費（{label}）※通常と別に使った分だけ計上", yen(event["spend"]),
                     f"予備費 {yen(reserve)} まで",
                     f"{event['spend'] / reserve:.0%}" if reserve else "—"])
        data.append(["イベント枠のROAS", f"{roas(event):.1f}" if event["spend"] else "—", "", ""])
    return table(data, [60 * mm, 30 * mm, 46 * mm, 26 * mm])


def sec_event(meta_client, google_client, today):
    """イベント枠（EC企画）: 企画ごとに Meta キャンペーン／Google プロモーション アセットを別建てで集計。"""
    from ads_manager.event_report import event_summary, load_events
    out = []
    for ev in load_events():
        if date.fromisoformat(ev["start"]) > today - timedelta(days=1):
            continue
        sm = event_summary(meta_client, google_client, ev, today - timedelta(days=1))
        data = [["媒体", "キャンペーン／アセット", "広告費", "表示", "クリック", "購入", "売上", "ROAS"]]
        for r in sm["rows"]:
            data.append([r["media"], Paragraph(disp(r["name"]), S["cell"]), yen(r["spend"]), f"{r['imp']:,}",
                         f"{r['clicks']:,}", f"{r['cv']:.0f}", yen(r["rev"]) if r["rev"] else "—",
                         f"{r['rev'] / r['spend']:.1f}" if r["spend"] and r["rev"] else "—"])
        t = sm["total"]
        data.append(["", "合計", yen(t["spend"]), "", "", f"{t['cv']:.0f}", yen(t["rev"]) if t["rev"] else "—",
                     f"{t['rev'] / t['spend']:.1f}" if t["spend"] and t["rev"] else "—"])
        tb = table(data, [14 * mm, 62 * mm, 20 * mm, 16 * mm, 16 * mm, 12 * mm, 22 * mm, 14 * mm], align_right_from=2)
        tb.setStyle(TableStyle([("BACKGROUND", (0, len(data) - 1), (-1, len(data) - 1), colors.HexColor("#dfe7f3"))]))
        title = f"{ev['label']}（{ev['start']}〜{ev['end']}、集計 {sm['since']}〜{sm['until']}）"
        note = (f"イベント予算（税抜）{yen(sm['reserve'])} に対する Meta 消化 {yen(sm['meta_spend'])}"
                f"（{sm['meta_spend'] / sm['reserve']:.0%}）。" if sm["reserve"] else "") + sm["note"]
        out += [KeepTogether([Paragraph(title, S["h2"]), tb]), Paragraph(note, S["note"])]
    return out


def sec_adset_compare(meta_client, since, until):
    """同じキャンペーン内に広告セットが複数あるもの（全員向け vs 絞った配信の比較テスト）を並べる。"""
    acct = meta_client.config.ad_account_id
    tr = json.dumps({"since": str(since), "until": str(until)})
    rows = meta_client.get_all(f"{acct}/insights", level="adset", time_range=tr, limit=200,
                               fields="campaign_id,campaign_name,adset_name,spend,impressions,reach,frequency,clicks,actions,action_values")
    by = defaultdict(list)
    for r in rows:
        m = _mm(r)
        if m["spend"] > 0:
            by[r["campaign_id"]].append({"camp": r["campaign_name"], "adset": r["adset_name"],
                                         "freq": float(r.get("frequency") or 0), **m})
    data = [["キャンペーン／広告セット", "広告費", "頻度", "購入", "売上", "ROAS"]]
    for cid, lst in by.items():
        if len(lst) < 2 or cid in EVENT_IDS:
            continue
        for x in sorted(lst, key=lambda x: -x["spend"]):
            label = disp(x["camp"]) + " / " + ("全員向け" if "全員" in x["adset"] else re.sub(r"^UCDN\d_", "", x["adset"]))
            data.append([Paragraph(label, S["cell"]), yen(x["spend"]), f"{x['freq']:.1f}", f"{x['cv']:.0f}",
                         yen(x["rev"]) if x["rev"] else "—", f"{roas(x):.1f}" if x["rev"] else "—"])
    if len(data) == 1:
        return None
    return table(data, [80 * mm, 24 * mm, 14 * mm, 14 * mm, 26 * mm, 16 * mm])


def sec_audit(meta_client, google_client, g_labels):
    lines = []
    audit = meta_audit(meta_client, check_links=True)
    broken = [r for r in audit["問題のある広告"] if any("リンク切れ" in f or "リダイレクト" in f for f in r["flags"])]
    lines.append(f"Meta: 配信中 {audit['summary']['調査対象']}本のリンクを検査 → リンク切れ {len(broken)}件")
    lines += [f"　※ {r['campaign']} / {r['ad_name']}: " + "; ".join(r["flags"]) for r in broken]
    if google_client:
        try:
            from ads_manager.creatives import google_list_creatives
            g_all = google_list_creatives(google_client)
            g_ads = [a for a in g_all if a["serving"]]
            g_broken = []
            for a in g_ads:
                for url in a["final_urls"]:
                    res = check_url(url)
                    if res["status"] is not None and res["status"] >= 400:
                        g_broken.append(f"{a['campaign']} / {a['ad_id']}: {url} ({res['status']})")
            lines.append(f"Google: 配信中 {len(g_ads)}本のリンクを検査 → リンク切れ {len(g_broken)}件"
                         f"（停止中キャンペーンの広告 {len(g_all) - len(g_ads)}本は対象外。再開時は要リンク確認）")
            lines += [f"　※ {b}" for b in g_broken]
        except Exception as e:
            lines.append(f"Google: リンク確認を実行できませんでした（{type(e).__name__}）")
        by_c = g_labels.get("outlet", {}); out = sum(by_c.values())
        lines.append(f"アウトレット品のショッピング表示: {out:,}回（方針: アウトレット品は広告しない）")
        if out:
            lines += [f"　※ {disp(c)}: {n:,}回（停止済みの枠なら停止前の表示。稼働中なら除外設定を確認）"
                      for c, n in sorted(by_c.items(), key=lambda kv: -kv[1]) if n]
    # 他口座
    try:
        other = []
        for acct, name in [("act_587527895389459", "フルマークス/MDX"), ("act_719498040184021", "認知施策用/MDX")]:
            d = meta_client.get(f"{acct}/insights", fields="spend", date_preset="this_month").get("data", [])
            other.append(f"{name} {yen(float(d[0]['spend']) if d else 0)}")
        lines.append("他口座の当月消化（回してはいけない口座）: " + "、".join(other))
    except Exception as e:
        lines.append(f"他口座の消化確認: 取得できませんでした（{type(e).__name__}）")
    return [Paragraph(l.lstrip("　").lstrip("※ "), S["bullet"] if not l.startswith("　") else S["sub_bullet"],
                      bulletText="■" if not l.startswith("　") else "※") for l in lines]


# ---------------- main ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=f"reports/広告週次レポート_{date.today()}.pdf")
    args = ap.parse_args()
    today = date.today()
    cs, cu = today - timedelta(days=7), today - timedelta(days=1)
    ps, pu = today - timedelta(days=14), today - timedelta(days=8)

    meta_client = MetaAdsClient(load_meta_config())
    m_camps, m_ads, m_daily = meta_data(meta_client, cs, cu)
    m_camps_p, m_ads_p, _ = meta_data(meta_client, ps, pu)
    google_client = None
    g_camps = g_camps_p = []; g_daily = {}; g_shop = {}; g_shop_p = {}; g_products = {}; g_labels = {}
    g_err = None
    try:
        from ads_manager.google_ads_client import GoogleAdsClientWrapper
        google_client = GoogleAdsClientWrapper(load_google_config())
        g_camps, g_daily, g_shop, g_products, g_labels = google_data(google_client, cs, cu)
        g_camps_p, _, g_shop_p, _, _ = google_data(google_client, ps, pu)
    except Exception as e:
        g_err = f"{type(e).__name__}"; google_client = None

    cur = total_of(g_camps + m_camps); prev = total_of(g_camps_p + m_camps_p)
    brand_cur = by_brand(g_camps, g_shop, m_ads); brand_prev = by_brand(g_camps_p, g_shop_p, m_ads_p)
    frame_cur = by_frame(g_camps, m_camps); frame_prev = by_frame(g_camps_p, m_camps_p)

    story = [Paragraph("広告 週次レポート", S["title"]),
             Paragraph(f"対象: {cs} 〜 {cu}（前週 {ps} 〜 {pu}）　媒体: Google広告 + Meta広告　"
                       "売上は各媒体計測のCV金額（税込）", S["sub"]), Spacer(1, 5 * mm)]
    if g_err:
        story.append(Paragraph(f"※ Google Ads API に接続できなかったため Google の数値は含まれていません（{g_err}）", S["body"]))

    # 1. サマリー
    story.append(Paragraph("1. サマリー", S["h1"]))
    story.append(kpi_tiles(cur, prev))
    story.append(Paragraph("今週のポイント", S["h2"]))
    hl = highlights(brand_cur, brand_prev, frame_cur, g_camps + m_camps, g_camps_p + m_camps_p)
    for line in hl or ["特筆事項なし"]:
        story.append(Paragraph(line, S["bullet"], bulletText="■"))
    pac = sec_pacing(meta_client, google_client, today)
    if pac:
        story.append(KeepTogether([Paragraph("月間ペース（targets.json の通常運用予算に対して）", S["h2"]), pac]))

    ev = sec_event(meta_client, google_client, today)
    if ev:
        story.append(Paragraph("イベント枠（EC企画・通常運用と別予算）", S["h2"]))
        story.extend(ev)

    # 2. 何が売れたか
    story.append(Paragraph("2. 何が売れたか", S["h1"]))
    story.append(KeepTogether([Paragraph("ブランド別（広告経由の売上順）", S["h2"]), sec_brand(brand_cur, brand_prev)]))
    story.append(Paragraph("ブランドの判定: 指名検索と静止画はキャンペーン名、ショッピングは商品のブランド属性、"
                           "Metaカタログは広告（ブランド／シリーズ別）から。店舗指名はブランド横断のため別建て。", S["note"]))
    story.append(KeepTogether([Paragraph("枠別", S["h2"]), sec_frame(frame_cur, frame_prev)]))
    story.append(KeepTogether([Paragraph("Googleショッピングで売れた商品", S["h2"]), sec_products(g_products)]))
    story.append(KeepTogether([Paragraph("Metaカタログ広告（ブランド／シリーズ別）", S["h2"]), sec_catalog_ads(m_ads, m_ads_p)]))
    story.append(Paragraph("Metaは商品単位の購入データを返さないため、カタログ広告は広告（ブランド／シリーズ）単位で表示。", S["note"]))

    # 3. キャンペーン別
    story.append(Paragraph("3. キャンペーン別", S["h1"]))
    if google_client:
        story.append(KeepTogether([Paragraph("Google", S["h2"]), sec_campaigns(g_camps, g_camps_p)]))
    story.append(KeepTogether([Paragraph("Meta", S["h2"]), sec_campaigns(m_camps, m_camps_p)]))
    cmp_tb = sec_adset_compare(meta_client, cs, cu)
    if cmp_tb:
        story.append(KeepTogether([Paragraph("Meta 配信先の比較（全員向け vs 絞った配信）", S["h2"]), cmp_tb]))
        story.append(Paragraph("同じキャンペーン内で予算を奪い合う形。ROASの高い方に寄せる判断材料（2026-09-23 開始のテスト）。", S["note"]))

    # 4. 日別
    story.append(KeepTogether([Paragraph("4. 日別推移（Google + Meta）", S["h1"]), sec_daily(g_daily, m_daily, cs, cu)]))

    # 5. 監査
    story.append(Paragraph("5. 監査", S["h1"]))
    story.extend(sec_audit(meta_client, google_client, g_labels))

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    def _footer(canvas, doc):
        canvas.saveState(); canvas.setFont(FONT, 7.5); canvas.setFillColor(GREY)
        canvas.drawString(15 * mm, 9 * mm, f"FULLMARKS 広告週次レポート  {cs} 〜 {cu}")
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"{doc.page}")
        canvas.restoreState()

    SimpleDocTemplate(str(out), pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm,
                      leftMargin=15 * mm, rightMargin=15 * mm, title="広告 週次レポート"
                      ).build(story, onFirstPage=_footer, onLaterPages=_footer)
    print(f"PDFを生成: {out}")


if __name__ == "__main__":
    main()

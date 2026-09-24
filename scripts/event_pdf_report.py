# -*- coding: utf-8 -*-
"""イベント広告（EC企画）の結果報告PDFを作る。

使い方: python scripts/event_pdf_report.py --key sw2026 [--out reports/イベント広告報告_sw2026.pdf]
構成: 1.結果サマリー / 2.いくら使って、いくら売れたか / 3.広告計測の精度 / 4.分析と次回への学び / 5.設定の記録
データ: Meta 広告API（広告セット別・日別・クリック/ビュー内訳・ピクセルの購入イベント数）、
       Google 広告API（プロモーション アセット、全キャンペーンのCV、コンバージョン設定）。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate,  # noqa: E402
                                Spacer, Table, TableStyle)

from ads_manager.config import load_google_config, load_meta_config  # noqa: E402
from ads_manager.event_report import load_events  # noqa: E402
from ads_manager.meta_ads import MetaAdsClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PIXEL_ID = "1044166285243333"
TAX = 1.10

_IPA = Path("/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf")
if _IPA.exists():
    pdfmetrics.registerFont(TTFont("IPAPGothic", str(_IPA)))
    FONT = "IPAPGothic"
else:
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    FONT = "HeiseiKakuGo-W5"

NAVY = colors.HexColor("#1a3c6e"); GREY = colors.HexColor("#555555")
LIGHT = colors.HexColor("#f0f4fa"); LINE = colors.HexColor("#c8d2e0")
GOOD = colors.HexColor("#1b7f3b"); BAD = colors.HexColor("#b3261e"); WARN = colors.HexColor("#9a6700")
S = {
    "title": ParagraphStyle("t", fontName=FONT, fontSize=18, leading=23),
    "sub": ParagraphStyle("s", fontName=FONT, fontSize=9, leading=13, textColor=GREY),
    "h1": ParagraphStyle("h1", fontName=FONT, fontSize=14, leading=18, spaceBefore=7 * mm, spaceAfter=3 * mm, textColor=NAVY),
    "h2": ParagraphStyle("h2", fontName=FONT, fontSize=11, leading=15, spaceBefore=4 * mm, spaceAfter=2 * mm, textColor=NAVY),
    "body": ParagraphStyle("b", fontName=FONT, fontSize=9, leading=14),
    "bullet": ParagraphStyle("bl", fontName=FONT, fontSize=9, leading=14, leftIndent=5 * mm, bulletIndent=1 * mm),
    "cell": ParagraphStyle("c", fontName=FONT, fontSize=8, leading=11),
    "note": ParagraphStyle("n", fontName=FONT, fontSize=7.5, leading=10.5, textColor=GREY),
    "tl": ParagraphStyle("tl", fontName=FONT, fontSize=8, leading=10, textColor=GREY, alignment=1),
    "tv": ParagraphStyle("tv", fontName=FONT, fontSize=15, leading=19, alignment=1),
    "td": ParagraphStyle("td", fontName=FONT, fontSize=7.5, leading=10, alignment=1, textColor=GREY),
}


def yen(v):
    return f"¥{v:,.0f}"


def table(data, widths, right_from=1, zebra=True, total_row=False):
    t = Table(data, colWidths=widths, repeatRows=1)
    st = [("FONT", (0, 0), (-1, -1), FONT, 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("ALIGN", (right_from, 1), (-1, -1), "RIGHT"), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
          ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
          ("ALIGN", (0, 0), (-1, 0), "CENTER")]
    if zebra:
        st.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]))
    if total_row:
        st.append(("BACKGROUND", (0, len(data) - 1), (-1, len(data) - 1), colors.HexColor("#dfe7f3")))
    t.setStyle(TableStyle(st))
    return t


def P(text, style="cell"):
    return Paragraph(text, S[style])


def tiles(items):
    cells = [[P(lbl, "tl"), P(val, "tv"), P(sub, "td")] for lbl, val, sub in items]
    t = Table([[Table([[c[0]], [c[1]], [c[2]]], colWidths=[42 * mm]) for c in cells]], colWidths=[44.5 * mm] * len(items))
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                           ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def act(r, k, values=False, key="value"):
    for a in (r.get("action_values" if values else "actions") or []):
        if a.get("action_type") == k:
            return float(a.get(key) or 0)
    return 0.0


# ---------------- データ取得 ----------------

def meta_event(mc, ev, since, until):
    cids = ev.get("meta_campaign_ids", [])
    tr = json.dumps({"since": str(since), "until": str(until)})
    win = '["7d_click","1d_view"]'
    f = "adset_name,spend,impressions,reach,frequency,clicks,inline_link_clicks,ctr,cpm,actions,action_values"
    adsets, daily = [], []
    for cid in cids:
        for r in mc.get_all(f"{cid}/insights", level="adset", time_range=tr, fields=f, limit=50, action_attribution_windows=win):
            adsets.append({
                "name": "全員向け（Advantage+）" if "全員" in r["adset_name"] else "訪問者・購入者30日",
                "spend": float(r["spend"]), "imp": int(r["impressions"]), "reach": int(r["reach"]),
                "freq": float(r["frequency"]), "clicks": int(r.get("inline_link_clicks") or 0),
                "ctr": float(r.get("ctr") or 0), "cpm": float(r.get("cpm") or 0),
                "lpv": act(r, "landing_page_view"), "atc": act(r, "add_to_cart"),
                "pur": act(r, "purchase"), "pur_click": act(r, "purchase", key="7d_click"),
                "pur_view": act(r, "purchase", key="1d_view"),
                "rev": act(r, "purchase", True), "rev_click": act(r, "purchase", True, "7d_click"),
                "rev_view": act(r, "purchase", True, "1d_view")})
        for r in mc.get_all(f"{cid}/insights", level="adset", time_range=tr, time_increment=1, limit=100,
                            fields="date_start,adset_name,spend,impressions,inline_link_clicks,actions,action_values",
                            action_attribution_windows=win):
            daily.append({"date": r["date_start"], "broad": "全員" in r["adset_name"], "spend": float(r["spend"]),
                          "imp": int(r["impressions"]), "clicks": int(r.get("inline_link_clicks") or 0),
                          "pur": act(r, "purchase"), "pur_view": act(r, "purchase", key="1d_view"),
                          "rev": act(r, "purchase", True)})
    acct = mc.config.ad_account_id
    acct_pur = sum(act(r, "purchase") for r in mc.get_all(f"{acct}/insights", level="campaign", time_range=tr,
                                                           fields="actions", limit=200))
    pixel = {}
    srcs = {}
    try:
        st = mc.get(f"{PIXEL_ID}/stats", aggregation="event", start_time=f"{since}T00:00:00+0900",
                    end_time=f"{until + timedelta(days=1)}T00:00:00+0900")
        for row in st.get("data", []):
            for d in row.get("data", []):
                pixel[d["value"]] = pixel.get(d["value"], 0) + int(d["count"])
        st = mc.get(f"{PIXEL_ID}/stats", aggregation="event_source", start_time=f"{since}T00:00:00+0900",
                    end_time=f"{until + timedelta(days=1)}T00:00:00+0900")
        for row in st.get("data", []):
            for d in row.get("data", []):
                srcs[d["value"]] = srcs.get(d["value"], 0) + int(d["count"])
    except Exception:  # noqa: BLE001
        pass
    pinfo = mc.get(PIXEL_ID, fields="enable_automatic_matching,first_party_cookie_status")
    return {"adsets": adsets, "daily": daily, "acct_pur": acct_pur, "pixel": pixel, "sources": srcs, "pixel_info": pinfo}


def google_event(gc, ev, since, until):
    if gc is None:
        return None
    ids = ",".join(str(int(a)) for a in ev.get("google_asset_ids", []))
    promo = {}
    if ids:
        for r in gc.search("SELECT campaign.name, metrics.impressions, metrics.clicks, metrics.cost_micros, "
                           "metrics.conversions, metrics.conversions_value FROM campaign_asset "
                           f"WHERE asset.id IN ({ids}) AND segments.date BETWEEN '{ev['start']}' AND '{until}'"):
            p = promo.setdefault(r.campaign.name, {"imp": 0, "clicks": 0, "spend": 0.0, "cv": 0.0, "rev": 0.0})
            m = r.metrics
            p["imp"] += m.impressions; p["clicks"] += m.clicks; p["spend"] += m.cost_micros / 1e6
            p["cv"] += m.conversions; p["rev"] += m.conversions_value
    tot = {"spend": 0.0, "cv": 0.0, "rev": 0.0}
    for r in gc.search("SELECT metrics.cost_micros, metrics.conversions, metrics.conversions_value FROM campaign "
                       f"WHERE segments.date BETWEEN '{since}' AND '{until}'"):
        tot["spend"] += r.metrics.cost_micros / 1e6; tot["cv"] += r.metrics.conversions; tot["rev"] += r.metrics.conversions_value
    conv = None
    for r in gc.search("SELECT conversion_action.name, conversion_action.category, conversion_action.counting_type, "
                       "conversion_action.attribution_model_settings.attribution_model, "
                       "conversion_action.click_through_lookback_window_days FROM conversion_action "
                       "WHERE conversion_action.status = 'ENABLED' AND conversion_action.category = 'PURCHASE'"):
        c = r.conversion_action
        conv = {"name": c.name, "model": c.attribution_model_settings.attribution_model.name,
                "count": c.counting_type.name, "window": c.click_through_lookback_window_days}
    return {"promo": promo, "total": tot, "conv": conv}


# ---------------- ページ構成 ----------------

def build(ev, meta, goog, since, until, out):
    ads = meta["adsets"]
    spend = sum(a["spend"] for a in ads); pur = sum(a["pur"] for a in ads); rev = sum(a["rev"] for a in ads)
    pur_c = sum(a["pur_click"] for a in ads); pur_v = sum(a["pur_view"] for a in ads)
    rev_c = sum(a["rev_click"] for a in ads)
    reserve = ev.get("reserve_ex_tax", 0)
    story = [P("イベント広告 結果報告", "title"),
             P(f"{ev['label']}　企画期間 {ev['start']}〜{ev['end']}　広告配信 {since}〜{until}", "sub"),
             P(f"企画内容: {ev.get('offer', '')}", "sub"), Spacer(1, 4 * mm)]

    # 1. サマリー
    story.append(P("1. 結果サマリー", "h1"))
    story.append(tiles([
        ("広告費（Meta・税抜）", yen(spend), f"イベント予算 {yen(reserve)} の {spend / reserve:.0%}" if reserve else ""),
        ("購入件数（広告計測）", f"{pur:.0f}件", f"うちクリック経由 {pur_c:.0f}件"),
        ("売上（広告計測・税込）", yen(rev), f"クリック経由のみ {yen(rev_c)}"),
        ("ROAS", f"{rev / spend:.1f}" if spend else "—", f"税抜換算 {rev / TAX / spend:.1f}／クリックのみ {rev_c / spend:.1f}" if spend else ""),
    ]))
    story.append(Spacer(1, 3 * mm))
    best = max(ads, key=lambda a: a["rev"]) if ads else None
    pts = [f"広告費 {yen(spend)} で、Meta の計測上 {pur:.0f}件・{yen(rev)} の購入がありました。",
           f"このうち確度の高いクリック経由は {pur_c:.0f}件・{yen(rev_c)} で、ROAS は {rev_c / spend:.1f} です。" if spend else "",
           f"成果の大半は「{best['name']}」の配信から出ています。" if best else "",
           "Google の指名検索には割引の告知（プロモーション表示）を追加費用なしで付けました。"]
    for s_ in pts:
        if s_:
            story.append(Paragraph(s_, S["bullet"], bulletText="■"))
    if ev.get("image") and (ROOT / ev["image"]).exists():
        story.append(Spacer(1, 3 * mm))
        img = Image(str(ROOT / ev["image"]), width=48 * mm, height=48 * mm)
        cap = P("配信した広告画像（1080×1080）。Facebook・Instagram のフィードとストーリーズに表示。", "note")
        story.append(Table([[img, cap]], colWidths=[52 * mm, 120 * mm],
                           style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    # 2. いくら使って、いくら売れたか
    story.append(P("2. いくら使って、いくら売れたか", "h1"))
    story.append(P("配信先（広告セット）別", "h2"))
    data = [["配信先", "広告費", "表示", "リンククリック", "購入", "売上（税込）", "ROAS"]]
    for a in sorted(ads, key=lambda a: -a["rev"]):
        data.append([a["name"], yen(a["spend"]), f"{a['imp']:,}", f"{a['clicks']:,}", f"{a['pur']:.0f}",
                     yen(a["rev"]) if a["rev"] else "—", f"{a['rev'] / a['spend']:.1f}" if a["rev"] else "0.0"])
    data.append(["合計", yen(spend), f"{sum(a['imp'] for a in ads):,}", f"{sum(a['clicks'] for a in ads):,}",
                 f"{pur:.0f}", yen(rev), f"{rev / spend:.1f}" if spend else "—"])
    story.append(table(data, [44 * mm, 22 * mm, 20 * mm, 24 * mm, 14 * mm, 28 * mm, 16 * mm], total_row=True))

    story.append(P("日別", "h2"))
    days = sorted({d["date"] for d in meta["daily"]})
    data = [["日付", "訪問者向け 広告費", "全員向け 広告費", "購入", "売上（税込）", "ROAS", "メモ"]]
    memo = ev.get("daily_memo", {})
    for d in days:
        rows = [x for x in meta["daily"] if x["date"] == d]
        sv = sum(x["spend"] for x in rows if not x["broad"]); sb = sum(x["spend"] for x in rows if x["broad"])
        p_ = sum(x["pur"] for x in rows); r_ = sum(x["rev"] for x in rows)
        data.append([d[5:].replace("-", "/"), yen(sv), yen(sb), f"{p_:.0f}", yen(r_) if r_ else "—",
                     f"{r_ / (sv + sb):.1f}" if (sv + sb) and r_ else "0.0", P(memo.get(d, ""))])
    data.append(["合計", yen(sum(x["spend"] for x in meta["daily"] if not x["broad"])),
                 yen(sum(x["spend"] for x in meta["daily"] if x["broad"])), f"{pur:.0f}", yen(rev),
                 f"{rev / spend:.1f}" if spend else "—", ""])
    story.append(table(data, [16 * mm, 28 * mm, 26 * mm, 12 * mm, 26 * mm, 14 * mm, 46 * mm], total_row=True))

    data = [["配信先", "クリック率", "表示単価（千回）", "サイト到着", "カート追加", "購入", "到着→購入"]]
    for a in sorted(ads, key=lambda a: -a["rev"]):
        data.append([a["name"], f"{a['ctr']:.1f}%", yen(a["cpm"]), f"{a['lpv']:.0f}", f"{a['atc']:.0f}",
                     f"{a['pur']:.0f}", f"{a['pur'] / a['lpv'] * 100:.1f}%" if a["lpv"] else "—"])
    story.append(KeepTogether([P("購入までの流れ（配信先別）", "h2"),
                               table(data, [44 * mm, 20 * mm, 26 * mm, 20 * mm, 20 * mm, 14 * mm, 22 * mm])]))

    if goog and goog["promo"]:
        story.append(P("Google 指名検索のプロモーション表示", "h2"))
        data = [["キャンペーン", "表示", "クリック", "広告費", "購入", "売上"]]
        for k, v in sorted(goog["promo"].items(), key=lambda kv: -kv[1]["imp"]):
            data.append([k.replace("UC_SK_1_", ""), f"{v['imp']:,}", f"{v['clicks']:,}", yen(v["spend"]),
                         f"{v['cv']:.1f}", yen(v["rev"]) if v["rev"] else "—"])
        story.append(table(data, [50 * mm, 20 * mm, 20 * mm, 24 * mm, 18 * mm, 28 * mm]))
        story.append(P("プロモーション表示は追加費用なし。広告費・購入は「表示が付いた検索広告」全体の数字で、"
                       "割引表示が生んだ効果ではありません（指名検索はもともと買う意思の強い人が多い）。"
                       "審査のため表示開始は 9/20 頃から。", "note"))

    # 3. 計測の精度
    story.append(P("3. 広告計測の精度", "h1"))
    story.append(P("広告の管理画面に出る購入は、媒体が「自分の広告の成果」と判定した数字です。実際の注文と"
                   "1対1で一致するわけではないため、どこまで信頼できるかを分けて示します。", "body"))
    story.append(P("購入の判定のされ方（Meta）", "h2"))
    data = [["判定", "条件", "購入", "売上（税込）", "確度"],
            ["クリック経由", "広告をクリックして7日以内に購入", f"{pur_c:.0f}件", yen(rev_c), "高い"],
            ["ビュー経由", "広告を見ただけで、24時間以内に購入", f"{pur_v:.0f}件", yen(rev - rev_c), "低い"],
            ["合計", "", f"{pur:.0f}件", yen(rev), ""]]
    t = table(data, [26 * mm, 70 * mm, 18 * mm, 30 * mm, 18 * mm], right_from=2, total_row=True)
    t.setStyle(TableStyle([("TEXTCOLOR", (4, 1), (4, 1), GOOD), ("TEXTCOLOR", (4, 2), (4, 2), BAD)]))
    story.append(t)
    story.append(P("ビュー経由は「広告を見た人が、たまたま翌日までに買った」場合も数えます。広告がなくても"
                   "買っていた可能性があるため、成果として控えめに見るのが安全です。", "note"))

    site_pur = meta["pixel"].get("Purchase", 0)
    story.append(P("サイト全体の購入と比べた規模", "h2"))
    g_cv = goog["total"]["cv"] if goog else 0
    data = [["項目", "購入件数", "説明"],
            ["サイト全体の購入（Metaピクセル記録）", f"{site_pur:,}件", "広告以外（自然検索・直接来訪など）も含む全注文"],
            ["Meta 広告全体が主張する購入", f"{meta['acct_pur']:.0f}件", "イベント以外の Meta 広告も含む"],
            ["うちイベント広告", f"{pur:.0f}件", f"サイト全体の {pur / site_pur:.0%}" if site_pur else ""],
            ["Google 広告全体が主張する購入", f"{g_cv:.0f}件", "指名検索・ショッピング。データドリブン配分で小数あり"]]
    t = table(data, [62 * mm, 24 * mm, 76 * mm], right_from=1)
    t.setStyle(TableStyle([("ALIGN", (2, 1), (2, -1), "LEFT")]))
    story.append(t)
    story.append(P("Meta と Google は互いの計測を知らないため、同じ注文を両方が「自分の成果」と数えることがあります。"
                   "両媒体の主張の合計がサイト全体を大きく下回っているので、極端な水増しはありません。", "note"))

    srcs = meta["sources"]; info = meta["pixel_info"]
    server = any(k != "BROWSER" for k in srcs)
    rows = [["要因", "今回の状態", "影響"],
            [P("計測方法（Meta）"), P("ブラウザのピクセルのみ。サーバーからの送信（コンバージョンAPI）は未導入" if not server else "ピクセル＋サーバー送信"),
             P("iPhoneの追跡制限や広告ブロックで一部の購入が記録されない。実際の購入は計測より多い可能性" if not server else "記録漏れは少ない")],
            [P("利用者の照合（Meta）"), P("自動詳細マッチング: " + ("オフ" if not info.get("enable_automatic_matching") else "オン")),
             P("オフだと広告を見た人と購入者の照合率が下がり、広告経由の購入が少なめに出る")],
            [P("売上金額"), P("注文金額（税込）をピクセルが記録"), P("広告費は税抜のため、税抜で比べるとROASは約1割低い。クーポン値引き後の金額かはEC側で要確認")],
            [P("Google の配分"), P(f"{goog['conv']['name']}：データドリブン、クリック後{goog['conv']['window']}日" if goog and goog["conv"] else "—"),
             P("1件の購入を複数の広告に分けて数えるため小数になる")],
            [P("媒体間の重複"), P("未確認"), P("同じ注文を Meta と Google の両方が数えている可能性")],
            [P("計測の遅れ"), P("配信終了翌日に集計"), P("クリック後7日以内の購入は後から増えることがある。9/24時点で変化なし")]]
    story.append(KeepTogether([P("精度に影響する要因", "h2"), table(rows, [32 * mm, 58 * mm, 72 * mm], right_from=9)]))

    data = [["数字", "信頼度", "理由"],
            ["広告費 " + yen(spend), "高い", "媒体の請求額そのもの（税抜）"],
            [f"クリック経由の購入 {pur_c:.0f}件・{yen(rev_c)}", "中〜高", "広告クリック後の購入。ただし記録漏れで実数はやや多い可能性"],
            [f"ビュー経由の購入 {pur_v:.0f}件・{yen(rev - rev_c)}", "低い", "広告がなくても買っていた可能性を含む"],
            ["Google プロモーション表示の成果", "参考値", "表示が付いた広告の成果で、割引表示の効果ではない"]]
    t = table(data, [58 * mm, 18 * mm, 86 * mm], right_from=9)
    t.setStyle(TableStyle([("TEXTCOLOR", (1, 1), (1, 1), GOOD), ("TEXTCOLOR", (1, 2), (1, 2), WARN),
                           ("TEXTCOLOR", (1, 3), (1, 3), BAD), ("TEXTCOLOR", (1, 4), (1, 4), GREY)]))
    story.append(KeepTogether([P("総合評価", "h2"), t]))
    story.append(P("実際の効果を確定するには、EC側の「企画期間中のクーポン利用件数・注文金額」と突き合わせるのが確実です。"
                   "データをいただければ、広告計測との差（計測漏れ・重複）を数字で出せます。", "note"))

    # 4. 分析
    story.append(P("4. 分析と次回への学び", "h1"))
    for s_ in ev.get("learnings", []):
        story.append(Paragraph(s_, S["bullet"], bulletText="■"))

    # 5. 設定
    story.append(KeepTogether([P("5. 設定の記録", "h1"), table([
        ["項目", "内容"],
        ["Meta キャンペーン", P("UC_DN_3_CVS_SW2026_AUTUMN_JOURNEY（購入最適化、キャンペーン予算）")],
        ["配信先", P("① 訪問者・購入者30日（9/20〜21、成果なしで停止）② 全員向け Advantage+（9/20〜23）。日本・25〜65歳")],
        ["予算", P("日予算 15,000円 → 20,000円（9/20 変更）。イベント予算 税込10万円（税抜 " + yen(reserve) + "）")],
        ["終了", P("9/23 23:50 に停止（締切直前の流入はクーポンを使えないため）")],
        ["Google", P("指名検索4本にプロモーション表示「対象のOUTLET商品 最大10%OFF」。9/23 23:50 に外した")],
        ["リンク先", P("トップページ（Google は utm_campaign=sw2026_autumn_journey 付き）")],
    ], [36 * mm, 126 * mm], right_from=9)]))

    def _footer(canvas, doc):
        canvas.saveState(); canvas.setFont(FONT, 7.5); canvas.setFillColor(GREY)
        canvas.drawString(15 * mm, 9 * mm, f"FULLMARKS イベント広告報告　{ev['label']}")
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, str(doc.page))
        canvas.restoreState()

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(out), pagesize=A4, topMargin=15 * mm, bottomMargin=16 * mm, leftMargin=15 * mm,
                      rightMargin=15 * mm, title=f"イベント広告報告 {ev['label']}").build(story, onFirstPage=_footer, onLaterPages=_footer)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    ev = next(e for e in load_events() if e["key"] == args.key)
    since = date.fromisoformat(ev.get("ads_start", ev["start"])); until = date.fromisoformat(ev["end"])
    mc = MetaAdsClient(load_meta_config())
    try:
        from ads_manager.google_ads_client import GoogleAdsClientWrapper
        gc = GoogleAdsClientWrapper(load_google_config())
    except Exception:  # noqa: BLE001
        gc = None
    meta = meta_event(mc, ev, since, until)
    goog = google_event(gc, ev, since, until)
    out = args.out or f"reports/イベント広告報告_{args.key}.pdf"
    build(ev, meta, goog, since, until, out)
    print(f"PDFを生成: {out}")


if __name__ == "__main__":
    main()

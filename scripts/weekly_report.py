# -*- coding: utf-8 -*-
"""週次の広告成果レポート（Meta + Google）をPDF生成する。

使い方:
  python scripts/weekly_report.py [--out reports/週次レポート.pdf]

内容:
  1. Meta: 直近7日のサマリー / キャンペーン別 / 広告別 / 日別推移
  2. Google: 直近7日のキャンペーン別成果（API接続できる場合）
  3. リンク切れチェック: Meta配信中広告 + Google広告の最終URL
Google Ads API に接続できない場合（開発者トークン無効など）は
その旨をレポートに記載してMetaのみで生成する。
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from ads_manager.audit import check_url, meta_audit
from ads_manager.config import load_google_config, load_meta_config
from ads_manager.meta_ads import MetaAdsClient

pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
FONT = "HeiseiKakuGo-W5"

STYLES = {
    "title": ParagraphStyle("t", fontName=FONT, fontSize=18, leading=24,
                            spaceAfter=2 * mm),
    "sub": ParagraphStyle("s", fontName=FONT, fontSize=9.5, leading=13,
                          textColor=colors.HexColor("#555555")),
    "h2": ParagraphStyle("h", fontName=FONT, fontSize=13, leading=18,
                         spaceBefore=7 * mm, spaceAfter=2.5 * mm,
                         textColor=colors.HexColor("#1a3c6e")),
    "body": ParagraphStyle("b", fontName=FONT, fontSize=9.5, leading=15),
    "cell": ParagraphStyle("c", fontName=FONT, fontSize=8, leading=10),
}


def table(data, widths, align_right_from=1):
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), FONT, 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c6e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (align_right_from, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f0f4fa")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d2e0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def yen(v):
    return f"¥{v:,.0f}"


def act(row, key):
    for a in row.get("actions") or []:
        if a["action_type"] == key:
            return float(a["value"])
    return 0.0


def actv(row, key):
    for a in row.get("action_values") or []:
        if a["action_type"] == key:
            return float(a["value"])
    return 0.0


def metrics(r):
    spend = float(r.get("spend") or 0)
    imp = int(r.get("impressions") or 0)
    clicks = int(r.get("clicks") or 0)
    pur = act(r, "omni_purchase")
    rev = actv(r, "omni_purchase")
    return {
        "spend": spend, "imp": imp, "clicks": clicks,
        "ctr": (clicks / imp * 100) if imp else 0,
        "cpc": (spend / clicks) if clicks else 0,
        "pur": pur, "rev": rev,
        "cpa": (spend / pur) if pur else 0,
        "roas": (rev / spend) if spend else 0,
    }


def meta_sections(story):
    client = MetaAdsClient(load_meta_config())
    acct = client.config.ad_account_id
    common = dict(date_preset="last_7d",
                  fields="campaign_name,ad_name,impressions,clicks,spend,"
                         "actions,action_values")
    camps = client.get(f"{acct}/insights", level="campaign",
                       **common).get("data", [])
    ads = client.get(f"{acct}/insights", level="ad", **common).get("data", [])
    daily = sorted(
        client.get(f"{acct}/insights", level="account", time_increment=1,
                   **common).get("data", []),
        key=lambda r: r["date_start"])
    period = (f"{daily[0]['date_start']} 〜 {daily[-1]['date_stop']}"
              if daily else "直近7日")

    total = metrics({
        "spend": sum(float(r.get("spend") or 0) for r in daily),
        "impressions": sum(int(r.get("impressions") or 0) for r in daily),
        "clicks": sum(int(r.get("clicks") or 0) for r in daily),
        "actions": [{"action_type": "omni_purchase",
                     "value": sum(act(r, "omni_purchase") for r in daily)}],
        "action_values": [{"action_type": "omni_purchase",
                           "value": sum(actv(r, "omni_purchase") for r in daily)}],
    })
    story.append(Paragraph(f"1. Meta 週間サマリー（{period}）", STYLES["h2"]))
    story.append(table([
        ["消化金額", "表示回数", "クリック", "CTR", "CPC", "購入", "購入金額", "CPA", "ROAS"],
        [yen(total["spend"]), f"{total['imp']:,}", f"{total['clicks']:,}",
         f"{total['ctr']:.2f}%", yen(total["cpc"]), f"{total['pur']:.0f}",
         yen(total["rev"]), yen(total["cpa"]) if total["pur"] else "—",
         f"{total['roas']:.2f}" if total["spend"] else "—"],
    ], [23 * mm, 20 * mm, 17 * mm, 15 * mm, 17 * mm, 12 * mm, 22 * mm,
        22 * mm, 15 * mm], align_right_from=0))

    story.append(Paragraph("2. Meta キャンペーン別", STYLES["h2"]))
    rows = [["キャンペーン", "消化金額", "表示", "クリック", "CTR", "CPC", "購入", "購入金額", "ROAS"]]
    for r in sorted(camps, key=lambda r: -float(r.get("spend") or 0)):
        m = metrics(r)
        rows.append([Paragraph(r.get("campaign_name") or "-", STYLES["cell"]),
                     yen(m["spend"]), f"{m['imp']:,}", f"{m['clicks']:,}",
                     f"{m['ctr']:.2f}%", yen(m["cpc"]), f"{m['pur']:.0f}",
                     yen(m["rev"]) if m["rev"] else "—",
                     f"{m['roas']:.2f}" if m["rev"] else "—"])
    story.append(table(rows, [46 * mm, 18 * mm, 15 * mm, 14 * mm, 13 * mm,
                              15 * mm, 10 * mm, 19 * mm, 12 * mm]))

    story.append(Paragraph("3. Meta 広告別", STYLES["h2"]))
    rows = [["広告", "キャンペーン", "消化金額", "クリック", "CTR", "購入", "ROAS"]]
    for r in sorted(ads, key=lambda r: -float(r.get("spend") or 0)):
        m = metrics(r)
        rows.append([Paragraph(r.get("ad_name") or "-", STYLES["cell"]),
                     Paragraph(r.get("campaign_name") or "-", STYLES["cell"]),
                     yen(m["spend"]), f"{m['clicks']:,}", f"{m['ctr']:.2f}%",
                     f"{m['pur']:.0f}",
                     f"{m['roas']:.2f}" if m["rev"] else "—"])
    story.append(table(rows, [48 * mm, 44 * mm, 18 * mm, 14 * mm, 13 * mm,
                              10 * mm, 12 * mm]))

    story.append(Paragraph("4. Meta 日別推移", STYLES["h2"]))
    rows = [["日付", "消化金額", "表示", "クリック", "CTR", "CPC", "購入", "購入金額"]]
    for r in daily:
        m = metrics(r)
        rows.append([r["date_start"], yen(m["spend"]), f"{m['imp']:,}",
                     f"{m['clicks']:,}", f"{m['ctr']:.2f}%", yen(m["cpc"]),
                     f"{m['pur']:.0f}", yen(m["rev"]) if m["rev"] else "—"])
    story.append(table(rows, [24 * mm, 20 * mm, 17 * mm, 16 * mm, 14 * mm,
                              17 * mm, 12 * mm, 22 * mm]))
    return client


def google_sections(story):
    """Google成果とリンク確認。接続不可なら注記を返す。"""
    story.append(Paragraph("5. Google 広告成果", STYLES["h2"]))
    try:
        from ads_manager.google_ads_client import GoogleAdsClientWrapper
        client = GoogleAdsClientWrapper(load_google_config())
        rows_data = client.get_metrics(days=7)
    except Exception as e:
        story.append(Paragraph(
            "Google Ads API に接続できなかったため今週は掲載できません。"
            f"（{type(e).__name__}: 開発者トークン/認証情報を確認してください）",
            STYLES["body"]))
        return None
    # 表示もコストもないキャンペーン（削除済み等）は載せない
    rows_data = [r for r in rows_data if r["impressions"] or r["cost"]]
    if not rows_data:
        story.append(Paragraph("直近7日に配信のあったGoogleキャンペーンはありません。",
                               STYLES["body"]))
        return client
    rows = [["キャンペーン", "費用", "表示", "クリック", "CTR", "平均CPC", "CV"]]
    for r in sorted(rows_data, key=lambda r: -r["cost"]):
        rows.append([Paragraph(r["name"], STYLES["cell"]), yen(r["cost"]),
                     f"{r['impressions']:,}", f"{r['clicks']:,}",
                     f"{r['ctr']:.2f}%", yen(r["avg_cpc"]),
                     f"{r['conversions']:.0f}"])
    story.append(table(rows, [56 * mm, 18 * mm, 16 * mm, 15 * mm, 13 * mm,
                              17 * mm, 12 * mm]))
    return client


def link_check_sections(story, meta_client, google_client):
    story.append(Paragraph("6. リンク切れチェック", STYLES["h2"]))
    audit = meta_audit(meta_client, check_links=True)
    broken = [r for r in audit["問題のある広告"]
              if any("リンク切れ" in f or "リダイレクト" in f for f in r["flags"])]
    lines = [f"Meta: 配信中 {audit['summary']['調査対象']}本を検査 → "
             f"リンク切れ {len(broken)}件"]
    for r in broken:
        lines.append(f"　⚠ {r['campaign']} / {r['ad_name']}: "
                     + "; ".join(r["flags"]))

    if google_client is not None:
        try:
            from ads_manager.creatives import google_list_creatives
            g_all = google_list_creatives(google_client)
            g_ads = [a for a in g_all if a["serving"]]
            g_dormant = len(g_all) - len(g_ads)
            g_broken = []
            for a in g_ads:
                for url in a["final_urls"]:
                    res = check_url(url)
                    if res["status"] is not None and res["status"] >= 400:
                        g_broken.append(f"{a['campaign']} / {a['ad_id']}: "
                                        f"{url} ({res['status']})")
            lines.append(f"Google: 配信中の広告 {len(g_ads)}本を検査 → "
                         f"リンク切れ {len(g_broken)}件")
            lines += [f"　⚠ {b}" for b in g_broken]
            if g_dormant:
                lines.append(
                    f"（参考）停止中キャンペーン等に残る広告 {g_dormant}本は"
                    "検査対象外。過去のリンク切れ広告が多数含まれるため、"
                    "旧キャンペーンを再開する際は必ず事前にリンク確認を行うこと")
        except Exception as e:
            lines.append(f"Google: リンク確認を実行できませんでした ({type(e).__name__})")
    else:
        lines.append("Google: API接続不可のため未検査")
    story.append(Paragraph("<br/>".join(lines), STYLES["body"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out",
                        default=f"reports/広告週次レポート_{date.today()}.pdf")
    args = parser.parse_args()

    story = [
        Paragraph("広告 週次成果レポート（Meta + Google）", STYLES["title"]),
        Paragraph(f"作成日: {date.today()}　|　通貨: JPY　|　"
                  "購入・CVは各プラットフォーム計測に基づく概算", STYLES["sub"]),
        Spacer(1, 4 * mm),
    ]
    meta_client = meta_sections(story)
    google_client = google_sections(story)
    link_check_sections(story, meta_client, google_client)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(out), pagesize=A4,
                      topMargin=18 * mm, bottomMargin=18 * mm,
                      leftMargin=16 * mm, rightMargin=16 * mm,
                      title="広告 週次成果レポート").build(story)
    print(f"PDFを生成: {out}")


if __name__ == "__main__":
    main()

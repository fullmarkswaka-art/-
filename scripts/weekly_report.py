# -*- coding: utf-8 -*-
"""週次の広告成果レポート（Meta + Google）をPDF生成する。

使い方:
  python scripts/weekly_report.py [--out reports/週次レポート.pdf]

構成（両プラットフォーム対称）:
  各プラットフォームについて
    - 週間サマリー（今週 vs 前週の比較）
    - キャンペーン別成果（前週比付き）
    - 日別推移
  共通
    - リンク切れチェック（配信中の広告のみ）
  今週 = 昨日までの7日間、前週 = その前の7日間。
Google Ads API に接続できない場合はその旨を記載してMetaのみで生成する。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
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

SUMMARY_COLS = ["", "費用", "表示", "クリック", "CTR", "CPC",
                "CV", "CV金額", "CPA", "ROAS"]


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


def pct_change(cur, prev):
    if not prev:
        return "—" if not cur else "新規"
    return f"{(cur - prev) / prev * 100:+.0f}%"


def derived(m):
    """spend/imp/clicks/cv/rev から率系の指標を補完する。"""
    m["ctr"] = m["clicks"] / m["imp"] * 100 if m["imp"] else 0
    m["cpc"] = m["spend"] / m["clicks"] if m["clicks"] else 0
    m["cpa"] = m["spend"] / m["cv"] if m["cv"] else 0
    m["roas"] = m["rev"] / m["spend"] if m["spend"] else 0
    return m


def summary_rows(cur, prev):
    def fmt(m):
        return [yen(m["spend"]), f"{m['imp']:,}", f"{m['clicks']:,}",
                f"{m['ctr']:.2f}%", yen(m["cpc"]), f"{m['cv']:.0f}",
                yen(m["rev"]) if m["rev"] else "—",
                yen(m["cpa"]) if m["cv"] else "—",
                f"{m['roas']:.2f}" if m["rev"] else "—"]
    change = [pct_change(cur["spend"], prev["spend"]),
              pct_change(cur["imp"], prev["imp"]),
              pct_change(cur["clicks"], prev["clicks"]),
              f"{cur['ctr'] - prev['ctr']:+.2f}pt",
              pct_change(cur["cpc"], prev["cpc"]),
              pct_change(cur["cv"], prev["cv"]),
              pct_change(cur["rev"], prev["rev"]),
              pct_change(cur["cpa"], prev["cpa"]) if cur["cv"] and prev["cv"] else "—",
              (f"{cur['roas'] - prev['roas']:+.2f}"
               if cur["rev"] or prev["rev"] else "—")]
    return [SUMMARY_COLS, ["今週"] + fmt(cur), ["前週"] + fmt(prev),
            ["前週比"] + change]


SUMMARY_W = [12 * mm, 20 * mm, 18 * mm, 16 * mm, 14 * mm, 15 * mm,
             11 * mm, 20 * mm, 20 * mm, 13 * mm]
CAMP_W = [42 * mm, 24 * mm, 15 * mm, 14 * mm, 13 * mm, 10 * mm,
          18 * mm, 12 * mm, 14 * mm]


def campaign_table(cur_rows, prev_rows):
    """キャンペーン別テーブル。前週比（費用）付き。"""
    prev_by_id = {r["id"]: r for r in prev_rows}
    data = [["キャンペーン", "費用 (前週比)", "表示", "クリック", "CTR",
             "CV", "CV金額", "ROAS", "前週CV"]]
    for r in sorted(cur_rows, key=lambda r: -r["spend"]):
        p = prev_by_id.get(r["id"], {"spend": 0, "cv": 0})
        m = derived(dict(r))
        data.append([
            Paragraph(r["name"], STYLES["cell"]),
            f"{yen(m['spend'])} ({pct_change(m['spend'], p['spend'])})",
            f"{m['imp']:,}", f"{m['clicks']:,}", f"{m['ctr']:.2f}%",
            f"{m['cv']:.0f}", yen(m["rev"]) if m["rev"] else "—",
            f"{m['roas']:.2f}" if m["rev"] else "—",
            f"{p['cv']:.0f}"])
    # 今週配信なしでも前週動いていたキャンペーンは示す（停止の影響が見えるように）
    cur_ids = {r["id"] for r in cur_rows}
    for p in sorted(prev_rows, key=lambda r: -r["spend"]):
        if p["id"] not in cur_ids and p["spend"]:
            data.append([Paragraph(p["name"], STYLES["cell"]),
                         f"¥0 ({pct_change(0, p['spend'])})",
                         "0", "0", "—", "0", "—", "—", f"{p['cv']:.0f}"])
    return table(data, CAMP_W)


def daily_table(rows):
    data = [["日付", "費用", "表示", "クリック", "CTR", "CPC", "CV", "CV金額"]]
    for r in rows:
        m = derived(dict(r))
        data.append([r["date"], yen(m["spend"]), f"{m['imp']:,}",
                     f"{m['clicks']:,}", f"{m['ctr']:.2f}%", yen(m["cpc"]),
                     f"{m['cv']:.0f}", yen(m["rev"]) if m["rev"] else "—"])
    return table(data, [24 * mm, 20 * mm, 17 * mm, 16 * mm, 14 * mm,
                        17 * mm, 12 * mm, 22 * mm])


# ---------------- Meta ----------------

def _meta_actions(row, key, values=False):
    src = row.get("action_values" if values else "actions") or []
    for a in src:
        if a["action_type"] == key:
            return float(a["value"])
    return 0.0


def _meta_metrics(row):
    return {"spend": float(row.get("spend") or 0),
            "imp": int(row.get("impressions") or 0),
            "clicks": int(row.get("clicks") or 0),
            "cv": _meta_actions(row, "omni_purchase"),
            "rev": _meta_actions(row, "omni_purchase", values=True)}


def meta_week(client, since, until):
    acct = client.config.ad_account_id
    tr = json.dumps({"since": str(since), "until": str(until)})
    fields = "campaign_id,campaign_name,impressions,clicks,spend,actions,action_values"
    total_rows = client.get(f"{acct}/insights", level="account",
                            time_range=tr, fields=fields).get("data", [])
    total = derived(_meta_metrics(total_rows[0] if total_rows else {}))
    camps = []
    for r in client.get(f"{acct}/insights", level="campaign",
                        time_range=tr, fields=fields).get("data", []):
        camps.append({"id": r.get("campaign_id"),
                      "name": r.get("campaign_name") or "-",
                      **_meta_metrics(r)})
    daily = []
    for r in client.get(f"{acct}/insights", level="account", time_range=tr,
                        time_increment=1, fields=fields).get("data", []):
        daily.append({"date": r["date_start"], **_meta_metrics(r)})
    return total, camps, sorted(daily, key=lambda r: r["date"])


# ---------------- Google ----------------

def _g_metrics(m):
    return {"spend": m.cost_micros / 1_000_000,
            "imp": m.impressions, "clicks": m.clicks,
            "cv": m.conversions, "rev": m.conversions_value}


def google_week(client, since, until):
    where = f"segments.date BETWEEN '{since}' AND '{until}'"
    fields = ("metrics.impressions, metrics.clicks, metrics.cost_micros, "
              "metrics.conversions, metrics.conversions_value")
    total = {"spend": 0, "imp": 0, "clicks": 0, "cv": 0, "rev": 0}
    camps = []
    for r in client.search(f"SELECT campaign.id, campaign.name, {fields} "
                           f"FROM campaign WHERE {where}"):
        m = _g_metrics(r.metrics)
        if not m["imp"] and not m["spend"]:
            continue
        camps.append({"id": r.campaign.id, "name": r.campaign.name, **m})
        for k in total:
            total[k] += m[k]
    daily = []
    for r in client.search(f"SELECT segments.date, {fields} "
                           f"FROM customer WHERE {where} "
                           "ORDER BY segments.date"):
        daily.append({"date": r.segments.date, **_g_metrics(r.metrics)})
    return derived(total), camps, daily


# ---------------- リンク切れ ----------------

def pacing_section(story, meta_client, google_client, today):
    """月初来の消化ペースと全体ROASを targets.json の目標と比較する。"""
    targets_path = Path(__file__).resolve().parent.parent / "targets.json"
    if not targets_path.exists():
        return
    targets = json.loads(targets_path.read_text())
    month_start = today.replace(day=1)
    until = today - timedelta(days=1)
    if until < month_start:  # 月初1日は前月分を対象にしない
        return
    m_total, _, _ = meta_week(meta_client, month_start, until)
    spend, rev = m_total["spend"], m_total["rev"]
    if google_client is not None:
        g_total, _, _ = google_week(google_client, month_start, until)
        spend += g_total["spend"]
        rev += g_total["rev"]
    budget = targets["monthly_budget_ex_tax"] - targets.get("event_reserve", 0)
    days_in_month = (month_start.replace(month=month_start.month % 12 + 1,
                                         day=1) - timedelta(days=1)).day
    elapsed = (until - month_start).days + 1
    pace_target = budget * elapsed / days_in_month
    roas = rev / spend if spend else 0
    min_roas = targets.get("min_roas", 0)
    story.append(Paragraph("月間ペース（通常運用予算に対する進捗）", STYLES["h2"]))
    story.append(table([
        ["項目", "実績", "目標", "評価"],
        [f"消化額 ({month_start}〜{until})", yen(spend),
         f"{yen(pace_target)}（{elapsed}/{days_in_month}日経過時点）",
         "順調" if spend >= pace_target * 0.9 else "⚠ 未消化ペース"],
        ["全体ROAS", f"{roas:.1f}", f"{min_roas:.0f} 以上",
         "達成" if roas >= min_roas else "⚠ 目標未達"],
        ["月間予算（税抜）", "", f"{yen(targets['monthly_budget_ex_tax'])}"
         f"（うち企画予備 {yen(targets.get('event_reserve', 0))}）", ""],
    ], [52 * mm, 32 * mm, 55 * mm, 22 * mm]))


def link_check_section(story, meta_client, google_client):
    story.append(Paragraph("リンク切れチェック", STYLES["h2"]))
    audit = meta_audit(meta_client, check_links=True)
    broken = [r for r in audit["問題のある広告"]
              if any("リンク切れ" in f or "リダイレクト" in f for f in r["flags"])]
    lines = [f"Meta: 配信中 {audit['summary']['調査対象']}本を検査 → "
             f"リンク切れ {len(broken)}件"]
    lines += [f"　⚠ {r['campaign']} / {r['ad_name']}: " + "; ".join(r["flags"])
              for r in broken]
    if google_client is not None:
        try:
            from ads_manager.creatives import google_list_creatives
            g_all = google_list_creatives(google_client)
            g_ads = [a for a in g_all if a["serving"]]
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
            dormant = len(g_all) - len(g_ads)
            if dormant:
                lines.append(
                    f"（参考）停止中キャンペーン等に残る広告 {dormant}本は"
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

    today = date.today()
    cur_since, cur_until = today - timedelta(days=7), today - timedelta(days=1)
    prev_since, prev_until = today - timedelta(days=14), today - timedelta(days=8)

    story = [
        Paragraph("広告 週次成果レポート（Meta + Google）", STYLES["title"]),
        Paragraph(f"今週: {cur_since} 〜 {cur_until}　|　前週: {prev_since} 〜 {prev_until}　|　"
                  "通貨: JPY　|　CV・CV金額は各プラットフォーム計測の概算", STYLES["sub"]),
        Spacer(1, 4 * mm),
    ]

    # ---- Meta ----
    meta_client = MetaAdsClient(load_meta_config())
    m_cur, m_camps, m_daily = meta_week(meta_client, cur_since, cur_until)
    m_prev, m_camps_prev, _ = meta_week(meta_client, prev_since, prev_until)
    story.append(Paragraph("1. Meta 週間サマリー（前週比較）", STYLES["h2"]))
    story.append(table(summary_rows(m_cur, m_prev), SUMMARY_W))
    story.append(Paragraph("2. Meta キャンペーン別", STYLES["h2"]))
    story.append(campaign_table(m_camps, m_camps_prev))
    story.append(Paragraph("3. Meta 日別推移（今週）", STYLES["h2"]))
    story.append(daily_table(m_daily))

    # ---- Google ----
    google_client = None
    try:
        from ads_manager.google_ads_client import GoogleAdsClientWrapper
        google_client = GoogleAdsClientWrapper(load_google_config())
        g_cur, g_camps, g_daily = google_week(google_client, cur_since, cur_until)
        g_prev, g_camps_prev, _ = google_week(google_client, prev_since, prev_until)
        story.append(Paragraph("4. Google 週間サマリー（前週比較）", STYLES["h2"]))
        story.append(table(summary_rows(g_cur, g_prev), SUMMARY_W))
        story.append(Paragraph("5. Google キャンペーン別", STYLES["h2"]))
        story.append(campaign_table(g_camps, g_camps_prev))
        story.append(Paragraph("6. Google 日別推移（今週）", STYLES["h2"]))
        story.append(daily_table(g_daily))
    except Exception as e:
        story.append(Paragraph("4. Google 広告成果", STYLES["h2"]))
        story.append(Paragraph(
            "Google Ads API に接続できなかったため今週は掲載できません。"
            f"（{type(e).__name__}: 認証情報を確認してください）", STYLES["body"]))
        google_client = None

    pacing_section(story, meta_client, google_client, today)
    link_check_section(story, meta_client, google_client)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(out), pagesize=A4,
                      topMargin=18 * mm, bottomMargin=18 * mm,
                      leftMargin=16 * mm, rightMargin=16 * mm,
                      title="広告 週次成果レポート").build(story)
    print(f"PDFを生成: {out}")


if __name__ == "__main__":
    main()

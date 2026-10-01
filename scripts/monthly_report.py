# -*- coding: utf-8 -*-
"""月次の広告成果レポート（Meta + Google、FULLMARKS STORE）をPDF生成する。

使い方:
  python scripts/monthly_report.py --month 2026-09 [--until 2026-09-27] [--out reports/...pdf]

--until を省略すると「昨日まで」（月が終わっていれば月末まで）。前月の同じ日数と比べる。
数値の表は API から作り、文章（今月のポイント・施策・来月に向けて）は copy/monthly/<月>.json から読む。
イベント枠（targets.json の events[]）は通常運用と分けて計上する。

構成:
  1. サマリー … 通常運用の費用/売上/ROAS/購入（前月同期比）、今月のポイント、予算の消化
  2. 媒体別・週別 … Google / Meta、週ごとの推移
  3. 何が売れたか … ブランド別・枠別・ショッピングで売れた商品
  4. キャンペーン別
  5. 今月の施策と結果
  6. イベント枠
  7. 来月に向けて
  8. 監査
"""
from __future__ import annotations

import argparse
import calendar
import importlib.util
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("weekly_report", ROOT / "scripts" / "weekly_report.py")
wr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wr)

from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer  # noqa: E402

from ads_manager.config import load_google_config, load_meta_config  # noqa: E402
from ads_manager.google_ads_client import GoogleAdsClientWrapper  # noqa: E402
from ads_manager.meta_ads import MetaAdsClient  # noqa: E402

S, yen, roas, pct, table, disp = wr.S, wr.yen, wr.roas, wr.pct, wr.table, wr.disp


def _targets() -> dict:
    p = ROOT / "targets.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _event_ids(t: dict) -> set[str]:
    ids = set(t.get("event_campaign_ids", []))
    for e in t.get("events", []):
        ids |= set(e.get("meta_campaign_ids", []))
    return ids


def fetch(meta, google, since: date, until: date) -> dict:
    m_camps, m_ads, _ = wr.meta_data(meta, since, until)
    g_camps, g_daily, g_shop, g_products, g_labels = wr.google_data(google, since, until)
    acct = meta.config.ad_account_id
    m_daily = [{"date": r["date_start"], "id": r["campaign_id"], **wr._mm(r)} for r in meta.get_all(
        f"{acct}/insights", level="campaign", time_increment=1,
        time_range=json.dumps({"since": str(since), "until": str(until)}),
        fields="campaign_id,impressions,clicks,spend,actions,action_values", limit=500)]
    return {"m_camps": m_camps, "m_ads": m_ads, "m_daily": m_daily, "g_camps": g_camps, "g_daily": g_daily,
            "g_shop": g_shop, "g_products": g_products, "g_labels": g_labels}


def split(d: dict, ev_ids: set[str]) -> tuple[list, list, list]:
    """(Meta 通常キャンペーン, Meta イベントキャンペーン, Meta 通常の広告)"""
    normal = [c for c in d["m_camps"] if c["id"] not in ev_ids]
    event = [c for c in d["m_camps"] if c["id"] in ev_ids]
    ev_names = {c["name"] for c in event}
    ads = [a for a in d["m_ads"] if a["campaign"] not in ev_names]
    return normal, event, ads


def weeks(since: date, until: date) -> list[tuple[date, date]]:
    out, s = [], since
    while s <= until:
        e = min(s + timedelta(days=6 - s.weekday()), until)  # 日曜まで
        out.append((s, e)); s = e + timedelta(days=1)
    return out


def sec_media(cur_m, cur_g, prev_m, prev_g, label):
    data = [["媒体", "広告費", "購入", "売上", "ROAS", f"{label} 売上", f"{label} ROAS", "売上の増減"]]
    for name, c, p in (("Google", cur_g, prev_g), ("Meta", cur_m, prev_m)):
        data.append([name, yen(c["spend"]), f"{c['cv']:.0f}", yen(c["rev"]), f"{roas(c):.1f}",
                     yen(p["rev"]), f"{roas(p):.1f}", pct(c["rev"], p["rev"])])
    t = wr.total_of([cur_g, cur_m]); tp = wr.total_of([prev_g, prev_m])
    data.append(["合計", yen(t["spend"]), f"{t['cv']:.0f}", yen(t["rev"]), f"{roas(t):.1f}",
                 yen(tp["rev"]), f"{roas(tp):.1f}", pct(t["rev"], tp["rev"])])
    return table(data, [18 * mm, 24 * mm, 13 * mm, 26 * mm, 13 * mm, 27 * mm, 22 * mm, 20 * mm])


def sec_weeks(d, ev_ids, since, until):
    data = [["週", "日数", "Google 費用", "Google ROAS", "Meta 費用", "Meta ROAS", "合計費用", "合計売上", "ROAS", "購入"]]
    for s, e in weeks(since, until):
        ks, ke = str(s), str(e)
        g = wr.total_of([v for k, v in d["g_daily"].items() if ks <= k <= ke])
        m = wr.total_of([r for r in d["m_daily"] if ks <= r["date"] <= ke and r["id"] not in ev_ids])
        t = wr.total_of([g, m])
        data.append([f"{s.month}/{s.day}〜{e.month}/{e.day}", f"{(e - s).days + 1}", yen(g["spend"]), f"{roas(g):.1f}",
                     yen(m["spend"]), f"{roas(m):.1f}", yen(t["spend"]), yen(t["rev"]), f"{roas(t):.1f}", f"{t['cv']:.0f}"])
    return table(data, [21 * mm, 9 * mm, 21 * mm, 19 * mm, 21 * mm, 17 * mm, 21 * mm, 23 * mm, 12 * mm, 12 * mm])


def sec_brand(cur, prev, label):
    data = [["ブランド", "広告費", "購入", "売上", "ROAS", f"{label} 売上", f"{label} ROAS"]]
    for b, m in sorted(cur.items(), key=lambda kv: -kv[1]["rev"]):
        if not (m["spend"] or m["rev"]):
            continue
        p = prev.get(b, {"spend": 0, "cv": 0, "rev": 0})
        data.append([b, yen(m["spend"]), f"{m['cv']:.0f}", yen(m["rev"]) if m["rev"] else "—",
                     f"{roas(m):.1f}" if m["rev"] else "—", yen(p["rev"]) if p["rev"] else "—",
                     f"{roas(p):.1f}" if p["rev"] else "—"])
    return table(data, [50 * mm, 22 * mm, 13 * mm, 26 * mm, 13 * mm, 26 * mm, 20 * mm])


def sec_frame(cur, prev, label):
    data = [["枠", "広告費", "購入", "売上", "ROAS", f"{label} ROAS"]]
    for f, m in sorted(cur.items(), key=lambda kv: -kv[1]["rev"]):
        p = prev.get(f, {"spend": 0, "rev": 0})
        data.append([f, yen(m["spend"]), f"{m['cv']:.0f}", yen(m["rev"]), f"{roas(m):.1f}",
                     f"{roas(p):.1f}" if p["spend"] else "—"])
    return table(data, [50 * mm, 26 * mm, 16 * mm, 30 * mm, 18 * mm, 26 * mm])


def sec_campaigns(cur, prev):
    prev_by = {c["id"]: c for c in prev}
    data = [["キャンペーン", "媒体", "広告費", "購入", "売上", "ROAS", "前月同期 ROAS"]]
    for media, c in sorted(cur, key=lambda x: -x[1]["spend"]):
        if c["spend"] < 100:
            continue
        p = prev_by.get(c["id"])
        data.append([disp(c["name"]), media, yen(c["spend"]), f"{c['cv']:.0f}",
                     yen(c["rev"]) if c["rev"] else "—", f"{roas(c):.1f}",
                     f"{roas(p):.1f}" if p and p["spend"] else "—"])
    return table(data, [58 * mm, 14 * mm, 22 * mm, 12 * mm, 24 * mm, 14 * mm, 24 * mm], align_right_from=2)


def sec_products(products, n=10):
    data = [["商品", "ブランド", "クリック", "広告費", "購入", "売上"]]
    for _, p in sorted(products.items(), key=lambda kv: -kv[1]["rev"])[:n]:
        if not p["rev"]:
            break
        data.append([Paragraph(p["title"], S["cell"]), p["brand"], f"{p['clicks']:,}", yen(p["spend"]),
                     f"{p['cv']:.1f}", yen(p["rev"])])
    return table(data, [70 * mm, 30 * mm, 16 * mm, 20 * mm, 14 * mm, 24 * mm], align_right_from=2)


def sec_budget(t: dict, normal: dict, event: dict, since: date, until: date, budget: float | None = None):
    dim = calendar.monthrange(since.year, since.month)[1]
    el = (until - since).days + 1
    if budget is None:  # 過去の月は copy/monthly/<月>.json の normal_budget_ex_tax を使う
        budget = t.get("normal_budget_ex_tax", t.get("monthly_budget_ex_tax", 0) - t.get("event_reserve", 0))
    proj = normal["spend"] / el * dim if el else 0
    data = [["項目", "金額（税抜）", "メモ"],
            [f"通常運用の予算（{since.month}月）", yen(budget), "FULLMARKS STORE の Google + Meta"],
            [f"通常運用の実績（{since.month}/1〜{until.month}/{until.day}）", yen(normal["spend"]),
             f"予算の {normal['spend'] / budget:.0%}（{el}/{dim}日経過）" if budget else ""],
            ["通常運用の月末見込み（日割り）" if el < dim else "通常運用の月の合計", yen(proj), f"予算比 {proj / budget:.0%}" if budget else ""],
            ["イベント枠の実績（別計上・使った分だけ）", yen(event["spend"]),
             f"購入 {event['cv']:.0f}件・売上 {yen(event['rev'])}（ROAS {roas(event):.1f}）" if event["spend"] else "—"]]
    return table(data, [70 * mm, 30 * mm, 80 * mm])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default=date.today().strftime("%Y-%m"))
    ap.add_argument("--until", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    y, m = map(int, args.month.split("-"))
    since = date(y, m, 1)
    month_end = date(y, m, calendar.monthrange(y, m)[1])
    until = date.fromisoformat(args.until) if args.until else min(month_end, date.today() - timedelta(days=1))
    n_days = (until - since).days + 1
    p_since = (since - timedelta(days=1)).replace(day=1)
    p_end = date(p_since.year, p_since.month, calendar.monthrange(p_since.year, p_since.month)[1])
    # 月が終わっていれば前月の全期間と比べる。途中なら前月の同じ日数と比べる
    p_until = p_end if until == month_end else min(p_since + timedelta(days=n_days - 1), p_end)
    t = _targets(); ev_ids = _event_ids(t)
    narr_p = ROOT / "copy" / "monthly" / f"{args.month}.json"
    narr = json.loads(narr_p.read_text(encoding="utf-8")) if narr_p.exists() else {}
    label = narr.get("compare_label", "前月同期")

    meta = MetaAdsClient(load_meta_config()); google = GoogleAdsClientWrapper(load_google_config())
    cur = fetch(meta, google, since, until); prev = fetch(meta, google, p_since, p_until)
    cm, ce, cads = split(cur, ev_ids); pm, _, pads = split(prev, ev_ids)
    cur_m, cur_g = wr.total_of(cm), wr.total_of(cur["g_camps"])
    prev_m, prev_g = wr.total_of(pm), wr.total_of(prev["g_camps"])
    normal, normal_p = wr.total_of([cur_m, cur_g]), wr.total_of([prev_m, prev_g])
    event = wr.total_of(ce)

    partial = until < month_end
    story = [Paragraph(f"広告 月次レポート　{y}年{m}月", S["title"]),
             Paragraph(f"対象: {since} 〜 {until}（{n_days}日間{'・月の途中' if partial else ''}）　"
                       f"比較: {p_since} 〜 {p_until}（{label}）　FULLMARKS STORE / Google広告 + Meta広告　"
                       "売上は各媒体計測のCV金額（税込）。広告費は税抜。", S["sub"]), Spacer(1, 4 * mm)]
    if partial:
        story.append(Paragraph(f"※ {until.month}/{until.day + 1}〜{month_end.month}/{month_end.day} の"
                               f"{(month_end - until).days}日分は含まれていません（月末見込みは日割りで算出）。", S["note"]))

    story.append(Paragraph("1. サマリー（通常運用。イベント枠は別計上）", S["h1"]))
    story.append(wr.kpi_tiles(normal, normal_p, vs=label))
    story.append(Paragraph("今月のポイント", S["h2"]))
    for line in narr.get("points", []) or ["（copy/monthly に文章がありません）"]:
        story.append(Paragraph(line, S["bullet"], bulletText="■"))
    story.append(KeepTogether([Paragraph("予算の消化", S["h2"]), sec_budget(t, normal, event, since, until, narr.get("normal_budget_ex_tax"))]))

    story.append(Paragraph("2. 媒体別・週別", S["h1"]))
    story.append(KeepTogether([Paragraph(f"媒体別（{label}との比較）", S["h2"]),
                               sec_media(cur_m, cur_g, prev_m, prev_g, label)]))
    story.append(KeepTogether([Paragraph("週別推移（通常運用）", S["h2"]), sec_weeks(cur, ev_ids, since, until)]))

    story.append(Paragraph("3. 何が売れたか", S["h1"]))
    story.append(KeepTogether([Paragraph("ブランド別（広告経由の売上順）", S["h2"]),
                               sec_brand(wr.by_brand(cur["g_camps"], cur["g_shop"], cads),
                                         wr.by_brand(prev["g_camps"], prev["g_shop"], pads), label)]))
    story.append(Paragraph("ブランドの判定: 指名検索と静止画はキャンペーン名、ショッピングは商品のブランド属性、"
                           "Metaカタログは広告（ブランド／シリーズ別）から。店舗指名はブランド横断のため別建て。", S["note"]))
    story.append(KeepTogether([Paragraph("枠別", S["h2"]),
                               sec_frame(wr.by_frame(cur["g_camps"], cm), wr.by_frame(prev["g_camps"], pm), label)]))
    story.append(KeepTogether([Paragraph("Googleショッピングで売れた商品", S["h2"]), sec_products(cur["g_products"])]))

    story.append(Paragraph("4. キャンペーン別（通常運用）", S["h1"]))
    story.append(sec_campaigns([("Google", c) for c in cur["g_camps"]] + [("Meta", c) for c in cm],
                               prev["g_camps"] + pm))

    if narr.get("actions"):
        story.append(Paragraph("5. 今月の施策と結果", S["h1"]))
        data = [["日付", "やったこと", "結果"]] + [
            [a[0], Paragraph(a[1], S["cell"]), Paragraph(a[2], S["cell"])] for a in narr["actions"]]
        story.append(table(data, [18 * mm, 92 * mm, 70 * mm], align_right_from=9))

    story.append(Paragraph("6. イベント枠（通常運用と別予算・別計上）", S["h1"]))
    if ce:
        data = [["キャンペーン", "広告費", "購入", "売上", "ROAS"]] + [
            [disp(c["name"]), yen(c["spend"]), f"{c['cv']:.0f}", yen(c["rev"]), f"{roas(c):.1f}"] for c in ce]
        story.append(table(data, [80 * mm, 26 * mm, 16 * mm, 30 * mm, 18 * mm]))
        story.append(Paragraph("イベント枠は使った分だけを計上し、通常運用の予算とは分けて管理する。", S["note"]))
    else:
        story.append(Paragraph("今月のイベント広告はありません。", S["body"]))

    if narr.get("next"):
        story.append(Paragraph("7. 来月に向けて", S["h1"]))
        for line in narr["next"]:
            story.append(Paragraph(line, S["bullet"], bulletText="■"))

    story.append(Paragraph("8. 監査", S["h1"]))
    story.extend(wr.sec_audit(meta, google, cur["g_labels"]))

    out = Path(args.out or ROOT / "reports" / f"広告月次レポート_{args.month}.pdf")
    out.parent.mkdir(parents=True, exist_ok=True)

    def _footer(canvas, doc):
        canvas.saveState(); canvas.setFont(wr.FONT, 7.5); canvas.setFillColor(wr.GREY)
        canvas.drawString(15 * mm, 9 * mm, f"FULLMARKS 広告月次レポート  {since} 〜 {until}")
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"{doc.page}")
        canvas.restoreState()

    SimpleDocTemplate(str(out), pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm,
                      leftMargin=15 * mm, rightMargin=15 * mm, title=f"広告 月次レポート {args.month}"
                      ).build(story, onFirstPage=_footer, onLaterPages=_footer)
    print(f"PDFを生成: {out}")


if __name__ == "__main__":
    main()

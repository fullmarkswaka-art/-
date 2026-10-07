# -*- coding: utf-8 -*-
"""月次の広告成果レポート（Meta + Google、FULLMARKS STORE）をPDF生成する。

使い方:
  python scripts/monthly_report.py --month 2026-09 [--until 2026-09-27] [--out reports/...pdf]

--until を省略すると「昨日まで」（月が終わっていれば月末まで）。前月の同じ日数と比べる。
数値の表は API から作り、文章（今月のポイント・施策・来月に向けて）は copy/monthly/<月>.json から読む。
イベント枠（targets.json の events[]）は通常運用と分けて計上する。

お店全体（EC）の売上は API で取れないため、copy/ec/<月>.json（scripts/ec_import.py でユーザー提供の
予実資料から作る）があれば読み込んで、広告の数字と並べる。

広告に詳しくない人が読んでも分かるように書く（ROAS は「広告1円あたりの売上」、判定は ◎○△×）。
構成:
  1. 今月のまとめ … ひとことで言うと、お店全体と広告の数字、信号、ポイント、承認のお願い
  2. お店全体の売上と広告 … 予算・前年・新作目標の進み具合、新作／旧品、ブランド別
  3. 広告の成績 … Google と Instagram・Facebook の比較、週ごとの推移、ブランド別
  4. 広告ごとの成績表（判定つき）
  5. 今月やったことと結果 / 来月に向けて
  参考資料 … 媒体別・週別・ブランド別・種類別の表、売れた商品、予算の消化、イベント、点検、言葉の説明
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
from reportlab.lib import colors  # noqa: E402
from reportlab.platypus import (CondPageBreak, KeepTogether, PageBreak, Paragraph,  # noqa: E402
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from ads_manager.config import load_google_config, load_meta_config  # noqa: E402
from ads_manager.google_ads_client import GoogleAdsClientWrapper  # noqa: E402
from ads_manager.meta_ads import MetaAdsClient  # noqa: E402

S, yen, roas, pct, table, disp, man = wr.S, wr.yen, wr.roas, wr.pct, wr.table, wr.disp, wr.man
TAX = 1.1  # 媒体の売上（税込）をお店の売上（税抜）と比べるときに割る


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
             f"購入 {event['cv']:.0f}件・売上 {yen(event['rev'])}（1円あたり {roas(event):.1f}円）" if event["spend"] else "—"]]
    return table(data, [70 * mm, 30 * mm, 80 * mm])


def ec_tiles(ec, ad_spend, ad_rev):
    """お店全体（EC、税抜）の4タイル。"""
    items = [("お店全体の売上（税抜）", man(ec["sales"]),
              f"予算比 {ec['sales'] / ec['budget']:.0%}・前年比 {ec['sales'] / ec['last_year']:.0%}", ec["sales"] >= ec["budget"]),
             (f"うち新作（{ec['new_season']['label']}）", man(ec["new_season"]["sales"]),
              f"新作目標 {man(ec['new_season']['target'])} の {ec['new_season']['sales'] / ec['new_season']['target']:.0%}",
              ec["new_season"]["sales"] >= ec["new_season"]["target"]),
             ("広告費（イベント込み・税抜）", man(ad_spend), f"お店の売上の {ad_spend / ec['sales']:.1%}", None),
             ("広告がきっかけの売上（税抜換算）", man(ad_rev / TAX), f"お店の売上の {ad_rev / TAX / ec['sales']:.0%}", None)]
    rows = [[Paragraph(a, S["tile_label"]) for a, _, _, _ in items],
            [Paragraph(b, S["tile_value"]) for _, b, _, _ in items],
            [Paragraph(f'<font color="{(wr.GREY if ok is None else (wr.GOOD if ok else wr.BAD)).hexval()}">{c}</font>',
                       S["tile_delta"]) for _, _, c, ok in items]]
    t = Table(rows, colWidths=[45 * mm] * 4)
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, wr.LINE), ("INNERGRID", (0, 0), (-1, -1), 0.6, wr.LINE),
                           ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f7f0")),
                           ("LINEBELOW", (0, 0), (-1, 0), 0, colors.HexColor("#f3f7f0")),
                           ("LINEBELOW", (0, 1), (-1, 1), 0, colors.HexColor("#f3f7f0")),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return t


def ec_signals(ec):
    r = ec["sales"] / ec["budget"]; rn = ec["new_season"]["sales"] / ec["new_season"]["target"]
    out = [("◎" if r >= 1 else ("△" if r >= 0.9 else "×"), "お店全体の売上",
            f"{man(ec['sales'])}（会社予算 {man(ec['budget'])} の {r:.0%}）",
            f"前年（{man(ec['last_year'])}）の {ec['sales'] / ec['last_year']:.1f}倍。"
            f"年度累計も予算の {ec['ytd']['sales'] / ec['ytd']['budget']:.0%}。"),
           ("◎" if rn >= 1 else ("△" if rn >= 0.5 else "×"), f"新作（{ec['new_season']['label']}）の売上",
            f"{man(ec['new_season']['sales'])}（目標 {man(ec['new_season']['target'])} の {rn:.0%}）",
            "売上の多くは旧品（セール品中心）。新作の立ち上がりはこれから。" if rn < 1 else "新作も目標を達成。")]
    return out


def sec_ec(ec, brand_ads):
    """お店全体の売上の進み具合と、ブランド別（お店の売上・新作・広告）。"""
    nx = ec.get("next_month", {})
    prog = wr.chart_progress([
        ("今月の売上 vs 会社予算", ec["sales"], ec["budget"], None,
         f"{man(ec['sales'])}／{man(ec['budget'])}（{ec['sales'] / ec['budget']:.0%}）"),
        ("今月の売上 vs 前年", ec["sales"], ec["last_year"], None,
         f"{man(ec['sales'])}／前年 {man(ec['last_year'])}（{ec['sales'] / ec['last_year']:.0%}）"),
        ("年度累計 vs 会社予算", ec["ytd"]["sales"], ec["ytd"]["budget"], None,
         f"{man(ec['ytd']['sales'])}／{man(ec['ytd']['budget'])}（{ec['ytd']['sales'] / ec['ytd']['budget']:.0%}）"),
        (f"新作（{ec['new_season']['label']}）vs 新作目標", ec["new_season"]["sales"], ec["new_season"]["target"], None,
         f"{man(ec['new_season']['sales'])}／{man(ec['new_season']['target'])}"
         f"（{ec['new_season']['sales'] / ec['new_season']['target']:.0%}）")])
    mix = wr.chart_hbars([
        (f"新作（{ec['new_season']['label']}）", ec["new_season"]["sales"],
         f"{man(ec['new_season']['sales'])}（{ec['new_season']['sales'] / ec['sales']:.0%}）", wr.GOOD),
        ("旧品（前シーズン以前）", ec["old_items"], f"{man(ec['old_items'])}（{ec['old_items'] / ec['sales']:.0%}）", wr.SPEND_C)])
    data = [["ブランド", "お店の売上", "前月比", "新作の売上", "新作目標\nの達成", "広告がきっかけ\n（税抜換算）",
             "広告費", "来月の\n新作目標"]]
    for b in ec["brands"]:
        ad = brand_ads.get(b["brand"], {"spend": 0, "rev": 0})
        rn = b["new"] / b["new_target"] if b["new_target"] else None
        mk = "—" if rn is None else ("◎" if rn >= 1 else ("△" if rn >= 0.5 else "×"))
        color = {"◎": wr.GOOD, "△": wr.WARN, "×": wr.BAD}.get(mk, wr.GREY)
        data.append([b["brand"], man(b["sales"]), pct(b["sales"], b["prev_month"]), man(b["new"]),
                     Paragraph(f'<font color="{color.hexval()}">{mk} {rn:.0%}</font>' if rn is not None else "—", S["cell_r"]),
                     man(ad["rev"] / TAX) if ad["rev"] else "—", man(ad["spend"]) if ad["spend"] else "—",
                     man(b["next_new_target"]) if b["next_new_target"] else "—"])
    tb = table(data, [32 * mm, 22 * mm, 16 * mm, 21 * mm, 20 * mm, 24 * mm, 20 * mm, 25 * mm])
    out = [Paragraph("今月の売上の進み具合", S["h2"]), prog,
           Paragraph("棒の長さは目標（予算）を100%とした割合。緑は目標達成。", S["note"]),
           KeepTogether([Paragraph("売上の中身：新作と旧品", S["h2"]), mix,
                         Paragraph("新作＝今シーズンの商品（会社の消化率の対象）。旧品＝前シーズン以前の商品で、セール品が中心。"
                                   "広告は新作・通常品だけに出している（アウトレット品は広告しない方針）。", S["note"])]),
           KeepTogether([Paragraph("ブランド別：お店の売上・新作・広告", S["h2"]), tb,
                         Paragraph("お店の売上は受注データ（税抜）。広告がきっかけの売上は媒体の計測（税込）を1.1で割って税抜に"
                                   "そろえた参考値で、広告を見ずに買った人もお店の売上には含まれる。新作目標の達成: ◎100%以上 "
                                   "△50%以上 ×50%未満。", S["note"])])]
    if nx:
        out.append(Paragraph(f"来月の会社予算は {man(nx.get('budget', 0))}（前年 {man(nx.get('last_year', 0))}）、"
                             f"新作目標は {man(nx.get('new_target', 0))}（今月の新作実績の "
                             f"{nx.get('new_target', 0) / ec['new_season']['sales']:.1f}倍）。", S["body"]))
    return out


def week_chart(d, ev_ids, since, until):
    labels, sp, rv = [], [], []
    for s, e in weeks(since, until):
        ks, ke = str(s), str(e)
        g = wr.total_of([v for k, v in d["g_daily"].items() if ks <= k <= ke])
        m = wr.total_of([r for r in d["m_daily"] if ks <= r["date"] <= ke and r["id"] not in ev_ids])
        t = wr.total_of([g, m])
        labels.append(f"{s.month}/{s.day}〜{e.month}/{e.day}\n1円あたり {roas(t):.1f}円")
        sp.append(t["spend"]); rv.append(t["rev"])
    return wr.chart_columns(labels, [sp, rv], ["広告費", "広告がきっかけの売上"], [wr.SPEND_C, wr.NAVY],
                            value_series=(0, 1), footnote="単位: 万円（イベント広告を除く）")


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
    ec_p = ROOT / "copy" / "ec" / f"{args.month}.json"
    ec = json.loads(ec_p.read_text(encoding="utf-8")) if ec_p.exists() and until == month_end else None
    label = narr.get("compare_label", "前月同期")

    meta = MetaAdsClient(load_meta_config()); google = GoogleAdsClientWrapper(load_google_config())
    cur = fetch(meta, google, since, until); prev = fetch(meta, google, p_since, p_until)
    cm, ce, cads = split(cur, ev_ids); pm, _, pads = split(prev, ev_ids)
    cur_m, cur_g = wr.total_of(cm), wr.total_of(cur["g_camps"])
    prev_m, prev_g = wr.total_of(pm), wr.total_of(prev["g_camps"])
    normal, normal_p = wr.total_of([cur_m, cur_g]), wr.total_of([prev_m, prev_g])
    event = wr.total_of(ce)
    brand_cur = wr.by_brand(cur["g_camps"], cur["g_shop"], cads)
    brand_prev = wr.by_brand(prev["g_camps"], prev["g_shop"], pads)
    budget = narr.get("normal_budget_ex_tax") or t.get("normal_budget_ex_tax", 0)
    dim = calendar.monthrange(y, m)[1]

    partial = until < month_end
    story = [Paragraph(f"広告 月次レポート　{y}年{m}月", S["title"]),
             Paragraph(f"対象: {since.month}/{since.day}〜{until.month}/{until.day}（{n_days}日間{'・月の途中' if partial else ''}）　"
                       f"比較: {p_since.month}/{p_since.day}〜{p_until.month}/{p_until.day}（{label}）　"
                       "FULLMARKS STORE の Google広告 + Instagram・Facebook広告（Meta）", S["sub"]), Spacer(1, 3 * mm)]
    if partial:
        story.append(Paragraph(f"※ {until.month}/{until.day + 1}〜{month_end.month}/{month_end.day} の"
                               f"{(month_end - until).days}日分は含まれていません（月末見込みは日割りで算出）。", S["note"]))

    # 1. まとめ
    story.append(Paragraph("1. 今月のまとめ", S["h1"]))
    if narr.get("conclusion"):
        story += [wr.boxed([Paragraph("ひとことで言うと", S["note"]), Paragraph(narr["conclusion"], S["lead"])]),
                  Spacer(1, 3 * mm)]
    if ec:
        story += [Paragraph("お店全体（EC）", S["h2"]), ec_tiles(ec, normal["spend"] + event["spend"], normal["rev"] + event["rev"])]
    story += [Paragraph(f"広告（通常の運用。イベント広告は別）　{label}との比較", S["h2"]), wr.kpi_tiles(normal, normal_p, vs=label)]
    sig = ec_signals(ec) if ec else []
    sig.append(wr.pace_signal(normal["spend"], budget, n_days, dim, "広告の予算"))
    if not partial:
        r = normal["spend"] / budget if budget else 0
        sig[-1] = ("○" if 0.9 <= r <= 1.0 else "△", "広告の予算", f"{man(normal['spend'])}（予算 {man(budget)} の {r:.0%}）",
                   "予算内で、ほぼ使い切れた。" if 0.9 <= r <= 1.0 else ("予算を超えた。" if r > 1 else "使い残しが出た。"))
    sig.append(wr.roas_signal(normal, "広告の効率（広告1円あたりの売上）"))
    story += [Paragraph("信号（○◎は問題なし、△×は対応が必要）", S["h2"]), wr.signal_table(sig)]
    if narr.get("asks"):
        story.append(wr.boxed([Paragraph("承認をお願いしたいこと", S["h2"])] +
                              [Paragraph(x, S["bullet"], bulletText=f"{i}.") for i, x in enumerate(narr["asks"], 1)],
                              bg=colors.HexColor("#fff6e8"), border=wr.WARN))
    story.append(Paragraph("今月のポイント", S["h2"]))
    for line in narr.get("points", []) or wr.plain_points(brand_cur, cur["g_camps"] + cm, prev["g_camps"] + pm, vs=label):
        story.append(Paragraph(line, S["bullet"], bulletText="■"))

    # 2. お店全体
    if ec:
        story += [CondPageBreak(170 * mm), Paragraph("2. お店全体の売上と広告", S["h1"])]
        story += sec_ec(ec, brand_cur)

    # 3. 広告の成績
    story += [CondPageBreak(150 * mm), Paragraph(f"{3 if ec else 2}. 広告の成績", S["h1"])]
    story.append(KeepTogether([Paragraph("Google と Instagram・Facebook の比較（購入以外も）", S["h2"]),
                               wr.media_compare(cur_g, cur_m),
                               Paragraph("Instagram・Facebook の購入には、広告を見ただけ（クリックなし）で後日買った分も含まれる。"
                                         f"{label}は Google {roas(prev_g):.1f}円・Instagram・Facebook {roas(prev_m):.1f}円。", S["note"])]))
    story.append(KeepTogether([Paragraph("週ごとの広告費と、広告がきっかけの売上", S["h2"]), week_chart(cur, ev_ids, since, until)]))
    story.append(KeepTogether([Paragraph("ブランド別：広告がきっかけの売上", S["h2"]), wr.brand_chart(brand_cur),
                               Paragraph("棒の色は判定（緑◎・青○・橙△・赤×・灰＝件数が少なく判断保留）。", S["note"])]))

    # 4. 成績表
    story += [PageBreak(), Paragraph(f"{4 if ec else 3}. 広告ごとの成績表（通常の運用）", S["h1"]), wr.mark_legend(),
              Spacer(1, 2 * mm),
              wr.scorecard([("Google", c) for c in cur["g_camps"]] + [("Meta", c) for c in cm], prev["g_camps"] + pm, vs=label)]

    # 5. 施策と来月
    n5 = 5 if ec else 4
    story += [CondPageBreak(80 * mm), Paragraph(f"{n5}. 今月やったことと結果 / 来月に向けて", S["h1"])]
    if narr.get("actions"):
        data = [["日付", "やったこと", "結果"]] + [
            [a[0], Paragraph(a[1], S["cell"]), Paragraph(a[2], S["cell"])] for a in narr["actions"]]
        story.append(table(data, [18 * mm, 92 * mm, 70 * mm], align_right_from=9))
    if narr.get("next"):
        story.append(Paragraph("来月に向けて", S["h2"]))
        for line in narr["next"]:
            story.append(Paragraph(line, S["bullet"], bulletText="→"))
    story.append(KeepTogether([Paragraph("言葉の説明", S["h2"]), wr.glossary_table()]))

    # 参考資料
    story += [PageBreak(), Paragraph("参考資料（担当者向けの詳細）", S["h1"])]
    story.append(KeepTogether([Paragraph("予算の消化", S["h2"]), sec_budget(t, normal, event, since, until, budget)]))
    story.append(KeepTogether([Paragraph(f"媒体別（{label}との比較）", S["h2"]), sec_media(cur_m, cur_g, prev_m, prev_g, label)]))
    story.append(KeepTogether([Paragraph("週別（通常運用）", S["h2"]), sec_weeks(cur, ev_ids, since, until)]))
    story.append(KeepTogether([Paragraph("ブランド別（表）", S["h2"]), sec_brand(brand_cur, brand_prev, label)]))
    story.append(KeepTogether([Paragraph("広告の種類別", S["h2"]),
                               wr.sec_frame(wr.by_frame(cur["g_camps"], cm), wr.by_frame(prev["g_camps"], pm), vs=label)]))
    story.append(KeepTogether([Paragraph("Googleショッピングで売れた商品", S["h2"]), sec_products(cur["g_products"])]))
    story.append(Paragraph("イベント広告（通常と別予算・使った分だけ計上）", S["h2"]))
    if ce:
        data = [["キャンペーン", "広告費", "購入", "売上", "1円あたり"]] + [
            [disp(c["name"]), yen(c["spend"]), f"{c['cv']:.0f}", yen(c["rev"]), f"{roas(c):.1f}円"] for c in ce]
        story.append(table(data, [80 * mm, 26 * mm, 16 * mm, 30 * mm, 18 * mm]))
    else:
        story.append(Paragraph("今月のイベント広告はありません。", S["body"]))
    story.append(Paragraph("点検（リンク切れ・使ってはいけない口座・アウトレット品の表示）", S["h2"]))
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

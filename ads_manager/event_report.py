# -*- coding: utf-8 -*-
"""EC企画（イベント）広告の予算・成果を通常運用と分けて集計する。

targets.json の events[] に企画ごとの設定を持つ:
  {"key": "sw2026", "label": "SW2026 AUTUMN JOURNEY DAYS", "start": "2026-09-16", "end": "2026-09-23",
   "reserve_ex_tax": 90909, "meta_campaign_ids": [...], "google_asset_ids": [...]}
- Meta: キャンペーン単位（広告セット内訳つき）。費用・購入・売上。
- Google: プロモーション アセット単位（キャンペーン別）。アセットが表示された広告の費用・購入・売上。
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

TARGETS = Path(__file__).resolve().parent.parent / "targets.json"


def load_events() -> list[dict]:
    if not TARGETS.exists():
        return []
    t = json.loads(TARGETS.read_text(encoding="utf-8"))
    return t.get("events", [])


def _meta_actions(row, key, values=False):
    src = row.get("action_values" if values else "actions") or []
    for a in src:
        if a.get("action_type") == key:
            return float(a.get("value") or 0)
    return 0.0


def meta_event_rows(client, campaign_ids: list[str], since: date, until: date) -> list[dict]:
    if not campaign_ids:
        return []
    acct = client.config.ad_account_id
    tr = json.dumps({"since": str(since), "until": str(until)})
    flt = json.dumps([{"field": "campaign.id", "operator": "IN", "value": campaign_ids}])
    rows = []
    for r in client.get_all(f"{acct}/insights", level="adset", time_range=tr, filtering=flt,
                            fields="campaign_name,adset_name,spend,impressions,reach,clicks,actions,action_values", limit=100):
        rows.append({"media": "Meta", "name": f"{r['campaign_name']} / {r['adset_name']}",
                     "spend": float(r.get("spend") or 0), "imp": int(r.get("impressions") or 0),
                     "reach": int(r.get("reach") or 0), "clicks": int(r.get("clicks") or 0),
                     "cv": _meta_actions(r, "omni_purchase"), "rev": _meta_actions(r, "omni_purchase", True)})
    return rows


def google_event_rows(gclient, asset_ids: list[str], since: date, until: date) -> list[dict]:
    if not asset_ids or gclient is None:
        return []
    ids = ",".join(str(int(a)) for a in asset_ids)
    rows = []
    for r in gclient.search(
            "SELECT campaign.name, asset.id, asset.promotion_asset.promotion_target, metrics.impressions, "
            "metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value "
            f"FROM campaign_asset WHERE asset.id IN ({ids}) AND segments.date BETWEEN '{since}' AND '{until}'"):
        m = r.metrics
        rows.append({"media": "Google", "name": f"{r.campaign.name} / プロモーション「{r.asset.promotion_asset.promotion_target}」",
                     "spend": m.cost_micros / 1e6, "imp": m.impressions, "reach": None, "clicks": m.clicks,
                     "cv": m.conversions, "rev": m.conversions_value})
    return rows


def event_summary(meta_client, gclient, ev: dict, until: date | None = None) -> dict:
    since = date.fromisoformat(ev["start"])
    end = date.fromisoformat(ev["end"])
    until = min(until or date.today(), end)
    rows = meta_event_rows(meta_client, ev.get("meta_campaign_ids", []), since, until)
    rows += google_event_rows(gclient, ev.get("google_asset_ids", []), since, until)
    meta_spend = sum(r["spend"] for r in rows if r["media"] == "Meta")
    tot = {"spend": sum(r["spend"] for r in rows), "cv": sum(r["cv"] for r in rows), "rev": sum(r["rev"] for r in rows)}
    return {"event": ev, "since": since, "until": until, "rows": rows, "total": tot,
            "meta_spend": meta_spend, "reserve": ev.get("reserve_ex_tax", 0),
            "note": "Google のプロモーション表示は追加費用なし。表示された広告の費用・購入を参考値として計上"}


def format_text(summary: dict) -> str:
    ev = summary["event"]
    lines = [f"■ {ev['label']}（{summary['since']}〜{summary['until']}、企画期間 {ev['start']}〜{ev['end']}）"]
    for r in summary["rows"]:
        roas = r["rev"] / r["spend"] if r["spend"] else 0
        lines.append(f"  {r['media']:6s} {r['name']}: 費用 ¥{r['spend']:,.0f} 表示 {r['imp']:,} クリック {r['clicks']:,} "
                     f"購入 {r['cv']:.0f} 売上 ¥{r['rev']:,.0f} ROAS {roas:.1f}")
    t = summary["total"]
    lines.append(f"  合計: 費用 ¥{t['spend']:,.0f} 購入 {t['cv']:.0f} 売上 ¥{t['rev']:,.0f}")
    if summary["reserve"]:
        lines.append(f"  イベント予算（税抜）¥{summary['reserve']:,} に対する Meta 消化: ¥{summary['meta_spend']:,.0f}"
                     f"（{summary['meta_spend'] / summary['reserve']:.0%}）")
    lines.append("  " + summary["note"])
    return "\n".join(lines)

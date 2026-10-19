# -*- coding: utf-8 -*-
"""NEW ARRIVAL 静止画への差し替えと、ブランド別の予算変更（2026-10）。

設定は copy/creatives/202610/creatives.json。2段階で進める:
  launch()   … 購入者180日リストを用意 → 画像アップロード → 配置別クリエイティブ → 各ブランドの広告セットに新広告
               （HESTRA は全員向けキャンペーンを新設）→ ブランド広告セットから購入者180日を除外
  finalize() … 新広告の審査通過を確認してから、旧広告を停止し、キャンペーン／広告セットの日予算を変える
どちらも apply=False では計画の表示だけ。
"""
from __future__ import annotations

import json
from pathlib import Path

from .creative_swap import SIZES, create_placement_creative, upload
from .event_ads import PIXEL_ID
from .meta_ads import MetaAdsClient

PURCHASERS_180 = "FM_購入者_180日"


def ensure_purchaser_audience(client: MetaAdsClient, apply: bool = False) -> str | None:
    """サイトで購入した人（過去180日）のカスタムオーディエンス。無ければ作る。"""
    acct = client.config.ad_account_id
    for a in client.get_all(f"{acct}/customaudiences", fields="id,name", limit=200):
        if a["name"] == PURCHASERS_180:
            return a["id"]
    if not apply:
        return None
    rule = {"inclusions": {"operator": "or", "rules": [{
        "event_sources": [{"id": PIXEL_ID, "type": "pixel"}], "retention_seconds": 180 * 86400,
        "filter": {"operator": "and", "filters": [{"field": "event", "operator": "eq", "value": "Purchase"}]}}]}}
    r = client.post(f"{acct}/customaudiences", name=PURCHASERS_180, prefill="true",
                    rule=json.dumps(rule), description="Meta ピクセルの購入（過去180日）。NEW ARRIVAL 写真広告の除外用")
    return r["id"]


def _exclude(client: MetaAdsClient, adset_id: str, audience_id: str) -> dict:
    t = client.get(adset_id, fields="targeting")["targeting"]
    t["excluded_custom_audiences"] = [{"id": audience_id}]
    client.post(adset_id, targeting=json.dumps(t, ensure_ascii=False))
    return {"adset": adset_id, "excluded": PURCHASERS_180}


def _hestra_campaign(client: MetaAdsClient, spec: dict, audience_id: str, template_adset: str) -> str:
    """全員向け（Advantage+ オーディエンス）の CBO キャンペーンと広告セットを作り、広告セット ID を返す。"""
    acct = client.config.ad_account_id
    camp = client.post(f"{acct}/campaigns", name=spec["campaign_name"], objective="OUTCOME_SALES", status="ACTIVE",
                       special_ad_categories="[]", daily_budget=str(spec["daily_budget"]),
                       bid_strategy="LOWEST_COST_WITHOUT_CAP")
    t = client.get(template_adset, fields="targeting")["targeting"]
    t.pop("custom_audiences", None)
    t["excluded_custom_audiences"] = [{"id": audience_id}]
    adset = client.post(f"{acct}/adsets", name=spec["adset_name"], campaign_id=camp["id"], status="ACTIVE",
                        billing_event="IMPRESSIONS", optimization_goal="OFFSITE_CONVERSIONS",
                        promoted_object=json.dumps({"pixel_id": PIXEL_ID, "custom_event_type": "PURCHASE"}),
                        targeting=json.dumps(t, ensure_ascii=False),
                        attribution_spec=json.dumps([{"event_type": "CLICK_THROUGH", "window_days": 7},
                                                     {"event_type": "VIEW_THROUGH", "window_days": 1}]))
    return camp["id"], adset["id"]


def launch(client: MetaAdsClient, conf_path: str, apply: bool = False) -> dict:
    conf_path = Path(conf_path)
    conf = json.loads(conf_path.read_text(encoding="utf-8"))
    img_dir = conf_path.parent
    aud = ensure_purchaser_audience(client, apply=apply)
    plan = {"apply": apply, "purchasers_180": aud or "(作成予定)", "ads": [], "exclusions": []}
    acct = client.config.ad_account_id
    for a in conf["ads"]:
        entry = {"brand": a["brand"], "adsets": a.get("adsets") or "(新設キャンペーン)", "link": a["link"],
                 "headline": a["headline"]}
        if apply:
            hashes = {k: upload(client, img_dir / f"{a['file']}-newarrival_{w}x{h}.jpg") for k, (w, h) in SIZES.items()}
            cr = create_placement_creative(client, f"{a['file']}-newarrival-202610", hashes, a["message"],
                                           a["headline"], a["link"])
            adsets = a.get("adsets") or []
            if a.get("new_campaign"):
                cid, sid = _hestra_campaign(client, a["new_campaign"], aud, conf["template_adset"])
                entry["campaign_id"] = cid
                adsets = [sid]
            entry["ad_ids"] = []
            for i, sid in enumerate(adsets):
                name = f"{a['file']}-newarrival-202610" + (f"_{i + 1}" if len(adsets) > 1 else "")
                ad = client.post(f"{acct}/ads", name=name, adset_id=sid,
                                 creative=json.dumps({"creative_id": cr}), status="ACTIVE")
                entry["ad_ids"].append(ad["id"])
            entry["creative_id"] = cr
            a["new_ad_ids"] = entry["ad_ids"]
            if a.get("new_campaign"):
                a["new_campaign"]["campaign_id"], a["new_campaign"]["adset_id"] = entry["campaign_id"], adsets[0]
        plan["ads"].append(entry)
    for a in conf["ads"]:
        for sid in a.get("adsets") or []:
            plan["exclusions"].append(_exclude(client, sid, aud) if apply else {"adset": sid, "exclude": PURCHASERS_180})
    if apply:
        conf["purchasers_180"] = aud
        conf_path.write_text(json.dumps(conf, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan


def finalize(client: MetaAdsClient, conf_path: str, apply: bool = False) -> dict:
    """新広告がすべて ACTIVE（審査通過）なら旧広告を停止し、日予算を変える。未通過があれば何もしない。"""
    conf = json.loads(Path(conf_path).read_text(encoding="utf-8"))
    status = {}
    for a in conf["ads"]:
        for ad in a.get("new_ad_ids", []):
            status[ad] = client.get(ad, fields="effective_status")["effective_status"]
    ready = bool(status) and all(s == "ACTIVE" for s in status.values())
    plan = {"apply": apply, "new_ads": status, "ready": ready,
            "pause": [x for a in conf["ads"] for x in a.get("pause", [])], "budgets": conf.get("budgets", [])}
    if not (apply and ready):
        return plan
    for ad in plan["pause"]:
        client.set_status(ad, "PAUSED")
    for b in plan["budgets"]:
        client.post(b["id"], daily_budget=str(b["daily"]))
    plan["done"] = True
    return plan

# -*- coding: utf-8 -*-
"""配信先の比較テスト: 既存の広告セットと同じキャンペーンに「全員向け（Advantage+ オーディエンス）」の
広告セットを並べ、同じ広告（クリエイティブ）を複製する。キャンペーン予算（CBO）が成果の良い方へ自動配分される。

2026-09-23 ユーザー承認: SW企画で全員向けが訪問者向けに勝ったため、カタログ広告・ポック・ノローナで比較する。
"""
from __future__ import annotations

import json

from .meta_ads import MetaAdsClient

BROAD_TARGETING = {
    "geo_locations": {"countries": ["JP"], "location_types": ["home", "recent"]},
    "age_min": 25, "age_max": 65,
    "targeting_automation": {"advantage_audience": 1},
}


def meta_add_broad_copy(client: MetaAdsClient, source_adset_id: str, new_name: str,
                        ad_suffix: str = "_all", apply: bool = False) -> dict:
    """source の広告セットと同じ最適化設定で全員向けの広告セットを作り、配信中の広告を同じクリエイティブで複製する。"""
    acct = client.config.ad_account_id
    src = client.get(source_adset_id, fields="id,name,campaign_id,optimization_goal,billing_event,"
                                             "promoted_object,attribution_spec")
    ads = [a for a in client.get_all(f"{source_adset_id}/ads", fields="id,name,effective_status,creative{id}", limit=100)
           if a["effective_status"] in ("ACTIVE", "IN_PROCESS", "PENDING_REVIEW")]
    existing = {a["name"]: a for a in client.get_all(f"{src['campaign_id']}/adsets", fields="id,name", limit=50)}
    plan = {"apply": apply, "campaign_id": src["campaign_id"], "source_adset": src["name"],
            "new_adset": existing.get(new_name) or {"name": new_name, "status": "(新規)"},
            "targeting": "日本・25〜65歳・Advantage+ オーディエンス（新規含む全員）",
            "ads": [{"name": a["name"] + ad_suffix, "creative_id": a["creative"]["id"]} for a in ads]}
    if not apply:
        return plan
    adset = existing.get(new_name)
    if adset is None:
        promoted = {k: v for k, v in src["promoted_object"].items() if k in ("pixel_id", "custom_event_type")}
        adset = client.post(f"{acct}/adsets", name=new_name, campaign_id=src["campaign_id"], status="ACTIVE",
                            billing_event=src["billing_event"], optimization_goal=src["optimization_goal"],
                            promoted_object=json.dumps(promoted),
                            targeting=json.dumps(BROAD_TARGETING, ensure_ascii=False),
                            attribution_spec=json.dumps(src["attribution_spec"]))
    plan["new_adset"] = adset
    have = {a["name"] for a in client.get_all(f"{adset['id']}/ads", fields="name", limit=100)}
    for a in plan["ads"]:
        if a["name"] in have:
            continue
        r = client.post(f"{acct}/ads", name=a["name"], adset_id=adset["id"],
                        creative=json.dumps({"creative_id": a["creative_id"]}), status="ACTIVE")
        a["ad_id"] = r["id"]
    return plan


def meta_set_advantage_audience(client: MetaAdsClient, adset_id: str, apply: bool = False) -> dict:
    """既存の広告セットの絞り込み（興味関心など）を残したまま Advantage+ オーディエンスを ON にし、
    Meta が絞り込みの外にも広げられるようにする。"""
    a = client.get(adset_id, fields="id,name,targeting")
    t = dict(a["targeting"])
    t["targeting_automation"] = {"advantage_audience": 1}
    t.pop("targeting_relaxation_types", None)
    geo = dict(t.get("geo_locations", {}))
    if "location_types" in geo:
        geo["location_types"] = [x for x in geo["location_types"] if x in ("home", "recent")] or ["home", "recent"]
    t["geo_locations"] = geo
    plan = {"apply": apply, "adset": a["name"], "advantage_audience": "0 → 1（興味関心は起点として残す）"}
    if apply:
        plan["result"] = client.post(adset_id, targeting=json.dumps(t, ensure_ascii=False))
    return plan

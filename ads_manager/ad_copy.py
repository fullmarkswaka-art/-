# -*- coding: utf-8 -*-
"""広告文の差し替え（Meta 静止画リンク広告 / Google レスポンシブ検索広告）。

どちらも既存の広告文は編集できないため、同じ画像・リンク・設定で新しい広告を作り、
旧広告を停止する（ドライラン → --apply）。
"""
from __future__ import annotations

import json
import unicodedata

from .meta_ads import MetaAdsClient

H_MAX, D_MAX = 30, 90  # Google: 全角は2文字分として数える


def gw(s: str) -> int:
    """Google の文字数カウント（全角=2）。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def validate_rsa(headlines: list[str], descriptions: list[str]) -> list[str]:
    errs = []
    if not 3 <= len(headlines) <= 15:
        errs.append(f"見出しは3〜15本（現在{len(headlines)}）")
    if not 2 <= len(descriptions) <= 4:
        errs.append(f"説明文は2〜4本（現在{len(descriptions)}）")
    for h in headlines:
        if gw(h) > H_MAX:
            errs.append(f"見出しが{H_MAX}を超過({gw(h)}): {h}")
    for d in descriptions:
        if gw(d) > D_MAX:
            errs.append(f"説明文が{D_MAX}を超過({gw(d)}): {d}")
    return errs


# ---------- Meta ----------

def meta_replace_link_ad(client: MetaAdsClient, ad_id: str, message: str,
                         headline: str | None = None, description: str | None = None,
                         apply: bool = False) -> dict:
    old = client.get(ad_id, fields="id,name,status,adset_id,creative{id,name,object_story_spec}")
    spec = old["creative"]["object_story_spec"]
    ld = dict(spec["link_data"])
    ld["message"] = message
    if headline is not None:
        ld["name"] = headline
    if description is not None:
        ld["description"] = description
    new_spec = {"page_id": spec["page_id"], "link_data": ld}
    plan = {"old_ad": {"id": old["id"], "name": old["name"], "status": old["status"]},
            "old_text": spec["link_data"], "new_text": ld, "apply": apply}
    if not apply:
        return plan
    creative = client.post(f"{client.config.ad_account_id}/adcreatives",
                           name=f"{old['creative'].get('name', old['name'])}_v2",
                           object_story_spec=json.dumps(new_spec, ensure_ascii=False))
    ad = client.post(f"{client.config.ad_account_id}/ads",
                     name=f"{old['name']}_v2", adset_id=old["adset_id"],
                     creative=json.dumps({"creative_id": creative["id"]}), status="ACTIVE")
    client.set_status(old["id"], "PAUSED")
    plan.update(new_creative_id=creative["id"], new_ad_id=ad["id"], old_ad_paused=True)
    return plan


# ---------- Google ----------

def google_replace_rsa(gclient, old_ad_id: str, headlines: list[str],
                       descriptions: list[str], path1: str | None = None,
                       path2: str | None = None, apply: bool = False) -> dict:
    errs = validate_rsa(headlines, descriptions)
    rows = gclient.search(
        "SELECT ad_group.id, ad_group.name, ad_group_ad.ad.id, ad_group_ad.status, "
        "ad_group_ad.ad.final_urls, ad_group_ad.ad.responsive_search_ad.headlines, "
        "ad_group_ad.ad.responsive_search_ad.descriptions, "
        "ad_group_ad.ad.responsive_search_ad.path1, ad_group_ad.ad.responsive_search_ad.path2 "
        f"FROM ad_group_ad WHERE ad_group_ad.ad.id={old_ad_id}")
    if not rows:
        raise RuntimeError(f"広告 {old_ad_id} が見つかりません")
    r = rows[0]
    old = r.ad_group_ad.ad
    plan = {"ad_group": {"id": r.ad_group.id, "name": r.ad_group.name},
            "old_ad": {"id": old.id, "status": r.ad_group_ad.status.name,
                       "headlines": [h.text for h in old.responsive_search_ad.headlines],
                       "descriptions": [d.text for d in old.responsive_search_ad.descriptions]},
            "new_ad": {"headlines": [f"{h} ({gw(h)})" for h in headlines],
                       "descriptions": [f"{d} ({gw(d)})" for d in descriptions],
                       "final_urls": list(old.final_urls),
                       "path1": path1 if path1 is not None else old.responsive_search_ad.path1,
                       "path2": path2 if path2 is not None else old.responsive_search_ad.path2},
            "validation_errors": errs, "apply": apply}
    if errs or not apply:
        return plan
    client = gclient.client
    cid = gclient.customer_id
    svc = client.get_service("AdGroupAdService")
    op = client.get_type("AdGroupAdOperation")
    aga = op.create
    aga.ad_group = client.get_service("AdGroupService").ad_group_path(cid, r.ad_group.id)
    aga.status = client.enums.AdGroupAdStatusEnum.ENABLED
    aga.ad.final_urls.extend(list(old.final_urls))
    rsa = aga.ad.responsive_search_ad
    for h in headlines:
        a = client.get_type("AdTextAsset"); a.text = h; rsa.headlines.append(a)
    for d in descriptions:
        a = client.get_type("AdTextAsset"); a.text = d; rsa.descriptions.append(a)
    if plan["new_ad"]["path1"]:
        rsa.path1 = plan["new_ad"]["path1"]
    if plan["new_ad"]["path2"]:
        rsa.path2 = plan["new_ad"]["path2"]
    res = svc.mutate_ad_group_ads(customer_id=cid, operations=[op])
    plan["new_ad"]["resource_name"] = res.results[0].resource_name
    # 旧広告を停止
    op2 = client.get_type("AdGroupAdOperation")
    op2.update.resource_name = svc.ad_group_ad_path(cid, r.ad_group.id, old.id)
    op2.update.status = client.enums.AdGroupAdStatusEnum.PAUSED
    from google.api_core import protobuf_helpers
    client.copy_from(op2.update_mask, protobuf_helpers.field_mask(None, op2.update._pb))
    svc.mutate_ad_group_ads(customer_id=cid, operations=[op2])
    plan["old_ad"]["status"] = "PAUSED"
    return plan

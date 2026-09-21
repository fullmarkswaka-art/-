# -*- coding: utf-8 -*-
"""EC企画（シルバーウィーク等）の期間限定バナー広告を Meta / Google に出す。

- Meta: 静止画1枚のリンク広告。訪問者・購入者へのリターゲティングに限定し、期間終了で自動停止。
- Google: 指名検索キャンペーンにプロモーション アセット（「最大10%OFF」＋期間）を付ける。
  ※ 検索広告は画像を出せないため、割引情報をアセットで表示する。
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from .meta_ads import MetaAdsClient
from .outlet_rtg import (AUD_ALL_VISITORS_30D, AUD_PURCHASERS_30D, IG_USER_ID, PAGE_ID,
                         PIXEL_ID)


# ---------- Meta ----------

def meta_create_event_ad(client: MetaAdsClient, name: str, image_path: str, message: str,
                         headline: str, link: str, daily_budget: int, end_date: str,
                         include_purchasers: bool = True, url_tags: str | None = None,
                         end_hm: str = "23:50", apply: bool = False) -> dict:
    """静止画1枚のリンク広告を新規キャンペーンで作成する（訪問者30日、任意で購入者30日も含む）。
    url_tags: 例 "utm_source=meta&utm_medium=paid_social&utm_campaign=sw2026"（EC側の計測用）。

    name: キャンペーン名の識別子（例 SW2026_AUTUMN_JOURNEY）。
    end_date: YYYY-MM-DD、end_hm: HH:MM（JST）でキャンペーン終了。
    既定を 23:50 にしているのは、締切直前の流入がクーポンを使えず無駄になるため（2026-09-21 ユーザー指示）。
    """
    acct = client.config.ad_account_id
    camp_name = f"UC_DN_3_CVS_{name}"
    adset_name = f"UCDN3_CVS_{name}_訪問者30日"
    ad_name = f"{name.lower()}_1080x1080"
    existing = {c["name"]: c for c in client.get_all(f"{acct}/campaigns", fields="id,name,status")}
    end_time = f"{end_date}T{end_hm}:00+0900"
    targeting = {
        "geo_locations": {"countries": ["JP"], "location_types": ["home", "recent"]},
        "age_min": 25, "age_max": 65,
        "custom_audiences": [{"id": AUD_ALL_VISITORS_30D}] + ([{"id": AUD_PURCHASERS_30D}] if include_purchasers else []),
        "targeting_automation": {"advantage_audience": 0},
    }
    plan = {"apply": apply, "campaign": existing.get(camp_name) or {"name": camp_name, "status": "(新規)"},
            "daily_budget": daily_budget, "end_time": end_time,
            "adset": {"name": adset_name, "include": ["FM_全訪問者_30日"] + (["FM_購入者_30日"] if include_purchasers else []),
                      "optimization": "OFFSITE_CONVERSIONS/PURCHASE"},
            "ad": {"name": ad_name, "image": str(image_path), "headline": headline, "link": link,
                   "message_preview": message[:120] + ("…" if len(message) > 120 else "")}}
    if not apply:
        return plan
    if not Path(image_path).exists():
        raise FileNotFoundError(image_path)
    up = client.post_file(f"{acct}/adimages", image_path)
    img = list(up["images"].values())[0]
    plan["ad"]["image_hash"] = img["hash"]
    camp = existing.get(camp_name)
    if camp is None:
        camp = client.post(f"{acct}/campaigns", name=camp_name, objective="OUTCOME_SALES",
                           status="PAUSED", buying_type="AUCTION", daily_budget=daily_budget,
                           bid_strategy="LOWEST_COST_WITHOUT_CAP", special_ad_categories="[]",
                           stop_time=end_time)
    plan["campaign"] = camp
    adset = client.post(f"{acct}/adsets", name=adset_name, campaign_id=camp["id"], status="ACTIVE",
                        billing_event="IMPRESSIONS", optimization_goal="OFFSITE_CONVERSIONS",
                        promoted_object=json.dumps({"pixel_id": PIXEL_ID, "custom_event_type": "PURCHASE"}),
                        targeting=json.dumps(targeting, ensure_ascii=False), end_time=end_time,
                        attribution_spec=json.dumps([{"event_type": "CLICK_THROUGH", "window_days": 7},
                                                     {"event_type": "VIEW_THROUGH", "window_days": 1}]))
    plan["adset"]["id"] = adset["id"]
    spec = {"page_id": PAGE_ID, "instagram_user_id": IG_USER_ID,
            "link_data": {"image_hash": img["hash"], "link": link, "message": message, "name": headline,
                          "call_to_action": {"type": "SHOP_NOW", "value": {"link": link}}}}
    extra = {"url_tags": url_tags} if url_tags else {}
    creative = client.post(f"{acct}/adcreatives", name=ad_name,
                           object_story_spec=json.dumps(spec, ensure_ascii=False), **extra)
    ad = client.post(f"{acct}/ads", name=ad_name, adset_id=adset["id"],
                     creative=json.dumps({"creative_id": creative["id"]}), status="ACTIVE")
    plan["ad"].update(creative_id=creative["id"], ad_id=ad["id"])
    client.set_status(camp["id"], "ACTIVE")
    plan["campaign"]["status"] = "ACTIVE"
    return plan


def meta_add_broad_adset(client: MetaAdsClient, campaign_id: str, creative_id: str, name: str,
                         end_date: str, end_hm: str = "23:50", apply: bool = False) -> dict:
    """既存のイベント広告キャンペーンに「全員向け（Advantage+ オーディエンス）」広告セットを追加し、
    同じクリエイティブで広告を作る。キャンペーン予算（CBO）が2つの広告セットに自動配分される。"""
    acct = client.config.ad_account_id
    adset_name = f"UCDN3_CVS_{name}_全員_Advantage+"
    ad_name = f"{name.lower()}_1080x1080_all"
    end_time = f"{end_date}T{end_hm}:00+0900"
    targeting = {
        "geo_locations": {"countries": ["JP"], "location_types": ["home", "recent"]},
        "age_min": 25, "age_max": 65,
        "targeting_automation": {"advantage_audience": 1},
    }
    existing = {a["name"]: a for a in client.get_all(f"{campaign_id}/adsets", fields="id,name,status")}
    plan = {"apply": apply, "campaign_id": campaign_id, "adset": existing.get(adset_name) or {"name": adset_name, "status": "(新規)"},
            "targeting": "日本・25〜65歳・Advantage+ オーディエンス（新規含む全員）", "ad": {"name": ad_name, "creative_id": creative_id},
            "end_time": end_time}
    if not apply:
        return plan
    adset = existing.get(adset_name)
    if adset is None:
        adset = client.post(f"{acct}/adsets", name=adset_name, campaign_id=campaign_id, status="ACTIVE",
                            billing_event="IMPRESSIONS", optimization_goal="OFFSITE_CONVERSIONS",
                            promoted_object=json.dumps({"pixel_id": PIXEL_ID, "custom_event_type": "PURCHASE"}),
                            targeting=json.dumps(targeting, ensure_ascii=False), end_time=end_time,
                            attribution_spec=json.dumps([{"event_type": "CLICK_THROUGH", "window_days": 7},
                                                         {"event_type": "VIEW_THROUGH", "window_days": 1}]))
    plan["adset"] = adset
    ad = client.post(f"{acct}/ads", name=ad_name, adset_id=adset["id"],
                     creative=json.dumps({"creative_id": creative_id}), status="ACTIVE")
    plan["ad"]["ad_id"] = ad["id"]
    return plan


# ---------- Google ----------

def google_create_promotion_asset(gclient, campaign_ids: list[str], promotion_target: str,
                                  percent_off: int, start_date: str, end_date: str,
                                  final_url: str, up_to: bool = True, promotion_code: str | None = None,
                                  apply: bool = False) -> dict:
    """プロモーション アセット（例: 対象のOUTLET商品 最大10%OFF 9/16〜9/23）を作り、
    指定キャンペーンにリンクする。期間終了後は自動で表示されなくなる。"""
    rows = gclient.search("SELECT campaign.id, campaign.name, campaign.status FROM campaign WHERE campaign.id IN ("
                          + ",".join(str(int(c)) for c in campaign_ids) + ")")
    camps = [{"id": str(r.campaign.id), "name": r.campaign.name, "status": r.campaign.status.name} for r in rows]
    plan = {"apply": apply, "asset": {"promotion_target": promotion_target,
                                     "discount": f"{'最大' if up_to else ''}{percent_off}%OFF",
                                     "period": f"{start_date}〜{end_date}", "final_url": final_url,
                                     "promotion_code": promotion_code},
            "campaigns": camps}
    if not apply:
        return plan
    client = gclient.client
    asset_svc = client.get_service("AssetService")
    op = client.get_type("AssetOperation")
    a = op.create
    a.name = f"promo_{promotion_target}_{start_date}"
    a.final_urls.append(final_url)
    p = a.promotion_asset
    p.promotion_target = promotion_target
    p.percent_off = int(percent_off) * 10_000  # 1,000,000 = 100%
    p.language_code = "ja"
    if up_to:
        p.discount_modifier = client.enums.PromotionExtensionDiscountModifierEnum.UP_TO
    p.start_date = start_date
    p.end_date = end_date
    if promotion_code:
        p.promotion_code = promotion_code
    resp = asset_svc.mutate_assets(customer_id=gclient.customer_id, operations=[op])
    asset_rn = resp.results[0].resource_name
    plan["asset"]["resource_name"] = asset_rn
    ca_svc = client.get_service("CampaignAssetService")
    ops = []
    for c in camps:
        cop = client.get_type("CampaignAssetOperation")
        ca = cop.create
        ca.campaign = client.get_service("CampaignService").campaign_path(gclient.customer_id, c["id"])
        ca.asset = asset_rn
        ca.field_type = client.enums.AssetFieldTypeEnum.PROMOTION
        ops.append(cop)
    r2 = ca_svc.mutate_campaign_assets(customer_id=gclient.customer_id, operations=ops)
    plan["campaign_assets"] = [x.resource_name for x in r2.results]
    return plan


def google_remove_promotion_asset(gclient, asset_id: str, apply: bool = False) -> dict:
    """プロモーション アセットのキャンペーン紐付けを外す。
    Google のアセットは終了日（日付単位）しか指定できないため、当日の途中で止めたいときに使う。"""
    rows = gclient.search(
        "SELECT campaign.name, campaign_asset.resource_name, campaign_asset.status FROM campaign_asset "
        f"WHERE campaign_asset.field_type='PROMOTION' AND asset.id = {int(asset_id)}")
    links = [{"campaign": r.campaign.name, "resource_name": r.campaign_asset.resource_name,
              "status": r.campaign_asset.status.name} for r in rows]
    plan = {"apply": apply, "asset_id": str(asset_id), "links": links}
    if not apply or not links:
        return plan
    client = gclient.client
    svc = client.get_service("CampaignAssetService")
    ops = []
    for link in links:
        op = client.get_type("CampaignAssetOperation")
        op.remove = link["resource_name"]
        ops.append(op)
    resp = svc.mutate_campaign_assets(customer_id=gclient.customer_id, operations=ops)
    plan["removed"] = [x.resource_name for x in resp.results]
    return plan

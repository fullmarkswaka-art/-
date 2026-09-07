# -*- coding: utf-8 -*-
"""アウトレット商品を「サイト訪問者だけ」に配信するリターゲティング枠（Meta / Google）。

ブランディング方針: 新規ユーザーの目に触れる枠（検索結果・類似オーディエンス）には
アウトレット品を出さない。売上の8割を占めるアウトレット品は、一度サイトを見た人への
再訴求に限定して配信する。
"""
from __future__ import annotations

import csv
import json

from .catalog_attributes import LABEL_OUTLET, SUPPLEMENT_CSV, load_feed
from .meta_ads import MetaAdsClient

CATALOG_ID = "610915616169358"
PAGE_ID = "314214805342365"
PIXEL_ID = "1044166285243333"
IG_USER_ID = "17841404773057326"
AUD_ALL_VISITORS_30D = "52598939034335"   # FM_全訪問者_30日
AUD_PURCHASERS_30D = "52597386243535"     # FM_購入者_30日
OUTLET_SET_NAME = "アウトレット_全ブランド（在庫あり）"
META_CAMPAIGN_NAME = "UC_DN_3_CVS_アウトレット_RTG"
META_ADSET_NAME = "UCDN3_CVS_アウトレット_訪問者30日"
META_AD_NAME = "fullmarks-dpa-OUTLET_RTG"
META_MESSAGE = "FULLMARKS OUTLET"
OUTLET_LINK = "https://www.fullmarksstore.jp/category/OUTLET/"

GOOGLE_CAMPAIGN_NAME = "UC_PL_6_PLA_outlet_RTG"
GOOGLE_MERCHANT_ID = 5642612701
GOOGLE_USER_LISTS = ["502631676", "826948853"]  # AdWords optimized list(30日) / カート訪問
GOOGLE_GEO_JP = "geoTargetConstants/2392"


def outlet_in_stock_ids() -> list[str]:
    feed = load_feed()
    with open(SUPPLEMENT_CSV, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return [r["id"] for r in rows if r["custom_label_0"] == LABEL_OUTLET
            and feed.get(r["id"], {}).get("availability") == "in stock"]


# ---------- Meta ----------

def meta_create_outlet_rtg(client: MetaAdsClient, daily_budget: int = 1500,
                           apply: bool = False) -> dict:
    ids = outlet_in_stock_ids()
    acct = client.config.ad_account_id
    existing_sets = {ps["name"]: ps for ps in client.get_all(f"{CATALOG_ID}/product_sets", fields="id,name,product_count")}
    existing_camps = {c["name"]: c for c in client.get_all(f"{acct}/campaigns", fields="id,name,status")}
    plan = {"apply": apply, "outlet_in_stock_ids": len(ids),
            "product_set": existing_sets.get(OUTLET_SET_NAME),
            "campaign": existing_camps.get(META_CAMPAIGN_NAME),
            "adset": {"name": META_ADSET_NAME, "daily_budget(campaign CBO)": daily_budget,
                      "include": "FM_全訪問者_30日", "exclude": "FM_購入者_30日",
                      "optimization": "OFFSITE_CONVERSIONS/PURCHASE"},
            "ad": {"name": META_AD_NAME, "message": META_MESSAGE, "link": OUTLET_LINK}}
    if not apply:
        return plan
    ps = existing_sets.get(OUTLET_SET_NAME)
    flt = json.dumps({"retailer_id": {"is_any": ids}})
    if ps is None:
        ps = client.post(f"{CATALOG_ID}/product_sets", name=OUTLET_SET_NAME, filter=flt)
    else:
        client.post(ps["id"], filter=flt)
    plan["product_set"] = ps
    camp = existing_camps.get(META_CAMPAIGN_NAME)
    if camp is None:
        camp = client.post(f"{acct}/campaigns", name=META_CAMPAIGN_NAME, objective="OUTCOME_SALES",
                           status="PAUSED", buying_type="AUCTION", daily_budget=daily_budget,
                           bid_strategy="LOWEST_COST_WITHOUT_CAP", special_ad_categories="[]")
    plan["campaign"] = camp
    targeting = {
        "geo_locations": {"countries": ["JP"], "location_types": ["home", "recent"]},
        "age_min": 25, "age_max": 65,
        "custom_audiences": [{"id": AUD_ALL_VISITORS_30D}],
        "excluded_custom_audiences": [{"id": AUD_PURCHASERS_30D}],
        "targeting_automation": {"advantage_audience": 0},
    }
    adset = client.post(f"{acct}/adsets", name=META_ADSET_NAME, campaign_id=camp["id"],
                        status="ACTIVE", billing_event="IMPRESSIONS",
                        optimization_goal="OFFSITE_CONVERSIONS",
                        promoted_object=json.dumps({"pixel_id": PIXEL_ID, "custom_event_type": "PURCHASE"}),
                        targeting=json.dumps(targeting, ensure_ascii=False),
                        attribution_spec=json.dumps([{"event_type": "CLICK_THROUGH", "window_days": 7},
                                                     {"event_type": "VIEW_THROUGH", "window_days": 1}]))
    plan["adset"]["id"] = adset["id"]
    creative = client.post(f"{acct}/adcreatives", name=META_AD_NAME,
                           object_story_spec=json.dumps({"page_id": PAGE_ID, "template_data": {
                               "link": OUTLET_LINK, "message": META_MESSAGE,
                               "call_to_action": {"type": "SHOP_NOW", "value": {"link": OUTLET_LINK}},
                               "multi_share_end_card": False, "show_multiple_images": False}}, ensure_ascii=False),
                           product_set_id=ps["id"], instagram_user_id=IG_USER_ID,
                           asset_feed_spec=json.dumps({"ad_formats": ["CAROUSEL", "COLLECTION"],
                                                       "optimization_type": "FORMAT_AUTOMATION"}))
    ad = client.post(f"{acct}/ads", name=META_AD_NAME, adset_id=adset["id"],
                     creative=json.dumps({"creative_id": creative["id"]}), status="ACTIVE")
    plan["ad"].update(creative_id=creative["id"], ad_id=ad["id"])
    client.set_status(camp["id"], "ACTIVE")
    plan["campaign"]["status"] = "ACTIVE"
    return plan


# ---------- Google ----------

def google_create_outlet_rtg(gclient, daily_budget_yen: float = 1500.0, cpc_yen: float = 15.0,
                             pla_v2_new_budget_yen: float | None = 3000.0,
                             apply: bool = False) -> dict:
    rows = gclient.search("SELECT campaign.id, campaign.name, campaign.status FROM campaign "
                          f"WHERE campaign.name='{GOOGLE_CAMPAIGN_NAME}'")
    existing = [(r.campaign.id, r.campaign.status.name) for r in rows]
    plan = {"apply": apply, "existing_campaign": existing,
            "campaign": {"name": GOOGLE_CAMPAIGN_NAME, "type": "SHOPPING (MANUAL_CPC)",
                         "daily_budget": daily_budget_yen, "cpc": cpc_yen,
                         "products": "custom_label_0 = outlet のみ（他は除外）",
                         "audience(TARGETING)": ["AdWords optimized list(30日)", "カート訪問"]},
            "pla_v2_budget": pla_v2_new_budget_yen}
    if not apply or existing:
        return plan
    client = gclient.client
    cid = gclient.customer_id
    # 1) 予算
    bs = client.get_service("CampaignBudgetService")
    bname = f"{GOOGLE_CAMPAIGN_NAME} budget"
    prev = gclient.search(f"SELECT campaign_budget.resource_name FROM campaign_budget WHERE campaign_budget.name='{bname}' AND campaign_budget.status='ENABLED'")
    if prev:
        budget_rn = prev[0].campaign_budget.resource_name
    else:
        op = client.get_type("CampaignBudgetOperation"); b = op.create
        b.name = bname; b.amount_micros = int(daily_budget_yen * 1_000_000)
        b.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
        budget_rn = bs.mutate_campaign_budgets(customer_id=cid, operations=[op]).results[0].resource_name
    # 2) キャンペーン
    cs = client.get_service("CampaignService")
    op = client.get_type("CampaignOperation"); c = op.create
    c.name = GOOGLE_CAMPAIGN_NAME
    c.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SHOPPING
    c.status = client.enums.CampaignStatusEnum.PAUSED
    c.campaign_budget = budget_rn
    c.contains_eu_political_advertising = client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
    c.manual_cpc.enhanced_cpc_enabled = False
    c.shopping_setting.merchant_id = GOOGLE_MERCHANT_ID
    c.shopping_setting.feed_label = "JP"
    c.shopping_setting.campaign_priority = 0
    c.network_settings.target_google_search = True
    c.network_settings.target_search_network = True
    camp_rn = cs.mutate_campaigns(customer_id=cid, operations=[op]).results[0].resource_name
    # 3) 地域: 日本
    ccs = client.get_service("CampaignCriterionService")
    op = client.get_type("CampaignCriterionOperation"); cc = op.create
    cc.campaign = camp_rn; cc.location.geo_target_constant = GOOGLE_GEO_JP
    ccs.mutate_campaign_criteria(customer_id=cid, operations=[op])
    # 4) 広告グループ
    ags = client.get_service("AdGroupService")
    op = client.get_type("AdGroupOperation"); ag = op.create
    ag.name = "アウトレット_訪問者"; ag.campaign = camp_rn
    ag.type_ = client.enums.AdGroupTypeEnum.SHOPPING_PRODUCT_ADS
    ag.status = client.enums.AdGroupStatusEnum.ENABLED
    ag.cpc_bid_micros = int(cpc_yen * 1_000_000)
    ag_rn = ags.mutate_ad_groups(customer_id=cid, operations=[op]).results[0].resource_name
    ag_id = ag_rn.split("/")[-1]
    # 5) 商品グループ: root → outlet(入札) / その他(除外)
    agcs = client.get_service("AdGroupCriterionService")
    lg = client.enums.ListingGroupTypeEnum; idx = client.enums.ProductCustomAttributeIndexEnum
    ops = []
    op = client.get_type("AdGroupCriterionOperation"); r = op.create
    r.ad_group = ag_rn; r.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
    r.resource_name = agcs.ad_group_criterion_path(cid, ag_id, -1)
    r.listing_group.type_ = lg.SUBDIVISION; ops.append(op); root_rn = r.resource_name
    op = client.get_type("AdGroupCriterionOperation"); u = op.create
    u.ad_group = ag_rn; u.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
    u.cpc_bid_micros = int(cpc_yen * 1_000_000)
    u.listing_group.type_ = lg.UNIT; u.listing_group.parent_ad_group_criterion = root_rn
    u.listing_group.case_value.product_custom_attribute.index = idx.INDEX0
    u.listing_group.case_value.product_custom_attribute.value = LABEL_OUTLET; ops.append(op)
    op = client.get_type("AdGroupCriterionOperation"); o = op.create
    o.ad_group = ag_rn; o.status = client.enums.AdGroupCriterionStatusEnum.ENABLED; o.negative = True
    o.listing_group.type_ = lg.UNIT; o.listing_group.parent_ad_group_criterion = root_rn
    o.listing_group.case_value.product_custom_attribute.index = idx.INDEX0; ops.append(op)
    agcs.mutate_ad_group_criteria(customer_id=cid, operations=ops)
    # 6) オーディエンス（ターゲティングモード）
    # AUDIENCE を「ターゲティング」(bid_only=False) にする。Google はデモグラ系の
    # 次元も同時に列挙しないと拒否する（bid_only=True のまま並べる）
    op = client.get_type("AdGroupOperation"); agu = op.update
    agu.resource_name = ag_rn
    TD = client.enums.TargetingDimensionEnum
    for dim, bid_only in [(TD.AUDIENCE, False), (TD.AGE_RANGE, True), (TD.GENDER, True),
                          (TD.PARENTAL_STATUS, True), (TD.INCOME_RANGE, True)]:
        tr = client.get_type("TargetRestriction")
        tr.targeting_dimension = dim; tr.bid_only = bid_only
        agu.targeting_setting.target_restrictions.append(tr)
    op.update_mask.paths.append("targeting_setting.target_restrictions")
    ags.mutate_ad_groups(customer_id=cid, operations=[op])
    uls = client.get_service("UserListService")
    ops = []
    for ul in GOOGLE_USER_LISTS:
        op = client.get_type("AdGroupCriterionOperation"); a = op.create
        a.ad_group = ag_rn; a.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        a.user_list.user_list = uls.user_list_path(cid, ul); ops.append(op)
    agcs.mutate_ad_group_criteria(customer_id=cid, operations=ops)
    # 7) ショッピング広告
    agas = client.get_service("AdGroupAdService")
    op = client.get_type("AdGroupAdOperation"); ada = op.create
    ada.ad_group = ag_rn; ada.status = client.enums.AdGroupAdStatusEnum.ENABLED
    client.copy_from(ada.ad.shopping_product_ad, client.get_type("ShoppingProductAdInfo"))
    agas.mutate_ad_group_ads(customer_id=cid, operations=[op])
    # 8) 有効化
    op = client.get_type("CampaignOperation"); cu = op.update
    cu.resource_name = camp_rn; cu.status = client.enums.CampaignStatusEnum.ENABLED
    op.update_mask.paths.append("status")
    cs.mutate_campaigns(customer_id=cid, operations=[op])
    plan["created"] = {"campaign": camp_rn, "ad_group": ag_rn}
    if pla_v2_new_budget_yen:
        plan["pla_v2_budget_result"] = gclient.set_campaign_budget("24136223642", pla_v2_new_budget_yen)
    return plan

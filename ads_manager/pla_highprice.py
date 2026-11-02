# -*- coding: utf-8 -*-
"""Googleショッピング：値段の高い冬物（4万円以上の通常品）だけの別キャンペーン（2026-11 ユーザー承認の形）。

  ・対象: 在庫ありの通常品（アウトレット除く）で、税込 4万円以上・アウター／ボトムス／トップス、商品名に夏物の語を含まないもの。
    Merchant Center の補助データで custom_label_2 = "pla_high" を付ける（`google mc-supplement --apply` が一緒に登録。
    毎週の定例で入れ替わる）。
  ・入札: 「クリック数の最大化」（1クリックの上限 60円）＋日予算 1,000円。単価は上限の範囲で Google が自動で決める。
    購入がたまったら（目安 月10件以上）「コンバージョン値の最大化」に切り替える。
  ・優先度「高」にして、PLA_v2 と同じ商品が重なったときはこちらが出る。除外キーワードは PLA_v2 と同じ。
apply=False では計画と対象商品の表示だけ。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .catalog_attributes import LABEL_OUTLET, SUPPLEMENT_CSV, load_feed
from .outlet_rtg import GOOGLE_GEO_JP, GOOGLE_MERCHANT_ID
from .shopping_titles import NEGATIVES, TITLES_CSV, pla_negatives

ROOT = Path(__file__).resolve().parent.parent
CAMPAIGN_NAME = "UC_PL_7_PLA_高価格冬物"
LABEL = "pla_high"
MIN_PRICE = 40000
CATEGORIES = {"アウター", "ボトムス", "トップス"}
DAILY_BUDGET = 1000
CPC_CEILING = 60
ITEMS_CSV = ROOT / "reports" / "pla_highprice_items.csv"


def high_price_items(feed: dict | None = None) -> list[dict]:
    feed = feed or load_feed()
    summer = [w.lower() for w in json.loads((ROOT / "config" / "season_sets.json").read_text(encoding="utf-8"))
              .get("exclude_title_words", [])]
    attrs = {r["id"]: r for r in csv.DictReader(open(SUPPLEMENT_CSV, encoding="utf-8"))}
    titles = {r["id"]: r for r in csv.DictReader(open(TITLES_CSV, encoding="utf-8"))} if TITLES_CSV.exists() else {}
    out = []
    for pid, f in feed.items():
        a, t = attrs.get(pid, {}), titles.get(pid, {})
        if (f["availability"] != "in stock" or a.get("custom_label_0") in (LABEL_OUTLET, "unavailable")
                or int(f["price"]) < MIN_PRICE or t.get("category") not in CATEGORIES
                or any(w in f["title"].lower() for w in summer)):
            continue
        out.append({"id": pid, "title": t.get("title") or f["title"], "brand": a.get("brand", ""),
                    "category": t["category"], "price": int(f["price"])})
    return sorted(out, key=lambda x: (x["brand"], -x["price"]))


def high_price_ids() -> set[str]:
    """mc-supplement が custom_label_2 を付けるときに使う。"""
    return {x["id"] for x in high_price_items()}


def write_items(items: list[dict]) -> Path:
    with open(ITEMS_CSV, "w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=["id", "brand", "category", "price", "title"])
        w.writeheader()
        w.writerows({k: x[k] for k in w.fieldnames} for x in items)
    return ITEMS_CSV


def create_campaign(gclient, apply: bool = False) -> dict:
    items = high_price_items()
    by_brand: dict[str, int] = {}
    for x in items:
        by_brand[x["brand"]] = by_brand.get(x["brand"], 0) + 1
    existing = [(str(r.campaign.id), r.campaign.status.name) for r in gclient.search(
        f"SELECT campaign.id, campaign.status FROM campaign WHERE campaign.name = '{CAMPAIGN_NAME}' AND campaign.status != 'REMOVED'")]
    plan = {"apply": apply, "existing": existing, "campaign": CAMPAIGN_NAME,
            "bidding": f"クリック数の最大化（1クリック上限 {CPC_CEILING}円）", "daily_budget": DAILY_BUDGET,
            "priority": "高（PLA_v2 より優先）", "products": f"custom_label_2 = {LABEL}（{len(items)}点）",
            "by_brand": by_brand, "negatives": len(NEGATIVES), "items_csv": str(write_items(items))}
    if not apply or existing:
        return plan
    client, cid = gclient.client, gclient.customer_id
    op = client.get_type("CampaignBudgetOperation"); b = op.create
    b.name = f"{CAMPAIGN_NAME} budget"; b.amount_micros = DAILY_BUDGET * 1_000_000
    b.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    b.explicitly_shared = False
    budget_rn = client.get_service("CampaignBudgetService").mutate_campaign_budgets(
        customer_id=cid, operations=[op]).results[0].resource_name
    op = client.get_type("CampaignOperation"); c = op.create
    c.name = CAMPAIGN_NAME
    c.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SHOPPING
    c.status = client.enums.CampaignStatusEnum.ENABLED
    c.campaign_budget = budget_rn
    c.contains_eu_political_advertising = client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
    c.target_spend.cpc_bid_ceiling_micros = CPC_CEILING * 1_000_000
    c.shopping_setting.merchant_id = GOOGLE_MERCHANT_ID
    c.shopping_setting.feed_label = "JP"
    c.shopping_setting.campaign_priority = 2
    c.network_settings.target_google_search = True
    c.network_settings.target_search_network = False
    camp_rn = client.get_service("CampaignService").mutate_campaigns(customer_id=cid, operations=[op]).results[0].resource_name
    op = client.get_type("CampaignCriterionOperation"); cc = op.create
    cc.campaign = camp_rn; cc.location.geo_target_constant = GOOGLE_GEO_JP
    client.get_service("CampaignCriterionService").mutate_campaign_criteria(customer_id=cid, operations=[op])
    op = client.get_type("AdGroupOperation"); ag = op.create
    ag.name = "高価格冬物"; ag.campaign = camp_rn
    ag.type_ = client.enums.AdGroupTypeEnum.SHOPPING_PRODUCT_ADS
    ag.status = client.enums.AdGroupStatusEnum.ENABLED
    ag_rn = client.get_service("AdGroupService").mutate_ad_groups(customer_id=cid, operations=[op]).results[0].resource_name
    op = client.get_type("AdGroupAdOperation"); ad = op.create
    ad.ad_group = ag_rn; ad.status = client.enums.AdGroupAdStatusEnum.ENABLED
    ad.ad.shopping_product_ad._pb.SetInParent()
    client.get_service("AdGroupAdService").mutate_ad_group_ads(customer_id=cid, operations=[op])
    # 商品グループ: root → custom_label_2 = pla_high（出す）/ その他（除外）
    agcs = client.get_service("AdGroupCriterionService")
    lg, idx = client.enums.ListingGroupTypeEnum, client.enums.ProductCustomAttributeIndexEnum
    st = client.enums.AdGroupCriterionStatusEnum.ENABLED
    ag_id = ag_rn.split("/")[-1]
    ops = []
    op = client.get_type("AdGroupCriterionOperation"); r = op.create
    r.ad_group = ag_rn; r.status = st; r.resource_name = agcs.ad_group_criterion_path(cid, ag_id, -1)
    r.listing_group.type_ = lg.SUBDIVISION; ops.append(op); root_rn = r.resource_name
    op = client.get_type("AdGroupCriterionOperation"); u = op.create
    u.ad_group = ag_rn; u.status = st
    u.listing_group.type_ = lg.UNIT; u.listing_group.parent_ad_group_criterion = root_rn
    u.listing_group.case_value.product_custom_attribute.index = idx.INDEX2
    u.listing_group.case_value.product_custom_attribute.value = LABEL; ops.append(op)
    op = client.get_type("AdGroupCriterionOperation"); o = op.create
    o.ad_group = ag_rn; o.status = st; o.negative = True
    o.listing_group.type_ = lg.UNIT; o.listing_group.parent_ad_group_criterion = root_rn
    o.listing_group.case_value.product_custom_attribute.index = idx.INDEX2; ops.append(op)
    agcs.mutate_ad_group_criteria(customer_id=cid, operations=ops)
    new_id = camp_rn.split("/")[-1]
    plan.update(campaign_id=new_id, ad_group=ag_rn,
                negatives_added=pla_negatives(gclient, new_id, apply=True).get("added", 0))
    return plan

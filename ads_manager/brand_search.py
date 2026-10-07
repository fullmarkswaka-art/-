"""Google 指名検索キャンペーン（ブランド名で検索した人向け）を新設する。

既存の指名キャンペーン（例: 指名_ポック 20299964808）を雛形にして、地域・言語・除外キーワードをそのまま写し、
入札は「コンバージョン数の最大化」、ネットワークは Google 検索＋検索パートナー（ディスプレイは使わない）。
広告文は copy/<brand>_google_rsa.json（headlines / descriptions / path1 / path2）。

安全のため、キャンペーンは必ず PAUSED で作る。配信開始は確認後に `google set-status <id> ENABLED --apply`。

使い方（Python）:
    from ads_manager.brand_search import google_create_brand_search
    google_create_brand_search(gclient, name="UC_SK_1_指名_HESTRA", daily_budget_yen=1000,
        keywords=[("hestra", "PHRASE"), ("ヘストラ", "PHRASE")], rsa_json="copy/hestra_google_rsa.json",
        final_url="https://www.fullmarksstore.jp/category/HESTRA/?utm_source=google&utm_medium=cpc&utm_campaign=sk",
        apply=False)
"""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATE_CAMPAIGN_ID = "20299964808"  # 指名_ポック（地域・言語・除外キーワードの雛形）


def _template_criteria(gclient, template_id: str) -> dict:
    out = {"locations": [], "languages": [], "negatives": []}
    for r in gclient.search(
            "SELECT campaign_criterion.type, campaign_criterion.location.geo_target_constant, "
            "campaign_criterion.language.language_constant, campaign_criterion.negative, "
            "campaign_criterion.keyword.text, campaign_criterion.keyword.match_type "
            f"FROM campaign_criterion WHERE campaign.id = {template_id}"):
        c = r.campaign_criterion
        t = c.type_.name
        if t == "LOCATION" and not c.negative:
            out["locations"].append(c.location.geo_target_constant)
        elif t == "LANGUAGE":
            out["languages"].append(c.language.language_constant)
        elif t == "KEYWORD" and c.negative:
            out["negatives"].append((c.keyword.text, c.keyword.match_type.name))
    return out


def google_create_brand_search(gclient, name: str, daily_budget_yen: float, keywords: list[tuple[str, str]],
                               rsa_json: str, final_url: str, ad_group_name: str | None = None,
                               template_id: str = TEMPLATE_CAMPAIGN_ID, apply: bool = False) -> dict:
    rsa = json.loads(Path(rsa_json).read_text(encoding="utf-8"))
    tpl = _template_criteria(gclient, template_id)
    existing = [(r.campaign.id, r.campaign.status.name) for r in gclient.search(
        f"SELECT campaign.id, campaign.status FROM campaign WHERE campaign.name = '{name}' AND campaign.status != 'REMOVED'")]
    plan = {"apply": apply, "existing": existing,
            "campaign": {"name": name, "type": "SEARCH（Google 検索＋検索パートナー）", "status": "PAUSED で作成",
                         "bidding": "コンバージョン数の最大化", "daily_budget": daily_budget_yen},
            "copied_from_template": {"template": template_id, "locations": len(tpl["locations"]),
                                     "languages": tpl["languages"], "negative_keywords": len(tpl["negatives"])},
            "ad_group": ad_group_name or f"{name}_指名", "keywords": keywords,
            "ad": {"final_url": final_url, "headlines": rsa["headlines"], "descriptions": rsa["descriptions"],
                   "path1": rsa.get("path1", ""), "path2": rsa.get("path2", "")}}
    if not apply or existing:
        return plan

    client, cid = gclient.client, gclient.customer_id
    # 1) 予算（共有しない）
    bs = client.get_service("CampaignBudgetService")
    op = client.get_type("CampaignBudgetOperation"); b = op.create
    b.name = f"{name} budget"; b.amount_micros = int(daily_budget_yen * 1_000_000)
    b.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    b.explicitly_shared = False
    budget_rn = bs.mutate_campaign_budgets(customer_id=cid, operations=[op]).results[0].resource_name
    # 2) キャンペーン（PAUSED）
    cs = client.get_service("CampaignService")
    op = client.get_type("CampaignOperation"); c = op.create
    c.name = name
    c.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH
    c.status = client.enums.CampaignStatusEnum.PAUSED
    c.campaign_budget = budget_rn
    c.contains_eu_political_advertising = client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
    client.copy_from(c.maximize_conversions, client.get_type("MaximizeConversions"))
    c.network_settings.target_google_search = True
    c.network_settings.target_search_network = True
    c.network_settings.target_content_network = False
    c.network_settings.target_partner_search_network = False
    c.geo_target_type_setting.positive_geo_target_type = client.enums.PositiveGeoTargetTypeEnum.PRESENCE
    camp_rn = cs.mutate_campaigns(customer_id=cid, operations=[op]).results[0].resource_name
    plan["created"] = {"campaign": camp_rn, "budget": budget_rn}
    # 3) 地域・言語・除外キーワード（雛形からコピー）
    ccs = client.get_service("CampaignCriterionService")
    ops = []
    for g in tpl["locations"]:
        op = client.get_type("CampaignCriterionOperation"); cc = op.create
        cc.campaign = camp_rn; cc.location.geo_target_constant = g; ops.append(op)
    for lang in tpl["languages"]:
        op = client.get_type("CampaignCriterionOperation"); cc = op.create
        cc.campaign = camp_rn; cc.language.language_constant = lang; ops.append(op)
    for text, mt in tpl["negatives"]:
        op = client.get_type("CampaignCriterionOperation"); cc = op.create
        cc.campaign = camp_rn; cc.negative = True
        cc.keyword.text = text; cc.keyword.match_type = client.enums.KeywordMatchTypeEnum[mt]; ops.append(op)
    for i in range(0, len(ops), 1000):
        ccs.mutate_campaign_criteria(customer_id=cid, operations=ops[i:i + 1000])
    # 4) 広告グループ
    ags = client.get_service("AdGroupService")
    op = client.get_type("AdGroupOperation"); ag = op.create
    ag.name = plan["ad_group"]; ag.campaign = camp_rn
    ag.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
    ag.status = client.enums.AdGroupStatusEnum.ENABLED
    ag_rn = ags.mutate_ad_groups(customer_id=cid, operations=[op]).results[0].resource_name
    plan["created"]["ad_group"] = ag_rn
    # 5) キーワード
    agcs = client.get_service("AdGroupCriterionService")
    ops = []
    for text, mt in keywords:
        op = client.get_type("AdGroupCriterionOperation"); k = op.create
        k.ad_group = ag_rn; k.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        k.keyword.text = text; k.keyword.match_type = client.enums.KeywordMatchTypeEnum[mt]; ops.append(op)
    agcs.mutate_ad_group_criteria(customer_id=cid, operations=ops)
    # 6) レスポンシブ検索広告
    agas = client.get_service("AdGroupAdService")
    op = client.get_type("AdGroupAdOperation"); ada = op.create
    ada.ad_group = ag_rn; ada.status = client.enums.AdGroupAdStatusEnum.ENABLED
    ada.ad.final_urls.append(final_url)
    for h in rsa["headlines"]:
        a = client.get_type("AdTextAsset"); a.text = h; ada.ad.responsive_search_ad.headlines.append(a)
    for d in rsa["descriptions"]:
        a = client.get_type("AdTextAsset"); a.text = d; ada.ad.responsive_search_ad.descriptions.append(a)
    if rsa.get("path1"):
        ada.ad.responsive_search_ad.path1 = rsa["path1"]
    if rsa.get("path2"):
        ada.ad.responsive_search_ad.path2 = rsa["path2"]
    plan["created"]["ad"] = agas.mutate_ad_group_ads(customer_id=cid, operations=[op]).results[0].resource_name
    return plan

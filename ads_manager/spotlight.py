# -*- coding: utf-8 -*-
"""1商品を集中的に見せる施策（2026-10 Tech Insulation Houdi）。設定は copy/houdini_techins.json。

  meta_carousel()          … 専用 CBO キャンペーン＋全員向け広告セット（インスタ限定の配置）＋カルーセル広告。
                             予算の振替元（offset_budget）の日予算も下げる
  google_sitelink_test()   … Google 広告の「テスト」機能で指名検索キャンペーンを 50/50 に分け、
                             テスト側にだけサイトリンクを付ける（予算は元キャンペーンを分け合う＝追加費用なし）
どちらも apply=False では計画の表示だけ。
"""
from __future__ import annotations

import json
from pathlib import Path

from .creative_swap import upload
from .event_ads import PIXEL_ID
from .meta_ads import MetaAdsClient
from .outlet_rtg import IG_USER_ID, PAGE_ID


def _with_utm(url: str, utm: str) -> str:
    return url + ("&" if "?" in url else "?") + utm


def meta_carousel(client: MetaAdsClient, conf_path: str, apply: bool = False) -> dict:
    conf_path = Path(conf_path)
    conf = json.loads(conf_path.read_text(encoding="utf-8"))
    m, name = conf["meta"], conf["name"]
    img_dir = Path("copy/creatives") / name.lower()
    end_time = f"{conf['end_date']}T23:50:00+0900"
    off = m["offset_budget"]
    cur = client.get(off["id"], fields="name,daily_budget")
    plan = {"apply": apply, "campaign": f"UC_DN_3_CVS_{name}", "daily_budget": m["daily_budget"], "end_time": end_time,
            "adset": f"UCDN3_CVS_{name}_全員_IG", "placements": ["instagram:" + p for p in m["instagram_positions"]],
            "message": m["message"], "cards": [(c["name"], c["description"], c["link"]) for c in m["cards"]],
            "offset": f"{cur['name']} {cur.get('daily_budget')} → {off['to']}"}
    for c in m["cards"]:
        if not (img_dir / c["image"]).exists():
            raise FileNotFoundError(img_dir / c["image"])
    if not apply:
        return plan
    acct = client.config.ad_account_id
    children = []
    for c in m["cards"]:
        link = _with_utm(c["link"], m["utm"])
        children.append({"link": link, "image_hash": upload(client, img_dir / c["image"]), "name": c["name"],
                         "description": c["description"],
                         "call_to_action": {"type": "SHOP_NOW", "value": {"link": link}}})
    spec = {"page_id": PAGE_ID, "instagram_user_id": IG_USER_ID,
            "link_data": {"link": _with_utm(m["link"], m["utm"]), "message": m["message"],
                          "child_attachments": children, "multi_share_optimized": False,
                          "multi_share_end_card": False, "call_to_action": {"type": "SHOP_NOW"}}}
    cr = client.post(f"{acct}/adcreatives", name=f"{name.lower()}_carousel",
                     object_story_spec=json.dumps(spec, ensure_ascii=False))["id"]
    camp = client.post(f"{acct}/campaigns", name=plan["campaign"], objective="OUTCOME_SALES", status="ACTIVE",
                       special_ad_categories="[]", daily_budget=str(m["daily_budget"]),
                       bid_strategy="LOWEST_COST_WITHOUT_CAP", stop_time=end_time)
    t = client.get(m["template_adset"], fields="targeting")["targeting"]
    for k in ("custom_audiences", "excluded_custom_audiences", "facebook_positions", "messenger_positions",
              "audience_network_positions", "device_platforms"):
        t.pop(k, None)
    t["publisher_platforms"] = ["instagram"]
    t["instagram_positions"] = m["instagram_positions"]
    adset = client.post(f"{acct}/adsets", name=plan["adset"], campaign_id=camp["id"], status="ACTIVE",
                        billing_event="IMPRESSIONS", optimization_goal="OFFSITE_CONVERSIONS",
                        promoted_object=json.dumps({"pixel_id": PIXEL_ID, "custom_event_type": "PURCHASE"}),
                        targeting=json.dumps(t, ensure_ascii=False), end_time=end_time,
                        attribution_spec=json.dumps([{"event_type": "CLICK_THROUGH", "window_days": 7},
                                                     {"event_type": "VIEW_THROUGH", "window_days": 1}]))
    ad = client.post(f"{acct}/ads", name=f"{name.lower()}_carousel", adset_id=adset["id"],
                     creative=json.dumps({"creative_id": cr}), status="ACTIVE")
    client.post(off["id"], daily_budget=str(off["to"]))
    m.update(campaign_id=camp["id"], adset_id=adset["id"], creative_id=cr, ad_id=ad["id"])
    conf_path.write_text(json.dumps(conf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plan.update(campaign_id=camp["id"], adset_id=adset["id"], creative_id=cr, ad_id=ad["id"])
    return plan


def google_sitelink_test(gclient, conf_path: str, apply: bool = False) -> dict:
    conf_path = Path(conf_path)
    conf = json.loads(conf_path.read_text(encoding="utf-8"))
    g = conf["google"]
    rows = gclient.search("SELECT campaign.id, campaign.name, campaign.status FROM campaign "
                          f"WHERE campaign.name = '{g['campaign_name']}' AND campaign.status = 'ENABLED'")
    if len(rows) != 1:
        raise RuntimeError(f"キャンペーンが特定できません: {g['campaign_name']} ({len(rows)}件)")
    cid = str(rows[0].campaign.id)
    plan = {"apply": apply, "campaign": f"{g['campaign_name']} ({cid})", "split": "50/50",
            "period": f"{g['start_date']}〜{g['end_date']}", "sitelink_on_treatment_only": g["sitelink"]}
    if not apply:
        return plan
    client, cust = gclient.client, gclient.customer_id
    # 1) テスト（実験）を作る
    eop = client.get_type("ExperimentOperation")
    e = eop.create
    e.name = g["experiment_name"]
    e.type_ = client.enums.ExperimentTypeEnum.SEARCH_CUSTOM
    e.suffix = g["suffix"]
    e.status = client.enums.ExperimentStatusEnum.SETUP
    e.start_date = g["start_date"]
    e.end_date = g["end_date"]
    exp_rn = client.get_service("ExperimentService").mutate_experiments(
        customer_id=cust, operations=[eop]).results[0].resource_name
    # 2) 元（control）とテスト側（treatment）を 50/50 で作る
    camp_rn = client.get_service("CampaignService").campaign_path(cust, cid)
    ops = []
    for is_control, arm_name in ((True, "control"), (False, "treatment")):
        op = client.get_type("ExperimentArmOperation")
        a = op.create
        a.experiment = exp_rn
        a.name = arm_name
        a.control = is_control
        a.traffic_split = 50
        if is_control:
            a.campaigns.append(camp_rn)
        ops.append(op)
    req = client.get_type("MutateExperimentArmsRequest")
    req.customer_id = cust
    req.operations.extend(ops)
    req.response_content_type = client.enums.ResponseContentTypeEnum.MUTABLE_RESOURCE
    res = client.get_service("ExperimentArmService").mutate_experiment_arms(request=req)
    treat = [r.experiment_arm for r in res.results if not r.experiment_arm.control][0]
    draft_rn = treat.in_design_campaigns[0]
    # 3) サイトリンクを作り、テスト側のキャンペーンにだけ付ける
    s = g["sitelink"]
    aop = client.get_type("AssetOperation")
    asset = aop.create
    asset.name = f"sitelink_{s['link_text']}_{g['start_date']}"
    asset.final_urls.append(s["final_url"])
    asset.sitelink_asset.link_text = s["link_text"]
    asset.sitelink_asset.description1 = s["description1"]
    asset.sitelink_asset.description2 = s["description2"]
    asset_rn = client.get_service("AssetService").mutate_assets(customer_id=cust, operations=[aop]).results[0].resource_name
    cop = client.get_type("CampaignAssetOperation")
    ca = cop.create
    ca.campaign = draft_rn
    ca.asset = asset_rn
    ca.field_type = client.enums.AssetFieldTypeEnum.SITELINK
    client.get_service("CampaignAssetService").mutate_campaign_assets(customer_id=cust, operations=[cop])
    # 4) 開始を予約（開始日から配信）
    client.get_service("ExperimentService").schedule_experiment(resource_name=exp_rn)
    g.update(campaign_id=cid, experiment=exp_rn, treatment_campaign=draft_rn, sitelink_asset=asset_rn)
    conf_path.write_text(json.dumps(conf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plan.update(experiment=exp_rn, treatment_campaign=draft_rn, sitelink_asset=asset_rn)
    return plan

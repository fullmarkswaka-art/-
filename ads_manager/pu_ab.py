# -*- coding: utf-8 -*-
"""Permanent Union シェルの画像 A/B テスト（2026-10）。設定は copy/pu_shell_ab.json。

1キャンペーンに A・B の広告セット（各自の日予算、全員向け Advantage+、インスタのフィード系配置のみ）を作り、
Meta の A/B テスト（ad_studies, SPLIT_TEST）で見る人を 50/50 に分ける。apply=False では計画の表示だけ。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .creative_swap import upload
from .event_ads import PIXEL_ID
from .meta_ads import MetaAdsClient
from .outlet_rtg import IG_USER_ID, PAGE_ID

JST = timezone(timedelta(hours=9))


def launch(client: MetaAdsClient, conf_path: str, apply: bool = False) -> dict:
    conf_path = Path(conf_path)
    conf = json.loads(conf_path.read_text(encoding="utf-8"))
    img_dir = Path("copy/creatives") / conf["name"].lower()
    end_time = f"{conf['end_date']}T23:50:00+0900"
    link = conf["link"] + ("&" if "?" in conf["link"] else "?") + conf["utm"]
    plan = {"apply": apply, "campaign": f"UC_DN_3_CVS_{conf['name']}", "end_time": end_time, "link": link,
            "headline": conf["headline"], "message": conf["message"],
            "placements": ["instagram:" + p for p in conf["instagram_positions"]],
            "cells": [(c["label"], c["image"], c["daily_budget"]) for c in conf["cells"]]}
    for c in conf["cells"]:
        if not (img_dir / c["image"]).exists():
            raise FileNotFoundError(img_dir / c["image"])
    if not apply:
        return plan
    acct = client.config.ad_account_id
    camp = client.post(f"{acct}/campaigns", name=plan["campaign"], objective="OUTCOME_SALES", status="ACTIVE",
                       special_ad_categories="[]", is_adset_budget_sharing_enabled="false", stop_time=end_time)
    t = client.get(conf["template_adset"], fields="targeting")["targeting"]
    for k in ("custom_audiences", "excluded_custom_audiences", "facebook_positions", "messenger_positions",
              "audience_network_positions", "device_platforms"):
        t.pop(k, None)
    t["publisher_platforms"] = ["instagram"]
    t["instagram_positions"] = conf["instagram_positions"]
    for c in conf["cells"]:
        h = upload(client, img_dir / c["image"])
        spec = {"page_id": PAGE_ID, "instagram_user_id": IG_USER_ID,
                "link_data": {"link": link, "message": conf["message"], "name": conf["headline"], "image_hash": h,
                              "call_to_action": {"type": "SHOP_NOW", "value": {"link": link}}}}
        cr = client.post(f"{acct}/adcreatives", name=f"pu_shell_{c['key']}",
                         object_story_spec=json.dumps(spec, ensure_ascii=False))["id"]
        adset = client.post(f"{acct}/adsets", name=f"UCDN3_{conf['name']}_{c['label']}", campaign_id=camp["id"],
                            status="ACTIVE", daily_budget=str(c["daily_budget"]), bid_strategy="LOWEST_COST_WITHOUT_CAP",
                            billing_event="IMPRESSIONS", optimization_goal="OFFSITE_CONVERSIONS",
                            promoted_object=json.dumps({"pixel_id": PIXEL_ID, "custom_event_type": "PURCHASE"}),
                            targeting=json.dumps(t, ensure_ascii=False), end_time=end_time,
                            attribution_spec=json.dumps([{"event_type": "CLICK_THROUGH", "window_days": 7},
                                                         {"event_type": "VIEW_THROUGH", "window_days": 1}]))
        ad = client.post(f"{acct}/ads", name=f"pu_shell_{c['key']}", adset_id=adset["id"],
                         creative=json.dumps({"creative_id": cr}), status="ACTIVE")
        c.update(creative_id=cr, adset_id=adset["id"], ad_id=ad["id"])
    conf["campaign_id"] = camp["id"]
    conf_path.write_text(json.dumps(conf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    start = max(datetime.now(JST) + timedelta(minutes=10),
                datetime.fromisoformat(conf["start_date"]).replace(tzinfo=JST))
    end = datetime.fromisoformat(end_time)
    try:
        study = client.post(f"{conf['business_id']}/ad_studies", name=f"PU shell A/B {conf['start_date']}", type="SPLIT_TEST",
                            start_time=str(int(start.timestamp())), end_time=str(int(end.timestamp())),
                            cells=json.dumps([{"name": c["label"], "treatment_percentage": 50, "adsets": [c["adset_id"]]}
                                              for c in conf["cells"]], ensure_ascii=False))
        conf["ad_study_id"] = study["id"]
    except Exception as e:  # A/B の割り当てに失敗しても広告セットは動く（重なりのある簡易比較になる）
        conf["ad_study_error"] = str(e)[:300]
    conf_path.write_text(json.dumps(conf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plan.update(campaign_id=camp["id"], cells=conf["cells"], ad_study=conf.get("ad_study_id") or conf.get("ad_study_error"))
    return plan

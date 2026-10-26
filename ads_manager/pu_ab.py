# -*- coding: utf-8 -*-
"""Permanent Union シェルの A/B テスト（2026-10）。設定は copy/pu_shell_ab.json。

1キャンペーン（広告セット予算）に2つの広告セットを作り、Meta の A/B テスト（ad_studies, SPLIT_TEST）で見る人を 50/50 に分ける。
  A: 3枚を順番に見せるカルーセル（「あ、」→「冬がくる」→「FW Collection」、正方形）
  B: 1枚の写真広告3本（それぞれ 1:1 / 4:5 / 9:16 を配置ごとに出し分け）
配信先は全員向け（Advantage+、除外なし）、インスタのみ。apply=False では計画の表示だけ。
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
IG_STORY = {"publisher_platforms": ["instagram"], "instagram_positions": ["story", "reels"]}
IG_FEED = {"publisher_platforms": ["instagram"], "instagram_positions": ["stream", "explore_home", "profile_feed"]}


def _placement_creative(client, name, hashes, message, headline, link):
    spec = {
        "images": [{"hash": hashes[k], "adlabels": [{"name": k}]} for k in ("1x1", "4x5", "9x16")],
        "bodies": [{"text": message}], "titles": [{"text": headline}],
        "link_urls": [{"website_url": link}], "call_to_action_types": ["SHOP_NOW"],
        "ad_formats": ["SINGLE_IMAGE"], "optimization_type": "PLACEMENT",
        "asset_customization_rules": [
            {"customization_spec": IG_STORY, "image_label": {"name": "9x16"}, "priority": 1},
            {"customization_spec": IG_FEED, "image_label": {"name": "4x5"}, "priority": 2},
            {"customization_spec": {"publisher_platforms": ["instagram"]}, "image_label": {"name": "1x1"}, "priority": 3},
        ],
    }
    return client.post(f"{client.config.ad_account_id}/adcreatives", name=name,
                       object_story_spec=json.dumps({"page_id": PAGE_ID, "instagram_user_id": IG_USER_ID}),
                       asset_feed_spec=json.dumps(spec, ensure_ascii=False))["id"]


def _carousel_creative(client, name, hashes1x1, message, headline, link):
    cards = [{"link": link, "image_hash": h, "name": headline,
              "call_to_action": {"type": "SHOP_NOW", "value": {"link": link}}} for h in hashes1x1]
    spec = {"page_id": PAGE_ID, "instagram_user_id": IG_USER_ID,
            "link_data": {"link": link, "message": message, "child_attachments": cards,
                          "multi_share_optimized": False, "multi_share_end_card": False,
                          "call_to_action": {"type": "SHOP_NOW"}}}
    return client.post(f"{client.config.ad_account_id}/adcreatives", name=name,
                       object_story_spec=json.dumps(spec, ensure_ascii=False))["id"]


def launch(client: MetaAdsClient, conf_path: str, apply: bool = False) -> dict:
    conf_path = Path(conf_path)
    conf = json.loads(conf_path.read_text(encoding="utf-8"))
    img_dir = Path("copy/creatives") / conf["name"].lower()
    end_time = f"{conf['end_date']}T23:50:00+0900"
    link = conf["link"] + ("&" if "?" in conf["link"] else "?") + conf["utm"]
    files = {img: {lab: img_dir / f"{img}_{lab}.jpg" for lab in ("1x1", "4x5", "9x16")} for img in conf["images"]}
    for d in files.values():
        for p in d.values():
            if not p.exists():
                raise FileNotFoundError(p)
    plan = {"apply": apply, "campaign": f"UC_DN_3_CVS_{conf['name']}", "end_time": end_time, "link": link,
            "headline": conf["headline"], "message": conf["message"],
            "placements": ["instagram:" + p for p in conf["instagram_positions"]],
            "cells": [(c["label"], c["type"], c["daily_budget"]) for c in conf["cells"]], "images": conf["images"]}
    if not apply:
        return plan
    acct = client.config.ad_account_id
    hashes = {img: {lab: upload(client, p) for lab, p in d.items()} for img, d in files.items()}
    camp = client.post(f"{acct}/campaigns", name=plan["campaign"], objective="OUTCOME_SALES", status="ACTIVE",
                       special_ad_categories="[]", is_adset_budget_sharing_enabled="false", stop_time=end_time)
    conf["campaign_id"] = camp["id"]
    t = client.get(conf["template_adset"], fields="targeting")["targeting"]
    for k in ("custom_audiences", "excluded_custom_audiences", "facebook_positions", "messenger_positions",
              "audience_network_positions", "device_platforms"):
        t.pop(k, None)
    t["publisher_platforms"] = ["instagram"]
    t["instagram_positions"] = conf["instagram_positions"]
    for c in conf["cells"]:
        adset = client.post(f"{acct}/adsets", name=f"UCDN3_{conf['name']}_{c['label']}", campaign_id=camp["id"],
                            status="ACTIVE", daily_budget=str(c["daily_budget"]), bid_strategy="LOWEST_COST_WITHOUT_CAP",
                            billing_event="IMPRESSIONS", optimization_goal="OFFSITE_CONVERSIONS",
                            promoted_object=json.dumps({"pixel_id": PIXEL_ID, "custom_event_type": "PURCHASE"}),
                            targeting=json.dumps(t, ensure_ascii=False), end_time=end_time,
                            attribution_spec=json.dumps([{"event_type": "CLICK_THROUGH", "window_days": 7},
                                                         {"event_type": "VIEW_THROUGH", "window_days": 1}]))
        c["adset_id"] = adset["id"]
        c["ad_ids"] = []
        if c["type"] == "carousel":
            cr = _carousel_creative(client, "pu_shell_carousel", [hashes[i]["1x1"] for i in conf["images"]],
                                    conf["message"], conf["headline"], link)
            ad = client.post(f"{acct}/ads", name="pu_shell_carousel", adset_id=adset["id"],
                             creative=json.dumps({"creative_id": cr}), status="ACTIVE")
            c["ad_ids"].append(ad["id"])
        else:
            for img in conf["images"]:
                cr = _placement_creative(client, img, hashes[img], conf["message"], conf["headline"], link)
                ad = client.post(f"{acct}/ads", name=img, adset_id=adset["id"],
                                 creative=json.dumps({"creative_id": cr}), status="ACTIVE")
                c["ad_ids"].append(ad["id"])
        conf_path.write_text(json.dumps(conf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    start = datetime.now(JST) + timedelta(minutes=10)
    end = datetime.fromisoformat(end_time)
    try:
        study = client.post(f"{conf['business_id']}/ad_studies", name=f"PU shell A/B {conf['start_date']}", type="SPLIT_TEST",
                            start_time=str(int(start.timestamp())), end_time=str(int(end.timestamp())),
                            cells=json.dumps([{"name": c["label"], "treatment_percentage": 50, "adsets": [c["adset_id"]]}
                                              for c in conf["cells"]], ensure_ascii=False))
        conf["ad_study_id"] = study["id"]
    except Exception as e:  # A/B の割り当てに失敗しても広告セットは動く（見る人が一部重なる簡易比較になる）
        conf["ad_study_error"] = str(e)[:300]
    conf_path.write_text(json.dumps(conf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plan.update(campaign_id=camp["id"], cells=conf["cells"], ad_study=conf.get("ad_study_id") or conf.get("ad_study_error"))
    return plan

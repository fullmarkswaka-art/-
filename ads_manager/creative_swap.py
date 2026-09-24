# -*- coding: utf-8 -*-
"""静止画広告の画像を差し替える。1:1 / 4:5 / 9:16 の3サイズを配置ごとに出し分ける（配置別アセットカスタマイズ）。

- フィード（Facebook / Instagram）: 4:5（1080×1350）
- ストーリーズ・リール: 9:16（1080×1920）
- その他の配置: 1:1（1080×1080）

新しい広告を同じ広告セットに作り、旧広告は停止する（旧広告の実績は残る）。
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from .meta_ads import MetaAdsClient
from .outlet_rtg import IG_USER_ID, PAGE_ID

SIZES = {"1x1": (1080, 1080), "4x5": (1080, 1350), "9x16": (1080, 1920)}
FEED = {"publisher_platforms": ["facebook", "instagram"],
        "facebook_positions": ["feed", "video_feeds", "marketplace"],
        "instagram_positions": ["stream", "explore", "explore_home", "profile_feed"]}
STORY = {"publisher_platforms": ["facebook", "instagram"],
         "facebook_positions": ["story", "facebook_reels"],
         "instagram_positions": ["story", "reels"]}


def prepare_image(src: str | Path, size: tuple[int, int], out: str | Path) -> Path:
    """書き出しサイズ（例 2251×2813）を広告の正式サイズに縮小して JPG 保存する。縦横比は変えない（中央で合わせる）。"""
    im = Image.open(src).convert("RGB")
    tw, th = size
    r = max(tw / im.width, th / im.height)
    im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    left, top = (im.width - tw) // 2, (im.height - th) // 2
    im = im.crop((left, top, left + tw, top + th))
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=92, optimize=True)
    return out


def upload(client: MetaAdsClient, path: str | Path) -> str:
    r = client.post_file(f"{client.config.ad_account_id}/adimages", str(path))
    return list(r["images"].values())[0]["hash"]


def create_placement_creative(client: MetaAdsClient, name: str, hashes: dict[str, str], message: str,
                              headline: str, link: str) -> str:
    """hashes = {"1x1": h, "4x5": h, "9x16": h}。配置ごとに画像を出し分けるクリエイティブを作る。"""
    spec = {
        "images": [{"hash": hashes[k], "adlabels": [{"name": k}]} for k in ("1x1", "4x5", "9x16")],
        "bodies": [{"text": message}],
        "titles": [{"text": headline}],
        "link_urls": [{"website_url": link}],
        "call_to_action_types": ["SHOP_NOW"],
        "ad_formats": ["SINGLE_IMAGE"],
        "optimization_type": "PLACEMENT",
        "asset_customization_rules": [
            {"customization_spec": STORY, "image_label": {"name": "9x16"}, "priority": 1},
            {"customization_spec": FEED, "image_label": {"name": "4x5"}, "priority": 2},
            {"customization_spec": {"publisher_platforms": ["facebook", "instagram", "audience_network", "messenger"]},
             "image_label": {"name": "1x1"}, "priority": 3},
        ],
    }
    r = client.post(f"{client.config.ad_account_id}/adcreatives", name=name,
                    object_story_spec=json.dumps({"page_id": PAGE_ID, "instagram_user_id": IG_USER_ID}),
                    asset_feed_spec=json.dumps(spec, ensure_ascii=False))
    return r["id"]


def swap_ads(client: MetaAdsClient, adset_id: str, old_ad_ids: list[str], new_ads: list[dict],
             apply: bool = False) -> dict:
    """new_ads = [{"name":..., "creative_id":...}]。同じ広告セットに新しい広告を作り、旧広告を停止する。"""
    plan = {"apply": apply, "adset_id": adset_id, "pause": old_ad_ids, "create": new_ads}
    if not apply:
        return plan
    acct = client.config.ad_account_id
    for a in new_ads:
        r = client.post(f"{acct}/ads", name=a["name"], adset_id=adset_id,
                        creative=json.dumps({"creative_id": a["creative_id"]}), status="ACTIVE")
        a["ad_id"] = r["id"]
    for oid in old_ad_ids:
        client.set_status(oid, "PAUSED")
    return plan

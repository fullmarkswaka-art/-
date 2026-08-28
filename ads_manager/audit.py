"""Meta広告の棚卸し（監査）。

配信中の広告を全件取得してリンク先URLを抽出し、
「過去商品の広告が配信され続けていないか」を調べるレポートを作る。

分類の観点:
  - リンク切れ (4xx/5xx) やトップページへのリダイレクト → 商品ページが消えた過去商品
  - creative に product_set_id がある → カタログ（商品フィード）起因。
    フィードから商品を消さない限り配信され続ける
  - ACTIVE のままの広告 → 終売時の停止漏れ
"""
from __future__ import annotations

from urllib.parse import urlparse

import requests

from .meta_ads import MetaAdsClient

AD_FIELDS = (
    "id,name,created_time,updated_time,effective_status,"
    "campaign{id,name,objective,effective_status},"
    "adset{id,name,effective_status},"
    "creative{id,product_set_id,object_story_spec,asset_feed_spec}"
)


def fetch_all_ads(client: MetaAdsClient) -> list[dict]:
    """ページングを辿って広告アカウントの全広告を取得する。"""
    ads: list[dict] = []
    body = client.get(f"{client.config.ad_account_id}/ads",
                      fields=AD_FIELDS, limit=100)
    while True:
        ads.extend(body.get("data", []))
        after = body.get("paging", {}).get("cursors", {}).get("after")
        if not after or "next" not in body.get("paging", {}):
            return ads
        body = client.get(f"{client.config.ad_account_id}/ads",
                          fields=AD_FIELDS, limit=100, after=after)


def extract_links(creative: dict) -> list[str]:
    """クリエイティブから遷移先URLをすべて抜き出す。"""
    links: list[str] = []
    spec = creative.get("object_story_spec") or {}
    link_data = spec.get("link_data") or {}
    if link_data.get("link"):
        links.append(link_data["link"])
    for child in link_data.get("child_attachments") or []:
        if child.get("link"):
            links.append(child["link"])
    video_data = spec.get("video_data") or {}
    cta_value = (video_data.get("call_to_action") or {}).get("value") or {}
    if cta_value.get("link"):
        links.append(cta_value["link"])
    feed = creative.get("asset_feed_spec") or {}
    for url in feed.get("link_urls") or []:
        if url.get("website_url"):
            links.append(url["website_url"])
    # 重複を除いて順序維持
    return list(dict.fromkeys(links))


def check_url(url: str) -> dict:
    """URLの生死を確認する。{status, final_url, note} を返す。"""
    try:
        resp = requests.head(url, allow_redirects=True, timeout=10)
        if resp.status_code in (405, 501):
            resp = requests.get(url, allow_redirects=True, timeout=10, stream=True)
        note = ""
        orig_path = urlparse(url).path.rstrip("/")
        final_path = urlparse(resp.url).path.rstrip("/")
        if resp.status_code < 400 and orig_path and not final_path:
            note = "トップページへリダイレクト（商品ページ消滅の可能性）"
        return {"status": resp.status_code, "final_url": resp.url, "note": note}
    except requests.RequestException as e:
        return {"status": None, "final_url": None,
                "note": f"接続エラー: {type(e).__name__}"}


def meta_audit(client: MetaAdsClient, include_paused: bool = False,
               check_links: bool = True) -> dict:
    """広告を棚卸しし、問題のある広告と原因分類を含むレポートを返す。"""
    ads = fetch_all_ads(client)
    url_cache: dict[str, dict] = {}
    rows: list[dict] = []
    for ad in ads:
        delivering = ad.get("effective_status") == "ACTIVE"
        if not delivering and not include_paused:
            continue
        creative = ad.get("creative") or {}
        links = extract_links(creative)
        is_catalog = bool(creative.get("product_set_id"))
        link_results = []
        if check_links:
            for url in links:
                if url not in url_cache:
                    url_cache[url] = check_url(url)
                link_results.append({"url": url, **url_cache[url]})

        flags = []
        if is_catalog:
            flags.append("カタログ広告: 商品フィードに残っている限り配信される")
        for r in link_results:
            if r["status"] is not None and r["status"] >= 400:
                flags.append(f"リンク切れ ({r['status']}): {r['url']}")
            elif r["note"].startswith("トップページ"):
                flags.append(f"{r['note']}: {r['url']}")
        if flags and delivering and not is_catalog:
            flags.append("終売後も広告が停止されていない（停止漏れ）")

        rows.append({
            "ad_id": ad["id"],
            "ad_name": ad.get("name"),
            "delivery": ad.get("effective_status"),
            "campaign": (ad.get("campaign") or {}).get("name"),
            "objective": (ad.get("campaign") or {}).get("objective"),
            "created_time": ad.get("created_time"),
            "links": links,
            "link_results": link_results,
            "flags": flags,
        })

    problems = [r for r in rows if r["flags"]]
    return {
        "summary": {
            "総広告数": len(ads),
            "調査対象": len(rows),
            "問題あり": len(problems),
            "リンク未確認": not check_links,
        },
        "問題のある広告": problems,
        "その他の広告": [r for r in rows if not r["flags"]],
    }

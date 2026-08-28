"""サイト (fullmarksstore.jp) の全商品を Meta カタログへ同期する。

流れ:
  1. item_list.html をページングして全商品URLを列挙
  2. 各商品ページの JSON-LD (schema.org/Product) から
     商品名・説明・画像・価格・在庫状態を取得
  3. items_batch でカタログへ UPSERT（retailer_id = 品番）
  4. サイトに存在しないカタログ内商品は「在庫なし + 非公開」へ

これを定期実行すればカタログは常にサイトと同じ状態に保たれる。
削除は行わないので、誤検出時は published に戻すだけで復旧できる。
"""
from __future__ import annotations

import html as html_mod
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

import requests

from .meta_ads import MetaAdsClient

SITE_BASE = "https://www.fullmarksstore.jp"
LIST_URL = SITE_BASE + "/item_list.html"
ITEM_RE = re.compile(r"/item/(\d+)\.html")
LDJSON_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S)
TAG_RE = re.compile(r"<[^>]+>")
MAX_PAGES = 100
HEADERS = {"User-Agent": "fullmarks-catalog-sync/1.0"}


def list_site_products() -> list[str]:
    """商品一覧をページングして全商品URLを収集する。"""
    seen: dict[str, None] = {}
    for page in range(1, MAX_PAGES + 1):
        url = LIST_URL if page == 1 else \
            f"{LIST_URL}?request=page&next_page={page}"
        resp = requests.get(url, timeout=30, headers=HEADERS)
        resp.raise_for_status()
        found_new = False
        for m in ITEM_RE.finditer(resp.text):
            item_url = f"{SITE_BASE}/item/{m.group(1)}.html"
            if item_url not in seen:
                seen[item_url] = None
                found_new = True
        if not found_new:
            break
        time.sleep(0.3)
    return list(seen)


def _parse_availability(value: str) -> str:
    v = (value or "").rsplit("/", 1)[-1].lower()
    if v == "instock":
        return "in stock"
    if v in ("preorder", "presale"):
        return "available for order"
    return "out of stock"


def scrape_product(url: str) -> dict | None:
    """商品ページの JSON-LD からカタログ用の商品データを組み立てる。"""
    try:
        resp = requests.get(url, timeout=30, headers=HEADERS)
        if resp.status_code != 200:
            return None
    except requests.RequestException:
        return None
    product = None
    for m in LDJSON_RE.finditer(resp.text):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            product = data
            break
    if not product:
        return None

    offers = product.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = offers.get("price") or offers.get("lowPrice")
    currency = offers.get("priceCurrency") or "JPY"
    images = product.get("image") or []
    if isinstance(images, str):
        images = [images]
    if not price or not images:
        return None  # 価格・画像はカタログ必須項目

    description = TAG_RE.sub(" ", product.get("description") or "")
    description = html_mod.unescape(re.sub(r"\s+", " ", description)).strip()
    retailer_id = ITEM_RE.search(url).group(1)
    return {
        "id": retailer_id,
        "title": (product.get("name") or "").strip()[:200],
        "description": (description or product.get("name") or "")[:5000],
        "link": urljoin(url, offers.get("url") or url),
        "image_link": images[0],
        "additional_image_link": images[1:11] or None,
        "price": f"{price} {currency}",
        "availability": _parse_availability(offers.get("availability", "")),
        "condition": "new",
        "mpn": retailer_id,
    }


def scrape_all_products(workers: int = 8, limit: int = 0) -> tuple[list[dict], list[str]]:
    """サイト全商品を取得して (成功リスト, 失敗URLリスト) を返す。"""
    urls = list_site_products()
    if limit:
        urls = urls[:limit]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        scraped = list(ex.map(scrape_product, urls))
    items = [p for p in scraped if p]
    failed = [u for u, p in zip(urls, scraped) if not p]
    return items, failed


GOOGLE_FEED_COLUMNS = [
    "id", "title", "description", "link", "image_link",
    "additional_image_link", "availability", "price", "condition",
    "mpn", "identifier_exists",
]
GOOGLE_AVAILABILITY = {
    "in stock": "in_stock",
    "out of stock": "out_of_stock",
    "available for order": "preorder",
}


def build_google_feed(items: list[dict]) -> str:
    """Google Merchant Center 用のTSVフィードを組み立てる。

    Merchant Center の「スケジュールされた取得」にこのファイルのURLを
    登録すれば、API権限なしでカタログを自動更新できる。
    """
    lines = ["\t".join(GOOGLE_FEED_COLUMNS)]
    for p in items:
        row = {
            "id": p["id"],
            "title": p["title"],
            "description": p["description"][:5000],
            "link": p["link"],
            "image_link": p["image_link"],
            "additional_image_link": ",".join(p.get("additional_image_link") or []),
            "availability": GOOGLE_AVAILABILITY.get(p["availability"],
                                                    "out_of_stock"),
            "price": p["price"],
            "condition": "new",
            "mpn": p["mpn"],
            "identifier_exists": "no",  # GTIN/ブランド情報が無いため
        }
        lines.append("\t".join(
            re.sub(r"[\t\r\n]+", " ", str(row[c])) for c in GOOGLE_FEED_COLUMNS))
    return "\n".join(lines) + "\n"


def register_feed(client: MetaAdsClient, catalog_id: str,
                  feed_url: str, apply: bool = False) -> dict:
    """サイト標準のGoogle Shoppingフィードを Meta カタログの
    定期取得フィードとして登録する。

    以後は Meta が毎日フィードを取得してカタログを自動更新するため、
    catalog-sync (スクレイプ同期) は不要になる。retailer_id の重複を
    避けるため、API投入した品番ID商品は先に削除してからフィードに任せる
    （フィードが同じIDで再作成するので実質的な入れ替え）。
    """
    feeds = client.get_all(f"{catalog_id}/product_feeds",
                           fields="id,name,schedule,latest_upload")
    already = [f for f in feeds
               if feed_url in json.dumps(f.get("schedule") or {})]
    prods = client.get_all(f"{catalog_id}/products",
                           fields="retailer_id", limit=100)
    api_items = [p["retailer_id"] for p in prods
                 if (p.get("retailer_id") or "").isdigit()]
    result = {
        "summary": {
            "既存フィード数": len(feeds),
            "このURLで登録済み": len(already),
            "入れ替え対象のAPI投入商品": len(api_items),
            "実行モード": "適用" if apply else "ドライラン（--apply で適用）",
        },
        "既存フィード": feeds,
    }
    if not apply or already:
        return result

    # 1) API投入分を削除（フィードが同じ品番IDで作り直す）
    for i in range(0, len(api_items), 500):
        client.post(
            f"{catalog_id}/items_batch",
            item_type="PRODUCT_ITEM",
            requests=json.dumps([
                {"method": "DELETE", "data": {"id": rid}}
                for rid in api_items[i:i + 500]]),
        )
    # 2) 定期取得フィードを登録（サイト側の生成が昼なので JST 14時 = UTC 5時に取得）
    feed = client.post(
        f"{catalog_id}/product_feeds",
        name="fullmarksstore.jp gsfeed (自動取得)",
        schedule=json.dumps(
            {"interval": "DAILY", "url": feed_url, "hour": 5}),
    )
    result["created_feed"] = feed
    # 3) 初回は即時取得
    result["first_upload"] = client.post(f"{feed['id']}/uploads",
                                         url=feed_url)
    return result


def catalog_sync(client: MetaAdsClient, catalog_id: str,
                 apply: bool = False, workers: int = 8,
                 limit: int = 0) -> dict:
    """サイトの全商品をカタログへ同期する。apply=False はドライラン。"""
    items, failed = scrape_all_products(workers=workers, limit=limit)

    existing = client.get_all(
        f"{catalog_id}/products",
        fields="retailer_id,visibility", limit=100)
    site_ids = {p["id"] for p in items}
    # サイトに無いのに公開中のカタログ商品 → 非表示化の対象
    to_hide = [e["retailer_id"] for e in existing
               if e.get("retailer_id") not in site_ids
               and (e.get("visibility") or "").lower() == "published"]

    result = {
        "summary": {
            "サイトの商品数": len(items) + len(failed),
            "取得成功": len(items),
            "取得失敗（スキップ）": len(failed),
            "在庫あり": sum(1 for p in items
                          if p["availability"] == "in stock"),
            "カタログへ投入": len(items),
            "サイトに無いため非表示化": len(to_hide),
            "実行モード": "適用" if apply else "ドライラン（--apply で適用）",
        },
        "取得失敗URL": failed,
        "サンプル": items[:3],
    }
    if not apply:
        return result

    requests_payload = [
        {"method": "UPDATE",  # allow_upsert が既定で有効なので新規も作成される
         "data": {k: v for k, v in p.items() if v is not None}}
        for p in items
    ] + [
        {"method": "UPDATE",
         "data": {"id": rid, "availability": "out of stock",
                  "visibility": "staging"}}
        for rid in to_hide
    ]
    handles = []
    for i in range(0, len(requests_payload), 500):
        resp = client.post(
            f"{catalog_id}/items_batch",
            item_type="PRODUCT_ITEM",
            requests=json.dumps(requests_payload[i:i + 500]),
        )
        handles.append(resp.get("handles") or resp)
    result["items_batch_handles"] = handles
    return result

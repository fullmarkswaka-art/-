# -*- coding: utf-8 -*-
"""カタログ属性の補完（brand / アウトレット判定 / シリーズ）と、それを使った配信制御。

gsfeed.xml には brand / product_type / custom_label / sale_price が無いため、
Meta・Google のカタログ広告は「通常価格品とアウトレット品」「ブランド」「シリーズ」を
区別できない。EC側（アラジン）のフィード改修には時間がかかるため、サイトのカテゴリを
巡回して属性を補い、補助フィードとして Meta / Merchant Center に流し込む。

  build_attribute_rows()        … id / brand / custom_label_0(outlet|regular) /
                                  custom_label_1(シリーズ) / product_type を作る
  write_supplement_csv()        … 補助フィード CSV（Meta / Merchant Center 共通）
  meta_supplementary_feed()     … Meta カタログに補助フィードを作成し CSV をアップロード
  meta_product_sets()           … 通常価格×ブランド（×シリーズ）の商品セットを作成
  meta_swap_catalog_ads()       … 「すべての商品」の広告をブランド別広告へ差し替え
  google_split_listing_group()  … ショッピング商品グループを custom_label_0 で分割し
                                  outlet を除外
"""
from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path

import requests

from .meta_ads import MetaAdsClient, MetaAdsError

SITE = "https://www.fullmarksstore.jp"
HEADERS = {"User-Agent": "Mozilla/5.0 (fullmarks-ads-tool)"}
REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"
SUPPLEMENT_CSV = REPORT_DIR / "catalog_attributes.csv"

# サイトのブランド絞り込みカテゴリ → ブランド表記
BRAND_CATEGORIES = {
    "FILTER_BRAND_HO": "HOUDINI",
    "FILTER_BRAND_NR": "NORRONA",
    "FILTER_BRAND_PO": "POC",
    "FILTER_BRAND_HE": "HESTRA",
    "FILTER_BRAND_AC": "ACLIMA",
    "FILTER_BRAND_SR": "SAIL RACING",
    "FILTER_BRAND_KA": "KANG",
    "FILTER_BRAND_POW": "POW",
    "FILTER_BRAND_PU": "PLUS ONE WORKS",
}
# 商品ID先頭2桁（11桁IDは先頭の7を除く）→ ブランド。カテゴリ未掲載品の補完用
BRAND_BY_ID_PREFIX = {
    "10": "HESTRA", "11": "POC", "12": "NORRONA", "13": "HOUDINI",
    "14": "ACLIMA", "15": "SAIL RACING", "16": "POW", "17": "PLUS ONE WORKS",
    "21": "KANG",
}
OUTLET_CATEGORIES = ["OUTLET", "HOUDINI_OUTLET", "NORRONA_OUTLET", "POC_OUTLET",
                     "HESTRA_OUTLET", "ACLIMA_OUTLET", "SAILRACING_OUTLET"]
LABEL_OUTLET = "outlet"
LABEL_REGULAR = "regular"

# シリーズ名抽出で読み飛ばすトークン（性別表記・品番）
_SKIP_TOKENS = {"ms", "ws", "m's", "w's", "mens", "womens", "men's", "women's",
                "unisex", "kids", "jr", "junior"}


def _get_with_retry(url: str, attempts: int = 5) -> requests.Response:
    """プロキシ切断などの一時的な失敗に備え、指数バックオフで再試行する。"""
    for i in range(attempts):
        try:
            resp = requests.get(url, timeout=30, headers=HEADERS)
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            if i == attempts - 1:
                raise
            time.sleep(2 ** i)
    raise RuntimeError("unreachable")


def crawl_category(cat: str, max_pages: int = 150) -> list[str]:
    """カテゴリ一覧ページを巡回して商品ID（フィードの g:id と同じ）を集める。"""
    ids: dict[str, None] = {}
    pat = re.compile(rf"/category/{re.escape(cat)}/(\d{{9,12}})\.html")
    for page in range(1, max_pages + 1):
        url = f"{SITE}/category/{cat}/"
        if page > 1:
            url += f"?request=page&next_page={page}"
        resp = _get_with_retry(url)
        new = [i for i in pat.findall(resp.text) if i not in ids]
        if not new:
            break
        for i in new:
            ids[i] = None
        time.sleep(0.15)
    return list(ids)


def load_feed(path: str | None = None) -> dict[str, dict]:
    """gsfeed.xml を読み、id → {availability, title, price} を返す。"""
    if path:
        text = Path(path).read_text(encoding="utf-8")
    else:
        text = _get_with_retry(f"{SITE}/gsfeed.xml").text
    feed = {}
    for entry in re.findall(r"<entry>.*?</entry>", text, re.S):
        gid = re.search(r"<g:id>(.*?)</g:id>", entry).group(1)
        feed[gid] = {
            "availability": re.search(r"<g:availability>(.*?)<", entry).group(1),
            "title": re.search(r"<title>(.*?)</title>", entry).group(1),
            "price": re.search(r"<g:price>(\d+)", entry).group(1),
        }
    return feed


def brand_from_id(pid: str) -> str:
    s = pid[1:] if len(pid) == 11 and pid.startswith("7") else pid
    return BRAND_BY_ID_PREFIX.get(s[:2], "")


def series_from_title(title: str) -> str:
    """商品名からシリーズ名を取り出す（例: 'lofoten Gore-Tex Pro Jacket (M)' → 'lofoten'）。"""
    for tok in re.split(r"\s+", title.strip()):
        t = tok.lower().strip("[]()【】")
        if not t or t in _SKIP_TOKENS or re.fullmatch(r"[\d\-/]+", t):
            continue
        t = t.replace("ø", "o").replace("å", "a").replace("/", "")
        return re.sub(r"[^a-z0-9]", "", t)[:30]
    return ""


def build_attribute_rows(feed_path: str | None = None) -> list[dict]:
    """フィード全商品に brand / custom_label_0 / custom_label_1 / product_type を付ける。"""
    feed = load_feed(feed_path)
    brand_map: dict[str, str] = {}
    for cat, brand in BRAND_CATEGORIES.items():
        for i in crawl_category(cat):
            brand_map.setdefault(i, brand)
    outlet: set[str] = set()
    for cat in OUTLET_CATEGORIES:
        outlet.update(crawl_category(cat))

    rows = []
    for pid, f in feed.items():
        brand = brand_map.get(pid) or brand_from_id(pid)
        series = series_from_title(f["title"])
        rows.append({
            "id": pid,
            "brand": brand,
            "custom_label_0": LABEL_OUTLET if pid in outlet else LABEL_REGULAR,
            "custom_label_1": series,
            "product_type": f"{brand} > {series}" if brand and series else brand,
            "availability": f["availability"],
            "title": f["title"],
        })
    return rows


def write_supplement_csv(rows: list[dict], path: Path = SUPPLEMENT_CSV) -> Path:
    """Meta / Merchant Center 共通の補助フィード CSV を書く（id をキーに属性だけ上書き）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "brand", "custom_label_0", "custom_label_1", "product_type"])
        for r in rows:
            w.writerow([r["id"], r["brand"], r["custom_label_0"],
                        r["custom_label_1"], r["product_type"]])
    return path


def summarize_rows(rows: list[dict]) -> dict:
    in_stock = [r for r in rows if r["availability"] == "in stock"]
    by_brand: dict[str, dict[str, int]] = {}
    for r in in_stock:
        b = by_brand.setdefault(r["brand"] or "(不明)", {"regular": 0, "outlet": 0})
        b[r["custom_label_0"]] += 1
    return {
        "feed_total": len(rows),
        "in_stock": len(in_stock),
        "in_stock_regular": sum(1 for r in in_stock if r["custom_label_0"] == LABEL_REGULAR),
        "in_stock_outlet": sum(1 for r in in_stock if r["custom_label_0"] == LABEL_OUTLET),
        "brand_unknown": sum(1 for r in in_stock if not r["brand"]),
        "by_brand": by_brand,
    }


# ---------- Meta: 補助フィード ----------

SUPPLEMENT_FEED_NAME = "属性補完（brand/outlet/series）補助フィード"


def meta_supplementary_feed(client: MetaAdsClient, catalog_id: str,
                            primary_feed_id: str, csv_path: Path,
                            apply: bool = False) -> dict:
    """補助フィードを（無ければ）作成し、CSV をアップロードする。"""
    feeds = client.get_all(f"{catalog_id}/product_feeds",
                           fields="id,name,primary_feed_ids")
    # primary_feed_ids は読み出しで返らないため、名前で既存の補助フィードを探す
    existing = next((f for f in feeds if f.get("name") == SUPPLEMENT_FEED_NAME
                     or f.get("primary_feed_ids")), None)
    plan = {
        "catalog_id": catalog_id,
        "primary_feed_id": primary_feed_id,
        "supplementary_feed": existing,
        "csv": str(csv_path),
        "rows": sum(1 for _ in open(csv_path, encoding="utf-8")) - 1,
        "apply": apply,
    }
    if not apply:
        plan["note"] = "--apply で作成/アップロードを実行"
        return plan
    if existing is None:
        created = client.post(f"{catalog_id}/product_feeds",
                              name=SUPPLEMENT_FEED_NAME,
                              primary_feed_ids=json.dumps([primary_feed_id]))
        existing = {"id": created["id"], "name": SUPPLEMENT_FEED_NAME}
        plan["supplementary_feed"] = existing
        plan["created"] = True
    upload = client.post_file(f"{existing['id']}/uploads", csv_path)
    plan["upload"] = upload
    return plan


def meta_feed_upload_status(client: MetaAdsClient, feed_id: str) -> dict:
    ups = client.get(f"{feed_id}/uploads",
                     fields="id,start_time,end_time,error_count,warning_count,"
                            "num_deleted_items,num_detected_items,num_persisted_items",
                     limit=1).get("data", [])
    return ups[0] if ups else {}


# ---------- Meta: 商品セット ----------

def _set_filter(brand: str | None = None, series: str | None = None) -> dict:
    conds = [{"custom_label_0": {"eq": LABEL_REGULAR}}]
    if brand:
        conds.append({"brand": {"eq": brand}})
    if series:
        conds.append({"custom_label_1": {"eq": series}})
    return {"and": conds} if len(conds) > 1 else conds[0]


def planned_product_sets(rows: list[dict], min_items: int = 8) -> list[dict]:
    """作成する商品セット（通常価格×ブランド、NORRONAはシリーズ別も）を決める。"""
    in_stock = [r for r in rows if r["availability"] == "in stock"
                and r["custom_label_0"] == LABEL_REGULAR]
    sets = [{"name": "通常価格_全ブランド", "filter": _set_filter(),
             "expected": len(in_stock)}]
    brands: dict[str, int] = {}
    for r in in_stock:
        if r["brand"]:
            brands[r["brand"]] = brands.get(r["brand"], 0) + 1
    for b, n in sorted(brands.items(), key=lambda x: -x[1]):
        if n >= min_items:
            sets.append({"name": f"通常価格_{b}", "filter": _set_filter(b), "expected": n})
    series: dict[str, int] = {}
    for r in in_stock:
        if r["brand"] == "NORRONA" and r["custom_label_1"]:
            series[r["custom_label_1"]] = series.get(r["custom_label_1"], 0) + 1
    for s, n in sorted(series.items(), key=lambda x: -x[1]):
        if n >= min_items:
            sets.append({"name": f"通常価格_NORRONA_{s}",
                         "filter": _set_filter("NORRONA", s), "expected": n})
    return sets


def meta_product_sets(client: MetaAdsClient, catalog_id: str, rows: list[dict],
                      apply: bool = False) -> dict:
    existing = {ps["name"]: ps for ps in client.get_all(
        f"{catalog_id}/product_sets", fields="id,name,product_count,filter")}
    plan = []
    for s in planned_product_sets(rows):
        cur = existing.get(s["name"])
        item = {**s, "filter": json.dumps(s["filter"], ensure_ascii=False),
                "existing_id": cur["id"] if cur else None,
                "current_count": cur.get("product_count") if cur else None}
        if apply and cur is None:
            res = client.post(f"{catalog_id}/product_sets", name=s["name"],
                              filter=json.dumps(s["filter"]))
            item["created_id"] = res.get("id")
        plan.append(item)
    return {"catalog_id": catalog_id, "apply": apply, "product_sets": plan}


# ---------- Meta: 広告差し替え ----------

def meta_swap_catalog_ads(client: MetaAdsClient, old_ad_id: str,
                          product_sets: list[dict], message: str | None = None,
                          apply: bool = False) -> dict:
    """「すべての商品」広告を、商品セットごとの広告に置き換える（旧広告は停止）。

    product_sets: [{"id": ..., "name": ...}, ...]
    message: 本文テンプレート。省略時は旧広告のものを流用。
    """
    old = client.get(old_ad_id,
                     fields="id,name,status,adset_id,creative{id,object_story_spec,"
                            "asset_feed_spec,product_set_id}")
    spec = old["creative"]["object_story_spec"]
    template = dict(spec.get("template_data", {}))
    if message:
        template["message"] = message
    plan = {"old_ad": {"id": old["id"], "name": old["name"], "status": old["status"],
                       "product_set_id": old["creative"].get("product_set_id")},
            "adset_id": old["adset_id"], "message": template.get("message"),
            "new_ads": [], "apply": apply}
    for ps in product_sets:
        name = f"fullmarks-dpa-{ps['name']}"
        entry = {"name": name, "product_set_id": ps["id"]}
        if apply:
            creative = client.post(
                f"{client.config.ad_account_id}/adcreatives",
                name=name,
                object_story_spec=json.dumps({"page_id": spec["page_id"],
                                              "template_data": template}),
                product_set_id=ps["id"],
                asset_feed_spec=json.dumps(old["creative"].get("asset_feed_spec") or {}),
            )
            ad = client.post(f"{client.config.ad_account_id}/ads",
                             name=name, adset_id=old["adset_id"],
                             creative=json.dumps({"creative_id": creative["id"]}),
                             status="ACTIVE")
            entry.update(creative_id=creative["id"], ad_id=ad["id"])
        plan["new_ads"].append(entry)
    if apply:
        client.set_status(old_ad_id, "PAUSED")
        plan["old_ad"]["status"] = "PAUSED"
    return plan


# ---------- Google: ショッピング商品グループ分割 ----------

def google_split_listing_group(gclient, campaign_id: str, apply: bool = False,
                               bid_yen: float = 20.0) -> dict:
    """商品グループを custom_label_0 で分割し、outlet を除外する。

    結果のツリー:
      すべての商品 (SUBDIVISION)
        ├ custom_label_0 = outlet   → 除外
        └ その他すべて              → 入札 bid_yen
    """
    rows = gclient.search(
        "SELECT ad_group.id, ad_group_criterion.resource_name, "
        "ad_group_criterion.listing_group.type, "
        "ad_group_criterion.listing_group.parent_ad_group_criterion, "
        "ad_group_criterion.cpc_bid_micros, ad_group_criterion.negative "
        f"FROM ad_group_criterion WHERE campaign.id={campaign_id} "
        "AND ad_group_criterion.type='LISTING_GROUP' AND ad_group_criterion.status!='REMOVED'")
    current = [{"resource": r.ad_group_criterion.resource_name,
                "type": r.ad_group_criterion.listing_group.type_.name,
                "parent": r.ad_group_criterion.listing_group.parent_ad_group_criterion,
                "bid": r.ad_group_criterion.cpc_bid_micros / 1e6,
                "negative": r.ad_group_criterion.negative} for r in rows]
    ad_group_ids = {r.ad_group.id for r in rows}
    plan = {"campaign_id": campaign_id, "current_tree": current,
            "ad_groups": sorted(ad_group_ids), "apply": apply,
            "new_tree": [
                {"node": "root", "type": "SUBDIVISION"},
                {"node": "custom_label_0 = outlet", "type": "UNIT", "negative": True},
                {"node": "その他すべて", "type": "UNIT", "bid_yen": bid_yen},
            ]}
    if len(current) != 1 or current[0]["type"] != "UNIT":
        plan["note"] = "既に分割済みのため何もしない（手動で確認してください）"
        return plan
    if not apply:
        plan["note"] = "--apply で分割を実行"
        return plan

    client = gclient.client
    customer_id = gclient.customer_id
    ag_id = next(iter(ad_group_ids))
    svc = client.get_service("AdGroupCriterionService")
    ag_service = client.get_service("AdGroupService")
    ad_group_rn = ag_service.ad_group_path(customer_id, ag_id)
    lg_type = client.enums.ListingGroupTypeEnum
    idx_enum = client.enums.ProductCustomAttributeIndexEnum
    ops = []
    # 1) 既存ルートを削除
    op = client.get_type("AdGroupCriterionOperation")
    op.remove = current[0]["resource"]
    ops.append(op)
    # 2) 新ルート(SUBDIVISION)
    root_tmp = -1
    op = client.get_type("AdGroupCriterionOperation")
    c = op.create
    c.ad_group = ad_group_rn
    c.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
    c.resource_name = svc.ad_group_criterion_path(customer_id, ag_id, root_tmp)
    c.listing_group.type_ = lg_type.SUBDIVISION
    ops.append(op)
    root_rn = c.resource_name
    # 3) outlet → 除外
    op = client.get_type("AdGroupCriterionOperation")
    c = op.create
    c.ad_group = ad_group_rn
    c.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
    c.negative = True
    c.listing_group.type_ = lg_type.UNIT
    c.listing_group.parent_ad_group_criterion = root_rn
    c.listing_group.case_value.product_custom_attribute.index = idx_enum.INDEX0
    c.listing_group.case_value.product_custom_attribute.value = LABEL_OUTLET
    ops.append(op)
    # 4) その他すべて → 入札
    op = client.get_type("AdGroupCriterionOperation")
    c = op.create
    c.ad_group = ad_group_rn
    c.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
    c.cpc_bid_micros = int(bid_yen * 1_000_000)
    c.listing_group.type_ = lg_type.UNIT
    c.listing_group.parent_ad_group_criterion = root_rn
    c.listing_group.case_value.product_custom_attribute.index = idx_enum.INDEX0
    ops.append(op)
    resp = svc.mutate_ad_group_criteria(customer_id=customer_id, operations=ops)
    plan["result"] = [r.resource_name for r in resp.results]
    return plan

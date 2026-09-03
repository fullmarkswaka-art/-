# -*- coding: utf-8 -*-
"""fullmarksstore.jp のアウトレットカテゴリを巡回し、広告除外用の商品IDリストを作る。

gsfeed.xml にはアウトレット判別用の属性（product_type / custom_label / sale_price）が
無いため、Meta・Google どちらのカタログ広告も通常商品とアウトレットを区別できない。
このスクリプトはサイト側のカテゴリ（/category/OUTLET/ 等）から対象IDを集め、

  reports/outlet_ids.json                 … ブランド別のアウトレット商品ID
  reports/outlet_supplemental_feed.csv    … Google Merchant Center 補助フィード用
                                            (id, custom_label_0=outlet, brand)
  reports/meta_outlet_supplementary.csv   … Meta 補助フィード用 (id, custom_label_0, brand)

を出力する。フィード本体に属性が追加されるまでの暫定運用に使う。

使い方: python scripts/outlet_products.py [--feed gsfeed.xml]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

import requests

SITE = "https://www.fullmarksstore.jp"
HEADERS = {"User-Agent": "Mozilla/5.0 (fullmarks-ads-tool)"}
# カテゴリ名 → ブランド表記（フィード側にbrand属性が無いので補助フィードで補う）
OUTLET_CATEGORIES = {
    "HOUDINI_OUTLET": "HOUDINI",
    "NORRONA_OUTLET": "NORRONA",
    "POC_OUTLET": "POC",
    "HESTRA_OUTLET": "HESTRA",
    "ACLIMA_OUTLET": "ACLIMA",
    "SAILRACING_OUTLET": "SAIL RACING",
}
REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"


def crawl_category(cat: str, max_pages: int = 100) -> list[str]:
    """カテゴリ一覧ページを巡回して商品ID（フィードの g:id と同じ）を集める。"""
    ids: dict[str, None] = {}
    pat = re.compile(rf"/category/{re.escape(cat)}/(\d{{9,12}})\.html")
    for page in range(1, max_pages + 1):
        url = f"{SITE}/category/{cat}/"
        if page > 1:
            url += f"?request=page&next_page={page}"
        resp = requests.get(url, timeout=30, headers=HEADERS)
        resp.raise_for_status()
        new = [i for i in pat.findall(resp.text) if i not in ids]
        if not new:
            break
        for i in new:
            ids[i] = None
        time.sleep(0.2)
    return list(ids)


def load_feed(path: str | None) -> dict[str, dict]:
    """gsfeed.xml を読み、id → {availability, title, price} を返す。"""
    if path:
        text = Path(path).read_text(encoding="utf-8")
    else:
        text = requests.get(f"{SITE}/gsfeed.xml", timeout=60, headers=HEADERS).text
    feed = {}
    for entry in re.findall(r"<entry>.*?</entry>", text, re.S):
        gid = re.search(r"<g:id>(.*?)</g:id>", entry).group(1)
        feed[gid] = {
            "availability": re.search(r"<g:availability>(.*?)<", entry).group(1),
            "title": re.search(r"<title>(.*?)</title>", entry).group(1),
            "price": re.search(r"<g:price>(\d+)", entry).group(1),
        }
    return feed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--feed", help="ローカルの gsfeed.xml（省略時はサイトから取得）")
    args = ap.parse_args(argv)

    feed = load_feed(args.feed)
    by_brand: dict[str, list[str]] = {}
    for cat, brand in OUTLET_CATEGORIES.items():
        by_brand[brand] = crawl_category(cat)
    # 総合OUTLETカテゴリにだけ入っている商品も拾う
    all_outlet = crawl_category("OUTLET")
    known = {i for ids in by_brand.values() for i in ids}
    by_brand["(brand unknown)"] = [i for i in all_outlet if i not in known]

    REPORT_DIR.mkdir(exist_ok=True)
    rows = []
    for brand, ids in by_brand.items():
        for i in ids:
            f = feed.get(i)
            rows.append({
                "id": i,
                "brand": brand,
                "in_feed": f is not None,
                "availability": f["availability"] if f else "",
                "title": f["title"] if f else "",
            })
    (REPORT_DIR / "outlet_ids.json").write_text(
        json.dumps({"generated": time.strftime("%Y-%m-%d"), "by_brand": by_brand},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    for name in ("outlet_supplemental_feed.csv", "meta_outlet_supplementary.csv"):
        with open(REPORT_DIR / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "custom_label_0", "brand"])
            for r in rows:
                if r["in_feed"]:
                    w.writerow([r["id"], "outlet",
                                "" if r["brand"].startswith("(") else r["brand"]])

    in_stock_total = sum(1 for v in feed.values() if v["availability"] == "in stock")
    outlet_in_stock = sum(1 for r in rows if r["availability"] == "in stock")
    print(f"フィード掲載 {len(feed)} 件 / 在庫あり {in_stock_total} 件")
    print(f"アウトレット {len(rows)} 件（在庫あり {outlet_in_stock} 件 = "
          f"在庫あり商品の {outlet_in_stock / in_stock_total:.0%}）")
    for brand, ids in by_brand.items():
        n = sum(1 for i in ids if feed.get(i, {}).get("availability") == "in stock")
        print(f"  {brand:16s} {len(ids):4d} 件（在庫あり {n}）")
    print(f"出力: {REPORT_DIR / 'outlet_ids.json'}, "
          f"{REPORT_DIR / 'outlet_supplemental_feed.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

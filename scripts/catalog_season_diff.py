# -*- coding: utf-8 -*-
"""カタログ広告の商品セットを config/season_sets.json で絞ったときの「入れ替え一覧」を作る（読み取りのみ）。

使い方: python scripts/catalog_season_diff.py [--out reports/カタログ広告_冬入れ替え案_<日付>.xlsx]
先に `python -m ads_manager meta catalog-attributes` で reports/catalog_attributes.csv を最新にしておく。
シートはセットごと。在庫ありの商品だけを、新しく出る／引き続き出る／出なくなる に分けて載せる。
"""
from __future__ import annotations

import argparse
import collections
import csv
import html
import json
import sys
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ads_manager.catalog_attributes import (SUPPLEMENT_CSV, _id_filter, _season_filter,  # noqa: E402
                                            load_feed, load_season_sets)
from ads_manager.config import load_meta_config  # noqa: E402
from ads_manager.meta_ads import MetaAdsClient  # noqa: E402
from ads_manager.secrets_aws import load_secrets_into_env  # noqa: E402

CATALOG = "610915616169358"
LABEL = {"通常価格_HOUDINI": "HOUDINI", "通常価格_ACLIMA": "ACLIMA", "通常価格_POC": "POC",
         "FW新作_NORRONA": "NORRØNA 新作", "通常価格_NORRONA_falketind": "NORRØNA falketind",
         "通常価格_NORRONA_femund": "NORRØNA femund", "通常価格_NORRONA_lofoten": "NORRØNA lofoten",
         "通常価格_NORRONA_trollveggen": "NORRØNA trollveggen", "通常価格_HESTRA": "HESTRA"}
SHOW = {"追加": "新しく出る", "残る": "引き続き出る", "外れる": "出なくなる"}
FILL = {"新作": "DDEBF7", "定番の冬物": "FFF2CC", "対象": "E2EFDA", "外れる": "F2F2F2"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "reports" / f"カタログ広告_冬入れ替え案_{date.today():%Y-%m-%d}.xlsx"))
    args = ap.parse_args()
    if not __import__("os").getenv("META_ACCESS_TOKEN"):
        load_secrets_into_env()
    client = MetaAdsClient(load_meta_config())
    feed = load_feed()
    rows = []
    for r in csv.DictReader(open(SUPPLEMENT_CSV, encoding="utf-8")):
        r["availability"] = feed.get(r["id"], {}).get("availability", "")
        r["title"] = feed.get(r["id"], {}).get("title", "")
        rows.append(r)
    season = load_season_sets()
    current = {ps["name"]: ps for ps in client.get_all(f"{CATALOG}/product_sets", fields="id,name,filter")}
    out = []
    for name, c in season["sets"].items():
        if c.get("brand"):
            base = _id_filter(rows, c["brand"])
        elif name.startswith("通常価格_NORRONA_"):
            base = _id_filter(rows, "NORRONA", name.split("_", 2)[2])
        else:
            base = _id_filter(rows, name.replace("通常価格_", ""))
        after = set(_season_filter(base, rows, c, season["exclude"])["retailer_id"]["is_any"])
        f = current.get(name, {}).get("filter") or {}
        f = json.loads(f) if isinstance(f, str) else f
        before = set(f.get("retailer_id", {}).get("is_any", []))
        cats = c.get("category_ids")
        for i in sorted(before | after):
            if feed.get(i, {}).get("availability") != "in stock":
                continue
            change = "残る" if i in before and i in after else ("外れる" if i in before else "追加")
            kind = "外れる" if change == "外れる" else ("対象" if cats is None else "新作" if i in cats else "定番の冬物")
            out.append({"set": name, "change": change, "kind": kind, "id": i,
                        "title": html.unescape(feed[i]["title"]), "price": int(feed[i]["price"])})
    wb = Workbook()
    ws = wb.active
    ws.title = "まとめ"
    ws.append(["広告", "入れ替え後に出る商品", "うち新作", "うち定番の冬物", "出なくなる商品", "入れ替え前"])
    by = collections.defaultdict(list)
    for r in out:
        by[r["set"]].append(r)
    for k, lab in LABEL.items():
        n = collections.Counter(r["kind"] for r in by[k])
        b = sum(1 for r in by[k] if r["change"] != "追加")
        ws.append([lab, n["新作"] + n["定番の冬物"] + n["対象"], n["新作"] or "", n["定番の冬物"] or "", n["外れる"], b])
    ws.append([])
    ws.append(["在庫ありの商品だけ。NORRØNA senja（トレラン）の広告は止めて「NORRØNA 新作」の広告に置き換える。"])
    ws.append(["色: 青=新作（サイトの新作・スノーカテゴリ）／黄=定番の冬物（新作ではないが残す）／緑=夏物を外しただけのセット／灰=出なくなる"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for col, w in zip("ABCDEF", (24, 20, 10, 14, 14, 12)):
        ws.column_dimensions[col].width = w
    order = {"新作": 0, "定番の冬物": 1, "対象": 1, "外れる": 2}
    for k, lab in LABEL.items():
        sh = wb.create_sheet(lab[:28])
        sh.append(["区分", "変更", "商品名", "価格（税込）", "商品ID"])
        for c in sh[1]:
            c.font = Font(bold=True)
        for r in sorted(by[k], key=lambda r: (order[r["kind"]], r["title"])):
            sh.append([r["kind"] if r["kind"] != "外れる" else "", SHOW[r["change"]], r["title"], r["price"], r["id"]])
            for c in sh[sh.max_row]:
                c.fill = PatternFill("solid", fgColor=FILL[r["kind"]])
            sh.cell(sh.max_row, 4).number_format = "#,##0"
        for col, w in zip("ABCDE", (12, 14, 46, 12, 14)):
            sh.column_dimensions[col].width = w
        sh.freeze_panes = "A2"
    wb.save(args.out)
    print(args.out)
    for k, lab in LABEL.items():
        n = collections.Counter(r["kind"] for r in by[k])
        print(f"{lab}: 新作 {n['新作']} / 定番の冬物 {n['定番の冬物']} / 対象 {n['対象']} / 出なくなる {n['外れる']}")
        if n["定番の冬物"]:
            print("   定番:", "; ".join(r["title"] for r in by[k] if r["kind"] == "定番の冬物"))


if __name__ == "__main__":
    main()

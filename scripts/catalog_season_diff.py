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
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

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
KIND = {"新作": "新作", "定番の冬物": "定番の冬物", "対象": "夏物を外しただけ", "外れる": "出なくなる"}
FILL = {"新作": "DDEBF7", "定番の冬物": "FFF2CC", "夏物を外しただけ": "E2EFDA", "出なくなる": "EDEDED"}
FONT = "Arial"


def _f(bold=False, size=10, color="000000"):
    return Font(name=FONT, bold=bold, size=size, color=color)


def write_review_book(out: list[dict], path: str) -> None:
    """社内確認用の Excel（概要＋全ブランドの商品一覧、確認欄つき）を書く。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "概要"
    li = wb.create_sheet("商品一覧")
    head = ["広告", "区分", "入れ替え後", "商品名", "価格（税込）", "商品ID", "商品ページ", "確認", "コメント"]
    li.append(head)
    order = {"新作": 0, "定番の冬物": 1, "対象": 1, "外れる": 2}
    names = list(LABEL)
    rows = sorted(out, key=lambda r: (names.index(r["set"]), order[r["kind"]], r["title"]))
    for r in rows:
        kind = KIND[r["kind"]]
        url = f"https://www.fullmarksstore.jp/item/{r['id']}.html"
        li.append([LABEL[r["set"]], kind, "出ない" if kind == "出なくなる" else "出る", r["title"], r["price"],
                   r["id"], url, None, None])
        n = li.max_row
        li.cell(n, 7).hyperlink = url
        li.cell(n, 7).value = "開く"
        li.cell(n, 7).font = _f(color="1F4E99")
        li.cell(n, 5).number_format = "#,##0"
    last = li.max_row
    for c in li[1]:
        c.font = _f(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F5B4A")
        c.alignment = Alignment(vertical="center")
    for row in li.iter_rows(min_row=2, max_row=last):
        for c in row:
            if c.column != 7:
                c.font = _f()
    for kind, color in FILL.items():
        li.conditional_formatting.add(f"A2:G{last}", FormulaRule(formula=[f'$B2="{kind}"'],
                                      fill=PatternFill("solid", fgColor=color)))
    li.conditional_formatting.add(f"H2:I{last}", FormulaRule(formula=['$H2="外したい"'],
                                  fill=PatternFill("solid", fgColor="F8CBAD")))
    li.conditional_formatting.add(f"H2:I{last}", FormulaRule(formula=['$H2="残したい"'],
                                  fill=PatternFill("solid", fgColor="C6E0B4")))
    for col in ("H", "I"):
        for n in range(2, last + 1):
            li[f"{col}{n}"].fill = PatternFill("solid", fgColor="FFFFE0")
    dv = DataValidation(type="list", formula1='"OK,外したい,残したい"', allow_blank=True,
                        promptTitle="確認", prompt="OK／外したい（出る商品）／残したい（出なくなる商品）から選ぶ")
    li.add_data_validation(dv)
    dv.add(f"H2:H{last}")
    for col, w in zip("ABCDEFGHI", (20, 16, 10, 46, 12, 14, 9, 11, 30)):
        li.column_dimensions[col].width = w
    li.freeze_panes = "A2"
    li.auto_filter.ref = f"A1:I{last}"

    # 概要
    for col, w in zip("ABCDEFG", (24, 13, 13, 13, 14, 13, 13)):
        ws.column_dimensions[col].width = w
    ws["A1"] = "カタログ広告 冬の入れ替え案（社内確認用）"
    ws["A1"].font = _f(bold=True, size=15)
    ws["A2"] = f"作成 {date.today():%Y年%m月%d日} ／ 状態: 承認待ち（まだ広告には反映していません）"
    ws["A2"].font = _f(color="8A5A00")
    lines = [
        ("なぜ入れ替えるのか", True),
        ("Instagram・Facebook の「商品が並ぶ広告」（カタログ広告）に、いまも夏物が出ている。", False),
        ("9/26〜10/17 のカタログ広告費 76,544円のうち 63,776円（83%）が冬の新作以外に使われた"
         "（Wadi Pants・キャップ・自転車用バッグなど）。", False),
        ("直近7日のカタログ広告は広告1円あたりの売上 2.6円で、Meta 広告の中でいちばん低い。", False),
        ("", False),
    ]
    r = 4
    for text, bold in lines:
        ws.cell(r, 1, text).font = _f(bold=bold, size=12 if bold else 10)
        r += 1
    ws.cell(r, 1, "何が変わるか（在庫ありの商品数。商品一覧シートから自動で数えます）").font = _f(bold=True, size=12)
    r += 1
    hdr = ["広告", "入れ替え前", "入れ替え後", "うち新作", "うち定番の冬物", "夏物を外しただけ", "出なくなる"]
    for j, h in enumerate(hdr, 1):
        c = ws.cell(r, j, h)
        c.font = _f(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F5B4A")
        c.alignment = Alignment(horizontal="center", wrap_text=True)
    top = r + 1
    rng = lambda col: f"商品一覧!${col}$2:${col}${last}"
    thin = Side(style="thin", color="BFBFBF")
    for lab in LABEL.values():
        r += 1
        ws.cell(r, 1, lab)
        a = f"$A{r}"
        ws.cell(r, 4, f'=COUNTIFS({rng("A")},{a},{rng("B")},"新作")')
        ws.cell(r, 5, f'=COUNTIFS({rng("A")},{a},{rng("B")},"定番の冬物")')
        ws.cell(r, 6, f'=COUNTIFS({rng("A")},{a},{rng("B")},"夏物を外しただけ")')
        ws.cell(r, 7, f'=COUNTIFS({rng("A")},{a},{rng("B")},"出なくなる")')
        ws.cell(r, 3, f"=D{r}+E{r}+F{r}")
        ws.cell(r, 2, 0 if lab == "NORRØNA 新作" else f"=C{r}+G{r}-{sum(1 for x in out if LABEL[x['set']] == lab and x['change'] == '追加')}")
        for j in range(1, 8):
            ws.cell(r, j).font = _f(bold=(j == 3))
            ws.cell(r, j).border = Border(bottom=thin)
            if j > 1:
                ws.cell(r, j).alignment = Alignment(horizontal="center")
    r += 1
    ws.cell(r, 1, "合計").font = _f(bold=True)
    for j in range(2, 8):
        col = "ABCDEFG"[j - 1]
        c = ws.cell(r, j, f"=SUM({col}{top}:{col}{r - 1})")
        c.font = _f(bold=True)
        c.alignment = Alignment(horizontal="center")
    r += 1
    notes = [
        "入れ替え前 = いま広告に載っている在庫ありの商品数（新しく入荷して加わる商品の数を差し引いて計算）。",
        "新作 = サイトの 2026FW 新作カテゴリ（POC はスノーカテゴリ）。定番の冬物 = 新作ではないが冬に売る商品（ダウン・中わた・フリース・ウールなど）。",
        "NORRØNA の各シリーズと HESTRA は、ショーツ・Tシャツ・スカートなどの夏物を外すだけ。",
        "NORRØNA 新作 は新しく作る広告で、NORRØNA senja（トレラン）の広告と置き換える。",
    ]
    for t in notes:
        ws.cell(r, 1, t).font = _f(size=9, color="595959")
        r += 1
    r += 1
    blocks = [
        ("変わらないこと", ["1日の予算 7,000円", "見せる相手（全員向け）", "広告の文言「ブランド｜Fall / Winter 2026」",
                       "アウトレット品は出さない"]),
        ("反映のしかた", ["今の広告は止めずに、中の商品だけ入れ替える（審査なし）。",
                     "NORRØNA 新作の広告だけ新しく作る（審査あり）。",
                     "毎週月曜の更新で、新しく入荷した新作も自動で加わる。"]),
        ("気をつけること", ["HOUDINI は今月このカタログ広告で15件売れている一番の柱。商品を絞るので売れ方が変わる可能性がある。"]),
        ("いつ判断するか", ["反映から1週間後（10/26ごろ）に、前の週と購入件数・売上を比べる。"]),
        ("確認のお願い", ["「商品一覧」シートの「確認」欄（黄色）で、出る商品は「OK／外したい」、出なくなる商品で残したいものは「残したい」を選ぶ。",
                     "理由があれば「コメント」欄へ。広告・区分・入れ替え後の列で絞り込めます。商品ページ列の「開く」でサイトの商品ページが開きます。",
                     "記入例: Ms Wadi Pants（出なくなる）→ 確認「残したい」、コメント「秋口まで売れているので残したい」"]),
    ]
    for title, items in blocks:
        ws.cell(r, 1, title).font = _f(bold=True, size=12)
        r += 1
        for t in items:
            ws.cell(r, 1, "・" + t).font = _f()
            r += 1
        r += 1
    ws.cell(r, 1, "集計: Meta 広告（9/26〜10/17）、在庫・商品名・価格はサイトの商品フィード（作成日時点、税込）。"
                  "作成: scripts/catalog_season_diff.py").font = _f(size=9, color="595959")
    ws.sheet_view.showGridLines = False
    wb.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "reports" / f"カタログ広告_冬入れ替え案_社内確認用_{date.today():%Y-%m-%d}.xlsx"))
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
    write_review_book(out, args.out)
    print(args.out)
    by = collections.defaultdict(list)
    for r in out:
        by[r["set"]].append(r)
    for k, lab in LABEL.items():
        n = collections.Counter(r["kind"] for r in by[k])
        print(f"{lab}: 新作 {n['新作']} / 定番の冬物 {n['定番の冬物']} / 対象 {n['対象']} / 出なくなる {n['外れる']}")
        if n["定番の冬物"]:
            print("   定番:", "; ".join(r["title"] for r in by[k] if r["kind"] == "定番の冬物"))


if __name__ == "__main__":
    main()

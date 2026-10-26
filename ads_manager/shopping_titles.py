# -*- coding: utf-8 -*-
"""Googleショッピング（PLA）の立て直し（2026-10）。

1. 商品名の補足: gsfeed.xml の商品名は英語の型番だけ（ブランド・日本語の種類なし）なので、
   Merchant Center の補助データで「<ブランド> <元の商品名>｜<性別> <種類>」に置き換え、
   Google の商品カテゴリ・性別・年齢層も足す。サイトの絞り込みカテゴリ（FILTER_CATEGORY_* /
   FILTER_TYPE_* / FILTER_ACTIVITY_BIKE）を巡回して判定する。結果は reports/google_shopping_titles.csv に書き、
   `google mc-supplement --apply` がこのファイルを読んで一緒に登録する（Meta のカタログには流さない）。
2. 除外キーワード: 購入につながっていない他社ブランド名・「アウトレット」などで検索した人に出さない。
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from .catalog_attributes import BRAND_BY_ID_PREFIX, crawl_category, load_feed

TITLES_CSV = Path(__file__).resolve().parent.parent / "reports" / "google_shopping_titles.csv"

# サイトの表示名（商品名の先頭に付ける）。ID 先頭2桁で判定（11桁のアウトレットIDは先頭の7を除く）
BRAND_LABEL = {"HESTRA": "HESTRA", "POC": "POC", "NORRONA": "NORRØNA", "HOUDINI": "HOUDINI", "ACLIMA": "ACLIMA",
               "SAIL RACING": "SAIL RACING", "KANG": "KANG"}
BRAND_LABEL_BY_PREFIX = {"16": "PLUS ONE WORKS", "17": "Permanent Union"}  # サイトの FILTER_BRAND_POW / _PU の表記

CATEGORIES = {"FILTER_CATEGORY_OUT": "アウター", "FILTER_CATEGORY_TOPS": "トップス", "FILTER_CATEGORY_BOT": "ボトムス",
              "FILTER_CATEGORY_BAG": "バッグ", "FILTER_CATEGORY_GLO": "グローブ", "FILTER_CATEGORY_GOG": "ゴーグル",
              "FILTER_CATEGORY_HEL": "ヘルメット", "FILTER_CATEGORY_EYE": "サングラス", "FILTER_CATEGORY_ACS": "アクセサリー"}
SKI = "Sporting Goods > Outdoor Recreation > Winter Sports & Activities > Skiing & Snowboarding"
GPC = {"アウター": "Apparel & Accessories > Clothing > Outerwear > Coats & Jackets",
       "トップス": "Apparel & Accessories > Clothing > Shirts & Tops",
       "ボトムス": "Apparel & Accessories > Clothing > Pants",
       "バッグ": "Luggage & Bags",
       "グローブ": "Apparel & Accessories > Clothing Accessories > Gloves & Mittens",
       "ゴーグル": f"{SKI} > Ski & Snowboard Goggles",
       "ヘルメット": f"{SKI} > Ski & Snowboard Helmets",
       "サングラス": "Apparel & Accessories > Clothing Accessories > Sunglasses",
       "アクセサリー": "Apparel & Accessories > Clothing Accessories"}
BIKE_HELMET = "Sporting Goods > Outdoor Recreation > Cycling > Bicycle Accessories > Bicycle Helmets"

# 種類の日本語（大分類ごとに、商品名の英語から細かくする。先に一致したもの）
_REFINE = {
    "アウター": [(r"\bvest\b", "ベスト"), (r"", "ジャケット")],
    "トップス": [(r"rashguard", "ラッシュガード"), (r"underwear|thermal|base ?layer", "インナー"),
                (r"\btee\b|t-shirt", "Tシャツ"), (r"\bpolo\b", "ポロシャツ"), (r"shirt", "シャツ"),
                (r"hood|houdi", "フーディ"), (r"crew|sweater|pullover|zip", "スウェット・セーター"), (r"", "トップス")],
    "ボトムス": [(r"\bbib", "ビブパンツ"), (r"shorts?\b", "ショーツ"), (r"skirt", "スカート"),
                (r"tights|leggings|long johns|longs", "タイツ"), (r"underwear", "インナー"), (r"", "パンツ")],
    "バッグ": [(r"hip|waist", "ヒップバッグ"), (r"pack|backpack|\d+\s?l\b", "バックパック"), (r"", "バッグ")],
    "アクセサリー": [(r"protector|knee|elbow|torso|spine", "プロテクター"), (r"\bcase\b", "ケース"),
                   (r"balaclava", "バラクラバ"), (r"headover", "ネックウォーマー"), (r"beanie|toque", "ニット帽"),
                   (r"\bhat\b", "帽子"), (r"\bcap\b", "キャップ"),
                   (r"headband", "ヘッドバンド"), (r"sock", "ソックス"), (r"gaiter|neck|tube", "ネックウォーマー"),
                   (r"lens", "交換レンズ"), (r"", "")],
}


# サイトの絞り込みカテゴリに入っていない商品は、商品名の英語から大分類を推定する（先に一致したもの）
_GUESS = [(r"sleeping bag", "寝袋"), (r"mitt|glove", "グローブ"), (r"\bcase\b|protector|knee|elbow|torso|spine vpd", "アクセサリー"),
          (r"helmet", "ヘルメット"), (r"goggle", "ゴーグル"), (r"sunglass", "サングラス"),
          (r"jacket|parka|anorak|coat|spraytop|\bvest\b", "アウター"),
          (r"pants?\b|shorts|tights|skirt|longs|joggers|sailshorts", "ボトムス"),
          (r"beanie|\bcap\b|\bhat\b|balaclava|headband|headover|sock|gaiter|lens", "アクセサリー"),
          (r"\btee\b|shirt|polo|hood|houdi|crew|sweater|\btop\b|pullover|rashguard|half zip|underwear|dunfri", "トップス"),
          (r"pack|\bbag\b|pouch", "バッグ")]
GPC["寝袋"] = "Sporting Goods > Outdoor Recreation > Camping & Hiking > Sleeping Bags"


def _guess_cat(pid: str, title: str) -> str:
    t = title.lower()
    for pat, cat in _GUESS:
        if re.search(pat, t):
            return cat
    return "グローブ" if brand_label(pid) == "HESTRA" else ""


# サイトのカテゴリより優先する商品名の語（大分類, 種類）。サロペット・交換レンズ・VPD プロテクターなど
_OVERRIDE = [(r"salopette|\bbib\b", "ボトムス", "ビブパンツ"), (r"\blongs\b", "ボトムス", "タイツ"),
             (r"\bcase\b", "アクセサリー", "ケース"), (r"\blens\b", "アクセサリー", "交換レンズ"), (r"trolley|duffel|duffle|wheeled", "バッグ", "キャリーバッグ"),
             (r"protector|vpd.*\b(vest|shorts|knee|elbow|sleeve|torso|spine|shins?)\b", "プロテクター", "プロテクター"),
             (r"singlet|tank top", "トップス", "タンクトップ")]
GPC["プロテクター"] = ""
GPC["スキーポール"] = f"{SKI} > Ski Poles"


def _override(title: str):
    t = title.lower()
    for pat, cat, kind in _OVERRIDE:
        if re.search(pat, t):
            return cat, kind
    return None


def _kind(cat: str, title: str) -> str:
    t = title.lower()
    for pat, word in _REFINE.get(cat, [(r"", cat)]):
        if re.search(pat, t):
            return word
    return cat


def _gender(pid: str, title: str, mens: set, womens: set, kids: set) -> tuple[str, str]:
    """(gender, ageGroup)。商品名の Ms/Ws/(M)/(W) を優先し、無ければサイトの MENS/WOMENS/KIDS 一覧。"""
    t = f" {title} "
    if pid in kids or re.search(r"\b(kids?|junior|jr|children)\b", title, re.I):
        return "unisex", "kids"
    if re.search(r"\(M/W\)|\(W/M\)|unisex", t, re.I):
        return "unisex", "adult"
    if re.search(r"\sMs\s|\(M\)|\bMen'?s\b|\bM's\b", t):
        return "male", "adult"
    if re.search(r"\sWs\s|\(W\)|\bWomen'?s\b|\bW's\b|\bWOMAN\b", t):
        return "female", "adult"
    if pid in mens and pid not in womens:
        return "male", "adult"
    if pid in womens and pid not in mens:
        return "female", "adult"
    return "unisex", "adult"


def brand_label(pid: str) -> str:
    s = pid[1:] if len(pid) == 11 and pid.startswith("7") else pid
    if s[:2] in BRAND_LABEL_BY_PREFIX:
        return BRAND_LABEL_BY_PREFIX[s[:2]]
    return BRAND_LABEL.get(BRAND_BY_ID_PREFIX.get(s[:2], ""), "")


def build_titles(feed: dict | None = None, crawl=crawl_category) -> list[dict]:
    feed = feed or load_feed()
    cat_of: dict[str, str] = {}
    for slug, word in CATEGORIES.items():
        for i in crawl(slug):
            cat_of.setdefault(i, word)
    mens, womens, kids = (set(crawl(c)) for c in ("FILTER_TYPE_MENS", "FILTER_TYPE_WOMENS", "FILTER_TYPE_KIDS"))
    bike = set(crawl("FILTER_ACTIVITY_BIKE"))
    rows = []
    for pid, f in feed.items():
        title = re.sub(r"\s+", " ", f["title"]).strip()
        brand = brand_label(pid)
        cat = cat_of.get(pid) or _guess_cat(pid, title)
        kind = _kind(cat, title) if cat else ""
        if brand == "KANG":
            cat, kind = "スキーポール", "スキーポール"
        ov = _override(title)
        if ov:
            cat, kind = ov
        if title.lower().startswith("norrona "):
            title = "NORRØNA " + title[8:]
        gender, age = _gender(pid, title, mens, womens, kids)
        gword = {"male": "メンズ", "female": "レディース"}.get(gender, "キッズ" if age == "kids" else "")
        tl = title.lower() + " "
        head = title if (not brand or tl.startswith(brand.lower() + " ")
                         or tl.startswith(brand.lower().replace("ø", "o") + " ")) else f"{brand} {title}"
        tail = " ".join(w for w in (gword, kind) if w)
        new = f"{head}｜{tail}" if tail else head
        gpc = BIKE_HELMET if (cat == "ヘルメット" and pid in bike) else GPC.get(cat, "")
        if kind == "交換レンズ":
            gpc = ""
        rows.append({"id": pid, "old_title": f["title"], "title": new[:150], "category": cat,
                     "google_product_category": gpc, "gender": gender, "age_group": age})
    return rows


def write_titles(rows: list[dict], path: Path = TITLES_CSV) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return path


def load_titles(path: Path = TITLES_CSV) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {r["id"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}


# ---- 除外キーワード ----
# 2026-08-01〜10-25 の検索語で購入0件だった他社ブランド・用途違いの語（パタゴニア・アークテリクス・ホグロフスは購入があったので残す）
NEGATIVES = [
    "モンベル", "montbell", "mont-bell", "mont bell",
    "ノースフェイス", "ノース フェイス", "northface", "north face",
    "マムート", "mammut", "ワークマン", "workman", "ナンガ", "nanga",
    "デサント", "descente", "水沢", "ミレー", "millet", "コロンビア", "columbia",
    "ユニクロ", "uniqlo", "サロモン", "salomon", "オークリー", "oakley", "ラコステ", "lacoste",
    "ニューエラ", "new era", "newera", "ヘリーハンセン", "ヘリー ハンセン", "helly hansen",
    "ダントン", "danton", "マンシング", "munsingwear", "ラルフローレン", "ラルフ ローレン", "ralph lauren",
    "ゴールドウイン", "goldwin", "カリマー", "karrimor", "グレゴリー", "gregory", "オスプレイ", "osprey",
    "モンクレール", "moncler", "ミステリーランチ", "ミステリー ランチ", "mystery ranch",
    "アウトレット", "outlet", "セール", "sale", "中古", "メルカリ",
    "ゴルフ", "golf", "ワンピース", "ランチ", "キャリー", "スーツケース",
]


def pla_negatives(gclient, campaign_id: str, words: list[str] = NEGATIVES, apply: bool = False) -> dict:
    """キャンペーン単位の除外キーワード（部分一致）を追加する。すでにある語は飛ばす。"""
    have = {r.campaign_criterion.keyword.text.lower() for r in gclient.search(
        "SELECT campaign_criterion.keyword.text FROM campaign_criterion "
        f"WHERE campaign.id = {int(campaign_id)} AND campaign_criterion.type = 'KEYWORD' "
        "AND campaign_criterion.negative = TRUE AND campaign_criterion.status != 'REMOVED'")}
    add = [w for w in words if w.lower() not in have]
    plan = {"apply": apply, "campaign_id": campaign_id, "already": len(have), "add": add}
    if not apply or not add:
        return plan
    client = gclient.client
    camp = client.get_service("CampaignService").campaign_path(gclient.customer_id, campaign_id)
    ops = []
    for w in add:
        op = client.get_type("CampaignCriterionOperation")
        c = op.create
        c.campaign = camp
        c.negative = True
        c.keyword.text = w
        c.keyword.match_type = client.enums.KeywordMatchTypeEnum.BROAD
        ops.append(op)
    res = client.get_service("CampaignCriterionService").mutate_campaign_criteria(
        customer_id=gclient.customer_id, operations=ops)
    plan["added"] = len(res.results)
    return plan

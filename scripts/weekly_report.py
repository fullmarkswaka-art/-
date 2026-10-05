# -*- coding: utf-8 -*-
"""週次の広告成果レポート（Meta + Google）をPDF生成する。

使い方:
  python scripts/weekly_report.py [--until YYYY-MM-DD] [--out reports/週次レポート.pdf]

広告に詳しくない人が読んでも分かるように書く（2026-10 改訂）。ROAS は「広告1円あたりの売上」と言い換え、
判定は ◎（10円以上＝目標）○（4.5円以上＝利益が出る）△（2.2円以上＝通常品なら利益）×（それ未満）。
文章（ひとことで言うと・ポイント・次にやること・承認のお願い）は copy/weekly/<最終日>.json があれば使い、
無ければ自動で作る。

構成:
  1. 今週のまとめ … ひとことで言うと、4つの数字（前週比）、信号（今月の予算・効率・購入件数・Meta の利用上限）、
                    承認のお願い、ポイント、次にやること
  2. グラフで見る … 毎日の広告費と売上、Google と Instagram・Facebook の比較（表示・来訪も）、ブランド別
  3. 広告ごとの成績表 … 判定つき、配信先テスト、イベント広告（その週にあれば）、言葉の説明
  参考資料 … 種類別・ブランド別の表、売れた商品、カタログ広告、日別の表、点検（リンク切れ・他口座・アウトレット表示）
今週 = 最終日までの7日間（既定は昨日まで）、前週 = その前の7日間。売上は各媒体計測のCV金額（税込）。
イベント広告（targets.json の events[]）は通常運用と分けて数える。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (CondPageBreak, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from ads_manager.audit import check_url, meta_audit
from ads_manager.config import load_google_config, load_meta_config
from ads_manager.meta_ads import MetaAdsClient

_IPA = Path("/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf")
if _IPA.exists():  # プロポーショナル日本語フォント（Ø や _ の字間が崩れない）
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("IPAPGothic", str(_IPA)))
    FONT = "IPAPGothic"
else:
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    FONT = "HeiseiKakuGo-W5"
registerFontFamily(FONT, normal=FONT, bold=FONT, italic=FONT, boldItalic=FONT)  # <b> を使えるように（太字書体は無い）
NAVY = colors.HexColor("#1a3c6e"); GREY = colors.HexColor("#555555")
LIGHT = colors.HexColor("#f0f4fa"); LINE = colors.HexColor("#c8d2e0")
GOOD = colors.HexColor("#1b7f3b"); BAD = colors.HexColor("#b3261e")
WARN = colors.HexColor("#c77700"); OK = colors.HexColor("#2f6db5")
SPEND_C = colors.HexColor("#b8c4d6"); G_C = colors.HexColor("#2f6db5"); M_C = colors.HexColor("#e08a2e")

S = {
    "title": ParagraphStyle("t", fontName=FONT, fontSize=17, leading=22, spaceAfter=1 * mm),
    "sub": ParagraphStyle("s", fontName=FONT, fontSize=9, leading=12, textColor=GREY),
    "h1": ParagraphStyle("h1", fontName=FONT, fontSize=14, leading=18, spaceBefore=7 * mm,
                         spaceAfter=3 * mm, textColor=NAVY),
    "h2": ParagraphStyle("h2", fontName=FONT, fontSize=11, leading=15, spaceBefore=5 * mm,
                         spaceAfter=2 * mm, textColor=NAVY),
    "body": ParagraphStyle("b", fontName=FONT, fontSize=9, leading=14),
    "bullet": ParagraphStyle("bl", fontName=FONT, fontSize=9, leading=14, leftIndent=5 * mm,
                             bulletIndent=1 * mm),
    "sub_bullet": ParagraphStyle("sbl", fontName=FONT, fontSize=8.5, leading=13, leftIndent=11 * mm,
                                 bulletIndent=6 * mm, textColor=BAD),
    "cell": ParagraphStyle("c", fontName=FONT, fontSize=8, leading=10),
    "tile_label": ParagraphStyle("tl", fontName=FONT, fontSize=8, leading=10, textColor=GREY,
                                 alignment=1),
    "tile_value": ParagraphStyle("tv", fontName=FONT, fontSize=15, leading=18, alignment=1),
    "tile_delta": ParagraphStyle("td", fontName=FONT, fontSize=8, leading=10, alignment=1),
    "note": ParagraphStyle("n", fontName=FONT, fontSize=7.5, leading=10, textColor=GREY),
    "lead": ParagraphStyle("ld", fontName=FONT, fontSize=11, leading=17),
    "mark": ParagraphStyle("mk", fontName=FONT, fontSize=15, leading=18, alignment=1),
    "cell_c": ParagraphStyle("cc", fontName=FONT, fontSize=8, leading=10, alignment=1),
    "cell_r": ParagraphStyle("cr", fontName=FONT, fontSize=8, leading=10, alignment=2),
    "cell_s": ParagraphStyle("cs", fontName=FONT, fontSize=6.5, leading=8, textColor=GREY),
}
for _st in S.values():
    _st.wordWrap = "CJK"  # 日本語を空白でなく文字単位で折り返す（不自然な改行を防ぐ）

BRANDS = [("HOUDINI", ["フーディ", "houdini"]), ("NORRØNA", ["ノローナ", "norrona", "norrøna"]),
          ("POC", ["ポック", "poc"]), ("ACLIMA", ["アクリマ", "aclima"]),
          ("HESTRA", ["ヘストラ", "hestra"]), ("SAIL RACING", ["セイル", "sail"]),
          ("PLUS ONE WORKS", ["plus one", "pu store"]), ("KANG", ["kang"]), ("POW", ["pow"])]


def brand_of(name: str) -> str:
    n = (name or "").lower()
    for b, keys in BRANDS:
        if any(k in n for k in keys):
            return b
    if "フルマークス" in n and ("指名" in n or "sk_" in n):
        return "店舗指名（フルマークス）"
    return "全ブランド（旧・全商品カタログ等）"


def disp(name: str) -> str:
    """キャンペーン名の表示用: 運用プレフィックス（UC_SK_1_ など）を落とす。"""
    n = re.sub(r"^UC_[A-Z]{2}_\d+_", "", name or "")
    return n.replace("NORRONA", "NORRØNA").replace("_", " ")


def frame_of(name: str) -> str:
    n = (name or "").upper()
    if "UC_SK" in n or "指名" in n:
        return "指名検索"
    if "UC_PL" in n or "PLA" in n or "ショッピング" in n:
        return "ショッピング"
    if "CVS" in n or "カタログ" in n or "DPA" in n:
        return "カタログ"
    if "RTG" in n:
        return "リターゲティング（静止画）"
    if "CLK" in n:
        return "新規向け（静止画）"
    return "その他"


# ---------------- 書式 ----------------

def yen(v):
    return f"¥{v:,.0f}"


def pct(cur, prev):
    if not prev:
        return "—" if not cur else "新規"
    return f"{(cur - prev) / prev * 100:+.0f}%"


def roas(m):
    return m["rev"] / m["spend"] if m["spend"] else 0.0


def table(data, widths, align_right_from=1, font_size=8, zebra=True, header=True):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("FONT", (0, 0), (-1, -1), FONT, font_size),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("ALIGN", (align_right_from, 1 if header else 0), (-1, -1), "RIGHT"),
          ("GRID", (0, 0), (-1, -1), 0.4, LINE),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
               ("ALIGN", (0, 0), (-1, 0), "CENTER")]
    if zebra:
        st.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]))
    t.setStyle(TableStyle(st))
    return t


def kpi_tiles(cur, prev, vs="前週"):
    """使った広告費 / 広告がきっかけの売上 / 広告1円あたりの売上 / 購入件数 の4タイル（前週比付き）。"""
    items = [("使った広告費（税抜）", man(cur["spend"]), pct(cur["spend"], prev["spend"]), None),
             ("広告がきっかけの売上（税込）", man(cur["rev"]), pct(cur["rev"], prev["rev"]), True),
             ("広告1円あたりの売上", f"{roas(cur):.1f}円", f"{roas(cur) - roas(prev):+.1f}円（{vs} {roas(prev):.1f}円）", True),
             ("広告がきっかけの購入", f"{cur['cv']:.0f}件", pct(cur["cv"], prev["cv"]), True)]
    row_label, row_value, row_delta = [], [], []
    for label, value, delta, good_up in items:
        row_label.append(Paragraph(label, S["tile_label"]))
        row_value.append(Paragraph(value, S["tile_value"]))
        color = GREY
        if good_up is not None and delta not in ("—", "新規"):
            color = GOOD if delta.startswith("+") else BAD
        row_delta.append(Paragraph(f'<font color="{color.hexval()}">{vs}比 {delta}</font>', S["tile_delta"]))
    t = Table([row_label, row_value, row_delta], colWidths=[45 * mm] * 4)
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE),
                           ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
                           ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                           ("LINEBELOW", (0, 0), (-1, 0), 0, LIGHT), ("LINEBELOW", (0, 1), (-1, 1), 0, LIGHT),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return t


# ---------------- わかりやすさ（広告に詳しくない人向け） ----------------
# 判定の基準。広告1円あたりの売上（売上は税込・広告費は税抜。媒体の計測のまま）
TARGET_ROAS = 10.0     # 目標（targets.json の min_roas）
BREAK_EVEN = 4.5       # 8〜9月の売れ方（通常品とセール品が混在）で利益が出る下限。粗利50%・セール品は平均40%引き
REGULAR_BE = 2.2       # 通常品（定価販売、粗利50%）だけなら利益が出る下限

MARKS = {"◎": ("目標達成", GOOD), "○": ("利益が出ている", OK), "△": ("注意", WARN),
         "×": ("要改善", BAD), "・": ("様子見", GREY)}

GLOSSARY = [
    ("広告1円あたりの売上（ROAS）", "広告費1円に対して、広告がきっかけで何円売れたか。10円なら「1万円の広告で10万円売れた」。"
     f"目標は{TARGET_ROAS:.0f}円。{BREAK_EVEN}円を下回ると、今の売れ方（通常品とセール品が混在）では広告費の分だけ赤字になりやすい。"),
    ("広告がきっかけの売上・購入", "広告を見た／クリックした人が、その後に買った分（Google・Meta がそれぞれ計測）。"
     "売上は税込、広告費は税抜のまま比べている。お店全体の売上（受注データ・税抜）とは別物。"),
    ("表示回数・クリック", "広告が画面に出た回数と、押されてサイトに来た回数。"),
    ("1件の購入にかかった広告費", "広告費 ÷ 購入件数。安いほど効率が良い。"),
    ("ブランド名・店名で検索した人への広告", "Google で「フーディニ」「フルマークス」などと検索した人に出す広告（指名検索）。"
     "もともと買う気のある人なので効率が良いが、検索する人の数以上には増やせない。"),
    ("Googleショッピング", "Google の検索結果に商品の写真と価格を並べる広告。通常品だけを出している。"),
    ("商品カタログ広告", "Instagram・Facebook に、サイトの商品を自動で並べて出す広告。通常品だけを出している。"),
    ("写真広告（サイト訪問者・全員向け）", "Instagram・Facebook に出す1枚写真の広告。「サイト訪問者」は一度サイトに来た人、"
     "「全員向け」は Meta が買いそうな人を自動で探す配信。"),
]


def man(v) -> str:
    """金額を「12.6万円」の形に（1万円未満は「8,000円」）。"""
    if abs(v) >= 10_000_000:
        return f"{v / 10000:,.0f}万円"
    if abs(v) >= 10000:
        return f"{v / 10000:,.1f}万円"
    return f"{v:,.0f}円"


def man_s(v) -> str:
    return f"{v / 10000:.1f}万" if abs(v) >= 1000 else f"{v:,.0f}"


def judge(m, min_cv=3) -> str:
    """広告1円あたりの売上で ◎○△×（件数が少ないものは「・」様子見）。"""
    if m["spend"] <= 0:
        return "・"
    r = roas(m)
    if m["cv"] < min_cv and not (m["spend"] >= 10000 and r < REGULAR_BE):
        return "・"
    if r >= TARGET_ROAS:
        return "◎"
    if r >= BREAK_EVEN:
        return "○"
    if r >= REGULAR_BE:
        return "△"
    return "×"


def mark_cell(mark: str, with_text=False):
    label, c = MARKS[mark]
    txt = f'<font color="{c.hexval()}" size="12">{mark}</font>'
    if with_text:
        txt += f'<br/><font color="{c.hexval()}" size="6.5">{label}</font>'
    return Paragraph(txt, S["cell_c"])


def mark_legend() -> Paragraph:
    return Paragraph(
        "判定（広告1円あたりの売上）: "
        f'<font color="{GOOD.hexval()}">◎ {TARGET_ROAS:.0f}円以上＝目標達成</font>　'
        f'<font color="{OK.hexval()}">○ {BREAK_EVEN}円以上＝利益が出ている</font>　'
        f'<font color="{WARN.hexval()}">△ {REGULAR_BE}円以上＝通常品なら利益、セール品だと赤字</font>　'
        f'<font color="{BAD.hexval()}">× {REGULAR_BE}円未満＝赤字の可能性</font>　'
        "・ 購入が少なく判断保留", S["note"])


MEDIA_PLAIN = {"Google": "Google", "Meta": "Instagram・Facebook"}
FRAME_PLAIN = {"指名検索": "ブランド名・店名で検索した人（Google）", "ショッピング": "Googleショッピング（商品の写真と価格）",
               "カタログ": "商品カタログ広告（Instagram・Facebook）",
               "リターゲティング（静止画）": "写真広告・サイト訪問者＋全員向け（Instagram・Facebook）",
               "新規向け（静止画）": "写真広告・新しいお客さん向け（Instagram・Facebook）", "その他": "その他"}


def plain_name(name: str, short=False) -> str:
    """キャンペーン名を、広告に詳しくない人にも分かる言い方に（short=True は配信先の説明を省く）。"""
    n = disp(name); fr = frame_of(name); b = brand_of(name)
    if b.startswith("店舗指名") or ("フルマークス" in n and fr == "指名検索"):
        b = "フルマークス"
    if fr == "指名検索":
        return f"「{b}」で検索した人に出す広告"
    if fr == "ショッピング":
        return "Googleショッピング（通常品の写真と価格）" if "outlet" not in n.lower() else "Googleショッピング（アウトレット）"
    if fr == "カタログ":
        if "SW" in n.upper() or "JOURNEY" in n.upper():
            return f"イベント広告（{n}）"
        return "商品カタログ広告（通常品を自動で並べる）"
    if fr == "リターゲティング（静止画）":
        return f"{b} の写真広告" + ("" if short else "（サイト訪問者＋全員向け）")
    if fr == "新規向け（静止画）":
        return f"{b} の写真広告（新しいお客さん向け）"
    return n


def boxed(flowables, bg=LIGHT, border=NAVY, width=180 * mm):
    """囲み（結論や承認のお願いなど）。"""
    t = Table([[flowables]], colWidths=[width])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 3, border),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def signal_table(rows):
    """信号表。rows = [(mark, 項目, 結果, ひとこと)]"""
    data = [[mark_cell(mk, with_text=True), Paragraph(f"<b>{item}</b>", S["cell"]), Paragraph(res, S["cell"]),
             Paragraph(msg, S["cell"])] for mk, item, res, msg in rows]
    t = Table(data, colWidths=[20 * mm, 34 * mm, 50 * mm, 76 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                           ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT]),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


def roas_signal(m, label="広告1円あたりの売上") -> tuple:
    r = roas(m); mk = judge(m, min_cv=0)
    msg = {"◎": f"目標（{TARGET_ROAS:.0f}円）を達成。", "○": f"目標の{TARGET_ROAS:.0f}円には届かないが、利益は出る水準（{BREAK_EVEN}円以上）。",
           "△": f"通常品なら利益が出るが、セール品が多いと赤字になる水準（{BREAK_EVEN}円未満）。",
           "×": "広告費に見合う売上が出ていない。", "・": "まだ判断できる件数がない。"}[mk]
    return (mk, label, f"{r:.1f}円（広告 {man(m['spend'])} → 売上 {man(m['rev'])}）", msg)


def pace_signal(spent, budget, elapsed, days, label) -> tuple:
    plan = budget * elapsed / days if days else 0
    proj = spent / elapsed * days if elapsed else 0
    r = spent / plan if plan else 0
    if 0.9 <= r <= 1.1:
        mk, msg = "○", f"予定どおり。月末は {man(proj)}（予算の{proj / budget:.0%}）の見込み。"
    elif r < 0.9:
        mk, msg = "△", f"予定より少ないペース。このままだと月末は {man(proj)}（予算の{proj / budget:.0%}）で、{man(budget - proj)} 残る見込み。"
    else:
        mk, msg = "△", f"予定より速いペース。このままだと月末は {man(proj)}（予算の{proj / budget:.0%}）で、予算を超える見込み。"
    return (mk, label, f"{man(spent)} 使用／予算 {man(budget)}（{elapsed}/{days}日）", msg)


def _bar_label(d, x, y, text, size=6.5, anchor="middle", color=colors.black):
    d.add(String(x, y, text, fontName=FONT, fontSize=size, textAnchor=anchor, fillColor=color))


def chart_columns(labels, series, names, fills, width=180 * mm, height=60 * mm, value_series=(1,), fmt=man_s,
                  footnote=""):
    """縦棒グラフ（グループ）。series = [[v...], ...]。value_series の系列だけ棒の上に数値を出す。"""
    d = Drawing(width, height)
    left, bottom, top = 4 * mm, 12 * mm, 9 * mm
    pw, ph = width - left - 2 * mm, height - bottom - top
    vmax = max([max(s) for s in series if s] + [1])
    n, k = len(labels), len(series)
    gw = pw / max(n, 1); bw = gw * 0.78 / k
    d.add(Line(left, bottom, left + pw, bottom, strokeColor=LINE, strokeWidth=0.6))
    for i, lab in enumerate(labels):
        x0 = left + i * gw + gw * 0.11
        for j, s in enumerate(series):
            v = s[i]; h = ph * v / vmax if v > 0 else 0
            d.add(Rect(x0 + j * bw, bottom, bw * 0.9, h, fillColor=fills[j], strokeColor=None))
            if j in value_series and v:
                _bar_label(d, x0 + j * bw + bw * 0.45, bottom + h + 1.5, fmt(v))
        for li, part in enumerate(str(lab).split("\n")):
            _bar_label(d, left + i * gw + gw / 2, bottom - 4 * mm - li * 3 * mm, part, size=7)
    x = left
    for nm, fc in zip(names, fills):
        d.add(Rect(x, height - 5 * mm, 3 * mm, 3 * mm, fillColor=fc, strokeColor=None))
        _bar_label(d, x + 4 * mm, height - 4.6 * mm, nm, size=7.5, anchor="start"); x += 8 * mm + len(nm) * 3 * mm
    if footnote:
        _bar_label(d, width - 2 * mm, height - 4.6 * mm, footnote, size=6.5, anchor="end", color=GREY)
    return d


def chart_hbars(rows, width=180 * mm, label_w=48 * mm, text_w=58 * mm, fill=NAVY, row_h=6.2 * mm):
    """横棒グラフ。rows = [(ラベル, 値, 右に出す文字, 色 or None)]"""
    rows = list(rows)
    d = Drawing(width, row_h * len(rows) + 2)
    vmax = max([r[1] for r in rows] + [1])
    bar_w = width - label_w - text_w
    for i, (lab, v, txt, fc) in enumerate(rows):
        y = d.height - (i + 1) * row_h
        _bar_label(d, 0, y + 2.2 * mm, lab, size=8, anchor="start")
        w = bar_w * max(v, 0) / vmax
        d.add(Rect(label_w, y + 1.2 * mm, max(w, 0.5), row_h - 2.2 * mm, fillColor=fc or fill, strokeColor=None))
        _bar_label(d, label_w + w + 2, y + 2.2 * mm, txt, size=7.5, anchor="start")
    return d


def chart_progress(rows, width=180 * mm, label_w=48 * mm, text_w=58 * mm, row_h=8 * mm):
    """進み具合バー。rows = [(ラベル, 実績, 目標, 目安線(0〜1 or None), 右の文字)]。目標を100%として塗る。"""
    d = Drawing(width, row_h * len(rows) + 2)
    bar_w = width - label_w - text_w
    for i, (lab, act, tgt, marker, txt) in enumerate(rows):
        y = d.height - (i + 1) * row_h
        _bar_label(d, 0, y + 3 * mm, lab, size=8, anchor="start")
        d.add(Rect(label_w, y + 1.5 * mm, bar_w, row_h - 3 * mm, fillColor=colors.HexColor("#e6ebf2"), strokeColor=None))
        r = act / tgt if tgt else 0
        fc = GOOD if r >= 1 else (OK if marker is None or r >= (marker or 0) * 0.9 else WARN)
        d.add(Rect(label_w, y + 1.5 * mm, bar_w * min(r, 1.0), row_h - 3 * mm, fillColor=fc, strokeColor=None))
        if r > 1:
            _bar_label(d, label_w + bar_w - 2, y + 3 * mm, "目標超え", size=6.5, anchor="end", color=colors.white)
        if marker:
            mx = label_w + bar_w * marker
            d.add(Line(mx, y + 0.5 * mm, mx, y + row_h - 0.5 * mm, strokeColor=BAD, strokeWidth=1))
        _bar_label(d, label_w + bar_w + 3, y + 3 * mm, txt, size=7.5, anchor="start")
    return d


def media_compare(g, m, g_note="探している人に出す（検索・ショッピング）", m_note="まだ探していない人にも見せる（SNS）"):
    """Google と Instagram・Facebook を、購入以外の成果（表示・来訪）も含めて並べる。"""
    def per(a, b, unit=1):
        return a / b * unit if b else 0
    rows = [("役割", g_note, m_note),
            ("使った広告費", man(g["spend"]), man(m["spend"])),
            ("広告が表示された回数", f"{g['imp']:,}回", f"{m['imp']:,}回"),
            ("サイトに来た回数（クリック）", f"{g['link']:,}回", f"{m['link']:,}回"),
            ("表示100回あたりの来訪", f"{per(g['link'], g['imp'], 100):.1f}回", f"{per(m['link'], m['imp'], 100):.1f}回"),
            ("1回の来訪にかかった広告費", f"{per(g['spend'], g['link']):,.0f}円", f"{per(m['spend'], m['link']):,.0f}円"),
            ("広告がきっかけの購入", f"{g['cv']:.0f}件", f"{m['cv']:.0f}件"),
            ("1件の購入にかかった広告費", f"{per(g['spend'], g['cv']):,.0f}円" if g["cv"] else "—",
             f"{per(m['spend'], m['cv']):,.0f}円" if m["cv"] else "—"),
            ("広告1円あたりの売上", f"{roas(g):.1f}円", f"{roas(m):.1f}円")]
    data = [["", "Google", "Instagram・Facebook（Meta）"]] + [
        [Paragraph(a, S["cell"]), Paragraph(b, S["cell_c"]), Paragraph(c, S["cell_c"])] for a, b, c in rows]
    data.append([Paragraph("判定", S["cell"]), mark_cell(judge(g), True), mark_cell(judge(m), True)])
    t = table(data, [56 * mm, 62 * mm, 62 * mm])
    t.setStyle(TableStyle([("ALIGN", (1, 1), (-1, -1), "CENTER")]))
    return t


def glossary_table():
    data = [[Paragraph(f"<b>{a}</b>", S["cell"]), Paragraph(b, S["cell"])] for a, b in GLOSSARY]
    t = Table(data, colWidths=[52 * mm, 128 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                           ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT]),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def scorecard(rows, prev_rows=None, vs="前週"):
    """広告ごとの成績表（媒体を混ぜて広告費の多い順、判定つき）。rows = [(media, campaign dict)]"""
    prev = {c["id"]: c for c in (prev_rows or [])}
    data = [["判定", "広告", "広告費", "購入", "売上", "1円あたり", f"{vs}の\n1円あたり"]]
    for media, c in sorted(rows, key=lambda x: -x[1]["spend"]):
        if c["spend"] < 100:
            continue
        p = prev.get(c["id"])
        name = Paragraph(f"{plain_name(c['name'])}<br/><font size='6.5' color='{GREY.hexval()}'>"
                         f"{MEDIA_PLAIN.get(media, media)}｜{disp(c['name'])}</font>", S["cell"])
        data.append([mark_cell(judge(c)), name, yen(c["spend"]), f"{c['cv']:.0f}件",
                     yen(c["rev"]) if c["rev"] else "—", f"{roas(c):.1f}円",
                     f"{roas(p):.1f}円" if p and p["spend"] else "—"])
    t = table(data, [12 * mm, 74 * mm, 20 * mm, 13 * mm, 22 * mm, 18 * mm, 21 * mm], align_right_from=2)
    t.setStyle(TableStyle([("ALIGN", (0, 1), (0, -1), "CENTER")]))
    return t


# ---------------- データ取得 ----------------

def _meta_actions(row, key, values=False):
    for a in row.get("action_values" if values else "actions") or []:
        if a["action_type"] == key:
            return float(a["value"])
    return 0.0


def _mm(row):
    return {"spend": float(row.get("spend") or 0), "imp": int(row.get("impressions") or 0),
            "clicks": int(row.get("clicks") or 0), "link": int(row.get("inline_link_clicks") or 0),
            "cv": _meta_actions(row, "omni_purchase"),
            "rev": _meta_actions(row, "omni_purchase", values=True)}


def meta_data(client, since, until):
    acct = client.config.ad_account_id
    tr = json.dumps({"since": str(since), "until": str(until)})
    f = "campaign_id,campaign_name,ad_id,ad_name,impressions,clicks,inline_link_clicks,spend,actions,action_values"
    camps = [{"id": r["campaign_id"], "name": r["campaign_name"], **_mm(r)}
             for r in client.get_all(f"{acct}/insights", level="campaign", time_range=tr, fields=f, limit=200)]
    ads = [{"id": r["ad_id"], "name": r["ad_name"], "campaign": r["campaign_name"], **_mm(r)}
           for r in client.get_all(f"{acct}/insights", level="ad", time_range=tr, fields=f, limit=500)]
    daily = {r["date_start"]: _mm(r) for r in client.get_all(
        f"{acct}/insights", level="account", time_range=tr, time_increment=1, fields=f, limit=100)}
    return camps, ads, daily


def _gm(m):
    return {"spend": m.cost_micros / 1e6, "imp": m.impressions, "clicks": m.clicks, "link": m.clicks,
            "cv": m.conversions, "rev": m.conversions_value}


def google_data(client, since, until):
    where = f"segments.date BETWEEN '{since}' AND '{until}'"
    f = "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value"
    camps = []
    for r in client.search(f"SELECT campaign.id, campaign.name, {f} FROM campaign WHERE {where}"):
        m = _gm(r.metrics)
        if m["imp"] or m["spend"]:
            camps.append({"id": str(r.campaign.id), "name": r.campaign.name, **m})
    daily = {}
    for r in client.search(f"SELECT segments.date, {f} FROM customer WHERE {where}"):
        daily[r.segments.date] = _gm(r.metrics)
    shop_brand = defaultdict(lambda: {"spend": 0.0, "imp": 0, "clicks": 0, "cv": 0.0, "rev": 0.0})
    products = defaultdict(lambda: {"title": "", "brand": "", "spend": 0.0, "clicks": 0, "cv": 0.0, "rev": 0.0})
    labels = defaultdict(lambda: defaultdict(int))  # label -> campaign -> imp
    for r in client.search(
            "SELECT campaign.id, campaign.name, segments.product_item_id, segments.product_title, "
            "segments.product_brand, segments.product_custom_attribute0, "
            f"{f} FROM shopping_performance_view WHERE {where}"):
        m = _gm(r.metrics)
        b = (r.segments.product_brand or "").upper().replace("NORRONA", "NORRØNA") or "ショッピング（ブランド属性なし）"
        for k in ("spend", "imp", "clicks", "cv", "rev"):
            shop_brand[b][k] += m[k]
        p = products[r.segments.product_item_id]
        p["title"] = r.segments.product_title; p["brand"] = b
        p["spend"] += m["spend"]; p["clicks"] += m["clicks"]; p["cv"] += m["cv"]; p["rev"] += m["rev"]
        labels[r.segments.product_custom_attribute0 or "（ラベルなし）"][r.campaign.name] += m["imp"]
    return camps, daily, shop_brand, products, labels


def total_of(rows):
    t = {"spend": 0.0, "imp": 0, "clicks": 0, "link": 0, "cv": 0.0, "rev": 0.0}
    for r in rows:
        for k in t:
            t[k] += r.get(k, 0)
    return t


# ---------------- 集計 ----------------

def by_brand(g_camps, g_shop_brand, m_ads):
    """ブランド別（広告経由）。指名検索/静止画はキャンペーン名、ショッピングは商品ブランド、
    カタログは広告名（fullmarks-dpa-<BRAND>）から判定する。"""
    agg = defaultdict(lambda: {"spend": 0.0, "cv": 0.0, "rev": 0.0})
    for c in g_camps:
        if frame_of(c["name"]) == "ショッピング":
            continue  # 商品ブランド別で計上
        b = brand_of(c["name"])
        for k in ("spend", "cv", "rev"):
            agg[b][k] += c[k]
    for b, m in g_shop_brand.items():
        for k in ("spend", "cv", "rev"):
            agg[b][k] += m[k]
    for a in m_ads:
        b = brand_of(a["name"]) if frame_of(a["campaign"]) == "カタログ" else brand_of(a["campaign"])
        for k in ("spend", "cv", "rev"):
            agg[b][k] += a[k]
    return agg


def by_frame(g_camps, m_camps):
    agg = defaultdict(lambda: {"spend": 0.0, "cv": 0.0, "rev": 0.0})
    for c in g_camps + m_camps:
        fr = frame_of(c["name"])
        for k in ("spend", "cv", "rev"):
            agg[fr][k] += c[k]
    return agg


def plain_points(brand_cur, camps_cur, camps_prev, vs="前週"):
    """ポイント（自動生成、文章が無いとき用）。専門用語を使わずに書く。"""
    lines = []
    top = [(b, m) for b, m in sorted(brand_cur.items(), key=lambda kv: -kv[1]["rev"]) if m["rev"]][:3]
    if top:
        lines.append("よく売れたブランド: " + "、".join(
            f"{b.replace('店舗指名（フルマークス）', '店名検索')} {man(m['rev'])}（購入{m['cv']:.0f}件）" for b, m in top))
    good = [c for c in camps_cur if judge(c) in ("◎", "○")]
    if good:
        c = max(good, key=lambda c: c["rev"])
        lines.append(f"よく効いた広告: {plain_name(c['name'])}（広告 {man(c['spend'])} → 売上 {man(c['rev'])}、1円あたり {roas(c):.1f}円）")
    weak = [c for c in camps_cur if c["spend"] >= 5000 and judge(c) in ("△", "×")]
    for c in sorted(weak, key=lambda c: -c["spend"])[:3]:
        lines.append(f"広告費のわりに売れていない: {plain_name(c['name'])}（広告 {man(c['spend'])} → 売上 {man(c['rev'])}、"
                     f"1円あたり {roas(c):.1f}円）")
    prev_by = {c["id"]: c for c in camps_prev}
    for c in camps_cur:
        p = prev_by.get(c["id"])
        if p and p["spend"] >= 3000 and c["spend"] >= 3000 and abs(roas(c) - roas(p)) >= 3:
            word = "良くなった" if roas(c) > roas(p) else "悪くなった"
            lines.append(f"{vs}から{word}: {plain_name(c['name'])}（1円あたり {roas(p):.1f}円 → {roas(c):.1f}円）")
    return lines


# ---------------- セクション ----------------

def sec_brand(brand_cur, brand_prev):
    data = [["ブランド", "広告費", "購入", "売上", "ROAS", "前週売上", "前週比"]]
    for b, m in sorted(brand_cur.items(), key=lambda kv: -kv[1]["rev"]):
        p = brand_prev.get(b, {"spend": 0, "cv": 0, "rev": 0})
        data.append([b, yen(m["spend"]), f"{m['cv']:.0f}", yen(m["rev"]) if m["rev"] else "—",
                     f"{roas(m):.1f}" if m["rev"] else "—", yen(p["rev"]) if p["rev"] else "—",
                     pct(m["rev"], p["rev"])])
    t = total_of([dict(imp=0, clicks=0, **m) for m in brand_cur.values()])
    data.append(["合計", yen(t["spend"]), f"{t['cv']:.0f}", yen(t["rev"]), f"{roas(t):.1f}", "", ""])
    tb = table(data, [42 * mm, 24 * mm, 14 * mm, 26 * mm, 16 * mm, 26 * mm, 18 * mm])
    tb.setStyle(TableStyle([("FONT", (0, len(data) - 1), (-1, len(data) - 1), FONT, 8),
                            ("BACKGROUND", (0, len(data) - 1), (-1, len(data) - 1), colors.HexColor("#dfe7f3"))]))
    return tb


def sec_frame(frame_cur, frame_prev, vs="前週"):
    data = [["判定", "広告の種類", "広告費", "購入", "売上", "1円あたり", vs]]
    for f, m in sorted(frame_cur.items(), key=lambda kv: -kv[1]["spend"]):
        p = frame_prev.get(f, {"spend": 0, "cv": 0, "rev": 0})
        data.append([mark_cell(judge(m)), Paragraph(FRAME_PLAIN.get(f, f), S["cell"]), yen(m["spend"]), f"{m['cv']:.0f}件",
                     yen(m["rev"]) if m["rev"] else "—", f"{roas(m):.1f}円", f"{roas(p):.1f}円" if p["spend"] else "—"])
    t = table(data, [12 * mm, 66 * mm, 22 * mm, 14 * mm, 24 * mm, 20 * mm, 22 * mm], align_right_from=2)
    t.setStyle(TableStyle([("ALIGN", (0, 1), (0, -1), "CENTER")]))
    return t


def sec_products(products):
    sold = [p for p in products.values() if p["cv"] >= 1]
    if not sold:
        return Paragraph("今週、Googleショッピング広告からの購入はありませんでした。", S["body"])
    data = [["商品", "ブランド", "クリック", "広告費", "購入", "売上"]]
    for p in sorted(sold, key=lambda p: -p["rev"])[:15]:
        data.append([Paragraph(p["title"][:40], S["cell"]), p["brand"], f"{p['clicks']}", yen(p["spend"]),
                     f"{p['cv']:.0f}", yen(p["rev"])])
    return table(data, [66 * mm, 26 * mm, 16 * mm, 20 * mm, 12 * mm, 26 * mm])


def sec_catalog_ads(m_ads, m_ads_prev):
    rows = [a for a in m_ads if frame_of(a["campaign"]) == "カタログ" and a["spend"] > 0]
    if not rows:
        return Paragraph("今週、Metaカタログ広告の配信はありませんでした。", S["body"])
    prev = {a["id"]: a for a in m_ads_prev}
    data = [["広告（ブランド／シリーズ）", "広告費", "表示", "購入", "売上", "ROAS", "前週売上"]]
    for a in sorted(rows, key=lambda a: -a["spend"]):
        label = re.sub(r"^fullmarks-dpa-", "", a["name"]).replace("NORRONA_", "NORRØNA ")
        p = prev.get(a["id"], {"rev": 0})
        data.append([label, yen(a["spend"]), f"{a['imp']:,}", f"{a['cv']:.0f}",
                     yen(a["rev"]) if a["rev"] else "—", f"{roas(a):.1f}" if a["rev"] else "—",
                     yen(p["rev"]) if p["rev"] else "—"])
    return table(data, [46 * mm, 22 * mm, 18 * mm, 12 * mm, 24 * mm, 14 * mm, 24 * mm])


def _event_ids():
    """イベント枠の Meta キャンペーン（終わった企画も含む。前週・前月との比較で通常運用に混ざらないように）。"""
    p = Path(__file__).resolve().parent.parent / "targets.json"
    try:
        t = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return set()
    ids = set(t.get("event_campaign_ids", []))
    for e in t.get("events", []):
        ids |= set(e.get("meta_campaign_ids", []))
    return ids


EVENT_IDS = _event_ids()


def sec_campaigns(cur, prev_rows):
    prev = {c["id"]: c for c in prev_rows}
    data = [["キャンペーン", "広告費", "前週比", "購入", "売上", "ROAS", "前週ROAS"]]
    for c in sorted(cur, key=lambda c: -c["spend"]):
        if c["spend"] <= 0:
            continue
        p = prev.get(c["id"], {"spend": 0, "cv": 0, "rev": 0})
        label = disp(c["name"]) + ("【イベント枠】" if c["id"] in EVENT_IDS else "")
        data.append([Paragraph(label, S["cell"]), yen(c["spend"]), pct(c["spend"], p["spend"]),
                     f"{c['cv']:.0f}", yen(c["rev"]) if c["rev"] else "—",
                     f"{roas(c):.1f}" if c["rev"] else "—", f"{roas(p):.1f}" if p["rev"] else "—"])
    cur_ids = {c["id"] for c in cur if c["spend"] > 0}
    for p in sorted(prev_rows, key=lambda r: -r["spend"]):
        if p["id"] not in cur_ids and p["spend"] > 0:
            data.append([Paragraph(disp(p["name"]) + "（今週配信なし）", S["cell"]), "¥0", pct(0, p["spend"]),
                         "0", "—", "—", f"{roas(p):.1f}" if p["rev"] else "—"])
    return table(data, [62 * mm, 22 * mm, 16 * mm, 12 * mm, 24 * mm, 14 * mm, 18 * mm])


def sec_daily(g_daily, m_daily, since, until):
    data = [["日付", "曜", "Google 費用", "Google 売上", "Meta 費用", "Meta 売上", "合計費用", "合計売上", "ROAS"]]
    d = since
    tot = defaultdict(float)
    while d <= until:
        k = d.isoformat(); g = g_daily.get(k, {"spend": 0, "rev": 0}); m = m_daily.get(k, {"spend": 0, "rev": 0})
        sp, rv = g["spend"] + m["spend"], g["rev"] + m["rev"]
        tot["gs"] += g["spend"]; tot["gr"] += g["rev"]; tot["ms"] += m["spend"]; tot["mr"] += m["rev"]
        data.append([k, "月火水木金土日"[d.weekday()], yen(g["spend"]), yen(g["rev"]), yen(m["spend"]), yen(m["rev"]),
                     yen(sp), yen(rv), f"{rv / sp:.1f}" if sp else "—"])
        d += timedelta(days=1)
    sp, rv = tot["gs"] + tot["ms"], tot["gr"] + tot["mr"]
    data.append(["合計", "", yen(tot["gs"]), yen(tot["gr"]), yen(tot["ms"]), yen(tot["mr"]), yen(sp), yen(rv),
                 f"{rv / sp:.1f}" if sp else "—"])
    tb = table(data, [22 * mm, 8 * mm, 20 * mm, 22 * mm, 20 * mm, 22 * mm, 20 * mm, 22 * mm, 12 * mm], align_right_from=2)
    tb.setStyle(TableStyle([("BACKGROUND", (0, len(data) - 1), (-1, len(data) - 1), colors.HexColor("#dfe7f3"))]))
    return tb


def month_to_date(meta_client, google_client, today):
    """今月1日〜昨日の通常運用・イベント枠の実績と、Meta の利用上限。"""
    p = Path(__file__).resolve().parent.parent / "targets.json"
    if not p.exists():
        return None
    t = json.loads(p.read_text(encoding="utf-8"))
    ms = today.replace(day=1); until = today - timedelta(days=1)
    if until < ms:
        return None
    m_c, _, _ = meta_data(meta_client, ms, until)
    g_c = google_data(google_client, ms, until)[0] if google_client else []
    normal_m = total_of([c for c in m_c if c["id"] not in EVENT_IDS])
    out = {"since": ms, "until": until, "elapsed": (until - ms).days + 1,
           "days": (ms.replace(month=ms.month % 12 + 1, year=ms.year + (ms.month == 12)) - timedelta(days=1)).day,
           "normal": total_of([normal_m] + g_c), "meta": normal_m,
           "event": total_of([c for c in m_c if c["id"] in EVENT_IDS]),
           "budget": t.get("normal_budget_ex_tax", t["monthly_budget_ex_tax"] - t.get("event_reserve", 0))}
    try:
        acc = meta_client.get(meta_client.config.ad_account_id, fields="spend_cap,amount_spent")
        out["cap"], out["cap_spent"] = float(acc.get("spend_cap") or 0), float(acc.get("amount_spent") or 0)
    except Exception:
        out["cap"] = 0
    return out


def cap_signal(mtd) -> tuple | None:
    """Meta の利用上限（毎月1日に使用額をリセットする運用）に月末前に届くか。"""
    if not mtd or not mtd.get("cap"):
        return None
    cap, spent = mtd["cap"], mtd["cap_spent"]
    rate = mtd["meta"]["spend"] / mtd["elapsed"] if mtd["elapsed"] else 0
    left_days = mtd["days"] - mtd["elapsed"]
    proj = spent + rate * left_days
    res = f"{man(spent)} 使用／上限 {man(cap)}"
    if spent >= cap * 0.99:
        return ("×", "Meta の利用上限", res, "上限に達していて、Instagram・Facebook の広告が止まっている。")
    if proj > cap and rate:
        hit = mtd["until"] + timedelta(days=int((cap - spent) / rate) + 1)
        return ("△", "Meta の利用上限", res, f"今のペースだと {hit.month}/{hit.day} ごろに上限に届き、広告が止まる見込み。月末前に相談。")
    return ("○", "Meta の利用上限", res, f"今のペースなら月末まで止まらない（月末に約 {man(proj)}）。")


def sec_event(meta_client, google_client, today):
    """イベント枠（EC企画）: 企画ごとに Meta キャンペーン／Google プロモーション アセットを別建てで集計。"""
    from ads_manager.event_report import event_summary, load_events
    out = []
    for ev in load_events():
        if date.fromisoformat(ev["start"]) > today - timedelta(days=1):
            continue
        sm = event_summary(meta_client, google_client, ev, today - timedelta(days=1))
        data = [["媒体", "キャンペーン／アセット", "広告費", "表示", "クリック", "購入", "売上", "ROAS"]]
        for r in sm["rows"]:
            data.append([r["media"], Paragraph(disp(r["name"]), S["cell"]), yen(r["spend"]), f"{r['imp']:,}",
                         f"{r['clicks']:,}", f"{r['cv']:.0f}", yen(r["rev"]) if r["rev"] else "—",
                         f"{r['rev'] / r['spend']:.1f}" if r["spend"] and r["rev"] else "—"])
        t = sm["total"]
        data.append(["", "合計", yen(t["spend"]), "", "", f"{t['cv']:.0f}", yen(t["rev"]) if t["rev"] else "—",
                     f"{t['rev'] / t['spend']:.1f}" if t["spend"] and t["rev"] else "—"])
        tb = table(data, [14 * mm, 62 * mm, 20 * mm, 16 * mm, 16 * mm, 12 * mm, 22 * mm, 14 * mm], align_right_from=2)
        tb.setStyle(TableStyle([("BACKGROUND", (0, len(data) - 1), (-1, len(data) - 1), colors.HexColor("#dfe7f3"))]))
        title = f"{ev['label']}（{ev['start']}〜{ev['end']}、集計 {sm['since']}〜{sm['until']}）"
        note = (f"イベント予算（税抜）{yen(sm['reserve'])} に対する Meta 消化 {yen(sm['meta_spend'])}"
                f"（{sm['meta_spend'] / sm['reserve']:.0%}）。" if sm["reserve"] else "") + sm["note"]
        out += [KeepTogether([Paragraph(title, S["h2"]), tb]), Paragraph(note, S["note"])]
    return out


def sec_adset_compare(meta_client, since, until):
    """同じキャンペーン内に広告セットが複数あるもの（全員向け vs 絞った配信の比較テスト）を並べる。"""
    acct = meta_client.config.ad_account_id
    tr = json.dumps({"since": str(since), "until": str(until)})
    rows = meta_client.get_all(f"{acct}/insights", level="adset", time_range=tr, limit=200,
                               fields="campaign_id,campaign_name,adset_name,spend,impressions,reach,frequency,clicks,actions,action_values")
    by = defaultdict(list)
    for r in rows:
        m = _mm(r)
        if m["spend"] > 0:
            by[r["campaign_id"]].append({"camp": r["campaign_name"], "adset": r["adset_name"],
                                         "freq": float(r.get("frequency") or 0), **m})
    data = [["判定", "広告／配信先", "広告費", "1人あたり表示", "購入", "売上", "1円あたり"]]
    for cid, lst in by.items():
        if len(lst) < 2 or cid in EVENT_IDS:
            continue
        for x in sorted(lst, key=lambda x: -x["spend"]):
            who = "全員向け（Meta が自動で探す）" if "全員" in x["adset"] else "サイト訪問者など（絞った配信）"
            label = f"{plain_name(x['camp'], short=True)}<br/><font size='6.5' color='{GREY.hexval()}'>配信先: {who}</font>"
            data.append([mark_cell(judge(x)), Paragraph(label, S["cell"]), yen(x["spend"]), f"{x['freq']:.1f}回",
                         f"{x['cv']:.0f}件", yen(x["rev"]) if x["rev"] else "—", f"{roas(x):.1f}円"])
    if len(data) == 1:
        return None
    t = table(data, [12 * mm, 72 * mm, 20 * mm, 22 * mm, 14 * mm, 22 * mm, 18 * mm], align_right_from=2)
    t.setStyle(TableStyle([("ALIGN", (0, 1), (0, -1), "CENTER")]))
    return t


def sec_audit(meta_client, google_client, g_labels):
    lines = []
    audit = meta_audit(meta_client, check_links=True)
    broken = [r for r in audit["問題のある広告"] if any("リンク切れ" in f or "リダイレクト" in f for f in r["flags"])]
    lines.append(f"Meta: 配信中 {audit['summary']['調査対象']}本のリンクを検査 → リンク切れ {len(broken)}件")
    lines += [f"　※ {r['campaign']} / {r['ad_name']}: " + "; ".join(r["flags"]) for r in broken]
    if google_client:
        try:
            from ads_manager.creatives import google_list_creatives
            g_all = google_list_creatives(google_client)
            g_ads = [a for a in g_all if a["serving"]]
            g_broken = []
            for a in g_ads:
                for url in a["final_urls"]:
                    res = check_url(url)
                    if res["status"] is not None and res["status"] >= 400:
                        g_broken.append(f"{a['campaign']} / {a['ad_id']}: {url} ({res['status']})")
            lines.append(f"Google: 配信中 {len(g_ads)}本のリンクを検査 → リンク切れ {len(g_broken)}件"
                         f"（停止中キャンペーンの広告 {len(g_all) - len(g_ads)}本は対象外。再開時は要リンク確認）")
            lines += [f"　※ {b}" for b in g_broken]
        except Exception as e:
            lines.append(f"Google: リンク確認を実行できませんでした（{type(e).__name__}）")
        by_c = g_labels.get("outlet", {}); out = sum(by_c.values())
        lines.append(f"アウトレット品のショッピング表示: {out:,}回（方針: アウトレット品は広告しない）")
        if out:
            lines += [f"　※ {disp(c)}: {n:,}回（停止済みの枠なら停止前の表示。稼働中なら除外設定を確認）"
                      for c, n in sorted(by_c.items(), key=lambda kv: -kv[1]) if n]
    # 他口座
    try:
        other = []
        for acct, name in [("act_587527895389459", "フルマークス/MDX"), ("act_719498040184021", "認知施策用/MDX")]:
            d = meta_client.get(f"{acct}/insights", fields="spend", date_preset="this_month").get("data", [])
            other.append(f"{name} {yen(float(d[0]['spend']) if d else 0)}")
        lines.append("他口座の当月消化（回してはいけない口座）: " + "、".join(other))
    except Exception as e:
        lines.append(f"他口座の消化確認: 取得できませんでした（{type(e).__name__}）")
    return [Paragraph(l.lstrip("　").lstrip("※ "), S["bullet"] if not l.startswith("　") else S["sub_bullet"],
                      bulletText="■" if not l.startswith("　") else "※") for l in lines]


# ---------------- main ----------------

def _narrative(until: date) -> dict:
    """copy/weekly/<最終日>.json（任意）: conclusion / points / next / asks。無ければ自動の文章を使う。"""
    p = Path(__file__).resolve().parent.parent / "copy" / "weekly" / f"{until}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def daily_chart(g_daily, m_daily, since, until, ev_daily=None):
    labels, sp, rv = [], [], []
    d = since
    while d <= until:
        k = d.isoformat(); g = g_daily.get(k, {}); m = m_daily.get(k, {}); e = (ev_daily or {}).get(k, {})
        labels.append(f"{d.month}/{d.day}\n({'月火水木金土日'[d.weekday()]})")
        sp.append(g.get("spend", 0) + m.get("spend", 0) - e.get("spend", 0))
        rv.append(g.get("rev", 0) + m.get("rev", 0) - e.get("rev", 0))
        d += timedelta(days=1)
    return chart_columns(labels, [sp, rv], ["広告費", "広告がきっかけの売上"], [SPEND_C, NAVY],
                         value_series=(0, 1), footnote="単位: 万円")


def brand_chart(brand):
    rows = []
    for b, m in sorted(brand.items(), key=lambda kv: -kv[1]["rev"]):
        if m["spend"] < 500 and not m["rev"]:
            continue
        label = "店名検索（フルマークス）" if b.startswith("店舗指名") else ("イベント・旧カタログ" if b.startswith("全ブランド") else b)
        mk = judge(m)
        txt = (f"{man(m['rev'])}　広告 {man(m['spend'])}・1円あたり {roas(m):.1f}円 {mk if mk != '・' else ''}"
               if m["rev"] else f"購入なし（広告 {man(m['spend'])}）")
        rows.append((label[:16], m["rev"], txt, MARKS[mk][1] if mk != "・" else SPEND_C))
    return chart_hbars(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--until", default=None, help="週の最終日（既定: 昨日）")
    args = ap.parse_args()
    cu = date.fromisoformat(args.until) if args.until else date.today() - timedelta(days=1)
    today = cu + timedelta(days=1)
    cs = cu - timedelta(days=6)
    ps, pu = cs - timedelta(days=7), cs - timedelta(days=1)
    out = Path(args.out or f"reports/広告週次レポート_{today}.pdf")

    meta_client = MetaAdsClient(load_meta_config())
    m_camps_all, m_ads_all, m_daily = meta_data(meta_client, cs, cu)
    m_camps_p_all, m_ads_p_all, _ = meta_data(meta_client, ps, pu)
    google_client = None
    g_camps = g_camps_p = []; g_daily = {}; g_shop = {}; g_shop_p = {}; g_products = {}; g_labels = {}
    g_err = None
    try:
        from ads_manager.google_ads_client import GoogleAdsClientWrapper
        google_client = GoogleAdsClientWrapper(load_google_config())
        g_camps, g_daily, g_shop, g_products, g_labels = google_data(google_client, cs, cu)
        g_camps_p, _, g_shop_p, _, _ = google_data(google_client, ps, pu)
    except Exception as e:
        g_err = f"{type(e).__name__}"; google_client = None

    # イベント枠（EC企画）は通常運用と分けて見る
    m_camps = [c for c in m_camps_all if c["id"] not in EVENT_IDS]
    m_camps_p = [c for c in m_camps_p_all if c["id"] not in EVENT_IDS]
    ev_cur = [c for c in m_camps_all if c["id"] in EVENT_IDS and c["spend"] > 0]
    ev_names = {c["name"] for c in m_camps_all + m_camps_p_all if c["id"] in EVENT_IDS}
    m_ads = [a for a in m_ads_all if a["campaign"] not in ev_names]
    m_ads_p = [a for a in m_ads_p_all if a["campaign"] not in ev_names]
    ev_daily = {}
    if ev_cur:
        tr = json.dumps({"since": str(cs), "until": str(cu)})
        for r in meta_client.get_all(f"{meta_client.config.ad_account_id}/insights", level="campaign", time_increment=1,
                                     time_range=tr, fields="campaign_id,spend,actions,action_values", limit=200):
            if r["campaign_id"] in EVENT_IDS:
                ev_daily[r["date_start"]] = total_of([ev_daily.get(r["date_start"], {}), _mm(r)])

    cur = total_of(g_camps + m_camps); prev = total_of(g_camps_p + m_camps_p)
    g_tot, m_tot = total_of(g_camps), total_of(m_camps)
    brand_cur = by_brand(g_camps, g_shop, m_ads); brand_prev = by_brand(g_camps_p, g_shop_p, m_ads_p)
    frame_cur = by_frame(g_camps, m_camps); frame_prev = by_frame(g_camps_p, m_camps_p)
    camps_cur = [("Google", c) for c in g_camps] + [("Meta", c) for c in m_camps]
    narr = _narrative(cu)
    mtd = month_to_date(meta_client, google_client, today)

    story = [Paragraph("広告 週次レポート", S["title"]),
             Paragraph(f"対象: {cs.month}/{cs.day}〜{cu.month}/{cu.day}（前週 {ps.month}/{ps.day}〜{pu.month}/{pu.day}）　"
                       "FULLMARKS STORE の Google広告 + Instagram・Facebook広告（Meta）。"
                       "イベント広告は別枠（このページの数字には含めない）。", S["sub"]), Spacer(1, 3 * mm)]
    if g_err:
        story.append(Paragraph(f"※ Google広告に接続できなかったため Google の数値は含まれていません（{g_err}）", S["body"]))

    # 1ページ目: まとめ
    story.append(Paragraph("1. 今週のまとめ", S["h1"]))
    concl = narr.get("conclusion") or (
        f"今週は広告費 {man(cur['spend'])} で、広告がきっかけの売上は {man(cur['rev'])}（購入 {cur['cv']:.0f}件）。"
        f"広告1円あたり {roas(cur):.1f}円で、前週の {roas(prev):.1f}円より"
        f"{'良くなった' if roas(cur) >= roas(prev) else '下がった'}。")
    story.append(boxed([Paragraph("ひとことで言うと", S["note"]), Paragraph(concl, S["lead"])]))
    story.append(Spacer(1, 3 * mm))
    story.append(kpi_tiles(cur, prev))
    sig = [roas_signal(cur, "今週の効率（広告1円あたりの売上）")]
    d_cv = (cur["cv"] - prev["cv"]) / prev["cv"] if prev["cv"] else 0
    sig.append(("○" if d_cv >= -0.1 else "△", "今週の購入件数", f"{cur['cv']:.0f}件（前週 {prev['cv']:.0f}件、{pct(cur['cv'], prev['cv'])}）",
                "前週と同じか増えている。" if d_cv >= -0.1 else "前週より減っている。理由は下の「ポイント」を参照。"))
    if mtd:
        sig.insert(0, pace_signal(mtd["normal"]["spend"], mtd["budget"], mtd["elapsed"], mtd["days"],
                                  f"今月の広告費（{mtd['since'].month}月）"))
        cs_ = cap_signal(mtd)
        if cs_:
            sig.append(cs_)
    story.append(Paragraph("信号（○は問題なし、△×は対応が必要）", S["h2"]))
    story.append(signal_table(sig))
    if narr.get("asks"):
        story.append(boxed([Paragraph("承認をお願いしたいこと", S["h2"])] +
                            [Paragraph(x, S["bullet"], bulletText=f"{i}.") for i, x in enumerate(narr["asks"], 1)],
                           bg=colors.HexColor("#fff6e8"), border=WARN))
    story.append(Paragraph("今週のポイント", S["h2"]))
    for line in narr.get("points") or plain_points(brand_cur, [c for _, c in camps_cur], g_camps_p + m_camps_p) or ["特筆事項なし"]:
        story.append(Paragraph(line, S["bullet"], bulletText="■"))
    if narr.get("next"):
        story.append(KeepTogether([Paragraph("次にやること", S["h2"])] +
                                  [Paragraph(x, S["bullet"], bulletText="→") for x in narr["next"]]))

    # 2ページ目: グラフ
    story += [CondPageBreak(150 * mm), Paragraph("2. グラフで見る", S["h1"])]
    story.append(KeepTogether([Paragraph("毎日の広告費と、広告がきっかけの売上", S["h2"]),
                               daily_chart(g_daily, m_daily, cs, cu, ev_daily),
                               Paragraph("Google の購入は2〜3日遅れて計上されることがあり、直近の日は後から少し増える。", S["note"])]))
    story.append(KeepTogether([Paragraph("Google と Instagram・Facebook の比較（購入以外も）", S["h2"]),
                               media_compare(g_tot, m_tot),
                               Paragraph("Instagram・Facebook の購入には、広告を見ただけ（クリックなし）で後日買った分も含まれる。"
                                         "Google はクリックした人の購入だけ。", S["note"])]))
    story.append(KeepTogether([Paragraph("ブランド別：広告がきっかけの売上", S["h2"]), brand_chart(brand_cur),
                               Paragraph("棒の色は判定（緑◎・青○・橙△・赤×・灰＝件数が少なく判断保留）。"
                                         "店名検索は「フルマークス」で検索した人で、ブランドをまたぐため別建て。", S["note"])]))

    # 3ページ目: 成績表
    story += [PageBreak(), Paragraph("3. 広告ごとの成績表", S["h1"]), mark_legend(), Spacer(1, 2 * mm),
              scorecard(camps_cur, g_camps_p + m_camps_p)]
    cmp_tb = sec_adset_compare(meta_client, cs, cu)
    if cmp_tb:
        story.append(KeepTogether([Paragraph("Instagram・Facebook：配信先のテスト（全員向け vs サイト訪問者など）", S["h2"]), cmp_tb,
                                   Paragraph("同じ広告の中で予算を取り合う形。Meta は成果の良い方に自動で予算を寄せる。"
                                             "「1人あたり表示」が大きいほど、同じ人に何度も出ている（飽きられやすい）。", S["note"])]))
    if ev_cur:
        ev = sec_event(meta_client, google_client, today)
        if ev:
            story.append(Paragraph("イベント広告（EC企画・通常と別予算）", S["h2"]))
            story.extend(ev)
    story.append(KeepTogether([Paragraph("言葉の説明", S["h2"]), glossary_table()]))

    # 参考資料
    story += [PageBreak(), Paragraph("参考資料（担当者向けの詳細）", S["h1"])]
    story.append(KeepTogether([Paragraph("広告の種類別", S["h2"]), sec_frame(frame_cur, frame_prev)]))
    story.append(KeepTogether([Paragraph("ブランド別（表）", S["h2"]), sec_brand(brand_cur, brand_prev)]))
    story.append(KeepTogether([Paragraph("Googleショッピングで売れた商品", S["h2"]), sec_products(g_products)]))
    story.append(KeepTogether([Paragraph("商品カタログ広告（ブランド／シリーズ別）", S["h2"]), sec_catalog_ads(m_ads, m_ads_p)]))
    story.append(Paragraph("Meta は商品ごとの購入を返さないため、カタログ広告は広告（ブランド／シリーズ）単位。", S["note"]))
    story.append(KeepTogether([Paragraph("日別の表（イベント広告を含む）", S["h2"]), sec_daily(g_daily, m_daily, cs, cu)]))
    story.append(Paragraph("点検（リンク切れ・使ってはいけない口座・アウトレット品の表示）", S["h2"]))
    story.extend(sec_audit(meta_client, google_client, g_labels))

    out.parent.mkdir(parents=True, exist_ok=True)

    def _footer(canvas, doc):
        canvas.saveState(); canvas.setFont(FONT, 7.5); canvas.setFillColor(GREY)
        canvas.drawString(15 * mm, 9 * mm, f"FULLMARKS 広告週次レポート  {cs} 〜 {cu}")
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"{doc.page}")
        canvas.restoreState()

    SimpleDocTemplate(str(out), pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm,
                      leftMargin=15 * mm, rightMargin=15 * mm, title="広告 週次レポート"
                      ).build(story, onFirstPage=_footer, onLaterPages=_footer)
    print(f"PDFを生成: {out}")


if __name__ == "__main__":
    main()

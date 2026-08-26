"""広告クリエイティブ（画像・テキスト）の取得とプレビュー生成。

取得したプレビューは previews/ に HTML として保存され、ブラウザ
（Chrome / Chromium）で開いて実際の見た目を確認できる。
"""
from __future__ import annotations

import html
from pathlib import Path

from .google_ads_client import GoogleAdsClientWrapper
from .meta_ads import MetaAdsClient

PREVIEW_DIR = Path(__file__).resolve().parent.parent / "previews"


# ---------- Meta ----------

def meta_list_creatives(client: MetaAdsClient, limit: int = 50) -> list[dict]:
    """広告ごとのテキスト・画像URL・リンク先を取得する。"""
    body = client.get(
        f"{client.config.ad_account_id}/ads",
        fields=(
            "id,name,status,effective_status,"
            "creative{id,title,body,image_url,thumbnail_url,"
            "object_story_spec,asset_feed_spec}"
        ),
        limit=limit,
    )
    ads = []
    for ad in body.get("data", []):
        creative = ad.get("creative", {})
        spec = creative.get("object_story_spec", {}) or {}
        link_data = spec.get("link_data", {}) or {}
        feed = creative.get("asset_feed_spec", {}) or {}
        ads.append({
            "ad_id": ad["id"],
            "name": ad.get("name"),
            "status": ad.get("effective_status"),
            "title": creative.get("title") or link_data.get("name")
                     or [t.get("text") for t in feed.get("titles", [])],
            "body": creative.get("body") or link_data.get("message")
                    or [b.get("text") for b in feed.get("bodies", [])],
            "image_url": creative.get("image_url") or creative.get("thumbnail_url"),
            "link": link_data.get("link"),
        })
    return ads


def meta_generate_preview(client: MetaAdsClient, ad_id: str,
                          ad_format: str = "MOBILE_FEED_STANDARD") -> Path:
    """Meta公式のプレビューHTML（実際の表示と同じiframe）を保存する。"""
    body = client.get(f"{ad_id}/previews", ad_format=ad_format)
    iframes = [d["body"] for d in body.get("data", [])]
    PREVIEW_DIR.mkdir(exist_ok=True)
    out = PREVIEW_DIR / f"meta_{ad_id}_{ad_format}.html"
    out.write_text(
        "<meta charset='utf-8'><style>body{margin:20px;font-family:sans-serif}</style>"
        f"<h3>Meta ad {ad_id} ({ad_format})</h3>" + "\n".join(iframes),
        encoding="utf-8")
    return out


# ---------- Google ----------

def google_list_creatives(client: GoogleAdsClientWrapper) -> list[dict]:
    """レスポンシブ検索広告の見出し・説明文・リンク先を取得する。"""
    rows = client.search(
        "SELECT ad_group_ad.ad.id, ad_group_ad.ad.name, ad_group_ad.status, "
        "ad_group_ad.ad.type, ad_group_ad.ad.final_urls, "
        "ad_group_ad.ad.responsive_search_ad.headlines, "
        "ad_group_ad.ad.responsive_search_ad.descriptions, "
        "campaign.name, ad_group.name "
        "FROM ad_group_ad WHERE ad_group_ad.status != 'REMOVED'")
    ads = []
    for r in rows:
        ad = r.ad_group_ad.ad
        rsa = ad.responsive_search_ad
        ads.append({
            "ad_id": ad.id,
            "campaign": r.campaign.name,
            "ad_group": r.ad_group.name,
            "status": r.ad_group_ad.status.name,
            "type": ad.type_.name,
            "headlines": [h.text for h in rsa.headlines],
            "descriptions": [d.text for d in rsa.descriptions],
            "final_urls": list(ad.final_urls),
        })
    return ads


def google_render_preview(ad: dict) -> Path:
    """検索広告の見た目を模したプレビューHTMLを生成する。"""
    PREVIEW_DIR.mkdir(exist_ok=True)
    url = ad["final_urls"][0] if ad["final_urls"] else "#"
    headlines = " | ".join(ad["headlines"][:3])
    desc = " ".join(ad["descriptions"][:2])
    out = PREVIEW_DIR / f"google_{ad['ad_id']}.html"
    out.write_text(f"""<meta charset='utf-8'>
<style>
body{{font-family:arial,sans-serif;margin:40px;max-width:600px}}
.ad{{border:1px solid #dadce0;border-radius:8px;padding:16px}}
.sponsor{{font-size:12px;font-weight:bold}}
.url{{font-size:14px;color:#202124}}
.headline{{font-size:20px;color:#1a0dab;margin:4px 0}}
.desc{{font-size:14px;color:#4d5156}}
</style>
<h3>Google ad {ad['ad_id']} ({html.escape(ad['campaign'])})</h3>
<div class='ad'>
  <div class='sponsor'>スポンサー</div>
  <div class='url'>{html.escape(url)}</div>
  <div class='headline'>{html.escape(headlines)}</div>
  <div class='desc'>{html.escape(desc)}</div>
</div>
<h4>全アセット</h4>
<b>見出し:</b><ul>{"".join(f"<li>{html.escape(h)}</li>" for h in ad["headlines"])}</ul>
<b>説明文:</b><ul>{"".join(f"<li>{html.escape(d)}</li>" for d in ad["descriptions"])}</ul>
""", encoding="utf-8")
    return out

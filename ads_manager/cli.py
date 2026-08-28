"""広告運用CLI。

使い方:
  python -m ads_manager check                       # 両方の接続確認
  python -m ads_manager meta campaigns              # Metaキャンペーン一覧
  python -m ads_manager meta insights [--days 7]    # Meta成果データ
  python -m ads_manager meta set-status <id> ACTIVE|PAUSED
  python -m ads_manager meta set-budget <id> <金額(円)>
  python -m ads_manager google campaigns            # Googleキャンペーン一覧
  python -m ads_manager google metrics [--days 7]   # Google成果データ
  python -m ads_manager google set-status <id> ENABLED|PAUSED
  python -m ads_manager google set-budget <id> <金額>
  python -m ads_manager meta audit                    # 広告棚卸し（リンク切れ・停止漏れ検出）
  python -m ads_manager meta catalog-usage            # 広告セットが参照するカタログ/商品セット
  python -m ads_manager meta catalog-products <ID> [--query 語]  # カタログ内商品の表示状態
  python -m ads_manager meta catalog-clean <カタログID> [--apply] # リンク切れ商品を非表示化
  python -m ads_manager meta catalog-sync <カタログID> [--apply]  # サイト全商品をカタログへ同期
  python -m ads_manager meta creatives                # 広告の画像・テキスト一覧
  python -m ads_manager meta preview <ad_id>          # 公式プレビューHTMLを保存
  python -m ads_manager google creatives              # 見出し・説明文一覧
  python -m ads_manager google preview <ad_id>        # プレビューHTMLを保存
"""
import argparse
import json
import sys

from .config import load_google_config, load_meta_config


def _print(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def cmd_check() -> int:
    ok = True
    meta_cfg = load_meta_config()
    if meta_cfg.configured:
        try:
            from .meta_ads import MetaAdsClient
            info = MetaAdsClient(meta_cfg).check_connection()
            print(f"✅ Meta: 接続OK — {info.get('name')} ({info.get('id')}, "
                  f"{info.get('currency')})")
        except Exception as e:
            print(f"❌ Meta: 接続失敗 — {e}")
            ok = False
    else:
        print("⚠️ Meta: 未設定 (.env に META_ACCESS_TOKEN / META_AD_ACCOUNT_ID)")

    g_cfg = load_google_config()
    if g_cfg.configured:
        try:
            from .google_ads_client import GoogleAdsClientWrapper
            info = GoogleAdsClientWrapper(g_cfg).check_connection()
            print(f"✅ Google: 接続OK — {info['name']} ({info['id']}, "
                  f"{info['currency']})")
        except Exception as e:
            print(f"❌ Google: 接続失敗 — {e}")
            ok = False
    else:
        print("⚠️ Google: 未設定 (.env に GOOGLE_ADS_* を設定)")
    return 0 if ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ads_manager", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="platform", required=True)

    sub.add_parser("check", help="両プラットフォームの接続確認")

    for name in ("meta", "google"):
        p = sub.add_parser(name)
        action_sub = p.add_subparsers(dest="action", required=True)
        action_sub.add_parser("campaigns")
        ins = action_sub.add_parser("insights" if name == "meta" else "metrics")
        ins.add_argument("--days", type=int, default=7)
        st = action_sub.add_parser("set-status")
        st.add_argument("object_id")
        st.add_argument("status")
        bd = action_sub.add_parser("set-budget")
        bd.add_argument("object_id")
        bd.add_argument("amount", type=float)
        action_sub.add_parser("creatives")
        if name == "google":
            fd = action_sub.add_parser("feed")
            fd.add_argument("--out", default="feeds/google_merchant_feed.tsv",
                            help="出力先TSVファイルパス")
            fd.add_argument("--limit", type=int, default=0,
                            help="テスト用: 先頭N商品だけ処理する")
        if name == "meta":
            au = action_sub.add_parser("audit")
            au.add_argument("--include-paused", action="store_true",
                            help="停止中の広告も棚卸しに含める")
            au.add_argument("--no-check-links", action="store_true",
                            help="リンク先URLの生死確認を省略する")
            action_sub.add_parser("catalog-usage")
            cp = action_sub.add_parser("catalog-products")
            cp.add_argument("container_id",
                            help="カタログID または 商品セットID")
            cp.add_argument("--query", default="",
                            help="商品名・retailer_id・URLの部分一致で絞り込み")
            cc = action_sub.add_parser("catalog-clean")
            cc.add_argument("catalog_id", help="カタログID")
            cc.add_argument("--apply", action="store_true",
                            help="リンク切れ商品を実際に非表示化する（省略時はドライラン）")
            cf = action_sub.add_parser("catalog-feed")
            cf.add_argument("catalog_id", help="カタログID")
            cf.add_argument("--url",
                            default="https://www.fullmarksstore.jp/gsfeed.xml",
                            help="Google ShoppingフィードのURL")
            cf.add_argument("--apply", action="store_true",
                            help="フィードを実際に登録する（省略時はドライラン）")
            cs = action_sub.add_parser("catalog-sync")
            cs.add_argument("catalog_id", help="カタログID")
            cs.add_argument("--apply", action="store_true",
                            help="サイトの全商品を実際にカタログへ同期する（省略時はドライラン）")
            cs.add_argument("--limit", type=int, default=0,
                            help="テスト用: 先頭N商品だけ処理する")
        pv = action_sub.add_parser("preview")
        pv.add_argument("ad_id")
        if name == "meta":
            pv.add_argument("--format", default="MOBILE_FEED_STANDARD",
                            help="例: DESKTOP_FEED_STANDARD, INSTAGRAM_STANDARD")

    args = parser.parse_args(argv)

    if args.platform == "check":
        return cmd_check()

    if args.platform == "meta":
        from .meta_ads import MetaAdsClient
        client = MetaAdsClient(load_meta_config())
        if args.action == "campaigns":
            _print(client.list_campaigns())
        elif args.action == "insights":
            preset = {7: "last_7d", 14: "last_14d", 30: "last_30d"}.get(
                args.days, "last_7d")
            _print(client.get_insights(date_preset=preset))
        elif args.action == "set-status":
            _print(client.set_status(args.object_id, args.status))
        elif args.action == "set-budget":
            _print(client.set_daily_budget(args.object_id, int(args.amount)))
        elif args.action == "audit":
            from .audit import meta_audit
            _print(meta_audit(client,
                              include_paused=args.include_paused,
                              check_links=not args.no_check_links))
        elif args.action == "catalog-usage":
            from .audit import catalog_usage
            _print(catalog_usage(client))
        elif args.action == "catalog-products":
            from .audit import catalog_products
            _print(catalog_products(client, args.container_id, args.query))
        elif args.action == "catalog-clean":
            from .audit import catalog_clean
            _print(catalog_clean(client, args.catalog_id, apply=args.apply))
        elif args.action == "catalog-feed":
            from .catalog_sync import register_feed
            _print(register_feed(client, args.catalog_id, args.url,
                                 apply=args.apply))
        elif args.action == "catalog-sync":
            from .catalog_sync import catalog_sync
            _print(catalog_sync(client, args.catalog_id,
                                apply=args.apply, limit=args.limit))
        elif args.action == "creatives":
            from .creatives import meta_list_creatives
            _print(meta_list_creatives(client))
        elif args.action == "preview":
            from .creatives import meta_generate_preview
            path = meta_generate_preview(client, args.ad_id, args.format)
            print(f"プレビューを保存: {path}")
    else:
        if args.action == "feed":
            # Merchant Center用フィード生成はGoogle APIを使わない
            from pathlib import Path
            from .catalog_sync import build_google_feed, scrape_all_products
            items, failed = scrape_all_products(limit=args.limit)
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(build_google_feed(items), encoding="utf-8")
            print(f"フィードを生成: {out} ({len(items)}商品, 取得失敗{len(failed)}件)")
            return 0
        from .google_ads_client import GoogleAdsClientWrapper
        client = GoogleAdsClientWrapper(load_google_config())
        if args.action == "campaigns":
            _print(client.list_campaigns())
        elif args.action == "metrics":
            _print(client.get_metrics(days=args.days))
        elif args.action == "set-status":
            _print(client.set_campaign_status(args.object_id, args.status))
        elif args.action == "set-budget":
            _print(client.set_campaign_budget(args.object_id, args.amount))
        elif args.action == "creatives":
            from .creatives import google_list_creatives
            _print(google_list_creatives(client))
        elif args.action == "preview":
            from .creatives import google_list_creatives, google_render_preview
            ads = [a for a in google_list_creatives(client)
                   if str(a["ad_id"]) == str(args.ad_id)]
            if not ads:
                print(f"広告 {args.ad_id} が見つかりません")
                return 1
            path = google_render_preview(ads[0])
            print(f"プレビューを保存: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

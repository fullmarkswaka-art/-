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
        elif args.action == "creatives":
            from .creatives import meta_list_creatives
            _print(meta_list_creatives(client))
        elif args.action == "preview":
            from .creatives import meta_generate_preview
            path = meta_generate_preview(client, args.ad_id, args.format)
            print(f"プレビューを保存: {path}")
    else:
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

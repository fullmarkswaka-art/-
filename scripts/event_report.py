# -*- coding: utf-8 -*-
"""イベント広告（EC企画）の成果を通常運用と分けて表示する。

使い方: python scripts/event_report.py [--until YYYY-MM-DD] [--key sw2026]
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ads_manager.config import load_google_config, load_meta_config  # noqa: E402
from ads_manager.event_report import event_summary, format_text, load_events  # noqa: E402
from ads_manager.meta_ads import MetaAdsClient  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", default=None)
    ap.add_argument("--key", default=None)
    args = ap.parse_args()
    until = date.fromisoformat(args.until) if args.until else date.today()
    mc = MetaAdsClient(load_meta_config())
    try:
        from ads_manager.google_ads_client import GoogleAdsClientWrapper
        gc = GoogleAdsClientWrapper(load_google_config())
    except Exception as e:  # noqa: BLE001
        print(f"Google に接続できません（{type(e).__name__}）。Meta のみ集計します。")
        gc = None
    for ev in load_events():
        if args.key and ev["key"] != args.key:
            continue
        print(format_text(event_summary(mc, gc, ev, until)))


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Meta 広告アカウントの利用上限（spend_cap）の確認・使用額のリセット・上限額の変更。

使い方:
  python scripts/meta_spend_cap.py                     # 今の上限と使用額を表示
  python scripts/meta_spend_cap.py --reset [--apply]   # 使用額を0に戻す（毎月1日。2026-10-19 ユーザー指示で毎月こちらで実施）
  python scripts/meta_spend_cap.py --cap 430000 [--apply]  # 上限額を変える（金額はその月の予算の承認時に決める）
--apply なしは変更内容の表示だけ。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ads_manager.config import load_meta_config  # noqa: E402
from ads_manager.meta_ads import MetaAdsClient  # noqa: E402
from ads_manager.secrets_aws import load_secrets_into_env  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="使用額を0に戻す")
    ap.add_argument("--cap", type=int, default=None, help="上限額（円）")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    load_secrets_into_env()
    c = MetaAdsClient(load_meta_config())
    acct = c.config.ad_account_id
    cur = c.get(acct, fields="spend_cap,amount_spent")
    cap, spent = int(cur.get("spend_cap") or 0), int(cur.get("amount_spent") or 0)
    print(f"現在: 上限 {cap:,}円 / 使用額 {spent:,}円 / 残り {cap - spent:,}円")
    params = {}
    if args.reset:
        params["spend_cap_action"] = "reset"
    if args.cap is not None:
        params["spend_cap"] = str(args.cap)
    if not params:
        return
    plan = []
    if args.reset:
        plan.append(f"使用額 {spent:,} → 0")
    if args.cap is not None:
        plan.append(f"上限 {cap:,} → {args.cap:,}")
    print("変更:", " / ".join(plan), "" if args.apply else "（--apply なしのため未実行）")
    if not args.apply:
        return
    c.post(acct, **params)
    after = c.get(acct, fields="spend_cap,amount_spent")
    print(f"変更後: 上限 {int(after.get('spend_cap') or 0):,}円 / 使用額 {int(after.get('amount_spent') or 0):,}円")


if __name__ == "__main__":
    main()

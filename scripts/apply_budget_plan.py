# -*- coding: utf-8 -*-
"""月の日予算案（copy/budgets/<月>.json）を、今の設定と並べて表示し、--apply で反映する。

使い方:
  python scripts/apply_budget_plan.py copy/budgets/2026-10.json          # 差分の表示のみ
  python scripts/apply_budget_plan.py copy/budgets/2026-10.json --apply  # 反映（ユーザー承認後）

反映するのは既存キャンペーンの日予算（Google はキャンペーン予算、Meta はキャンペーン/広告セットの daily_budget）と
Google の目標ROAS。「new」（新設）は表示だけで、作成は別の手順で行う。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ads_manager.config import load_google_config, load_meta_config  # noqa: E402
from ads_manager.google_ads_client import GoogleAdsClientWrapper  # noqa: E402
from ads_manager.meta_ads import MetaAdsClient  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    g = GoogleAdsClientWrapper(load_google_config())
    m = MetaAdsClient(load_meta_config())

    ids = ",".join(str(int(x["campaign_id"])) for x in plan.get("google", []))
    cur = {}
    if ids:
        for r in g.search("SELECT campaign.id, campaign.name, campaign.bidding_strategy_type, "
                          "campaign.maximize_conversion_value.target_roas, campaign_budget.amount_micros "
                          f"FROM campaign WHERE campaign.id IN ({ids})"):
            cur[str(r.campaign.id)] = {"budget": r.campaign_budget.amount_micros / 1e6,
                                      "bidding": r.campaign.bidding_strategy_type.name,
                                      "troas": r.campaign.maximize_conversion_value.target_roas}
    total_now = total_new = 0
    print(f"== {plan['month']} 日予算案（{'反映' if args.apply else '差分の表示のみ'}）")
    for x in plan.get("google", []):
        c = cur.get(x["campaign_id"], {})
        now = c.get("budget", 0); total_now += now; total_new += x["daily"]
        troas = ""
        if "target_roas" in x:
            troas = f"  目標ROAS {c.get('troas') or '—'} → {x['target_roas']}"
        print(f"Google {x['name']}: {now:,.0f} → {x['daily']:,}円/日{troas}")
        if args.apply:
            if now != x["daily"]:
                g.set_campaign_budget(x["campaign_id"], x["daily"])
            if "target_roas" in x and c.get("troas") != x["target_roas"]:
                g.set_target_roas(x["campaign_id"], x["target_roas"])
    for x in plan.get("meta", []):
        o = m.get(x["object_id"], fields="name,daily_budget")
        now = float(o.get("daily_budget") or 0); total_now += now; total_new += x["daily"]
        print(f"Meta   {x['name']}: {now:,.0f} → {x['daily']:,}円/日")
        if args.apply and now != x["daily"]:
            m.set_daily_budget(x["object_id"], int(x["daily"]))
    for x in plan.get("new", []):
        total_new += x["daily"]
        print(f"新設   {x['media']} {x['name']}: {x['daily']:,}円/日（作成は別途）")
    print(f"合計（日予算）: {total_now:,.0f} → {total_new:,}円/日　月上限 {plan.get('monthly_cap_ex_tax', 0):,}円")


if __name__ == "__main__":
    main()

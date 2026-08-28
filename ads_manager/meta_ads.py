"""Meta Marketing API クライアント（Graph API を直接叩く薄いラッパー）。

参照: https://developers.facebook.com/docs/marketing-apis
"""
from __future__ import annotations

from typing import Any

import requests

from .config import MetaConfig

GRAPH_URL = "https://graph.facebook.com"


class MetaAdsError(RuntimeError):
    pass


class MetaAdsClient:
    def __init__(self, config: MetaConfig):
        if not config.configured:
            raise MetaAdsError(
                "META_ACCESS_TOKEN / META_AD_ACCOUNT_ID が未設定です (.env を確認)")
        self.config = config

    # ---- 低レベル ----
    def _request(self, method: str, path: str, **params: Any) -> dict:
        url = f"{GRAPH_URL}/{self.config.api_version}/{path}"
        params.setdefault("access_token", self.config.access_token)
        try:
            if method == "GET":
                resp = requests.get(url, params=params, timeout=30)
            else:
                resp = requests.post(url, data=params, timeout=30)
        except requests.RequestException as e:
            # 例外メッセージにトークン入りURLが含まれるため、そのまま投げない
            raise MetaAdsError(
                f"Meta APIへの接続に失敗 ({type(e).__name__}): "
                f"{GRAPH_URL} への通信路（プロキシ/ネットワーク許可）を確認してください") from None
        body = resp.json()
        if "error" in body:
            err = body["error"]
            raise MetaAdsError(
                f"Meta API error {err.get('code')}: {err.get('message')}")
        return body

    def get(self, path: str, **params: Any) -> dict:
        return self._request("GET", path, **params)

    def post(self, path: str, **params: Any) -> dict:
        return self._request("POST", path, **params)

    # ---- 接続確認 ----
    def check_connection(self) -> dict:
        return self.get(
            self.config.ad_account_id,
            fields="id,name,account_status,currency,timezone_name",
        )

    # ---- データ取得 ----
    def list_campaigns(self, limit: int = 50) -> list[dict]:
        body = self.get(
            f"{self.config.ad_account_id}/campaigns",
            fields="id,name,status,effective_status,objective,daily_budget,lifetime_budget",
            limit=limit,
        )
        return body.get("data", [])

    def get_insights(self, level: str = "campaign",
                     date_preset: str = "last_7d") -> list[dict]:
        body = self.get(
            f"{self.config.ad_account_id}/insights",
            level=level,
            date_preset=date_preset,
            fields="campaign_id,campaign_name,impressions,clicks,ctr,cpc,spend,actions",
        )
        return body.get("data", [])

    # ---- 広告の変更 ----
    def set_status(self, object_id: str, status: str) -> dict:
        """キャンペーン/広告セット/広告の配信ステータスを変更 (ACTIVE / PAUSED)。"""
        if status not in ("ACTIVE", "PAUSED"):
            raise MetaAdsError("status は ACTIVE か PAUSED を指定")
        return self.post(object_id, status=status)

    def set_daily_budget(self, object_id: str, amount_minor_units: int) -> dict:
        """日予算を変更。金額はアカウント通貨の最小単位（JPYなら円）で指定。"""
        return self.post(object_id, daily_budget=amount_minor_units)

"""Google Ads API クライアント（公式 google-ads ライブラリのラッパー）。

参照: https://developers.google.com/google-ads/api/docs/start
"""
from __future__ import annotations

from .config import GoogleAdsConfig


class GoogleAdsError(RuntimeError):
    pass


class GoogleAdsClientWrapper:
    def __init__(self, config: GoogleAdsConfig):
        if not config.configured:
            raise GoogleAdsError(
                "GOOGLE_ADS_* の環境変数が不足しています (.env を確認)")
        self.config = config
        try:
            from google.ads.googleads.client import GoogleAdsClient
        except ImportError as e:
            raise GoogleAdsError(
                "google-ads がインストールされていません: pip install -r requirements.txt") from e
        cfg = {
            "developer_token": config.developer_token,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "refresh_token": config.refresh_token,
            "use_proto_plus": True,
        }
        if config.login_customer_id:
            cfg["login_customer_id"] = config.login_customer_id
        self.client = GoogleAdsClient.load_from_dict(cfg)
        self.customer_id = config.customer_id

    def search(self, query: str) -> list[dict]:
        service = self.client.get_service("GoogleAdsService")
        rows = []
        for batch in service.search_stream(customer_id=self.customer_id, query=query):
            for row in batch.results:
                rows.append(row)
        return rows

    # ---- 接続確認 ----
    def check_connection(self) -> dict:
        rows = self.search(
            "SELECT customer.id, customer.descriptive_name, "
            "customer.currency_code, customer.time_zone FROM customer LIMIT 1")
        c = rows[0].customer
        return {"id": c.id, "name": c.descriptive_name,
                "currency": c.currency_code, "timezone": c.time_zone}

    # ---- データ取得 ----
    def list_campaigns(self) -> list[dict]:
        rows = self.search(
            "SELECT campaign.id, campaign.name, campaign.status, "
            "campaign_budget.amount_micros "
            "FROM campaign ORDER BY campaign.id")
        return [{
            "id": r.campaign.id,
            "name": r.campaign.name,
            "status": r.campaign.status.name,
            "daily_budget": r.campaign_budget.amount_micros / 1_000_000,
        } for r in rows]

    def get_metrics(self, days: int = 7) -> list[dict]:
        rows = self.search(
            "SELECT campaign.id, campaign.name, metrics.impressions, "
            "metrics.clicks, metrics.ctr, metrics.average_cpc, "
            "metrics.cost_micros, metrics.conversions "
            f"FROM campaign WHERE segments.date DURING LAST_{days}_DAYS")
        return [{
            "id": r.campaign.id,
            "name": r.campaign.name,
            "impressions": r.metrics.impressions,
            "clicks": r.metrics.clicks,
            "ctr": round(r.metrics.ctr * 100, 2),
            "avg_cpc": r.metrics.average_cpc / 1_000_000,
            "cost": r.metrics.cost_micros / 1_000_000,
            "conversions": r.metrics.conversions,
        } for r in rows]

    # ---- 広告の変更 ----
    def set_campaign_status(self, campaign_id: str, status: str) -> str:
        """キャンペーンの配信ステータスを変更 (ENABLED / PAUSED)。"""
        if status not in ("ENABLED", "PAUSED"):
            raise GoogleAdsError("status は ENABLED か PAUSED を指定")
        service = self.client.get_service("CampaignService")
        op = self.client.get_type("CampaignOperation")
        campaign = op.update
        campaign.resource_name = service.campaign_path(self.customer_id, campaign_id)
        campaign.status = self.client.enums.CampaignStatusEnum[status]
        op.update_mask.paths.append("status")
        resp = service.mutate_campaigns(
            customer_id=self.customer_id, operations=[op])
        return resp.results[0].resource_name

    def set_campaign_budget(self, campaign_id: str, daily_amount: float) -> str:
        """キャンペーンの日予算を変更（金額はアカウント通貨単位）。"""
        rows = self.search(
            "SELECT campaign.id, campaign_budget.resource_name FROM campaign "
            f"WHERE campaign.id = {int(campaign_id)}")
        if not rows:
            raise GoogleAdsError(f"campaign {campaign_id} が見つかりません")
        budget_rn = rows[0].campaign_budget.resource_name
        service = self.client.get_service("CampaignBudgetService")
        op = self.client.get_type("CampaignBudgetOperation")
        budget = op.update
        budget.resource_name = budget_rn
        budget.amount_micros = int(daily_amount * 1_000_000)
        op.update_mask.paths.append("amount_micros")
        resp = service.mutate_campaign_budgets(
            customer_id=self.customer_id, operations=[op])
        return resp.results[0].resource_name

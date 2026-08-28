"""環境変数から認証情報を読み込む。.env があれば自動で読む。"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# AWS (Secrets Manager / SSM) が設定されていれば不足分をそこから補完する
from .secrets_aws import load_secrets_into_env  # noqa: E402

try:
    load_secrets_into_env()
except Exception as e:  # AWS側の失敗は警告に留め、環境変数だけでも動かせるようにする
    print(f"⚠️ AWSからのシークレット取得に失敗: {e}")


@dataclass
class MetaConfig:
    access_token: str
    ad_account_id: str
    api_version: str = "v23.0"

    @property
    def configured(self) -> bool:
        return bool(self.access_token and self.ad_account_id)


@dataclass
class GoogleAdsConfig:
    developer_token: str
    client_id: str
    client_secret: str
    refresh_token: str
    customer_id: str
    login_customer_id: str = ""

    @property
    def configured(self) -> bool:
        return all([self.developer_token, self.client_id, self.client_secret,
                    self.refresh_token, self.customer_id])


def load_meta_config() -> MetaConfig:
    account_id = os.getenv("META_AD_ACCOUNT_ID", "").strip()
    if account_id and not account_id.startswith("act_"):
        # Graph API の広告アカウントノードは act_ プレフィックス必須
        account_id = f"act_{account_id}"
    return MetaConfig(
        access_token=os.getenv("META_ACCESS_TOKEN", ""),
        ad_account_id=account_id,
        api_version=os.getenv("META_API_VERSION", "v23.0"),
    )


def load_google_config() -> GoogleAdsConfig:
    return GoogleAdsConfig(
        developer_token=os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", ""),
        client_id=os.getenv("GOOGLE_ADS_CLIENT_ID", ""),
        client_secret=os.getenv("GOOGLE_ADS_CLIENT_SECRET", ""),
        refresh_token=os.getenv("GOOGLE_ADS_REFRESH_TOKEN", ""),
        customer_id=os.getenv("GOOGLE_ADS_CUSTOMER_ID", "").replace("-", ""),
        login_customer_id=os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", ""),
    )

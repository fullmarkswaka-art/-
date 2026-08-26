"""AWS から広告API認証情報を取得して環境変数に展開する。

対応:
  - AWS Secrets Manager: ADS_AWS_SECRET_NAME にシークレット名を設定
    （シークレット値は {"META_ACCESS_TOKEN": "...", ...} のJSON）
  - SSM Parameter Store: ADS_AWS_SSM_PREFIX にパスを設定（例: /ads/）
    （/ads/META_ACCESS_TOKEN のようにキー名でパラメータを作成、SecureString可）

AWS自体の認証は boto3 の標準方式（環境変数 AWS_ACCESS_KEY_ID /
AWS_SECRET_ACCESS_KEY / AWS_REGION、IAMロール、~/.aws/credentials）に従う。
既に環境変数で設定済みのキーは上書きしない。
"""
from __future__ import annotations

import json
import os

AD_KEYS = [
    "META_ACCESS_TOKEN",
    "META_AD_ACCOUNT_ID",
    "META_API_VERSION",
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_CUSTOMER_ID",
    "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
]


def load_secrets_into_env() -> list[str]:
    """AWSから取得できたキー名のリストを返す。AWS未設定なら何もしない。"""
    secret_name = os.getenv("ADS_AWS_SECRET_NAME", "")
    ssm_prefix = os.getenv("ADS_AWS_SSM_PREFIX", "")
    if not secret_name and not ssm_prefix:
        return []

    try:
        import boto3
    except ImportError as e:
        raise RuntimeError(
            "boto3 がインストールされていません: pip install -r requirements.txt") from e

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-northeast-1"
    loaded: list[str] = []

    if secret_name:
        client = boto3.client("secretsmanager", region_name=region)
        resp = client.get_secret_value(SecretId=secret_name)
        data = json.loads(resp["SecretString"])
        for key, value in data.items():
            if key in AD_KEYS and value and not os.getenv(key):
                os.environ[key] = str(value)
                loaded.append(key)

    if ssm_prefix:
        client = boto3.client("ssm", region_name=region)
        prefix = ssm_prefix if ssm_prefix.endswith("/") else ssm_prefix + "/"
        paginator = client.get_paginator("get_parameters_by_path")
        for page in paginator.paginate(Path=prefix, WithDecryption=True):
            for param in page["Parameters"]:
                key = param["Name"].rsplit("/", 1)[-1]
                if key in AD_KEYS and param["Value"] and not os.getenv(key):
                    os.environ[key] = param["Value"]
                    loaded.append(key)

    return loaded

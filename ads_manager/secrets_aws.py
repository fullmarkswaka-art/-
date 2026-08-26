"""AWS から広告API認証情報を取得して環境変数に展開する。

対応:
  - Lambda 関数の環境変数: ADS_AWS_LAMBDA_FUNCTION に関数名を設定
    （例: ad-routine-check。関数の環境変数から広告APIキーを読み取る）
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

# 取得元でキー名が違っていても拾えるようにする別名表（大文字小文字は無視）
KEY_ALIASES = {
    "META_ACCESS_TOKEN": ["FB_ACCESS_TOKEN", "FACEBOOK_ACCESS_TOKEN",
                          "META_TOKEN", "FB_TOKEN"],
    "META_AD_ACCOUNT_ID": ["FB_AD_ACCOUNT_ID", "FACEBOOK_AD_ACCOUNT_ID",
                           "AD_ACCOUNT_ID", "META_ACCOUNT_ID"],
    "GOOGLE_ADS_DEVELOPER_TOKEN": ["GOOGLE_DEVELOPER_TOKEN", "DEVELOPER_TOKEN"],
    "GOOGLE_ADS_CLIENT_ID": ["GOOGLE_CLIENT_ID"],
    "GOOGLE_ADS_CLIENT_SECRET": ["GOOGLE_CLIENT_SECRET"],
    "GOOGLE_ADS_REFRESH_TOKEN": ["GOOGLE_REFRESH_TOKEN", "REFRESH_TOKEN"],
    "GOOGLE_ADS_CUSTOMER_ID": ["GOOGLE_CUSTOMER_ID", "CUSTOMER_ID"],
    "GOOGLE_ADS_LOGIN_CUSTOMER_ID": ["LOGIN_CUSTOMER_ID", "MCC_ID",
                                     "MCC_CUSTOMER_ID"],
}


def _apply_vars(variables: dict, loaded: list[str]) -> None:
    """取得した変数群を（別名も解決しつつ）未設定の環境変数へ反映する。"""
    upper = {k.upper(): v for k, v in variables.items() if v}
    for key in AD_KEYS:
        if os.getenv(key):
            continue
        value = upper.get(key)
        if not value:
            for alias in KEY_ALIASES.get(key, []):
                if upper.get(alias):
                    value = upper[alias]
                    break
        if value:
            os.environ[key] = str(value)
            loaded.append(key)


def load_secrets_into_env() -> list[str]:
    """AWSから取得できたキー名のリストを返す。AWS未設定なら何もしない。"""
    lambda_fn = os.getenv("ADS_AWS_LAMBDA_FUNCTION", "")
    secret_name = os.getenv("ADS_AWS_SECRET_NAME", "")
    ssm_prefix = os.getenv("ADS_AWS_SSM_PREFIX", "")
    if not lambda_fn and not secret_name and not ssm_prefix:
        return []

    try:
        import boto3
    except ImportError as e:
        raise RuntimeError(
            "boto3 がインストールされていません: pip install -r requirements.txt") from e

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-northeast-1"
    loaded: list[str] = []

    if lambda_fn:
        client = boto3.client("lambda", region_name=region)
        resp = client.get_function_configuration(FunctionName=lambda_fn)
        variables = resp.get("Environment", {}).get("Variables", {})
        _apply_vars(variables, loaded)

    if secret_name:
        client = boto3.client("secretsmanager", region_name=region)
        resp = client.get_secret_value(SecretId=secret_name)
        _apply_vars(json.loads(resp["SecretString"]), loaded)

    if ssm_prefix:
        client = boto3.client("ssm", region_name=region)
        prefix = ssm_prefix if ssm_prefix.endswith("/") else ssm_prefix + "/"
        params: dict[str, str] = {}
        paginator = client.get_paginator("get_parameters_by_path")
        for page in paginator.paginate(Path=prefix, WithDecryption=True):
            for param in page["Parameters"]:
                params[param["Name"].rsplit("/", 1)[-1]] = param["Value"]
        _apply_vars(params, loaded)

    return loaded

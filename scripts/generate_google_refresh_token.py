"""Google Ads API 用のリフレッシュトークンを生成するスクリプト。

ローカルPC（ブラウザが開ける環境）で実行する:
  1. Google Cloud Console で OAuth クライアント（デスクトップアプリ）を作成
  2. .env に GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET を設定
  3. python scripts/generate_google_refresh_token.py
  4. ブラウザで Google 広告アカウントの権限を持つ Google アカウントでログイン
  5. 表示されたリフレッシュトークンを .env の GOOGLE_ADS_REFRESH_TOKEN に貼る
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ads_manager import config  # noqa: E402  (.env を読み込むため)

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/adwords"]


def main() -> None:
    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET を .env に設定してください")

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )
    creds = flow.run_local_server(port=0)
    print("\n以下を .env の GOOGLE_ADS_REFRESH_TOKEN に設定してください:\n")
    print(creds.refresh_token)


if __name__ == "__main__":
    main()

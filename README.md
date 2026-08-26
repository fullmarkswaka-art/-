# 広告運用ツール（Meta広告 × Google広告）

Meta（Facebook/Instagram）広告と Google 広告に API で接続し、
**データ確認 → 広告の変更（配信ON/OFF・予算変更）** までを行うためのツールです。

## できること

| 操作 | Meta | Google |
|---|---|---|
| 接続確認 | ✅ | ✅ |
| キャンペーン一覧 | ✅ | ✅ |
| 成果データ（表示・クリック・費用・CV） | ✅ | ✅ |
| 配信ステータス変更（ON/OFF） | ✅ | ✅ |
| 日予算の変更 | ✅ | ✅ |

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env
# .env に認証情報を記入
python -m ads_manager check   # 接続確認
```

### 1. Meta広告の認証情報

1. [Meta for Developers](https://developers.facebook.com/) でアプリを作成（タイプ: ビジネス）
2. アプリに「Marketing API」を追加
3. [ビジネス設定 → システムユーザー](https://business.facebook.com/settings/system-users) でシステムユーザーを作成し、
   広告アカウントへのアクセスを割り当て
4. `ads_read`, `ads_management` 権限でトークンを生成（システムユーザートークンは無期限）
5. `.env` に設定:
   - `META_ACCESS_TOKEN` = 生成したトークン
   - `META_AD_ACCOUNT_ID` = `act_` から始まる広告アカウントID
     （[広告マネージャ](https://adsmanager.facebook.com/)のURLの `act=` の数字に `act_` を付ける）

### 2. Google広告の認証情報

1. [Google Ads 管理画面 → ツール → APIセンター](https://ads.google.com/aw/apicenter) で
   **開発者トークン** を取得（MCCアカウントが必要）
2. [Google Cloud Console](https://console.cloud.google.com/apis/credentials) で
   OAuth クライアントID（種類: デスクトップアプリ）を作成 → `GOOGLE_ADS_CLIENT_ID` / `GOOGLE_ADS_CLIENT_SECRET`
3. ローカルPCで `python scripts/generate_google_refresh_token.py` を実行し、
   表示されたトークンを `GOOGLE_ADS_REFRESH_TOKEN` に設定
4. `GOOGLE_ADS_CUSTOMER_ID` = 操作対象アカウントのID（ハイフンなし10桁）
5. MCC 経由の場合は `GOOGLE_ADS_LOGIN_CUSTOMER_ID` に MCC の ID も設定

## 使い方

```bash
# 接続確認（両方まとめて）
python -m ads_manager check

# --- Meta ---
python -m ads_manager meta campaigns                  # キャンペーン一覧
python -m ads_manager meta insights --days 7          # 直近7日の成果
python -m ads_manager meta set-status <ID> PAUSED     # 配信停止
python -m ads_manager meta set-status <ID> ACTIVE     # 配信再開
python -m ads_manager meta set-budget <ID> 5000       # 日予算を5,000円に

# --- Google ---
python -m ads_manager google campaigns                # キャンペーン一覧
python -m ads_manager google metrics --days 7         # 直近7日の成果
python -m ads_manager google set-status <ID> PAUSED   # 配信停止
python -m ads_manager google set-status <ID> ENABLED  # 配信再開
python -m ads_manager google set-budget <ID> 5000     # 日予算を5,000円に
```

## Claude Code から使う場合

このリポジトリを開いた Claude Code のセッションで、`.env` に認証情報が入っていれば
「先週のMeta広告の成果を見せて」「CPAが高いキャンペーンを止めて」のような指示で
Claude が上記コマンドを実行して対応できます。

リモート環境（claude.ai/code）で使う場合は、環境設定の **環境変数** に
`.env.example` と同じキーで認証情報を登録してください。

## セキュリティ

- `.env` は `.gitignore` 済み。**トークンは絶対にコミットしないこと**
- トークンが漏れた場合は Meta / Google 側で即失効させること

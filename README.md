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
| クリエイティブ（画像・テキスト）確認 | ✅ | ✅ |
| プレビューHTML生成（ブラウザ確認用） | ✅ | ✅ |

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

### 3. AWSに認証情報を置いている場合

個別のキーを .env に書く代わりに、AWSから自動取得できます。

- **Lambda 関数の環境変数**: 既存の Lambda（例: `ad-routine-check`）の
  環境変数にキーが入っている場合、`ADS_AWS_LAMBDA_FUNCTION` に関数名を
  設定すれば自動で読み取ります。
  必要なIAM権限: `lambda:GetFunctionConfiguration`。
  キー名が `FB_ACCESS_TOKEN` や `GOOGLE_REFRESH_TOKEN` のような別名でも
  自動でマッピングされます（`ads_manager/secrets_aws.py` の `KEY_ALIASES` 参照）
- **Secrets Manager**: 上記キーをまとめた1つのJSONシークレットを作成し、
  `ADS_AWS_SECRET_NAME` にシークレット名を設定
  ```json
  {"META_ACCESS_TOKEN": "...", "META_AD_ACCOUNT_ID": "act_...",
   "GOOGLE_ADS_DEVELOPER_TOKEN": "...", "GOOGLE_ADS_CLIENT_ID": "...",
   "GOOGLE_ADS_CLIENT_SECRET": "...", "GOOGLE_ADS_REFRESH_TOKEN": "...",
   "GOOGLE_ADS_CUSTOMER_ID": "..."}
  ```
- **SSM Parameter Store**: `/ads/META_ACCESS_TOKEN` のようにキー名ごとの
  パラメータ（SecureString可）を作成し、`ADS_AWS_SSM_PREFIX=/ads/` を設定

AWSへの認証は boto3 標準（`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` /
`AWS_REGION`、またはIAMロール）。必要なIAM権限は
`secretsmanager:GetSecretValue`（または `ssm:GetParametersByPath`）のみ。

### Google接続を切らさないために（毎日ログインは不要）

Google Ads のアクセストークンは1時間で切れますが、**リフレッシュトークンが
あればライブラリが自動更新する**ため、通常は再ログイン不要です。
「1日〜1週間で切れる」場合は、Google Cloud Console の
**OAuth同意画面が「テスト」モード**になっているのが原因です
（テストモードのリフレッシュトークンは7日で失効）。

対処: [OAuth同意画面](https://console.cloud.google.com/apis/credentials/consent)
→ 「アプリを公開」で **本番（Production）** に切り替え → リフレッシュトークンを
再生成。これで無期限（6ヶ月以上未使用の場合のみ失効）になります。

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

# --- 棚卸し（過去商品の広告が残っていないか調査） ---
python -m ads_manager meta audit                      # 配信中の全広告のリンク先を検査し、
                                                      # リンク切れ・停止漏れ・カタログ起因を分類
python -m ads_manager meta audit --include-paused     # 停止中も含めて棚卸し
python -m ads_manager meta audit --no-check-links     # URLの生死確認を省略（高速）

# --- カタログ広告の調査（過去商品がカタログ経由で配信されていないか） ---
python -m ads_manager meta catalog-usage              # 広告セットが参照するカタログ/商品セットを特定
python -m ads_manager meta catalog-products <ID> --query daybreak
                                                      # カタログ/商品セット内の商品の
                                                      # visibility(公開状態)・availability(在庫)を確認

# --- カタログ同期 ---
python -m ads_manager meta catalog-feed <カタログID> --apply   # サイト標準の gsfeed.xml を
                                                      # 定期取得フィードとして登録（推奨・以後自動更新）
python -m ads_manager meta catalog-sync <カタログID> --apply   # 予備: サイトをスクレイプして直接同期
python -m ads_manager google feed                              # 予備: Merchant Center用TSVを生成
                                                      # （通常は gsfeed.xml の登録で足りるため不要）

# --- クリエイティブ確認 ---
python -m ads_manager meta creatives                  # 画像URL・テキスト一覧
python -m ads_manager meta preview <広告ID>           # Meta公式プレビューを previews/ に保存
python -m ads_manager google creatives                # 見出し・説明文一覧
python -m ads_manager google preview <広告ID>         # 検索広告の見た目を previews/ に保存
```

プレビューは `previews/*.html` に保存されるので、Chrome で開いて実際の
見た目を確認できます。Claude Code のセッション内では Chromium で
スクリーンショットを撮って確認することもできます。

## Claude Code から使う場合

このリポジトリを開いた Claude Code のセッションで、`.env` に認証情報が入っていれば
「先週のMeta広告の成果を見せて」「CPAが高いキャンペーンを止めて」のような指示で
Claude が上記コマンドを実行して対応できます。

リモート環境（claude.ai/code）で使う場合は、環境設定の **環境変数** に
`.env.example` と同じキーで認証情報を登録してください。

## セキュリティ

- `.env` は `.gitignore` 済み。**トークンは絶対にコミットしないこと**
- トークンが漏れた場合は Meta / Google 側で即失効させること

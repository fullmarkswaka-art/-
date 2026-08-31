# 運用メモ（Claude向けコンテキスト）

FULLMARKS（fullmarksstore.jp）の広告運用ツール。Meta/Google広告のAPI操作と
カタログ管理を行う。認証情報はAWS Lambda `ad-routine-check` の環境変数から
自動取得される（`ADS_AWS_LAMBDA_FUNCTION` 参照）。

## 重要なID

- Meta広告アカウント: `act_976410622096585`（FULLMARKS広告運用、JPY）
- Metaカタログ: `610915616169358`（Products for Fullmarks (store)）
- Metaカタログの定期取得フィード: `1058904553805180`
  （https://www.fullmarksstore.jp/gsfeed.xml を毎日自動取得）
- 商品セット「すべての商品」: `664073467745725`（カタログ広告が参照）

## カタログ運用の原則（2026-08の事故の教訓）

- サイトの商品フィード `gsfeed.xml` が唯一の商品データ源。
  Meta・Google Merchant Center の両方がこれを毎日自動取得する構成。
  **カタログへ商品を手動投入・個別編集しないこと**（同期が壊れる）。
- 2020年の旧ページショップ由来の商品893件は「在庫なし+staging」で
  カタログ内に温存してある。削除も再公開もしない。
- 過去商品の広告が配信される事故（Daybreak Pullover問題）の原因は、
  更新の止まったカタログを「すべての商品」セットで配信したこと。
  詳細はブランチ `claude/daybreak-pullover-ad-issue-3el99r` の履歴参照。

## 定例タスク

- 週次レポート: `python scripts/weekly_report.py` でMeta+Googleの
  直近7日成果とリンク切れチェックをPDF生成（reports/ に出力）。
  ユーザーは毎週このPDFの送付を希望している。
- リンク切れ監視: `python -m ads_manager meta audit`
- フィード掲載漏れ確認: `python -m ads_manager google feed-gap`
  （在庫があるのにgsfeed.xml未掲載の商品を検出。EC側の設定漏れ）

## 既知の問題

- Google Ads API は開発者トークンが無効（DEVELOPER_TOKEN_INVALID）。
  ユーザーがAPIセンターで再取得するまでGoogle成果は取得不可。
  週次レポートはGoogle不通時もMetaのみで生成される。
- Googleのリフレッシュトークンのスコープは `adwords` のみ。
  Merchant Center (Content API) は操作不可（必要ならスコープを
  追加してトークン再生成）。

## 広告操作の注意

- 配信ON/OFF・予算変更・カタログ書き込みは必ずユーザーの承認を得てから
  実行する。ドライラン（--apply なし）で差分を見せてから適用する。

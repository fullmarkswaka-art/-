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

## 既知の問題（解決済み含む）

- 【解決済み 2026-08-31】Google Ads API の DEVELOPER_TOKEN_INVALID は、
  Lambda環境変数 `GOOGLE_ADS_DEVELOPER_TOKEN` に混入した改行が原因だった。
  config.py で全認証情報を strip するよう修正済み。トークン自体は有効。
  Lambda側の環境変数はいずれ改行なしの値に直しておくのが望ましい。
- Google接続は恒久維持される構成: OAuthアプリは Workspace「内部」
  （テスト/本番の区別なし、リフレッシュトークン無期限）、
  アクセストークンはライブラリが自動更新、週次レポートが毎週使うため
  6ヶ月未使用失効も起きない。
- 【解決済み 2026-09-03】Googleのリフレッシュトークンを adwords + content の
  両スコープで取り直し、Lambda 環境変数に反映済み。Merchant Center も API 操作可。
  再取得が必要になったら `scripts/google_oauth_manual.py url` で認可URLを出し、
  ユーザーがブラウザでログイン後の localhost URL を貼る → `exchange` で交換
  （PCへのインストール不要。内部アプリのため marble.jp.net のアカウントで認証）。

## Google側の地雷（Metaと同型）

- Google広告の停止中キャンペーンには過去の広告が800本以上残っており、
  その大半がリンク切れ（2026-08-31時点の検査で845本）。
  現在配信中の広告5本は正常。**停止中の旧キャンペーンを安易に再開しない**。
  再開時は必ず事前にリンク確認（weekly_report のリンク検査か
  google creatives で final_urls を確認）を行うこと。

## 年間予算計画（2026-05〜2027-04）

- 年間広告費上限: 税抜1,200万円（4ストア合計:
  FULLMARKS / HOUDINI / NORRONA / PU STORE）。
- このツールで見えるのは FULLMARKS の広告アカウントのみ。
  5〜7月実績では月95万のうちFULLMARKSが約30万、他3ストアが約65万。
- 月別配分・ストア配分・イベント予備費（SW/年末/2月冬セール等）は
  Excel「広告予算計画_2026-05_2027-04.xlsx」で管理（ユーザーに送付済み。
  黄色セル=仮置きで、他ストアの実績数値が来たら差し替える）。
- 繁忙期（10〜1月）に厚く配分。2027-04は年間上限に合わせる調整月。

## 売上目標（FY2026 = 2026-05〜2027-04）※すべて税抜

- **売上は税抜で扱う**（会社のWEB年度予算ファイル基準）。受注CSVは税込で
  約1.1倍の値になるため混同しないこと。
- 会社予算: 2.8億（前年比106%）。ストレッチ目標: 3.2億（前年比121%、
  9〜4月で前年比115%が必要）。FY2025実績 2.63億。
- 5〜8月実績: 8,092万（予算比114%・前年比146%）。
- 月別目標はExcel「広告予算計画_2026-05_2027-04_金額確定版.xlsx」の
  「売上計画」シート（会社予算2.8億の月割り形状を採用。10月に厚く、
  2月セールは前年割れ設定）。勝負月は10月（前年比197%が必要）。
- ブランド構成(5〜8月): HOUDINI 71% / NORRONA 12% / POC 8% / ACLIMA 5%。
  HOUDINI STORE稼働時はFULLMARKS売上の約7割が移管されるため、
  「3ストアで4,000万」は規模の再設定が必要。
- 会社FW取扱率計画（NORRONA 24%・HESTRA 9%）は広告実力と乖離。要協議。
- 旧品比率43%（3〜8月）。値引き依存の構造リスク。
- EC全体の売上実績はAPIで取れないため、月次でユーザーからデータをもらい
  売上計画シートと突き合わせる。

## 月間運用方針（2026-09〜）

- 月間広告費: 税抜70万円（targets.json 参照）。
  うち5〜10万はシルバーウィーク等のEC企画用予備費として残し、
  通常運用は約60万（実消化 約2万円/日）を Google + Meta で使い切る。
- 目標: 全体ROAS 10倍以上を維持しながら予算を消化する。
  未消化（機会損失）と低ROASの両方を週次レポートで監視し、
  予算損失が出ている枠へ増額、ROASが立たない枠から減額する。
- 2026-08の実績: 消化46.8万/70万（67%）。Google ROAS 16.1、Meta 0.5。
  Googleの指名検索とショッピング(PLA)が収益の柱。
- 予算増減はキャンペーン単位で行い、変更前に必ずユーザー承認を得る。

## 広告アカウントの原則（2026-09-03 ユーザー指示）

- **広告を回してよいのは Meta `act_976410622096585`（FULLMARKS広告運用）と
  Google `6803842189`（FULLMARKS Inc.）だけ**。メディックス(MDX)管理の
  Meta `act_587527895389459` / `act_719498040184021`、Google `3627928709`（認知施策用）
  で広告を出してはいけない。これらは 2026-09 以降消化ゼロ・稼働キャンペーンなしを確認済み
  （8月は MDX Meta 2口座で計 ¥81,291 の消化あり）。週次レポート時に他口座の消化が
  ゼロであることを確認し、消化があれば即報告する。

## 広告操作の注意

- 配信ON/OFF・予算変更・カタログ書き込みは必ずユーザーの承認を得てから
  実行する。ドライラン（--apply なし）で差分を見せてから適用する。

## ブランディング課題（2026-09-03 発見・対応中）

- gsfeed.xml には brand / product_type / custom_label / sale_price が無く、
  在庫あり1,596件のうち791件（50%）がアウトレット商品。EC側（アラジン）の
  フィード改修は約2ヶ月かかるため、当面はサイト巡回で属性を補完する運用。
- 属性補完の仕組み（実装済み）:
  - `python -m ads_manager meta catalog-attributes` … サイトのブランド絞り込み
    カテゴリ（FILTER_BRAND_*）とOUTLETカテゴリを巡回し、全商品に brand /
    custom_label_0 (outlet|regular) / custom_label_1 (シリーズ) / product_type を
    付けた `reports/catalog_attributes.csv` を生成（商品ID先頭2桁でもブランド判定可:
    10 HESTRA / 11 POC / 12 NORRONA / 13 HOUDINI / 14 ACLIMA / 15 SAIL RACING /
    16 POW / 17 PLUS ONE WORKS / 21 KANG）。
  - `python -m ads_manager meta catalog-supplement 610915616169358 --apply` …
    Meta 補助フィード `1098537166224560`（primary=1058904553805180）へCSVを
    アップロード。**毎週月曜の定例で再実行する**（アウトレット入替に追随）。
  - `python -m ads_manager google mc-supplement --apply` … Merchant Center
    (ID 5642612701) の API 補助データソース `10719929792`（プライマリ
    `10585554861` = gsfeed.xml 取得、デフォルトルールで連結済み）へ商品ごとに
    brand / customLabel0 / customLabel1 / productTypes を productInputs として登録。
    **毎週月曜の定例で再実行する**。Merchant API v1 を使用（Content API は終了予定）。
    GCPプロジェクト 913768367915 (fullmarks-analytics) は developerRegistration 済み。
- 除外の実装:
  - Google: PLA_v2 (24136223642) の商品グループを custom_label_0 で分割済み。
    outlet=除外、その他=¥20。ルート(SUBDIVISION)の status が API 上 PAUSED と
    表示されるが仕様（UNIT以外は無意味）。翌日以降のインプレッションで要確認。
  - Meta: 商品セット「通常価格_*」を作成済み（全ブランド 1061636746673854 /
    HOUDINI 1066692882884067 / NORRONA 2928671157303376 / POC 924896417345197 /
    ACLIMA 2252281938679870 / HESTRA 2164694404474862 / NORRONA_falketind
    2425736481284111 / femund 1724713352166731 / senja 1063318003222881 /
    lofoten 1477226797547982 / trollveggen 1324032626282004 ほか）。
    【2026-09-03 実施済み】`meta swap-catalog-ads ... --sets-json copy/catalog_ads.json`
    で「すべての商品」広告 52598939357735 を停止し、広告セット 52598939140535 に
    ブランド/シリーズ別のカタログ広告9本（HOUDINI / POC / ACLIMA / HESTRA /
    NORRØNA falketind・femund・senja・lofoten・trollveggen）を作成。本文は
    「<ブランド or シリーズ>｜Fall / Winter 2026」形式（copy/catalog_ads.json）。
    1広告=1ブランド、NORRØNAはシリーズ単位。カルーセル内でブランドを混ぜない。
- Meta アプリ「FULLMARKS広告分析」(2559664041137913) は 2026-09-03 に公開モードへ
  切替済み。広告クリエイティブの新規作成（`meta replace-copy` /
  `swap-catalog-ads`）は公開モードでないと Meta に拒否される（エラー 1885183）。
  カタログ広告のクリエイティブ作成には instagram_user_id (17841404773057326) が必要。
- 【2026-09-03 実施済み】NORRØNA 静止画 RTG 広告を `meta replace-copy` で差し替え
  （新広告 52604711975335、旧 52597391295935 は停止）。Google 指名_ノローナ の RSA も
  `google replace-copy`（copy/norrona_google_rsa.json）で差し替え済み（新 823291183637、
  旧 663462201975 停止）。表記は NORRØNA、カタカナ不使用がユーザー方針。
- 【2026-09-03 実施済み】ユーザー指示「正規販売店FULLMARKSで。は全て無くす」。
  Meta 静止画（HOUDINI / POC / ACLIMA ×3）を copy/*_meta.json（full-marks.com の
  公式ブランド紹介文、見出し「ブランド｜Fall / Winter 2026」）で差し替え、Google
  指名_フーディニ / 指名_ノローナ の RSA も「買うなら」「正規販売店」を含まない文言に
  差し替え済み。今後の広告文でも「正規販売店FULLMARKSで」「〇〇を買うなら」は使わない。
- 「〇〇を買うならフルマークス」型の文言は、Google指名検索RSA（ノローナ・
  フーディニ）の見出し/説明文と、Metaカタログ広告テンプレート
  `{{product.name}} ― アウトドアの正規販売店、FULLMARKSで。` が原因。
  ユーザー方針: ブランド紹介ではなく「その商品がなぜ良いか」を伝える商品訴求型に
  する。ブランドを混ぜない。NORRONAはシリーズ（lofoten/falketind等）で分ける。

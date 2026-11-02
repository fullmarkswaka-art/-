# PERMANENT UNION — Shopify テーマ（v2.0）

デザインPDF「TOP v0.3」「下層ページ v0.1」をそのまま Shopify テーマ（Online Store 2.0）にしたものです。
PC・スマホの両方に対応し、文章・写真・リンクはすべてテーマエディターから差し替えられます。

- 配色：Paper `#F2EEE7` ／ Ink `#2A211E` ／ Logo Brown `#4A3A34` ／ Accent `#D8652C`
- 書体：和文 Shippori Mincho B1 ／ 見出し・カテゴリ名・商品名 Cormorant Garamond ／ 英文 Jost ／ UI Noto Sans JP（Google Fonts）
- オリジナル要素：ロゴの「縄」の線画（区切り線・SCROLL・章インジケーター）、章ごとのジャケットのカラー名

---

## 1. アップロード

1. `permanent-union-theme.zip` を用意します（このフォルダを ZIP にしたもの）。
2. Shopify 管理画面 → **オンラインストア → テーマ → テーマを追加 → ZIP ファイルをアップロード**。
3. アップロード後「カスタマイズ」で内容を確認し、問題なければ「公開」。

> ZIP に写真・ロゴ・商品画像（仮）を同梱しています。映像だけはテーマに入れられないため、下記「3. TOP の背景（写真／映像）」の手順でアップロードしてください。

## 2. 最初に作るもの（管理画面）

| 作るもの | 場所 | 内容 |
|---|---|---|
| メニュー `main-menu`（メインメニュー） | オンラインストア → メニュー | **SHOP** の並び。All Products（/collections/all）／ Outerwear ／ Tops ／ Bottoms ／ Accessories など。全画面メニュー・フッター・商品一覧のタブに使われます |
| メニュー `footer`（フッターメニュー） | 同上 | **INFORMATION** の並び。About Us（/pages/about）／ Riders（/pages/riders）／ Journal（/blogs/journal）／ Shop List（/pages/shoplist）／ ご利用ガイド・FAQ（/pages/guide）／ お問い合わせ（/pages/contact）／ 特定商取引法に基づく表記（/pages/legal） |
| コレクション | 商品 → コレクション | カテゴリ構成が決まったら作成（例：outerwear / tops / bottoms / accessories）。TOP の Products の4枠はテーマエディターでコレクションを選ぶだけで名称・写真・リンクが入ります |
| ページ | オンラインストア → ページ | 下の表のとおり「テーマテンプレート」を選んで作成 |
| ブログ `journal` | オンラインストア → ブログ記事 → ブログを管理 | Journal。記事のタグ（NEWS / RIDERS / COLUMN / EVENT）がカテゴリタブになります |
| ポリシー | 設定 → ポリシー | プライバシーポリシー・利用規約を登録するとフッターに自動表示 |

### ページとテンプレート

| ページ | テンプレート | 内容 |
|---|---|---|
| About Us | `page.about` | キービジュアル（雲海）＋ブランド紹介＋コンセプト。文章・写真はエディターで変更 |
| Riders | `page.riders` | 4列×2段。ライダーはブロックで追加・並び替え（写真・名前・種目・プロフィール・SNS） |
| Shop List | `page.shoplist` | 日本地図＋台湾。ブロックは「地域」→「店舗」の順に並べる。店舗の都道府県を選ぶと地図にピンが付き、カーソルを合わせる／タップで店舗カードが出ます |
| ご利用ガイド・FAQ | `page.guide` | 左に目次、右に本文。項目・質問はブロックで追加。FAQ は開閉式 |
| お問い合わせ | `page.contact` | フォーム（Shopify 標準・送信先はストアのメールアドレス）＋右側に特定商取引法に基づく表記 |
| 特定商取引法に基づく表記 | `page.legal` | 表記だけの単独ページ（フッターのリンク用） |

## 3. TOP の背景（写真／映像）

TOP は3層構成です：**LAYER 1 背景（画面に固定）** → **LAYER 2 写真（スクロールで流れる）** → **LAYER 3 文字**。

- 背景は初期状態で白馬の雲海写真（テーマ同梱）です。差し替えは **テーマエディター → トップページ → 「TOP 背景（最背面・固定）」**。
- 映像を使う場合：1920×1080 ／ 15〜30秒 ／ H.264 MP4 ／ 音声なし ／ 10MB 以下を目安に書き出し、**管理画面 → コンテンツ → ファイル** にアップロードしてから同セクションの「映像（Shopify）」で選択します。写真はポスター（読み込み前・再生できない環境）として使われます。
- 「視差効果を減らす」設定の端末では映像を止めて静止画を表示します。

## 4. TOP の各セクション（テーマエディター）

| セクション | 内容・設定 |
|---|---|
| オープニング（ロゴ） | ロゴ fade in 0.8s → hold 1.2s → fade out 0.8s。ロゴ幅 PC 30%（最大 440px）／ SP 60%。初回訪問時のみ。クリック・スクロールでスキップ |
| ファーストビュー（写真） | 写真を背景の上に約70%で重ね、スクロールで上へ流れて消える。**マーシーさんの写真が届いたらここで差し替え**（トリミング位置は PC／SP 別に調整可） |
| STORY（章）×7 | 全画面写真＋語りかけ。章番号・カラー名（Muku / Kakishibu / Wakaba / Slate Blue / Midnight / Babaji）・レイアウト（7種）・文章・写真（PC／SP 別、トリミング位置）・暗さ・パララックス。**STORY 01〜03 の写真が届いたら差し替え** |
| 映像の間（背景だけ）×3 | 写真が途切れて背景だけが見える区間（高さ 70%）。STORY 03→04、06→07、07→Products |
| Products（カテゴリ） | 4枠。コレクションを選ぶと名称・写真・リンクが自動。カテゴリ構成が決まるまで「仮」ラベルを表示（ブロックのチェックで消せます） |
| New Arrivals（新着） | Ordify から Shopify に同期された商品を公開日の新しい順で4点。コレクションを指定することも可能 |
| Riders（TOP） | 写真＋全員の名前を2列で表示（ブロック） |
| Journal（TOP） | ブログの最新3件 |
| Instagram | 写真6枚（ブロック）。投稿の自動取り込みは Instagram 連携アプリを導入してこのセクションと置き換え |

## 5. 商品の登録

- 同梱の `../permanent-union-products.csv` を **商品 → インポート** で読み込むと、公式サイト掲載の5商品（GIN JACKET ／ NO TEN JACKET ／ KOVAL JACKET ／ EYGUEBELLE JACKET ／ KOVAL BIB PANTS）がカラー6色×サイズ7（XXS〜XXL）のバリエーション付きで登録されます（在庫数は 0。Ordify 連携後に同期）。
- オプション名は **Color** と **Size**（テーマ設定 > カラーチップで変更可）。
- カラーチップの色は **テーマ設定 → カラーチップ** に「カラー名:カラーコード」で登録（初期値：Midnight / Slate Blue / Wakaba / Babaji / Muku / Kakishibu）。
- **NEW バッジ**：タグ `new` を付けるか、公開から 30 日以内（日数はテーマ設定）。
- **残りわずか／在庫なし**：バリエーションの在庫数（Ordify から同期）で自動表示。しきい値はテーマ設定 > 商品（初期値 3）。
- 商品詳細の **SPEC・サイズ表・導線リンク** はメタフィールド（設定 → カスタムデータ → 商品）で商品ごとに設定できます。未設定でも動作します。

| メタフィールド（名前空間 `custom`） | 型 | 使われる場所 |
|---|---|---|
| `short_description` | 1行テキスト | 商品詳細 上部の短い説明（未設定なら説明文の先頭90字） |
| `subtitle` | 1行テキスト | 商品名の下の一言 |
| `material` `waterproof` `breathability` `finish` `features` `weight` `made_in` | 1行／複数行テキスト | SPEC 表 |
| `size_chart` | リッチテキスト（表） | SIZE CHART（未設定なら項目だけの空の表） |
| `link_column` `link_riders` | URL | 導線カード 01・03 のリンク先（商品ごと） |

## 6. ヘッダー・フッター・カート

- ヘッダー：左 **SHOP**（カートドロワーを開く）／ 中央ロゴ ／ 右 **MENU**（全画面メニュー）。写真の上では白、ペーパー色の上ではブラウンに自動で切り替わります。
- ロゴ画像の差し替え：**テーマ設定 → ロゴ**（ブラウン・白の2種。SVG または透過 PNG 推奨）。未設定の間はテーマ同梱のロゴを表示します。
- カート：追加後はポップアップではなく右からドロワーを表示。数量変更・削除もドロワー内で完結。チェックアウトは Shopify 標準。
- フッター：縄の区切り線＋SHOP／INFORMATION／NEWSLETTER／SNS／ポリシー。

## 7. 支給・確認が必要なもの（テーマ内は仮表示）

- マーシーさんのファーストビュー写真、STORY 01〜03 の写真（現在はテーマ同梱の仮写真）
- ロゴの元データ（SVG／AI。現在は PDF から取り出した PNG）
- 商品説明文（150〜200字）、サイズ表の数値、商品写真（全商品・全カラー）
- ライダーの写真・プロフィール・SNS、取扱店舗の一覧、台湾向けメッセージ
- ご利用ガイド・FAQ・特定商取引法の内容、プライバシーポリシー・利用規約
- 商品カテゴリの構成（決まり次第コレクションを作成し、TOP の「仮」ラベルを外す）

## 8. 構成

```
layout/      theme.liquid, password.liquid
templates/   index / product / collection / cart / blog / article / search / 404 / list-collections /
             page (.about / .riders / .shoplist / .guide / .contact / .legal) / customers / gift_card / password
sections/    TOP: top-background, opening, first-view, story, interlude, products-categories, new-arrivals,
                  riders, journal, instagram
             下層: main-collection, main-product, related-products, main-cart, cart-drawer, about-hero, about-intro,
                  riders-page, shoplist, main-blog, main-article, guide, contact-form, legal-notice, main-page,
                  main-search, main-404, main-list-collections, main-* (customers)
             共通: header, footer（header-group / footer-group）
snippets/    logo, icon, product-card, swatches, cart-line, chapter-indicator, map-japan, pagination, meta-tags
assets/      base.css, theme.js, pu-*.jpg / pu-logo-*.png（同梱写真・ロゴ）
config/      settings_schema.json, settings_data.json
locales/     ja.default.json, en.json
```

## 9. 素材について

- `assets/pu-fv.jpg` `pu-story-01〜07.jpg` `pu-bg-still.jpg` はご提供いただいた写真と白馬の雲海（若山さん撮影）です。公開前に使用許諾・クレジット表記の要否をご確認ください。
- `snippets/map-japan.liquid` の日本地図は Geolonia 社の都道府県 SVG を元に配色を調整したものです。公開前にライセンス表記の要否を確認してください（問題があれば自作の地図に差し替えます）。台湾の形は簡略化した手描きです。
- 商品画像 `assets/pu-*-jacket.jpg` などは FULLMARKS STORE 掲載の画像です。商品を登録すると商品側の画像に置き換わります。

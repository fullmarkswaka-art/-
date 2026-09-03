# PERMANENT UNION — Shopify テーマ

「Be Awesome In The Mountain 〜山にいるときこそ最高であれ〜」をコンセプトにした
PERMANENT UNION のブランドサイト兼オンラインストア用 Shopify テーマ（Online Store 2.0）。

トップページは EC 色を抑え、フルスクリーン動画 → ブランドステートメント → 編集型のコレクション紹介 →
素材へのこだわり → カテゴリー → ライダー → Journal → Instagram の順に、ブランドの世界観を優先して構成しています。

## セットアップ手順

1. **テーマのアップロード**
   Shopify 管理画面 → オンラインストア → テーマ → 「テーマを追加」→「ZIPファイルをアップロード」で
   `permanent-union-theme.zip` をアップロードします。
2. **メニューの作成**（オンラインストア → メニュー）
   - `main-menu`（メインメニュー）: Shell / Tops / Bottoms / Accessories / About / Riders / Shop List
   - `footer`（フッターメニュー）: ショッピングガイド / 製品の修理について / 特定商取引法に基づく表記 / プライバシーポリシー / お問い合わせ
3. **コレクションの作成**（商品 → コレクション）
   `shell` `tops` `bottoms` `accessories` の4つ（ハンドル名は任意。トップの「カテゴリータイル」から選択します）。
   各コレクションにイメージ画像を設定すると、タイルに自動反映されます。
4. **商品の登録**
   オプションは `Color`（Midnight / Slate Blue / Wakaba / Babaji / Muku / Kakishibu）と
   `Size`（XXS〜XXL）を推奨。`new` タグを付けると NEW バッジが表示されます。
   スペック表にはメタフィールド（`custom.material` `custom.waterproof` `custom.breathability`
   `custom.weight` `custom.made_in` `custom.features` `custom.story` `custom.subtitle`）を使用できます。
   （設定 → カスタムデータ → 商品 で定義してください。未設定でも動作します。）
5. **ページの作成**（オンラインストア → ページ）
   - About … テーマテンプレート `page.about`
   - Riders … テーマテンプレート `page.riders`
   - Shop List … テーマテンプレート `page.shoplist`
   - お問い合わせ … テーマテンプレート `page.contact`
6. **ブログ**
   ハンドル `news` のブログを作成すると、トップの Journal セクションに最新記事が表示されます。
7. **ヒーロー動画**
   テーマカスタマイズ → トップページ → 「ヒーロー動画」で設定します。
   - Shopify の動画ピッカー（コンテンツ → ファイル にアップロード）
   - または外部 MP4 の URL（初期値は既存の PU ブランドムービー）
   Adobe Stock の動画は **1920×1080 / 15〜30秒 / H.264 / 10MB 以下** に書き出してから
   Shopify のファイルにアップロードしてください（ループ再生・無音で使用されます）。
8. **ロゴ**
   ヘッダー / フッターセクションでロゴ画像を設定します（透過 PNG 推奨。白ロゴを別途設定可能）。

## 同梱画像について

`assets/pu-*.jpg` は初期表示用にブランドサイトの画像を同梱しています。
テーマエディタで商品・画像を設定すると自動的に置き換わります。
置き換え後は「初期画像（テーマ同梱）」欄を空にし、不要になった画像は削除して構いません。

## 構成

```
layout/      theme.liquid, password.liquid
templates/   index / product / collection / cart / page(.about/.riders/.shoplist/.contact) / blog / article / search / 404 / customers
sections/    hero-video, brand-statement, collection-showcase, image-with-text, category-tiles,
             featured-collection, riders, riders-grid, journal, follow, newsletter, marquee, rich-text,
             page-hero, shoplist, contact-form, main-* (product/collection/cart/page/blog/article/search/404/customers)
snippets/    product-card, price, pagination, icon, meta-tags, cart-drawer
assets/      base.css, theme.js, pu-*.jpg
config/      settings_schema.json, settings_data.json
locales/     ja.default.json, en.json
```

## デザインの要点

- 書体: 和文明朝 Shippori Mincho / 欧文セリフ Cormorant Garamond / UI DM Sans（Google Fonts）
- 配色: 雪面のオフホワイト `#F4F2EE`、チャコール `#1C1A18`、Midnight `#15171A`、アクセントに Slate Blue `#5D6D7E`
- セクション番号 (01)〜、字間の広い小見出し、余白を大きく取った編集的レイアウト
- スクロール時のフェードイン、透過ヘッダー、カートドロワー、AJAX カート

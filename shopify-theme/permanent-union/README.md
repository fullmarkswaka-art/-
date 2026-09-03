# PERMANENT UNION — Shopify テーマ

「Be Awesome In The Mountain 〜山にいるときこそ最高であれ〜」をコンセプトにした
PERMANENT UNION のブランドサイト兼オンラインストア用 Shopify テーマ（Online Store 2.0）。

トップページには商品を置かず、ブランドの世界観と「どんなブランドか」を優先しています。
構成: 3層ヒーロー（動画 / 写真 / テキスト）→ (01) Our Philosophy → (02) About Us（Since 2013）→ 流れるテキスト →
(03) 素材へのこだわり → (04) ライダー → (05) Journal → (06) オンラインストア入口（テキストリンクのみ）→ Instagram → ニュースレター。
商品（カテゴリータイル / コレクション紹介 / おすすめ商品）は Shop ページ（テンプレート `page.shop`）に置いています。

## セットアップ手順

1. **テーマのアップロード**
   Shopify 管理画面 → オンラインストア → テーマ → 「テーマを追加」→「ZIPファイルをアップロード」で
   `permanent-union-theme.zip` をアップロードします。
2. **メニューの作成**（オンラインストア → メニュー）
   - `main-menu`（メインメニュー）: Online Store（→ /pages/shop）/ Shell / Tops / Bottoms / Accessories / About / Riders / Shop List
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
   - Shop … テーマテンプレート `page.shop`（オンラインストアの入口。カテゴリータイル / コレクション紹介 / おすすめ商品）
     ※ トップの「オンラインストア入口」セクションとヒーローのボタン2は `/pages/shop` を指しています
   - About … テーマテンプレート `page.about`
   - Riders … テーマテンプレート `page.riders`
   - Shop List … テーマテンプレート `page.shoplist`
   - お問い合わせ … テーマテンプレート `page.contact`
6. **ブログ**
   ハンドル `news` のブログを作成すると、トップの Journal セクションに最新記事が表示されます。
7. **ヒーロー（3層構成: 動画 / 写真 / テキスト）**
   テーマカスタマイズ → トップページ → 「ヒーロー（動画 / 写真 / テキスト）」で設定します。
   - **最背面 = 動画**: Shopify の動画ピッカー（コンテンツ → ファイル にアップロード）、または外部 MP4 の URL。
     初期値は既存の PU ブランドムービー。Adobe Stock の雪山動画に差し替える手順は下記「Adobe Stock 雪山動画」を参照。
   - **中間 = 写真**: 雪山やライダーの写真を「額装カード」（動画の上に1枚、右 or 左、幅 30〜70%）か
     「全面に重ねる」（不透明度 40〜60% + ブレンド）で配置。スマホでは「小さく表示 / 非表示 / そのまま」を選択。
     初期値はテーマ同梱の `pu-hero.jpg`（仮）。雪山やライダーの写真を設定したら「初期画像」欄は空にしてください。
   - **最前面 = テキスト**: 小見出し / 見出し / サブコピー / ボタン2つ。
8. **ロゴ**
   ヘッダー / フッターセクションでロゴ画像を設定します（透過 PNG 推奨。白ロゴを別途設定可能）。

## Adobe Stock 雪山動画

ライセンス素材はこちらから直接取得できないため、以下を候補としてリストしています。
検索結果のタイトルから選定しているので、購入前に必ずプレビューで動き・色味を確認してください。

| Adobe Stock ID | 内容 | 推奨理由 |
|---|---|---|
| [165410317](https://stock.adobe.com/jp/video/165410317) | 4K Aerial Drone – Hakuba, Nagano Mountains | 白馬・長野。ブランドの拠点と一致。第一候補 |
| [286041309](https://stock.adobe.com/jp/video/286041309) | 4K Aerial – Northern Japanese Alps near Mt. Jonen, Nagano | 北アルプス常念岳の空撮 |
| [985928615](https://stock.adobe.com/jp/video/985928615) | FPV drone – Mt. Karamatsu, Hakuba, fog & mist at sunset | 唐松岳・夕景の霧。ムーディーな世界観向き |
| [1573741572](https://stock.adobe.com/jp/video/1573741572) | Snowy Mountains at Dawn, shrouded in clouds | 雲海と朝焼け。現ヒーロー写真と同じ空気感 |
| [398065128](https://stock.adobe.com/jp/video/398065128) | 4K Aerial Drone – Snow covered mountains of Vail | 海外だが稜線の映像が汎用的 |
| [383311863](https://stock.adobe.com/jp/video/383311863) | 4K drone aerial mountain pan out | 引きの山岳ショット |
| [291813122](https://stock.adobe.com/jp/video/291813122) | Aerial dolly zoom on rocky mountain over snowy hill | 動きのあるカット |
| [1185404533](https://stock.adobe.com/jp/video/1185404533) | Whitefish Montana aerial snowy winter scenery | 森と雪原 |
| [309840037](https://stock.adobe.com/jp/video/309840037) | Aerial drone view of mountain winter forest | 雪の森（サブ用） |

追加で探す場合の検索リンク:
[hakuba](https://stock.adobe.com/jp/search/video?k=hakuba+winter) /
[japan alps snow aerial](https://stock.adobe.com/jp/search/video?k=japan+alps+snow+aerial) /
[powder skiing](https://stock.adobe.com/jp/search/video?k=powder+skiing+slow+motion) /
[wind blowing snow ridge](https://stock.adobe.com/jp/search/video?k=wind+blowing+snow+mountain+ridge)

### 書き出し仕様
- 1920×1080（4K素材は縮小）/ 15〜30秒 / H.264 MP4 / 10MB 以下 / 音声なし / 24〜30fps / ビットレート 3〜5Mbps
- 冒頭と末尾が自然につながるカット（ループ再生）を推奨。テキストが左下に乗るので、左下が暗めか空いている構図が扱いやすい

### アップロードと差し替え
1. Shopify 管理画面 → コンテンツ → ファイル → 「ファイルをアップロード」で MP4 を追加
2. テーマカスタマイズ → トップページ → 「ヒーロー（動画 / 写真 / テキスト）」→「動画（Shopify）」で選択
3. 「動画URL（MP4）」欄は空にする（Shopify 動画が優先されますが、念のため）
4. 「動画のポスター」に静止画を設定すると、読み込み前と動画非対応環境で表示されます

## 同梱画像について

`assets/pu-*.jpg` は初期表示用にブランドサイトの画像を同梱しています。
テーマエディタで商品・画像を設定すると自動的に置き換わります。
置き換え後は「初期画像（テーマ同梱）」欄を空にし、不要になった画像は削除して構いません。

## 構成

```
layout/      theme.liquid, password.liquid
templates/   index / product / collection / cart / page(.shop/.about/.riders/.shoplist/.contact) / blog / article / search / 404 / customers
sections/    hero-video(3層), store-entrance, brand-statement, collection-showcase, image-with-text, category-tiles,
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

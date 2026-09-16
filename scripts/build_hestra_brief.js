// HESTRA 広告作成依頼書（docx）を生成する。使い方: cd scripts && npm i docx && node build_hestra_brief.js ../reports/HESTRA広告_作成依頼書_2026-09-16.docx
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType,
  AlignmentType, HeadingLevel, ShadingType, BorderStyle, LevelFormat, TabStopType,
} = require("docx");

const FONT = { ascii: "Yu Gothic", hAnsi: "Yu Gothic", eastAsia: "Yu Gothic", cs: "Yu Gothic" };
const NAVY = "1F3864";
const P = (text, opts = {}) => new Paragraph({
  spacing: { after: 80, line: 300 }, ...opts.para,
  children: [new TextRun({ text, font: FONT, size: opts.size || 20, bold: opts.bold, color: opts.color })],
});
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 280, after: 120 },
  children: [new TextRun({ text: t, font: FONT, size: 26, bold: true, color: NAVY })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 80 },
  children: [new TextRun({ text: t, font: FONT, size: 22, bold: true, color: NAVY })] });
const B = (t) => new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 60, line: 300 },
  children: [new TextRun({ text: t, font: FONT, size: 20 })] });
const NOTE = (t) => P(t, { size: 17, color: "555555" });

const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(rows, widths, opts = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((r, i) => new TableRow({
      tableHeader: i === 0,
      children: r.map((c, j) => new TableCell({
        width: { size: widths[j], type: WidthType.DXA }, borders,
        shading: i === 0 ? { type: ShadingType.CLEAR, fill: NAVY, color: "auto" }
          : (opts.zebra && i % 2 === 0 ? { type: ShadingType.CLEAR, fill: "F2F5FA", color: "auto" } : undefined),
        margins: { top: 60, bottom: 60, left: 90, right: 90 },
        children: [new Paragraph({ spacing: { after: 0, line: 260 },
          alignment: (i > 0 && opts.right && opts.right.includes(j)) ? AlignmentType.RIGHT : AlignmentType.LEFT,
          children: [new TextRun({ text: String(c), font: FONT, size: 18, bold: i === 0, color: i === 0 ? "FFFFFF" : "000000" })] })],
      })),
    })),
  });
}

const W = 9640; // usable width (A4, 15mm margins ≈ 10.2k; keep a little slack)

const story = [];
story.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "広告作成依頼書", font: FONT, size: 36, bold: true, color: NAVY })] }));
story.push(new Paragraph({ spacing: { after: 240 }, children: [new TextRun({ text: "HESTRA｜Fall / Winter 2026　FULLMARKS ONLINE STORE", font: FONT, size: 24, color: NAVY })] }));

story.push(table([
  ["項目", "内容"],
  ["依頼日", "2026年9月16日"],
  ["ブランド", "HESTRA（表記は必ず「HESTRA」。カタカナ表記は使わない）"],
  ["対象ストア", "FULLMARKS ONLINE STORE（fullmarksstore.jp）"],
  ["広告口座", "Meta: FULLMARKS広告運用 act_976410622096585 ／ Google: FULLMARKS Inc. 6803842189（この2口座以外では配信しない）"],
  ["配信期間", "2026年9月末 開始 〜 2027年1月（本番は10〜1月。以降は在庫と実績で継続判断）"],
  ["月予算（税抜）", "9月 26,000円 ／ 10月 45,951円 ／ 11月 47,483円 ／ 12月 52,078円 ／ 1月 42,888円（広告予算計画_2026-09改訂「FULLMARKS内訳」HESTRA行）"],
  ["依頼先", "（記入）"],
  ["回答希望日", "（記入）"],
], [2200, W - 2200]));

story.push(H1("1. 目的・背景"));
story.push(B("グローブは10〜1月に需要が集中する。前年はHESTRAの広告枠が無く、検索需要（「ヘストラ グローブ」等）はショッピング広告で拾うだけだった。今季は指名検索とMetaカタログの専用枠を持ち、通常価格品で売上を取る。"));
story.push(B("直近90日の検索語は「ヘストラ グローブ」「ヘストラ」「hestra army leather heli ski」「ヘストラ ヘリスキー」「ヘストラ エルゴグリップ」「ヘストラ wakayama」など。購入はまだ0件で、これから立ち上げる枠。"));
story.push(B("Metaカタログ広告 fullmarks-dpa-HESTRA は9/3から存在するが、同じ広告セット内でHOUDINI・POCに予算が寄り、2週間で約200円しか配信されていない。専用の広告セットに切り出す。"));

story.push(H1("2. 商品・在庫の現状（2026-09-15 時点）"));
story.push(table([
  ["項目", "数値", "備考"],
  ["在庫あり商品", "186件", "商品ID先頭「10」= HESTRA"],
  ["うち通常価格（広告対象）", "135件", "custom_label_0 = regular"],
  ["うちアウトレット（広告対象外）", "51件", "方針: アウトレット品は広告しない"],
  ["価格帯", "5,500〜45,100円", "ライナー 5,500円〜、GRIPPEN GS 45,100円"],
  ["主なシリーズ（件数）", "ergo 11 / xc 10 / gauntlet 8 / heli 7 / wakayama 6 / fall 6 / army 6 / expedition 6", "custom_label_1"],
  ["サイトのカテゴリ", "HESTRA_SKI 40 / HESTRA_LINER 23 / HESTRA_KIDS 27 / HESTRA_CLASSIC 16 / HESTRA_CROSS 14 / HESTRA_OUTDOOR 12 / HESTRA_MOUNTAIN 5", "リンク先候補"],
  ["フィード未掲載（在庫あり）", "14件", "下記 6. の一覧。広告開始前にEC側で解消"],
], [3000, 3600, W - 6600]));

story.push(H1("3. 配信構成（依頼内容）"));
story.push(table([
  ["媒体", "キャンペーン／広告セット", "枠", "状態", "開始", "日予算（税抜）", "対象商品・オーディエンス"],
  ["Google", "UC_SK_1_指名_HESTRA", "指名検索", "新設", "9月末", "9月 800円 → 10月 900円 → 11〜12月 1,000円 → 1月 800円", "キーワードは 4. 参照。リンク先 /category/HESTRA/"],
  ["Google", "UC_PL_5_PLA_v2（既存）", "ショッピング", "既存", "配信中", "変更なし（2,500円）", "HESTRA通常価格品は既に対象。フィード未掲載14件を解消すると露出が増える"],
  ["Meta", "UC_DN_3_CVS_フルマークス ＞ 新広告セット「HESTRA」", "カタログ", "新設（既存広告を移動）", "10/1", "10月 600円 → 11〜12月 700円 → 1月 600円", "商品セット「通常価格_HESTRA」2164694404474862（135件、週次で自動更新）。全訪問者30日＋類似"],
  ["Meta", "UC_DN_3_RTG_HESTRA（静止画）", "リターゲティング", "新設・任意", "素材受領後", "300〜500円（予算計画外。他ブランドの減額分から充当、要判断）", "新規オーディエンス「FM_HESTRA訪問者_30日」− 購入者30日。画像素材が必要（5. 参照）"],
], [900, 2300, 1100, 1000, 900, 1700, W - 7900]));
story.push(NOTE("日予算の合計は月予算に合わせる（10月 1,500円/日 ≒ 45,951円/月、11月 1,700円/日、12月 1,700円/日、1月 1,400円/日）。静止画RTGを追加する場合は、9/16に減額した枠（PLA v2・アクリマ/ポック/ノローナ RTG、計 約2,900円/日）から充当する。"));

story.push(H1("4. 広告文（案）"));
story.push(H2("4-1. Google 指名検索（レスポンシブ検索広告）"));
story.push(table([
  ["種別", "文言", "文字数"],
  ["見出し1", "HESTRA｜FULLMARKS", "17"],
  ["見出し2", "FULLMARKS ONLINE STORE", "22"],
  ["見出し3", "1936年創業、スウェーデンの手袋", "30"],
  ["見出し4", "伝統の皮革と機能素材のグローブ", "30"],
  ["見出し5", "Fall / Winter 2026", "18"],
  ["見出し6", "Army Leather Heli Ski", "21"],
  ["見出し7", "Fall Line / Ergo Grip", "21"],
  ["見出し8", "スキー・スノーボードグローブ", "28"],
  ["見出し9", "ライナーからキッズまで", "22"],
  ["説明文1", "1936年スウェーデン生まれのグローブブランド HESTRA。伝統の皮革と機能素材を合わせた一双。", "90"],
  ["説明文2", "Army Leather Heli Ski、Fall Line、Ergo Grip。定番からライナー・キッズまで。", "75"],
  ["説明文3", "HESTRA Fall / Winter 2026 コレクション。FULLMARKS ONLINE STORE。", "64"],
  ["パス", "fullmarksstore.jp/HESTRA", "—"],
  ["最終ページURL", "https://www.fullmarksstore.jp/category/HESTRA/", "—"],
], [1700, W - 2700, 1000], { zebra: true }));
story.push(NOTE("全角換算で見出し30・説明文90以内を確認済み（copy/hestra_google_rsa.json）。「正規販売店」「〇〇を買うなら」は使わない。"));
story.push(H2("キーワード（案）"));
story.push(table([
  ["区分", "キーワード", "マッチタイプ"],
  ["ブランド指名", "ヘストラ／hestra／ヘストラ グローブ／hestra グローブ／ヘストラ 手袋／ヘストラ ミトン／hestra gloves", "完全一致・フレーズ一致"],
  ["用途", "ヘストラ スキー グローブ／ヘストラ スノーボード グローブ／ヘストラ インナー グローブ／ヘストラ ライナー／ヘストラ キッズ／ヘストラ レディース", "フレーズ一致"],
  ["シリーズ", "army leather heli ski／ヘストラ ヘリスキー／hestra fall line／ヘストラ エルゴグリップ／hestra ergo grip／hestra wakayama／ヘストラ 3フィンガー／hestra czone／ヘストラ オムニ", "フレーズ一致"],
  ["除外", "中古／メルカリ／ヤフオク／楽天／amazon／偽物／サイズ表（情報検索）", "除外キーワード"],
], [1700, W - 4200, 2500], { zebra: true }));
story.push(NOTE("入札は既存の指名キャンペーンと同じ「コンバージョン数の最大化」。初月はCPC 15〜30円の想定。検索語の実績を見て2週間後にキーワードを追加・除外する。"));

story.push(H2("4-2. Meta カタログ広告（既存広告を専用広告セットへ）"));
story.push(table([
  ["項目", "内容"],
  ["広告名", "fullmarks-dpa-HESTRA（既存 ID は変更なし）"],
  ["本文", "HESTRA｜Fall / Winter 2026"],
  ["形式", "カルーセル（商品セットから自動）。1広告=1ブランド。他ブランドの商品を混ぜない"],
  ["商品セット", "通常価格_HESTRA（2164694404474862）。retailer_id 列挙、毎週月曜に自動更新。アウトレット51件は含まない"],
  ["リンク先", "各商品ページ（フィードの link）"],
  ["Instagram", "17841404773057326（クリエイティブ作成に必須）"],
], [2200, W - 2200]));

story.push(H2("4-3. Meta 静止画広告（リターゲティング・任意）"));
story.push(table([
  ["項目", "内容"],
  ["見出し", "HESTRA｜Fall / Winter 2026"],
  ["本文", "1936年、スウェーデン南西部の小さな街「ヘストラ」で誕生したグローブブランド。創業時の丈夫な革製手袋を原点とし、現在は伝統的な皮革素材と機能素材を組み合わせ、信頼のおける高品質なグローブとして世界中で愛用されています。（full-marks.com 公式ブランド紹介文をそのまま使用）"],
  ["CTA", "購入する（Shop Now）"],
  ["リンク先", "https://www.fullmarksstore.jp/category/HESTRA/（スキー訴求は /category/HESTRA_SKI/）"],
  ["オーディエンス", "FM_HESTRA訪問者_30日（新規作成: URL に /category/HESTRA または /item/10 を含む訪問者）− FM_購入者_30日"],
  ["配置", "Facebook・Instagram フィード、ストーリーズ／リール（縦長素材がある場合）"],
], [2200, W - 2200]));

story.push(H1("5. 必要な素材（依頼事項）"));
story.push(table([
  ["素材", "仕様", "点数", "用途"],
  ["キービジュアル（正方形）", "1080×1080px、JPG/PNG、文字・ロゴ焼き込みなし", "3点以上", "Meta 静止画（フィード）"],
  ["キービジュアル（縦長）", "1080×1920px、JPG/PNG、文字なし、上下250pxはUI被りを考慮", "3点以上", "Meta ストーリーズ／リール"],
  ["商品カット", "Army Leather Heli Ski／Fall Line／Ergo Grip／Wakayama の着用または物撮り。背景は白または雪山", "各1〜2点", "静止画のバリエーション、Google 画像アセット"],
  ["ブランドロゴ", "PNG（白・黒）、ベクター可", "各1", "Google ビジネスロゴ、Meta"],
  ["使用許諾", "上記素材を FULLMARKS の Meta／Google 広告で使用してよい旨（HESTRA Japan／代理店の確認）", "—", "ブランド側の規定確認（表記・トリミング・期間）"],
  ["商品ページ／カテゴリの整備", "リンク先カテゴリの掲載順（今季主力を上位に）、在庫切れ商品の非表示", "—", "広告からの遷移先"],
], [2400, W - 5600, 1100, 2100]));
story.push(NOTE("画像に文字を入れる場合はブランド名「HESTRA」とシーズン表記のみ。価格・割引・「正規販売店」は入れない。"));

story.push(H1("6. 広告開始前に解消すること"));
story.push(H2("6-1. フィード未掲載の在庫あり商品（14件）"));
story.push(B("gsfeed.xml に載っていないため、Google ショッピング・Meta カタログのどちらにも出ない。EC側（アラジン）でフィード出力の対象に含める。"));
story.push(table([
  ["商品ID", "品番・商品名", "価格"],
  ["1000300900", "30090 GRIPPEN GS", "45,100円"],
  ["1000300910", "30091 GRIPPEN GS MITT", "45,100円"],
  ["1030030200", "3003020 ARMY LEATHER GORE-TEX", "28,600円"],
  ["1030030210", "3003021 ARMY LEATHER GORE-TEX MITT", "28,600円"],
  ["1000317400", "31740 IMPACT RACING JR", "28,600円"],
  ["1030027610", "3002761 CZONE MAUNTAIN MITT", "16,500円"],
  ["1000205600", "20560 OLAV", "16,500円"],
  ["1030049300", "3004930 FEROX CZONE JR", "8,250円"],
  ["1030050510", "3005051 BABY ZIP MITT", "7,700円"],
  ["1030030610", "3003061 EXTREME MITT LINER", "6,600円"],
  ["1030051100", "3005110 TOUCH POINT THERMO", "6,600円"],
  ["1030030500", "3003050 WOMENS FALL LINE LINER", "5,500円"],
  ["1000304310", "30431 OMNI MITT", "19,800円"],
  ["1030030300", "3003030 ERGO GRIP DELTA HDry", "19,800円"],
], [1800, W - 3400, 1600], { zebra: true }));
story.push(H2("6-2. 運用側の準備（Claude が実施・承認後）"));
story.push(B("Meta: カスタムオーディエンス「FM_HESTRA訪問者_30日」作成 → 広告セット「HESTRA」新設（カタログ）→ 既存広告 fullmarks-dpa-HESTRA を移動。"));
story.push(B("Google: キャンペーン UC_SK_1_指名_HESTRA 新設（キーワード・RSA・除外・地域 日本・入札 コンバージョン数の最大化）。作成スクリプトは outlet-rtg と同様に用意する。"));
story.push(B("毎週月曜: catalog-attributes → product-sets --apply で商品セットを更新（新入荷を自動で組み入れ）。"));

story.push(H1("7. 運用ルール・評価"));
story.push(B("アウトレット品は広告しない（51件は商品セット・PLA から除外済み）。"));
story.push(B("表記は「HESTRA」。カタカナ表記、「正規販売店FULLMARKSで」「〇〇を買うなら」は使わない。ブランド紹介文は公式サイトの文をそのまま使う。"));
story.push(B("配信ON/OFF・予算変更は事前承認。ドライランで差分を見せてから適用。"));
story.push(B("評価: 指名検索は ROAS 8 以上、カタログ・静止画は ROAS 3 以上を目安。週次レポート（何が売れたか）でブランド別に確認し、2週間ごとにキーワードと予算を見直す。"));
story.push(B("HESTRA 専用ストアの予定はないため、10〜1月は FULLMARKS 口座で継続する。"));

story.push(H1("8. 承認"));
story.push(table([
  ["項目", "承認", "日付", "備考"],
  ["3. 配信構成・日予算", "□", "", ""],
  ["4-1. Google 広告文・キーワード", "□", "", ""],
  ["4-2. Meta カタログ（広告セット切り出し）", "□", "", ""],
  ["4-3. Meta 静止画（素材受領後）", "□", "", ""],
  ["5. 素材の依頼先・期限", "□", "", ""],
], [3600, 1000, 1600, W - 6200]));

const doc = new Document({
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 420, hanging: 260 } } } }] }] },
  styles: { default: { document: { run: { font: FONT, size: 20 } } } },
  sections: [{ properties: { page: { margin: { top: 1000, bottom: 1000, left: 1000, right: 1000 } } }, children: story }],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(process.argv[2], buf); console.log("wrote", process.argv[2]); });

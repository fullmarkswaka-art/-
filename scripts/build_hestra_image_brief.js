// HESTRA 広告画像 制作依頼書（docx）を生成する。
// 使い方: node scripts/build_hestra_image_brief.js <画像ディレクトリ> <出力.docx>
//   画像ディレクトリには ref_houdini_s.jpg / ref_norrona_s.jpg / prod_<商品ID>_s.jpg を置く（無ければ画像は省略）。
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ImageRun,
  AlignmentType, HeadingLevel, ShadingType, BorderStyle, LevelFormat,
} = require("docx");

const IMG_DIR = process.argv[2];
const OUT = process.argv[3];
const FONT = { ascii: "Yu Gothic", hAnsi: "Yu Gothic", eastAsia: "Yu Gothic", cs: "Yu Gothic" };
const NAVY = "1F3864";
const P = (text, opts = {}) => new Paragraph({
  spacing: { after: 80, line: 300 },
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
function cellPara(content, i, opts) {
  if (typeof content === "object" && content && content.image) return content.image;
  return new Paragraph({ spacing: { after: 0, line: 260 },
    children: [new TextRun({ text: String(content), font: FONT, size: 18, bold: i === 0, color: i === 0 ? "FFFFFF" : "000000" })] });
}
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
        children: [cellPara(c, i, opts)],
      })),
    })),
  });
}
function img(file, w, h) {
  const p = path.join(IMG_DIR, file);
  if (!fs.existsSync(p)) return P(`（画像: ${file}）`, { size: 16, color: "888888" });
  return new Paragraph({ spacing: { after: 0 }, children: [new ImageRun({ type: "jpg", data: fs.readFileSync(p),
    transformation: { width: w, height: h } })] });
}
const W = 9640;

const story = [];
story.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "広告画像 制作依頼書", font: FONT, size: 36, bold: true, color: NAVY })] }));
story.push(new Paragraph({ spacing: { after: 240 }, children: [new TextRun({ text: "HESTRA｜Fall / Winter 2026　Meta 静止画広告用", font: FONT, size: 24, color: NAVY })] }));

story.push(table([
  ["項目", "内容"],
  ["依頼日", "2026年9月16日"],
  ["ブランド", "HESTRA（表記は必ず「HESTRA」。カタカナ表記は使わない）"],
  ["用途", "FULLMARKS ONLINE STORE の Meta 広告（Facebook / Instagram フィード、ストーリーズ／リール）。HESTRA 商品ページ閲覧者へのリターゲティング"],
  ["掲載期間", "2026年10月〜2027年1月（グローブの需要期）"],
  ["納品点数", "必須: 1080×1080 を3案 ／ 推奨: 同じ3案の 1080×1350 と 1080×1920"],
  ["希望納期", "初稿 9月26日（金）／ 修正戻し 9月30日（火）／ 最終納品 10月3日（金）（10月第2週の配信開始）"],
  ["依頼先", "（記入）"],
  ["担当・連絡先", "（記入）"],
], [2200, W - 2200]));

story.push(H1("1. 制作の狙い"));
story.push(B("HESTRA を「1936年からスウェーデンで手袋だけを作り続けてきたブランド」として、上質さと信頼感で見せる。値引きやセール感は出さない。"));
story.push(B("既存の HOUDINI / NORRØNA 静止画（下記 3. 参照）と同じレイアウト・同じ品質で揃え、FULLMARKS のブランド広告として統一感を持たせる。"));
story.push(B("見る人は HESTRA 商品ページを一度見た人。ブランド説明は最小限にし、写真とひと言で「欲しい」に戻す。"));

story.push(H1("2. 納品サイズ・仕様"));
story.push(table([
  ["サイズ（px）", "比率", "用途", "優先度", "注意"],
  ["1080 × 1080", "1:1", "Facebook / Instagram フィード", "必須", "既存広告と同じ。ロゴ右下、見出し左上"],
  ["1080 × 1350", "4:5", "Instagram フィード（縦）", "推奨", "1:1 の上下に写真を伸ばす。文字位置は 1:1 と同じ"],
  ["1080 × 1920", "9:16", "ストーリーズ／リール", "推奨", "上 250px・下 340px は UI に隠れるため文字・ロゴを置かない"],
  ["1200 × 628 ／ 1200 × 1200", "1.91:1 ／ 1:1", "Google 検索広告の画像アセット（任意）", "任意", "文字なしの写真のみ。ロゴ不可"],
], [2000, 1200, 2800, 900, W - 6900], { zebra: true }));
story.push(table([
  ["項目", "指定"],
  ["形式", "JPG（sRGB、品質 90 以上）。1ファイル 30MB 以下。あわせて再編集用の PSD または AI（レイヤー付き）"],
  ["ファイル名", "hestra-202610_v1_1080x1080.jpg のように「ブランド-年月_版_サイズ」。案ごとに v1 / v2 / v3（既存: houdini-202608_v5_1080x1080）"],
  ["文字量", "画像面積の 20% 以内。見出し1行＋サブコピー1行＋ロゴのみ"],
  ["フォント", "既存広告と同じゴシック系（太字の見出し＋細めのサブコピー）。白文字、写真が明るい場合は薄いグラデーションを敷いて可読性を確保"],
  ["ロゴ", "HESTRA 公式ロゴ（白）を右下。ブランド規定の余白・最小サイズを守る。FULLMARKS のロゴは入れない"],
  ["色", "写真の色味を活かす。HESTRA の世界観（革・雪・北欧の冬）から外れる加工はしない"],
], [2200, W - 2200]));

story.push(H1("3. レイアウト参考（既存の配信中広告）"));
story.push(P("下の2点が現在配信中の FULLMARKS ブランド広告です。HESTRA もこの構成に揃えてください。写真フルブリード、見出し（太字）＋サブコピー（細字）、ブランドロゴ右下。"));
story.push(table([
  ["HOUDINI（houdini-202608_v5_1080x1080）", "NORRØNA（norrona-202608_v5_1080x1080）"],
  [{ image: img("ref_houdini_s.jpg", 300, 300) }, { image: img("ref_norrona_s.jpg", 300, 300) }],
  ["見出し左上「軽くて、伸びて、蒸れにくい。」＋サブ「スウェーデン発、動くためのウェア」、ロゴ右下", "見出し左下「北欧の山で鍛えられた、タフなウェア。」＋サブ「1929年創業、ノルウェーの老舗アウトドアブランド」、ロゴ右下"],
], [W / 2, W / 2]));
story.push(NOTE("見出しの位置は写真の抜け（空・雪面など）に合わせて上下どちらでも可。人物の顔や商品に文字を重ねない。"));

story.push(H1("4. コピー（3案。1案につき1点制作）"));
story.push(table([
  ["案", "見出し（太字）", "サブコピー（細字）", "狙い・写真の指定"],
  ["A（推奨）", "1936年から、手袋だけ。", "スウェーデンの小さな街 HESTRA 生まれのグローブ", "ブランドの専業性。工房や革の質感が分かる写真、または雪山で手元が主役のカット"],
  ["B", "革は、使うほど手に馴染む。", "伝統の皮革と機能素材。HESTRA のグローブ", "素材訴求。Army Leather Heli Ski など革グローブのクローズアップ"],
  ["C", "Fall / Winter 2026", "HESTRA GLOVES", "コレクション訴求。文字を最小にし、写真で見せる。ブランド公式のシーズンビジュアル向き"],
], [1100, 2700, 3000, W - 6800], { zebra: true }));
story.push(NOTE("ブランド紹介文（本文）は広告の投稿テキスト側に入れるため、画像には入れません。公式紹介文: 「1936年、スウェーデン南西部の小さな街「ヘストラ」で誕生したグローブブランド。創業時の丈夫な革製手袋を原点とし、現在は伝統的な皮革素材と機能素材を組み合わせ、信頼のおける高品質なグローブとして世界中で愛用されています。」（full-marks.com）"));

story.push(H1("5. 写真素材"));
story.push(H2("5-1. 優先して使う素材"));
story.push(B("HESTRA 公式の Fall / Winter 2026 ルックブック・キービジュアル（雪山、スキー、街の冬）。HESTRA Japan（輸入元）に広告使用の許諾と元データ（高解像度）を依頼する。"));
story.push(B("公式素材が間に合わない場合は、下記 5-2 の商品を使った物撮り（白背景または木・革の質感のある背景）で制作する。"));
story.push(H2("5-2. 写真に使う商品（通常価格・在庫あり。アウトレット品は使わない）"));
story.push(table([
  ["商品", "品番・商品名", "価格（税込）", "商品ページ"],
  [{ image: img("prod_1030030220_s.jpg", 100, 150) }, "3003022 ARMY LEATHER GORE-TEX 3-FINGER（army）", "28,600円", "fullmarksstore.jp/item/1030030220.html"],
  [{ image: img("prod_1000305700_s.jpg", 100, 150) }, "30570 HELI SKI（heli）", "22,000円", "fullmarksstore.jp/item/1000305700.html"],
  [{ image: img("prod_1030007800_s.jpg", 100, 150) }, "3000780 FALL LINE（fall）", "24,200円", "fullmarksstore.jp/item/1030007800.html"],
  [{ image: img("prod_1030006600_s.jpg", 100, 150) }, "3000660 WAKAYAMA（wakayama）", "22,000円", "fullmarksstore.jp/item/1030006600.html"],
  [{ image: img("prod_1030036500_s.jpg", 100, 150) }, "3003650 ERGO GRIP HDRY DESCENT（ergo）", "27,500円", "fullmarksstore.jp/item/1030036500.html"],
], [1400, 3800, 1400, W - 6600]));
story.push(NOTE("商品画像は商品ページの掲載写真（1440×2160）。広告用にはブランド提供の高解像度データを優先し、商品ページ画像は構図の参考として扱う。他ブランドの商品・ウェアを同じ画像に写し込まない。"));

story.push(H1("6. NG事項"));
story.push(B("価格、割引率、「SALE」「OUTLET」の表示。"));
story.push(B("「正規販売店」「〇〇を買うなら」などの店側の売り文句。FULLMARKS の店名・ロゴも画像には入れない。"));
story.push(B("ブランド名のカタカナ表記（ヘストラ）。ロゴ・名称は必ず「HESTRA」。"));
story.push(B("他ブランド（HOUDINI / NORRØNA / POC 等）との混在。1画像＝1ブランド。"));
story.push(B("公式素材のトリミングでロゴやモデルの顔を切る、色味を大きく変える、といったブランド規定に反する加工。"));

story.push(H1("7. 納品・確認の流れ"));
story.push(table([
  ["段階", "日程", "内容"],
  ["素材確認", "9月19日（金）", "HESTRA Japan からの公式素材の有無・使用許諾を確認（FULLMARKS）"],
  ["初稿", "9月26日（金）", "3案 × 1080×1080 を提出。FULLMARKS がコピーとレイアウトを確認"],
  ["修正戻し", "9月30日（火）", "修正指示は1回にまとめる"],
  ["最終納品", "10月3日（金）", "3案 × 3サイズ（JPG）＋ PSD/AI。ファイル名規則どおり"],
  ["入稿・配信", "10月第2週", "Meta 広告に登録し審査後に配信開始。配信結果は週次レポートで共有"],
], [1600, 1900, W - 3500], { zebra: true }));

story.push(H1("8. 承認"));
story.push(table([
  ["項目", "承認", "日付", "備考"],
  ["4. コピー3案", "□", "", ""],
  ["5. 使用する写真素材", "□", "", ""],
  ["7. スケジュール", "□", "", ""],
], [3600, 1000, 1600, W - 6200]));

const doc = new Document({
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 420, hanging: 260 } } } }] }] },
  styles: { default: { document: { run: { font: FONT, size: 20 } } } },
  sections: [{ properties: { page: { margin: { top: 1000, bottom: 1000, left: 1000, right: 1000 } } }, children: story }],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT); });

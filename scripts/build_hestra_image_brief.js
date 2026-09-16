// HESTRA 画像制作依頼書（docx、画像制作のみ）を生成する。
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
story.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "画像制作依頼書", font: FONT, size: 36, bold: true, color: NAVY })] }));
story.push(new Paragraph({ spacing: { after: 240 }, children: [new TextRun({ text: "HESTRA｜Fall / Winter 2026", font: FONT, size: 24, color: NAVY })] }));

story.push(table([
  ["項目", "内容"],
  ["依頼日", "2026年9月16日"],
  ["ブランド", "HESTRA（表記は「HESTRA」で統一。カタカナ表記は使わない）"],
  ["用途", "Instagram / Facebook 広告用の静止画"],
  ["納品物", "3案 × 1080×1080（必須）。可能であれば同じ3案の 1080×1350 と 1080×1920"],
  ["納期", "初稿 9月26日（金）／ 最終納品 10月3日（金）"],
  ["依頼先", "（記入）"],
], [2200, W - 2200]));

story.push(H1("1. 仕上がりイメージ（配信中の他ブランド広告に揃える）"));
story.push(P("写真をフルブリードで使い、見出し（太字）＋サブコピー（細字）を白文字で、ブランドロゴを右下に置く構成です。"));
story.push(table([
  ["HOUDINI", "NORRØNA"],
  [{ image: img("ref_houdini_s.jpg", 300, 300) }, { image: img("ref_norrona_s.jpg", 300, 300) }],
], [W / 2, W / 2]));
story.push(NOTE("見出しの位置は写真の抜け（空・雪面など）に合わせて上でも下でも可。人物の顔や商品に文字を重ねない。"));

story.push(H1("2. サイズ・仕様"));
story.push(table([
  ["サイズ（px）", "比率", "用途", "注意"],
  ["1080 × 1080", "1:1", "フィード（必須）", "上の参考と同じ構成"],
  ["1080 × 1350", "4:5", "Instagram フィード縦", "1:1 の上下に写真を伸ばす。文字位置は同じ"],
  ["1080 × 1920", "9:16", "ストーリーズ／リール", "上 250px・下 340px には文字・ロゴを置かない"],
], [2000, 1000, 2800, W - 5800], { zebra: true }));
story.push(table([
  ["項目", "指定"],
  ["形式", "JPG（sRGB）＋ 再編集用の PSD または AI（レイヤー付き）"],
  ["ファイル名", "hestra-202610_v1_1080x1080.jpg（案ごとに v1 / v2 / v3）"],
  ["文字", "見出し1行＋サブコピー1行のみ。白文字。写真が明るい場合は薄いグラデーションを敷いて可読性を確保"],
  ["ロゴ", "HESTRA 公式ロゴ（白）を右下。FULLMARKS のロゴは入れない"],
  ["色", "写真の色味を活かす。革・雪・北欧の冬の空気感"],
], [2200, W - 2200]));

story.push(H1("3. コピー（3案。1案につき1点）"));
story.push(table([
  ["案", "見出し（太字）", "サブコピー（細字）", "写真の方向性"],
  ["A", "1936年から、手袋だけ。", "スウェーデンの小さな街 HESTRA 生まれのグローブ", "革の質感や工房感、または雪山で手元が主役のカット"],
  ["B", "革は、使うほど手に馴染む。", "伝統の皮革と機能素材。HESTRA のグローブ", "革グローブのクローズアップ"],
  ["C", "Fall / Winter 2026", "HESTRA GLOVES", "文字は最小。ブランドのシーズンビジュアルをそのまま活かす"],
], [700, 2900, 3200, W - 6800], { zebra: true }));

story.push(H1("4. 写真素材"));
story.push(B("HESTRA 公式の Fall / Winter 2026 ビジュアル（雪山・スキー・冬の街）を優先。高解像度データと広告使用の許諾は FULLMARKS から HESTRA Japan に依頼します。"));
story.push(B("公式素材が使えない場合は、下記の商品で物撮り（白背景、または木・革の質感のある背景）。"));
story.push(table([
  ["商品", "品番・商品名", "商品ページ"],
  [{ image: img("prod_1030030220_s.jpg", 90, 135) }, "3003022 ARMY LEATHER GORE-TEX 3-FINGER", "fullmarksstore.jp/item/1030030220.html"],
  [{ image: img("prod_1000305700_s.jpg", 90, 135) }, "30570 HELI SKI", "fullmarksstore.jp/item/1000305700.html"],
  [{ image: img("prod_1030007800_s.jpg", 90, 135) }, "3000780 FALL LINE", "fullmarksstore.jp/item/1030007800.html"],
  [{ image: img("prod_1030006600_s.jpg", 90, 135) }, "3000660 WAKAYAMA", "fullmarksstore.jp/item/1030006600.html"],
  [{ image: img("prod_1030036500_s.jpg", 90, 135) }, "3003650 ERGO GRIP HDRY DESCENT", "fullmarksstore.jp/item/1030036500.html"],
], [1300, 4400, W - 5700]));

story.push(H1("5. 入れないもの"));
story.push(B("価格、割引、「SALE」「OUTLET」の表示"));
story.push(B("「正規販売店」「〇〇を買うなら」などの売り文句、FULLMARKS の店名・ロゴ"));
story.push(B("ブランド名のカタカナ表記"));
story.push(B("他ブランドの商品・ウェアの写り込み（1画像＝1ブランド）"));

const doc = new Document({
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 420, hanging: 260 } } } }] }] },
  styles: { default: { document: { run: { font: FONT, size: 20 } } } },
  sections: [{ properties: { page: { margin: { top: 1000, bottom: 1000, left: 1000, right: 1000 } } }, children: story }],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT); });

// 新入荷（NEW ARRIVAL）広告の画像制作依頼書（docx、画像制作のみ）を生成する。
// 使い方: node scripts/build_new_arrival_image_brief.js <参考画像ディレクトリ> <出力.docx>
//   参考画像ディレクトリには houdini-pace_v1_1080x1080.jpg / norrona-senja_v1_1080x1080.jpg を置く（無ければ省略）。
// 元資料: ユーザー提供「新入荷広告」表（2026-09-29）。ブランドの広告として作る（特定商品に絞らない）。
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ImageRun,
  AlignmentType, HeadingLevel, ShadingType, BorderStyle, LevelFormat, PageBreak,
} = require("docx");

const IMG_DIR = process.argv[2];
const OUT = process.argv[3];
const FONT = { ascii: "Yu Gothic", hAnsi: "Yu Gothic", eastAsia: "Yu Gothic", cs: "Yu Gothic" };
const NAVY = "1F3864";
const P = (text, opts = {}) => new Paragraph({
  spacing: { after: 80, line: 300 },
  children: [new TextRun({ text, font: FONT, size: opts.size || 20, bold: opts.bold, color: opts.color })],
});
const H1 = (t, pageBreak) => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: !!pageBreak,
  spacing: { before: 280, after: 120 },
  children: [new TextRun({ text: t, font: FONT, size: 26, bold: true, color: NAVY })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 80 },
  children: [new TextRun({ text: t, font: FONT, size: 22, bold: true, color: NAVY })] });
const B = (t) => new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 60, line: 300 },
  children: [new TextRun({ text: t, font: FONT, size: 20 })] });
const NOTE = (t) => P(t, { size: 17, color: "555555" });

const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
function cellPara(content, i) {
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
        children: [cellPara(c, i)],
      })),
    })),
  });
}
function img(file, w, h) {
  const p = IMG_DIR ? path.join(IMG_DIR, file) : "";
  if (!p || !fs.existsSync(p)) return P(`（画像: ${file}）`, { size: 16, color: "888888" });
  return new Paragraph({ spacing: { after: 0 }, children: [new ImageRun({ type: "jpg", data: fs.readFileSync(p),
    transformation: { width: w, height: h } })] });
}
const W = 9640;

// ---- ブランドごとの内容 ----
const BRANDS = [
  {
    name: "ACLIMA", file: "aclima", timing: "制作完了後すぐに",
    theme: "WARMWOOL・WOOLNET を中心とした、冬のウールの下着・中間着",
    scene: "寒い屋外（雪の森・冬の山小屋・朝の冷えた空気）で、ウールのベースレイヤーを着ている人物。肌に近いウールの質感（編み目・起毛感）が伝わる寄りのカットもあると良い",
    why: "メリノウールで汗冷えしにくく、暖かい。冬の外遊びの「一枚目」",
    copyA: ["NEW ARRIVAL", "ACLIMA｜Fall / Winter 2026"],
    copyB: ["冬の一枚目は、ウール。", "ACLIMA WARMWOOL / WOOLNET"],
    link: "商品一覧 または 特集ページ（EC側で決定）",
    notes: ["ブランド表記は「ACLIMA」。", "下着の着用カットは、露出が強すぎないもの（Meta の広告審査対策）。"],
  },
  {
    name: "NORRØNA", file: "norrona", timing: "次の入荷後すぐに",
    theme: "スキー・スノーボードのウェア（lofoten ほか）",
    scene: "雪山を滑っている、または滑る直前の人物。深い雪・急斜面・北欧の山の空気感。ウェアの色が雪に映えるカット",
    why: "ノルウェーの山で鍛えられた、滑るためのウェア",
    copyA: ["NEW ARRIVAL", "NORRØNA｜Ski & Snowboard"],
    copyB: ["滑るために、つくられた。", "NORRØNA Ski & Snowboard Collection"],
    link: "https://www.fullmarksstore.jp/topics_detail.html?info_id=25318",
    notes: ["表記は必ず「NORRØNA」（Ø）。カタカナは使わない。", "シリーズ名を入れる場合は小文字（lofoten など）がブランドの表記。"],
  },
  {
    name: "HOUDINI", file: "houdini", timing: "次の入荷後すぐに",
    theme: "主力の中間着（フリース・ウール系のミッドレイヤー）",
    scene: "山や街で、中間着を一枚で着ている人物。アクティブな場面と日常の場面のどちらでも。シェル（アウター）が主役に見えないカット",
    why: "山でも街でも一枚で着られる、長く使える中間着",
    copyA: ["NEW ARRIVAL", "HOUDINI｜Fall / Winter 2026"],
    copyB: ["山でも街でも、一枚で。", "HOUDINI Midlayer Collection"],
    link: "https://www.fullmarksstore.jp/topics_detail.html?info_id=25184",
    notes: ["配信中の PACE SERIES の画像（参考画像）とトーンを揃える。", "シェル（アウター）は今回の主役にしない。"],
  },
  {
    name: "HESTRA", file: "hestra", timing: "10月上旬",
    theme: "冬のグローブ（スキー・革・ウール）",
    scene: "雪の中でグローブを着けた手元が主役のカット。革の質感が見える寄り、または雪山でストックやボードを握る手元",
    why: "1936年から手袋だけをつくり続けるブランドの、革と機能素材のグローブ",
    copyA: ["NEW ARRIVAL", "HESTRA｜Fall / Winter 2026"],
    copyB: ["1936年から、手袋だけ。", "HESTRA GLOVES"],
    link: "特集ページ（EC側で作成中）",
    notes: ["ブランドの画像素材が少ないため、公式ビジュアルが足りない場合は商品の物撮り（白背景、または木・革の質感のある背景）で構成してよい。",
            "9/16 の HESTRA 画像制作依頼書と同じ方向性。今回はその NEW ARRIVAL 版として扱う。"],
  },
  {
    name: "POC", file: "poc", timing: "主力商品の入荷後",
    theme: "新しいヘルメットとゴーグル",
    scene: "新作のヘルメットとゴーグルを着けたスキーヤー・スノーボーダー。顔まわりの寄りのカットで、ヘルメットとゴーグルの形・色がはっきり見えるもの",
    why: "スウェーデン生まれ。命を守るためにデザインされたヘルメットとゴーグル",
    copyA: ["NEW ARRIVAL", "POC｜Helmets & Goggles"],
    copyB: ["守るための、デザイン。", "POC Fall / Winter 2026"],
    link: "特集ページ（EC側で作成）",
    notes: ["新作アイテムが写っている画像を使う（旧モデルが主役に見えないように）。"],
  },
];

const story = [];
story.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "画像制作依頼書", font: FONT, size: 36, bold: true, color: NAVY })] }));
story.push(new Paragraph({ spacing: { after: 240 }, children: [new TextRun({ text: "新入荷（NEW ARRIVAL）広告｜Fall / Winter 2026", font: FONT, size: 24, color: NAVY })] }));

story.push(table([
  ["項目", "内容"],
  ["依頼日", "2026年9月29日"],
  ["対象ブランド", BRANDS.map(b => b.name).join(" / ")],
  ["用途", "Instagram / Facebook 広告用の静止画（新しいお客さまを含む全員向けに配信）"],
  ["作るもの", "ブランドごとに2案（A: NEW ARRIVAL 型、B: メッセージ型）× 3サイズ"],
  ["公開時期", "ブランドごとに異なる（各ページ参照）。納期は各入荷・公開時期に合わせて別途相談"],
], [2200, W - 2200]));

story.push(H1("1. この広告の考え方"));
story.push(B("特定の商品ではなく、ブランドの「今シーズンの新作が入った」ことを伝える広告です。商品ごとの広告は別途、自動の商品広告（カタログ広告）で出しています。"));
story.push(B("ただし、見た人が「何が入ったか」を一目でわかるように、ブランドごとに見せる種類・場面を指定しています（品番の指定はしません）。"));
story.push(B("リンク先は各ブランドの新作ページです。広告で見たものが、リンク先ですぐ見つかる写真にしてください。"));

story.push(H1("2. 仕上がりイメージ（配信中の広告に揃える）"));
story.push(P("写真をフルブリードで使い、見出し（太字）＋サブコピー（細字）を白文字で、ブランドロゴを右下に置く構成です。"));
story.push(table([
  ["HOUDINI（PACE SERIES）", "NORRØNA（senja）"],
  [{ image: img("houdini-pace_v1_1080x1080.jpg", 290, 290) }, { image: img("norrona-senja_v1_1080x1080.jpg", 290, 290) }],
], [W / 2, W / 2]));
story.push(NOTE("見出しの位置は写真の抜け（空・雪面など）に合わせて上でも下でも可。人物の顔や商品に文字を重ねない。"));

story.push(H1("3. サイズ・仕様（全ブランド共通）"));
story.push(table([
  ["サイズ（px）", "比率", "用途", "注意"],
  ["1080 × 1080", "1:1", "フィード（必須）", "上の参考と同じ構成"],
  ["1080 × 1350", "4:5", "Instagram フィード縦", "1:1 の上下に写真を伸ばす。文字位置は同じ"],
  ["1080 × 1920", "9:16", "ストーリーズ／リール", "上 250px・下 340px には文字・ロゴを置かない"],
], [2000, 1000, 2800, W - 5800], { zebra: true }));
story.push(table([
  ["項目", "指定"],
  ["形式", "JPG（sRGB）＋ 再編集用の PSD または AI（レイヤー付き）"],
  ["ファイル名", "<ブランド>-newarrival-202610_A_1080x1080.jpg（例: houdini-newarrival-202610_B_1080x1920.jpg）"],
  ["文字", "見出し1行＋サブコピー1行のみ。白文字。写真が明るい場合は薄いグラデーションを敷いて可読性を確保"],
  ["ロゴ", "各ブランドの公式ロゴ（白）を右下。FULLMARKS のロゴは入れない"],
  ["写真", "各ブランドの Fall / Winter 2026 公式ビジュアルを優先（広告使用の許諾は FULLMARKS 側で確認）"],
], [2200, W - 2200]));

story.push(H1("4. 入れないもの（全ブランド共通）"));
story.push(B("価格、割引、「SALE」「OUTLET」の表示"));
story.push(B("「正規販売店」「〇〇を買うなら」などの売り文句、FULLMARKS の店名・ロゴ"));
story.push(B("ブランド名のカタカナ表記（NORRØNA は Ø で表記）"));
story.push(B("他ブランドの商品・ウェアの写り込み（1画像＝1ブランド）"));

BRANDS.forEach((b, i) => {
  story.push(H1(`${5 + i}. ${b.name}`, true));
  story.push(table([
    ["項目", "内容"],
    ["公開時期", b.timing],
    ["見せるもの", b.theme],
    ["写真の場面", b.scene],
    ["伝えたいこと", b.why],
    ["リンク先", b.link],
  ], [2000, W - 2000]));
  story.push(H2("コピー（2案。1案につき1点×3サイズ）"));
  story.push(table([
    ["案", "見出し（太字）", "サブコピー（細字）"],
    ["A（NEW ARRIVAL 型）", b.copyA[0], b.copyA[1]],
    ["B（メッセージ型）", b.copyB[0], b.copyB[1]],
  ], [2400, 3400, W - 5800], { zebra: true }));
  story.push(NOTE("コピーは仮。写真に合わせて文字量を減らすのは可（見出しだけ、など）。"));
  story.push(H2("注意"));
  b.notes.forEach(n => story.push(B(n)));
});

const doc = new Document({
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 420, hanging: 260 } } } }] }] },
  styles: { default: { document: { run: { font: FONT, size: 20 } } } },
  sections: [{ properties: { page: { margin: { top: 1000, bottom: 1000, left: 1000, right: 1000 } } }, children: story }],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT); });

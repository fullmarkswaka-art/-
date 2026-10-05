// 新入荷（NEW ARRIVAL）広告の画像制作依頼書（docx、画像制作のみ）を、ブランドごとに1ファイルずつ生成する。
// 使い方: node scripts/build_new_arrival_image_brief.js <参考画像ディレクトリ> <出力ディレクトリ>
//   参考画像ディレクトリには houdini-pace_v1_1080x1080.jpg / norrona-senja_v1_1080x1080.jpg を置く
//   （copy/creatives/202609 にある。無ければ省略）。
// 元資料: ユーザー提供「新入荷広告」表（2026-09-29）。ブランドの広告として作る（特定商品に絞らない）。
// 2026-10-05 改訂: ユーザー指示「ブランド別にして、見やすく整理」→ 1ブランド＝1ファイル。
//   同日「写真の選び方・コピー・入れないもの・最終チェックは消して詰めて」→ 1ページ
//   （伝えたいこと・仕上がりイメージ・サイズ・納品ファイル名）。BRANDS の ok/ng/copy/notes は確定内容の控えとして残す（出力しない）。
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ImageRun,
  AlignmentType, ShadingType, BorderStyle, VerticalAlign,
} = require("docx");

const IMG_DIR = process.argv[2];
const OUT_DIR = process.argv[3];
const FONT = { ascii: "Yu Gothic", hAnsi: "Yu Gothic", eastAsia: "Yu Gothic", cs: "Yu Gothic" };
const NAVY = "1F3864", GREY = "666666", LIGHT = "F2F5FA";
const W = 9640;  // A4・左右余白 1000

const run = (text, o = {}) => new TextRun({ text, font: FONT, size: o.size || 20, bold: o.bold, color: o.color });
const P = (text, o = {}) => new Paragraph({ spacing: { before: o.before || 0, after: o.after ?? 80, line: o.line ?? 290 },
  alignment: o.align, children: Array.isArray(text) ? text : [run(text, o)] });
const H = (num, t) => new Paragraph({ spacing: { before: 200, after: 80 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: NAVY, space: 2 } },
  children: [run(num ? `${num}  ` : "", { size: 24, bold: true, color: NAVY }), run(t, { size: 24, bold: true, color: NAVY })] });
const NOTE = (t) => P(t, { size: 17, color: GREY, before: 40 });

const line = { style: BorderStyle.SINGLE, size: 4, color: "C8CFDA" };
const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const BORDERS = { top: line, bottom: line, left: line, right: line };
const NO_BORDERS = { top: none, bottom: none, left: none, right: none };

function cell(children, width, o = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA }, borders: o.borders || BORDERS,
    shading: o.fill ? { type: ShadingType.CLEAR, fill: o.fill, color: "auto" } : undefined,
    margins: { top: o.pad ?? 55, bottom: o.pad ?? 55, left: 120, right: 120 },
    verticalAlign: o.valign || VerticalAlign.TOP, columnSpan: o.span,
    children: Array.isArray(children) ? children : [children],
  });
}
const tbl = (rows, widths) => new Table({ width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
  columnWidths: widths, rows: rows.map(r => new TableRow({ children: r })) });
// 見出し付きの表（1行目を紺）
function grid(rows, widths) {
  return tbl(rows.map((r, i) => r.map((c, j) => cell(
    typeof c === "string" ? P(c, { after: 0, size: 19, bold: i === 0, color: i === 0 ? "FFFFFF" : undefined }) : c,
    widths[j], { fill: i === 0 ? NAVY : (i % 2 === 0 ? LIGHT : undefined) }))), widths);
}
// 左ラベル＋右内容の表（ラベル列は薄い紺）
function kv(rows, labelW = 2100) {
  return tbl(rows.map(([k, v]) => [
    cell(P(k, { after: 0, size: 19, bold: true, color: NAVY }), labelW, { fill: LIGHT, valign: VerticalAlign.CENTER }),
    cell(Array.isArray(v) ? v : P(v, { after: 0, size: 20 }), W - labelW, { valign: VerticalAlign.CENTER }),
  ]), [labelW, W - labelW]);
}
function img(file, w, h) {
  const p = IMG_DIR ? path.join(IMG_DIR, file) : "";
  if (!p || !fs.existsSync(p)) return P(`（画像: ${file}）`, { size: 16, color: "888888" });
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
    children: [new ImageRun({ type: "jpg", data: fs.readFileSync(p), transformation: { width: w, height: h } })] });
}

// ---- ブランドごとの内容 ----
const BRANDS = [
  {
    name: "ACLIMA", file: "aclima", timing: "制作完了後すぐに",
    theme: "WARMWOOL・WOOLNET を中心とした、冬のウールの下着・中間着",
    why: "メリノウールで汗冷えしにくく、暖かい。冬の外遊びの「一枚目」",
    ok: ["ウールそのものが主役。WARMWOOL の起毛やループ、WOOLNET の網目が、スマホの画面でも分かるくらい寄った写真",
         "着用カットなら、寒い場所で一枚で着ていて暖かそうに見えるもの（吐く息が白い、霜・雪など寒さが分かる要素）"],
    ng: ["素材の違いが見えない引きの写真（ただのインナー姿に見える）", "他社の下着と区別がつかない無地の着用写真",
         "露出が強すぎる下着の着用カット（Meta の広告審査で止まるため）"],
    copyA: ["NEW ARRIVAL", "ACLIMA｜Fall / Winter 2026"],
    copyB: ["冬の一枚目は、ウール。", "ACLIMA WARMWOOL / WOOLNET"],
    link: "商品一覧 または 特集ページ（EC側で決定）",
    notes: ["ブランド表記は「ACLIMA」。"],
  },
  {
    name: "NORRØNA", file: "norrona", timing: "次の入荷後すぐに",
    theme: "スキー・スノーボードのウェア（lofoten ほか）",
    why: "ノルウェーの山で鍛えられた、滑るためのウェア",
    ok: ["ウェアが主役として大きく写り、ひと目で NORRØNA と分かる写真",
         "lofoten 特有のはっきりした配色・切り替えのデザイン、胸や袖のロゴが見える",
         "深雪や吹雪の中で、ウェアが働いている瞬間（雪煙を浴びている、雪をはじいている）だと、なお良い",
         "写っている色・モデルは今季の入荷分で、リンク先で買えるもの"],
    ng: ["人物が小さく、雪山の景色が主役の写真（どのスキーブランドでも同じに見える）", "ロゴや特徴的な配色が見えない写真",
         "入荷していない色・旧モデルが主役の写真"],
    copyA: ["NEW ARRIVAL", "NORRØNA｜Ski & Snowboard"],
    copyB: ["滑るために、つくられた。", "NORRØNA Ski & Snowboard Collection"],
    link: "https://www.fullmarksstore.jp/topics_detail.html?info_id=25318",
    notes: ["表記は必ず「NORRØNA」（Ø）。カタカナは使わない。", "シリーズ名を入れる場合は小文字（lofoten など）がブランドの表記。"],
  },
  {
    name: "HOUDINI", file: "houdini", timing: "次の入荷後すぐに",
    theme: "主力の中間着（フリース・ウール系のミッドレイヤー）",
    why: "山でも街でも一枚で着られる、長く使える中間着",
    ok: ["Power シリーズのフリースの表情、Lykan・Alto のウールの質感など、HOUDINI らしい素材が分かる寄りの写真",
         "または、一枚で着て様になっている全身の写真（ミニマルなデザインと色が伝わるもの）",
         "写っている色は今季の入荷分"],
    ng: ["アウター（シェル）が主役の写真", "素材感の分からない引きの写真",
         "他ブランドのウェアと重ね着していて、HOUDINI がどれか分からない写真"],
    copyA: ["NEW ARRIVAL", "HOUDINI｜Fall / Winter 2026"],
    copyB: ["山でも街でも、一枚で。", "HOUDINI Midlayer Collection"],
    link: "https://www.fullmarksstore.jp/topics_detail.html?info_id=25184",
    notes: ["配信中の PACE SERIES の画像（2ページ目の参考画像）とトーンを揃える。"],
  },
  {
    name: "HESTRA", file: "hestra", timing: "10月上旬",
    theme: "冬のグローブ（スキー・革・ウール）",
    why: "1936年から手袋だけをつくり続けるブランドの、革と機能素材のグローブ",
    ok: ["グローブだけが主役の手元アップ",
         "革のしわ・ステッチ・HESTRA のタグなど、作りの良さとブランドが分かる寄りの写真",
         "使う場面なら、雪の中でストックやロープを握る・雪をつかむなど、手元が働いている瞬間"],
    ng: ["手元が小さく、全身や景色が主役の写真", "ブランドのタグやロゴが見えない写真"],
    copyA: ["NEW ARRIVAL", "HESTRA｜Fall / Winter 2026"],
    copyB: ["1936年から、手袋だけ。", "HESTRA GLOVES"],
    link: "特集ページ（EC側で作成中）",
    notes: ["公式ビジュアルが足りない場合は、商品の物撮り（白背景、または木・革の質感のある背景）で構成してよい。",
            "9/16 の HESTRA 画像制作依頼書と同じ方向性。今回はその NEW ARRIVAL 版。"],
  },
  {
    name: "POC", file: "poc", timing: "主力商品の入荷後",
    theme: "新しいヘルメットとゴーグル",
    why: "スウェーデン生まれ。命を守るためにデザインされたヘルメットとゴーグル",
    ok: ["顔まわりの寄り。ヘルメットとゴーグルの形・色・ロゴが画面の大きな部分を占める写真",
         "POC らしい形（丸みのあるシェル、大きなレンズ）が一瞬で分かる",
         "写っているのは今季の新作で、リンク先で買えるモデル"],
    ng: ["人物が小さく、ヘルメットの形が分からない写真", "旧モデルや入荷していない色が主役の写真"],
    copyA: ["NEW ARRIVAL", "POC｜Helmets & Goggles"],
    copyB: ["守るための、デザイン。", "POC Fall / Winter 2026"],
    link: "特集ページ（EC側で作成）",
    notes: [],
  },
];

const SIZES = [["1080 × 1080", "1:1", "フィード（基本）"], ["1080 × 1350", "4:5", "フィード（縦長）"],
               ["1080 × 1920", "9:16", "ストーリーズ・リール"]];

function page(b) {
  const out = [];
  // タイトル帯
  out.push(tbl([[cell([
    P("画像制作依頼書｜NEW ARRIVAL 広告（Instagram・Facebook）｜依頼日 2026年9月29日",
      { size: 17, color: "D6DEEB", after: 60, line: 240 }),
    new Paragraph({ spacing: { before: 120, after: 80 }, children: [run(b.name, { size: 44, bold: true, color: "FFFFFF" })] }),
    P(`見せるもの：${b.theme}`, { size: 20, color: "FFFFFF", after: 0, line: 240 }),
  ], W, { fill: NAVY, borders: NO_BORDERS, pad: 120 })]], [W]));
  out.push(P("", { after: 60 }));
  out.push(kv([
    ["公開時期", b.timing],
    ["作るもの", "2案（A・B）× 3サイズ ＝ 計6点"],
    ["リンク先", b.link],
  ]));

  out.push(H("1", "この広告で伝えたいこと"));
  out.push(tbl([[cell(P(b.why, { size: 24, bold: true, color: NAVY, after: 0 }), W,
    { fill: LIGHT, borders: { ...NO_BORDERS, left: { style: BorderStyle.SINGLE, size: 24, color: NAVY } }, pad: 140 })]], [W]));
  out.push(NOTE("特定の商品ではなく、このブランドの今シーズンの新作が入ったことを伝える広告。品番の指定はしない。"));

  out.push(H("2", "仕上がりイメージ（配信中の広告に揃える）"));
  const half = W / 2;
  out.push(tbl([
    [cell(img("houdini-pace_v1_1080x1080.jpg", 140, 140), half, { borders: NO_BORDERS }),
     cell(img("norrona-senja_v1_1080x1080.jpg", 140, 140), half, { borders: NO_BORDERS })],
    [cell(P("HOUDINI（PACE SERIES）", { size: 17, color: GREY, align: AlignmentType.CENTER, after: 0 }), half, { borders: NO_BORDERS, pad: 0 }),
     cell(P("NORRØNA（senja）", { size: 17, color: GREY, align: AlignmentType.CENTER, after: 0 }), half, { borders: NO_BORDERS, pad: 0 })],
  ], [half, half]));
  out.push(kv([
    ["構成", "写真を全面に使い、見出し（太字）＋サブコピー（細字）を白文字で。ブランドの公式ロゴ（白）を右下"],
    ["文字の位置", "写真の抜け（空・雪面など）に合わせて上でも下でも可。人物の顔や商品に文字を重ねない。"
      + "写真が明るい場合は、文字の下に薄いグラデーションを敷く"],
    ["写真", "各ブランドの Fall / Winter 2026 公式ビジュアルを優先（広告使用の許諾は FULLMARKS 側で確認）"],
  ]));

  out.push(H("3", "サイズ（1案につき3サイズ）"));
  out.push(grid([["サイズ（px）", "比率", "使う場所", "注意"],
    ...SIZES.map((s, i) => [s[0], s[1], s[2], ["上の参考と同じ構成", "1:1 の上下に写真を伸ばす",
      "上 250px・下 340px には文字・ロゴを置かない"][i]])], [1900, 900, 2700, W - 5500]));

  out.push(H("4", "納品ファイル名"));
  const files = [];
  for (const ab of ["A", "B"]) for (const s of SIZES) files.push(`${b.file}-newarrival-202610_${ab}_${s[0].replace(" × ", "x")}.jpg`);
  out.push(tbl([0, 1, 2].map(r => [0, 1].map(c => cell(P(files[c * 3 + r], { size: 17, after: 0 }), W / 2,
    { fill: r % 2 ? LIGHT : undefined, pad: 35 }))), [W / 2, W / 2]));
  out.push(NOTE("JPG（sRGB）。あわせて再編集用の PSD または AI（レイヤー付き）も納品。"));
  return out;
}

fs.mkdirSync(OUT_DIR, { recursive: true });
const jobs = BRANDS.map(b => {
  const doc = new Document({
    styles: { default: { document: { run: { font: FONT, size: 20 } } } },
    sections: [{ properties: { page: { size: { width: 11906, height: 16838 },
      margin: { top: 900, bottom: 900, left: 1133, right: 1133 } } }, children: page(b) }],
  });
  const out = path.join(OUT_DIR, `画像制作依頼書_${b.name.replace("Ø", "O")}_NEW_ARRIVAL.docx`);
  return Packer.toBuffer(doc).then(buf => { fs.writeFileSync(out, buf); console.log("wrote", out); });
});
Promise.all(jobs);

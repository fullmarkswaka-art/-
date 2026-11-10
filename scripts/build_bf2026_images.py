# -*- coding: utf-8 -*-
"""ブラックフライデー2026 の Meta 広告画像（1:1・4:5・9:16）を作る。

使い方: python scripts/build_bf2026_images.py <素材フォルダ> <出力フォルダ>
  素材フォルダには powder.jpg（雪煙の写真）・bw.jpg（白黒の滑走写真）・store_logo.png・store_logo_wt.png を置く。
  画像の文字は「BLACK FRIDAY」と日付だけ（2026-11-05 ユーザー指示）。左上に FULLMARKS ロゴ。
  9:16 は上 250px・下 340px に文字を置かない（アカウント名やボタンが重なるため）。
  元画像の色は ICC で sRGB に変換してから使う（Adobe RGB・CMYK のままだと色が変わる）。
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image, ImageCms, ImageDraw, ImageFilter, ImageFont

INTER = "/usr/share/fonts/opentype/inter/"
F_TITLE = INTER + "Inter-Black.otf"
F_DATE = INTER + "Inter-SemiBold.otf"
F_DOW = INTER + "Inter-Medium.otf"
SIZES = {"1080x1080": (1080, 1080), "1080x1350": (1080, 1350), "1080x1920": (1080, 1920)}
DATE = ("11.23", "(Mon)", "11.30", "(Mon)")


def to_srgb(im: Image.Image) -> Image.Image:
    icc = im.info.get("icc_profile")
    if im.mode == "CMYK" or icc:
        src = ImageCms.ImageCmsProfile(io.BytesIO(icc)) if icc else ImageCms.createProfile("sRGB")
        im = ImageCms.profileToProfile(im, src, ImageCms.createProfile("sRGB"), outputMode="RGB")
    return im.convert("RGB")


def cover(im: Image.Image, size: tuple[int, int], cx: float, cy: float) -> Image.Image:
    """size の比率で、中心 (cx, cy)（0〜1）を基準に切り出して縮小する。"""
    W, H = im.size
    tw, th = size
    r = tw / th
    if W / H > r:
        ch, cw = H, round(H * r)
    else:
        cw, ch = W, round(W / r)
    x = min(max(round(cx * W - cw / 2), 0), W - cw)
    y = min(max(round(cy * H - ch / 2), 0), H - ch)
    return im.crop((x, y, x + cw, y + ch)).resize(size, Image.LANCZOS)


def logo(path: Path, width: int) -> Image.Image:
    lg = Image.open(path).convert("RGBA")
    lg = lg.crop(lg.getbbox())
    return lg.resize((width, round(lg.height * width / lg.width)), Image.LANCZOS)


def text_w(d, s, f, track=0):
    return d.textlength(s, font=f) + track * (len(s) - 1)


def draw_tracked(d, xy, s, f, fill, track=0):
    x, y = xy
    for ch in s:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + track


def title_block(canvas: Image.Image, x: int, y: int, width: int, color, align="left", shadow=False):
    """BLACK / FRIDAY の2行と日付。width に合わせて文字の大きさを決める。戻り値は下端の y。"""
    d = ImageDraw.Draw(canvas)
    size = 200
    while True:
        f = ImageFont.truetype(F_TITLE, size)
        w = max(text_w(d, "BLACK", f, -size * 0.02), text_w(d, "FRIDAY", f, -size * 0.02))
        if w <= width or size < 40:
            break
        size -= 2
    track = -size * 0.02
    fd = ImageFont.truetype(F_DATE, round(size * 0.30))
    fw = ImageFont.truetype(F_DOW, round(size * 0.17))
    lines = []
    ty = y
    for s in ("BLACK", "FRIDAY"):
        lines.append((s, f, ty, track))
        ty += round(size * 0.92)
    ty += round(size * 0.22)
    date = f"{DATE[0]} {DATE[1]}  —  {DATE[2]} {DATE[3]}"
    # 日付は数字を大きく、曜日を小さく
    parts = [(DATE[0], fd), (" " + DATE[1], fw), ("  —  ", fw), (DATE[2], fd), (" " + DATE[3], fw)]
    dw = sum(d.textlength(s, font=ff) for s, ff in parts)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for s, ff, yy, tr in lines:
        xx = x if align == "left" else x + width - text_w(ld, s, ff, tr)
        draw_tracked(ld, (xx, yy), s, ff, color, tr)
    xx = x if align == "left" else x + width - dw
    base = ty + fd.getmetrics()[0]
    for s, ff in parts:
        ld.text((xx, base - ff.getmetrics()[0]), s, font=ff, fill=color)
        xx += ld.textlength(s, font=ff)
    if shadow:
        sh = layer.split()[3].filter(ImageFilter.GaussianBlur(10)).point(lambda a: a * 0.45)
        canvas.paste(Image.new("RGB", canvas.size, (0, 0, 0)), (0, 0), sh)
    canvas.paste(layer, (0, 0), layer)
    return base + fd.getmetrics()[1]


def build(src: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    powder = to_srgb(Image.open(src / "powder.jpg"))
    bw = to_srgb(Image.open(src / "bw.jpg"))
    black, white = (17, 17, 17), (255, 255, 255)
    for key, (w, h) in SIZES.items():
        top = 250 if h == 1920 else 64      # 9:16 は上 250px を空ける
        m = 72
        # A: 雪煙の写真（白い空と雪に黒い文字）
        cy = {"1080x1080": 0.55, "1080x1350": 0.5, "1080x1920": 0.5}[key]
        a = cover(powder, (w, h), 0.55, cy)
        lg = logo(src / "store_logo.png", 300)
        # 左上は岩があり暗いので、ロゴも文字も右上の空に寄せる（右揃え）
        a.paste(lg, (w - m - lg.width, top), lg)
        tw = {"1080x1080": 560, "1080x1350": 620, "1080x1920": 760}[key]
        title_block(a, w - m - tw, top + lg.height + 40, tw, black, align="right")
        a.save(out / f"bf_A_powder_{key}.jpg", quality=92, subsampling=0)
        # B: 白黒の滑走写真（白い文字）
        b = cover(bw, (w, h), 0.42, 0.55)
        lgw = logo(src / "store_logo_wt.png", 300)
        b.paste(lgw, (m, top), lgw)
        if h == 1920:
            title_block(b, m, h - 340 - 520, w - 2 * m, white, shadow=True)
        else:
            title_block(b, m, h - m - (420 if h == 1080 else 470), 700, white, shadow=True)
        b.save(out / f"bf_B_bw_{key}.jpg", quality=92, subsampling=0)


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))

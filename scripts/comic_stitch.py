#!/usr/bin/env python3
"""
comic_stitch.py — 把多格黑白漫画拼接为纵向条漫 (每格下方配台词条)

用法:
  python3 comic_stitch.py --title "今日热点" --panels p1.png p2.png p3.png p4.png \
      --captions "台词1" "台词2" "台词3" "台词4" --out comic.png

  --panels    每格图片路径 (按顺序), 至少 1 张
  --captions  与格子数相同的台词/旁白文本; 少于格子数时缺省为空
  --title     顶部标题条文字 (可选)
  --subtitle  标题下的副标题/日期 (可选)
  --width     每格统一宽度 px, 默认 1024 (图宽大于此则等比缩小, 小于则保持)
  --panel-gap 相邻格间距 px, 默认 16
  --caption-h 台词条高度 px, 默认 110
  --dark      深色台词条(黑底白字), 默认开; 传 --light 则白底黑字
  --out       输出 PNG 路径, 默认 comic.png

说明:
  只做拼接与文字排版, 不修改格子内容。台词支持多行, 按 \n 换行。
"""

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
]


def find_font():
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def load_font(size: int):
    path = find_font()
    if path is None:
        sys.exit("[错误] 未找到系统中文字体 (PingFang/Heiti)")
    try:
        return ImageFont.truetype(path, size)
    except Exception as e:
        sys.exit(f"[错误] 字体加载失败: {e}")


def fit_image(img: Image.Image, max_w: int) -> Image.Image:
    """等比缩放到宽度不超过 max_w (小于则不放大)。"""
    if img.width > max_w:
        h = round(img.height * max_w / img.width)
        return img.resize((max_w, h), Image.LANCZOS)
    return img


def wrap_text(draw, text: str, font, max_w: int) -> list[str]:
    """按像素宽度折行, 支持显式 \n。"""
    lines: list[str] = []
    for raw in text.split("\n"):
        raw = raw.strip()
        if not raw:
            lines.append("")
            continue
        cur = ""
        for ch in raw:
            if draw.textlength(cur + ch, font=font) <= max_w:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
        lines.append(cur)
    return lines


def render_caption(img: Image.Image, text: str, font_path: str, dark: bool) -> Image.Image:
    """在格子下方生成一条台词带。"""
    w = img.width
    pad_x = 36
    cap_h = 110
    font_size = 34
    cap = Image.new("RGB", (w, cap_h), (15, 15, 15) if dark else (245, 245, 245))
    draw = ImageDraw.Draw(cap)
    font = load_font(font_size)
    fg = (245, 245, 245) if dark else (20, 20, 20)
    if text:
        lines = wrap_text(draw, text, font, w - pad_x * 2)
        # 多行自动增高
        if len(lines) > 1:
            line_h = font_size + 8
            new_h = max(cap_h, pad_x * 2 + len(lines) * line_h)
            cap = Image.new("RGB", (w, new_h), (15, 15, 15) if dark else (245, 245, 245))
            draw = ImageDraw.Draw(cap)
        y = 12
        for ln in lines:
            draw.text((pad_x, y), ln, font=font, fill=fg)
            y += font_size + 8
    # 台词条左边加一条装饰竖线, 突出"对话/旁白"
    draw.rectangle([14, 12, 22, cap.height - 12], fill=(200, 60, 60) if not dark else (220, 80, 80))
    # 垂直拼接
    out = Image.new("RGB", (img.width, img.height + cap.height), (255, 255, 255))
    out.paste(img, (0, 0))
    out.paste(cap, (0, img.height))
    return out


def main():
    p = argparse.ArgumentParser(description="多格漫画拼接为纵向条漫")
    p.add_argument("--panels", nargs="+", required=True, help="每格图片路径")
    p.add_argument("--captions", nargs="*", default=[], help="每格台词, 按顺序")
    p.add_argument("--title", default="", help="顶部标题")
    p.add_argument("--subtitle", default="", help="副标题/日期")
    p.add_argument("--width", type=int, default=1024, help="格子统一宽度")
    p.add_argument("--panel-gap", type=int, default=16, help="格间距")
    p.add_argument("--caption-h", type=int, default=110, help="台词条高度")
    p.add_argument("--light", action="store_true", help="白底黑字台词条")
    p.add_argument("--out", default="comic.png", help="输出 PNG")
    args = p.parse_args()

    panels = [Image.open(x).convert("RGB") for x in args.panels]
    if not panels:
        sys.exit("[错误] 至少需要一张格子图")

    dark = not args.light
    # 顶部标题条
    header_h = 0
    header = None
    if args.title:
        header_h = 150 if args.subtitle else 100
        header = Image.new("RGB", (args.width, header_h), (15, 15, 15))
        d = ImageDraw.Draw(header)
        f_title = load_font(52)
        f_sub = load_font(30)
        tw = d.textlength(args.title, font=f_title)
        d.text(((args.width - tw) // 2, 18), args.title, font=f_title, fill=(240, 240, 240))
        if args.subtitle:
            sw = d.textlength(args.subtitle, font=f_sub)
            d.text(((args.width - sw) // 2, 88), args.subtitle, font=f_sub, fill=(170, 170, 170))

    # 逐格: 缩放 + 台词条
    strip_parts = []
    for i, img in enumerate(panels):
        img = fit_image(img, args.width)
        cap_text = args.captions[i] if i < len(args.captions) else ""
        img = render_caption(img, cap_text, find_font() or "", dark)
        strip_parts.append(img)

    gap = max(0, args.panel_gap)
    total_h = header_h + sum(im.height for im in strip_parts) + gap * (len(strip_parts) - 1)
    final_w = max(args.width, max(im.width for im in strip_parts))
    final = Image.new("RGB", (final_w, total_h), (255, 255, 255))

    y = 0
    if header is not None:
        final.paste(header, (0, 0))
        y = header_h
    for i, im in enumerate(strip_parts):
        final.paste(im, (0, y))
        y += im.height
        if i < len(strip_parts) - 1:
            y += gap

    final.save(args.out)
    print(f"[条漫] 已保存: {args.out} ({final.width}x{final.height}, {len(panels)}格)")


if __name__ == "__main__":
    main()

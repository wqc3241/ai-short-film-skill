# -*- coding: utf-8 -*-
"""素材总览图（contact sheet）：把图片/视频帧平铺成一张带标签的大图，供自检与用户过目。

  # 图片模式：平铺目录下所有图片（递归），标签=相对路径
  python contact_sheet.py images assets/characters -o build/cs_characters.png

  # 视频模式：整片均匀抽 N 帧
  python contact_sheet.py video final/成片.mp4 12 -o build/cs_film.png

生成后 Read 输出文件查看；给用户过目时用 SendUserFile 发送。
"""
import subprocess, os, sys, glob

from PIL import Image, ImageDraw, ImageFont

F = ImageFont.truetype("/Library/Fonts/Arial Unicode.ttf", 22)
TW, TH = 360, 360  # 素材多为方图/竖图，按 fit 缩放不裁切

def fit(im, w=TW, h=TH):
    im = im.convert("RGB"); im.thumbnail((w, h))
    bg = Image.new("RGB", (w, h), (12, 12, 12))
    bg.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return bg

def grab(path, t):
    # PNG 而非 JPG：ffmpeg 8.x 对 full-range YUV 出 mjpeg 会报 Non full-range YUV is non-standard
    o = f"/tmp/cs_{abs(hash((path, t))) % 99999}.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(max(t, 0)), "-i", path,
                    "-frames:v", "1", o], check=True)
    return Image.open(o)

def sheet(items, out):  # items: list of (PIL image, label)
    cols = min(5, max(1, len(items))); rows = (len(items) + cols - 1) // cols
    s = Image.new("RGB", (cols * TW, rows * (TH + 30)), (12, 12, 12)); d = ImageDraw.Draw(s)
    for i, (im, lab) in enumerate(items):
        x, y = (i % cols) * TW, (i // cols) * (TH + 30)
        s.paste(fit(im), (x, y))
        d.text((x + 5, y + TH + 4), lab[:38], font=F, fill=(0, 255, 150))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    s.save(out); print("->", out, s.size, f"{len(items)} items")

args = sys.argv[1:]
out = "contact.png"
if "-o" in args:
    i = args.index("-o"); out = args[i + 1]; args = args[:i] + args[i + 2:]
mode = args[0]
if mode == "video":
    v = args[1]; n = int(args[2]) if len(args) > 2 else 12
    D = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                       "format=duration", "-of", "csv=p=0", v]).strip())
    sheet([(grab(v, D * (k + 0.5) / n), f"{D * (k + 0.5) / n:.1f}s") for k in range(n)], out)
elif mode == "images":
    root = args[1]
    exts = ("*.png", "*.jpg", "*.jpeg", "*.webp")
    paths = sorted(p for e in exts for p in glob.glob(os.path.join(root, "**", e), recursive=True))
    if not paths:
        sys.exit(f"no images under {root}")
    sheet([(Image.open(p), os.path.relpath(p, root)) for p in paths], out)
else:
    sys.exit("mode must be: images | video")

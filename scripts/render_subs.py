# -*- coding: utf-8 -*-
"""SRT → 每条字幕一张透明 PNG + ffmpeg overlay 滤镜链（本机 ffmpeg 无 libass/subtitles 滤镜的替代方案）。

  python3 render_subs.py subs.srt <video_w> <video_h> <outdir>

输出: <outdir>/sub_NNN.png 与 <outdir>/filter.txt（含 -i 参数与 filter_complex，供 burn_subs_and_cards.sh 拼装）。
"""
import re, sys, os
from PIL import Image, ImageDraw, ImageFont

srt, W, H, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
os.makedirs(out, exist_ok=True)
FS = max(18, H // 24)                      # 字号随分辨率
FONTS = ["/Library/Fonts/Arial Unicode.ttf",              # contact_sheet.py 同款，已验证含中文
         "/System/Library/Fonts/Hiragino Sans GB.ttc",
         "/System/Library/Fonts/STHeiti Medium.ttc"]
for fp in FONTS:
    try:
        F = ImageFont.truetype(fp, FS); break
    except OSError:
        continue
else:
    sys.exit("no usable CJK font found: " + ", ".join(FONTS))
MARGIN_V = H // 12

def ts(s):
    h, m, rest = s.split(":"); sec, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000

cues = []
for block in re.split(r"\n\s*\n", open(srt, encoding="utf-8").read().strip()):
    lines = [l for l in block.splitlines() if l.strip()]
    if len(lines) < 2 or "-->" not in lines[1]:
        continue
    a, b = [ts(x.strip()) for x in lines[1].split("-->")]
    cues.append((a, b, "\n".join(lines[2:])))

inputs, chain, prev = [], [], "[0:v]"
for i, (a, b, text) in enumerate(cues):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    tw = max(d.textlength(l, font=F) for l in text.splitlines())
    th = len(text.splitlines()) * (FS + 8)
    x, y = (W - tw) / 2, H - MARGIN_V - th
    d.rectangle([x - 12, y - 6, x + tw + 12, y + th + 6], fill=(0, 0, 0, 140))
    d.multiline_text((x, y), text, font=F, fill=(255, 255, 255, 255), align="center", spacing=8)
    p = os.path.join(out, f"sub_{i:03d}.png"); im.save(p)
    inputs.append(f"-i {p}")
    nxt = f"[v{i + 1}]"
    chain.append(f"{prev}[{i + 1}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'{nxt}")
    prev = nxt

with open(os.path.join(out, "filter.txt"), "w") as f:
    f.write(" ".join(inputs) + "\t" + ";".join(chain) + "\t" + prev + "\n")
print(f"{len(cues)} cues -> {out}")

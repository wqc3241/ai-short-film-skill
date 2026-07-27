# -*- coding: utf-8 -*-
"""画面内空白牌面/屏幕补全（通用模板，按项目改顶部常量）：
 用途：AI 生成的车站信息屏、店招、告示牌常常是空的或乱码，重新生成整段代价高且可能破坏已通过的画面；
 本脚本在后期把内容合成上去，比重生成便宜且不动已批准的镜头。

 1) 逐帧模板跟踪后，对可信帧拟合线性运动模型(平移+缩放)并外推到全部帧 —— 消除开头被立柱遮挡时的跟踪丢失与抖动
 2) 合成时用底层亮度做遮罩 —— 文字只出现在牌面暗区，被前景立柱遮住的部分自动不显示
"""
import os, json, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SRC = "shots/v2/HKD·S02·镜v2.mp4"
OUT = "shots/v2/HKD·S02·镜v2-补牌.mp4"
TMP = "/private/tmp/claude-501/-Users-qichaowang/64888358-eea7-4429-8af8-7ff0e415901d/scratchpad/s02frames"
CACHE = TMP + "_track.json"
FPS, REF_T = 24, 0.5
BOARD = (267, 85, 595, 210)
ROW1, ROW2 = (13, 67, 313, 87), (13, 92, 313, 115)
COLX = [56, 140, 230, 293]
ROWS = [["特急北斗", "12:05", "札幌", "1"], ["普通", "12:33", "長万部", "4"]]

files = sorted(f for f in os.listdir(TMP) if f.endswith(".png"))
N = len(files)

def gray_half(p):
    im = Image.open(p).convert("L")
    return np.asarray(im.resize((im.width // 2, im.height // 2)), dtype=np.float32)

REF = int(round(REF_T * FPS))
bx0, by0, bx1, by1 = [v // 2 for v in BOARD]
tpl0 = gray_half(f"{TMP}/{files[REF]}")[by0:by1, bx0:bx1]
TH, TW = tpl0.shape

if os.path.exists(CACHE):
    track = json.load(open(CACHE))
else:
    def ncc(a, b):
        a = a - a.mean(); b = b - b.mean()
        d = np.sqrt((a * a).sum() * (b * b).sum())
        return float((a * b).sum() / d) if d > 1e-6 else -1.0
    def st(s):
        if abs(s - 1) < 1e-6: return tpl0
        im = Image.fromarray(tpl0)
        return np.asarray(im.resize((int(round(TW * s)), int(round(TH * s))), Image.BILINEAR), np.float32)
    def search(g, x, y, s):
        best = (-2, x, y, s)
        for sc in np.linspace(s - 0.03, s + 0.03, 5):
            t = st(sc); th, tw = t.shape
            for dy in range(-7, 8):
                for dx in range(-7, 8):
                    yy, xx = y + dy, x + dx
                    if yy < 0 or xx < 0 or yy + th > g.shape[0] or xx + tw > g.shape[1]: continue
                    v = ncc(g[yy:yy + th, xx:xx + tw], t)
                    if v > best[0]: best = (v, xx, yy, sc)
        return best
    track = [None] * N; track[REF] = [1.0, bx0, by0, 1.0]
    for rng in (range(REF + 1, N), range(REF - 1, -1, -1)):
        prev = track[REF]
        for i in rng:
            v, x, y, s = search(gray_half(f"{TMP}/{files[i]}"), prev[1], prev[2], prev[3])
            track[i] = [v, x, y, s]; prev = track[i]
    json.dump(track, open(CACHE, "w"))

tr = np.array(track)
ok = tr[:, 0] > 0.72
idx = np.arange(N)
print(f"可信帧 {ok.sum()}/{N}  NCC区间 {tr[ok,0].min():.3f}-{tr[ok,0].max():.3f}")

# 对可信帧拟合二次模型（镜头末段减速），外推到全部帧
model = {}
for k, name in [(1, "x"), (2, "y"), (3, "s")]:
    c = np.polyfit(idx[ok], tr[ok, k], 2)
    fit = np.polyval(c, idx)
    print(f"  {name}: 残差RMS {np.sqrt(((fit[ok]-tr[ok,k])**2).mean()):.2f}  范围 {fit.min():.2f}-{fit.max():.2f}")
    model[name] = fit

# 表头取色
rgb = np.asarray(Image.open(f"{TMP}/{files[REF]}").convert("RGB"), np.float32)
h = rgb[BOARD[1]+12:BOARD[1]+45, BOARD[0]+60:BOARD[0]+260].reshape(-1, 3)
h = h[h.mean(1) > np.percentile(h.mean(1), 92)]
TXT = tuple(int(c) for c in h.mean(0)); print("文字取色:", TXT)

SS = 4; lw, lh = BOARD[2]-BOARD[0], BOARD[3]-BOARD[1]
layer = Image.new("RGBA", (lw*SS, lh*SS), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
FP = "/Library/Fonts/Arial Unicode.ttf"
for (rx0, ry0, rx1, ry1), cells in zip([ROW1, ROW2], ROWS):
    hh = (ry1-ry0)*SS; f = ImageFont.truetype(FP, int(hh*0.72)); cy = (ry0+ry1)/2*SS
    for cx, txt in zip(COLX, cells):
        w = d.textlength(txt, font=f)
        d.text((cx*SS - w/2, cy - hh*0.42), txt, font=f, fill=TXT+(255,))
layer = layer.resize((lw, lh), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.4))

OUTD = TMP + "_out"; os.makedirs(OUTD, exist_ok=True)
for i, fn in enumerate(files):
    im = Image.open(f"{TMP}/{fn}").convert("RGB")
    s = float(model["s"][i]); px, py = int(round(model["x"][i]*2)), int(round(model["y"][i]*2))
    w2, h2 = max(4, int(round(lw*s))), max(4, int(round(lh*s)))
    lay = layer.resize((w2, h2), Image.LANCZOS)
    fw, fh = im.size
    x0, y0 = max(0, px), max(0, py); x1, y1 = min(fw, px+w2), min(fh, py+h2)
    if x1 <= x0 or y1 <= y0:
        im.save(f"{OUTD}/{fn}"); continue
    sub = lay.crop((x0-px, y0-py, x1-px, y1-py))
    # 亮度遮罩：底层越暗(牌面)越显示，越亮(立柱/天空)越隐藏
    under = np.asarray(im.crop((x0, y0, x1, y1)).convert("L"), np.float32)
    mask = np.clip((105.0 - under) / 45.0, 0, 1)
    a = (np.asarray(sub.split()[3], np.float32)/255.0) * mask * 0.88
    sub.putalpha(Image.fromarray((a*255).astype(np.uint8)))
    base = im.convert("RGBA"); base.alpha_composite(sub, (x0, y0))
    base.convert("RGB").save(f"{OUTD}/{fn}")
print("合成完成")
subprocess.run(["ffmpeg","-y","-loglevel","error","-framerate",str(FPS),"-i",f"{OUTD}/f%04d.png",
                "-i",SRC,"-map","0:v","-map","1:a","-c:v","libx264","-crf","17",
                "-pix_fmt","yuv420p","-c:a","copy",OUT], check=True)
print("输出:", OUT)

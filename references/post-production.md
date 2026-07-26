# 本地后期精修与交付（P8）

前提：`final/` 已有 LibTV 成片；`assets/audio/` 已有 BGM/环境音源文件（P4d 下载的）。成片下载后**先问用户两件事**：要不要字幕？片头片尾要什么样式？（SKILL.md Gate 之外的运行时询问，用户已定为下载后询问制。）

## 1. 三轨混音精修（可选，推荐）

LibTV 内配乐是静态音量粗混（P7 只为画布预览）。精修用干净路径：P7 前的**无乐版终剪**（或让 video-clip 去掉音频轨后重下）+ 本地叠 BGM/环境音：

```bash
scripts/mix_and_master.sh final/无乐版.mp4 final/混音版.mp4 \
  --bgm assets/audio/全片·BGM-开场.mp3 --bgm-vol 0.35 --duck \
  --amb assets/audio/S03·环境-雨夜街道.mp3 --amb-vol 0.2 --fade 1.5
```
`--duck`＝对白出现时 BGM 自动压低（sidechaincompress，约 -12dB）；末尾统一 loudnorm（I=-16 LUFS）。多段 BGM 按叙事节奏表分段时：先 ffmpeg concat 各段 BGM（段间 acrossfade）成一条再喂入。混完全片复听一遍：对白清晰度、闪避是否呼吸感过重（release 400ms 可调）、结尾淡出是否干净。

## 2. 字幕（用户要求时）

台词来源=方案 §5 剧本（唯一权威，不要听写）。按成片实际时间轴写 SRT：逐镜 `ffprobe` 时长累加得每镜起点，镜内对白按台词音频时长（P4d 下载的文件 `ffprobe`）铺时间码，存 `final/subs.srt`。抽 3 处带对白的时间点截帧核对不早不晚。

```bash
scripts/burn_subs_and_cards.sh final/混音版.mp4 final/成片.mp4 --srt final/subs.srt
```
本机 Homebrew ffmpeg 8.1 未编译 `subtitles`/`ass`/`drawtext` 滤镜——脚本内部走 `render_subs.py`（PIL 逐条渲染透明 PNG + overlay 时间窗叠加），默认样式：Arial Unicode、字号=高度/24、半透明黑底、居中距底 1/12 高。用户有样式要求直接改 `render_subs.py` 的字号/边距/颜色常量。

## 3. 片头标题 / 片尾 credits（用户要求时）

卡片是与正片同分辨率的静态 PNG。生成方式按用户样式要求选：简洁文字卡→PIL 画（黑底+片名+副题）；美术卡→回 ChatGPT project 生成（挂统一风格提示词 §16，走 chatgpt-assets.md 取图流程）。

```bash
scripts/burn_subs_and_cards.sh final/成片.mp4 final/成片-终.mp4 \
  --title build/title.png --title-dur 3 --credits build/credits.png --credits-dur 5
```
卡片自带 0.5s 黑场淡入淡出；片头卡默认无声。credits 内容：片名/出品/「AI 生成声明」一行（LibTV 去水印下载后建议保留声明）。

## 4. 交付

终版命名 `final/<片名>.mp4`。`contact_sheet.py video final/<片名>.mp4 12` 末检一遍（字幕无错字、片头片尾正常、无坏帧）→ SendUserFile 交付，caption 注明：本片总时长、需要复听/复看的点（如某镜是重试后的最佳版本）、以及 manifest 里仍标记失败的镜（若有）。更新 `state.md` 为已交付，画布 URL 一并附上供用户回溯。

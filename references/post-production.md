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

卡片是与正片同分辨率的静态 PNG。生成方式按用户样式要求选：简洁文字卡→PIL 画（黑底+片名+副题）；美术卡→回 ChatGPT project 生成（挂 §7 风格行 + §9 色彩行，走 chatgpt-assets.md 取图流程）。

```bash
scripts/burn_subs_and_cards.sh final/成片.mp4 final/成片-终.mp4 \
  --title build/title.png --title-dur 3 --credits build/credits.png --credits-dur 5
```
卡片自带 0.5s 黑场淡入淡出；片头卡默认无声。credits 内容：片名/出品/「AI 生成声明」一行（LibTV 去水印下载后建议保留声明）。

## 4. 交付

终版命名 `final/<片名>.mp4`。`contact_sheet.py video final/<片名>.mp4 12` 末检一遍（字幕无错字、片头片尾正常、无坏帧）→ SendUserFile 交付，caption 注明：本片总时长、需要复听/复看的点（如某镜是重试后的最佳版本）、以及 manifest 里仍标记失败的镜（若有）。更新 `state.md` 为已交付，画布 URL 一并附上供用户回溯。

## 5. 剪辑修订工具箱（星火预告片教训，2026-07）

**concat 拼接**：清单里一律绝对路径——`-f concat` 的相对路径按**清单文件所在目录**解析，不是 cwd。重编码修订段与原生段混拼：相同 codec/profile/pix_fmt/fps/采样率即可 `-c copy`（如 `libx264 -profile:v high -pix_fmt yuv420p -r 24 -c:a aac -ar 44100`）。

**镜内剪帧**（删坏帧/砍半段）：trim+concat 单命令搞定，帧级精确（24fps 下按 1/24 对齐剪点）：
```bash
ffmpeg -i in.mp4 -filter_complex "[0:v]trim=0:3.4167,setpts=PTS-STARTPTS[v1];[0:v]trim=4.5:8.081,setpts=PTS-STARTPTS[v2];[0:a]atrim=0:3.4167,asetpts=PTS-STARTPTS[a1];[0:a]atrim=4.5:8.081,asetpts=PTS-STARTPTS[a2];[v1][a1][v2][a2]concat=n=2:v=1:a=1[v][a]" -map "[v]" -map "[a]" <编码参数> out.mp4
```
剪点先做密集抽帧扫描定位（`fps=6..8` 出 tile 图逐帧看），涉及"物体状态反转"（如插入→拔出）要全分辨率单帧确认。

**慢放**：`setpts=(PTS-STARTPTS)*2` 后接 `minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1` 真补帧（帧复制会顿）；**声音不跟慢**——用原速环境音接续到段尾（可从源音轨取更早的等长段补满），配 afade 渐弱。渐暗收尾：`fade=t=out` 作用于慢放段。

**标题压画面**：本机 ffmpeg 无 fontconfig，`drawtext` 直接报错——用 PIL 渲透明 PNG 再 `-loop 1 -i title.png` overlay（alpha fade：`format=argb,fade=t=in:st=..:alpha=1`）。笔刷 logo 风（CP2077 类）本机无现成字体，SignPainter 底 + 大角度斜切 + 逐行随机位移毛边 + 随机细横线擦痕 + 金色渐变 + 深色错位投影可达近似；更像需用户批准下载字体或用户提供 ttf。

**验证习惯**：改完音轨跑一遍 whisper 反扫成片核对台词落点；但 tiny 模型会在 BGM 上幻听人声、长段时间戳松——疑似新对白先对该单镜干净音轨单独验证再处理。

**zsh 两坑**：空目录 glob（`rm -rf dir/*`）直接报错断掉 `&&` 链——用 `rm -rf dir && mkdir dir`；`$VAR` 存放多个参数不会自动分词——参数内联或 `${=VAR}`。

## 字幕时间轴定位（《证明》2026-07 定版，两次翻车后的正确做法）

**不要用**：①语音频段能量检测——环境音（雨声、脚步、打印机、站台广播）会误触发，实测最大偏差 7 秒；②原始单元片段时间反推——用户在剪映里会混剪新旧版本、删尾帧，时间对不上；③能量包络互相关——会被全片最响的段落主导，所有片段都指向同一处。

**正确做法**：
1. 从**成片**提音频（不是粗剪），`-ac 1 -ar 16000`
2. 切 **15 秒块、3 秒重叠**，逐块跑 `whisper --model small --word_timestamps True`
   - 为什么要切块：whisper 在长稀疏语音（大段无人声）上会把 segment 时间戳吸附到 30 秒窗口边界（0/30/60/90…），整条时间轴作废
   - `--word_timestamps True` 走 DTW 强制对齐，精度到 0.1 秒
3. 块偏移拼回全片时间轴，按剧本台词顺序匹配（**台词文本以剧本为准，whisper 只提供时间**，它会把中文台词转成错字、把英文转成日文假名）
4. **漏检兜底**：音量低的台词 whisper 会完全跳过。对该区间做 `volume=18dB,highpass=f=120,lowpass=f=6000` 后用 **medium** 模型单独转，实测可捕捉
5. 逐条抽帧核对口型（`ffmpeg -ss <字幕中点>` 取帧，看角色是否张嘴）

**长台词按停顿拆条**：whisper 的分段边界通常就是自然停顿点，直接用它拆两条字幕比硬塞一行更好读。

**配乐闪避窗必须跟着字幕时间同步更新**——时间轴改了却没重做闪避，等于 BGM 在错误的位置压低。

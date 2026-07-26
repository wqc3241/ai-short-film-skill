---
name: ai-short-film
description: >-
  端到端 AI 短片制作流水线：从主题大纲到成片交付。用户 Web ChatGPT 出完整制作方案与全部图片素材（角色三视图/表情/服装/场景四方向/道具），
  LibTV CLI（libtv）完成配音、环境音、配乐、分镜图组、Seedance 分镜视频、终剪与下载，本地 ffmpeg 精修混音/字幕/片头片尾后交付。
  Use whenever the user wants to make an AI short film / AI 短片 / AI 短剧 / AI 微电影 — e.g. "做一个AI短片"、"用 LibTV 拍一部短片"、
  "把这个故事做成AI视频"、"generate an AI film from this outline"、"帮我从剧本到成片走一遍" — even when the user names only part of
  the workflow (只说写方案、只说生成分镜、只说角色定妆图也触发). Also use when iterating on a film project created by this skill
  (改剧本/换角色/重生成某分镜/重新配乐/加字幕/续跑中断的项目).
---

# AI 短片端到端工作流 (AI Short Film)

从一句主题到可交付成片的完整流水线。制作方案与图片素材在**用户自己的 Web ChatGPT** 里生成；音频、分镜图、分镜视频、终剪在 **LibTV 画布**（经 `libtv` CLI）完成；混音精修、字幕、片头片尾在**本地 ffmpeg** 完成。

**REQUIRED SUB-SKILL:** 所有 `libtv` 操作遵循 libtv-cli skill（命令手册）。所有浏览器操作先invoke claude-in-chrome skill。

## The mental model

一部片 = 一个项目目录 + 一张 LibTV 画布 + 一份 `manifest.json`。片子是**分镜（shot）的列表**；每个分镜 = 分镜细节提示词 + 参考素材（角色图/场景图/分镜图/台词音频）+ 一段 ≤15s 的生成视频。所有状态写盘（`state.md` 人读、`manifest.json` 机读），任何一步中断都能从 manifest 续跑。

## Hard rules — 每条都来自真机审计或既有 skill 的教训，不要回退

1. **方案与图片素材一律在用户自己的 Web ChatGPT 生成，绝不自己写/自己画。**（沿用 vertical-commentary-video 的用户硬规则："一定要用 web 版 GPT 去生成，不要你自己生成"）GPT 反复失败且用户明确批准后才可降级，且交付时说明。
2. **`-s model=` 只接受 modelName**（如 `Seedance 2.0`、`Mureka V8`），传 modelKey 会报错。含空格必须引号。
3. **`--run` 是同步阻塞命令**：不当异步提交、不自行加 timeout、不额外轮询、不因看到 taskId 就停。进度看 stderr（约 3 分钟一条）。长任务用 Bash 后台任务跑**整条阻塞命令**并等完成通知。
4. **模型 schema 以运行时实查为准**：每次运行先 `libtv model search --type <t>` + `libtv model <key>`，不硬编码文档里的枚举（文档样本会过期；`download`、Seed Audio 都是文档没有而真机有的例子）。
5. **画面比例三处键名不同但必须同值**：GPT 生图（提示词措辞）、`script storyboard -s aspectRatio=`、video 节点 `-s ratio=`。P1 确认后写入 manifest，逐步引用。
6. **单镜 duration 4–15 秒**；更长的镜头必须拆段并用 frames2video 首尾帧衔接（见 references/libtv-pipeline.md）。
7. **节点名一律带run前缀**（如 `S01·镜-03`、`S01·BGM-开场`），失败清理靠前缀批删；`--left` 数量受 modeType.items 上限约束。
8. **并行写入不共管道**：多个 `libtv` 写命令并行会让 NDJSON 穿插损坏，串行 `&&` 链或分文件再合并。
9. **真人照片作参考图会触发 Seedance 合规校验中止**——素材全部用 GPT 生成图可规避；若用户提供真人照片，先警告。
10. **分镜视频生成时禁止 BGM 与字幕**（写进每条视频提示词的负向约束）；音乐只在 P7 配乐进入，字幕只在 P8 后期进入。
11. **每个 Gate 都要 PRESENT 具体产物并 WAIT 明确批准**；用户中途小修改不需要重新过闸，换主题/换剧本/换素材集才需要。
12. **写盘先于汇报**：每完成一个素材/分镜，先更新 manifest 再继续；限额/积分中断时，把待发提示词原文存入 state.md 再交还用户。

## Workflow (in order)

### P0. 前置检查（全部通过才开始）
| 检查 | 命令/方法 | 失败处理 |
|---|---|---|
| 外置卷已挂载 | `ls /Volumes/Storage` | 提醒用户插盘，停 |
| libtv 已登录 | `libtv account info` | `libtv login web --open` |
| Chrome + ChatGPT 可达 | claude-in-chrome 打开 chatgpt.com | 让用户登录 |
| ffmpeg/PIL 可用 | `ffmpeg -version`; `python3 -c 'import PIL'` | 安装 |

建项目目录 `/Volumes/Storage/ai-short-film/<片名>/`：`plan/ assets/{characters,scenes,props,audio}/ shots/ build/ final/` + `manifest.json` + `state.md` + `characters.json`。已存在同名项目 → 读 manifest 续跑，不重建。

### P1. 立项（Gate 0 —— 一次性确认所有全局参数）
用 AskUserQuestion 收齐并写入 manifest：**主题与大纲**（用户口述，复述确认）、**画面比例**、**目标总时长**、**配音机制**（必问：A. TTS 逐句配音喂进 Seedance mixed2video 驱动口型；B. Seedance enableSound=on 自带语音）、**视频模型与画质**（默认 Seedance 2.0 / 720p，须确认）、**配乐模型**（默认 Mureka V8，须确认）。
按时长估算生成量（分镜数≈总时长/8s；图片≈角色数×8+场景数×4+道具数）并告知：**CLI 无积分查询命令**，请用户自查网页端余额是否充足。

### P2. 制作方案（Gate 1）
→ references/production-plan-template.md（方案 17 个板块的完整模板与 ChatGPT 分段提问脚手架）
在用户的 ChatGPT 里**新建 project**，按模板分段生成完整制作方案，保存 `plan/production-plan.md`，按模板清单逐项校验无缺漏（尤其：每个分镜细节提示词内镜头时长之和 ≤ 分镜时长；长镜头已拆段）。
**→ GATE 1: PRESENT 完整方案文件给用户 review，WAIT 批准后才进素材阶段。**

### P3. 图片素材（Gate 2）
→ references/chatgpt-assets.md（GPT 驱动规程、一致性链、图片进出方法、限额中断处理）
生成顺序（一致性链，环环相扣）：角色脸部白底三视图 → 表情图 → 服装白底三视图 → 各服装下角色三视图 → 场景图（每场景 4 方向，关键细节对剧本）→ 道具白底三视图。分类存 `assets/`，逐张复检三个一致性（人物/场景/道具）。
`python3 scripts/contact_sheet.py images assets -o build/cs_all.png` 自查后 SendUserFile。
**→ GATE 2: PRESENT 素材总览图，WAIT 批准后才上传 LibTV。**

### P4. LibTV 建站与音频素材
→ references/libtv-pipeline.md（建站、上传命名、角色注册表、音色发现、三类音频生成）
`workspace create/use` → `project create/use` → 逐个 `libtv upload`（命名 `<类>-<名>-<变体>`）→ 写 `characters.json`（角色→参考图节点+音色ID+外貌提示词，这是「主体」的 CLI 等价物）→ 音色试听确认 → 角色配音（按 P1 选定机制）→ 环境音（Seed Audio 1.0）→ BGM（Mureka V8，生成前把音乐提示词读给用户确认）。

### P5. 分镜图组
script 节点写入 rows（`imageGenerationPrompt`/`videoMotionPrompt`/`durationSeconds`/`dialogue`/`characters[]` 等，来自方案）→ `libtv script storyboard "<剧本>" -s aspectRatio=<比例>` → 逐张自检，不合格的挂角色/场景参考图重生成。

### P6. 分镜视频（Gate 3）
→ references/libtv-pipeline.md §逐镜生成
逐镜循环：video 节点挂参考（分镜图+角色图+场景图+台词音频，≤modeType 上限）+ 分镜细节提示词（含 lens/运镜；负向：无BGM无字幕无水印）→ `--run` → 逐镜质检（画面完整/角色一致/时长正确/衔接帧）→ 失败自动调整提示词重试 ≤2 次，仍失败标记进 state.md。长镜头拆段：`libtv download` 上段 → `scripts/extract_last_frame.sh` → `upload` 尾帧 → frames2video 生成下段。
全部完成后 video-clip 节点按镜号串联（简单拼接路径），报画布 URL。
**→ GATE 3: PRESENT 编排结果（画布链接 + 问题镜清单 + 抽帧总览图），WAIT 批准。**

### P7. 配乐（Gate 4）
按方案把 BGM/环境音接入 video-clip 时间线（`clipTimelineData`，静态音量，天花板见 references/libtv-pipeline.md §终剪）——此版供用户在画布里预览检查；精细混音留给 P8。
**→ GATE 4: PRESENT 带乐版画布预览，WAIT 批准。**

### P8. 下载与本地精修交付
`libtv download -n "<终剪>" --without-ai-watermark -o final/` → **询问用户**：是否加字幕？片头片尾要什么样式？→ 按需执行：`scripts/mix_and_master.sh`（三轨平衡/淡入淡出/`--duck` 对白闪避）→ `scripts/burn_subs_and_cards.sh`（字幕/片头/片尾）→ SendUserFile 交付成片，caption 注明需要复听/复看的点。
→ references/post-production.md（字幕文件生成、片头片尾卡制作、参数细节）

## Engine scripts (scripts/)

`contact_sheet.py`（图片素材/成片抽帧总览图，images|video 两模式）· `extract_last_frame.sh`（抽尾帧供 frames2video 衔接）· `mix_and_master.sh`（三轨混音+闪避+响度归一）· `burn_subs_and_cards.sh`（字幕烧录+片头片尾卡拼接）· `render_subs.py`（SRT→PIL 透明 PNG+overlay 链，被 burn 脚本调用；本机 ffmpeg 无 libass）

## References（到步骤再读）

- **production-plan-template.md** — 制作方案 17 板块模板 + ChatGPT 分段提问脚手架 + 完整性校验清单（P2）
- **chatgpt-assets.md** — Web GPT 驱动规程与素材生成序列、一致性链、图片进出、限额处理（P2/P3）
- **libtv-pipeline.md** — LibTV 全链路命令参考：建站/上传/注册表/音频/分镜图/逐镜视频/首尾帧/终剪/下载（P4–P7）
- **post-production.md** — 本地后期：混音、字幕、片头片尾、交付（P8）

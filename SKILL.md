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
2. **`-s model=` 只接受 modelName**（实测真名如 `Seedance 2.0 VIP`、`Mureka V8`，文档里的名字会过期，每次 `libtv model search` 实查），传 modelKey 会报错。含空格必须引号。
2b. **视频提示词一律中文分区关键词**（`【主体§3】…【运镜§10】…` 形式），由 GPT 在 §17 直接产出成品，**不翻译不压缩原样喂给视频模型**。实测同一镜英文散文 2000 字符只覆盖 5 个板块、中文关键词 750 字符覆盖 11 个；Seedance `maxLength: 0` 无长度上限（**只有 Mureka 是 1024**，别把音频模型的限制套到视频模型上）。排序即优先级：主体一致性/运镜/禁止项靠前。
2c. **分镜是三层结构**：分镜(叙事单元) → 镜头(生成单元，4–15 整数秒) → 运镜段(镜头内运动分段)。**<4 秒的镜头不单独生成**，写进 §17【切镜】行并入同一次生成。
3. **`--run` 是同步阻塞命令**：不当异步提交、不自行加 timeout、不额外轮询、不因看到 taskId 就停。进度看 stderr（约 3 分钟一条）。长任务用 Bash 后台任务跑**整条阻塞命令**并等完成通知。
4. **模型 schema 以运行时实查为准**：每次运行先 `libtv model search --type <t>` + `libtv model <key>`，不硬编码文档里的枚举（文档样本会过期；`download`、Seed Audio 都是文档没有而真机有的例子）。
5. **画面比例三处键名不同但必须同值**：GPT 生图（提示词措辞）、`script storyboard -s aspectRatio=`、video 节点 `-s ratio=`。P1 确认后写入 manifest，逐步引用。
6. **单镜 duration 4–15 秒**；更长的镜头必须拆段并用 frames2video 首尾帧衔接（见 references/libtv-pipeline.md）。
7. **节点名一律带run前缀**（如 `S01·镜-03`、`S01·BGM-开场`），失败清理靠前缀批删；`--left` 数量受 modeType.items 上限约束。
8. **并行写入不共管道**：多个 `libtv` 写命令并行会让 NDJSON 穿插损坏，串行 `&&` 链或分文件再合并。
9. **真人照片作参考图会触发 Seedance 合规校验中止**——素材全部用 GPT 生成图可规避；若用户提供真人照片，先警告。
10. **分镜视频生成时禁止 BGM 与字幕**（写进每条提示词的【禁止】行）；音乐只在 P7 进入，字幕只在 P8 进入。但**环境音与外语独白反而要在生成时一起出**——写进 §17【音效】行 + `enableSound=on`，音画天然同步，不做独立 TTS/音效生成。
10b. **提示词里为转场做的构图准备，剪辑阶段必须真正执行对应转场**。写了「让某色块靠近画框右缘以便色彩匹配」却只做硬切，等于白写——这是本次实测漏掉的一环。
10c. **场景要有生活感**：除非剧本明确要求空场，否则每镜【群演】行必须写背景人流车流（略失焦·不看镜头·不遮挡主体·不穿与主角同色服装）。负提示词里写 `no people` 会把整座城市清空，是本次返工的直接原因。
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
用 AskUserQuestion 收齐并写入 manifest：**主题与大纲**（用户口述，复述确认）、**画面比例**、**目标总时长**（按整数秒排镜，别留 7.5s）、**配音机制**（默认且推荐：视频模型 `enableSound=on` 自带语音——实测外语独白效果好过 TTS，且免去口型对齐；仅当需要指定音色时才走 TTS）、**视频模型与画质**（`libtv model search --type video` 实查后确认）、**配乐模型**（默认 Mureka V8，须确认）。
按时长估算生成量（分镜数≈总时长/8s；图片≈角色数×8+场景数×4+道具数）并告知：**CLI 无积分查询命令**，请用户自查网页端余额是否充足。

### P2. 制作方案（Gate 1）
→ references/production-plan-template.md（方案 17 个板块的完整模板与 ChatGPT 分段提问脚手架）
在用户的 ChatGPT 里**新建 project**，按模板分段生成完整制作方案，保存 `plan/production-plan.md`。
**提问时就要写死两条**（否则整轮白做）：①§16/§17 必须是**中文分区关键词成品**，不要英文散文；②§11 用**三层结构**，每个镜头标时长(4–15整数秒)与生成方式。
按模板的汇总校验清单逐项核对——重点查那些**"写在方案里但没落到提示词里"**的板块：§9 色值是否进了【色彩】行、§14 音效关键词是否逐镜进了【音效】行、§10 转场准备是否有对应的剪辑动作。
**→ GATE 1: PRESENT 完整方案文件给用户 review，WAIT 批准后才进素材阶段。**

### P3. 图片素材（Gate 2）
→ references/chatgpt-assets.md（GPT 驱动规程、一致性链、图片进出方法、限额中断处理）
生成顺序（一致性链，环环相扣）：角色脸部白底三视图 → 表情图 → 服装白底三视图 → 各服装下角色三视图 → 场景图（每场景 4 方向，关键细节对剧本）→ 道具白底三视图。分类存 `assets/`，逐张复检三个一致性（人物/场景/道具）。
`python3 scripts/contact_sheet.py images assets -o build/cs_all.png` 自查后 SendUserFile。
**→ GATE 2: PRESENT 素材总览图，WAIT 批准后才上传 LibTV。**

### P4. LibTV 建站与音频素材
→ references/libtv-pipeline.md（建站、上传命名、角色注册表、BGM 生成）
`workspace create/use` → `project create/use` → 逐个 `libtv upload`（命名 `<类>-<名>-<变体>`）→ 写 `characters.json`（角色→参考图节点+外貌提示词，这是「主体」的 CLI 等价物）→ BGM（Mureka V8，`scene=Music`，提示词 ≤450 字符）。
**环境音与独白不在这里生成**——它们随视频一起出（见硬规则 10）。

### P5. 分镜图组（可选）
镜头数少（≤6）且已有场景图时可跳过：直接把场景图+角色图作为参考挂进视频节点，比走 script/storyboard 机制更可控。
需要时：script 节点写入 rows（`imageGenerationPrompt`/`videoMotionPrompt`/`durationSeconds`/`dialogue`/`characters[]`）→ `libtv script storyboard "<剧本>" -s aspectRatio=<比例>` → 逐张自检，不合格的挂角色/场景参考图重生成。

### P6. 分镜视频（Gate 3）
→ references/libtv-pipeline.md §逐镜生成
逐镜头循环：video 节点挂参考（场景图+角色图+道具图，≤modeType 上限）+ **§17 中文卡原样贴入** + `enableSound=on` → `--run` → 逐镜质检（画面完整/角色一致/**背景人流车流是否到位**/时长/衔接帧；小道具要放大裁切核对）→ 失败调整提示词重试 ≤2 次，仍失败记 state.md。长镜头拆段：`libtv download` 上段 → `scripts/extract_last_frame.sh` → `upload` 尾帧 → frames2video 生成下段。
全部完成后**本地 ffmpeg `-c copy` 拼接**（各段参数天然一致，零积分零损失），并执行 §17【转场】要求的转场动作。
**→ GATE 3: PRESENT 成片 + 问题镜清单，WAIT 批准。**

### P7. 配乐（Gate 4）
Mureka 无时长参数会出 2–3 分钟完整曲 → 按能量包络选段（导 PCM 算 RMS，找「起始最安静、末段最强」的窗口）→ **定点闪避**：只在独白秒段把 BGM 降到 ~42%（带 0.4s 斜坡）。**不要用 sidechain 自动闪避**——环境音是持续的，会让 BGM 一直被压并产生泵浦感。
**→ GATE 4: PRESENT 带乐版，WAIT 批准。**

### P8. 本地精修交付
**询问用户**：是否加字幕（中/外双语？）？片头片尾要什么样式？→ 按需执行：`scripts/burn_subs_and_cards.sh`（字幕/片头/片尾）→ SendUserFile 交付，同时保留一份无字幕版。片尾标题日系片建议明朝体+宽字距，位置避开主体动作区。
→ references/post-production.md（字幕文件生成、片头片尾卡制作、参数细节）

## Engine scripts (scripts/)

`contact_sheet.py`（图片素材/成片抽帧总览图，images|video 两模式）· `extract_last_frame.sh`（抽尾帧供 frames2video 衔接）· `mix_and_master.sh`（三轨混音+闪避+响度归一）· `burn_subs_and_cards.sh`（字幕烧录+片头片尾卡拼接）· `render_subs.py`（SRT→PIL 透明 PNG+overlay 链，被 burn 脚本调用；本机 ffmpeg 无 libass）· `fill_signage.py`（**画面内空白牌面/屏幕后期补全**：模板跟踪+运动模型拟合+亮度遮罩，处理 AI 生成的空信息屏/店招，比重生成整段便宜且不动已批准画面）

**用后期补而不是重生成**：AI 生成常见的局部瑕疵（空白信息屏、缺失文字、需要微调的元素），优先用 `fill_signage.py` 这类合成手段修——重生成会连已通过的构图、表演、一致性一起赌掉。

## References（到步骤再读）

- **production-plan-template.md** — 制作方案 17 板块模板 + ChatGPT 分段提问脚手架 + 完整性校验清单（P2）
- **chatgpt-assets.md** — Web GPT 驱动规程与素材生成序列、一致性链、图片进出、限额处理（P2/P3）
- **libtv-pipeline.md** — LibTV 全链路命令参考：建站/上传/注册表/音频/分镜图/逐镜视频/首尾帧/终剪/下载（P4–P7）
- **post-production.md** — 本地后期：混音、字幕、片头片尾、交付（P8）

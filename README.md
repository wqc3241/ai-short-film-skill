# ai-short-film — 端到端 AI 短片工作流 Skill

A [Claude Code](https://claude.com/claude-code) skill that runs an end-to-end AI short-film pipeline: from a one-line theme to a delivered film.

从一句主题到可交付成片的完整流水线：

- **制作方案与图片素材** — 在用户自己的 Web ChatGPT 里生成（15 板块制作方案模板、全流程中文提示词、角色三视图/表情/服装/场景/道具/分镜首帧，全链一致性锚定）
- **音频 / 分镜图 / 分镜视频 / 终剪** — 通过 [LibTV](https://www.liblib.tv) 官方 CLI（`libtv`）在画布上完成：TTS 配音、Seed Audio 环境音、Mureka V8 配乐、`script storyboard` 分镜图组、Seedance 2.0 逐镜视频（含长镜头首尾帧拆段衔接）、video-clip 终剪
- **本地后期** — ffmpeg 三轨混音（BGM 对白闪避）、字幕烧录（PIL+overlay，不依赖 libass）、片头片尾卡、交付

## 安装

```bash
git clone https://github.com/wqc3241/ai-short-film-skill.git ~/.claude/skills/ai-short-film
```

## 依赖

| 依赖 | 说明 |
|---|---|
| [LibTV CLI](https://www.liblib.tv) (`libtv`) | 画布操作与所有云端生成；需登录（`libtv login web`） |
| libtv-cli skill | LibTV 官方命令手册 skill（本 skill 的 REQUIRED SUB-SKILL） |
| Claude-in-Chrome | 驱动用户已登录的 Web ChatGPT 生成方案与图片素材 |
| ffmpeg + Python3/Pillow | 本地质检与后期（字幕方案不依赖 libass，精简构建可用） |

## 工作流概览

P0 前置检查 → P1 立项(Gate 0: 比例/时长/配音机制/模型确认) → P2 制作方案(Gate 1) → P3 图片素材(Gate 2: contact sheet 过目) → P4 LibTV 建站与音频 → P5 分镜图组 → P6 逐镜视频(Gate 3: 编排检查, 自动重试≤2) → P7 配乐(Gate 4) → P8 下载与本地精修交付。

细节见 [SKILL.md](SKILL.md) 与 `references/`。

## 目录

```
SKILL.md                                # 工作流 + 硬规则 + 检查闸门
references/production-plan-template.md  # 制作方案 15 板块模板（§17 即梦官方四段式）+ ChatGPT 提问脚手架
references/chatgpt-assets.md            # Web GPT 驱动规程与素材一致性链
references/libtv-pipeline.md            # LibTV 全链路命令参考
references/post-production.md           # 本地混音/字幕/片头片尾/交付
scripts/                                # contact sheet、抽尾帧、混音、字幕烧录
```

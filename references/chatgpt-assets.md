# Web ChatGPT 驱动规程与图片素材生成（P2/P3）

工具：claude-in-chrome（用户真实 Chrome，已登录 ChatGPT）。完整驱动手法的权威出处是 `~/.claude/skills/xhs-personal-vlog/references/copy-generation.md`（进出图桥、JS 注入细节），本文只列本 skill 必需的规则与差异。

## 驱动规则（违反必翻车）

1. **每次运行为本片新建一个 ChatGPT project**，方案与素材都在其中（上下文连续=一致性来源之一）。项目 URL 从 DOM 取：`[...document.querySelectorAll('a[href*="/g/g-p-"]')]`，直接导航 `https://chatgpt.com/g/<project-id>/project`。
2. **提示词必须单行**——换行会自动发送。用 `、；【】` 和 `1) 2) 3)` 组织。
3. **不要 computer type 输入长提示词**（会静默丢字）：`javascript_tool` 用 `execCommand('selectAll')+('delete')+('insertText', P)` 注入，校验 `#prompt-textarea` innerText 关键子串后 JS 点击 `button[data-testid="send-button"]`。别点错旁边的语音波形按钮。
4. **一次只要一个产物**（one asset per turn）——多任务合并请求会塌缩只出一个。
5. 等待节奏：文本 30–60s、图片 60–120s，10s 步进轮询 `get_page_text`；Canvas 卡流时要求「纯文本对话回复」并刷新页面看服务端真相。
6. **取图**：页内 `fetch(img.src)` → base64 → POST 到 localhost 桥（起临时 `python3 -m http.server` 型接收脚本或复用 `xhs-personal-vlog/scripts/cover_bridge.py`）。**base64 内容绝不放进工具返回值**（会被安全过滤），JS 里只 return 长度/校验值。
7. **喂参考图回 GPT**：压到 ≤20KB JPEG → base64 分 3200 字符块注入 `window.__P`（每块校验累计长度）→ `atob`→`Uint8Array`（校验 JPEG 魔数 0xFFD8）→ `new File`→`DataTransfer`→ 对聚焦的 `#prompt-textarea` 派发 `ClipboardEvent('paste')`。
8. **改图 vs 重生成**：布局/构图/内容结构变化 → 开新对话重生成；属性微调（换色/修一处细节）→ 同线程「基于你上一张生成的图修改：…」（重出图会连底图一起换掉）。
9. **限额中断**（"You've hit your usage limit"）：把**未发出的提示词原文**逐条存入 `state.md`，更新 manifest，交还用户等重置——不要 retry-loop，不要降级自己画。

## 素材生成序列（一致性链——顺序即依赖）

所有图片提示词来自方案 §3/§12/§13；**每张图的提示词都要带上比例措辞与负提示词**。每生成一张：下载 → 存入 `assets/` 对应目录（命名见下）→ 与链上游对图复检 → 更新 manifest。

| 步 | 产物 | 一致性锚点（必须作为参考图上传回 GPT） |
|---|---|---|
| 1 | 每角色·脸部白底三视图（定妆图） | —（链的源头；不满意就重来，后面全靠它） |
| 2 | 每角色·情感表情图（≥6 表情一张网格） | 该角色定妆图 |
| 3 | 每套服装·白底三视图 | —（纯服装，无人） |
| 4 | 每角色×每套服装·着装三视图 | 定妆图 + 对应服装图 **两张都挂** |
| 5 | 每场景×4 方向（东南西北/前后左右） | 同场景已生成的方向图（第 2–4 张挂第 1 张，锁空间一致） |
| 6 | 主要道具·白底三视图 | —（对照 §13 描述核对细节） |

**场景关键细节**：§12 标注的剧本相关元素（文字/位置/数量）逐张放大核对——中文字是 GPT 生图第一失败点，错字必须同线程改图修正。

## 命名与目录

```
assets/characters/<角色>-定妆三视图.png / <角色>-表情.png / <角色>-<服装>-三视图.png
assets/characters/服装-<服装名>-三视图.png
assets/scenes/<场景>-<方向>.png        # 方向 ∈ {正,右,背,左} 或 {N,E,S,W}
assets/props/<道具名>-三视图.png
```
文件名（去扩展名）= 之后 `libtv upload` 的节点显示名，全片唯一。

## 三重一致性自检（Gate 2 之前）

1. **人物**：同一角色所有图并排（contact_sheet.py 按角色目录出图）——脸型/发型/身形/标志特征逐项对比。
2. **场景**：同场景 4 方向空间逻辑自洽（门窗位置对得上），关键细节与 §12 一致。
3. **道具**：与 §13 描述逐字段核对。
不合格 → 按规则 8 改图或重生成，**换锚点图必须级联重查其所有下游**。

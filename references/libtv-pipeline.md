# LibTV 流水线命令参考（P4–P7）

命令细节的权威出处是 libtv-cli skill 与 `libtv <子命令> --help`；本文是本工作流用到的调用序列与坑位。所有生成型 `--run` 都是同步阻塞（SKILL.md 硬规则 3）。

## P4a. 建站

```bash
WS=$(libtv workspace create "<片名>" | jq -r '.workspaceId') && libtv workspace use "$WS"
EP=$(libtv project create "<片名>-画布" | jq -r '.uuid') && libtv project use "$EP"
```
在**项目目录**下执行（状态写入 `./.libtv/project.json`）。坑：`workspace use` 会清掉 `projectUuid`，顺序必须先 workspace 后 project；`project list -p` 是页码而 `node -p` 是画布 UUID，别混。把画布 URL 报给用户：`https://www.liblib.tv/canvas?spaceId=<WS>&projectId=<EP>`。

## P4b. 上传素材

```bash
find assets -name '*.png' | while read -r f; do
  n=$(basename "$f" .png)
  libtv upload "$n" -f "$f" -t image || { echo "FAIL $n" >> build/upload-fail.txt; }
done
```
显示名是**位置参数**（无 --name flag），无批量命令只能循环；重名由画布自动去重——所以文件名必须全片唯一。上传完 `libtv node list | jq '.count'` 对账 manifest。

## P4c. 角色注册表 characters.json（「主体」的 CLI 等价物）

```json
{ "林悦": { "refNodes": ["林悦-定妆三视图", "林悦-冬装-三视图"],
            "voiceId": "<音色ID>", "voiceModel": "Eleven V3",
            "appearance": "<外貌提示词一句>" } }
```
每次给某角色出镜的分镜建 video 节点时：`--left` 挂该角色 refNodes、提示词嵌 appearance、台词音频用 voiceId 生成。**这是跨镜一致性的机制，漏挂=角色漂移。**

## P4d. 音色发现与三类音频

模型先实查：`libtv model search --type audio`；TTS 音色是 singleSelect 动态选项，文档无枚举——先 `libtv model vocal-v3` 看 schema，若无 enum 则生成一条短句试听（每候选音色一个小节点），下载给用户听后把选定 ID 写入 characters.json，试听节点删除。

```bash
# 角色配音（逐句；节点名 = S<镜号>·白-<角色>-<序号>）
libtv node create "S03·白-林悦-1" -t audio --prompt "<台词>（<语气，来自§5/§17>）" \
  --set "model=Eleven V3" --set voice=<ID> --set stability=0.5 --run
# 环境音/音效（Seed Audio 1.0：人声/音效/音乐一体化，方案§14 提示词）
libtv node create "S03·环境-雨夜街道" -t audio --prompt "<§14提示词>" \
  --set "model=Seed Audio 1.0" --run
# BGM（生成前把 §15 提示词读给用户确认）
libtv node create "全片·BGM-开场" -t audio --prompt "<§15提示词>" \
  --set "model=Mureka V8" --set instrumental=1 --run
```
坑：部分 TTS 模型时长参数是**毫秒**（`music_length_ms`）；`-s` 具体键以 `libtv model <key>` 实查为准。全部音频 `libtv download` 存 `assets/audio/` 备 P8 本地混音用。

## P5. 剧本 → 分镜图组

```bash
libtv node create "剧本" -t script --set "model=<script模型，实查>" 
libtv node "剧本" -u rows='[<全量行数组>]'   # rows 只能整块替换，别指望改单行
libtv script storyboard "剧本" -s "model=<image模型>" -s aspectRatio=<比例>
```
rows 每行来自方案 §11/§17：`durationSeconds`（≤15）、`plotDescription`、`characters[]`（characterName/characterDescription/characterImageUrl 用已上传定妆图的 URL）、`shotSize`、`characterAction`、`emotion`、`lightingAndAtmosphere`、`audioEffects`、`dialogue`、**`imageGenerationPrompt`**（分镜图用）、**`videoMotionPrompt`**（视频用）。坑：分镜图组的比例键名是 **`aspectRatio`**（video 节点才是 `ratio`）；`shotNumber`/`title`/`linkedImageGroupId` 服务端维护别写。输出 `imageRuns[]` 里 `status=3` 的行单独重跑：给对应 image 节点 `--left` 挂角色/场景参考图后 `--run`。

## P6. 逐镜视频生成

每镜（含拆段子镜）循环，节点名 `S<镜号>·镜`：

```bash
libtv node create "S03·镜" -t video \
  --prompt "<§16统一风格>；<§17本镜卡：场景细节/情感/主体/运镜/镜头型号/焦距>；负向：无背景音乐、无字幕、无水印、无文字" \
  --set "model=Seedance 2.0" --set modeType=mixed2video \
  --set ratio=<比例> --set resolution=720p --set duration=<秒> --set enableSound=<on|off按P1配音机制> \
  --left "S03-分镜图" --left "林悦-定妆三视图" --left "<场景>-正" --left "S03·白-林悦-1" --run
```
- 配音机制 A（TTS 喂入）：台词音频节点一并 `--left`（mixed2video 音频上限 3），enableSound=on 让模型对口型出人声。机制 B：不挂音频，台词写进提示词。
- `--left` 总数受 `modeType.items` 上限（mixed2video 图9/视频3/音频3），超了 CLI 直接拒。
- **质检**（每镜生成完立即）：`libtv download -n "S03·镜" -o build/qc/` → 抽首中尾 3 帧 Read：画面完整？角色与定妆图一致？无字幕无水印？时长 `ffprobe` 核对。失败 → 修改提示词（写明具体病灶）重试，≤2 次，仍败记 state.md 继续下一镜。

**长镜头拆段（首尾帧衔接）**：
```bash
libtv download -n "S07a·镜" -o build/ && scripts/extract_last_frame.sh build/S07a*.mp4 build/S07a-tail.png
libtv upload "S07a-尾帧" -f build/S07a-tail.png -t image
libtv node create "S07b·镜" -t video --prompt "<延续S07a动作的描述>…" \
  --set "model=Seedance 2.0" --set modeType=frames2video --set ratio=… --set resolution=720p \
  --left "S07a-尾帧" --run          # frames2video 挂1图=首帧；挂2图=首帧+尾帧
```
首尾帧槽位按边序分配（先 left 的为首帧）——首次使用时先用两张差异明显的图做一次 4s 便宜验证，确认槽位顺序再批量用。衔接质检：S07a 尾帧 vs S07b 首帧并排 Read，跳变即重生成 S07b。

## P6b/P7. 终剪与配乐

```bash
{ libtv node "S01·镜"; libtv node "S02·镜"; …; } | libtv node create "终剪" -t video-clip >/dev/null
libtv node "终剪" --run    # 无 clipTimelineData 时按边序首尾拼接——P6 编排检查用这条
```
P7 配乐：接入 BGM/环境音节点后写显式时间线（**天花板：1 视频轨+1 音频轨、静态音量、无淡入淡出无闪避**——只求画布可预览，精修在 P8）：
```bash
libtv node "终剪" --left-add "全片·BGM-开场"
libtv node "终剪" -u clipTimelineData='{"clips":[{"sourceNodeId":"<BGM节点id>","type":"audio","startTime":0,"duration":<全长>,"sourceOffset":0,"sourceDuration":<素材长>,"decibel":-12}],"videoAudioVolume":1,"audioTrackVolume":0.6}' 
libtv node "终剪" --run
```
坑：`videoSourceNodeIds`/`audioSourceNodeIds` 由 CLI 从边自动维护，手写会被覆盖；clips 四个时间字段（startTime/duration/sourceOffset/sourceDuration）都必填，单位秒。

## P8 入口. 下载成片

```bash
libtv download -n "终剪" --without-ai-watermark -o final/
```
分组批量下载出 ZIP（`-n` 传分组节点 id + `-g`）。下载后 `ffprobe` 核对时长与分辨率再进后期。

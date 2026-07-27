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
# BGM（提示词 ≤450 字符；Mureka 声明上限 1024，1500 字符会失败）
libtv node create "全片·BGM" -t audio --prompt "<§15提示词,精简版>" \
  --set "model=Mureka V8" --set scene=Music --set instrumental=1 --run
```

**环境音不在这里生成**——写进 §17 每镜的【音效】行，由视频模型 `enableSound=on` 连画面一起出，音画天然同步且省一轮生成。只有当成片听感确实缺层次时，才在 P8 用 Seed Audio 1.0 补做叠加。

坑：
- **Mureka 必须 `--set scene=Music`**，否则报「音频新建节点默认场景为 Text-to-Speech，与所选模型 catalog 场景不一致」
- **Mureka 没有时长参数**，会出 2–3 分钟完整曲。P8 按能量包络选段：`ffmpeg -f s16le` 导出 PCM → numpy 算每 0.25s RMS → 找「起始最安静、末段最强」的窗口
- 日语等非中英语种：Seed Audio `language` 枚举**只有 zh/en**；Minimax speech 实测能念日语但音色库 CLI 不可枚举（只有中文默认音色）。**外语独白优先走视频模型自带语音**（写进 §17 音效行），实测效果好过 TTS
- 部分 TTS 模型时长参数是**毫秒**（`music_length_ms`）；`-s` 具体键以 `libtv model <key>` 实查为准

## P5. 剧本 → 分镜图组

```bash
libtv node create "剧本" -t script --set "model=<script模型，实查>" 
libtv node "剧本" -u rows='[<全量行数组>]'   # rows 只能整块替换，别指望改单行
libtv script storyboard "剧本" -s "model=<image模型>" -s aspectRatio=<比例>
```
rows 每行来自方案 §11/§17：`durationSeconds`（≤15）、`plotDescription`、`characters[]`（characterName/characterDescription/characterImageUrl 用已上传定妆图的 URL）、`shotSize`、`characterAction`、`emotion`、`lightingAndAtmosphere`、`audioEffects`、`dialogue`、**`imageGenerationPrompt`**（分镜图用）、**`videoMotionPrompt`**（视频用）。坑：分镜图组的比例键名是 **`aspectRatio`**（video 节点才是 `ratio`）；`shotNumber`/`title`/`linkedImageGroupId` 服务端维护别写。输出 `imageRuns[]` 里 `status=3` 的行单独重跑：给对应 image 节点 `--left` 挂角色/场景参考图后 `--run`。

## P6. 逐镜视频生成

**先实查模型名**：`libtv model search --type video`。文档里的名字会过期——实测「Seedance 2.0」已不存在，真名是 **`Seedance 2.0 VIP`**（`-s model=` 只接受 modelName，传 modelKey 报错）。

每个**镜头**（§11 三层结构里的生成单元）循环，节点名 `<前缀>·S<镜号>·镜`：

```bash
libtv node create "HKD·S02·镜" -t video \
  --prompt "<§17 该镜的中文分区关键词卡，整卡原样贴进来>" \
  --set "model=Seedance 2.0 VIP" --set modeType=mixed2video \
  --set ratio=<比例> --set resolution=720p --set duration=<4-15整数秒> --set enableSound=on \
  --left "<场景图>" --left "<角色定妆三视图>" --left "<道具图>" --run
```

- **提示词直接用 §17 的中文卡，不要翻译不要压缩**。Seedance 声明 `maxLength: 0`（**无长度上限**）——这次误以为它和 Mureka 一样有 1024 上限，把 GPT 写好的提示词整条丢弃重写，白费一轮
- **`enableSound=on` 承担全部环境音与外语独白**：音效关键词和独白秒段都在 §17 的【音效】行里
- `--left` 数量受 `modeType.items` 上限（mixed2video 图9/视频3/音频3），超了 CLI 直接拒
- **`duration` 只接受 4–15 整数秒**。<4s 的镜头不要单独生成（按 4s 计费再裁，浪费），改用 §17 的【切镜】行并入同一次生成
- **质检**（每镜生成完立即）：`libtv download -n "<节点>" --without-ai-watermark --vip -o shots/` → contact_sheet 抽 8 帧 Read。查：画面完整？角色与定妆图一致？**背景有无该有的人流车流**？无字幕无水印？时长 `ffprobe` 核对。缩略图上易误判的小道具要**放大裁切**再看（实测：手持旧照片在缩略图上像手机，放大后是白边照片）。失败 → 提示词写明具体病灶重试，≤2 次，仍败记 state.md
- **去水印必须 `--without-ai-watermark` 加 `--vip` 两个都给**，只给前者成片仍带 LibTV 水印

**长镜头拆段（首尾帧衔接）**：
```bash
libtv download -n "S07a·镜" -o build/ && scripts/extract_last_frame.sh build/S07a*.mp4 build/S07a-tail.png
libtv upload "S07a-尾帧" -f build/S07a-tail.png -t image
libtv node create "S07b·镜" -t video --prompt "<延续S07a动作的描述>…" \
  --set "model=Seedance 2.0 VIP" --set modeType=frames2video --set ratio=… --set resolution=720p \
  --left "S07a-尾帧" --run          # frames2video 挂1图=首帧；挂2图=首帧+尾帧
```
首尾帧槽位按边序分配（先 left 的为首帧）——首次使用时先用两张差异明显的图做一次 4s 便宜验证，确认槽位顺序再批量用。衔接质检：S07a 尾帧 vs S07b 首帧并排 Read，跳变即重生成 S07b。

## P6b/P7. 终剪与配乐

**首选本地 ffmpeg 拼接，不用画布终剪**：四段素材质检时已下载到本地，各段参数天然一致（同模型同分辨率同帧率），`-c copy` 无损直拼，零积分零画质损失，且顺序完全可控。
```bash
for f in shots/S01.mp4 shots/S02.mp4 …; do echo "file '$PWD/$f'" >> list.txt; done
ffmpeg -f concat -safe 0 -i list.txt -c copy build/终剪-无乐版.mp4
```
拼接前 `ffprobe` 核对四段的 codec/分辨率/帧率/音频采样率是否一致；不一致才重编码。

**§17 写了【转场】的镜，这一步必须真正执行对应转场**（叠化/色彩匹配剪辑），不能一律硬切——否则提示词里为转场做的构图准备（如"让黄色车身色块靠近右缘"）全部白做。这是本次实测漏掉的一环。

画布终剪仅在需要给用户在画布里预览时才做：
```bash
{ libtv node "S01·镜"; libtv node "S02·镜"; …; } | libtv node create "终剪" -t video-clip >/dev/null
libtv node "终剪" --run    # 无 clipTimelineData 时按边序拼接，边序不保证=镜号序！
```
坑：**边序是乱的**，必须写显式 `clipTimelineData` 锁顺序；且 `--run` 的结果 URL 只在 stdout 出现一次，`libtv download` 对 video-clip 节点常报「没有可下载的资源」——**别用 `tail` 截断 `--run` 输出**，否则 URL 丢失只能重跑。
P7 配乐：接入 BGM/环境音节点后写显式时间线（**天花板：1 视频轨+1 音频轨、静态音量、无淡入淡出无闪避**——只求画布可预览，精修在 P8）：
```bash
libtv node "终剪" --left-add "全片·BGM-开场"
libtv node "终剪" -u clipTimelineData='{"clips":[{"sourceNodeId":"<BGM节点id>","type":"audio","startTime":0,"duration":<全长>,"sourceOffset":0,"sourceDuration":<素材长>,"decibel":-12}],"videoAudioVolume":1,"audioTrackVolume":0.6}' 
libtv node "终剪" --run
```
坑：`videoSourceNodeIds`/`audioSourceNodeIds` 由 CLI 从边自动维护，手写会被覆盖；clips 四个时间字段（startTime/duration/sourceOffset/sourceDuration）都必填，单位秒。

## P8 入口. 下载成片

```bash
libtv download -n "终剪" --without-ai-watermark --vip -o final/   # 两个标志都要给，否则带水印
```
分组批量下载出 ZIP（`-n` 传分组节点 id + `-g`）。下载后 `ffprobe` 核对时长与分辨率再进后期。

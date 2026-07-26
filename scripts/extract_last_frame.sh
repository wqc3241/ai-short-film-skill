#!/usr/bin/env bash
# 抽取视频最后一帧（用于 frames2video 首尾帧衔接：上一段的尾帧 = 下一段的首帧参考）。
# 用法: extract_last_frame.sh <video.mp4> <out.png>
set -euo pipefail
[[ $# -eq 2 ]] || { echo "usage: extract_last_frame.sh <video> <out.png>" >&2; exit 1; }
# -sseof 从末尾回退 0.15s 起解码到 EOF，-update 1 让最后写入的一帧留下——比按时长定位更抗时间戳误差
ffmpeg -y -loglevel error -sseof -0.15 -i "$1" -vsync 0 -q:v 1 -update 1 "$2"
[[ -s "$2" ]] || { echo "no frame extracted from $1" >&2; exit 1; }
echo "$2"

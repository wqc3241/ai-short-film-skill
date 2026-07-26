#!/usr/bin/env bash
# 字幕烧录 + 片头/片尾卡拼接（均可选）。片头/片尾卡为静态图（PNG，与正片同分辨率），配黑场淡入淡出。
# 字幕不依赖 libass（本机 ffmpeg 未编译 subtitles/ass/drawtext 滤镜）：render_subs.py 用 PIL 逐条渲染
# 透明 PNG，再以 overlay+enable 时间窗叠加。
# 用法: burn_subs_and_cards.sh <film.mp4> <out.mp4> [--srt subs.srt] [--title title.png --title-dur 3] [--credits credits.png --credits-dur 5]
set -euo pipefail
FILM="$1"; OUT="$2"; shift 2
SRT="" TITLE="" CREDITS="" TDUR=3 CDUR=5
while [[ $# -gt 0 ]]; do case "$1" in
  --srt) SRT="$2"; shift 2;;
  --title) TITLE="$2"; shift 2;; --title-dur) TDUR="$2"; shift 2;;
  --credits) CREDITS="$2"; shift 2;; --credits-dur) CDUR="$2"; shift 2;;
  *) echo "unknown arg $1" >&2; exit 1;;
esac; done
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CUR="$FILM"

if [[ -n "$SRT" ]]; then
  R=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$CUR")
  W=${R%%,*}; H=${R##*,}
  python3 "$HERE/render_subs.py" "$SRT" "$W" "$H" "$TMP/subs"
  IFS=$'\t' read -r INPUTS FC LASTPAD < "$TMP/subs/filter.txt"
  # shellcheck disable=SC2086 — INPUTS 是成对的 "-i path" 序列
  ffmpeg -y -loglevel error -i "$CUR" $INPUTS -filter_complex "$FC" \
    -map "$LASTPAD" -map 0:a -c:v libx264 -pix_fmt yuv420p -c:a copy "$TMP/subbed.mp4"
  CUR="$TMP/subbed.mp4"
fi

if [[ -n "$TITLE" || -n "$CREDITS" ]]; then
  R=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$CUR")
  W=${R%%,*}; T=${R#*,}; H=${T%%,*}; FPS=${R##*,}
  # concat demuxer 要求各段流参数完全同质：所有段统一 libx264/yuv420p + aac 48k 立体声，拼接才能 -c copy
  AENC=(-c:a aac -ar 48000 -ac 2 -b:a 192k)
  card() { # $1 img  $2 dur  $3 out — 静态卡 + 无声音轨，前后 0.5s 淡入淡出
    ffmpeg -y -loglevel error -loop 1 -t "$2" -i "$1" -f lavfi -t "$2" -i anullsrc=r=48000:cl=stereo \
      -vf "scale=$W:$H,fade=t=in:d=0.5,fade=t=out:st=$(python3 -c "print(max(0,$2-0.5))"):d=0.5,fps=$FPS,format=yuv420p" \
      -c:v libx264 "${AENC[@]}" -shortest "$3"; }
  LIST="$TMP/list.txt"; : > "$LIST"
  [[ -n "$TITLE" ]] && { card "$TITLE" "$TDUR" "$TMP/t.mp4"; echo "file '$TMP/t.mp4'" >> "$LIST"; }
  ffmpeg -y -loglevel error -i "$CUR" -vf "fps=$FPS,format=yuv420p" -c:v libx264 "${AENC[@]}" "$TMP/main.mp4"
  echo "file '$TMP/main.mp4'" >> "$LIST"
  [[ -n "$CREDITS" ]] && { card "$CREDITS" "$CDUR" "$TMP/c.mp4"; echo "file '$TMP/c.mp4'" >> "$LIST"; }
  ffmpeg -y -loglevel error -f concat -safe 0 -i "$LIST" -c copy "$OUT"
else
  [[ "$CUR" == "$FILM" ]] && cp "$FILM" "$OUT" || mv "$CUR" "$OUT"
fi
echo "$OUT"

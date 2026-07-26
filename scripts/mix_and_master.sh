#!/usr/bin/env bash
# 三轨精修混音：成片(含对白/现场声) + BGM + 环境音 → 淡入淡出 + BGM 对白闪避(sidechain) + 响度归一。
# 用法: mix_and_master.sh <film.mp4> <out.mp4> [--bgm bgm.mp3 --bgm-vol 0.35] [--amb amb.mp3 --amb-vol 0.2] [--duck] [--fade 1.5]
# 无 --bgm/--amb 时仅做响度归一(loudnorm)。--duck 用对白轨压低 BGM（遇人声自动闪避）。
set -euo pipefail
FILM="$1"; OUT="$2"; shift 2
BGM="" AMB="" BGMV=0.35 AMBV=0.2 DUCK=0 FADE=1.5
while [[ $# -gt 0 ]]; do case "$1" in
  --bgm) BGM="$2"; shift 2;; --bgm-vol) BGMV="$2"; shift 2;;
  --amb) AMB="$2"; shift 2;; --amb-vol) AMBV="$2"; shift 2;;
  --duck) DUCK=1; shift;; --fade) FADE="$2"; shift 2;;
  *) echo "unknown arg $1" >&2; exit 1;;
esac; done

D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$FILM")
FO=$(python3 -c "print(max(0,$D-$FADE))")

IN=(-i "$FILM"); FC=""; N=1
FC+="[0:a]anull[voice];"
if [[ -n "$BGM" ]]; then
  IN+=(-stream_loop -1 -i "$BGM")
  FC+="[$N:a]volume=$BGMV,atrim=0:$D,afade=t=in:d=$FADE,afade=t=out:st=$FO:d=$FADE[bgm0];"
  if [[ "$DUCK" == 1 ]]; then
    # 对白出现时 BGM 自动压低约 -12dB，释放 400ms
    FC+="[voice]asplit[v1][v2];[bgm0][v2]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[bgm];"
    VOICE="[v1]"
  else FC+="[bgm0]anull[bgm];"; VOICE="[voice]"; fi
  ((N++))
else VOICE="[voice]"; fi
if [[ -n "$AMB" ]]; then
  IN+=(-stream_loop -1 -i "$AMB")
  FC+="[$N:a]volume=$AMBV,atrim=0:$D,afade=t=in:d=$FADE,afade=t=out:st=$FO:d=$FADE[amb];"
  ((N++))
fi
MIXIN="$VOICE"; CNT=1
[[ -n "$BGM" ]] && { MIXIN+="[bgm]"; ((CNT++)); }
[[ -n "$AMB" ]] && { MIXIN+="[amb]"; ((CNT++)); }
FC+="${MIXIN}amix=inputs=$CNT:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[aout]"

ffmpeg -y -loglevel error "${IN[@]}" -filter_complex "$FC" \
  -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k "$OUT"
echo "$OUT"

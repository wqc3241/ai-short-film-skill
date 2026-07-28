#!/usr/bin/env bash
# 三轨精修混音：成片(含对白/现场声) + BGM + 环境音 → 淡入淡出 + BGM 闪避 + 响度归一。
# 用法: mix_and_master.sh <film.mp4> <out.mp4> [--bgm bgm.mp3 --bgm-vol 0.35] [--amb amb.mp3 --amb-vol 0.2]
#        [--duck-spots "a-b,c-d" [--duck-level 0.42] [--duck-ramp 0.4]] [--duck] [--fade 1.5]
# 无 --bgm/--amb 时仅做响度归一(loudnorm)。
# 闪避两种模式：
#   --duck-spots "12.3-15.6,40-45.2"  定点闪避（首选）：只在给定秒窗把 BGM 降到 duck-level(默认0.42)，
#                                     0.4s 斜坡。窗口=VO 落点 + 原声对白（先 whisper 全片拿对白清单）。
#   --duck                            sidechain 自动闪避（仅兼容保留）：环境音持续会把 BGM 一直压出泵浦感，
#                                     星火项目实测弃用，新项目不要选它。
set -euo pipefail
FILM="$1"; OUT="$2"; shift 2
BGM="" AMB="" BGMV=0.35 AMBV=0.2 DUCK=0 FADE=1.5 SPOTS="" DLVL=0.42 DRAMP=0.4
while [[ $# -gt 0 ]]; do case "$1" in
  --bgm) BGM="$2"; shift 2;; --bgm-vol) BGMV="$2"; shift 2;;
  --amb) AMB="$2"; shift 2;; --amb-vol) AMBV="$2"; shift 2;;
  --duck) DUCK=1; shift;; --fade) FADE="$2"; shift 2;;
  --duck-spots) SPOTS="$2"; shift 2;;
  --duck-level) DLVL="$2"; shift 2;; --duck-ramp) DRAMP="$2"; shift 2;;
  *) echo "unknown arg $1" >&2; exit 1;;
esac; done
if [[ -n "$SPOTS" && "$DUCK" == 1 ]]; then
  echo "warn: --duck-spots 与 --duck 同给，采用定点模式" >&2; DUCK=0
fi

D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$FILM")
FO=$(python3 -c "print(max(0,$D-$FADE))")

# 定点闪避表达式：每窗 trapezoid(0.4s 斜坡)，多窗取 max，gain = 1-(1-level)*m
SPOT_EXPR=""
if [[ -n "$SPOTS" ]]; then
  SPOT_EXPR=$(python3 - "$SPOTS" "$DLVL" "$DRAMP" << 'PY'
import sys
spots, lvl, ramp = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
terms = []
for tok in spots.split(','):
    a, b = [float(x) for x in tok.split('-')]
    terms.append(f"clip(min((t-({a-ramp:.3f}))/{ramp},(({b+ramp:.3f})-t)/{ramp}),0,1)")
m = terms[0]
for f in terms[1:]:
    m = f"max({m},{f})"
print(f"1-{1-lvl:.3f}*({m})")
PY
)
fi

IN=(-i "$FILM"); FC=""; N=1
FC+="[0:a]anull[voice];"
if [[ -n "$BGM" ]]; then
  IN+=(-stream_loop -1 -i "$BGM")
  FC+="[$N:a]volume=$BGMV,atrim=0:$D,afade=t=in:d=$FADE,afade=t=out:st=$FO:d=$FADE[bgm0];"
  if [[ -n "$SPOT_EXPR" ]]; then
    FC+="[bgm0]volume='$SPOT_EXPR':eval=frame[bgm];"
    VOICE="[voice]"
  elif [[ "$DUCK" == 1 ]]; then
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

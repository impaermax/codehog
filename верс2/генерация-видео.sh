#!/bin/bash
# Зацикленные анимации состояний персонажа для магазина и лендинга.
# Из каждого клипа берутся стабильные 2 секунды и делается бумеранг —
# модель склонна наезжать камерой, и на длинном куске петля рвётся.
set -u
cd "$(dirname "$0")"
mkdir -p vid
TAIL="The character stays centered and still. Camera holds perfectly still, no zoom, no pan. Subtle idle motion only: quills sway gently, one blink, slight breathing. Background stays flat and unchanged. No text, no new objects"

: > /tmp/видео-задачи.txt
gen() {
  NAME=$1; SRC=$2; EXTRA=$3
  if [ -f "vid/$NAME.mp4" ]; then echo "· $NAME уже есть"; return; fi
  RESP=$(pixverse create video --prompt "$EXTRA $TAIL" --image "$SRC" --model v6 \
         --quality 720p --duration 5 --count 1 --no-wait --json </dev/null 2>&1)
  ID=$(echo "$RESP" | jq -r '.video_id // empty')
  COST=$(echo "$RESP" | jq -r '.cost_credits // "?"')
  if [ -z "$ID" ]; then echo "✗ $NAME: $(echo "$RESP" | tr '\n' ' ' | head -c 120)"; return; fi
  echo "$NAME:$ID" >> /tmp/видео-задачи.txt
  echo "→ $NAME задача $ID (${COST} кр.)"
}

gen "full"    "img/hog-full.png"    "The hedgehog wearing cap, glowing glasses and backpack idles confidently."
gen "chrome"  "img/hog-chrome.png"  "Light slowly travels across the polished chrome body as a soft reflection sweep."
gen "capsule" "img/hog-capsule.png" "The monitor behind glows softly and its light flickers once across the room."
gen "loft"    "img/hog-loft.png"    "City lights behind the window twinkle slowly and server rack indicators blink."

echo; echo "жду и обрабатываю..."
while IFS=: read -r NAME ID; do
  pixverse task wait "$ID" --json </dev/null >/dev/null 2>&1
  T=$(mktemp -d)
  pixverse asset download "$ID" --dest "$T/" </dev/null >/dev/null 2>&1 || \
  pixverse asset download "$ID" --dest "$T/" </dev/null >/dev/null 2>&1
  F=$(ls "$T"/*.mp4 2>/dev/null | head -1)
  if [ -n "$F" ]; then
    ffmpeg -hide_banner -loglevel error -i "$F" -t 2.0 -an -y "/tmp/$NAME-fw.mp4"
    ffmpeg -hide_banner -loglevel error -i "/tmp/$NAME-fw.mp4" -vf reverse -an -y "/tmp/$NAME-bw.mp4"
    printf "file '/tmp/%s-fw.mp4'\nfile '/tmp/%s-bw.mp4'\n" "$NAME" "$NAME" > "/tmp/$NAME.txt"
    ffmpeg -hide_banner -loglevel error -f concat -safe 0 -i "/tmp/$NAME.txt" \
      -vf "scale=540:-2" -c:v libx264 -crf 28 -preset slow -pix_fmt yuv420p \
      -movflags +faststart -an -y "vid/$NAME.mp4"
    echo "✓ vid/$NAME.mp4 ($(du -h "vid/$NAME.mp4" | cut -f1), петля 4 с)"
  else
    echo "✗ $NAME не скачался"
  fi
  rm -rf "$T"
done < /tmp/видео-задачи.txt

#!/bin/bash
# Генерация видов персонажа в вещах магазина.
# Каждый вид делается image-to-video от базового кадра — так ёж остаётся тем же.
# Имена переменных латиницей: bash 3.2 не понимает кириллицу в идентификаторах.
set -u
cd "$(dirname "$0")"
BASE="img/hog-base.png"
OUT="img"
[ -f "$BASE" ] || { echo "нет базового кадра $BASE"; exit 1; }

TAIL="Keep the identical hedgehog character, same face, same proportions, same pose, same flat vector mascot style, same plain dark background, full body visible. No text, no logos, no watermark"

gen() {
  NAME=$1; PROMPT=$2
  if [ -f "$OUT/$NAME.png" ]; then echo "· $NAME уже есть"; return; fi
  RESP=$(pixverse create image --prompt "$PROMPT. $TAIL" --image "$BASE" \
         --model gpt-image-2.0 --aspect-ratio 3:4 --count 1 --no-wait --json </dev/null 2>&1)
  ID=$(echo "$RESP" | jq -r '.image_id // empty')
  if [ -z "$ID" ]; then echo "✗ $NAME: $(echo "$RESP" | tr '\n' ' ' | head -c 120)"; return; fi
  echo "$NAME:$ID" >> /tmp/скины-задачи.txt
  echo "→ $NAME задача $ID"
}

: > /tmp/скины-задачи.txt
gen "hog-cap"      "The hedgehog now wears a neon-teal baseball cap with a glowing '>_' symbol on the front"
gen "hog-glasses"  "The hedgehog now wears futuristic debug glasses with brightly glowing mint-green lenses instead of the plain ones"
gen "hog-backpack" "The hedgehog now wears a black technical developer backpack with mint-green straps and two coiled cables sticking out"
gen "hog-full"     "The hedgehog now wears the full kit at once: neon-teal cap with '>_' symbol, glowing mint-green debug glasses, and a developer backpack with cables"
sleep 30
gen "hog-capsule"  "The hedgehog stands inside a compact coder capsule room with a desk, a glowing monitor and shelves behind him, warm mint-green screen light"
gen "hog-loft"     "The hedgehog stands in a cyber loft: panoramic night city window behind him and a server rack with mint-green indicator lights"

echo
echo "жду и скачиваю..."
while IFS=: read -r NAME ID; do
  pixverse task wait "$ID" --type image --json </dev/null >/dev/null 2>&1
  T=$(mktemp -d)
  pixverse asset download "$ID" --type image --dest "$T/" </dev/null >/dev/null 2>&1 || \
  pixverse asset download "$ID" --type image --dest "$T/" </dev/null >/dev/null 2>&1
  F=$(ls "$T"/* 2>/dev/null | head -1)
  if [ -n "$F" ]; then
    mv "$F" "/tmp/$NAME-raw.png"
    ../.venv/bin/python убрать-фон.py "/tmp/$NAME-raw.png" "$OUT/$NAME.png" >/dev/null
    echo "✓ $NAME.png (фон убран)"
  else
    echo "✗ $NAME не скачался"
  fi
  rm -rf "$T"
done < /tmp/скины-задачи.txt

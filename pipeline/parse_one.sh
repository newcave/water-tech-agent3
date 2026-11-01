#!/usr/bin/env bash
# Parse one report with kordoc. Called by run_parse.sh (env: REPO_ROOT, OUT, SOURCE, KD).
#   $1 = repo path of the PDF, e.g. "alio_report/(010) AI기반 ....pdf"
# Writes  $OUT/md/NNN.md            Markdown (headings, tables as HTML; images left as placeholders)
#         $OUT/chunks/NNN.json      RAG chunks with heading breadcrumbs, tables as GFM
# Appends $OUT/run_log.tsv          NNN <tab> md exit <tab> chunks exit <tab> seconds <tab> finished-at
set -u
path="$1"
num=$(printf '%s' "$path" | grep -oP '^alio_report/\(\K\d{3}')
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
pdf="$tmp/$num.pdf"
if [ "$SOURCE" = git ]; then
  git -C "$REPO_ROOT" cat-file blob "HEAD:$path" > "$pdf" 2>/dev/null
else
  cp "$REPO_ROOT/$path" "$pdf"
fi
# Git LFS pointer stub (file not pulled) -> skip, it stays "대기" in the quality report
if head -c 40 "$pdf" | grep -q 'git-lfs'; then
  echo "skip $num (LFS pointer, run: git lfs pull)"; exit 0
fi
start=$(date +%s)
"$KD" "$pdf" --no-images --silent -o "$OUT/md/$num.md" > "$tmp/md.log" 2>&1; rc1=$?
"$KD" "$pdf" --no-images --silent --format chunks --table-format gfm -o "$OUT/chunks/$num.json" > "$tmp/ch.log" 2>&1; rc2=$?
secs=$(( $(date +%s) - start ))
printf '%s\t%s\t%s\t%s\t%s\n' "$num" "$rc1" "$rc2" "$secs" "$(date '+%Y-%m-%d %H:%M')" >> "$OUT/run_log.tsv"
if [ $rc1 -ne 0 ] || [ $rc2 -ne 0 ]; then
  { echo "== $num $(date '+%F %T')"; tail -5 "$tmp/md.log"; tail -5 "$tmp/ch.log"; } >> "$OUT/errors.log"
fi

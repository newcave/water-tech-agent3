#!/usr/bin/env bash
# kordoc batch parse of ALIO reports -> data/parsed/{md,chunks}/NNN.*
#
#   pipeline/run_parse.sh                 # PDFs from alio_report/ on disk (normal checkout, git lfs pull done)
#   SOURCE=git pipeline/run_parse.sh      # PDFs from the git object store (sparse/partial clone, no checkout)
#   JOBS=2 ONLY="010 025" pipeline/run_parse.sh
#
# Already parsed reports (present in run_log.tsv with exit 0/0) are skipped, so the
# script can be re-run after new PDFs are added. LFS pointer stubs are skipped.
set -euo pipefail
cd "$(dirname "$0")/.."
export REPO_ROOT="$PWD"
export OUT="${OUT:-$REPO_ROOT/data/parsed}"
export SOURCE="${SOURCE:-file}"
export KORDOC_VERSION="${KORDOC_VERSION:-4.24.33}"
JOBS="${JOBS:-2}"
mkdir -p "$OUT/md" "$OUT/chunks"
touch "$OUT/run_log.tsv"

# kordoc pinned: local install keeps every run on the same parser version
if [ ! -x "$REPO_ROOT/.kordoc/node_modules/.bin/kordoc" ]; then
  mkdir -p "$REPO_ROOT/.kordoc"
  (cd "$REPO_ROOT/.kordoc" && npm init -y >/dev/null && npm install --no-audit --no-fund "kordoc@$KORDOC_VERSION" >/dev/null)
fi
export KD="$REPO_ROOT/.kordoc/node_modules/.bin/kordoc"

if [ "$SOURCE" = git ]; then
  list=$(git -c core.quotepath=false ls-tree -r --name-only HEAD alio_report | grep -E '\.pdf$')
else
  list=$(printf '%s\n' alio_report/*.pdf)
fi

done_ok=$(awk -F'\t' '$2==0 && $3==0 {print $1}' "$OUT/run_log.tsv" | sort -u)
todo=()
while IFS= read -r p; do
  num=$(printf '%s' "$p" | grep -oP '^alio_report/\(\K\d{3}' || true)
  [ -z "$num" ] && continue
  if [ -n "${ONLY:-}" ] && ! grep -qw "$num" <<<"$ONLY"; then continue; fi
  grep -qx "$num" <<<"$done_ok" && continue
  todo+=("$p")
done <<<"$list"

echo "kordoc $KORDOC_VERSION · source=$SOURCE · to parse: ${#todo[@]} · jobs=$JOBS"
[ ${#todo[@]} -eq 0 ] && exit 0
printf '%s\0' "${todo[@]}" | xargs -0 -P "$JOBS" -n 1 "$REPO_ROOT/pipeline/parse_one.sh"
echo "done: $(wc -l < "$OUT/run_log.tsv") rows in run_log.tsv"

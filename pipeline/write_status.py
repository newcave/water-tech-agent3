"""Write run_info.json and an agent-status file after a parse + quality run.

data/parsed/run_info.json                       kordoc version/options, source commit, counts
data/parsed/agents/alio_kordoc_parser.json      same shape as water-tech-agent data_seed/agents/*.json
                                                (agent, state, summary, counts, last_run, next_run, events)
usage: python pipeline/write_status.py --out data/parsed --source-commit <sha> [--kordoc 4.24.33]
"""
import argparse, csv, json, time
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="data/parsed")
ap.add_argument("--source-commit", required=True)
ap.add_argument("--kordoc", default="4.24.33")
a = ap.parse_args()
out = Path(a.out)

rows = list(csv.DictReader(open(out / "quality.csv", encoding="utf-8-sig")))
status = Counter(r["판정"] for r in rows)
parsed = [r for r in rows if r["판정"] != "대기"]
wr = [float(r["어절성공률"]) for r in parsed if r["어절성공률"]]
words = sum(int(float(r["추출어절"] or 0)) for r in parsed)
secs = sum(int(float(r["변환초"] or 0)) for r in parsed)
now = datetime.now(KST)

counts = {"대상": len(rows), "성공": status.get("성공", 0), "주의": status.get("주의", 0),
          "실패": status.get("실패", 0), "대기": status.get("대기", 0), "추출 어절": words}
info = {
    "kordoc_version": a.kordoc,
    "kordoc_options": {"markdown": "--no-images --silent",
                       "chunks": "--format chunks --table-format gfm --no-images --silent"},
    "reference_text": "poppler pdftotext (PDF text layer)",
    "source_repo": "newcave/water-tech-agent3", "source_dir": "alio_report",
    "source_commit": a.source_commit,
    "checked_at": now.strftime("%Y-%m-%d %H:%M KST"),
    "counts": counts,
    "mean_word_success": round(sum(wr) / len(wr), 4) if wr else None,
    "parse_seconds_total": secs,
}
(out / "run_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")

agent = {
    "agent": "alio_kordoc_parser",
    "state": "idle",
    "summary": f"ALIO 보고서 kordoc 파싱 — {len(parsed)}/{len(rows)}건 변환, 성공 {counts['성공']} · 주의 {counts['주의']} · 실패 {counts['실패']}",
    "counts": counts,
    "last_run": time.time(),
    "next_run": "PDF 추가 시 수동 (pipeline/run_parse.sh)",
    "events": [
        {"ts": time.time(), "msg": f"kordoc {a.kordoc} 변환 {len(parsed)}건 · 평균 어절 성공률 "
                                   f"{info['mean_word_success']:.1%}" if wr else "변환 없음"},
        {"ts": time.time(), "msg": f"대기 {counts['대기']}건 (Git LFS 원본 미수신)"},
    ],
}
(out / "agents").mkdir(exist_ok=True)
(out / "agents" / "alio_kordoc_parser.json").write_text(json.dumps(agent, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(info, ensure_ascii=False))

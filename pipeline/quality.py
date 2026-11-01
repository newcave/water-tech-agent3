"""Per-report parsing quality check for kordoc output.

Reference = the PDF's own text layer read by poppler `pdftotext` (no layout).
kordoc output = data/parsed/md/NNN.md.

Metrics per report
  쪽수, 글없는쪽       pdfinfo pages; pages whose text layer has < 30 word characters
                       (scanned/image-only pages -> OCR candidates)
  기준어절, 추출어절   word tokens in reference / kordoc text, split at Hangul|Latin|digit
                       boundaries so both sides tokenise mixed words the same way
  어절성공률           multiset overlap / 기준어절   (recall; 1 - 어절실패율)
  어절정밀도           multiset overlap / 추출어절   (low -> merged or garbled words)
  글자재현율           same overlap on single characters (ignores spacing differences)
  깨진글자             U+FFFD and private-use characters in kordoc output
  메타항목             filled fields out of 7 from metadata.jsonl
  판정                 성공 / 주의 / 실패 (rules in judge())

kordoc removes running headers/footers (page numbers etc.) by default, so a recall of
~97-99% on a clean report is normal; the gap is mostly those repeated lines.

usage: python pipeline/quality.py --md-dir data/parsed/md --meta data/parsed/metadata.jsonl \
         --run-log data/parsed/run_log.tsv --pdf-dir alio_report [--git-repo PATH] --out data/parsed/quality.csv
  PDFs are read from --pdf-dir; if a file is not checked out (sparse/partial clone),
  it is read from --git-repo's object store instead.
"""
import argparse, csv, html, json, re, subprocess, tempfile
from collections import Counter
from pathlib import Path

# split at script boundaries (Hangul | Latin | digits) on both sides: pdftotext breaks
# mixed tokens like "KS를", "3개월" at font changes, kordoc keeps them joined.
WORD = re.compile(r"[가-힣]+|[A-Za-z]+|[0-9]+")
CHAR = re.compile(r"[가-힣A-Za-z0-9]")
META_FIELDS = ["수행연도", "수행조직", "연구책임자_원문", "연구기간", "연구목적", "연구내용", "연구결과"]


def md_to_text(md: str) -> str:
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)          # image refs
    md = re.sub(r"\[(?:image|그림)\]", " ", md)
    md = re.sub(r"<!--.*?-->", " ", md, flags=re.S)
    md = re.sub(r"<[^>]+>", " ", md)                       # html table tags
    md = html.unescape(md).replace("\\", "")
    return md


def title_from_path(p: str) -> str:
    name = Path(p).name
    name = re.sub(r"^\(\d{3}\)\s*(?:__)?", "", name)
    name = re.sub(r"(?:\.pdf)+$", "", name)
    name = re.split(r"_\d{4}\.\d{2}\.\d{2}_", name)[0]
    return re.sub(r"\s*\(alio\)\s*$", "", name).strip()


def pdf_sources(pdf_dir: Path, git_repo: Path | None):
    """Map report number -> (kind, path) for every PDF under alio_report."""
    found = {}
    if git_repo:
        out = subprocess.run(["git", "-C", str(git_repo), "-c", "core.quotepath=false", "ls-tree", "-r",
                              "--name-only", "HEAD", "alio_report"], capture_output=True, text=True).stdout
        for p in out.splitlines():
            m = re.match(r"alio_report/\((\d{3})\)", p)
            if m and p.endswith(".pdf"):
                found[int(m.group(1))] = ("git", p)
    for p in pdf_dir.glob("(*).pdf") if pdf_dir.exists() else []:
        m = re.match(r"\((\d{3})\)", p.name)
        if m and p.stat().st_size > 1024:
            found[int(m.group(1))] = ("file", str(p))
    return found


def reference_text(src, git_repo, tmpdir):
    kind, p = src
    if kind == "git":
        pdf = Path(tmpdir) / "ref.pdf"
        with pdf.open("wb") as f:
            subprocess.run(["git", "-C", str(git_repo), "cat-file", "blob", f"HEAD:{p}"], stdout=f, check=True)
    else:
        pdf = Path(p)
    head = pdf.read_bytes()[:200]
    if head.startswith(b"version https://git-lfs"):
        return None, None
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    pages = int(re.search(r"Pages:\s+(\d+)", info).group(1)) if "Pages:" in info else None
    txt = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True).stdout.decode("utf-8", "replace")
    return txt, pages


THRESHOLDS = {
    "인코딩_이상문자": 0.30,  # (라틴확장+한자) / (한글+라틴확장+한자) 초과 -> 글꼴 인코딩 깨짐
    "인코딩_한글": 0.05,      # 한글 / (한글+영문) 미만 -> 한글 보고서인데 한글이 거의 없음
    "글자_실패": 0.60,
    "어절_주의": 0.85, "글자_주의": 0.90, "글없는쪽_주의": 0.10, "기호_주의": 0.01,
}


def judge(r):
    """파싱 판정(성공 / 주의 / 실패). 메타데이터 추출은 별도 열(메타상태)로 본다.

    실패 = kordoc 결과를 그대로 쓸 수 없는 경우만: 변환 오류, 글꼴 인코딩 깨짐, 글자 대량 손실.
    pdftotext 기준은 잡음이 크다(반복 머리글 중복, 자간 벌린 영문을 글자 단위로 쪼갬,
    그래프 축 글자, kordoc 이 LaTeX 로 바꾼 수식). 그래서 어절 성공률은 '주의' 신호로만 쓴다.
    """
    t = THRESHOLDS
    if r["kordoc_종료코드"] != 0:
        return "실패", "kordoc 변환 오류"
    if r["이상문자비율"] > t["인코딩_이상문자"] or r["한글비율"] < t["인코딩_한글"]:
        return "실패", "글꼴 인코딩 깨짐 — 텍스트층을 읽을 수 없음, OCR 필요 (kordoc --ocr-force)"
    if r["어절성공률"] is None:
        return "실패", "기준 텍스트 없음"
    if r["글자재현율"] < t["글자_실패"]:
        return "실패", f"글자재현율 {r['글자재현율']:.1%}"
    reasons = []
    if r["어절성공률"] < t["어절_주의"]:
        reasons.append(f"어절성공률 {r['어절성공률']:.1%}")
    if r["글자재현율"] < t["글자_주의"]:
        reasons.append(f"글자재현율 {r['글자재현율']:.1%}")
    if r["쪽수"] and r["글없는쪽"] / r["쪽수"] > t["글없는쪽_주의"]:
        reasons.append(f"글 없는 쪽 {r['글없는쪽']}쪽(OCR 후보)")
    if r["깨진글자"] > t["기호_주의"] * max(r["추출글자"], 1):
        reasons.append(f"사용자정의 기호 {r['깨진글자']}자")
    return ("주의" if reasons else "성공"), "; ".join(reasons)


def script_mix(text):
    h = len(re.findall(r"[가-힣]", text))
    a = len(re.findall(r"[A-Za-z]", text))
    odd = len(re.findall(r"[À-ɏ㐀-䶿一-鿿]", text))
    return round(h / max(h + a, 1), 4), round(odd / max(h + odd, 1), 4)


def meta_state(n):
    return "완전" if n == 7 else ("없음" if n == 0 else f"부분 {n}/7")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md-dir", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--run-log", required=True)
    ap.add_argument("--pdf-dir", default="alio_report")
    ap.add_argument("--git-repo")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    md_dir, git_repo = Path(a.md_dir), (Path(a.git_repo) if a.git_repo else None)
    meta = {}
    if Path(a.meta).exists():
        for line in open(a.meta, encoding="utf-8"):
            d = json.loads(line); meta[d["번호"]] = d
    runlog = {}
    for line in open(a.run_log, encoding="utf-8"):
        num, rc1, rc2, secs = line.rstrip("\n").split("\t")[:4]
        runlog[int(num)] = (int(rc1), int(rc2), int(secs))
    sources = pdf_sources(Path(a.pdf_dir), git_repo)

    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for num in sorted(set(sources) | set(runlog)):
            rc1, rc2, secs = runlog.get(num, (None, None, None))
            r = {"번호": num, "보고서제목": title_from_path(sources[num][1]) if num in sources else "",
                 "kordoc_종료코드": (rc1 or 0) + (rc2 or 0) if rc1 is not None else -1,
                 "변환초": secs}
            m = meta.get(num, {})
            r["수행조직"] = m.get("수행조직", "")
            r["소속구분"] = m.get("소속구분", "")
            r["수행연도"] = m.get("수행연도", "")
            r["메타항목"] = sum(1 for k in META_FIELDS if m.get(k))
            mdp = md_dir / f"{num:03d}.md"
            # only read the reference PDF for reports that were parsed (skips LFS stubs / pending ones)
            ref, pages = (reference_text(sources[num], git_repo, tmp)
                          if num in sources and mdp.exists() else (None, None))
            out = md_to_text(mdp.read_text(encoding="utf-8")) if mdp.exists() else ""
            if ref is None or not mdp.exists():
                r.update({"쪽수": pages, "글없는쪽": None, "기준어절": None, "추출어절": len(WORD.findall(out)),
                          "어절성공률": None, "어절정밀도": None, "글자재현율": None, "추출글자": len(CHAR.findall(out)),
                          "깨진글자": len(re.findall(r"[�-]", out))})
                if r["kordoc_종료코드"] == -1:
                    r["kordoc_종료코드"] = 0 if mdp.exists() else -1
            else:
                page_txt = ref.split("\f")
                empty = sum(1 for t in page_txt[:pages or len(page_txt)] if len(CHAR.findall(t)) < 30)
                rw, ow = Counter(WORD.findall(ref)), Counter(WORD.findall(out))
                rc, oc = Counter(CHAR.findall(ref)), Counter(CHAR.findall(out))
                ov_w, ov_c = sum((rw & ow).values()), sum((rc & oc).values())
                nrw, now, nrc = sum(rw.values()), sum(ow.values()), sum(rc.values())
                r.update({"쪽수": pages, "글없는쪽": empty, "기준어절": nrw, "추출어절": now,
                          "어절성공률": round(ov_w / nrw, 4) if nrw else None,
                          "어절정밀도": round(ov_w / now, 4) if now else None,
                          "글자재현율": round(ov_c / nrc, 4) if nrc else None,
                          "추출글자": sum(oc.values()),
                          "깨진글자": len(re.findall(r"[�-]", out))})
            r["한글비율"], r["이상문자비율"] = script_mix(out)
            r["메타상태"] = meta_state(r["메타항목"]) if mdp.exists() else ""
            if num not in runlog and ref is None:
                r["판정"], r["사유"] = "대기", "LFS 파일 — 원본 미수신, 변환 전"
            else:
                r["판정"], r["사유"] = judge(r)
            rows.append(r)

    cols = ["번호", "보고서제목", "판정", "사유", "어절성공률", "어절정밀도", "글자재현율", "기준어절", "추출어절", "추출글자",
            "깨진글자", "한글비율", "이상문자비율", "쪽수", "글없는쪽", "메타항목", "메타상태", "수행연도", "수행조직",
            "소속구분", "변환초", "kordoc_종료코드"]
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in cols})
    print(f"wrote {a.out}: {len(rows)} rows; " + ", ".join(f"{k} {v}" for k, v in Counter(r['판정'] for r in rows).items()))


if __name__ == "__main__":
    main()

"""Rule-based front-matter extraction from kordoc Markdown of K-water research reports.

Reads <md_dir>/NNN.md, writes one JSON line per report to <out.jsonl>.
No LLM calls: uses the standard 제출문 / 요약문 layout of K-water reports.
"""
import json, re, sys, html
from pathlib import Path

INSTITUTES = {
    "경영연구소": "INST-01", "수자원환경연구소": "INST-02", "상하수도연구소": "INST-03",
    "물인프라안전연구소": "INST-04", "물에너지연구소": "INST-05", "수자원위성연구소": "INST-06",
    "AI연구소": "INST-07",
}

def norm(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    s = s.replace("\\", "")
    return re.sub(r"[ \t　]+", " ", s).strip()

def squash(s):
    return re.sub(r"\s+", "", s)

H1 = re.compile(r"^#\s+(.*)$")

def sections_h1(lines):
    """Split document into top-level (# ) sections: list of (squashed_title, start, end)."""
    idx = [(i, squash(m.group(1))) for i, l in enumerate(lines) if (m := H1.match(l))]
    out = []
    for k, (i, t) in enumerate(idx):
        end = idx[k + 1][0] if k + 1 < len(idx) else len(lines)
        out.append((t, i, end))
    return out

def find_section(secs, *names, lines=None):
    for t, s, e in secs:
        if any(t.startswith(n) for n in names):
            return s, e
    # fallback: the section title came out as a plain line (not a heading).
    # Exact match only, so table-of-contents entries such as "요약문  1" are skipped.
    if lines:
        for i, l in enumerate(lines):
            if not l.startswith("#") and squash(norm(l)) in names:
                nxt = next((k for k in range(i + 1, len(lines)) if H1.match(lines[k])), len(lines))
                return i, nxt
    return None

POSITION = re.compile(r"(연구위원|수석|책임|선임|위촉|위원|처장|부장|팀장|원장|소장|단장|실장|교수|박사|\d급)")

def org_from_lead(lead):
    """'K-water연구원 상하수도연구소 연구위원 이두진' -> 'K-water연구원 상하수도연구소'"""
    m = POSITION.search(lead or "")
    return lead[:m.start()].strip() if m and m.start() > 1 else None

def parse_submission(block):
    text = norm("\n".join(block))
    d = {}
    m = re.search(r"이\s*보고서를\s*(\d{4})\s*년도?\s*(.+?)에서\s*수행한\s*[“\"](.+?)[”\"]", text, re.S)
    if m:
        d["수행연도"] = int(m.group(1))
        d["수행조직"] = re.sub(r"\s+", " ", m.group(2)).strip()
        d["과제명_제출문"] = re.sub(r"\s+", " ", m.group(3)).strip()
    m = re.search(r"(20\d{2})\s*[.\-년]\s*(\d{1,2})", text[m.end():] if m else text)
    if m:
        d["제출연월"] = f"{m.group(1)}.{int(m.group(2)):02d}"
    m = re.search(r"연구\s*책임자\s*[:：]?\s*(.+?)(?:\n|연구\s*수행자|$)", text)
    if m:
        d["연구책임자_원문"] = re.sub(r"\s+", " ", m.group(1)).strip()[:80]
    # rough participant count: lines after 연구수행자 that end with a Korean name (2-4 chars)
    m = re.search(r"연구\s*수행자(.*)", text, re.S)
    if m:
        tail = m.group(1)
        names = re.findall(r"[가-힣]{2,4}\s*$", tail, re.M)
        d["참여인원_추정"] = len(names)
    return d

SUMMARY_KEYS = [("연구제목", "연구제목"), ("연구기간", "연구기간"), ("연구목적", "연구목적"),
                ("연구내용", "연구내용"), ("연구결과", "연구결과"), ("활용", "활용방안")]

def parse_summary(block):
    d = {}
    heads = [(i, squash(re.sub(r"^#+\s*", "", l))) for i, l in enumerate(block) if l.startswith("##")]
    for k, (i, h) in enumerate(heads):
        h2 = re.sub(r"^[\dIVX가-하]+[.)]", "", h)
        for key, field in SUMMARY_KEYS:
            if h2.startswith(key) and field not in d:
                end = heads[k + 1][0] if k + 1 < len(heads) else len(block)
                body = "\n".join(l for l in block[i + 1:end] if l.strip())
                d[field] = norm(body)[:4000]
    return d

def classify(org):
    if not org:
        return None, None
    for name, code in INSTITUTES.items():
        if name in squash(org):
            return code, name
    if "연구원" in org or "연구소" in org:
        return "K-water연구원(기타)", None
    return "본사·지역 부서", None

def extract(md_path):
    lines = md_path.read_text(encoding="utf-8").splitlines()
    secs = sections_h1(lines)
    rec = {"번호": int(md_path.stem), "문서제목": norm(H1.match(lines[0]).group(1)) if lines and H1.match(lines[0]) else None}
    sub = find_section(secs, "제출문", lines=lines)
    if sub:
        rec.update(parse_submission(lines[sub[0] + 1:sub[1]]))
        if not rec.get("수행조직") and rec.get("연구책임자_원문"):
            org = org_from_lead(rec["연구책임자_원문"])
            if org:
                rec["수행조직"] = org
                rec["수행조직_출처"] = "연구책임자"
    summ = find_section(secs, "요약문", "요약", "국문요약", lines=lines)
    if summ:
        block = lines[summ[0] + 1:summ[1]]
        rec.update(parse_summary(block))
        # raw summary text: the input for later LLM research-asset extraction (cheap vs full text)
        rec["요약문_원문"] = norm("\n".join(l for l in block if l.strip()))[:3000]
    code, inst = classify(rec.get("수행조직"))
    rec["소속구분"] = code
    rec["연구소"] = inst
    rec["찾은절"] = {"제출문": bool(sub), "요약문": bool(summ)}
    rec["본문글자수"] = len(re.findall(r"[가-힣A-Za-z0-9]", "\n".join(lines)))
    return rec

if __name__ == "__main__":
    md_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    with out.open("w", encoding="utf-8") as f:
        for p in sorted(md_dir.glob("[0-9][0-9][0-9].md")):
            f.write(json.dumps(extract(p), ensure_ascii=False) + "\n")

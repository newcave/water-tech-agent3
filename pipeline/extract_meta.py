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

MAJOR = re.compile(r"(목차|차례|요약|제\d+장|제\d+편|Ⅰ\.|1\.서론|서론|Summary|SUMMARY|Abstract)")

def extend_to_major(lines, start, cap=400):
    """A section runs to the next *major* top-level heading (목차/요약/제1장 ...), not to any '# ' line:
    kordoc often makes '# 사장 귀하' or a title line into a heading inside 제출문."""
    for k in range(start + 1, min(len(lines), start + cap)):
        m = H1.match(lines[k])
        if m and MAJOR.match(squash(m.group(1))):
            return k
    return min(len(lines), start + cap)

def find_section(secs, *names, lines=None):
    for t, s, e in secs:
        if any(t.startswith(n) for n in names):
            return s, (extend_to_major(lines, s) if lines else e)
    # fallback: the section title came out as a plain line (not a heading).
    # Exact match only, so table-of-contents entries such as "요약문  1" are skipped.
    if lines:
        for i, l in enumerate(lines):
            if squash(norm(re.sub(r"^#+", "", l))) in names and not re.search(r"\d+\s*$", l):
                stop = next((k for k in range(i + 1, min(len(lines), i + 400))
                             if H1.match(lines[k]) and re.match(r"(목차|차례|제1장|제1편|Ⅰ\.|1\.서론)", squash(H1.match(lines[k]).group(1)))),
                            min(len(lines), i + 400))
                return i, stop
    return None

POSITION = re.compile(r"(연구위원|수석|책임|선임|위촉|위원|처장|부장|팀장|원장|소장|단장|실장|교수|박사|\d급)")

def org_from_lead(lead):
    """'K-water연구원 상하수도연구소 연구위원 이두진' -> 'K-water연구원 상하수도연구소'"""
    m = POSITION.search(lead or "")
    return lead[:m.start()].strip() if m and m.start() > 1 else None

def parse_submission(block):
    text = norm("\n".join(block))
    d = {}
    m = re.search(r"이\s*보고서를\s*(?:(\d{4})\s*년도?\s*)?(.+?)(?:에서|에\s*의해|이|가)\s*수행한\s*[“\"「『<](.+?)[”\"」』>]", text, re.S)
    if m:
        if m.group(1):
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

SUMMARY_KEYS = [("연구제목", "연구제목"), ("과제명", "연구제목"), ("용역명", "연구제목"), ("과업명", "연구제목"),
                ("연구기간", "연구기간"), ("과업기간", "연구기간"), ("용역기간", "연구기간"), ("사업기간", "연구기간"),
                ("연구목적", "연구목적"), ("과업목적", "연구목적"), ("목적", "연구목적"),
                ("연구내용", "연구내용"), ("과업내용", "연구내용"), ("주요내용", "연구내용"), ("주요연구내용", "연구내용"),
                ("연구결과", "연구결과"), ("과업결과", "연구결과"), ("주요결과", "연구결과"), ("연구성과", "연구결과"),
                ("활용", "활용방안"), ("기대효과", "활용방안")]
INLINE_KEYS = [("연구제목", r"(?:연구|과업|용역|과제)\s*명\s*[:：]\s*(.+)"),
               ("연구기간", r"(?:연구|과업|용역|사업)\s*기간\s*[:：]\s*(.+)")]

def parse_summary(block):
    d = {}
    numbered = re.compile(r"^\s*(?:#+\s*)?(?:[0-9]{1,2}|[가-하]|[IVX]{1,4})\s*[.)]\s*\S")
    heads = [(i, squash(re.sub(r"^#+\s*", "", l))) for i, l in enumerate(block)
             if l.startswith("##") or (numbered.match(l) and len(squash(l)) <= 20)]
    for k, (i, h) in enumerate(heads):
        h2 = re.sub(r"^[\dIVX가-하]+[.)]", "", h)
        for key, field in SUMMARY_KEYS:
            if h2.startswith(key) and field not in d:
                end = heads[k + 1][0] if k + 1 < len(heads) else len(block)
                body = "\n".join(l for l in block[i + 1:end] if l.strip())
                d[field] = norm(body)[:4000]
    text = "\n".join(norm(l) for l in block)
    for field, pat in INLINE_KEYS:
        if field not in d and (m := re.search(pat, text)):
            d[field] = m.group(1).strip()[:300]
    return d

EXTERNAL = re.compile(r"(대학교|대학|학회|산학협력단|\(재\)|\(사\)|㈜|주식회사|정책[·･‧]?평가연구원|국제도시물정보과학연구원)")

def classify(org):
    """소속구분: INST-0n(현 7개 연구소) | K-water연구원(기타) | 외부기관(용역) | 본사·지역 부서.
    옛 연구소 이름(물정책·물순환·스마트워터·유역물관리 ...)은 'K-water연구원(기타)' 로 두고,
    사용자가 줄 조직 개편 대응표(org_map.csv)로 나중에 다시 매긴다."""
    if not org:
        return None, None
    o = squash(org)
    for name, code in INSTITUTES.items():
        if name in o:
            return code, name
    if "K-water연구원" in o or "kwater연구원" in o.lower() or re.search(r"(연구소|연구센터|센터)$", o) and not EXTERNAL.search(o):
        return "K-water연구원(기타)", None
    if EXTERNAL.search(o):
        return "외부기관(용역)", None
    return "본사·지역 부서", None

def extract(md_path):
    lines = md_path.read_text(encoding="utf-8").splitlines()
    secs = sections_h1(lines)
    rec = {"번호": int(md_path.stem), "문서제목": norm(H1.match(lines[0]).group(1)) if lines and H1.match(lines[0]) else None}
    sub = find_section(secs, "제출문", "제출서", lines=lines)
    if sub:
        rec.update(parse_submission(lines[sub[0] + 1:sub[1]]))
        if not rec.get("수행조직") and rec.get("연구책임자_원문"):
            org = org_from_lead(rec["연구책임자_원문"])
            if org:
                rec["수행조직"] = org
                rec["수행조직_출처"] = "연구책임자"
    summ = find_section(secs, "요약문", "요약서", "요약보고서", "연구요약", "국문요약", "국문초록", "요약", lines=lines)
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

def load_org_map(path):
    """org_names.csv 의 '대응_연구소코드' 열(사용자가 조직 개편 정보로 채움) -> {수행조직 원문: INST-0n}"""
    import csv
    m = {}
    if path.exists():
        for r in csv.DictReader(path.open(encoding="utf-8-sig")):
            code = (r.get("대응_연구소코드(INST-01~07, 빈칸=해당없음)") or "").strip()
            if code:
                m[r["수행조직_원문"].strip()] = code
    return m


if __name__ == "__main__":
    md_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    org_map = load_org_map(out.parent / "org_names.csv")
    code_name = {v: k for k, v in INSTITUTES.items()}
    with out.open("w", encoding="utf-8") as f:
        for p in sorted(md_dir.glob("[0-9][0-9][0-9].md")):
            rec = extract(p)
            org = re.sub(r"\s+", " ", rec.get("수행조직") or "").strip()
            if org in org_map:            # 조직 개편 대응표가 원래 분류보다 우선
                rec["소속구분"], rec["연구소"] = org_map[org], code_name.get(org_map[org])
                rec["소속구분_출처"] = "org_names.csv"
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

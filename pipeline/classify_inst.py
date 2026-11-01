"""Assign each report to a K-water연구원 institute (INST-01..07) with the water-tech-agent scorer.

Same scoring as water-tech-agent's paper labelling (vendor/water_tech_agent/label_review.py Scorer +
label_review_profiles.json): fit = 0.5 * domain affinity + 0.5 * keyword fit; 위성(INST-06)·AI(INST-07) are
'method' institutes that do not own a domain and appear mainly as share candidates.

Differences for reports (no LLM labels) — same profiles, same fit formula and thresholds, report-shaped text:
  * Korean keywords: 제목 hit 3.0 (= title_weight), 요약문 hit >=2 times 1.5 (= ko_weight), once 0.6
    (papers: abstract once x0.4). Summary text = 연구목적 + 연구내용 (else 요약문 원문) first 1,500 chars.
    Long summaries hit generic words (정책·경제·비용) in almost every report, hence the title/once weighting.
  * English keywords: first Latin-script heading (English title), title weight.
  * domain: inferred, not labelled: D(W) = max_i kw_i * affinity_i(W) over topical institutes (max, not sum —
    a sum favours INST-02 which owns four domains). primary = argmax, secondary = >= 0.6 x primary (max 2).
  * share / move suggestions: label_review.Scorer.score rules re-applied to these fits (same thresholds).
연구소_배정 = 수행조직 institute when the 제출문 names one (or org_names.csv maps it), else the predicted one.

in : data/parsed/metadata.jsonl, data/parsed/quality.csv (보고서제목), data/parsed/md
out: data/assets/report_inst.csv
"""
import csv, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "water_tech_agent"))
import label_review as lr  # noqa: E402  (vendored, unmodified)

PROFILES = json.loads((ROOT / "vendor/water_tech_agent/label_review_profiles.json").read_text(encoding="utf-8"))
SC = lr.Scorer(PROFILES)
INSTS = lr.INSTS
METHOD = set(PROFILES.get("method_institutes", []))
AFF = PROFILES["domain_affinity"]
S = PROFILES["scoring"]


def english_title(lines):
    for l in lines[:60]:
        t = re.sub(r"^#+\s*", "", l).strip()
        letters = re.findall(r"[A-Za-z가-힣]", t)
        if len(t) > 20 and letters and sum(c.isascii() for c in letters) / len(letters) > 0.9:
            return t
    return ""


def infer_domain(kws):
    d = {}
    for inst, k in kws.items():
        if inst in METHOD:
            continue
        for w, a in AFF.get(inst, {}).items():
            d[w] = d.get(w, 0.0) + k * a
    if not d or max(d.values()) < 0.15:
        return "", []
    order = sorted(d, key=lambda w: -d[w])
    top = d[order[0]]
    return order[0], [w for w in order[1:3] if d[w] >= 0.6 * top]


def kw_report(inst, title_ko, summary, en_title):
    w, hits = 0.0, []
    for t in SC.ko.get(inst, []):
        if t in title_ko:
            w += S.get("title_weight", 3.0); hits.append(t)
        else:
            n = summary.count(t)
            if n:
                w += S.get("ko_weight", 1.5) * (1.0 if n >= 2 else 0.4); hits.append(t)
    for name, rx, lit in SC.en.get(inst, []):
        if en_title and lit in en_title and lr._count(rx, en_title, first=True):
            w += S.get("title_weight", 3.0); hits.append(name)
    return 1 - __import__("math").exp(-w / S.get("kw_scale", 3.0)), hits


def infer_domain(kws):
    d = {}
    for inst, k in kws.items():
        if inst in METHOD:
            continue
        for w, a in AFF.get(inst, {}).items():
            d[w] = max(d.get(w, 0.0), k * a)
    if not d or max(d.values()) < 0.15:
        return "", []
    order = sorted(d, key=lambda w: -d[w])
    return order[0], [w for w in order[1:3] if d[w] >= 0.6 * d[order[0]]]


def suggestions(home, fits, kws):
    """label_review.Scorer.score: move / also rules on report fits."""
    h = fits[home]
    topical = [i for i in INSTS if i != home and i not in METHOD]
    bo_i = max(topical, key=lambda i: fits[i]) if topical else None
    bo = fits[bo_i] if bo_i else 0.0
    cands = []
    if bo >= S.get("move_min", .45) and bo - h >= S.get("move_margin", .10) and kws[bo_i] >= S.get("move_kw_min", .4):
        cands.append((bo, bo_i))
    for m in METHOD:
        if m != home and kws[m] >= S.get("method_move_kw", .7) and kws[m] - h >= S.get("method_move_margin", .15):
            cands.append((kws[m], m))
    to = max(cands)[1] if cands else None
    also = sorted([i for i in INSTS if i not in (home, to) and (
        (i in METHOD and kws[i] >= S.get("share_min", .6)) or
        (i not in METHOD and fits[i] >= S.get("share_min", .6) and fits[i] >= h - 0.1))], key=lambda i: -fits[i])
    return to, also


def classify(num, title, meta, md_lines):
    body = " ".join(x for x in (meta.get("연구목적"), meta.get("연구내용")) if x) or meta.get("요약문_원문") \
        or " ".join(l for l in md_lines[:400] if not l.startswith("<"))
    summary = body[:1500]
    en = english_title(md_lines).lower()
    kh = {i: kw_report(i, title, summary, en) for i in INSTS}
    kws = {i: v[0] for i, v in kh.items()}
    prim, sec = infer_domain(kws)
    fits = {}
    for i in INSTS:
        d = SC.dom(i, prim, sec)
        f = S.get("w_domain", .5) * d + S.get("w_keyword", .5) * kws[i]
        fits[i] = max(kws[i], f) if i in METHOD else f
    topical = [i for i in INSTS if i not in METHOD]
    pred = max(topical, key=lambda i: fits[i])
    for m in METHOD:   # method institute is home only when the method clearly dominates (same rule as 'move')
        if kws[m] >= S.get("method_move_kw", .7) and kws[m] - fits[pred] >= S.get("method_move_margin", .15):
            pred = m
    ranked = sorted(INSTS, key=lambda i: -fits[i])
    return pred, fits, kws, prim, sec, ranked, {i: v[1] for i, v in kh.items()}


def main():
    meta = {json.loads(l)["번호"]: json.loads(l) for l in open(ROOT / "data/parsed/metadata.jsonl", encoding="utf-8")}
    titles = {int(r["번호"]): r["보고서제목"] for r in csv.DictReader(open(ROOT / "data/parsed/quality.csv", encoding="utf-8-sig"))}
    out, agree, labelled = [], 0, 0
    for num in sorted(titles):
        mdp = ROOT / f"data/parsed/md/{num:03d}.md"
        m = meta.get(num, {})
        lines = mdp.read_text(encoding="utf-8").splitlines() if mdp.exists() else []
        if not lines:
            out.append({"번호": num, "보고서제목": titles[num], "연구소_배정": "", "배정근거": "미변환"}); continue
        pred, fits, kws, prim, sec, ranked, hits = classify(num, titles[num], m, lines)
        org_inst = m.get("소속구분") if str(m.get("소속구분") or "").startswith("INST-") else None
        if org_inst:
            home, why = org_inst, "수행조직"
            labelled += 1; agree += (pred == org_inst)
        elif fits[pred] >= S.get("ng_home_max", .30):
            home, why = pred, "키워드추정"
        else:
            home, why = "", "미정(적합도 낮음)"
        to, also = suggestions(home or pred, fits, kws)
        out.append({
            "번호": num, "보고서제목": titles[num], "수행조직": m.get("수행조직", ""), "소속구분": m.get("소속구분") or "",
            "연구소_배정": home, "배정근거": why,
            "추정_1순위": pred, "추정_적합도": round(fits[pred], 3),
            "추정_2순위": next(i for i in ranked if i != pred), "추정_2순위_적합도": round(fits[next(i for i in ranked if i != pred)], 3),
            "분야": "+".join(x for x in [prim, *sec] if x), "분야명": " / ".join(lr.DOMAIN_NAME.get(x, x) for x in [prim, *sec] if x),
            "공유후보": " ".join(also), "이관제안": to or "",
            "맞은키워드": " ".join(hits[home or pred][:8]),
            "공유후보_키워드": " | ".join(f"{i}:{' '.join(hits[i][:4])}" for i in also),
            **{f"fit_{i}": round(fits[i], 3) for i in INSTS},
        })
    dst = ROOT / "data/assets/report_inst.csv"
    dst.parent.mkdir(parents=True, exist_ok=True)
    cols = list(out[next(i for i, r in enumerate(out) if "fit_INST-01" in r)].keys())
    with open(dst, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(out)
    from collections import Counter
    print(f"wrote {dst}: {len(out)} rows | 배정 {dict(Counter(r['연구소_배정'] or '-' for r in out))}")
    print(f"근거 {dict(Counter(r['배정근거'] for r in out))}")
    if labelled:
        print(f"수행조직이 연구소를 밝힌 {labelled}건에서 추정 1순위 일치 {agree}건 ({agree / labelled:.0%})")


if __name__ == "__main__":
    main()

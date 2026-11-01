"""Report x research-asset map and cross-institute sharing (rule-based, no LLM).

in : data/parsed/md/NNN.md, data/assets/asset_gazetteer.json, data/assets/report_inst.csv (연구소_배정, 기계)
     + data/assets/inst_overrides.csv (사람 판정, 있으면 우선)
out: data/assets/report_assets.csv     번호, asset_id, kind, name, 언급수
     data/assets/shared_assets.json    water-tech-agent shared_datasources.json shape + kind/docs/main_inst/provider:
                                       {cid, name, kind, avail, n_docs, n_inst, institutes, main_inst, provider, docs}
                                       provider = method institute (INST-06 위성 / INST-07 AI) that can supply the asset
     data/assets/edges.json            [{src, dst, w}]  w = number of assets used by both institutes
A report "uses" an asset when any alias appears >= MIN_MENTIONS times in its full text.
"""
import csv, json, re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent))  # noqa: E702
MD, ASSETS = ROOT / "data/parsed/md", ROOT / "data/assets"
MIN_MENTIONS = 2          # one stray mention (e.g. a reference list) is not use
LATIN = re.compile(r"[A-Za-z]")


def alias_regex(a):
    if LATIN.search(a):   # whole-token, case-sensitive: "AWS" must not hit "laws", "GRU" not "GROUP"
        return re.compile(r"(?<![A-Za-z0-9])" + re.escape(a) + r"(?![A-Za-z0-9])")
    return re.compile(re.escape(a))


def plain(md):
    md = re.sub(r"<[^>]+>", " ", md)
    return re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)


def main():
    gaz = json.loads((ASSETS / "asset_gazetteer.json").read_text(encoding="utf-8"))["assets"]
    rx = {g["id"]: [alias_regex(a) for a in g["aliases"]] for g in gaz}
    info = {g["id"]: g for g in gaz}
    import pandas as pd
    import inst_overrides                     # 사람 판정(data/assets/inst_overrides.csv)이 기계 배정보다 우선
    ri = inst_overrides.apply(pd.read_csv(ASSETS / "report_inst.csv", encoding="utf-8-sig", dtype={"연구소_배정": str}),
                              inst_overrides.read_local(ROOT))
    inst = {int(r["번호"]): (r["연구소_배정"] if isinstance(r["연구소_배정"], str) else "") for _, r in ri.iterrows()}

    rows, uses = [], defaultdict(list)          # uses[asset] = [(num, inst)]
    for p in sorted(MD.glob("[0-9][0-9][0-9].md")):
        num, text = int(p.stem), plain(p.read_text(encoding="utf-8"))
        for aid, rs in rx.items():
            n = sum(len(r.findall(text)) for r in rs)
            if n >= MIN_MENTIONS:
                g = info[aid]
                rows.append({"번호": num, "asset_id": aid, "kind": g["kind"], "name": g["name"], "언급수": n})
                uses[aid].append((num, inst.get(num, "")))
    with open(ASSETS / "report_assets.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["번호", "asset_id", "kind", "name", "언급수"]); w.writeheader(); w.writerows(rows)

    shared, inst_assets = [], defaultdict(set)
    for aid, lst in uses.items():
        g = info[aid]
        insts = Counter(i for _, i in lst if i.startswith("INST-"))
        for i in insts:
            inst_assets[i].add(aid)
        shared.append({"cid": aid, "name": g["name"], "kind": g["kind"], "avail": g["avail"],
                       "n_docs": len(lst), "n_inst": len(insts), "institutes": sorted(insts),
                       "main_inst": insts.most_common(1)[0][0] if insts else None, "provider": g.get("provider"),
                       "inst_docs": dict(sorted(insts.items())), "docs": sorted(n for n, _ in lst)})
    shared.sort(key=lambda x: (-x["n_inst"], -x["n_docs"]))
    (ASSETS / "shared_assets.json").write_text(json.dumps(shared, ensure_ascii=False, indent=1), encoding="utf-8")

    codes = sorted(inst_assets)
    edges = []
    for a in range(len(codes)):
        for b in range(a + 1, len(codes)):
            w = len(inst_assets[codes[a]] & inst_assets[codes[b]])
            if w:
                edges.append({"src": codes[a], "dst": codes[b], "w": w})
    edges.sort(key=lambda e: -e["w"])
    (ASSETS / "edges.json").write_text(json.dumps(edges, ensure_ascii=False, indent=1), encoding="utf-8")
    k = Counter(r["kind"] for r in rows)
    print(f"report-asset links {len(rows)} ({dict(k)}), assets used {len(shared)}, "
          f"shared by >=2 institutes {sum(1 for s in shared if s['n_inst'] >= 2)}, edges {len(edges)}")


if __name__ == "__main__":
    main()

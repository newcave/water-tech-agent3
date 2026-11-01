"""ALIO 보고서 파싱 관제 — water-tech-agent3

Reads the outputs of pipeline/ (kordoc parse + quality check) from data/parsed/:
  quality.csv      one row per report: 판정, 어절성공률, 글자재현율, 쪽수, 글없는쪽, 메타항목 ...
  metadata.jsonl   제출문·요약문 fields per report
  run_log.tsv      kordoc exit codes and seconds per report
  run_info.json    kordoc version / options / source commit of the last run
Run locally:  streamlit run app.py
"""
import json
from pathlib import Path

import pandas as pd
import altair as alt
import streamlit as st

DATA = Path(__file__).parent / "data" / "parsed"
STATUS_ORDER = ["성공", "주의", "실패", "대기"]
STATUS_COLOR = {"성공": "#2BB673", "주의": "#F2A93B", "실패": "#E5484D", "대기": "#7A8699"}

st.set_page_config(page_title="ALIO 파싱 관제", page_icon="📄", layout="wide")


@st.cache_data(ttl=300)
def load():
    q = pd.read_csv(DATA / "quality.csv", encoding="utf-8-sig")
    meta = {}
    mp = DATA / "metadata.jsonl"
    if mp.exists():
        for line in mp.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            meta[d["번호"]] = d
    info = json.loads((DATA / "run_info.json").read_text(encoding="utf-8")) if (DATA / "run_info.json").exists() else {}
    return q, meta, info


if not (DATA / "quality.csv").exists():
    st.error("data/parsed/quality.csv 가 없습니다. pipeline/README 순서대로 파싱과 품질 점검을 먼저 실행하세요.")
    st.stop()

q, meta, info = load()
q["어절실패율"] = 1 - q["어절성공률"]
q["판정"] = pd.Categorical(q["판정"], STATUS_ORDER, ordered=True)

ASSETS = Path(__file__).parent / "data" / "assets"
INST_NAME = {"INST-01": "경영연구소", "INST-02": "수자원환경연구소", "INST-03": "상하수도연구소",
             "INST-04": "물인프라안전연구소", "INST-05": "물에너지연구소", "INST-06": "수자원위성연구소",
             "INST-07": "AI연구소"}
KIND_KO = {"data": "데이터", "model": "모델", "method": "방법"}
page = st.sidebar.radio("화면", ["파싱 관제", "연구소 협업 지도"], index=0)


def inst_label(c):
    return f"{c} {INST_NAME.get(c, '')}".strip() if isinstance(c, str) and c and c != "미정" else "미정"


@st.cache_data(ttl=300)
def load_assets():
    ri = pd.read_csv(ASSETS / "report_inst.csv", encoding="utf-8-sig")
    shared = json.loads((ASSETS / "shared_assets.json").read_text(encoding="utf-8"))
    edges = json.loads((ASSETS / "edges.json").read_text(encoding="utf-8"))
    return ri, shared, edges


if page == "연구소 협업 지도":
    if not (ASSETS / "report_inst.csv").exists():
        st.error("data/assets 가 없습니다. pipeline/classify_inst.py → asset_map.py 를 먼저 실행하세요.")
        st.stop()
    ri, shared, edges = load_assets()
    st.title("연구소 협업 지도")
    st.caption("연구소 배정은 water-tech-agent 연구소 라벨 점수(vendor/water_tech_agent, 키워드·분야 친화도)와 같은 기준 · "
               "데이터·모델·방법은 자산 사전(data/assets/asset_gazetteer.json)으로 보고서 전문에서 찾음(2회 이상 언급) · LLM 없음")
    lab = ri[ri["배정근거"] == "수행조직"]
    agree = (lab["추정_1순위"] == lab["연구소_배정"]).mean() if len(lab) else float("nan")
    multi = [s for s in shared if s["n_inst"] >= 2]
    c = st.columns(5)
    c[0].metric("연구소 배정", f"{int(ri['연구소_배정'].notna().sum())}건",
                help="수행조직이 연구소를 밝힌 보고서는 그 연구소, 나머지는 키워드 적합도 1순위")
    c[1].metric("수행조직 기준", f"{len(lab)}건")
    c[2].metric("키워드 추정 일치율", f"{agree:.0%}", help="수행조직이 연구소를 밝힌 보고서에서 키워드 추정 1순위가 맞은 비율")
    c[3].metric("찾은 자산", f"{len(shared)}종", help="보고서 2회 이상 언급된 데이터·모델·방법")
    c[4].metric("2개 이상 연구소가 쓰는 자산", f"{len(multi)}종")

    st.subheader("연구소별 보고서")
    by = ri.assign(연구소=ri["연구소_배정"].map(inst_label)).groupby(["연구소", "배정근거"]).size().reset_index(name="건수")
    st.altair_chart(alt.Chart(by).mark_bar().encode(
        y=alt.Y("연구소:N", title=None, sort="-x", axis=alt.Axis(labelLimit=240, labelOverlap=False)),
        x=alt.X("sum(건수):Q", title="보고서 수"),
        color=alt.Color("배정근거:N", legend=alt.Legend(orient="top", title=None),
                        scale=alt.Scale(domain=["수행조직", "키워드추정", "미정(적합도 낮음)", "미변환"],
                                        range=["#22C3E6", "#4F7DF3", "#8A94A6", "#4A5263"])),
        tooltip=["연구소:N", "배정근거:N", "건수:Q"]).properties(height=34 * by["연구소"].nunique()),
        use_container_width=True)

    st.subheader("연구소 사이 공유 자산 수")
    if edges:
        e = pd.DataFrame(edges)
        e = pd.concat([e, e.rename(columns={"src": "dst", "dst": "src"})])
        e["a"], e["b"] = e["src"].map(inst_label), e["dst"].map(inst_label)
        base = alt.Chart(e).encode(x=alt.X("a:N", title=None, axis=alt.Axis(labelAngle=-30, labelLimit=160, labelOverlap=False)),
                                   y=alt.Y("b:N", title=None, axis=alt.Axis(labelLimit=160, labelOverlap=False)))
        st.altair_chart((base.mark_rect().encode(color=alt.Color("w:Q", title="공유 자산", scale=alt.Scale(scheme="teals")),
                                                 tooltip=["a:N", "b:N", alt.Tooltip("w:Q", title="공유 자산 수")])
                         + base.mark_text(fontSize=12).encode(text="w:Q")).properties(height=320),
                        use_container_width=True)
        st.caption("칸 숫자 = 두 연구소 보고서가 함께 쓰는 데이터·모델·방법 종류 수 (water-tech-agent edges.json 과 같은 꼴)")

    st.subheader("같이 쓰는 자산 — 공동관리·협업 후보")
    sd = pd.DataFrame(multi)
    if len(sd):
        sd["종류"] = sd["kind"].map(KIND_KO)
        sd["연구소별 보고서"] = sd["inst_docs"].apply(lambda d: " · ".join(f"{INST_NAME.get(k, k)[:-3] or k} {v}" for k, v in d.items()))
        sd["주 사용"] = sd["main_inst"].map(inst_label)
        sd["공급 가능"] = sd["provider"].map(lambda x: inst_label(x) if isinstance(x, str) else "")
        kpick = st.multiselect("종류", list(KIND_KO.values()), default=list(KIND_KO.values()))
        st.dataframe(sd[sd["종류"].isin(kpick)][["종류", "name", "avail", "n_docs", "n_inst", "연구소별 보고서", "주 사용", "공급 가능"]]
                     .rename(columns={"name": "자산", "avail": "접근성", "n_docs": "보고서", "n_inst": "연구소"}),
                     hide_index=True, use_container_width=True, height=380)
        st.caption("접근성 internal_only = K-water 내부 자료 → 여러 연구소가 쓰면 공동관리 1순위")

    st.subheader("넘길 수 있는 자산 — 수단 연구소(위성·AI)가 공급·지원할 후보")
    pv = pd.DataFrame([s for s in shared if s.get("provider")])
    if len(pv):
        pv["공급 연구소"] = pv["provider"].map(inst_label)
        pv["쓰는 연구소"] = pv["institutes"].apply(lambda L: ", ".join(INST_NAME.get(i, i) for i in L if i != None))
        st.dataframe(pv[["공급 연구소", "name", "n_docs", "쓰는 연구소"]].rename(columns={"name": "자산", "n_docs": "보고서"})
                     .sort_values(["공급 연구소", "보고서"], ascending=[True, False]), hide_index=True, use_container_width=True)
    sc = ri[ri["공유후보"].fillna("") != ""]
    st.caption(f"보고서 단위 공유 후보(연구소 라벨 점수의 share 규칙): {len(sc)}건 — 아래 표의 '공유후보' 열")

    st.subheader("보고서별 연구소 배정")
    f1, f2 = st.columns(2)
    ipick = f1.multiselect("연구소", sorted(ri["연구소_배정"].dropna().unique()), format_func=inst_label, placeholder="전체")
    wpick = f2.multiselect("배정 근거", sorted(ri["배정근거"].dropna().unique()), placeholder="전체")
    v = ri.copy()
    v["연구소_배정"] = v["연구소_배정"].fillna("미정")
    if ipick:
        v = v[v["연구소_배정"].isin(ipick)]
    if wpick:
        v = v[v["배정근거"].isin(wpick)]
    st.dataframe(v[["번호", "보고서제목", "연구소_배정", "배정근거", "추정_1순위", "추정_적합도", "분야명", "공유후보", "이관제안",
                    "맞은키워드", "수행조직"]], hide_index=True, use_container_width=True, height=420,
                 column_config={"번호": st.column_config.NumberColumn(format="%03d", width="small"),
                                "보고서제목": st.column_config.TextColumn(width="large"),
                                "추정_적합도": st.column_config.NumberColumn(format="%.2f")})
    st.stop()

# ---------------- header
st.title("ALIO 보고서 파싱 관제")
st.caption(
    f"kordoc {info.get('kordoc_version', '?')} · 원본 커밋 {info.get('source_commit', '?')} · "
    f"마지막 점검 {info.get('checked_at', '?')} · 기준 텍스트: PDF 텍스트층(pdftotext)"
)

counts = q["판정"].value_counts().reindex(STATUS_ORDER, fill_value=0)
done = q[q["판정"] != "대기"]
c = st.columns(6)
c[0].metric("대상 보고서", f"{len(q)}건")
c[1].metric("성공", f"{counts['성공']}건")
c[2].metric("주의", f"{counts['주의']}건")
c[3].metric("실패", f"{counts['실패']}건")
c[4].metric("대기 (LFS)", f"{counts['대기']}건")
c[5].metric("평균 어절 성공률", f"{done['어절성공률'].mean():.1%}" if len(done) else "-",
            help="PDF 텍스트층 어절 중 kordoc 결과에서 다시 찾은 비율(다중집합 겹침). 실패율 = 1 - 성공률")

c = st.columns(4)
c[0].metric("추출 어절 합계", f"{int(done['추출어절'].sum()):,}")
c[1].metric("평균 글자 재현율", f"{done['글자재현율'].mean():.1%}" if len(done) else "-",
            help="띄어쓰기 차이를 뺀 글자 단위 재현율")
c[2].metric("OCR 후보 쪽", f"{int(done['글없는쪽'].sum()):,}쪽",
            help="텍스트층 글자가 30자 미만인 쪽 — 스캔·그림 쪽. kordoc --ocr 로 다시 읽을 대상")
c[3].metric("메타 7항목 모두 추출", f"{int((done['메타항목'] == 7).sum())}건",
            help="제출문·요약문 규칙 추출(파싱 판정과 별개). 없음/부분은 LLM 단계나 수작업 보완 대상")

st.caption("판정은 kordoc 파싱 품질만 봅니다. 실패 = 변환 오류 · 글꼴 인코딩 깨짐(OCR 필요) · 글자 재현율 60% 미만. "
           "주의 = 어절 성공률 85% 미만 · 글자 재현율 90% 미만 · 글 없는 쪽 10% 초과 · 사용자정의 기호 1% 초과. "
           "기준 텍스트(pdftotext)는 반복 머리글·자간 벌린 영문·그래프 축 글자·수식 때문에 실제보다 어절이 많게 잡혀, "
           "깨끗한 보고서도 어절 성공률이 90%대 초반으로 나올 수 있습니다.")

# ---------------- per-report chart
st.subheader("보고서별 어절 성공률")
status_scale = alt.Scale(domain=STATUS_ORDER, range=[STATUS_COLOR[s] for s in STATUS_ORDER])
y_min = max(0.0, min(0.8, (done["어절성공률"].min() if len(done) else 0.8) - 0.02))
bars = (
    alt.Chart(done.assign(판정=done["판정"].astype(str), 사유=done["사유"].fillna("")))
    .mark_bar(size=5, clip=True)
    .encode(
        x=alt.X("번호:Q", title="보고서 번호", scale=alt.Scale(domain=[0, int(q["번호"].max()) + 1], nice=False)),
        y=alt.Y("어절성공률:Q", title="어절 성공률", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[y_min, 1.0])),
        color=alt.Color("판정:N", scale=status_scale, legend=alt.Legend(orient="top", title=None)),
        tooltip=[alt.Tooltip("번호:Q", format="03d"), "보고서제목:N", alt.Tooltip("어절성공률:Q", format=".1%"),
                 alt.Tooltip("글자재현율:Q", format=".1%"), "판정:N", "사유:N"],
    )
)
rule = alt.Chart(pd.DataFrame({"y": [0.85]})).mark_rule(strokeDash=[4, 4], color="#8A94A6").encode(y="y:Q")
st.altair_chart((bars + rule).properties(height=320), use_container_width=True)
st.caption("점선 = 주의선 85%")

# ---------------- by organisation type
st.subheader("소속 구분별 보고서와 판정")
org = (q.assign(소속구분=q["소속구분"].fillna("미확인(제출문 없음)"), 판정=q["판정"].astype(str))
       .groupby(["소속구분", "판정"]).size().reset_index(name="건수"))
org_chart = (
    alt.Chart(org)
    .mark_bar()
    .encode(
        y=alt.Y("소속구분:N", title=None, sort="-x", axis=alt.Axis(labelLimit=240, labelOverlap=False)),
        x=alt.X("sum(건수):Q", title="보고서 수"),
        color=alt.Color("판정:N", scale=status_scale, legend=alt.Legend(orient="top", title=None)),
        order=alt.Order("판정:N"),
        tooltip=["소속구분:N", "판정:N", "건수:Q"],
    )
    .properties(height=34 * org["소속구분"].nunique())
)
st.altair_chart(org_chart, use_container_width=True)
st.caption("수행조직은 제출문 원문 그대로입니다. 옛 연구소 이름(물정책·물순환·스마트워터·유역물관리 등)은 'K-water연구원(기타)'로 두었고, "
           "조직 개편 대응표를 받으면 data/parsed/org_names.csv 의 대응 연구소 열로 다시 매깁니다.")

# ---------------- table
st.subheader("보고서별 상세")
f1, f2, f3 = st.columns([2, 2, 3])
pick = f1.multiselect("판정", STATUS_ORDER, default=["주의", "실패", "대기"], placeholder="전체")
orgs = sorted(x for x in q["소속구분"].dropna().unique())
org_pick = f2.multiselect("소속 구분", orgs, placeholder="전체")
text = f3.text_input("제목·조직 검색")
view = q.copy()
if pick:
    view = view[view["판정"].isin(pick)]
if org_pick:
    view = view[view["소속구분"].isin(org_pick)]
if text:
    view = view[view["보고서제목"].fillna("").str.contains(text) | view["수행조직"].fillna("").str.contains(text)]

st.dataframe(
    view[["번호", "보고서제목", "판정", "사유", "어절성공률", "어절실패율", "글자재현율", "추출어절",
          "쪽수", "글없는쪽", "한글비율", "메타상태", "수행연도", "수행조직", "소속구분", "변환초"]].sort_values("번호"),
    hide_index=True, use_container_width=True, height=420,
    column_config={
        "번호": st.column_config.NumberColumn(format="%03d", width="small"),
        "보고서제목": st.column_config.TextColumn(width="large"),
        "어절성공률": st.column_config.ProgressColumn(format="%.3f", min_value=0.5, max_value=1.0),
        "한글비율": st.column_config.NumberColumn(format="%.2f", help="한글 / (한글+영문). 0에 가까우면 글꼴 인코딩 깨짐 의심"),
        "어절실패율": st.column_config.NumberColumn(format="%.3f"),
        "글자재현율": st.column_config.NumberColumn(format="%.3f"),
        "추출어절": st.column_config.NumberColumn(format="%d"),
        "메타상태": st.column_config.TextColumn(help="제출문·요약문에서 채운 항목: 완전(7/7) · 부분 n/7 · 없음"),
        "수행연도": st.column_config.NumberColumn(format="%d"),
        "변환초": st.column_config.NumberColumn(help="kordoc Markdown + 청크 변환에 걸린 시간"),
    },
)
st.caption(f"{len(view)}건 표시")

# ---------------- one report
st.subheader("보고서 메타데이터 보기")
num = st.selectbox("보고서", q["번호"].tolist(),
                   format_func=lambda n: f"({n:03d}) {q.loc[q['번호'] == n, '보고서제목'].iloc[0]}")
m = meta.get(num)
if not m:
    st.info("이 보고서는 아직 파싱되지 않았습니다.")
else:
    a, b = st.columns([1, 2])
    with a:
        for k in ["수행연도", "수행조직", "소속구분", "연구책임자_원문", "참여인원_추정", "연구기간", "제출연월"]:
            if m.get(k) not in (None, ""):
                st.markdown(f"**{k.replace('_원문', '')}** · {m[k]}")
    with b:
        for k in ["연구목적", "연구내용", "연구결과", "활용방안"]:
            if m.get(k):
                with st.expander(k, expanded=(k == "연구내용")):
                    st.text(m[k])
        if not any(m.get(k) for k in ["연구목적", "연구내용", "연구결과"]) and m.get("요약문_원문"):
            with st.expander("요약문 원문", expanded=True):
                st.text(m["요약문_원문"])

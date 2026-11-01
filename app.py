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
import plotly.graph_objects as go
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
fig = go.Figure()
for s in STATUS_ORDER[:3]:
    d = q[q["판정"] == s]
    fig.add_bar(x=d["번호"], y=d["어절성공률"], name=s, marker_color=STATUS_COLOR[s], width=0.8,
                customdata=d[["보고서제목", "사유"]].fillna(""),
                hovertemplate="(%{x:03d}) %{customdata[0]}<br>어절 성공률 %{y:.1%}<br>%{customdata[1]}<extra></extra>")
for y, label in [(0.85, "주의선 85%")]:
    fig.add_hline(y=y, line_dash="dot", line_color="#8A94A6", annotation_text=label, annotation_position="top right")
fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), barmode="overlay", bargap=0.15,
                  yaxis=dict(tickformat=".0%", range=[max(0.0, min(0.8, (done["어절성공률"].min() or 0.8) - 0.02)), 1.0]),
                  xaxis=dict(title="보고서 번호"), legend=dict(orientation="h", y=1.12))
st.plotly_chart(fig, use_container_width=True)

# ---------------- by organisation type
st.subheader("소속 구분별 보고서와 판정")
org = q.assign(소속구분=q["소속구분"].fillna("미확인(제출문 없음)")).groupby(["소속구분", "판정"], observed=True).size().reset_index(name="건수")
fig2 = go.Figure()
for s in STATUS_ORDER:
    d = org[org["판정"] == s]
    fig2.add_bar(y=d["소속구분"], x=d["건수"], name=s, orientation="h", marker_color=STATUS_COLOR[s])
fig2.update_layout(height=300, barmode="stack", margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.15),
                   yaxis=dict(categoryorder="total ascending"))
st.plotly_chart(fig2, use_container_width=True)
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

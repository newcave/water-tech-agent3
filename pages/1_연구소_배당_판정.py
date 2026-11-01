"""연구소 배당 판정 — 사람이 보고서마다 연구소를 다시 정한다 (기계 배정은 참고로만 보여 줌).

저장: Streamlit Secrets 에 GITHUB_TOKEN 이 있으면 data/assets/inst_overrides.csv 를 main 에 바로 커밋,
없으면 CSV 내려받기(그 파일을 같은 경로에 올리면 된다). 판정은 classify_inst.py·협업 지도가 기계 배정보다 먼저 쓴다.
"""
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import inst_overrides as io_  # noqa: E402

st.set_page_config(page_title="연구소 배당 판정", page_icon="📄", layout="wide")

INST_NAME = {"INST-01": "경영연구소", "INST-02": "수자원환경연구소", "INST-03": "상하수도연구소",
             "INST-04": "물인프라안전연구소", "INST-05": "물에너지연구소", "INST-06": "수자원위성연구소",
             "INST-07": "AI연구소"}
OPTIONS = [""] + [f"{k} {v}" for k, v in INST_NAME.items()] + ["OUT 연구소 밖"]
code = lambda label: (label or "").split(" ")[0]                         # "INST-02 수자원…" -> "INST-02"
label = lambda c: next((o for o in OPTIONS if o.split(" ")[0] == c), "") if c else ""

def secret(key, default=""):
    """Streamlit Cloud 는 최상위 secrets 를 환경변수로도 넘긴다. 로컬에 secrets.toml 이 없으면 st.secrets 를 건드리지 않는다
    (건드리면 'No secrets found' 경고가 화면에 뜬다)."""
    if os.environ.get(key):
        return os.environ[key]
    if any(p.exists() for p in (Path.home() / ".streamlit/secrets.toml", ROOT / ".streamlit/secrets.toml")):
        try:
            return st.secrets.get(key, default)
        except Exception:
            return default
    return default


TOKEN = secret("GITHUB_TOKEN")
PASSCODE = secret("JUDGE_PASSCODE")      # 있으면 이 암호를 넣어야 GitHub 저장 버튼이 켜진다 (공개 앱 링크 대비)
REPO = secret("GITHUB_REPO", "newcave/water-tech-agent3")
BRANCH = secret("GITHUB_BRANCH", "main")

st.title("연구소 배당 판정")
st.caption("기계 배정(water-tech-agent 연구소 라벨 점수)은 참고입니다. 판정 연구소를 고르거나, 맞으면 '맞음'만 체크하세요. "
           "공유 연구소는 INST 코드를 띄어 적습니다(예: INST-06 INST-07). 저장한 판정은 기계 배정보다 우선합니다.")

ri = pd.read_csv(ROOT / "data/assets/report_inst.csv", encoding="utf-8-sig")
if "ov" not in st.session_state:
    if TOKEN:
        try:
            st.session_state.ov, _ = io_.github_get(REPO, BRANCH, TOKEN)
        except Exception as e:
            st.warning(f"GitHub 에서 판정 파일을 읽지 못해 앱에 들어 있는 사본을 씁니다: {e}")
            st.session_state.ov = io_.read_local(ROOT)
    else:
        st.session_state.ov = io_.read_local(ROOT)
ov = st.session_state.ov

j1, j2 = st.columns([3, 2])
judge = j1.text_input("판정자", value=st.session_state.get("judge", ""), placeholder="이름 (저장 기록에 남음)")
st.session_state.judge = judge
unlocked = True
if TOKEN and PASSCODE:
    unlocked = j2.text_input("저장 암호", type="password") == PASSCODE

f1, f2, f3, f4 = st.columns([2, 2, 2, 3])
m_inst = f1.multiselect("기계 배정 연구소", sorted(ri["연구소_배정"].dropna().unique()), placeholder="전체",
                        format_func=lambda c: f"{c} {INST_NAME.get(c, '')}")
why = f2.multiselect("배정 근거", sorted(ri["배정근거"].dropna().unique()), placeholder="전체")
todo_only = f3.checkbox("아직 판정 안 한 것만", value=False)
q = f4.text_input("제목·조직 검색")

base = ri[["번호", "보고서제목", "수행조직", "연구소_배정", "배정근거", "추정_1순위", "추정_적합도", "추정_2순위",
           "추정_2순위_적합도", "분야명", "맞은키워드", "공유후보"]].copy()
o = io_._clean(ov).set_index("번호")
base["판정_연구소"] = base["번호"].map(lambda n: label(o.loc[n, "판정_연구소"]) if n in o.index else "")
base["맞음"] = base["번호"].map(lambda n: bool(o.loc[n, "확인"]) if n in o.index else False)
base["공유_연구소"] = base["번호"].map(lambda n: o.loc[n, "공유_연구소"] if n in o.index else "")
base["메모"] = base["번호"].map(lambda n: o.loc[n, "메모"] if n in o.index else "")
base["기계_배정"] = base["연구소_배정"].map(lambda c: label(c) if isinstance(c, str) else "미정")
base["수행조직"] = base["수행조직"].fillna("")
base["맞은키워드"] = base["맞은키워드"].fillna("")

view = base
if m_inst:
    view = view[view["연구소_배정"].isin(m_inst)]
if why:
    view = view[view["배정근거"].isin(why)]
if todo_only:
    view = view[(view["판정_연구소"] == "") & (~view["맞음"])]
if q:
    view = view[view["보고서제목"].fillna("").str.contains(q) | view["수행조직"].fillna("").str.contains(q)]

done = int(((base["판정_연구소"] != "") | base["맞음"]).sum())
c = st.columns(3)
c[0].metric("판정 완료", f"{done} / {len(base)}건")
c[1].metric("기계 배정과 다르게 판정", f"{int(((base['판정_연구소'] != '') & (base['판정_연구소'].map(code) != base['연구소_배정'].fillna(''))).sum())}건")
c[2].metric("저장 방식", "GitHub 바로 저장" if TOKEN else "CSV 내려받기", help="Streamlit Secrets 에 GITHUB_TOKEN 을 넣으면 바로 저장")

shown = view[["번호", "보고서제목", "기계_배정", "판정_연구소", "맞음", "공유_연구소", "메모",
              "수행조직", "배정근거", "추정_적합도", "추정_2순위", "맞은키워드"]]
edited = st.data_editor(
    shown, hide_index=True, use_container_width=True, height=560,
    key="editor-" + str(abs(hash((tuple(m_inst), tuple(why), todo_only, q)))),   # 필터가 바뀌면 편집칸을 새로 (엉뚱한 행에 붙지 않게)
    disabled=["번호", "보고서제목", "수행조직", "기계_배정", "배정근거", "추정_적합도", "추정_2순위", "맞은키워드"],
    column_config={
        "번호": st.column_config.NumberColumn(format="%03d", width="small"),
        "보고서제목": st.column_config.TextColumn(width="medium"),
        "기계_배정": st.column_config.TextColumn("기계 배정", width="medium"),
        "추정_적합도": st.column_config.NumberColumn("적합도", format="%.2f", width="small"),
        "추정_2순위": st.column_config.TextColumn("2순위", width="small"),
        "판정_연구소": st.column_config.SelectboxColumn("판정 연구소", options=OPTIONS, width="medium"),
        "맞음": st.column_config.CheckboxColumn("맞음", help="기계 배정이 맞으면 체크", width="small"),
        "공유_연구소": st.column_config.TextColumn("공유 연구소", help="예: INST-06 INST-07"),
        "메모": st.column_config.TextColumn("메모"),
    },
)

# 이번 화면에서 바뀐 행만 모은다
before = shown.set_index("번호")[["판정_연구소", "맞음", "공유_연구소", "메모"]]
after = edited.set_index("번호")[["판정_연구소", "맞음", "공유_연구소", "메모"]].fillna("")
diff = after[(after.astype(str) != before.fillna("").astype(str)).any(axis=1)]
changed = pd.DataFrame({"번호": diff.index, "판정_연구소": diff["판정_연구소"].map(code).values,
                        "공유_연구소": diff["공유_연구소"].str.upper().str.replace(",", " ").str.split().str.join(" ").values,
                        "확인": diff["맞음"].values, "메모": diff["메모"].values})

st.write(f"바뀐 행 {len(changed)}건 — 필터를 바꾸기 전에 저장하세요(필터를 바꾸면 저장 안 한 편집은 사라집니다).")
if TOKEN:
    if st.button("판정 저장 (GitHub)", type="primary", disabled=len(changed) == 0 or not judge or not unlocked):
        try:
            latest, sha = io_.github_get(REPO, BRANCH, TOKEN)
            merged = io_.merge(latest, changed, judge)
            io_.github_put(REPO, BRANCH, TOKEN, merged, sha, f"연구소 배당 판정 {len(changed)}건 ({judge})")
            st.session_state.ov = merged
            st.success(f"저장했습니다: {len(changed)}건 → {REPO} {io_.REL_PATH}")
            st.rerun()
        except Exception as e:
            st.error(f"저장하지 못했습니다: {e} — 아래 CSV 로 내려받아 두세요.")
    if not judge:
        st.caption("판정자 이름을 넣어야 저장됩니다.")
    if not unlocked:
        st.caption("저장 암호가 맞아야 저장됩니다.")
merged_local = io_.merge(ov, changed, judge or "unknown")
st.download_button("판정 CSV 내려받기", data=("﻿" + io_.to_csv_text(merged_local)).encode("utf-8"),
                   file_name="inst_overrides.csv", mime="text/csv",
                   help=f"저장소의 {io_.REL_PATH} 에 이 파일을 올리면 판정이 반영됩니다")
if not TOKEN:
    st.info("바로 저장하려면 Streamlit Cloud → Manage app → Settings → Secrets 에 "
            "`GITHUB_TOKEN = \"…\"`(이 저장소 Contents 쓰기 권한)과 `JUDGE_PASSCODE = \"…\"`(저장 암호)를 넣으세요. "
            "그 전에는 CSV 를 내려받아 두면 됩니다.")

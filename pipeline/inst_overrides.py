"""사람 판정(연구소 배당) 저장·병합 — 판정 화면(pages/1_연구소_배당_판정.py)과 classify_inst.py 가 함께 쓴다.

data/assets/inst_overrides.csv  (utf-8-sig)
  번호, 판정_연구소(INST-01..07 | OUT=연구소 밖), 공유_연구소(공백 구분 INST 코드), 확인(1=기계 배정 맞음 확인),
  메모, 판정자, 판정시각
규칙: 판정_연구소가 있으면 기계 배정보다 우선(배정근거 = "사람 판정"). 저장은 번호 단위로 덮어쓴다 —
다른 사람이 같은 시간에 다른 번호를 판정해도 서로 지우지 않는다(저장 직전 최신 파일을 다시 읽어 병합).
GitHub 저장: Streamlit Secrets 의 GITHUB_TOKEN(이 저장소 contents 쓰기 권한)이 있을 때만, main 에 이 파일 한 개만 커밋.
"""
from __future__ import annotations

import base64
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

REL_PATH = "data/assets/inst_overrides.csv"
COLS = ["번호", "판정_연구소", "공유_연구소", "확인", "메모", "판정자", "판정시각"]
EDIT_COLS = ["판정_연구소", "공유_연구소", "확인", "메모"]
KST = timezone(timedelta(hours=9))


def empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COLS)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reindex(columns=COLS).copy()
    df["번호"] = pd.to_numeric(df["번호"], errors="coerce").astype("Int64")
    for c in ("판정_연구소", "공유_연구소", "메모", "판정자", "판정시각"):
        df[c] = df[c].fillna("").astype(str).str.strip()
    df["확인"] = df["확인"].map(lambda v: str(v).strip().lower() in ("1", "true", "yes", "y", "o"))
    return df.dropna(subset=["번호"]).drop_duplicates("번호", keep="last")


def from_csv_text(text: str) -> pd.DataFrame:
    if not text.strip():
        return empty()
    return _clean(pd.read_csv(io.StringIO(text), dtype=str))


def to_csv_text(df: pd.DataFrame) -> str:
    out = _clean(df).sort_values("번호")
    out["확인"] = out["확인"].map(lambda b: "1" if b else "")
    return out.to_csv(index=False)


def read_local(root: Path) -> pd.DataFrame:
    p = Path(root) / REL_PATH
    return from_csv_text(p.read_text(encoding="utf-8-sig")) if p.exists() else empty()


def is_meaningful(r) -> bool:
    return bool(r["판정_연구소"] or r["공유_연구소"] or r["메모"] or r["확인"])


def merge(base: pd.DataFrame, changed: pd.DataFrame, judge: str) -> pd.DataFrame:
    """base(최신 저장본) 위에 changed(이번에 고친 번호들)를 덮어쓴다. 내용이 다 빈 행은 판정 취소로 지운다."""
    base, changed = _clean(base), _clean(changed)
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    changed["판정자"], changed["판정시각"] = judge, now
    keep = base[~base["번호"].isin(changed["번호"])]
    new = changed[changed.apply(is_meaningful, axis=1)]
    return pd.concat([keep, new], ignore_index=True).sort_values("번호").reset_index(drop=True)


def apply(ri: pd.DataFrame, ov: pd.DataFrame) -> pd.DataFrame:
    """report_inst 표에 사람 판정을 덮는다: 연구소_배정 / 배정근거 / 공유후보."""
    ri = ri.copy()
    ri["기계_배정"] = ri["연구소_배정"]
    ov = _clean(ov).set_index("번호")
    for i, r in ri.iterrows():
        n = int(r["번호"])
        if n not in ov.index:
            continue
        o = ov.loc[n]
        if o["판정_연구소"]:
            ri.at[i, "연구소_배정"] = "" if o["판정_연구소"] == "OUT" else o["판정_연구소"]
            ri.at[i, "배정근거"] = "사람 판정" if o["판정_연구소"] != "OUT" else "사람 판정(연구소 밖)"
        elif o["확인"]:
            ri.at[i, "배정근거"] = "사람 확인"
        if o["공유_연구소"]:
            ri.at[i, "공유후보"] = o["공유_연구소"]
    return ri


# ---------- GitHub contents API (requests 는 streamlit 에 딸려 온다) ----------
def github_get(repo: str, branch: str, token: str):
    import requests
    r = requests.get(f"https://api.github.com/repos/{repo}/contents/{REL_PATH}", params={"ref": branch},
                     headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, timeout=20)
    if r.status_code == 404:
        return empty(), None
    r.raise_for_status()
    j = r.json()
    return from_csv_text(base64.b64decode(j["content"]).decode("utf-8-sig")), j["sha"]


def github_put(repo: str, branch: str, token: str, df: pd.DataFrame, sha: str | None, message: str):
    import requests
    body = {"message": message, "branch": branch,
            "content": base64.b64encode(("﻿" + to_csv_text(df)).encode("utf-8")).decode()}
    if sha:
        body["sha"] = sha
    r = requests.put(f"https://api.github.com/repos/{repo}/contents/{REL_PATH}", json=body,
                     headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, timeout=30)
    r.raise_for_status()
    return r.json()["commit"]["sha"]

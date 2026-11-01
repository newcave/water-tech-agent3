# water-tech-agent3 — K-water 연구자산 아카이브 (ALIO 공개 보고서 1단계)

## 목적
K-water 연구보고서에서 **모델링 연구자산·실험 연구자산**을 뽑아 아카이브를 만든다.
연구소별 특성과 여러 소가 함께 쓸 공통 자산을 찾고, 내부 연구자 공유·활용을 넓히는 AI연구소 역할의 기반 자료다.

- 1단계(지금): ALIO 공시 K-water 보고서 147건(`alio_report/`) → kordoc 파싱 → 기본 메타데이터 → 파싱 품질 관제(`app.py`)
- 다음: 요약문 기반 연구자산(모델·데이터·실험) 추출, 연구소별/공통 자산 지도
- 나중: 실제 파일 기록, 보고서에 없는 비공개 부록·내부망 논문 — **온프렘에서만 처리**

## 꼭 지킬 것
1. **이 저장소는 공개(public)다.** 내부 문서·비공개 부록·내부망 논문·비밀값은 커밋하지 않는다. 그런 자료는 온프렘/비공개 저장소에서만 다룬다.
2. 파서는 **kordoc**(npm `kordoc`)을 쓴다. 버전은 `pipeline/run_parse.sh` 의 `KORDOC_VERSION`(현재 4.24.33)에 고정하고, 올릴 때는 전체를 다시 파싱하고 `quality.csv` 변화를 PR 본문에 적는다.
3. `수행조직`은 보고서 제출문에 적힌 **원문 그대로** 둔다. 연구부서 신설·합병·분리 대응표는 사용자가 나중에 준다 → 대응표 파일을 따로 두고 분류(`소속구분`)만 다시 매긴다. 원문을 고쳐 쓰지 않는다.
4. 토큰 절약: LLM 단계는 전문이 아니라 `metadata.jsonl` 의 `요약문_원문`(최대 3,000자)과 요약문 항목을 입력으로 쓴다. 규칙으로 뽑을 수 있는 것은 규칙으로 뽑는다.
5. 후배 박사들이 만든 별도 메타데이터가 있다 — 아직 검토 전. 합칠 때는 번호(NNN)로 맞추고 출처 열을 남긴다.
6. 작업 방식: 최신 main 에서 브랜치 → PR → 머지. 결정·맥락은 PR 본문과 이 파일에 남긴다.

## 폴더
```
alio_report/              원본 PDF 147건 "(NNN) 제목_공시일_약칭.pdf.pdf" — (074)(113)은 100MB 초과라 Git LFS
pipeline/run_parse.sh     kordoc 일괄 변환 (이미 성공한 번호는 건너뜀, LFS 포인터는 건너뜀)
pipeline/parse_one.sh     1건 변환: Markdown + RAG 청크
pipeline/extract_meta.py  제출문·요약문 규칙 추출 → metadata.jsonl
pipeline/quality.py       보고서별 파싱 품질(어절 성공·실패율 등) → quality.csv
data/parsed/md/NNN.md         kordoc Markdown (표=HTML, 그림=자리 표시만)
data/parsed/chunks/NNN.json   kordoc RAG 청크 (제목 경로 breadcrumb, 표=GFM 독립 청크, page 번호)
data/parsed/metadata.jsonl    보고서별 메타데이터
data/parsed/quality.csv       보고서별 품질·판정
data/parsed/run_log.tsv       번호 · md 종료코드 · chunks 종료코드 · 초 (· 완료시각)
data/parsed/run_info.json     마지막 실행의 kordoc 버전·옵션·원본 커밋
app.py                        파싱 관제 화면 (Streamlit)
```

## 실행
```bash
git lfs pull                                   # LFS 2건까지 받으려면
pipeline/run_parse.sh                          # 또는 SOURCE=git (PDF 체크아웃 없는 부분 clone)
python pipeline/extract_meta.py data/parsed/md data/parsed/metadata.jsonl
python pipeline/quality.py --md-dir data/parsed/md --meta data/parsed/metadata.jsonl \
  --run-log data/parsed/run_log.tsv --pdf-dir alio_report [--git-repo .] --out data/parsed/quality.csv
streamlit run app.py
```
- kordoc 옵션: Markdown `--no-images --silent`, 청크 `--format chunks --table-format gfm --no-images`. 머리글·바닥글 자동 제거는 기본값(켜짐).
- 그림이 필요하면 `--no-images` 를 빼고 다시 돈다(1건에 수십 MB라 저장소에는 넣지 않는다).
- 스캔 쪽(OCR 후보)은 `kordoc 파일.pdf --ocr` 로 다시 읽는다. 첫 실행에 OCR 모델(~18MB)을 받는다.

## 품질 지표 (`pipeline/quality.py`)
- 기준 텍스트 = 같은 PDF의 텍스트층(poppler `pdftotext`). 정답지가 아니라 비교 기준이다.
- 어절: 한글·영문·숫자 경계에서 나눈 토큰. pdftotext 가 "KS를"·"3개월"을 글꼴 경계에서 쪼개기 때문에 양쪽을 같은 규칙으로 나눈다.
- **어절 성공률** = 겹친 어절 수(다중집합) / 기준 어절 수, **어절 실패율** = 1 − 성공률. 어절 정밀도 = 겹친 어절 / kordoc 어절.
- 글자 재현율 = 같은 계산을 글자 단위로(띄어쓰기 차이 제외). 글 없는 쪽 = 텍스트층 30자 미만 쪽(스캔·그림).
- 판정: 어절 성공률 < 85% 실패 · < 93% 주의 · 글자 재현율 < 95% · 글 없는 쪽 > 10% · 메타 < 5/7 → 주의. 깨끗한 보고서도 3~5%는
  기준 쪽 잡음(자간 벌린 제목 "제 출 문", 제거된 머리글·쪽번호)이라 93%를 주의선으로 둔다. 기준은 `THRESHOLDS` 한 곳에서 바꾼다.

## 알게 된 것 (2026-11-01, 1차 실행)
- ALIO 보고서에는 K-water연구원 7개 연구소 과제뿐 아니라 **본사·지역 부서 과제**(수자원운영처, 환경본부 수질안전처, 소양강댐지사 등)가 섞여 있다.
- 표준 형식: 제출문(수행연도·수행조직·연구책임자·연구수행자) → 요약문(1.연구제목 2.연구기간 3.연구목적 4.연구내용 5.연구결과 …). 요약문의 연구내용에 쓴 모델이 이미 나온다(예: (010) 랜덤포레스트 하천수위, LSTM 저수지 유입량).
- 형식이 다른 보고서: (001)~(009)·(019) 는 파일명에 날짜가 없고 일부는 제출문이 없다(예: (007) 유럽 물시장 진입 전략). 메타가 비면 관제 화면에서 "주의 · 메타 n/7" 로 보인다.
- (019) 만 확장자가 `.pdf` 하나, 나머지 146건은 `.pdf.pdf`.
- 파싱 속도: 1건 Markdown+청크 평균 약 24초(2코어 동시 2건). 55MB 보고서도 문제없음.

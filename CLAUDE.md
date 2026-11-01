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
7. `app.py` 는 Streamlit 에 딸려 오는 패키지(pandas·altair)만 쓴다. Streamlit Cloud 는 앱을 처음 배포한 뒤 `requirements.txt` 가
   바뀌어도 재부팅 전까지 새 패키지를 설치하지 않을 수 있다(2026-11-01 plotly ModuleNotFoundError). 새 패키지가 꼭 필요하면 머지 후 Manage app → Reboot.

## 폴더
```
alio_report/              원본 PDF 147건 "(NNN) 제목_공시일_약칭.pdf.pdf" — (074)(113)은 100MB 초과라 Git LFS
pipeline/run_parse.sh     kordoc 일괄 변환 (이미 성공한 번호는 건너뜀, LFS 포인터는 건너뜀)
pipeline/parse_one.sh     1건 변환: Markdown + RAG 청크
pipeline/extract_meta.py  제출문·요약문 규칙 추출 → metadata.jsonl
pipeline/quality.py       보고서별 파싱 품질(어절 성공·실패율 등) → quality.csv
pipeline/write_status.py  run_info.json + 에이전트 상태 파일
data/parsed/md/NNN.md         kordoc Markdown (표=HTML, 그림=자리 표시만)
data/parsed/chunks/NNN.json   kordoc RAG 청크 (제목 경로 breadcrumb, 표=GFM 독립 청크, page 번호)
data/parsed/metadata.jsonl    보고서별 메타데이터
data/parsed/quality.csv       보고서별 품질·판정
data/parsed/run_log.tsv       번호 · md 종료코드 · chunks 종료코드 · 초 (· 완료시각)
data/parsed/run_info.json     마지막 실행의 kordoc 버전·옵션·원본 커밋
data/parsed/org_names.csv     수행조직 원문 목록 — '대응_연구소코드' 열을 채우면 extract_meta.py 가 소속구분을 그 값으로 다시 매김
data/parsed/agents/alio_kordoc_parser.json   실행 상태 (water-tech-agent 관제센터 에이전트 상태 형식)
app.py                        파싱 관제 화면 (Streamlit)
```

## 실행
```bash
git lfs pull                                   # LFS 2건까지 받으려면
pipeline/run_parse.sh                          # 또는 SOURCE=git (PDF 체크아웃 없는 부분 clone)
python pipeline/extract_meta.py data/parsed/md data/parsed/metadata.jsonl
python pipeline/quality.py --md-dir data/parsed/md --meta data/parsed/metadata.jsonl \
  --run-log data/parsed/run_log.tsv --pdf-dir alio_report [--git-repo .] --out data/parsed/quality.csv
python pipeline/write_status.py --out data/parsed --source-commit $(git rev-parse --short HEAD)
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
- 한글비율 = 한글/(한글+영문), 이상문자비율 = (라틴확장+한자)/(한글+라틴확장+한자). 글꼴 인코딩 깨짐 탐지용.
  **기준 텍스트도 똑같이 깨져 있으면 어절 비교는 '성공'으로 나오므로** 이 두 비율이 꼭 필요하다.
- 판정(파싱 품질만): 실패 = kordoc 오류 · 인코딩 깨짐(이상문자 > 30% 또는 한글 < 5%) · 글자 재현율 < 60%.
  주의 = 어절 성공률 < 85% · 글자 재현율 < 90% · 글 없는 쪽 > 10% · 사용자정의 기호(PUA) > 1%. 기준은 `THRESHOLDS` 한 곳.
- 메타데이터는 판정과 분리해 `메타상태`(완전 / 부분 n/7 / 없음)로 본다 — 추출기 품질이지 kordoc 품질이 아니다.
- pdftotext 기준의 잡음(1차 실행에서 확인): 매 쪽 반복 머리글(kordoc 은 지움, 예 (070) 과제명 56회), 자간 벌린 영문을
  글자 단위로 쪼갬(예 (060) "e i t"), 그래프 축·범례 글자, kordoc 이 LaTeX(`\lambda`)로 바꾼 수식, 목차 줄. 그래서 어절 성공률이
  80%대여도 kordoc 쪽 손실이 아닌 경우가 많다 — 낮은 보고서는 쪽별 대조로 확인하고 판단한다.

## 알게 된 것 (2026-11-01, 1차 실행)
- ALIO 보고서에는 K-water연구원 7개 연구소 과제뿐 아니라 **본사·지역 부서 과제**(수자원운영처, 환경본부 수질안전처, 소양강댐지사 등)가 섞여 있다.
- 표준 형식: 제출문(수행연도·수행조직·연구책임자·연구수행자) → 요약문(1.연구제목 2.연구기간 3.연구목적 4.연구내용 5.연구결과 …). 요약문의 연구내용에 쓴 모델이 이미 나온다(예: (010) 랜덤포레스트 하천수위, LSTM 저수지 유입량).
- 형식이 다른 보고서: (001)~(009)·(019) 는 파일명에 날짜가 없고 일부는 제출문이 없다(예: (007) 유럽 물시장 진입 전략). 메타가 비면 관제 화면에서 "주의 · 메타 n/7" 로 보인다.
- (019) 만 확장자가 `.pdf` 하나, 나머지 146건은 `.pdf.pdf`.
- 1차 판정(2026-11-01): 성공 103 · 주의 38 · 실패 4(인코딩 깨짐) · 대기 2(LFS). 평균 어절 성공률 91.3%, 평균 글자 재현율 96.5%, 추출 어절 560만, OCR 후보 쪽 1,946쪽.
- 파싱: 145건 전부 kordoc 오류 0. 1건 Markdown+청크 평균 29초(2코어 동시 2건), 최장 (056) 105초. 55MB 보고서도 문제없음.
- **글꼴 인코딩 깨짐 4건 — (008) (033) (101) (120)**: PDF 텍스트층이 "ìÞÿí" 같은 글자로 깨져 있어 kordoc·pdftotext 모두 못 읽는다.
  `kordoc --ocr-force` 로 다시 읽어야 한다. **이 클라우드 환경은 OCR 모델 주소(huggingface.co)가 막혀** `--ocr-force` 가 조용히
  텍스트층으로 돌아간다(1초 만에 같은 깨진 글자). PC나 온프렘에서 돌리거나, 모델을 미리 받아 `~/.cache/kordoc/models/ppocr/` 에
  두고 `KORDOC_OFFLINE=1` 로 돌린다.
- 메타데이터(규칙 추출): 7항목 완전 52건, 요약문 원문 확보 111건, 수행조직 확보 99건. 제출문이 없거나 형식이 다른 보고서
  (외부기관 용역 "요약서", 해외 진출 보고서 "요약보고서" 표 등)는 비거나 부분만 찬다 — LLM 단계 입력은 `요약문_원문`.
- 수행조직 원문 62종 → `data/parsed/org_names.csv`(건수·현재 분류·보고서 번호, 대응 연구소 열은 빈칸). 옛 이름이 많다:
  물정책연구소, 물순환연구소, 스마트워터연구소, 스마트연구소, 유역물관리연구소, 물인프라·에너지연구소, 수질안전센터,
  연구관리처 AI연구센터, 연구지원처. **사용자가 조직 개편(신설·합병·분리) 정보를 주면 이 파일의 대응 열을 채우고
  `extract_meta.py` 가 그 표를 읽어 소속구분을 다시 매기게 한다.** 외부기관(대학 산학협력단·학회) 용역도 20건쯤 있다.

## 다음 단계 메모
- 연구자산 인벤토리 출력은 `newcave/water-tech-agent` 의 `data_seed/shared_datasources.json` 과 같은 꼴로 낸다:
  `{cid, name, avail(open|internal_only), n_docs, n_inst, institutes:[INST-0n]}`. INST 코드·연구소 이름도 그쪽 `INST_NAME` 과 같다.
  그쪽 기존 파이프라인은 ALIO 121건을 gpt-4o 로 처리(성공 105, 데이터소스 언급 1,695 → 고유 1,285)했다 — agent3 은 147건 · kordoc · 규칙 우선.
- 실행 상태는 `data/parsed/agents/alio_kordoc_parser.json` 에 water-tech-agent 의 `data_seed/agents/*.json` 형식으로 쓴다
  (관제센터에서 바로 읽을 수 있게). 그쪽 저장소는 참고만 하고 고치지 않는다.

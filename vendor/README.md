# vendor — 다른 저장소에서 그대로 복사한 파일 (고치지 않는다)

agent3 의 연구소 분류·데이터소스 탐지를 기존 파이프라인과 **같은 기준**으로 하기 위해 원본을 복사해 둔다.
원본이 바뀌면 같은 경로로 다시 복사하고 이 표의 커밋을 갱신한다. 내용을 여기서 고치지 않는다.

| 파일 | 원본 | 커밋 | 쓰는 곳 |
|---|---|---|---|
| `water_tech_agent/label_review.py` | newcave/water-tech-agent `label_review.py` | f796cc9 (2026-11-01) | `Scorer` — 연구소 적합도·이관·공유 후보 |
| `water_tech_agent/label_review_profiles.json` | newcave/water-tech-agent `data_seed/label_review_profiles.json` | f796cc9 | 연구소별 키워드·분야 친화도·점수 설정 |
| `water_tech_agent/shared_datasources.json` | newcave/water-tech-agent `data_seed/shared_datasources.json` | f796cc9 | 기존 공유 데이터소스 인벤토리(비교·별칭 보강) |
| `alio_pipeline/datasource_registry.json` | newcave/2607alioreport `datasource_registry.json` | cdeaf49 (2026-07-08) | 데이터소스 사전(정식 ID·별칭·접근성) |

"""Build data/assets/asset_gazetteer.json — the dictionary of research assets to look for.

kind = data    data systems / observation sets  (base: vendor/alio_pipeline/datasource_registry.json, 24)
kind = model   numerical / process models       (curated list below)
kind = method  named analysis methods (ML etc.)  (curated list below)

Edit MODELS / METHODS / EXTRA_DATA here (or the generated JSON) to extend; ids are stable keys.
Matching rules (pipeline/asset_map.py): Latin aliases = case-sensitive whole-token match,
Korean aliases = substring match.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
reg = json.loads((ROOT / "vendor/alio_pipeline/datasource_registry.json").read_text(encoding="utf-8"))["registry"]

EXTRA_DATA = [  # K-water systems seen in water-tech-agent shared_datasources.json but not in the registry
    {"id": "WATERNET", "name": "water-NET (K-water 수도 통합운영)", "avail": "internal_only", "owner": "K-water",
     "aliases": ["water-NET", "Water-NET", "WaterNET", "워터넷"]},
    {"id": "IWATER", "name": "i-water (스마트 물관리 플랫폼)", "avail": "internal_only", "owner": "K-water",
     "aliases": ["i-water", "I-water", "i-Water", "아이워터"]},
    {"id": "SWIS", "name": "스마트워터시티·스마트미터(AMI) 데이터", "avail": "internal_only", "owner": "K-water",
     "aliases": ["스마트미터", "스마트 미터", "AMI", "원격검침"]},
    {"id": "DAM_OPS", "name": "댐 운영자료(유입·방류·저수위)", "avail": "internal_only", "owner": "K-water",
     "aliases": ["댐 운영자료", "댐운영자료", "방류량 자료", "저수위 자료", "댐 유입량 자료"]},
]

MODELS = [
    ("SWAT", "SWAT (유역 수문·수질)", ["SWAT", "SWAT+"]),
    ("HSPF", "HSPF (유역 수문·수질)", ["HSPF"]),
    ("HEC_RAS", "HEC-RAS (하천 수리)", ["HEC-RAS", "HEC RAS", "HECRAS"]),
    ("HEC_HMS", "HEC-HMS (강우-유출)", ["HEC-HMS", "HEC HMS", "HECHMS"]),
    ("HEC_RESSIM", "HEC-ResSim (저수지 운영)", ["HEC-ResSim", "ResSim"]),
    ("SWMM", "SWMM (도시 유출·관거)", ["SWMM", "XP-SWMM", "EPA-SWMM", "EPA SWMM"]),
    ("EPANET", "EPANET (상수관망 수리)", ["EPANET", "EPAnet"]),
    ("WATERGEMS", "WaterGEMS (상수관망)", ["WaterGEMS"]),
    ("INFOWORKS", "InfoWorks (관망·도시홍수)", ["InfoWorks", "InfoWorks ICM"]),
    ("MODFLOW", "MODFLOW (지하수 흐름)", ["MODFLOW", "Visual MODFLOW", "GMS"]),
    ("FEFLOW", "FEFLOW (지하수)", ["FEFLOW"]),
    ("CE_QUAL_W2", "CE-QUAL-W2 (저수지 수질)", ["CE-QUAL-W2", "CE-QUAL W2", "CEQUALW2", "W2 모형"]),
    ("AEM3D", "AEM3D (3차원 수질)", ["AEM3D", "ELCOM", "CAEDYM", "ELCOM-CAEDYM"]),
    ("EFDC", "EFDC (3차원 수리·수질)", ["EFDC", "EFDC-NIER"]),
    ("QUAL2", "QUAL2E/QUAL2K (하천 수질)", ["QUAL2E", "QUAL2K", "QUAL2Kw"]),
    ("WASP", "WASP (수질)", ["WASP", "WASP7", "WASP8"]),
    ("DELFT3D", "Delft3D (수리·수질·지형)", ["Delft3D", "Delft-3D", "D-Flow"]),
    ("MIKE", "MIKE 계열 (DHI)", ["MIKE 11", "MIKE11", "MIKE 21", "MIKE21", "MIKE SHE", "MIKE URBAN", "MIKE+", "MIKE FLOOD"]),
    ("FLO2D", "FLO-2D (범람)", ["FLO-2D", "FLO2D"]),
    ("TANK", "TANK 모형 (강우-유출)", ["TANK 모형", "TANK모형", "탱크모형", "탱크 모형"]),
    ("SSARR", "SSARR (하천 유출)", ["SSARR"]),
    ("PRMS", "PRMS (유역 수문)", ["PRMS"]),
    ("VIC", "VIC (대규모 수문)", ["VIC model", "VIC 모형", "VIC모형"]),
    ("WEAP", "WEAP (물수급 계획)", ["WEAP", "K-WEAP"]),
    ("MODSIM", "MODSIM / KModSim (물배분)", ["MODSIM", "KModSim", "K-ModSim"]),
    ("COSFIM", "COSFIM (댐 홍수 운영)", ["COSFIM"]),
    ("KDRUM", "K-DRUM (분포형 유출)", ["K-DRUM", "KDRUM"]),
    ("GR4J", "GR4J (개념적 유출)", ["GR4J"]),
    ("STORAGE_FN", "저류함수법 (홍수 유출)", ["저류함수법", "저류함수모형", "저류함수 모형"]),
    ("CFD", "CFD (전산유체: FLOW-3D·Fluent 등)", ["FLOW-3D", "FLOW3D", "Fluent", "OpenFOAM", "CFD"]),
    ("RCM_SSP", "기후변화 시나리오 (SSP/RCP·GCM)", ["SSP1", "SSP2", "SSP3", "SSP5", "RCP4.5", "RCP8.5", "CMIP6", "CMIP5", "GCM"]),
]

METHODS = [
    ("LSTM", "LSTM / GRU (순환신경망)", ["LSTM", "GRU", "Bi-LSTM", "BiLSTM"]),
    ("CNN", "CNN (합성곱신경망)", ["CNN", "U-Net", "UNet", "ResNet", "YOLO"]),
    ("TRANSFORMER", "Transformer (어텐션)", ["Transformer", "트랜스포머", "Attention", "어텐션"]),
    ("RF", "Random Forest", ["Random Forest", "random forest", "랜덤포레스트", "랜덤 포레스트", "랜덤포레스트(RF)"]),
    ("GBM", "XGBoost / LightGBM / GBM", ["XGBoost", "LightGBM", "CatBoost", "GBM", "Gradient Boosting"]),
    ("SVM", "SVM / SVR", ["SVM", "SVR", "서포트 벡터", "서포트벡터"]),
    ("ANN", "ANN / MLP (인공신경망)", ["ANN", "MLP", "인공신경망", "인공 신경망"]),
    ("PINN", "PINN (물리기반 신경망)", ["PINN", "물리정보 신경망", "물리기반 신경망"]),
    ("RL", "강화학습", ["강화학습", "Reinforcement Learning", "DQN", "PPO"]),
    ("LLM", "LLM / 생성형 AI", ["LLM", "GPT", "ChatGPT", "생성형 AI", "생성형AI", "언어모델", "RAG"]),
    ("DIGITAL_TWIN", "디지털트윈", ["디지털트윈", "디지털 트윈", "Digital Twin", "digital twin"]),
    ("KRIGING", "크리깅 (공간 보간)", ["크리깅", "Kriging", "kriging"]),
    ("MONTE_CARLO", "몬테카를로 모의", ["몬테카를로", "Monte Carlo", "Monte-Carlo"]),
    ("BAYES", "베이지안 추론", ["베이지안", "Bayesian"]),
    ("ARIMA", "ARIMA (시계열)", ["ARIMA", "SARIMA"]),
    ("OPTIM", "최적화 (GA·PSO·LP)", ["유전자 알고리즘", "유전자알고리즘", "Genetic Algorithm", "PSO", "선형계획법"]),
]

# agent3 overrides of registry aliases: "현장조사"/"현지조사" hit almost every report (61/145) -> keep water-quality-specific ones
ALIAS_OVERRIDE = {"FIELD_WQ_SURVEY": ["현장 수질조사", "수질 현지조사", "수질 현장조사", "시료채취", "수질오염공정시험"]}

# 수단 연구소(method institutes)가 다른 연구소에 공급·지원할 수 있는 자산 = '넘길 수 있는' 축
PROVIDER = {**{k: "INST-06" for k in ("MODIS", "Landsat", "Sentinel", "KOMPSAT", "KMA_RADAR")},
            **{k: "INST-07" for k in ("LSTM", "CNN", "TRANSFORMER", "RF", "GBM", "SVM", "ANN", "PINN", "RL", "LLM",
                                      "DIGITAL_TWIN")}}

out = []
for r in reg:
    out.append({"id": r["canonical_id"], "name": r["name_kr"], "kind": "data", "avail": r["default_availability"],
                "owner": r.get("owner"), "aliases": ALIAS_OVERRIDE.get(r["canonical_id"], sorted(set(r["aliases"]))),
                "source": "2607alioreport registry" + (" (aliases narrowed by agent3)" if r["canonical_id"] in ALIAS_OVERRIDE else "")})
for r in EXTRA_DATA:
    out.append({**r, "kind": "data", "source": "agent3 (water-tech-agent inventory)"})
for i, n, a in MODELS:
    out.append({"id": i, "name": n, "kind": "model", "avail": "open", "owner": None, "aliases": a, "source": "agent3"})
for i, n, a in METHODS:
    out.append({"id": i, "name": n, "kind": "method", "avail": "open", "owner": None, "aliases": a, "source": "agent3"})

for x in out:
    x["provider"] = PROVIDER.get(x["id"])

dst = ROOT / "data/assets/asset_gazetteer.json"
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps({"_doc": __doc__.strip(), "assets": out}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {dst}: {len(out)} assets", {k: sum(1 for x in out if x['kind'] == k) for k in ('data', 'model', 'method')})

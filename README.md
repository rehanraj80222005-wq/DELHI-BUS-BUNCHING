# Delhi Bus Bunching Predictor (DBBP)

A real-time public-transit intelligence and machine learning system using Delhi Open Transit Data (OTD) GTFS static schedules and live GTFS-Realtime Protocol Buffer telemetry to detect abnormal bus headways and predict route-level bunching 10 to 15 minutes before it occurs.

---

## 1. Problem Statement

Bus bunching occurs when buses on the same route fail to maintain uniform headway spacing. A delayed bus encounters more waiting passengers, increasing dwell time; conversely, the trailing bus encounters fewer passengers, accelerates, and eventually catches up to the lead bus.

```
Normal Pattern:
Bus A ────── (10 min) ────── Bus B ────── (10 min) ────── Bus C

Bunched Pattern:
Bus A ── (2 min) ── Bus B ───────────────── (22 min) ───────────────── Bus C
```

**Negative impacts on passengers and operations:**
- Excessive and unpredictable passenger waiting times.
- Severe overcrowding on lead vehicles followed by under-utilized trailing buses.
- Unreliable headway adherence and fleet inefficiency.

---

## 2. End-to-End System Architecture

```
 Delhi OTD Static GTFS       Delhi OTD Realtime API
 (543 routes, 8,374 stops)   (5,500+ live buses / pb)
            │                           │
            └─────────────┬─────────────┘
                          ▼
              Realtime Ingestion & Cleaning
               (Outlier & Stale Filters)
                          │
                          ▼
            Movement Reconstruction Engine
              (Speed, Bearing, Progress)
                          │
                          ▼
                 Headway Engine
             (Consecutive Vehicle Spacing)
                          │
                          ▼
            Statistical Bunching Detector
            (NORMAL, LOW, MOD, HIGH, SEVERE)
                          │
                          ▼
               SQLite / PostgreSQL DB
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
    Feature Engineering        Historical Analytics
  (Zero Temporal Leakage)       (Hotspots & Heatmaps)
            │
            ▼
    Machine Learning Models
 (Logistic, Random Forest, XGBoost)
            │
            ▼
   SHAP Explainability Layer
  (Feature Attributions per Risk)
            │
            ├───────────────────────────┐
            ▼                           ▼
     FastAPI Backend           Streamlit Dashboard
     (REST Endpoints)           (5-Page Ops Monitor)
```

---

## 3. Implemented Modules

| Module | Location | Purpose |
| :--- | :--- | :--- |
| **Config** | `src/config.py` | Environment, paths, Delhi NCR bounding box (`28.20..29.05 N`, `76.60..77.60 E`). |
| **GTFS Loader** | `src/ingestion/gtfs_loader.py` | Loads and indexes static schedules with preserved string IDs. |
| **Validation** | `src/processing/validation.py` | Referential integrity checks (`trips` $\to$ `routes`, `stop_times` $\to$ `stops`). |
| **Realtime Client** | `src/ingestion/realtime_client.py` | Queries `/api/realtime/VehiclePositions.pb` with hidden API key. |
| **Protobuf Parser** | `src/ingestion/protobuf_parser.py` | Deserializes `FeedMessage` protobuf into structured records. |
| **Cleaning** | `src/processing/cleaning.py` | Drops out-of-bounds coords, duplicate pings, and stale timestamps. |
| **Movement** | `src/processing/movement.py` | Haversine distance, speed, bearing, and $O(1)$ GTFS stop matching. |
| **Headway Engine** | `src/analytics/headway.py` | Route-level grouping and consecutive pair headway calculations. |
| **Bunching Detector**| `src/analytics/bunching.py` | Detects bunching events with severity classification. |
| **Historical** | `src/analytics/historical.py` | Computes route bunching frequency, stop hotspots, and headway statistics. |
| **Feature Store** | `src/features/engineering.py` | Temporal, headway, kinematic, and spatial features with chronological splits. |
| **ML Training** | `src/models/train.py` | Progressive training: Baseline Logistic Regression $\to$ Random Forest $\to$ Champion XGBoost. |
| **Explainability** | `src/models/explain.py` | Mathematical feature attributions explaining individual risk predictions. |
| **Predictor** | `src/models/predict.py` | Online inference service providing probability and severity. |
| **REST API** | `src/api/main.py` | FastAPI backend exposing live vehicles, routes, predictions, and alerts. |
| **Dashboard** | `dashboard/app.py` | 5-page interactive operations dashboard with Leaflet map and Plotly charts. |

---

## 4. Quickstart & Usage

### 1. Environment Setup
```bash
# Clone / open workspace
cd delhi-bus-bunching

# Create and activate virtual environment
uv venv .venv
.\.venv\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt
```

### 2. Configure API Key
Copy the template and paste your authorized Delhi OTD API key:
```bash
copy .env.example .env
# Edit .env:
OTD_API_KEY=your_actual_key_here
```

### 3. Run Ingestion & Detection
Execute a single live collection and detection cycle across Delhi:
```bash
python scripts/run_collector.py --once
```
Or run the continuous collector daemon (default 30s polling):
```bash
python scripts/run_collector.py --interval 30
```

### 4. Train Predictive Models
Train Baseline Logistic Regression, Random Forest, and XGBoost:
```bash
python src/models/train.py
```

### 5. Launch FastAPI REST Service
```bash
uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive Swagger documentation available at: `http://127.0.0.1:8000/docs`

Key endpoints:
- `GET /health`: System and database health status
- `GET /routes`: Active monitored routes
- `GET /vehicles/live`: Real-time vehicle GPS coordinates
- `GET /routes/{route_id}/headway`: Inter-bus headways on a route
- `GET /routes/{route_id}/prediction`: Bunching probability & SHAP explanations
- `GET /stops/hotspots`: Top bunching stops in Delhi
- `GET /alerts`: High-severity bunching alerts

### 6. Launch Operations Dashboard
```bash
streamlit run dashboard/app.py
```
Open `http://localhost:8501` to access the 5 monitoring pages:
1. **Overview:** Fleet metrics & active early warning alerts
2. **Live Map:** Interactive geospatial bus tracking
3. **Route Intelligence:** Headway deviation patterns per route
4. **Hotspots:** High-risk bunching stops & routes
5. **Model Explainability:** Interactive feature attribution tool

### 7. Run Test Suite
```bash
pytest tests/ -v
```
All 29 tests verify data loaders, validation rules, protobuf parsing, movement math, database storage, ML training, and API endpoints.

---

## 5. Security and Methodology Notes

- **Zero Credential Exposure:** API keys are loaded strictly via `.env` and are never logged, printed, or sent in API responses.
- **No Temporal Leakage:** Feature pipelines use strictly historical and current observation data; train/validation/test sets are split chronologically.
- **Explainability vs. Causality:** SHAP and feature contribution scores represent model mathematical attributions, not proven causal relationships.

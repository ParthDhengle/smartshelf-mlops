# 🏗️ SmartShelf AI: Technical Architecture & System Report

This document outlines the complete end-to-end architecture of **SmartShelf AI**, detailing how operational data flows into the data warehouse, gets transformed into features, trains orchestrated machine learning models, and is served in real-time to a cutting-edge Next.js frontend.

---

## 1. High-Level Architecture Flow

SmartShelf runs a decoupled, modern MLOps architecture. The system is broken down into four core domains:

1. **Transactional Data (OLTP):** Live data capturing sales, products, and inventory (PostgreSQL).
2. **Data Warehouse (OLAP):** Aggregated batch data for Model Training (Google BigQuery).
3. **MLOps Engine:** Automated model training, tuning, evaluation, and registry (Prefect & MLflow).
4. **Serving Layer:** REST API and Frontend Dashboard for real-time predictions (FastAPI & Next.js).

### Architecture Diagram (Mermaid)

```mermaid
graph TD
    subgraph Data Sources
        PG[(PostgreSQL<br>Live OLTP DB)]
        EXT((External APIs<br>Weather, Macro))
    end

    subgraph Data Warehouse
        BQ[(BigQuery<br>Feature Store)]
    end

    subgraph MLOps Orchestration (Prefect)
        FE[Feature Engineering<br>Pipeline]
        MD[Train Demand Model<br>XGBoost]
        MP[Train Pricing Model<br>LightGBM]
        MI[Train Inventory Model<br>XGBoost + EOQ]
    end

    subgraph Model Registry & Serving
        MLF[(MLflow<br>Tracking Server)]
        API[FastAPI Backend]
        cache[(Model RAM Cache)]
    end

    subgraph Client Application
        UI[Next.js Dashboard UI]
        CS[Critical Stock Engine]
        PL[Predictions Lab]
    end

    %% Data Flow
    PG -- ELT Sync --> BQ
    EXT -- Live Sync --> PG
    
    BQ -- SQL Aggregations --> FE
    FE --> MD
    MD -- Demand Context --> MP
    MD & MP -- Joint Context --> MI
    
    MD & MP & MI -- Log Metrics & Artifacts --> MLF
    
    MLF -- Load Prod Models --> API
    API -- In-Memory --> cache
    
    API <--> UI
    UI --> CS
    UI --> PL
```

---

## 2. Component Deep Dive

### 2.1 The Data Layer (PostgreSQL & BigQuery)
To prevent heavy ML feature aggregations from locking up the live database, SmartShelf employs a traditional Data Warehouse architecture.

- **PostgreSQL (OLTP):** Stores the live state of the supermarket (e.g., current stock, daily sales transactions, product metadata).
- **Google BigQuery (OLAP):** The Prefect flow `feature_flow.py` periodically syncs PostgreSQL tables to BigQuery using `pandas-gbq`. BigQuery handles the heavy lifting of calculating 7-day, 14-day, and 28-day rolling means/standards, lag features, and time-based alignments.

**External API Sync:** The system routinely pulls data from OpenWeather and standard holiday APIs natively into Postgres to contextualize the ML models regarding seasonal traffic and rain/heat anomalies.

### 2.2 The MLOps Pipeline (Prefect & MLflow)
The legacy Airflow DAGs were removed in favor of **Prefect**, which integrates purely natively with Python logic and removes massive environmental overhead.

The core pipeline `src/smartshelf/flows/training_flow.py` runs sequentially:
1. **Demand Model (XGBoost):** Predicts future 7-day sales demand for a specific item.
2. **Pricing Model (LightGBM):** Takes the new *Predicted Demand* as an input. It calculates price elasticity natively and determines the pricing threshold that yields maximum net profit. LightGBM is chosen here for extreme inference speeds when sweeping pricing arrays.
3. **Inventory Model (XGBoost + EOQ Hybrid):** Takes *Predicted Demand* and *Optimal Price* to predict a target Safety Stock based on lead-time variances. It then fuses the classical **Economic Order Quantity (EOQ)** mathematical formulation with the ML safety stock to give an exact "Reorder quantity and timestamp".

*All hyperparameters, CV metrics (RMSE/r2), feature importances, and model artifact files are rigorously tracked and stored inside **MLflow** locally.*

### 2.3 The Serving API (FastAPI)
The backend routes logic seamlessly while heavily leaning on MLflow. 

When the server spins up, it queries the MLflow Tracking Server for any model staged as `Production`. It loads them directly into RAM (cached).
- **Endpoint:** `/api/v1/full-pipeline` executes all three models sequentially in memory (<200ms) to deliver a 7-day outlook to the UI.
- **Admin System:** The API dynamically queries MLflow's registry and pushes the active model names, RMSEs, and version tags to the Next.js frontend, resulting in 0 hardcoded metrics.

### 2.4 The Client Application (Next.js 14)
The frontend utilizes TypeScript, React, and `recharts` for an ultra-premium glassmorphic user experience.

- **Predictions Lab:** Allows data scientists / managers to test specific store-product ID combinations and review predicted demand/elasticity curves isolated from the database.
- **Critical Stock Application:** A real-time engine that queries the Postgres Database for items with `stock_on_hand` <= 0 (or rapidly declining). When an admin clicks "Analyze & Predict", it calls the full FastAPI pipeline, providing instantaneous decisions on exactly when and how much to restock, and at what optimal retail price.
- **Sales Simulator:** Used to artificially simulate anomalous purchases, verifying the model's resilience to Data Drift in future retraining runs.

---

## 3. Hardware Safety & Resource Limiters
To ensure the pipeline is mathematically stable and does not lock up native operating systems during heavy TimeSeriesSplit cross-validations, the MLOps pipeline natively invokes `nvidia-smi` hardware probes.

- **If an NVIDIA GPU is detected:** XGBoost and LightGBM attach natively to the `cuda`/`gpu` device architectures, pushing parallelism to threading limits (`n_jobs=-1`).
- **If a CPU is detected:** The system acts gracefully. While defaulting `device='cpu'`, it artificially throttles `n_jobs=2` for models and `1` for the CV Grid Search. This ensures the CPU load stays below max limits, preventing OS freezes or memory lockups while executing slightly slower.

---

## 4. CI/CD & Cloud Preparedness Architecture
For the final production push, the repository already integrates core DevOps constructs:

- **GitHub Actions (`ci.yml`, `cd.yml`):** PRs natively trigger ephemeral dockerized PostgreSQL instances and run comprehensive Pytest architectures to intercept structural breaks.
- **Vercel Readiness:** The frontend avoids hardcoded ENV URLs, pulling purely dynamically for instant scalable Edge deployments on Vercel.
- **Backend Containerization:** FastAPI code is cleanly detached, ensuring it can easily be encapsulated in an `alpine-python` Dockerfile and pushed to Amazon EC2 instances or AWS Fargate for horizontal scaling.

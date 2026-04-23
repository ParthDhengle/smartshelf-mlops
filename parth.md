# 🛒 SmartShelf AI: Production-Grade Retail MLOps

Welcome to **SmartShelf AI**, an end-to-end Machine Learning ecosystem designed to revolutionize how retail sectors handle demand forecasting, dynamic price optimization, and inventory restocking.

This project isn't just a prototype—it is a fully functioning **MLOps Architecture** connecting live PostgreSQL databases to Data Warehouses, training heavily orchestrated ML models, tracking versions in MLflow, and serving actionable intelligence instantly to a Next.js Dashboard.

---

## 🎯 Presentation Walkthrough Guide

*Use this step-by-step roadmap to present your project and absolutely blow the audience away!*

### 1. The Home Page & The "Why"
**Where to start:** Show them the `Home / Dashboard` page first.
**What to say:**
> *"Welcome to the SmartShelf AI. Retail margins are incredibly thin, and millions are lost daily to overstocking (unsold inventory) and stockouts (missed sales). SmartShelf solves this by orchestrating 3 independent, state-of-the-art AI models that work together in a chain. It gives store managers a real-time, bird's-eye view of revenue, stock levels, and profitability."*
* Point out the live KPI cards and the dynamic charts calculating margins in real-time.

### 2. The Data Layer (OLTP & Warehouse)
**Where to start:** Switch to the `Products Admin` tab in the UI, and visually reference the backend code: `src/smartshelf/flows/feature_flow.py`

**What to say:**
> *"Our active system operates on a live PostgreSQL database (OLTP) to record day-to-day operations like products, categories, and sales. However, ML models require massive historical aggregation. So, I built an automated ELT pipeline (Data Engineering). It natively syncs our live PostgreSQL data directly into Google BigQuery. From BigQuery, we engineer thousands of lag, rolling, and temporal features to feed our models."*

### 3. The 3 ML Models
**Where to start:** Mention the models conceptually.
**What to say:**
> *"SmartShelf runs 3 distinct models that pass data to each other in a chain:*
> 1. **Demand Model (XGBoost):** Predicts exactly how many units of a product we will sell over the next 7 days.
> 2. **Pricing Model (LightGBM):** Takes the predicted demand and calculates the exact elasticity margin to find the *optimal price* to maximize profit.
> 3. **Inventory Model (XGBoost + EOQ):** Takes both the demand and price predictions, factoring in supplier lead times, to generate mathematically perfect Reorder Points and Safety Stock figures."*

### 4. Live ML Predictions (The "Predictions Lab")
**Where to start:** Click on the `Predictions Lab` tab on your sidebar.
**What to say:**
> *"Rather than looking at static reports, let’s see the models run live. In our Predictions Lab, an analyst can select any specific Product ID and Store ID. When we click 'Run Predictions', the FastAPI backend natively fetches the absolute latest models from our MLflow registry in memory, and spits out the exact forecasted demand chart and the recommended optimal price in real-time!"*

### 5. The Core Value Proposition: The "Critical Stock" Page
**Where to start:** Click on the `Critical Stock` tab (formerly Inventory).
**What to say:** 
> *"This is the crown jewel of the system. In a real supermarket, you don't have time to manually predict 10,000 items. This component continuously scans the database and alerts us to products that have fallen beneath their strict Reorder Points. 
> Notice the **'Analyze & Predict'** button next to the failing items. When I click this, it triggers our entire AI Pipeline at once! It instantly shows us what the demand will be for the next 7 days, how we should price it during the restock, and exactly how many units we must urgently order from our supplier to maximize profit without overstocking."*

### 6. The MLflow Registry & Admin Connectivity
**Where to start:** 
1. First, show them your terminal running the `mlflow ui` (typically at `http://localhost:5000`). Show them how the models are safely registered and versioned.
2. Next, hop back to your Next.js app and click the `Admin Panel`.
**What to say:**
> *"Versioning is critical in production. My FastAPI backend is directly connected to MLflow. Notice the 'Model Registry' table on this Admin panel—those versions and stages aren't hardcoded. They are being pulled **live** from the MLflow Tracking Server! If a data scientist promotes a new model version to 'Production' in MLflow, this dashboard instantly updates, and my API starts routing traffic to the new model without needing a server restart!"*

### 7. Prefect Orchestration
**Where to start:** Open your VS Code / IDE and display `src/smartshelf/flows/training_flow.py`
**What to say:**
> *"To ensure these models don't go stale, I threw out heavy legacy schedulers like Airflow and integrated **Prefect**. Prefect wraps my training code. Every Sunday at 4 AM, it natively executes the feature extraction, trains the Demand model, passes those results to train the Price model, and finally the Inventory model, logging everything automatically. I can trigger it right now manually from my command line."* (Optionally, run `python src/smartshelf/flows/training_flow.py` in your terminal to show it executing perfectly).

### 8. The Sales Simulator
**Where to start:** Click on the `Sales Simulator` tab.
**What to say:**
> *"To truly test the robustness of the system without waiting for real customers, I built a Sales Simulator. We can inject fake transaction volumes and massive random discounts natively into our Postgres Database. This allows us to trigger unexpected 'Data Drift' and see how our Prefect pipelines handle retraining against anomalous behavior!"*

### 9. Next Steps: CI/CD & Cloud Architecture
**Where to start:** Open your IDE and show the `.github/workflows/ci.yml` file.
**What to say:**
> *"What's next for SmartShelf? The architecture is completely production-ready.
> 1. **Robust CI/CD**: I already have GitHub Actions written. When code is pushed, ephemeral Postgres databases are spun up via Docker, running deep Pytest verifications before any merges are allowed.
> 2. **Cloud Hosting**: The Next.js frontend is fully typed and ready to be hosted on simply scalable edge networks like Vercel. 
> 3. **Containerization**: My FastAPI backend is completely decoupled, meaning it will be packaged into a Docker Image and deployed natively onto an AWS EC2 instance (or EKS) to allow for horizontal auto-scaling during heavy retail seasons!"*

---

## 🛠 Tech Stack Details

* **Frontend:** React (Next.js 14), Recharts (Dynamic Visualization), Tailwind/Vanilla CSS (Premium UI aesthetics).
* **Backend:** FastAPI, Python 3.12, SQLAlchemy, Pydantic.
* **Data Engineering:** PostgreSQL (OLTP), Google BigQuery (Data Warehouse), Pandas.
* **Machine Learning:** XGBoost (Regression), LightGBM (Gradient Boosting), Scikit-Learn.
* **MLOps & Orchestration:** MLflow (Model Tracking/Registry), Prefect (Automated DAG pipelines).
* **Monitoring & DevOps:** Prometheus (Metric Logging), Grafana (Time-series alerts), GitHub Actions (CI/CD), Docker.

# 🚀 SmartShelf — Next Steps Checklist

Everything below is what you need to do **after your presentation** to take this from a local demo to a production-hosted platform.

---

## 1. 🧠 Train Your ML Models (CRITICAL — Do This First!)

Your MLflow registry currently shows models as "NOT REGISTERED" because they haven't been trained yet. This is why prediction buttons return 503 errors.

```bash
# Activate environment
cd C:\Users\parth\Desktop\Projects\MLOPS\smartshelf-mlops
.\venv\Scripts\activate
$env:PYTHONPATH="src"

# Run the full training pipeline
python src/smartshelf/flows/training_flow.py
```

**After this runs**, check:
- [ ] Open MLflow UI at `http://localhost:5000` → Models tab should show `Demand_Model`, `Price_Model`, `Inventory_Model`
- [ ] Admin Panel model registry table should now show real versions, RMSE, and training dates
- [ ] Predictions Lab should return actual forecasts
- [ ] Critical Stock "Generate Prediction List" should populate the table

---

## 2. 📊 Verify BigQuery Data Warehouse

```bash
# Run the DB → BigQuery sync
python src/smartshelf/flows/feature_flow.py
```

**Check in Google Cloud Console:**
- [ ] Go to `https://console.cloud.google.com/bigquery?project=smartshelf-493319`
- [ ] Verify dataset `smartshelf_1st_dataset` has tables synced from PostgreSQL
- [ ] Check row counts match your local PostgreSQL tables
- [ ] Ensure `GOOGLE_APPLICATION_CREDENTIALS` is set in your `.env` pointing to the service account key

---

## 3. 🔍 Verify PostgreSQL Database

```bash
# Quick health check via API
curl http://localhost:8000/health
```

**Manual checks:**
- [ ] Confirm 12 tables exist: `products`, `categories`, `stores`, `sales_orders`, `sales_order_items`, `inventory`, `suppliers`, `promotions`, `weather`, `calendar`, `economic_data`, `competitor_pricing`
- [ ] The `categories` table is currently **empty** — you should populate it to get category names on the dashboard
- [ ] Run: `INSERT INTO categories (category_id, category_name) SELECT DISTINCT category_id, 'Category ' || category_id FROM products;` to auto-populate

---

## 4. 🔄 Prefect Orchestration

**For the presentation (manual trigger):**
```bash
python src/smartshelf/flows/training_flow.py
```

**For production (automated scheduling):**
```bash
# Install and start Prefect server
pip install prefect
prefect server start                    # UI at http://localhost:4200

# Create the deployment
prefect deployment build src/smartshelf/flows/training_flow.py:weekly_training_flow \
  -n weekly-training -q default --cron "0 4 * * 0"   # Every Sunday 4 AM

# Apply and start the agent
prefect deployment apply weekly_training_flow-deployment.yaml
prefect agent start -q default
```

- [ ] Verify flow appears at `http://localhost:4200/deployments`
- [ ] Trigger a manual run from the Prefect UI to validate

---

## 5. 📈 Monitoring Stack (Prometheus + Grafana)

```bash
# Start monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

- [ ] Prometheus at `http://localhost:9090` — query `smartshelf_request_count` 
- [ ] Grafana at `http://localhost:3001` (login: admin / smartshelf)
- [ ] Import the dashboard JSON from `grafana/dashboards/`
- [ ] Verify FastAPI metrics are flowing: check `http://localhost:8000/metrics`

---

## 6. 🐙 GitHub — Pre-Push Checklist

```bash
# Make sure .gitignore is covering everything
git status

# These should NOT appear in git status:
# - .env, smartshelf-secret-key.json
# - mlflow.db, mlflow_artifacts/, mlruns/
# - venv/, __pycache__/
# - frontend/node_modules/, frontend/.next/
# - data/raw/*.csv, data/processed/*.parquet
```

- [ ] Remove any accidentally tracked files: `git rm --cached <file>`
- [ ] Verify `.github/workflows/ci.yml` and `cd.yml` are present
- [ ] Push: `git add . && git commit -m "production-ready" && git push origin main`
- [ ] Check GitHub Actions tab for CI pipeline results

---

## 7. 🐳 Docker Containerization (Backend)

```bash
# Build the Docker image
docker build -t smartshelf-api:latest .

# Test it locally
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://postgres:1246@host.docker.internal:5432/smartshelf \
  -e MLFLOW_TRACKING_URI=http://host.docker.internal:5000 \
  smartshelf-api:latest
```

- [ ] Verify `http://localhost:8000/health` returns healthy
- [ ] Verify Dockerfile is correct and builds cleanly
- [ ] Tag for registry: `docker tag smartshelf-api:latest <your-ecr-repo>/smartshelf-api:latest`

---

## 8. ☁️ AWS EC2 Deployment (Backend)

### a) Launch EC2 Instance
- [ ] AMI: Ubuntu 22.04 LTS
- [ ] Instance type: t3.medium (2 vCPU, 4 GB RAM)
- [ ] Security group: open ports 8000 (API), 5000 (MLflow), 9090 (Prometheus), 3001 (Grafana)

### b) Setup on EC2
```bash
# SSH into instance
ssh -i your-key.pem ubuntu@<ec2-ip>

# Install Docker
sudo apt update && sudo apt install -y docker.io docker-compose
sudo usermod -aG docker ubuntu

# Pull and run
docker pull <your-ecr-repo>/smartshelf-api:latest
docker run -d -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  smartshelf-api:latest
```

### c) Database Options
- [ ] **Option A**: Install PostgreSQL on EC2 directly
- [ ] **Option B**: Use Amazon RDS (managed, recommended for production)
- [ ] **Option C**: Use Google Cloud SQL (if staying on GCP)

---

## 9. 🌐 Vercel Deployment (Frontend)

```bash
# From the frontend directory
cd frontend

# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

**Environment variable to set on Vercel:**
```
NEXT_PUBLIC_API_URL=http://<your-ec2-ip>:8000
```

- [ ] Set the env var in Vercel dashboard → Settings → Environment Variables
- [ ] Verify the deployed URL connects to your EC2 backend
- [ ] Update CORS in `main.py` to include your Vercel domain

---

## 10. 🔁 CI/CD Pipeline Finalization

The CI pipeline (`.github/workflows/ci.yml`) already runs tests on push. To complete:

- [ ] Add `DATABASE_URL` and `MLFLOW_TRACKING_URI` as GitHub Secrets
- [ ] Enable branch protection on `main` requiring CI to pass
- [ ] For CD: configure ECR push + EC2 deploy in `cd.yml` with your AWS credentials as GitHub Secrets

---

## Priority Order

| Priority | Task | Time Estimate |
|----------|------|--------------|
| 🔴 P0 | Train models (Step 1) | 5-15 min |
| 🔴 P0 | Populate categories table (Step 3) | 2 min |
| 🟡 P1 | BigQuery sync verification (Step 2) | 10 min |
| 🟡 P1 | GitHub push (Step 6) | 5 min |
| 🟢 P2 | Docker build (Step 7) | 15 min |
| 🟢 P2 | Prefect scheduling (Step 4) | 10 min |
| 🔵 P3 | AWS EC2 deploy (Step 8) | 30-60 min |
| 🔵 P3 | Vercel deploy (Step 9) | 10 min |
| 🔵 P3 | Monitoring setup (Step 5) | 15 min |
